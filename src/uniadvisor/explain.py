"""Vietnamese explanations built only from engine / KB numbers and typed SLM answers (no free generation)."""

from __future__ import annotations

from uniadvisor.kb.rules import BUCKET_VI

DISCLAIMER = (
    "Kết quả chỉ mang tính tham khảo. Xác suất được ước tính từ điểm chuẩn các năm trước và có thể sai khi đề thi, "
    "chỉ tiêu hay quy chế thay đổi. Em cần đối chiếu với đề án tuyển sinh và quy chế chính thức của Bộ GD&ĐT và "
    "của từng trường trước khi đăng ký nguyện vọng."
)


def pct(p: float) -> str:
    return f"{100 * p:.0f}%"


def confidence_label(n_years: int, latest_status: str, slm_escalations: int, tuition_estimated: bool) -> tuple[str, list[str]]:
    reasons = []
    score = 0
    if n_years >= 3:
        score += 2
    elif n_years == 2:
        score += 1
    else:
        reasons.append("chỉ có điểm chuẩn 1 năm")
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
        parts.append(f"Mức dự báo tương đương nhóm {pct(fc.top_share)} thí sinh điểm cao nhất tổ hợp {fc.ref_combo} năm {fc.dist_year}.")
    if ev["wins"]:
        parts.append("Mạnh hơn các lựa chọn khác ở: " + ", ".join(ev["wins"]) + ".")
    if ev["losses"]:
        parts.append("Kém hơn ở: " + ", ".join(ev["losses"]) + ".")
    if ev["flags"]:
        parts.append("Lưu ý: " + "; ".join(ev["flags"]) + ".")
    return " ".join(parts)


def list_summary(chosen: list[dict], p_any: float, expected: float, min_safe: int, score_kind: str) -> str:
    counts = {b: sum(1 for c in chosen if c["bucket"] == b) for b in ("safe", "match", "reach", "unlikely")}
    s = (f"Danh sách {len(chosen)} nguyện vọng: {counts['safe']} an toàn, {counts['match']} vừa sức, {counts['reach']} thử thách"
         + (f", {counts['unlikely']} khó đỗ" if counts["unlikely"] else "") + ". "
         f"Xác suất đỗ ít nhất một nguyện vọng ≈ {pct(p_any)}" + (" (ước tính lạc quan vì điểm của em là điểm dự kiến)" if score_kind == "mock" else "") + ". "
         f"Nguyện vọng được xếp theo mức độ phù hợp giảm dần, vì em sẽ trúng tuyển nguyện vọng cao nhất mà em đủ điểm; "
         f"thứ tự không làm thay đổi khả năng đỗ từng nguyện vọng.")
    if counts["safe"] < min_safe:
        s += f" Chưa đủ {min_safe} nguyện vọng an toàn phù hợp — em nên cân nhắc thêm lựa chọn an toàn."
    if chosen:
        top = chosen[0]
        safest = max(chosen, key=lambda c: c["p_admit"])
        if top is not safest:
            s += (f" Đánh đổi chính: NV1 ({top['program']['program_name']}) hợp em nhất nhưng xác suất đỗ ≈ {pct(top['p_admit'])}; "
                  f"{safest['program']['program_name']} ({safest['program']['school_code']}) gần như chắc chắn ({pct(safest['p_admit'])}) nhưng kém phù hợp hơn.")
    return s
