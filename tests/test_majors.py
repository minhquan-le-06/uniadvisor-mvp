"""MOET's major codes: the catalog, the code -> field mapping, and matching program names to codes."""

import pytest
from conftest import needs_real_db

from uniadvisor.build import majors as moet
from uniadvisor.build.fields import FIELDS, code_prefixes, field_of, field_of_code
from uniadvisor.collect import moet as collect_moet
from uniadvisor.db.schema import FIELD_KEYS
from uniadvisor.kb import rules

PAGE = """<table>
<tr><td>Mã ngành</td><td>Tên ngành</td><td>Hiệu lực</td><td>Ghi chú</td></tr>
<tr><td>714</td><td>Khoa học giáo dục và đào tạo giáo viên</td><td></td><td></td></tr>
<tr><td>71402</td><td>Đào tạo giáo viên</td><td></td><td></td></tr>
<tr><td>7140201</td><td>Giáo dục Mầm non</td><td></td><td></td></tr>
<tr><td>7140207</td><td>Huấn luyện thể thao</td><td>Có hiệu lực áp dụng từ ngày 22/7/2022</td><td>Chuyển đến nhóm ngành 78103</td></tr>
<tr><td>781</td><td>Du lịch, khách sạn, thể thao và dịch vụ cá nhân</td><td></td><td></td></tr>
<tr><td>78103</td><td>Thể dục, thể thao</td><td></td><td></td></tr>
<tr><td>7810302</td><td>Huấn luyện thể thao</td><td>Có hiệu lực</td><td>Ngành chuyển đến từ nhóm ngành 71402 (mã cũ là 7140207)</td></tr>
</table>"""


def test_parse_reads_levels_parents_and_renumbered_majors():
    df = collect_moet.parse(PAGE).set_index("code")
    assert df.loc["714", "level"] == "linh_vuc" and df.loc["71402", "level"] == "nhom_nganh"
    assert df.loc["7140201", "level"] == "nganh" and df.loc["7140201", "parent"] == "71402"
    assert df.loc["7810302", "former_code"] == "7140207"
    assert "7140207" not in df.index                    # the old code of a moved major is not a major of its own


def test_the_catalog_file_is_complete():
    cat = moet.catalog()
    assert collect_moet.check(cat) == []
    counts = cat[cat.source == collect_moet.SOURCE].level.value_counts()
    assert (counts["linh_vuc"], counts["nhom_nganh"]) == (24, 95) and counts["nganh"] >= 370
    assert moet.current_code("7140207") == "7810302" and moet.current_code("7480201") == "7480201"


def test_fields_follow_moet_codes():
    assert tuple(FIELDS) == FIELD_KEYS
    codes = set(moet.catalog().code)
    assert {p for p, _ in code_prefixes()} <= codes                     # every prefix is a real MOET code
    for area in moet.catalog().query("level == 'linh_vuc'").code:   # every lĩnh vực has a field, except "Khác"
        assert (field_of_code(area + "0101") is not None) or area == "790", area
    assert field_of_code("7480201") == "cntt"
    assert field_of_code("7460108") == "cntt"            # data science: named in the cntt field
    assert field_of_code("7460101") == "khoa_hoc_tn"     # mathematics stays with MOET's Toán và thống kê
    assert field_of_code("7510605") == "du_lich"         # logistics: named in the du_lich field
    assert field_of_code("7440112") == "sinh_hoa"
    assert field_of_code("7310403") == "xa_hoi"          # educational psychology is not teacher training
    # the code decides; the name only fills in without one
    assert field_of("Công nghệ kỹ thuật cơ khí (CTĐT bằng Tiếng Anh)", "7510201") == "ky_thuat"
    assert field_of("Công nghệ kỹ thuật cơ khí (CTĐT bằng Tiếng Anh)") == "ngon_ngu"


@pytest.mark.parametrize("name, code", [
    ("Kỹ thuật điện tử - viễn thông (Chuyên ngành Kỹ thuật điện tử và tin học công nghiệp)", "7520207"),
    ("Tài chính - Ngân hàng", "7340201"),        # "tài" folds to "tai" (= tại): must not be cut as a campus
    ("Hệ thống thông tin", "7480104"),           # "hệ" must not be cut as "hệ chất lượng cao"
    ("Quản lí xây dựng", "7580302"),             # i / y spelling
    ("Chương trình tiên tiến Kỹ thuật Y sinh", "7520212"),
    ("Kinh tế xây dựng (Chương trình CLC Kinh tế xây dựng công trình giao thông Việt - Anh)", "7580301"),
    ("Quản trị Kinh doanh CTTT", "7340101"),
    ("Khoa học thông tin địa không gian", None),  # not an official ngành name
    ("Logistics trong kinh tế tầm thấp", None),   # starts like one, but prefix matches were wrong 59% of the time
])
def test_match_name(name, code):
    assert moet.match_name(name) == code


@needs_real_db
def test_name_matching_is_right_on_programs_with_a_known_code():
    from uniadvisor.db import load

    p = load()["programs"]
    observed = p[p.major_code_provenance == "observed"]
    r = moet.evaluate(observed)
    assert r["matched"] > 800 and r["same_major"] >= 0.98 and r["same_group"] >= 0.98


def test_teacher_training_floor_follows_the_code():
    assert rules.floor_for("7140209", "su_pham")[0] == 19.0      # Sư phạm Toán học
    assert rules.floor_for("7140114", "su_pham") is None          # Quản lý giáo dục: education, not teacher training
    assert rules.floor_for("", "su_pham")[0] == 19.0              # no code: the field stands in
    assert rules.floor_for("7720101", "y_duoc")[0] == 20.5
