"""Synthetic student profiles with hidden ground-truth attributes (`Latent`) and Vietnamese free text.

Design goals (docs/MVP.md §5):
- score distributions close to real ones: subject scores are drawn from the real 2026 per-subject
  histograms (VnExpress) with a shared ability factor; every student has the post-2025 exam shape
  (Toán + Văn + 2 electives)
- diverse free text: several voices (student / casual / parent), paraphrase banks, hobby-implied
  interests, irrelevant filler, missing diacritics, typos
- ambiguous and contradictory cases on purpose (parent pressure, mixed risk signals, vague budget)
- paired with REAL programs from the database's catalog (see slm/dataset.py)

The latent attributes are what the rubric teacher (slm/teacher.py) labels from. An LLM teacher can
relabel the same texts from the rubric alone (it never sees the latents).
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import norm

from unidata.build.fields import FIELDS
from unidata.paths import COLLECTED

# ------------------------------------------------------------------ geography
NORTH = ["Hà Nội", "Hải Phòng", "Quảng Ninh", "Bắc Ninh", "Hưng Yên", "Ninh Bình", "Phú Thọ", "Thái Nguyên",
         "Tuyên Quang", "Lào Cai", "Lạng Sơn", "Cao Bằng", "Điện Biên", "Lai Châu", "Sơn La", "Thanh Hóa", "Nghệ An", "Hà Tĩnh"]
CENTRAL = ["Quảng Trị", "Huế", "Đà Nẵng", "Quảng Ngãi", "Gia Lai", "Đắk Lắk", "Khánh Hòa"]
SOUTH = ["TP. Hồ Chí Minh", "Đồng Nai", "Tây Ninh", "Đồng Tháp", "An Giang", "Vĩnh Long", "Cần Thơ", "Cà Mau", "Lâm Đồng"]
REGION_OF = {**{p: "north" for p in NORTH}, **{p: "central" for p in CENTRAL}, **{p: "south" for p in SOUTH}}
HUB_OF_REGION = {"north": "Hà Nội", "south": "TP. Hồ Chí Minh", "central": None}
CITIES = ["Hà Nội", "TP. Hồ Chí Minh"]
CITY_SAY = {"Hà Nội": ["Hà Nội", "HN", "thủ đô", "Hà Nội"], "TP. Hồ Chí Minh": ["TP.HCM", "Sài Gòn", "HCM", "thành phố Hồ Chí Minh"]}

# ------------------------------------------------------------------ fields
RELATED = {
    "cntt": ["ky_thuat", "khoa_hoc_tn", "thiet_ke"], "ky_thuat": ["cntt", "xay_dung", "khoa_hoc_tn"],
    "kinh_te": ["tai_chinh", "du_lich", "bao_chi"], "tai_chinh": ["kinh_te", "khoa_hoc_tn"],
    "luat": ["xa_hoi", "kinh_te"], "y_duoc": ["sinh_hoa"], "su_pham": ["xa_hoi", "ngon_ngu"],
    "ngon_ngu": ["du_lich", "bao_chi", "su_pham"], "bao_chi": ["xa_hoi", "ngon_ngu", "kinh_te"],
    "xa_hoi": ["bao_chi", "luat", "su_pham"], "khoa_hoc_tn": ["cntt", "tai_chinh", "sinh_hoa"],
    "sinh_hoa": ["y_duoc", "nong_lam_mt", "khoa_hoc_tn"], "xay_dung": ["ky_thuat", "thiet_ke"],
    "nong_lam_mt": ["sinh_hoa", "xay_dung"], "du_lich": ["ngon_ngu", "kinh_te"], "thiet_ke": ["cntt", "xay_dung", "bao_chi"],
}
from uniadvisor.student.slm.questions import CORE_SUBJECTS  # noqa: E402,F401  (one table for the teacher and the written rubric)

# explicit wish / career / hobby (implied) / dislike phrase banks per field
FIELD_TEXT: dict[str, dict[str, list[str]]] = {
    "cntt": {
        "want": ["học Công nghệ thông tin", "học CNTT", "theo ngành khoa học máy tính", "học về trí tuệ nhân tạo", "học ngành IT", "học khoa học dữ liệu", "học an toàn thông tin"],
        "career": ["làm lập trình viên", "làm kỹ sư phần mềm", "làm về AI", "làm data analyst", "làm game developer", "làm chuyên gia bảo mật"],
        "hobby": ["hay tự viết code Python", "mê lập trình, tự làm được mấy cái web nhỏ", "thích mày mò máy tính, cài win cho cả xóm", "hay tham gia thi Tin học trẻ", "suốt ngày xem video về AI", "tự làm bot Discord cho nhóm bạn"],
        "dislike": ["không thích ngồi máy tính cả ngày", "sợ code lắm", "học Tin là buồn ngủ", "không muốn làm IT dù ai cũng bảo lương cao"],
    },
    "ky_thuat": {
        "want": ["học kỹ thuật", "học cơ khí", "học điện - điện tử", "học ngành ô tô", "học tự động hóa", "học cơ điện tử"],
        "career": ["làm kỹ sư điện", "làm kỹ sư cơ khí", "làm trong nhà máy sản xuất ô tô", "thiết kế robot"],
        "hobby": ["thích tháo lắp đồ điện tử trong nhà", "hay sửa xe máy cùng bố", "mê robot, từng thi sáng tạo kỹ thuật", "thích lắp mạch Arduino"],
        "dislike": ["không hợp với máy móc", "ghét mấy thứ kỹ thuật khô khan", "không muốn làm kỹ sư trong nhà máy"],
    },
    "kinh_te": {
        "want": ["học Quản trị kinh doanh", "học Marketing", "học kinh doanh quốc tế", "học thương mại điện tử", "học kinh tế"],
        "career": ["làm marketing", "tự mở công ty riêng", "làm quản lý doanh nghiệp", "làm xuất nhập khẩu", "làm sales cho tập đoàn lớn"],
        "hobby": ["đang bán quần áo online kiếm thêm", "thích lên kế hoạch, tổ chức sự kiện ở trường", "hay đọc sách về khởi nghiệp", "làm trưởng ban truyền thông CLB"],
        "dislike": ["không thích buôn bán", "không hợp với kinh doanh", "ghét phải đi thuyết phục người khác mua hàng"],
    },
    "tai_chinh": {
        "want": ["học Tài chính - Ngân hàng", "học Kế toán", "học Kiểm toán", "học về đầu tư, chứng khoán", "học công nghệ tài chính"],
        "career": ["làm ở ngân hàng", "làm kế toán", "làm kiểm toán cho Big4", "làm chuyên viên phân tích đầu tư"],
        "hobby": ["thích theo dõi chứng khoán", "hay quản lý quỹ lớp rất chặt", "thích các con số, tính toán"],
        "dislike": ["ghét tính toán sổ sách", "không thích làm ngân hàng", "sợ làm kế toán cả đời ngồi một chỗ"],
    },
    "luat": {
        "want": ["học Luật", "học ngành Luật kinh tế", "học luật quốc tế"],
        "career": ["làm luật sư", "làm thẩm phán", "làm pháp chế doanh nghiệp"],
        "hobby": ["thích tranh biện, hay đi thi debate", "hay xem phim về luật sư và tòa án", "hay đọc các vụ án"],
        "dislike": ["không thích học thuộc luật", "không hợp ngành luật"],
    },
    "y_duoc": {
        "want": ["học Y", "học Dược", "học Điều dưỡng", "học Răng hàm mặt", "theo ngành y"],
        "career": ["làm bác sĩ", "làm dược sĩ", "làm việc trong bệnh viện", "làm bác sĩ nha khoa"],
        "hobby": ["thích tìm hiểu về cơ thể người", "hay chăm sóc ông bà khi ốm", "tham gia hội chữ thập đỏ ở trường"],
        "dislike": ["sợ máu", "sợ bệnh viện", "không muốn học Y vì học quá lâu", "sợ tiêm"],
    },
    "su_pham": {
        "want": ["học sư phạm", "học sư phạm Toán", "học sư phạm Văn", "học sư phạm tiếng Anh", "học giáo dục tiểu học"],
        "career": ["làm giáo viên", "làm cô giáo", "đi dạy học", "làm giáo viên mầm non"],
        "hobby": ["hay kèm bài cho em nhỏ hàng xóm", "thích giảng bài cho bạn bè", "đi dạy gia sư từ lớp 11"],
        "dislike": ["không thích đi dạy", "sợ đứng trước đông người", "không muốn làm giáo viên"],
    },
    "ngon_ngu": {
        "want": ["học Ngôn ngữ Anh", "học ngôn ngữ Nhật", "học tiếng Hàn", "học ngôn ngữ Trung", "học quốc tế học", "học Đông phương học"],
        "career": ["làm phiên dịch", "làm biên dịch viên", "làm việc cho công ty Nhật", "làm hướng dẫn viên quốc tế"],
        "hobby": ["mê K-pop, tự học tiếng Hàn", "xem anime và tự học tiếng Nhật", "hay xem phim không cần phụ đề", "thích học ngoại ngữ"],
        "dislike": ["học ngoại ngữ rất chán", "không có năng khiếu ngoại ngữ"],
    },
    "bao_chi": {
        "want": ["học Báo chí", "học Truyền thông đa phương tiện", "học Quan hệ công chúng", "học ngành truyền thông"],
        "career": ["làm nhà báo", "làm MC", "làm content creator", "làm PR", "làm biên tập viên"],
        "hobby": ["làm kênh TikTok riêng", "viết bài cho báo tường", "hay chụp ảnh, dựng video", "làm admin fanpage của trường"],
        "dislike": ["không thích viết lách", "không thích lên hình", "ngại giao tiếp"],
    },
    "xa_hoi": {
        "want": ["học Tâm lý học", "học Xã hội học", "học Công tác xã hội", "học Quan hệ quốc tế", "học Hành chính"],
        "career": ["làm chuyên viên tâm lý", "làm công tác xã hội", "làm việc trong cơ quan nhà nước", "làm ngoại giao"],
        "hobby": ["hay lắng nghe tâm sự của bạn bè", "thích đọc sách lịch sử", "tham gia tình nguyện nhiều"],
        "dislike": ["không thích mấy ngành xã hội", "thấy ngành xã hội khó xin việc"],
    },
    "khoa_hoc_tn": {
        "want": ["học Toán ứng dụng", "học Vật lý", "học Thống kê", "học khoa học cơ bản"],
        "career": ["làm nhà nghiên cứu", "làm giảng viên đại học", "làm nghiên cứu khoa học"],
        "hobby": ["mê giải toán khó", "từng đi thi học sinh giỏi Lý", "thích đọc về vũ trụ, vật lý"],
        "dislike": ["không thích học lý thuyết khô khan", "ghét Toán"],
    },
    "sinh_hoa": {
        "want": ["học Công nghệ sinh học", "học Hóa học", "học Công nghệ thực phẩm", "học kỹ thuật hóa"],
        "career": ["làm trong phòng thí nghiệm", "làm kỹ sư thực phẩm", "nghiên cứu sinh học"],
        "hobby": ["thích làm thí nghiệm Hóa", "hay nấu ăn và tò mò về thực phẩm", "thích quan sát cây cối, vi sinh vật"],
        "dislike": ["sợ Hóa", "không thích làm thí nghiệm"],
    },
    "xay_dung": {
        "want": ["học Xây dựng", "học Kiến trúc", "học kỹ thuật xây dựng", "học quy hoạch"],
        "career": ["làm kỹ sư xây dựng", "làm kiến trúc sư", "thiết kế nhà"],
        "hobby": ["thích vẽ nhà, thiết kế phòng", "hay xem các công trình cầu đường", "quen công trường vì bố làm thầu xây dựng"],
        "dislike": ["không muốn làm công trường", "sợ nắng nóng ngoài công trường"],
    },
    "nong_lam_mt": {
        "want": ["học Môi trường", "học Nông nghiệp công nghệ cao", "học Quản lý tài nguyên", "học Thú y"],
        "career": ["làm về bảo vệ môi trường", "làm nông nghiệp công nghệ cao", "làm kỹ sư môi trường"],
        "hobby": ["thích trồng cây", "tham gia CLB môi trường xanh", "lớn lên ở trang trại của gia đình"],
        "dislike": ["không thích ngành nông nghiệp", "không muốn về nông thôn làm việc"],
    },
    "du_lich": {
        "want": ["học Du lịch", "học Quản trị khách sạn", "học Logistics", "học ngành hàng không"],
        "career": ["làm hướng dẫn viên du lịch", "làm quản lý khách sạn", "làm tiếp viên hàng không", "làm logistics"],
        "hobby": ["thích đi phượt", "mê du lịch, khám phá", "thích giao tiếp với người nước ngoài"],
        "dislike": ["không thích ngành dịch vụ", "không muốn đi lại nhiều"],
    },
    "thiet_ke": {
        "want": ["học Thiết kế đồ họa", "học thiết kế", "học mỹ thuật số"],
        "career": ["làm designer", "làm họa sĩ minh họa", "làm thiết kế UI/UX"],
        "hobby": ["vẽ rất nhiều, hay đăng tranh lên mạng", "thích chỉnh ảnh, làm poster cho lớp", "mê thiết kế"],
        "dislike": ["không có năng khiếu vẽ", "không thích mấy ngành nghệ thuật"],
    },
}

# What each phrase means in MOET codes: the truth for intent extraction (uniadvisor.student.intent). Codes are nhóm ngành; a
# ngành where its nhóm ngành also holds things the student did not mean (data science sits in Toán học, chemistry
# next to physics, logistics in Quản lý công nghiệp); a lĩnh vực for a phrase that broad. A phrase not listed means
# its field's default. Tagging never touches the random stream, so the generated texts stay the same.
FIELD_CODES: dict[str, tuple[str, ...]] = {
    "cntt": ("74801", "74802"), "ky_thuat": ("751", "752"), "kinh_te": ("73401", "73404", "73101"),
    "tai_chinh": ("73402", "73403"), "luat": ("73801",), "y_duoc": ("772",), "su_pham": ("71402",),
    "ngon_ngu": ("72202",), "bao_chi": ("73201",), "xa_hoi": ("73102", "73103", "73104", "72290", "77601"),
    "khoa_hoc_tn": ("744", "746"), "sinh_hoa": ("742", "7440112", "75401"), "xay_dung": ("758", "75101"),
    "nong_lam_mt": ("762", "785", "74403"), "du_lich": ("781", "784", "7510605"), "thiet_ke": ("721",),
}
_MECH, _ELEC = ("75102", "75201"), ("75103", "75202")
PHRASE_CODES: dict[str, tuple[str, ...]] = {
    # cntt
    "theo ngành khoa học máy tính": ("74801",), "học khoa học dữ liệu": ("7460108",), "học an toàn thông tin": ("74802",),
    "làm data analyst": ("7460108", "74801", "74802"), "làm chuyên gia bảo mật": ("74802",),
    # ky_thuat
    "học cơ khí": _MECH, "học điện - điện tử": _ELEC, "học ngành ô tô": _MECH, "học tự động hóa": _ELEC, "học cơ điện tử": _MECH,
    "làm kỹ sư điện": _ELEC, "làm kỹ sư cơ khí": _MECH, "làm trong nhà máy sản xuất ô tô": _MECH, "thiết kế robot": _MECH + _ELEC,
    "thích tháo lắp đồ điện tử trong nhà": _ELEC, "hay sửa xe máy cùng bố": _MECH,
    "mê robot, từng thi sáng tạo kỹ thuật": _MECH + _ELEC, "thích lắp mạch Arduino": _ELEC,
    # kinh_te
    "học Quản trị kinh doanh": ("73401",), "học Marketing": ("73401",), "học kinh doanh quốc tế": ("73401",),
    "học thương mại điện tử": ("73401",), "học kinh tế": ("73101",), "làm marketing": ("73401",), "tự mở công ty riêng": ("73401",),
    "làm quản lý doanh nghiệp": ("73401", "73404"), "làm xuất nhập khẩu": ("73401", "73101"), "làm sales cho tập đoàn lớn": ("73401",),
    "đang bán quần áo online kiếm thêm": ("73401",), "thích lên kế hoạch, tổ chức sự kiện ở trường": ("73401", "73404"),
    "hay đọc sách về khởi nghiệp": ("73401",), "làm trưởng ban truyền thông CLB": ("73401",),
    "không thích buôn bán": ("73401",), "không hợp với kinh doanh": ("73401",), "ghét phải đi thuyết phục người khác mua hàng": ("73401",),
    # tai_chinh
    "học Tài chính - Ngân hàng": ("73402",), "học Kế toán": ("73403",), "học Kiểm toán": ("73403",),
    "học về đầu tư, chứng khoán": ("73402",), "học công nghệ tài chính": ("73402",), "làm ở ngân hàng": ("73402",),
    "làm kế toán": ("73403",), "làm kiểm toán cho Big4": ("73403",), "làm chuyên viên phân tích đầu tư": ("73402",),
    "thích theo dõi chứng khoán": ("73402",), "hay quản lý quỹ lớp rất chặt": ("73403",), "ghét tính toán sổ sách": ("73403",),
    "không thích làm ngân hàng": ("73402",), "sợ làm kế toán cả đời ngồi một chỗ": ("73403",),
    # y_duoc
    "học Y": ("77201",), "học Dược": ("77202",), "học Điều dưỡng": ("77203",), "học Răng hàm mặt": ("77205",), "theo ngành y": ("77201",),
    "làm bác sĩ": ("77201",), "làm dược sĩ": ("77202",), "làm bác sĩ nha khoa": ("77205",), "không muốn học Y vì học quá lâu": ("77201",),
    # ngon_ngu
    "học quốc tế học": ("73106",), "học Đông phương học": ("73106",),
    # xa_hoi
    "học Tâm lý học": ("73104",), "học Xã hội học": ("73103",), "học Công tác xã hội": ("77601",), "học Quan hệ quốc tế": ("73102",),
    "học Hành chính": ("73102",), "làm chuyên viên tâm lý": ("73104",), "làm công tác xã hội": ("77601",),
    "làm việc trong cơ quan nhà nước": ("73102",), "làm ngoại giao": ("73102",), "hay lắng nghe tâm sự của bạn bè": ("73104",),
    "thích đọc sách lịch sử": ("72290",), "tham gia tình nguyện nhiều": ("77601",),
    # khoa_hoc_tn
    "học Toán ứng dụng": ("74601",), "học Vật lý": ("74401",), "học Thống kê": ("74602",), "mê giải toán khó": ("74601",),
    "từng đi thi học sinh giỏi Lý": ("74401",), "thích đọc về vũ trụ, vật lý": ("74401",), "ghét Toán": ("74601",),
    # sinh_hoa
    "học Công nghệ sinh học": ("74202",), "học Hóa học": ("7440112",), "học Công nghệ thực phẩm": ("75401",),
    "học kỹ thuật hóa": ("7510401", "7520301"), "làm trong phòng thí nghiệm": ("742", "7440112"), "làm kỹ sư thực phẩm": ("75401",),
    "nghiên cứu sinh học": ("742",), "thích làm thí nghiệm Hóa": ("7440112",), "hay nấu ăn và tò mò về thực phẩm": ("75401",),
    "thích quan sát cây cối, vi sinh vật": ("742",), "sợ Hóa": ("7440112", "7510401", "7520301"),
    "không thích làm thí nghiệm": ("742", "7440112"),
    # xay_dung
    "học Xây dựng": ("75802",), "học Kiến trúc": ("75801",), "học kỹ thuật xây dựng": ("75802", "75101"), "học quy hoạch": ("75801",),
    "làm kỹ sư xây dựng": ("75802", "75101"), "làm kiến trúc sư": ("75801",), "thiết kế nhà": ("75801",),
    "thích vẽ nhà, thiết kế phòng": ("75801",), "hay xem các công trình cầu đường": ("75802",),
    "quen công trường vì bố làm thầu xây dựng": ("75802",), "không muốn làm công trường": ("75802", "75101"),
    "sợ nắng nóng ngoài công trường": ("75802", "75101"),
    # nong_lam_mt
    "học Môi trường": ("785", "74403"), "học Nông nghiệp công nghệ cao": ("76201",), "học Quản lý tài nguyên": ("78501",),
    "học Thú y": ("76401",), "làm về bảo vệ môi trường": ("785", "74403"), "làm nông nghiệp công nghệ cao": ("76201",),
    "làm kỹ sư môi trường": ("785", "7510406", "7520320"), "thích trồng cây": ("76201",), "tham gia CLB môi trường xanh": ("785", "74403"),
    "lớn lên ở trang trại của gia đình": ("762",), "không thích ngành nông nghiệp": ("762",), "không muốn về nông thôn làm việc": ("762",),
    # du_lich
    "học Du lịch": ("78101",), "học Quản trị khách sạn": ("78102",), "học Logistics": ("7510605",), "học ngành hàng không": ("78401",),
    "làm hướng dẫn viên du lịch": ("78101",), "làm quản lý khách sạn": ("78102",), "làm tiếp viên hàng không": ("78401",),
    "làm logistics": ("7510605",), "thích đi phượt": ("78101",), "mê du lịch, khám phá": ("78101",),
    "thích giao tiếp với người nước ngoài": ("78101",), "không thích ngành dịch vụ": ("781",), "không muốn đi lại nhiều": ("78101", "78401"),
    # thiet_ke
    "học Thiết kế đồ họa": ("72104",), "học thiết kế": ("72104",), "học mỹ thuật số": ("72101", "72104"), "làm designer": ("72104",),
    "làm họa sĩ minh họa": ("72101", "72104"), "làm thiết kế UI/UX": ("72104",), "vẽ rất nhiều, hay đăng tranh lên mạng": ("72101", "72104"),
    "thích chỉnh ảnh, làm poster cho lớp": ("72104",), "mê thiết kế": ("72104",), "không có năng khiếu vẽ": ("72101", "72104"),
}


def phrase_codes(sentence: str, f: str, keys: tuple[str, ...]) -> list[str]:
    """The MOET codes meant by the phrases of field `f` that a generated sentence contains (before voice and typos)."""
    bank = FIELD_TEXT[f]
    found = [p for k in keys for p in bank[k] if p in sentence or _as_major(p) in sentence]
    found = [p for p in found if not any(p != q and p in q for q in found)]  # "làm bác sĩ" inside "làm bác sĩ nha khoa"
    return sorted({c for p in found for c in PHRASE_CODES.get(p, FIELD_CODES[f])}) or list(FIELD_CODES[f])


RISK_TEXT = {
    "an_toan": ["em chỉ cần chắc chắn đỗ, không muốn mạo hiểm", "nhà em không cho thi lại nên phải đỗ bằng được", "em sợ trượt lắm, muốn chọn chỗ chắc ăn",
                "ưu tiên của em là an toàn, đỗ là được", "em không dám liều, năm nay nhất định phải có trường", "bố mẹ dặn phải đỗ ngay năm nay"],
    "can_bang": ["em muốn thử một vài trường cao hơn sức mình nhưng vẫn phải có trường dự phòng", "em muốn cân bằng, vừa thử sức vừa có đường lui",
                 "chọn vừa sức là chính, thêm 1-2 nguyện vọng thử thách", "em muốn có cả phương án an toàn lẫn phương án cao"],
    "mao_hiem": ["em sẵn sàng liều để vào trường mơ ước, trượt thì năm sau thi lại", "được ăn cả ngã về không, em chỉ muốn trường top",
                 "em chấp nhận rủi ro, không đỗ trường mình thích thì ôn thêm một năm", "em muốn thử sức hết mình với trường thật cao"],
}
PRIORITY_TEXT = {
    "nganh_yeu_thich": ["quan trọng nhất là được học đúng ngành mình thích", "với em đam mê là số 1", "em chỉ cần học cái mình yêu thích, trường nào cũng được"],
    "truong_danh_tieng": ["em muốn vào trường thật danh tiếng", "quan trọng nhất là trường top, có tiếng", "em muốn học trường có tên tuổi để sau này dễ xin việc", "bằng của trường xịn là quan trọng nhất"],
    "hoc_phi_thap": ["nhà em khó khăn nên học phí là điều em lo nhất", "quan trọng nhất là học phí rẻ", "em cần trường học phí thấp để đỡ cho bố mẹ"],
    "gan_nha": ["quan trọng nhất là được học gần nhà", "em không muốn đi xa gia đình", "em ưu tiên học ở gần để còn về phụ bố mẹ"],
    "viec_lam_thu_nhap": ["quan trọng nhất là ra trường dễ xin việc", "em muốn ngành có thu nhập cao", "em cần ngành ổn định, ra trường có việc ngay", "lương cao là ưu tiên của em"],
}
FILLER = ["Em có nuôi một con mèo tên Mướp.", "Cuối tuần em hay đá bóng với bạn.", "Dạo này ôn thi mệt quá.", "Em thích nghe nhạc Sơn Tùng.",
          "Em là lớp trưởng.", "Nhà em có 3 anh chị em.", "Em đang học thêm ở trung tâm gần nhà.", "Em hay đọc truyện tranh.",
          "Em từng đạt giải khuyến khích văn nghệ.", "Em thích ăn bún chả.", "Em ở nội trú.", "Em hay chơi cầu lông."]


@dataclass
class Latent:
    scores: dict[str, float]
    score_kind: str
    province: str
    region: str
    gender: str | None
    interests: list[tuple[str, float]] = field(default_factory=list)   # (field, clarity)
    dislikes: list[str] = field(default_factory=list)
    parent_field: str | None = None
    accepts_parent: bool | None = None
    budget: float | None = None           # VND per year
    budget_kind: str | None = None        # number | poor | rich
    location: str | None = None           # city:<name> | near_home | anywhere | no_big_city
    avoid_branch: bool = False
    risk: str | None = None
    risk_conflict: bool = False
    priority: str | None = None
    english: str | None = None            # good | weak | ielts
    speech_issue: bool = False
    strong: list[str] = field(default_factory=list)
    weak: list[str] = field(default_factory=list)
    voice: str = "em"
    # MOET codes the text actually names (PHRASE_CODES), filled in by ProfileGenerator.text(): one list per interest
    # and per dislike, and the family's wish
    interest_codes: list[list[str]] = field(default_factory=list)
    dislike_codes: list[list[str]] = field(default_factory=list)
    parent_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------ scores from real distributions
class ScoreSampler:
    ELECTIVES = {"LI": 0.19, "HO": 0.12, "SI": 0.05, "SU": 0.2, "DI": 0.16, "N1": 0.14, "GDKTPL": 0.1, "TI": 0.02, "CNNN": 0.02}

    def __init__(self) -> None:
        sh = pd.read_csv(COLLECTED / "vnexpress_subject_hist.csv")
        sh["subject"] = sh["subject"].replace({"KTPL": "GDKTPL"})
        self.q = {}
        for s, g in sh[sh.year == sh.year.max()].groupby("subject"):
            g = g.sort_values("score")
            self.q[s] = (g.score.to_numpy(), np.cumsum(g["count"].to_numpy()) / g["count"].sum())

    def draw(self, rng: np.random.Generator, prefer: list[str] | None = None) -> dict[str, float]:
        names = list(self.ELECTIVES)
        p = np.array([self.ELECTIVES[n] for n in names])
        if prefer:
            p = p * np.array([4.0 if n in prefer else 1.0 for n in names])
        electives = [str(e) for e in rng.choice(names, size=2, replace=False, p=p / p.sum())]
        ability = rng.normal()
        out = {}
        for s in ["TO", "VA", *electives]:
            u = norm.cdf(0.75 * ability + 0.66 * rng.normal())
            vals, cum = self.q[s]
            out[s] = float(vals[min(np.searchsorted(cum, u), len(vals) - 1)])
        return out


# ------------------------------------------------------------------ text helpers
def strip_diacritics(t: str) -> str:
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")


def typos(t: str, rng: random.Random, rate: float = 0.03) -> str:
    chars = list(t)
    for i in range(len(chars)):
        if chars[i].isalpha() and rng.random() < rate:
            op = rng.random()
            if op < 0.4 and i + 1 < len(chars):
                chars[i], chars[i + 1] = chars[i + 1], chars[i]
            elif op < 0.7:
                chars[i] = ""
            else:
                chars[i] = chars[i] * 2
    return "".join(chars)


TEEN = [("không", "ko"), ("được", "đc"), ("biết", "bít"), ("vậy", "v"), ("gì", "j"), ("với", "vs"), ("rồi", "r"), ("em ", "e ")]


def teencode(t: str, rng: random.Random) -> str:
    for a, b in TEEN:
        if rng.random() < 0.7:
            t = t.replace(a, b)
    return t


def money_say(v: float, rng: random.Random) -> str:
    m = v / 1e6
    style = rng.random()
    if style < 0.5:
        return f"khoảng {m:.0f} triệu một năm"
    if style < 0.75:
        return f"tầm {m / 10:.1f} triệu mỗi tháng".replace(".0 ", " ")
    if style < 0.9:
        return f"tối đa {m:.0f}tr/năm"
    return f"không quá {m:.0f} triệu/năm"


def _as_major(want: str) -> str:
    """'học Luật' -> 'ngành Luật'; 'theo ngành y' stays."""
    return "ngành " + want[4:] if want.startswith("học ") else want.replace("theo ngành", "ngành")


# ------------------------------------------------------------------ generator
class ProfileGenerator:
    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self.nrng = np.random.default_rng(seed)
        self.sampler = ScoreSampler()
        self.fields = list(FIELDS)

    def latent(self) -> Latent:
        r = self.rng
        province = r.choice(NORTH * 3 + CENTRAL * 2 + SOUTH * 3)
        n_int = r.choices([0, 1, 2], weights=[0.18, 0.55, 0.27])[0]
        interests = []
        for f in r.sample(self.fields, n_int):
            interests.append((f, r.choice([1.0, 1.0, 0.7])))  # 0.7 = implied through a hobby only
        prefer = [s for f, _ in interests for s in CORE_SUBJECTS[f] if s not in ("TO", "VA")]
        scores = self.sampler.draw(self.nrng, prefer)
        free = [f for f in self.fields if f not in dict(interests)]
        dislikes = r.sample(free, r.choices([0, 1, 2], weights=[0.6, 0.3, 0.1])[0])
        parent_field, accepts = None, None
        if r.random() < 0.2:
            parent_field = r.choice([f for f in self.fields if f not in dislikes and f not in dict(interests)])
            accepts = r.random() < 0.4
        budget_kind = r.choices([None, "number", "poor", "rich"], weights=[0.35, 0.35, 0.18, 0.12])[0]
        budget = float(r.choice([12, 15, 18, 20, 25, 30, 35, 40, 50, 60, 80]) * 1e6) if budget_kind == "number" else None
        location = r.choices([None, "city", "near_home", "anywhere", "no_big_city"], weights=[0.3, 0.3, 0.2, 0.15, 0.05])[0]
        if location == "city":
            location = "city:" + r.choice(CITIES)
        risk = r.choices([None, "an_toan", "can_bang", "mao_hiem"], weights=[0.35, 0.3, 0.2, 0.15])[0]
        priority = r.choices([None, "nganh_yeu_thich", "truong_danh_tieng", "hoc_phi_thap", "gan_nha", "viec_lam_thu_nhap"],
                             weights=[0.35, 0.17, 0.12, 0.12, 0.1, 0.14])[0]
        if priority == "hoc_phi_thap" and budget_kind is None:
            budget_kind = "poor"
        if priority == "gan_nha" and location is None:
            location = "near_home"
        english = r.choices([None, "good", "weak", "ielts"], weights=[0.55, 0.18, 0.17, 0.1])[0]
        en = scores.get("N1")
        if en is not None and ((english == "weak" and en >= 6.5) or (english in ("good", "ielts") and en < 6.5)):
            english = None  # self-assessment must not contradict the actual English score
        subj = list(scores)
        strong = [s for s in subj if scores[s] >= 8.5 and r.random() < 0.5]
        weak = [s for s in subj if scores[s] <= 5.0 and r.random() < 0.5]
        return Latent(
            scores=scores, score_kind=r.choices(["actual", "mock"], weights=[0.7, 0.3])[0], province=province,
            region=REGION_OF[province], gender=r.choices([None, "nam", "nu"], weights=[0.3, 0.35, 0.35])[0],
            interests=interests, dislikes=dislikes, parent_field=parent_field, accepts_parent=accepts,
            budget=budget, budget_kind=budget_kind, location=location, avoid_branch=r.random() < 0.08,
            risk=risk, risk_conflict=risk is not None and r.random() < 0.08, priority=priority, english=english,
            speech_issue=r.random() < 0.03, strong=strong, weak=weak,
            voice=r.choices(["em", "minh", "teen", "parent"], weights=[0.5, 0.2, 0.15, 0.15])[0],
        )

    # ---------------------------------------------------------- text
    def text(self, z: Latent) -> str:
        r = self.rng
        sents: list[str] = []
        z.interest_codes, z.dislike_codes, z.parent_codes = [], [], []
        for f, clarity in z.interests:
            bank = FIELD_TEXT[f]
            if clarity >= 1.0:
                sents.append(r.choice([
                    f"Em muốn {r.choice(bank['want'])}.", f"Ước mơ của em là {r.choice(bank['career'])}.",
                    f"Em rất thích {_as_major(r.choice(bank['want']))}, sau này muốn {r.choice(bank['career'])}.",
                    f"Em định {r.choice(bank['want'])} vì muốn {r.choice(bank['career'])}.",
                    f"Nguyện vọng của em là {r.choice(bank['want'])}.",
                ]))
            else:
                sents.append(r.choice([f"Em {r.choice(bank['hobby'])}.", f"Ngoài giờ học em {r.choice(bank['hobby'])}.", f"Mọi người bảo em {r.choice(bank['hobby'])}."]))
            z.interest_codes.append(phrase_codes(sents[-1], f, ("want", "career") if clarity >= 1.0 else ("hobby",)))
        for f in z.dislikes:
            sents.append(r.choice([f"Em {r.choice(FIELD_TEXT[f]['dislike'])}.", f"Nói thật là em {r.choice(FIELD_TEXT[f]['dislike'])}."]))
            z.dislike_codes.append(phrase_codes(sents[-1], f, ("dislike",)))
        if z.parent_field:
            want = r.choice(FIELD_TEXT[z.parent_field]["want"])
            if z.accepts_parent:
                sents.append(r.choice([f"Bố mẹ muốn em {want}, em thấy cũng được.", f"Gia đình định hướng em {want} và em cũng không phản đối."]))
            else:
                sents.append(r.choice([f"Bố mẹ bắt em {want} nhưng em không muốn.", f"Mẹ em muốn em {want}, còn em thì không thích lắm."]))
            z.parent_codes = phrase_codes(want, z.parent_field, ("want",))
        if z.budget_kind == "number":
            sents.append(r.choice([f"Gia đình em chỉ lo được học phí {money_say(z.budget, r)}.", f"Học phí em có thể đóng {money_say(z.budget, r)}.",
                                   f"Bố mẹ nói chỉ chi được {money_say(z.budget, r)} tiền học."]))
        elif z.budget_kind == "poor":
            sents.append(r.choice(["Nhà em khó khăn, bố mẹ làm nông.", "Kinh tế gia đình em không khá lắm.", "Em thuộc hộ cận nghèo nên rất lo tiền học.",
                                   "Nhà em không có điều kiện, em phải tự đi làm thêm."]))
        elif z.budget_kind == "rich":
            sents.append(r.choice(["Gia đình em không lo về học phí.", "Kinh tế nhà em khá thoải mái.", "Bố mẹ bảo học phí bao nhiêu cũng lo được."]))
        if z.location and z.location.startswith("city:"):
            city = z.location.split(":", 1)[1]
            sents.append(r.choice([f"Em chỉ muốn học ở {r.choice(CITY_SAY[city])}.", f"Em muốn lên {r.choice(CITY_SAY[city])} học.",
                                   f"Em thích môi trường ở {r.choice(CITY_SAY[city])} nên muốn học ở đó."]))
        elif z.location == "near_home":
            sents.append(r.choice(["Em không muốn học xa nhà.", "Em muốn học gần nhà để tiện về thăm bố mẹ.", "Bố mẹ không cho em đi học xa."]))
        elif z.location == "anywhere":
            sents.append(r.choice(["Em học ở đâu cũng được.", "Địa điểm không quan trọng với em.", "Bắc hay Nam em đều đi được."]))
        elif z.location == "no_big_city":
            sents.append(r.choice(["Em không thích sống ở thành phố lớn, ồn ào lắm.", "Em sợ cuộc sống ở Hà Nội hay Sài Gòn."]))
        if z.avoid_branch:
            sents.append(r.choice(["Em không muốn học ở phân hiệu hay cơ sở tỉnh.", "Em chỉ học cơ sở chính thôi."]))
        if z.risk:
            sents.append(r.choice(RISK_TEXT[z.risk]).capitalize() + ".")
            if z.risk_conflict:
                other = r.choice([k for k in RISK_TEXT if k != z.risk])
                sents.append("Nhưng mà " + r.choice(RISK_TEXT[other]) + ".")
        if z.priority:
            sents.append(r.choice(PRIORITY_TEXT[z.priority]).capitalize() + ".")
        if z.english == "good":
            sents.append(r.choice(["Tiếng Anh của em khá tốt.", "Em giao tiếp tiếng Anh ổn.", "Em học tiếng Anh từ nhỏ nên khá tự tin."]))
        elif z.english == "weak":
            sents.append(r.choice(["Tiếng Anh em rất kém.", "Em mất gốc tiếng Anh.", "Em sợ nhất là môn tiếng Anh."]))
        elif z.english == "ielts":
            sents.append(r.choice(["Em có IELTS 6.5.", "Em đã có IELTS 7.0.", "Em thi IELTS được 6.0."]))
        if z.speech_issue:
            sents.append(r.choice(["Em hơi bị nói lắp.", "Em nói ngọng l/n một chút."]))
        from uniadvisor.student.slm.state import SUBJECT_VI
        for s in z.strong:
            sents.append(r.choice([f"Em học tốt môn {SUBJECT_VI[s]}.", f"{SUBJECT_VI[s]} là môn mạnh nhất của em."]))
        for s in z.weak:
            sents.append(r.choice([f"Em yếu môn {SUBJECT_VI[s]}.", f"Môn {SUBJECT_VI[s]} em học kém."]))
        if r.random() < 0.4:
            sents.append(r.choice(FILLER))
        r.shuffle(sents)
        text = " ".join(sents)
        if z.voice == "minh":
            text = re.sub(r"\b[Ee]m\b", "mình", text)
        elif z.voice == "parent":
            text = "Tôi là phụ huynh. " + re.sub(r"\b[Ee]m\b", "cháu", text).replace("Bố mẹ", "Vợ chồng tôi").replace("bố mẹ", "vợ chồng tôi")
        elif z.voice == "teen":
            text = teencode(text.lower(), r)
        if r.random() < 0.12:
            text = strip_diacritics(text)
        if r.random() < 0.15:
            text = typos(text, r)
        return text.strip()
