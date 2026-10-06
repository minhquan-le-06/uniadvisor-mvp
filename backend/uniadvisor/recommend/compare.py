"""Multi-criteria comparison: turn engine numbers + SLM answers into criteria scores in [0, 1],
weight them by the student's goal profile, cluster programs into criteria, and explain trade-offs."""

from __future__ import annotations

import numpy as np

from uniadvisor.student.slm.infer import Answer
from uniadvisor.student.slm.questions import INSUFFICIENT

CRITERIA = {
    "fit": "Hợp sở thích",
    "ability": "Hợp năng lực",
    "tuition": "Học phí",
    "location": "Địa điểm",
    "selectivity": "Độ cạnh tranh / uy tín",
}
BASE_WEIGHTS = {"fit": 0.35, "ability": 0.15, "tuition": 0.15, "location": 0.15, "selectivity": 0.20}
PRIORITY_TO_CRITERION = {
    "nganh_yeu_thich": "fit",
    "truong_danh_tieng": "selectivity",
    "hoc_phi_thap": "tuition",
    "gan_nha": "location",
    "viec_lam_thu_nhap": "selectivity",
}
NEUTRAL = 0.5


def rank_criteria_by_user(profile, top_priority: str | None = None) -> list[dict]:
    """Xếp hạng 5 đặc trưng từ quan trọng nhất đến thấp nhất dựa trên hồ sơ thí sinh."""
    scores = {k: 1.0 for k in CRITERIA}
    reasons = {k: "Tiêu chí cân nhắc bổ sung" for k in CRITERIA}

    # 1. Dựa trên danh sách priorities từ JSON profile
    priorities = getattr(profile, "priorities", []) or []
    for rank_idx, prio in enumerate(priorities):
        crit = PRIORITY_TO_CRITERION.get(prio)
        if crit:
            boost = (len(priorities) - rank_idx) * 2.0
            scores[crit] += boost
            reasons[crit] = f"Ưu tiên số {rank_idx + 1} được bạn lựa chọn trong hồ sơ"

    # 2. Xử lý ưu tiên hàng đầu từ SLM nếu chưa có
    if top_priority in PRIORITY_TO_CRITERION:
        crit = PRIORITY_TO_CRITERION[top_priority]
        scores[crit] += 2.5
        if crit not in reasons or "bổ sung" in reasons[crit]:
            reasons[crit] = "SLM đánh giá là mối quan tâm hàng đầu của bạn"

    # 3. Ràng buộc ngân sách nghiêm ngặt
    budget = getattr(profile, "budget", None)
    if budget and getattr(budget, "strict", False):
        scores["tuition"] += 2.0
        reasons["tuition"] = "Gia đình có trần ngân sách nghiêm ngặt, học phí là yếu tố quyết định"

    # 4. Khẩu vị an toàn đẩy tiêu chí Hợp năng lực lên
    risk = getattr(profile, "risk", None)
    if risk == "an_toan":
        scores["ability"] += 1.8
        reasons["ability"] = "Bạn chọn hướng an toàn, cần ưu tiên ngành vừa sức để nắm chắc cơ hội"
    elif risk == "mao_hiem":
        scores["selectivity"] += 1.5
        reasons["selectivity"] = "Bạn sẵn sàng thử sức với các trường top có tính cạnh tranh cao"

    ranked_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    return [
        {
            "criterion": k,
            "name_vi": CRITERIA[k],
            "rank": idx + 1,
            "weight_score": round(scores[k], 2),
            "reason": reasons[k],
        }
        for idx, k in enumerate(ranked_keys)
    ]


def weights_for(top_priority: str | None, override: dict[str, float] | None = None) -> dict[str, float]:
    w = dict(BASE_WEIGHTS)
    if override:
        w.update({k: float(v) for k, v in override.items() if k in w})
    elif top_priority in PRIORITY_TO_CRITERION:
        w[PRIORITY_TO_CRITERION[top_priority]] *= 2.5
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


def _level01(a: Answer | None) -> float:
    if a is None:
        return NEUTRAL
    lvl = a.expected_level()
    if lvl is None:
        return NEUTRAL
    suff = 1 - a.p(INSUFFICIENT)
    return float(suff * (lvl - 1) / 4 + (1 - suff) * NEUTRAL)


def _yes01(a: Answer | None, prior: float = NEUTRAL) -> float:
    if a is None:
        return prior
    return float(a.p("yes") + a.p(INSUFFICIENT) * prior)


def criteria(program: dict, forecast_score: float | None, answers: dict[str, Answer], tuition_rank: float | None) -> dict[str, float]:
    tuition_prior = NEUTRAL if tuition_rank is None else 1.0 - 0.6 * tuition_rank
    sel = NEUTRAL if forecast_score is None else float(np.clip((forecast_score - 15.0) / 14.0, 0, 1))
    return {
        "fit": _level01(answers.get("interest_fit")),
        "ability": _level01(answers.get("ability_fit")),
        "tuition": _yes01(answers.get("budget_ok"), tuition_prior),
        "location": _yes01(answers.get("location_ok"), 0.6),
        "selectivity": sel,
    }


def utility(crit: dict[str, float], weights: dict[str, float], conditions: Answer | None) -> float:
    u = sum(weights[k] * crit[k] for k in weights)
    if conditions is not None:
        u *= 1.0 - 0.8 * conditions.p("no")
    return float(np.clip(u, 0, 1))


def wins_losses(crit: dict[str, float], others: list[dict[str, float]], margin: float = 0.12) -> tuple[list[str], list[str]]:
    wins, losses = [], []
    if not others:
        return wins, losses
    for k in CRITERIA:
        med = float(np.median([o[k] for o in others]))
        if crit[k] >= med + margin:
            wins.append(CRITERIA[k])
        elif crit[k] <= med - margin:
            losses.append(CRITERIA[k])
    return wins, losses


def generate_triple_explanation(ev: dict, criterion_key: str, cluster_programs: list[dict], profile) -> dict[str, str]:
    """Tạo bộ giải thích 3 tầng: Liên đặc trưng, Nội đặc trưng và Khớp hồ sơ."""
    crit_scores = ev["criteria"]
    target_name = CRITERIA[criterion_key]

    # Tầng 1: Tại sao ngành này ở đặc trưng này mà không phải đặc trưng khác?
    other_crits = {k: v for k, v in crit_scores.items() if k != criterion_key}
    max_other_k = max(other_crits, key=other_crits.get)
    diff = crit_scores[criterion_key] - other_crits[max_other_k]
    if diff >= 0.1:
        cross_exp = (
            f"Điểm {target_name} ({crit_scores[criterion_key]:.2f}) là ưu điểm vượt trội nhất của ngành này, "
            f"áp đảo so với các khía cạnh khác (như {CRITERIA[max_other_k]}: {other_crits[max_other_k]:.2f})."
        )
    elif ev.get("is_core", False):
        cross_exp = (
            f"Ngành này đại diện tiêu biểu cho hướng {target_name} với chỉ số đạt {crit_scores[criterion_key]:.2f}/1.0."
        )
    else:
        cross_exp = (
            f"Ngành đóng vai trò cầu nối: vừa đạt tiêu chí {target_name} ở mức tốt ({crit_scores[criterion_key]:.2f}), "
            f"vừa nằm gần tâm cân bằng (Hợp năng lực: {crit_scores['ability']:.2f}) giúp bạn dễ dàng đưa vào danh sách chọn."
        )

    # Tầng 2: So sánh hơn / thua với các ngành trong cùng đặc trưng
    peer_criteria = [p["criteria"] for p in cluster_programs if p["program"]["program_id"] != ev["program"]["program_id"]]
    w, l = wins_losses(crit_scores, peer_criteria, margin=0.10)
    intra_parts = []
    if w:
        intra_parts.append(f"ưu thế hơn các ngành cùng nhóm về {', '.join(w)}")
    if l:
        intra_parts.append(f"cần đánh đổi hoặc thấp hơn mặt bằng chung nhóm về {', '.join(l)}")
    intra_exp = (
        f"Trong nhóm {target_name}, ngành này " + (" và ".join(intra_parts) if intra_parts else "có các chỉ số đồng đều với mặt bằng chung.")
    )

    # Tầng 3: Khớp hồ sơ thí sinh
    p_admit_pct = round(ev["p_admit"] * 100, 1)
    bucket_text = ev.get("bucket", "match")
    bucket_vi = {"safe": "An toàn", "match": "Vừa sức", "reach": "Thử thách", "unlikely": "Khó đỗ"}.get(bucket_text, bucket_text)
    user_exp = (
        f"Với điểm xét tuyển {ev['total']} (tổ hợp {ev['combo']}), bạn có {p_admit_pct}% cơ hội đỗ (nhóm {bucket_vi}, "
        f"dự báo điểm chuẩn {ev['forecast'].score}). "
    )
    if ev["program"].get("tuition_min"):
        user_exp += f"Học phí khoảng {ev['program']['tuition_min']:.1f} tr/năm. "
    if ev.get("flags"):
        user_exp += f"Lưu ý: {'; '.join(ev['flags'])}."

    return {
        "cross_criteria": cross_exp,
        "intra_criterion": intra_exp,
        "user_fit": user_exp.strip(),
    }


def cluster_programs_by_criteria(evals: list[dict], profile, core_range: tuple[int, int] = (4, 4), sec_range: tuple[int, int] = (4, 4)) -> dict:
    """Chia tập ứng viên thành 5 cụm (6-10 ngành mỗi cụm: 3-5 ngành chính + 3-5 ngành phụ gần tâm)."""
    clusters = {}
    for crit_key in CRITERIA:
        # 1. Chọn 3-5 ngành chính (Core): Điểm đặc trưng cao nhất, phân bổ đa dạng trường (tối đa 2 ngành/trường)
        sorted_core = sorted(evals, key=lambda ev: (ev["criteria"][crit_key], ev["utility"], ev["p_admit"]), reverse=True)
        core_picks = []
        school_counts = {}
        for ev in sorted_core:
            s_code = ev["program"]["school_code"]
            if school_counts.get(s_code, 0) < 2:
                item = dict(ev)
                item["is_core"] = True
                core_picks.append(item)
                school_counts[s_code] = school_counts.get(s_code, 0) + 1
            if len(core_picks) >= core_range[1]:
                break

        core_ids = {p["program"]["program_id"] for p in core_picks}

        # 2. Chọn 3-5 ngành phụ (Secondary - gần tâm lăng kính):
        # Điểm đặc trưng crit_key vẫn tốt, nhưng ability cao và xác suất đỗ an toàn/vừa sức để dễ dàng gộp danh sách
        remaining = [ev for ev in evals if ev["program"]["program_id"] not in core_ids]
        sorted_sec = sorted(
            remaining,
            key=lambda ev: (
                0.35 * ev["criteria"][crit_key]
                + 0.35 * ev["criteria"]["ability"]
                + 0.30 * min(ev["p_admit"], 0.85)
            ),
            reverse=True,
        )
        sec_picks = []
        sec_schools = dict(school_counts)
        for ev in sorted_sec:
            s_code = ev["program"]["school_code"]
            if sec_schools.get(s_code, 0) < 3:
                item = dict(ev)
                item["is_core"] = False
                sec_picks.append(item)
                sec_schools[s_code] = sec_schools.get(s_code, 0) + 1
            if len(sec_picks) >= sec_range[1]:
                break

        all_in_cluster = core_picks + sec_picks

        # 3. Tạo giải thích 3 tầng và vector ngũ giác cho từng ngành trong cụm
        for p in all_in_cluster:
            p["triple_explanation"] = generate_triple_explanation(p, crit_key, all_in_cluster, profile)
            p["radar_vector"] = {k: round(v, 2) for k, v in p["criteria"].items()}

        clusters[crit_key] = {
            "criterion": crit_key,
            "name_vi": CRITERIA[crit_key],
            "core_programs": core_picks,
            "secondary_programs": sec_picks,
            "programs": all_in_cluster,  # Tổng cộng 6 - 10 ngành
            "count": len(all_in_cluster),
        }

    return clusters