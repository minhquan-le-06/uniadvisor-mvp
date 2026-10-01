"""The SLM's input: a `state` (student profile + program) rendered as compact Vietnamese text.

The same functions are used to build training data and at inference, so the model always sees the
same format. The JSON form (`state_json`) is kept alongside every training example for auditing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

SUBJECT_VI = {
    "TO": "Toán", "VA": "Văn", "LI": "Lý", "HO": "Hóa", "SI": "Sinh", "SU": "Sử", "DI": "Địa",
    "N1": "Anh", "N2": "Nga", "N3": "Pháp", "N4": "Trung", "N5": "Đức", "N6": "Nhật", "N7": "Hàn",
    "TI": "Tin", "GDKTPL": "KTPL", "CNCN": "CN công nghiệp", "CNNN": "CN nông nghiệp",
}


@dataclass
class StudentProfile:
    scores: dict[str, float] = field(default_factory=dict)  # subject code -> score (0-10)
    province: str | None = None
    area: str = "KV3"                  # KV1 / KV2-NT / KV2 / KV3
    category: str = "none"             # none / UT1 / UT2
    gender: str | None = None          # nam / nu
    score_kind: str = "actual"         # actual (real exam) | mock (thi thử / dự kiến)
    free_text: str = ""                # the student's messages, one per line, newest last
    years_since_graduation: int = 0
    answers: dict[str, str] = field(default_factory=dict)  # answers the student gave to clarifying questions

    def to_dict(self) -> dict:
        return asdict(self)


def profile_text(p: StudentProfile | dict) -> str:
    d = p.to_dict() if isinstance(p, StudentProfile) else p
    scores = ", ".join(f"{SUBJECT_VI.get(k, k)} {v:g}" for k, v in (d.get("scores") or {}).items())
    parts = [f"Điểm {'thi thử' if d.get('score_kind') == 'mock' else 'thi'}: {scores or 'chưa có'}."]
    if d.get("province"):
        parts.append(f"Nhà ở: {d['province']}.")
    if d.get("gender"):
        parts.append(f"Giới tính: {'nam' if d['gender'] == 'nam' else 'nữ'}.")
    answers = d.get("answers") or {}
    if answers:
        parts.append("Trả lời thêm: " + "; ".join(f"{k}={v}" for k, v in answers.items()) + ".")
    parts.append(f"Học sinh chia sẻ: {(d.get('free_text') or '').strip() or '(không chia sẻ gì)'}")
    return " ".join(parts)


def _money(v: float | None) -> str:
    return f"{v / 1e6:.0f}" if v else "?"


def _val(r: dict, key: str):  # noqa: ANN202
    """r[key], with pandas NaN treated as missing (NaN is truthy and would render as 'nan')."""
    v = r.get(key)
    return None if isinstance(v, float) and v != v else v


def program_text(r: dict) -> str:
    r = {k: _val(r, k) for k in r}
    tmin, tmax = r.get("tuition_min"), r.get("tuition_max")
    if tmin and tmin == tmin:  # not NaN
        fee = f"{_money(tmin)}-{_money(tmax)} triệu/năm" if tmax and tmax != tmin else f"{_money(tmin)} triệu/năm"
        if r.get("tuition_imputed") in (True, "True"):
            fee += " (ước tính theo mức chung của trường)"
    else:
        fee = "không rõ"
    kind = {"standard": "chuẩn", "high_quality": "chất lượng cao", "advanced": "tiên tiến", "international": "liên kết/quốc tế"}.get(r.get("kind"), "chuẩn")
    where = r.get("campus") or r.get("city") or ""
    cond = r.get("conditions") or ""
    cond = cond if isinstance(cond, str) and cond else "không có"
    return (f"Ngành: {r.get('program_name')} - {r.get('school_name')}. Lĩnh vực: {r.get('field_name') or 'khác'}. "
            f"Nơi học: {where}. Chương trình: {kind}. Học phí: {fee}. Điều kiện riêng: {cond}.")


def model_input(question_text: str, profile: StudentProfile | dict, program: dict | None) -> tuple[str, str]:
    """(text_a, text_b) pair for the cross-encoder."""
    a = f"Câu hỏi: {question_text} Hồ sơ: {profile_text(profile)}"
    b = program_text(program) if program is not None else "Câu hỏi về hồ sơ, không gắn với ngành cụ thể."
    return a, b
