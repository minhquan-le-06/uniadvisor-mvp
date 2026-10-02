"""The major-group suggester for "Em chưa biết" (docs/MODEL.md): its questionnaire and its one entry point.

The questionnaire below is the model's input contract; the guided chat renders it. The model itself is not built
yet: until artifacts/models/suggester/ holds a trained model, `available()` is False and `suggest` returns [], and the
chat sends the student to the picker instead.
"""

from __future__ import annotations

from unidata.db import Database
from unidata.paths import MODELS

MODEL_DIR = MODELS / "suggester"

MAX_SUBJECTS = 3
MAX_WORK_TYPES = 2

WORK_TYPES = {
    "R": "Làm với máy móc, dụng cụ, xây dựng, sửa chữa",
    "I": "Tìm hiểu, nghiên cứu, giải bài toán khó",
    "A": "Sáng tạo: vẽ, viết, thiết kế, âm nhạc",
    "S": "Giúp đỡ, chăm sóc, dạy người khác",
    "E": "Thuyết phục, kinh doanh, dẫn dắt nhóm",
    "C": "Sắp xếp, tính toán, làm với số liệu, giấy tờ",
}

# hobby key -> (checkbox text, its RIASEC type)
HOBBIES = {
    "code": ("Viết code, mày mò máy tính", "I"),
    "ve_thiet_ke": ("Vẽ, thiết kế", "A"),
    "am_nhac": ("Chơi nhạc, hát", "A"),
    "viet_doc": ("Viết lách, đọc sách", "A"),
    "quay_dung": ("Chụp ảnh, quay và dựng video", "A"),
    "the_thao": ("Chơi thể thao", "R"),
    "sua_chua": ("Sửa chữa, lắp ráp đồ", "R"),
    "cay_con_vat": ("Trồng cây, nuôi con vật", "R"),
    "thi_nghiem": ("Làm thí nghiệm, tìm hiểu khoa học", "I"),
    "cham_soc": ("Chăm sóc người khác, tình nguyện", "S"),
    "day_ban": ("Giảng bài cho bạn bè", "S"),
    "tranh_bien": ("Tranh biện, thuyết trình", "E"),
    "kinh_doanh": ("Buôn bán, kinh doanh online", "E"),
    "sap_xep": ("Lập kế hoạch, sắp xếp, ghi chép", "C"),
    "du_lich": ("Du lịch, tìm hiểu văn hóa, ngoại ngữ", "S"),
}

WORKPLACES = {
    "van_phong": "Văn phòng",
    "ngoai_troi": "Ngoài trời, công trường",
    "benh_vien": "Bệnh viện, phòng khám",
    "nha_may_phong_thi_nghiem": "Nhà máy, phòng thí nghiệm",
    "truong_hoc": "Trường học",
    "tu_do": "Làm tự do, ở nhà",
}

QUESTIONS = {
    "subjects": "Em thích hoặc học tốt môn nào? (tối đa 3 môn)",
    "work_types": "Em thích làm việc với điều gì hơn? (tối đa 2)",
    "hobbies": "Lúc rảnh em hay làm gì?",
    "workplace": "Sau này em muốn làm việc ở đâu?",
    "text": "Sau này em mơ ước làm công việc gì?",
}


def available() -> bool:
    return (MODEL_DIR / "model.npz").exists()


def suggest(answers: dict, db: Database | None = None) -> list[dict]:
    """[{"code", "score", "reasons"}] for the questionnaire `answers` (keys: subjects, work_types, hobbies, workplace,
    text; absent = skipped). [] while no model is trained."""
    if not available() or not any(answers.get(k) for k in QUESTIONS):
        return []
    raise NotImplementedError("the suggester model is not built yet (docs/MODEL.md)")
