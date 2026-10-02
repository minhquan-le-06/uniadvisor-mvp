"""Module 2's guided chat: answers -> the student JSON of docs/STUDENT_SCHEMA.md, on the tiny simulated world."""

import pytest
from streamlit.testing.v1 import AppTest

from uniadvisor.student.form import NEAR_HOME, Answers, ScoreEntry, build, picker, problems, search, summary
from uniadvisor.student.form.options import NEAREST_CITY, PROVINCES
from unidata.paths import ROOT


def _answers(**kw) -> Answers:
    base = dict(scores=[ScoreEntry("TO", "exact", 8.4), ScoreEntry("VA", "range", low=7, high=8),
                        ScoreEntry("LI", "level", level="gioi"), ScoreEntry("N1", "exact", 8.25)], gender="nam")
    return Answers(**{**base, **kw})


@pytest.fixture
def p(tiny_db):
    return picker(tiny_db)


@pytest.mark.parametrize(("entry", "score"), [
    (ScoreEntry("TO", "exact", 8.4), 8.4),
    (ScoreEntry("VA", "range", low=7, high=8), 7.5),
    (ScoreEntry("VA", "range", low=7.5, high=8.25), 7.75),     # midpoint 7.875, rounded down to 0.25
    (ScoreEntry("TO", "range", low=7, high=8.1), 7.55),        # Toán in steps of 0.05
    (ScoreEntry("LI", "level", level="xuat_sac"), 9.5),
    (ScoreEntry("LI", "level", level="yeu"), 5.0),
])
def test_scores_from_exact_range_and_level(entry, score):
    assert entry.problem() is None
    assert entry.score() == score


def test_scores_off_their_step_or_out_of_range_are_rejected():
    assert ScoreEntry("VA", "exact", 8.3).problem()            # Văn in steps of 0.25
    assert ScoreEntry("TO", "exact", 8.33).problem()
    assert ScoreEntry("TO", "exact", 10.5).problem()
    assert ScoreEntry("LI", "range", low=8, high=7).problem()
    assert ScoreEntry("LI", "level").problem()


def test_scores_need_toan_van_and_two_different_electives_with_one_language(p):
    toan_van = _answers().scores[:2]
    assert not _answers().missing()
    assert _answers(scores=_answers().scores[:3]).missing()
    assert _answers(scores=[*toan_van, ScoreEntry("N1", "exact", 8), ScoreEntry("N3", "exact", 8)]).missing()
    assert _answers(gender=None).missing()
    with pytest.raises(ValueError):
        build(_answers(gender=None), p)


def test_defaults_are_listed_in_assumed_with_a_notice(p):
    doc, notices = build(_answers(), p, year=2027)
    assert problems(doc, p) == []
    pr = doc["profile"]
    assert (pr["area"], pr["category"], pr["graduation_year"]) == ("KV3", "none", 2027)
    assert [a["field"] for a in doc["assumed"]] == ["profile.area", "profile.category", "profile.graduation_year"]
    assert len(notices) == 3
    doc, notices = build(_answers(area="KV1", category="none", graduation_year=2026), p, year=2027)
    assert doc["assumed"] == [] and notices == []


def test_score_kind_is_actual_only_for_exact_official_scores(p):
    exact = [ScoreEntry(s, "exact", 8.0) for s in ("TO", "VA", "LI", "HO")]
    assert build(_answers(scores=exact, scores_official=True), p)[0]["profile"]["score_kind"] == "actual"
    assert build(_answers(scores=exact), p)[0]["profile"]["score_kind"] == "mock"
    assert build(_answers(scores_official=True), p)[0]["profile"]["score_kind"] == "mock"   # has a range and a level


def test_sections_skipped_are_null_or_empty(p):
    doc, _ = build(_answers(), p)
    assert (doc["interests"], doc["dislikes"], doc["priorities"]) == ([], [], [])
    assert doc["family"] is doc["budget"] is doc["location"] is doc["risk"] is None
    assert doc["profile"]["province"] is None


def test_interests_dislikes_and_family(p):
    a = _answers(interests=[("74801", "love"), ("74801", "like"), ("77201", "like")], dislikes=["74801", "73401"],
                 family_codes=["71402"], family_agrees=False)
    doc, _ = build(a, p)
    assert doc["interests"] == [{"code": "74801", "strength": "love"}, {"code": "77201", "strength": "like"}]
    assert doc["dislikes"] == [{"code": "73401"}]          # never in both lists
    assert doc["family"] == {"codes": ["71402"], "student_agrees": False}
    assert problems(doc, p) == []


def test_budget_and_location(p):
    doc, _ = build(_answers(budget_kind="no_limit", budget_strict=True, location=NEAR_HOME, province="Nghệ An"), p)
    assert doc["budget"] == {"max_million_per_year": None, "strict": False}
    assert doc["location"] == {"cities": ["Hà Nội"], "main_campus_only": False}
    doc, _ = build(_answers(budget_kind="amount", budget_million=25, budget_strict=True, main_campus_only=True), p)
    assert doc["budget"] == {"max_million_per_year": 25.0, "strict": True}
    assert doc["location"] == {"cities": list(p.cities), "main_campus_only": True}   # only "cơ sở chính" ticked
    assert problems(doc, p) == []


def test_every_province_has_a_nearest_city():
    assert len(PROVINCES) == 34
    assert set(NEAREST_CITY) == set(PROVINCES)


@pytest.mark.parametrize(("break_it", "why"), [
    (lambda d: d["profile"]["scores"].update(SI=7.0), "scores"),
    (lambda d: d["profile"]["scores"].update(VA=7.3), "VA"),
    (lambda d: d["dislikes"].append({"code": "74801"}), "both"),
    (lambda d: d.update(budget={"max_million_per_year": None, "strict": True}), "strict"),
    (lambda d: d.update(location={"cities": ["Đà Nẵng"], "main_campus_only": False}), "scope"),
    (lambda d: d["interests"].append({"code": "99999", "strength": "like"}), "picker"),
    (lambda d: d.update(priorities=["hoc_phi_thap", "hoc_phi_thap"]), "priorities"),
    (lambda d: d.pop("risk"), "missing"),
])
def test_problems_catch_documents_that_break_the_schema(p, break_it, why):
    doc, _ = build(_answers(interests=[("74801", "like")]), p)
    break_it(doc)
    found = problems(doc, p)
    assert found and any(why in x for x in found)


def test_picker_lists_only_groups_with_programs_and_search_reads_student_words(p, tiny_db):
    codes = {g.code for g in p.groups}
    assert codes == set(tiny_db.catalog.moet_group_code.dropna())
    assert p.cities == ("Hà Nội", "TP. Hồ Chí Minh")
    assert {"74801", "74802"} <= set(search("IT", p))
    assert search("bác sĩ", p)[0] == "77201"
    assert search("", p) == []


def test_summary_reads_the_document_back(p):
    doc, _ = build(_answers(interests=[("74801", "love")], budget_kind="amount", budget_million=25,
                            budget_strict=True), p)
    s = summary(doc, p)
    assert s["scores"].startswith("Toán 8,4 · Ngữ văn 7,5")
    assert "Máy tính (rất thích)" in s["interests"]
    assert s["budget"] == "Tối đa 25 triệu/năm, không thể vượt."


def test_guided_chat_page_runs_to_the_summary(use_tiny):
    at = AppTest.from_file(str(ROOT / "app" / "pages" / "hoi_dap.py"), default_timeout=120).run()
    at.selectbox(key="f_e1").set_value("LI").run()
    at.selectbox(key="f_e2").set_value("N1").run()
    for i, v in enumerate([8.4, 7.5, 8.5, 8.25]):
        at.number_input(key=f"f_v{i}").set_value(v)
    at.button(key="f_next_scores").click().run()
    at.radio(key="f_gender").set_value("nu")
    at.button(key="f_next_about").click().run()
    at.selectbox(key="f_pg_interests").set_value("74801").run()
    at.button(key="f_add_interests").click().run()
    at.button(key="f_next_interests").click().run()
    for step in ("dislikes", "family", "budget", "location", "plan"):
        at.button(key=f"f_skip_{step}").click().run()
    assert not at.exception
    assert any("Máy tính (rất thích)" in m.value for m in at.markdown)
    assert len(at.info) == 3                                  # the three defaults, told to the student
