"""End to end: profile -> ordered list. On the tiny simulated world (always runs, contents known) and a smoke
test on the real database."""

from unidata.testing import needs_real_db

from uniadvisor.recommend.advisor import advise
from uniadvisor.recommend.forecast import ForecastParams
from uniadvisor.student.slm.infer import HeuristicJudge
from uniadvisor.student.slm.state import StudentProfile

ANSWERED = {"risk_tolerance": "can_bang", "top_priority": "nganh_yeu_thich"}


def _check_list(a):
    assert 0 < len(a.chosen) <= a.constraints["max_choices"]
    utils = [c["utility"] for c in a.chosen]
    assert utils == sorted(utils, reverse=True)                      # ordered by utility
    # at least min_safe safe wishes when that many exist; otherwise as many as exist, and the summary says so
    safe = sum(c["bucket"] == "safe" for c in a.chosen)
    available = sum(c["bucket"] == "safe" for c in a.chosen + a.alternatives)
    assert safe >= min(a.constraints["min_safe"], len(a.chosen), available)
    assert all(0 <= c["p_admit"] <= 1 for c in a.chosen)
    assert all(0 <= c["utility"] <= 1 and set(c["criteria"]) == {"fit", "ability", "tuition", "location", "selectivity"}
               for c in a.chosen)
    assert all(c["bucket"] != "unlikely" for c in a.chosen)          # never recommended automatically
    assert a.clarify == []                                          # both profile questions answered by the student


def test_advise_on_the_tiny_world_is_deterministic_and_valid(tiny_db):
    p = StudentProfile(scores={"TO": 8.0, "VA": 7.0, "LI": 7.5, "N1": 7.0}, province="Nghệ An", area="KV2-NT",
                       free_text="Em muốn học kinh tế hoặc kỹ thuật. Nhà em lo được khoảng 40 triệu một năm. Em muốn học ở Hà Nội.",
                       answers=ANSWERED)
    run = lambda: advise(p, judge=HeuristicJudge(), db=tiny_db, params=ForecastParams())  # noqa: E731
    a1, a2 = run(), run()
    assert [c["program"]["program_id"] for c in a1.chosen] == [c["program"]["program_id"] for c in a2.chosen]
    _check_list(a1)
    assert all(c["program"]["program_id"].startswith("SIM-") for c in a1.chosen + a1.alternatives)


def test_floors_and_missing_combinations_exclude_programs(tiny_db):
    # B00 total 6+6+6 = 18 is under the medicine floor (20.5) but over the nursing floor (17)
    p = StudentProfile(scores={"TO": 6.0, "HO": 6.0, "SI": 6.0, "VA": 5.0}, answers=ANSWERED)
    a = advise(p, judge=HeuristicJudge(), db=tiny_db, params=ForecastParams())
    seen = {c["program"]["program_id"] for c in a.chosen + a.alternatives}
    assert "SIM-HC1:MD" not in seen
    assert not any(pid.startswith("SIM-HN1") for pid in seen)          # no A00/A01/D01 scores: no engineering




@needs_real_db
def test_advise_on_the_real_database():
    p = StudentProfile(scores={"TO": 8.4, "VA": 7.0, "LI": 8.0, "N1": 8.2}, province="Nghệ An", area="KV2-NT",
                       free_text="Em muốn học Công nghệ thông tin. Nhà em lo được khoảng 30 triệu một năm. Em muốn học ở Hà Nội.",
                       answers=ANSWERED)
    _check_list(advise(p, judge=HeuristicJudge()))
