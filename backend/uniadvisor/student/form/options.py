"""Closed lists of the student JSON (docs/STUDENT_SCHEMA.md): the key that goes into the JSON -> the Vietnamese the
student sees. Order is the order shown on screen."""

from __future__ import annotations

from datetime import date

from uniadvisor.student.slm.synth import CENTRAL, NORTH, SOUTH
from unidata.text import fold

SCHEMA_VERSION = 1

SUBJECTS = {
    "TO": "Toán", "VA": "Ngữ văn", "LI": "Vật lý", "HO": "Hóa học", "SI": "Sinh học", "SU": "Lịch sử", "DI": "Địa lý",
    "TI": "Tin học", "GDKTPL": "Giáo dục kinh tế và pháp luật", "N1": "Tiếng Anh", "N2": "Tiếng Nga", "N3": "Tiếng Pháp",
    "N4": "Tiếng Trung", "N5": "Tiếng Đức", "N6": "Tiếng Nhật", "N7": "Tiếng Hàn", "CNCN": "Công nghệ công nghiệp",
    "CNNN": "Công nghệ nông nghiệp",
}
REQUIRED_SUBJECTS = ("TO", "VA")
ELECTIVES = tuple(k for k in SUBJECTS if k not in REQUIRED_SUBJECTS)
LANGUAGES = tuple(k for k in SUBJECTS if k.startswith("N") and k[1:].isdigit())

# a self-rated level -> the score written (docs/STUDENT_SCHEMA.md, "How module 2 turns answers into scores")
LEVELS = {
    "xuat_sac": ("Xuất sắc (9-10 điểm)", 9.5),
    "gioi": ("Giỏi (8-9 điểm)", 8.5),
    "trung_binh_kha": ("Trung bình khá (7-8 điểm)", 7.5),
    "trung_binh_yeu": ("Trung bình yếu (6-7 điểm)", 6.5),
    "yeu": ("Yếu (dưới 6 điểm)", 5.0),
}

AREAS = {"KV1": "KV1", "KV2-NT": "KV2 nông thôn (KV2-NT)", "KV2": "KV2", "KV3": "KV3"}
CATEGORIES = {"none": "Không", "UT1": "Có, nhóm 1 (đối tượng 01-04)", "UT2": "Có, nhóm 2 (đối tượng 05-07)"}
GENDERS = {"nam": "Nam", "nu": "Nữ"}
STRENGTHS = {"love": "Rất thích", "like": "Thích"}
AGREES = {True: "Em đồng ý", False: "Em không muốn", None: "Em chưa chắc"}
RISKS = {
    "an_toan": "Em muốn chắc chắn có trường",
    "can_bang": "Vừa thử sức vừa có lót",
    "mao_hiem": "Em sẵn sàng liều vì trường mơ ước",
}
PRIORITIES = {
    "nganh_yeu_thich": "Học đúng ngành yêu thích",
    "truong_danh_tieng": "Trường danh tiếng",
    "hoc_phi_thap": "Học phí thấp",
    "gan_nha": "Học gần nhà",
    "viec_lam_thu_nhap": "Việc làm, thu nhập sau này",
}

MAX_INTERESTS = 5
MAX_PRIORITIES = 3
FIRST_GRADUATION_YEAR = 2020

# the 34 provinces after the July 2025 merger, in alphabetical order
PROVINCES = tuple(sorted(NORTH + CENTRAL + SOUTH, key=fold))

# the city in scope nearer each province, by road from its capital. Central provinces split at Đà Nẵng (Hà Nội about
# 760 km, TP. Hồ Chí Minh about 960 km); from Quảng Ngãi south, TP. Hồ Chí Minh is nearer.
NEAREST_CITY = {
    **{p: "Hà Nội" for p in NORTH},
    **{p: "Hà Nội" for p in ("Quảng Trị", "Huế", "Đà Nẵng")},
    **{p: "TP. Hồ Chí Minh" for p in ("Quảng Ngãi", "Gia Lai", "Đắk Lắk", "Khánh Hòa")},
    **{p: "TP. Hồ Chí Minh" for p in SOUTH},
}

# what module 2 fills in when the student does not say, and what it tells them
NOTICES = {
    "profile.area": "Em chưa chọn khu vực ưu tiên nên mình tạm tính KV3, tức là chưa cộng điểm khu vực. "
                    "Nếu biết khu vực của mình, em báo mình nhé.",
    "profile.category": "Mình tạm tính em không thuộc diện ưu tiên nào. Nếu có, em báo mình nhé.",
    "profile.graduation_year": "Mình tạm hiểu em là học sinh lớp 12 năm nay.",
}


def target_year(today: date | None = None) -> int:
    """The admission year the advice is for: this year until July, then next year (the season ends in August)."""
    today = today or date.today()
    return today.year if today.month < 8 else today.year + 1


def default_ruleset() -> str:
    from uniadvisor.recommend.rules import DEFAULT_RULESET

    return DEFAULT_RULESET
