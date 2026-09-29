"""End-to-end smoke test on the real processed data (skipped when data/processed is missing)."""

import pytest

from uniadvisor.paths import PROCESSED

pytestmark = pytest.mark.skipif(not (PROCESSED / "programs.csv").exists(), reason="run `uniadvisor build` first")


def test_advise_end_to_end_is_deterministic_and_valid():
    from uniadvisor.advisor import advise
    from uniadvisor.slm.infer import HeuristicJudge
    from uniadvisor.slm.state import StudentProfile

    p = StudentProfile(scores={"TO": 8.4, "VA": 7.0, "LI": 8.0, "N1": 8.2}, province="Nghệ An", area="KV2-NT",
                       free_text="Em muốn học Công nghệ thông tin. Nhà em lo được khoảng 30 triệu một năm. Em muốn học ở Hà Nội.",
                       answers={"risk_tolerance": "can_bang", "top_priority": "nganh_yeu_thich"})
    a1 = advise(p, judge=HeuristicJudge())
    a2 = advise(p, judge=HeuristicJudge())
    assert [c["program"]["program_id"] for c in a1.chosen] == [c["program"]["program_id"] for c in a2.chosen]
    assert 0 < len(a1.chosen) <= a1.constraints["max_choices"]
    utils = [c["utility"] for c in a1.chosen]
    assert utils == sorted(utils, reverse=True)                      # ordered by utility
    assert sum(c["bucket"] == "safe" for c in a1.chosen) >= min(a1.constraints["min_safe"], len(a1.chosen))
    assert all(0 <= c["p_admit"] <= 1 for c in a1.chosen)
    assert a1.clarify == []                                          # both profile questions answered by the student
    assert all(c["explanation"] for c in a1.chosen)
