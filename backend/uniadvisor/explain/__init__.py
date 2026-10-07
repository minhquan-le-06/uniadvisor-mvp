"""Vietnamese explanations built from engine values and typed student judgments only.

This module deliberately receives plain evaluation dictionaries from ``Advice``.  It does
not calculate admission probabilities, make regulatory claims, or generate facts that
are absent from those dictionaries.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from uniadvisor.recommend.compare import CRITERIA, wins_losses
from uniadvisor.recommend.rules import BUCKET_VI

DISCLAIMER = (
    "Kết quả chỉ mang tính tham khảo. Xác suất được ước tính từ điểm chuẩn các năm trước và có thể sai khi đề thi, "
    "chỉ tiêu hay quy chế thay đổi. Em cần đối chiếu với đề án tuyển sinh và quy chế chính thức của Bộ GD&ĐT và "
    "của từng trường trước khi đăng ký nguyện vọng."
)


def pct(p: float) -> str:
    return f"{100 * p:.0f}%"


def confidence_label(forecast_sigma: float, latest_status: str, slm_escalations: int,
                     tuition_estimated: bool) -> tuple[str, list[str]]:
    """Describe confidence from the forecast uncertainty fitted by the engine.

    ``forecast_sigma`` is the forecast model's measured residual scale, not a reward
    for having more historical rows.  Source disagreement and uncertain soft judgments
    can still lower the label because they affect what the student sees alongside the
    forecast.
    """
    reasons = [f"độ bất định dự báo ước tính khoảng ±{forecast_sigma:.2f} điểm"]
    score = 2 if forecast_sigma <= 1.3 else 1 if forecast_sigma <= 1.6 else 0
    if latest_status == "confirmed_2_sources":
        score += 1
    elif latest_status == "disputed":
        score -= 1
        reasons.append("hai nguồn báo điểm chuẩn khác nhau")
    else:
        reasons.append("điểm chuẩn gần nhất chỉ có 1 nguồn")
    if slm_escalations:
        score -= 1
        reasons.append(f"{slm_escalations} nhận định về độ phù hợp chưa chắc chắn")
    if tuition_estimated:
        reasons.append("học phí là ước tính theo mức chung của trường")
    label = "cao" if score >= 3 else "trung bình" if score >= 1 else "thấp"
    return label, reasons


def program_explanation(ev: dict) -> str:
    fc = ev["forecast"]
    lo, hi = ev["cutoff_interval"]
    hist = ", ".join(f"{y}: {s:g}" for y, s in zip(fc.years, fc.past_scores))
    parts = [
        f"Dự báo điểm chuẩn {fc.target_year}: khoảng {fc.score:.2f} (80% khả năng trong {lo:.2f}–{hi:.2f}); "
        f"lịch sử THPT: {hist}.",
        f"Điểm xét của em: {ev['total']:.2f} (tổ hợp {ev['combo']}: {ev['raw_total']:.2f}"
        + (f" + ưu tiên {ev['priority']:.2f}" if ev["priority"] else "") + f") → xác suất đỗ ≈ {pct(ev['p_admit'])} "
        f"({BUCKET_VI[ev['bucket']]}).",
    ]
    if fc.top_share == fc.top_share:
        # The percentile is calculated from the forecast reference combination.  Keep it
        # in its own sentence so it can never be read as a percentile for the student's
        # (possibly different) admission combination.
        parts.append(
            f"Trên thang phân bố của tổ hợp tham chiếu {fc.ref_combo} năm {fc.dist_year}, "
            f"mức dự báo này thuộc nhóm {pct(fc.top_share)} thí sinh có điểm cao nhất."
        )
    if ev["wins"]:
        parts.append("Mạnh hơn các lựa chọn đã chọn khác ở: " + ", ".join(ev["wins"]) + ".")
    if ev["losses"]:
        parts.append("Kém hơn các lựa chọn đã chọn khác ở: " + ", ".join(ev["losses"]) + ".")
    if ev["flags"]:
        parts.append("Lưu ý: " + "; ".join(ev["flags"]) + ".")
    return " ".join(parts)


def _criterion_changes(first: dict, second: dict, weights: dict[str, float]) -> list[str]:
    """Positive weighted criterion differences, strongest first, as display labels."""
    changes = sorted(
        ((weights.get(k, 0.0) * (first["criteria"][k] - second["criteria"][k]), CRITERIA[k]) for k in CRITERIA),
        reverse=True,
    )
    return [label for delta, label in changes if delta > 1e-9]


def ranking_reasons(chosen: list[dict], weights: dict[str, float]) -> list[str]:
    """One factual ordering explanation for every selected wish.

    The optimiser orders a fixed set by descending utility.  We expose its actual
    utility and the weighted criteria that distinguish adjacent wishes rather than
    inferring that rank one is automatically the best interest match.
    """
    out: list[str] = []
    for index, ev in enumerate(chosen):
        rank = index + 1
        if index == len(chosen) - 1:
            out.append(f"NV{rank} có độ phù hợp tổng hợp u={ev['utility']:.2f}; đây là vị trí cuối trong danh sách đã chọn.")
            continue
        below = chosen[index + 1]
        gains = _criterion_changes(ev, below, weights)
        if gains:
            why = "; tiêu chí tạo khác biệt là " + ", ".join(gains[:2])
        elif ev["utility"] > below["utility"] + 1e-9:
            why = "; khác biệt đến từ điều kiện riêng hoặc các điểm tiêu chí chưa đủ lớn để nêu riêng"
        elif ev["p_admit"] > below["p_admit"] + 1e-9:
            why = "; hai lựa chọn có cùng độ phù hợp tổng hợp, nên xác suất đỗ cao hơn được dùng để phá hoà"
        else:
            why = "; hai lựa chọn hoà theo các chỉ số hiển thị, nên hệ thống dùng mã ngành để phá hoà ổn định"
        out.append(
            f"NV{rank} đứng trên NV{rank + 1} vì u={ev['utility']:.2f} cao hơn "
            f"u={below['utility']:.2f}{why}."
        )
    return out


def _expected_value(rows: Iterable[dict]) -> float:
    value, miss = 0.0, 1.0
    for row in rows:
        value += miss * row["p_admit"] * row["utility"]
        miss *= 1 - row["p_admit"]
    return value


def alternative_reason(ev: dict, chosen: list[dict], weights: dict[str, float], min_safe: int,
                       max_per_school: int) -> str:
    """Explain an excluded option without inventing an optimiser decision.

    When a direct one-for-one replacement is feasible, the explanation reports the
    measured expected-utility comparison.  Otherwise it reports the exact automatic
    exclusion or constraint visible in the input.
    """
    name = ev["program"]["program_name"]
    if ev["bucket"] == "unlikely":
        return f"{name} không được tự động đưa vào danh sách vì thuộc nhóm khó đỗ (xác suất ≈ {pct(ev['p_admit'])})."

    baseline = _expected_value(chosen)
    feasible: list[tuple[float, int, list[dict]]] = []
    for i in range(len(chosen)):
        candidate = [*chosen[:i], ev, *chosen[i + 1:]]
        if sum(row["bucket"] == "safe" for row in candidate) < min_safe:
            continue
        schools = Counter(row["program"]["school_code"] for row in candidate)
        if schools and max(schools.values()) > max_per_school:
            continue
        ordered = sorted(candidate, key=lambda row: (-row["utility"], -row["p_admit"], row["program"]["program_id"]))
        feasible.append((_expected_value(ordered), i, ordered))
    if feasible:
        replacement_value, removed_index, _ = max(feasible, key=lambda item: item[0])
        removed = chosen[removed_index]
        if replacement_value < baseline - 1e-9:
            differences = _criterion_changes(removed, ev, weights)
            detail = f" Bất lợi rõ so với NV{removed_index + 1} là " + ", ".join(differences[:2]) + "." if differences else ""
            return (
                f"Nếu thay NV{removed_index + 1} bằng lựa chọn này, độ hữu ích kỳ vọng của cả danh sách giảm "
                f"từ {baseline:.3f} xuống {replacement_value:.3f}.{detail}"
            )

    schools = Counter(row["program"]["school_code"] for row in chosen)
    school = ev["program"]["school_code"]
    if schools[school] >= max_per_school:
        return f"Danh sách đã có {schools[school]} nguyện vọng của trường {school}, bằng giới hạn {max_per_school} nguyện vọng mỗi trường."
    if sum(row["bucket"] == "safe" for row in chosen) <= min_safe and ev["bucket"] != "safe":
        return f"Danh sách cần giữ ít nhất {min_safe} nguyện vọng an toàn; lựa chọn này thuộc nhóm {BUCKET_VI[ev['bucket']]}."
    return (
        f"Lựa chọn này không nằm trong tập tối ưu hiện tại (u={ev['utility']:.2f}, xác suất đỗ ≈ {pct(ev['p_admit'])}); "
        "em có thể cân nhắc nếu muốn đổi ưu tiên hoặc trọng số tiêu chí."
    )


def judgment_evidence(profile, ev: dict) -> dict[str, list[str]]:  # noqa: ANN001
    """Student sentences that substantiate the typed judgments when Module 2 found them.

    Evidence is deliberately omitted when the intent reader has no matching fact; a
    missing quote is more honest than presenting an unrelated sentence as evidence.
    """
    from uniadvisor.student.intent import covers, extract

    intent = extract(profile.free_text)
    out: dict[str, list[str]] = {}
    code = ev["program"].get("major_code") or ""
    interest = next((x.evidence for x in intent.interests if any(covers(c, code) for c in x.codes)), None)
    dislike = next((x.evidence for x in intent.dislikes if any(covers(c, code) for c in x.codes)), None)
    if interest or dislike:
        out["interest_fit"] = [interest or dislike]
    if intent.budget:
        out["budget_ok"] = [intent.budget.evidence]
    if intent.location:
        out["location_ok"] = [intent.location.evidence]
    return out


def triple_explanation(ev: dict, criterion_key: str, cluster_programs: list[dict]) -> dict[str, str]:
    """Explain a program's place in a numeric Module 3 criterion cluster.

    The cluster, criterion scores, forecast and admission probability are produced by
    Module 3.  This function only turns those supplied values into Vietnamese prose.
    """
    scores = ev["criteria"]
    criterion_name = CRITERIA[criterion_key]

    other_scores = {key: value for key, value in scores.items() if key != criterion_key}
    strongest_other = max(other_scores, key=other_scores.get)
    if scores[criterion_key] - other_scores[strongest_other] >= 0.1:
        cross_criteria = (
            f"Điểm {criterion_name} ({scores[criterion_key]:.2f}) là ưu điểm nổi bật nhất của ngành này, "
            f"cao hơn {CRITERIA[strongest_other]} ({other_scores[strongest_other]:.2f})."
        )
    elif ev.get("is_core", False):
        cross_criteria = f"Ngành này là lựa chọn tiêu biểu trong hướng {criterion_name}, với chỉ số {scores[criterion_key]:.2f}/1.0."
    else:
        cross_criteria = (
            f"Ngành này là lựa chọn cân bằng trong hướng {criterion_name}: chỉ số {scores[criterion_key]:.2f}/1.0 "
            f"và Hợp năng lực {scores['ability']:.2f}/1.0."
        )

    peers = [row["criteria"] for row in cluster_programs if row["program"]["program_id"] != ev["program"]["program_id"]]
    wins, losses = wins_losses(scores, peers, margin=0.10)
    comparisons = []
    if wins:
        comparisons.append("nhỉnh hơn nhóm về " + ", ".join(wins))
    if losses:
        comparisons.append("cần đánh đổi ở " + ", ".join(losses))
    intra_criterion = (
        f"Trong nhóm {criterion_name}, ngành này "
        + ("; ".join(comparisons) if comparisons else "có các chỉ số gần với mặt bằng chung")
        + "."
    )

    user_fit = (
        f"Điểm xét {ev['total']:.2f} theo tổ hợp {ev['combo']}; xác suất đỗ ≈ {pct(ev['p_admit'])} "
        f"({BUCKET_VI[ev['bucket']]}), dự báo điểm chuẩn {ev['forecast'].score:.2f}."
    )
    fee = ev["program"].get("tuition_min")
    if fee:
        user_fit += f" Học phí khoảng {fee / 1e6:.1f} triệu đồng/năm."
    if ev.get("flags"):
        user_fit += " Lưu ý: " + "; ".join(ev["flags"]) + "."

    return {"cross_criteria": cross_criteria, "intra_criterion": intra_criterion, "user_fit": user_fit}


def enrich_advice(advice, max_per_school: int = 4):  # noqa: ANN001
    """Attach Module 4 display fields to Module 3's current ``Advice`` output.

    Module 3 owns the calculations and returns only engine values.  This adapter is
    intentionally called at presentation boundaries (Streamlit/API), so Module 4 can
    tolerate structural additions to ``Advice`` without taking ownership of the
    recommendation engine.
    """
    chosen = advice.chosen
    alternatives = advice.alternatives
    selected_criteria = [ev["criteria"] for ev in chosen]

    for ev in chosen + alternatives:
        # Current Module 3 supplies flags and confidence, but not the comparative
        # fields used by the legacy list presentation.
        others = [criteria for criteria in selected_criteria if criteria is not ev["criteria"]]
        ev["wins"], ev["losses"] = wins_losses(ev["criteria"], others)
        ev.setdefault("flags", [])
        ev["judgment_evidence"] = judgment_evidence(advice.profile, ev)
        ev["explanation"] = program_explanation(ev)

    for ev, reason in zip(chosen, ranking_reasons(chosen, advice.weights)):
        ev["ranking_reason"] = reason
    for ev in alternatives:
        ev["alternative_reason"] = alternative_reason(
            ev, chosen, advice.weights, advice.constraints["min_safe"], max_per_school
        )
    for criterion_key, cluster in getattr(advice, "criteria_clusters", {}).items():
        programs = cluster.get("programs", [])
        for ev in programs:
            ev["triple_explanation"] = triple_explanation(ev, criterion_key, programs)
    return advice


def list_summary(chosen: list[dict], p_any: float, expected: float, min_safe: int, score_kind: str,
                 weights: dict[str, float] | None = None) -> str:
    counts = {b: sum(1 for c in chosen if c["bucket"] == b) for b in ("safe", "match", "reach", "unlikely")}
    s = (f"Danh sách {len(chosen)} nguyện vọng: {counts['safe']} an toàn, {counts['match']} vừa sức, {counts['reach']} thử thách"
         + (f", {counts['unlikely']} khó đỗ" if counts["unlikely"] else "") + ". "
         f"Xác suất đỗ ít nhất một nguyện vọng ≈ {pct(p_any)}" + (" (mô phỏng cả biến động của điểm thi dự kiến)" if score_kind == "mock" else "") + ". "
         "Nguyện vọng được xếp theo độ phù hợp tổng hợp (u) giảm dần; với cùng tập ngành, thứ tự này tối đa hoá độ hữu ích kỳ vọng "
         "và em sẽ trúng tuyển nguyện vọng cao nhất mà em đủ điểm.")
    if len(chosen) > 1 and weights:
        top_reasons = _criterion_changes(chosen[0], chosen[1], weights)
        if top_reasons:
            s += f" NV1 đứng trên NV2 chủ yếu nhờ {', '.join(top_reasons[:2])}, không mặc định vì hợp sở thích hơn."
    if counts["safe"] < min_safe:
        s += f" Chưa đủ {min_safe} nguyện vọng an toàn phù hợp — em nên cân nhắc thêm lựa chọn an toàn."
    return s
