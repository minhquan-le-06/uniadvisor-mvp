import pytest

from uniadvisor.build.cutoffs import _method, scale_of
from uniadvisor.build.fields import field_of
from uniadvisor.kb import rules
from uniadvisor.text import fold, parse_score, split_combos


def test_text_helpers():
    assert fold("Đại học Bách khoa") == "dai hoc bach khoa"
    assert parse_score("28,69") == 28.69 and parse_score(" 29.01 ") == 29.01 and parse_score("XTTN") is None
    assert split_combos("A00; A01, D07 / x26") == ["A00", "A01", "D07", "X26"]


@pytest.mark.parametrize("raw,area,cat,expected", [
    (20.0, "KV1", "none", 0.75),          # below 22.5: full priority
    (24.0, "KV1", "UT1", 2.2),            # (30-24)/7.5 * 2.75
    (29.0, "KV2-NT", "none", 0.07),       # (30-29)/7.5 * 0.5
    (22.5, "KV3", "none", 0.0),
])
def test_priority_points_taper(raw, area, cat, expected):
    assert rules.priority_points(raw, area, cat) == expected


def test_area_priority_expires():
    assert rules.priority_points(20.0, "KV1", years_since_graduation=2) == 0.0
    assert rules.priority_points(20.0, "KV1", years_since_graduation=1) == 0.75


def test_combo_totals_and_foreign_languages():
    s = {"TO": 8.5, "LI": 8.0, "HO": 7.75, "VA": 7.0, "N1": 8.2}
    assert rules.combo_total(s, "A00") == 24.25
    assert rules.combo_total(s, "D01") == 23.7
    assert rules.combo_total(s, "D03") is None      # French combination needs a French score
    assert rules.combo_total(s, "B00") is None


def test_eligibility_best_combo_and_floor():
    s = {"TO": 8.5, "LI": 8.0, "HO": 7.75, "VA": 7.0, "N1": 8.2}
    e = rules.eligibility({"combos": "A00;A01;D07", "major_code": "7480201", "field": "cntt"}, s)
    assert e.eligible and e.combo == "A01" and e.total == 24.7
    low = rules.eligibility({"combos": "A00", "major_code": "7720101", "field": "y_duoc"}, {"TO": 6, "LI": 6, "HO": 6})
    assert not low.eligible and "sàn" in low.reasons[0]
    none = rules.eligibility({"combos": "B00"}, s)
    assert not none.eligible


def test_gender_only_program():
    p = {"combos": "A00", "conditions": "Chỉ tuyển thí sinh nam"}
    assert not rules.eligibility(p, {"TO": 8, "LI": 8, "HO": 8}, gender="nu").eligible
    assert rules.eligibility(p, {"TO": 8, "LI": 8, "HO": 8}, gender="nam").eligible


def test_buckets_and_ruleset_inheritance():
    r = rules.load_rules("2027-draft")
    assert r["status"] == "draft" and r["priority"]["area"]["KV1"] == 0.75   # inherited from 2026
    assert [rules.risk_bucket(p) for p in (0.9, 0.5, 0.2, 0.05)] == ["safe", "match", "reach", "unlikely"]
    assert rules.list_constraints("an_toan")["min_safe"] == 3


@pytest.mark.parametrize("note,expected", [
    ("Xét duyệt điểm thi THPT", "thpt"),
    ("Điểm thi TN THPT", "thpt"),
    ("Kết hợp điểm thi THPT với chứng chỉ IELTS", "other"),
    ("Điểm chuẩn tương đương - XTTN", "other"),
    ("Học bạ", "other"),
    ("Điểm ĐGNL", "other"),
    ("Thang điểm: 30", "unknown"),
    ("", "unknown"),
])
def test_method_from_note(note, expected):
    assert _method(note) == expected


def test_scale_and_fields():
    assert (scale_of(28.5), scale_of(36.4), scale_of(85.4)) == (30, 40, 100)
    assert field_of("Khoa học máy tính") == "cntt"
    assert field_of("Kế toán") == "tai_chinh"
    assert field_of("Điện ảnh và Nghệ thuật đại chúng") == "thiet_ke"
    assert field_of("Kỹ thuật điện") == "ky_thuat"
    assert field_of("Chăn nuôi", "7620105") == "nong_lam_mt"


def test_ads_final_rows_keep_thpt_and_mark_40_point_scale(tmp_path, monkeypatch):
    import pandas as pd

    import uniadvisor.build.cutoffs as cutoffs

    rows = [
        # source, school, year, code, name, combos, score, type, note
        ("ads_final_cutoffs", "MHN", 2019, "7220201", "Ngôn ngữ Anh", "D01", "28.47", "THPTQG - Thang 40", ""),
        ("ads_final_cutoffs", "BKA", 2019, "IT1", "Khoa học máy tính", "A00;A01", "27.42", "THPTQG", "TTNV <= 2"),
        ("ads_final_cutoffs", "BKA", 2019, "IT2", "Kỹ thuật máy tính", "A00", "26,85", "THPTQG", "(CT tiên tiến)"),
        ("ads_final_cutoffs", "BKA", 2019, "IT3", "Tin học", "A00", "24", "THPTQG", "kết hợp chứng chỉ IELTS"),
    ]
    cols = ["source", "school_code", "year", "program_code", "program_name", "combos", "score_raw", "score_type", "note"]
    pd.DataFrame(rows, columns=cols).assign(url="u", fetched_at="t").to_csv(tmp_path / "ads_final_cutoffs.csv", index=False)
    monkeypatch.setattr(cutoffs, "COLLECTED", tmp_path)
    df = cutoffs.ads_final_rows().set_index("program_code")
    assert list(df.index) == ["7220201", "IT1", "IT2"]  # a programme label is fine; a named other method is dropped
    assert df.loc["IT2", "score"] == 26.85
    assert df.loc["7220201", "scale_hint"] == 40 and df.loc["IT1", "scale_hint"] == 0


def test_reused_program_codes_are_cut_from_history():
    import pandas as pd

    from uniadvisor.build.catalog import _drop_reused_codes, same_name

    assert same_name("Kế toán (Chương trình chất lượng cao)", "Kế toán CLC")
    assert not same_name("Ngôn ngữ Trung Quốc", "Ngôn ngữ Anh")
    assert not same_name("Quản lý xây dựng", "Khoa học máy tính")
    h = pd.DataFrame([
        # XDA29 became a different program: the 2021 row and anything older must go
        ("XDA:XDA29", 2020, "Quản lý xây dựng", 16.0), ("XDA:XDA29", 2021, "Quản lý xây dựng", 16.0),
        ("XDA:XDA29", 2026, "Khoa học máy tính", 24.63),
        # a wrong name with a plausible score is kept (one aggregate mislabels names)
        ("BKA:IT1", 2019, "Kỹ thuật xây dựng", 27.42), ("BKA:IT1", 2026, "Khoa học Máy tính", 28.5),
    ], columns=["program_id", "year", "program_name", "score"])
    out = _drop_reused_codes(h, {"XDA:XDA29": "Khoa học máy tính", "BKA:IT1": "Khoa học Máy tính"})
    assert sorted(zip(out.program_id, out.year)) == [("BKA:IT1", 2019), ("BKA:IT1", 2026), ("XDA:XDA29", 2026)]
