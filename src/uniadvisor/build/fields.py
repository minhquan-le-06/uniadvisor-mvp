"""Map a program to one broad field (nhóm ngành) from its name, falling back to the ministry major code.

Used to describe programs to the SLM and in the comparison table. Keyword rules are checked in order
(more specific first) on the diacritic-free lowercase name.
"""

from __future__ import annotations

import re

from uniadvisor.text import fold

FIELDS: dict[str, str] = {
    "cntt": "Công nghệ thông tin - Máy tính - Dữ liệu - AI",
    "ky_thuat": "Kỹ thuật - Công nghệ (cơ khí, điện, điện tử, ô tô, tự động hóa, vật liệu)",
    "kinh_te": "Kinh tế - Kinh doanh - Quản trị - Marketing - Thương mại",
    "tai_chinh": "Tài chính - Ngân hàng - Kế toán - Kiểm toán - Bảo hiểm",
    "luat": "Luật",
    "y_duoc": "Y - Dược - Điều dưỡng - Sức khỏe",
    "su_pham": "Sư phạm - Giáo dục",
    "ngon_ngu": "Ngôn ngữ - Văn hóa - Quốc tế học",
    "bao_chi": "Báo chí - Truyền thông - Quan hệ công chúng",
    "xa_hoi": "Khoa học xã hội - Tâm lý - Nhân văn - Chính trị - Hành chính",
    "khoa_hoc_tn": "Khoa học tự nhiên - Toán - Vật lý - Thống kê",
    "sinh_hoa": "Sinh học - Hóa học - Công nghệ sinh học - Thực phẩm",
    "xay_dung": "Kiến trúc - Xây dựng - Giao thông - Quy hoạch",
    "nong_lam_mt": "Nông - Lâm - Thủy sản - Môi trường - Tài nguyên",
    "du_lich": "Du lịch - Khách sạn - Logistics - Hàng không - Dịch vụ",
    "thiet_ke": "Thiết kế - Nghệ thuật - Sáng tạo số",
}

# (field, any of these keywords in the folded name)
RULES: list[tuple[str, tuple[str, ...]]] = [
    ("su_pham", ("su pham", "giao duc mam non", "giao duc tieu hoc", "giao duc the chat", "giao duc chinh tri", "giao duc dac biet", "quan ly giao duc", "cong nghe giao duc", "khoa hoc giao duc", "giao duc")),
    ("y_duoc", ("y khoa", "y hoc", "duoc", "dieu duong", "rang ham mat", "ho sinh", "xet nghiem", "ky thuat y", "hinh anh y", "phuc hoi chuc nang", "dinh duong", "y te cong cong", "suc khoe", "thu y", "nhan khoa", "nha khoa", "rang")),
    ("luat", ("luat",)),
    ("bao_chi", ("bao chi", "truyen thong", "quan he cong chung", "bao mang", "xuat ban", "quang cao", "phat thanh", "truyen hinh", "media")),
    ("tai_chinh", ("tai chinh", "ngan hang", "ke toan", "kiem toan", "bao hiem", "dau tu", "fintech", "cong nghe tai chinh", "chung khoan", "thue", "tham dinh gia")),
    ("du_lich", ("du lich", "khach san", "nha hang", "logistics", "chuoi cung ung", "hang khong", "van tai", "dich vu", "lu hanh", "su kien")),
    ("cntt", ("cong nghe thong tin", "khoa hoc may tinh", "ky thuat may tinh", "may tinh", "phan mem", "tri tue nhan tao", "du lieu", "an toan thong tin", "an ninh mang", "khong gian so", "he thong thong tin", "mang may tinh", "truyen thong va mang", "cntt", " it ", "data", " ai ", "thiet ke vi mach", "ban dan", "game", "iot", "robot", "dia khong gian", "thong tin dia ly")),
    ("ngon_ngu", ("ngon ngu", "tieng ", "quoc te hoc", "dong phuong", "han quoc hoc", "nhat ban hoc", "trung quoc hoc", "van hoa", "phien dich", "bien dich", "khu vuc hoc", "viet nam hoc", "han nom", "dong nam a hoc", "hoa ky hoc", "my hoc", "chau au hoc")),
    ("xa_hoi", ("tam ly", "chu nghia xa hoi", "xa hoi hoc", "cong tac xa hoi", "chinh tri", "triet hoc", "lich su", "nhan hoc", "van hoc", "hanh chinh", "quan ly nha nuoc", "quan ly cong", "dia ly", "luu tru", "thu vien", "ton giao", "nhan van", "quan he quoc te", "chinh sach", "dia li", "phat trien quoc te", "nghien cuu phat trien")),
    ("xay_dung", ("xay dung", "kien truc", "quy hoach", "giao thong", "cau duong", "cong trinh", "do thi", "ha tang", "noi that", "duong sat", "cang")),
    ("nong_lam_mt", ("nong nghiep", "lam nghiep", "thuy san", "chan nuoi", "trong trot", "bao ve thuc vat", "moi truong", "tai nguyen", "dat dai", "lam hoc", "kinh te nong nghiep", "thuy loi", "khi tuong", "thuy van", "dia chat", "bien doi khi hau", "nong hoc", "nong thon")),
    ("sinh_hoa", ("sinh hoc", "cong nghe sinh hoc", "hoa hoc", "hoa duoc", "thuc pham", "ky thuat hoa", "cong nghe hoa", "sinh hoa", "vi sinh")),
    ("kinh_te", ("kinh te", "kinh doanh", "quan tri", "marketing", "thuong mai", "thuong mai dien tu", "quan ly", "bat dong san", "nhan luc", "doanh nghiep", "khoi nghiep", "ban le", "thuong hieu", "thi truong", "ngoai thuong", "cu nhan")),
    ("khoa_hoc_tn", ("toan", "vat ly", "vat li", "thong ke", "khoa hoc vat lieu", "hai duong", "thien van", "khoa hoc tu nhien", "vu tru")),
    ("thiet_ke", ("thiet ke", "nghe thuat", "my thuat", "do hoa", "thoi trang", "am nhac", "thanh nhac", "piano", "dien anh", "am thanh anh sang")),
    ("ky_thuat", ("ky thuat", "cong nghe", "co khi", " dien ", "dien tu", "dien lanh", "dien -", "tu dong", "o to", "co dien tu", "nhiet", "vat lieu", "det may", " in ", "hat nhan", "hang hai", " may ", "khuon", "che tao", "nang luong", "dau khi", " mo ", "trac dia", "bao ho lao dong", "bao duong", "da quy")),
]

# Words that identify a field in a program *name* but are too generic in a student's free text
# ("công nghệ", "quản lý", "dịch vụ" appear in many sentences that are not about a field).
GENERIC_IN_FREE_TEXT = {"cong nghe", "ky thuat", "quan ly", "dich vu", " may ", " in ", " mo ", " dien ", "toan", "cu nhan",
                        "kinh te", "van hoa", "chinh sach", "thue", "rang", "dau tu", "an toan thong tin", "he thong thong tin",
                        "duoc", "tieng ", "hoc tap", "suc khoe", "lich su", "dia li"}

# ministry major code prefix -> field (fallback when the name matches nothing)
CODE_PREFIX = [
    ("714", "su_pham"), ("721", "ngon_ngu"), ("722", "ngon_ngu"), ("7310", "xa_hoi"), ("731", "kinh_te"),
    ("732", "bao_chi"), ("7340", "kinh_te"), ("738", "luat"), ("742", "sinh_hoa"), ("744", "khoa_hoc_tn"),
    ("746", "khoa_hoc_tn"), ("748", "cntt"), ("751", "ky_thuat"), ("752", "ky_thuat"), ("754", "sinh_hoa"),
    ("758", "xay_dung"), ("762", "nong_lam_mt"), ("764", "y_duoc"), ("772", "y_duoc"), ("776", "xa_hoi"),
    ("781", "du_lich"), ("784", "du_lich"), ("785", "nong_lam_mt"),
]


def field_of(name: str, major_code: str | None = None) -> str | None:
    # whole words only: as substrings, "thời trang" contained "rang" (dentistry) and "tâm lý học" contained
    # "y học" (medicine), which put fashion design and psychology under health
    f = f" {re.sub(r'[^a-z0-9]+', ' ', fold(name))} "
    for field, words in RULES:
        if any(f" {w.strip()} " in f for w in words):
            return field
    code = (major_code or "").strip()
    for prefix, field in CODE_PREFIX:
        if code.startswith(prefix):
            return field
    return None
