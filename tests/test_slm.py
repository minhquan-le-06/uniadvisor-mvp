import random

import pytest

from uniadvisor.slm import teacher
from uniadvisor.slm.infer import HeuristicJudge, HybridJudge, _budget, _likes
from uniadvisor.slm.questions import INSUFFICIENT, QUESTIONS
from uniadvisor.slm.state import StudentProfile, model_input
from uniadvisor.slm.synth import Latent

PROGRAM = {"program_id": "X:1", "school_code": "X", "school_name": "Trường X", "program_name": "Khoa học máy tính",
           "field": "cntt", "field_name": "CNTT", "city": "Hà Nội", "campus": None, "kind": "standard",
           "tuition_min": 30e6, "tuition_max": 40e6, "tuition_imputed": False, "conditions": None}


def _latent(**kw):
    base = dict(scores={"TO": 8.0, "VA": 7.0, "LI": 7.5, "N1": 8.0}, score_kind="actual", province="Nghệ An", region="north", gender="nam")
    base.update(kw)
    return Latent(**base)


def test_teacher_soft_labels_are_distributions():
    rng = random.Random(0)
    z = _latent(interests=[("cntt", 1.0)], budget_kind="number", budget=35e6, location="city:Hà Nội", risk="an_toan")
    for q in QUESTIONS:
        soft = teacher.label(q.id, z, PROGRAM if q.scope == "program" else None, rng)
        assert set(soft) == set(q.all_labels) and abs(sum(soft.values()) - 1) < 1e-9


def test_teacher_rubric_cases():
    rng = random.Random(1)
    top = lambda d: max(d, key=d.get)  # noqa: E731
    assert top(teacher.label("interest_fit", _latent(interests=[("cntt", 1.0)]), PROGRAM, rng)) == "5"
    assert top(teacher.label("interest_fit", _latent(dislikes=["cntt"]), PROGRAM, rng)) == "1"
    assert top(teacher.label("interest_fit", _latent(), PROGRAM, rng)) == INSUFFICIENT
    assert top(teacher.label("budget_ok", _latent(budget_kind="number", budget=20e6), PROGRAM, rng)) == "no"
    assert top(teacher.label("budget_ok", _latent(budget_kind="rich"), PROGRAM, rng)) == "yes"
    assert top(teacher.label("location_ok", _latent(location="city:TP. Hồ Chí Minh"), PROGRAM, rng)) == "no"
    assert top(teacher.label("location_ok", _latent(location="near_home"), PROGRAM, rng)) == "yes"   # Nghệ An -> Hà Nội
    assert top(teacher.label("risk_tolerance", _latent(), None, rng)) == INSUFFICIENT


def test_model_input_mentions_both_sides():
    p = StudentProfile(scores={"TO": 8}, free_text="Em thích lập trình")
    a, b = model_input("Câu hỏi?", p, PROGRAM)
    assert "lập trình" in a and "Khoa học máy tính" in b and "30-40 triệu/năm" in b


def test_heuristic_parsing():
    likes, dislikes = _likes("Em muốn học Công nghệ thông tin. Gia đình lo được 30 triệu. Em không thích kinh doanh.")
    assert "cntt" in likes and "kinh_te" in dislikes and "y_duoc" not in likes
    assert _budget("Nhà em chỉ lo được tầm 2.5 triệu mỗi tháng tiền học") == ("number", 25e6)
    j = HeuristicJudge()
    prof = StudentProfile(scores={"TO": 8}, free_text="Em muốn học CNTT. Học phí em có thể đóng khoảng 50 triệu một năm.", answers={"risk_tolerance": "mao_hiem"})
    ans = {a.question: a for a in j.answer([("interest_fit", prof, PROGRAM), ("budget_ok", prof, PROGRAM), ("risk_tolerance", prof, None)])}
    assert ans["interest_fit"].label == "5" and ans["budget_ok"].label == "yes"
    assert ans["risk_tolerance"].source == "student" and ans["risk_tolerance"].label == "mao_hiem"


def test_typed_heads_math():
    torch = pytest.importorskip("torch")
    from uniadvisor.slm.model import probs_from_logits, soft_loss

    for kind, width, n_labels in (("choice", 4, 4), ("bool", 2, 3), ("score", 5, 6)):
        logits = torch.randn(7, width)
        p = probs_from_logits(kind, logits)
        assert p.shape == (7, n_labels) and torch.allclose(p.sum(-1), torch.ones(7), atol=1e-5) and (p >= 0).all()
        target = torch.softmax(torch.randn(7, n_labels), -1)
        assert torch.isfinite(soft_loss(kind, logits, target))


def test_hybrid_routes_each_question_to_its_judge():
    class StubSLM:
        name = "slm"
        cfg: dict = {}
        thresholds = {"location_ok": 0.5, "ability_fit": 0.9}

        def __init__(self):
            self.seen = []

        def answer(self, items):
            self.seen.extend(q for q, _, _ in items)
            return HeuristicJudge().answer(items)

    slm = StubSLM()
    j = HybridJudge(slm, slm_questions=("location_ok",))
    prof = StudentProfile(scores={"TO": 8, "VA": 7}, free_text="Em muốn học ở Hà Nội.")
    qs = ["ability_fit", "location_ok", "interest_fit", "location_ok"]
    ans = j.answer([(q, prof, PROGRAM) for q in qs])
    assert slm.seen == ["location_ok", "location_ok"]
    assert [a.question for a in ans] == qs
    assert j.thresholds["location_ok"] == 0.5 and j.thresholds["ability_fit"] != 0.9
    with pytest.raises(ValueError):
        HybridJudge(slm, slm_questions=("nope",))


def test_program_text_treats_nan_as_missing():
    from uniadvisor.slm.state import program_text

    t = program_text(dict(PROGRAM, campus=float("nan"), tuition_min=float("nan"), conditions=float("nan")))
    assert "nan" not in t and "Nơi học: Hà Nội" in t and "Học phí: không rõ" in t


def test_teacher_nan_campus_is_not_a_branch_campus():
    """Regression: a NaN campus (pandas 3 string column) counted as a branch campus, so every
    location_ok label for a matching city came out 'no'."""
    rng = random.Random(3)
    top = lambda d: max(d, key=d.get)  # noqa: E731
    p = dict(PROGRAM, campus=float("nan"))
    assert top(teacher.label("location_ok", _latent(location="city:" + PROGRAM["city"]), p, rng)) == "yes"
    assert top(teacher.label("location_ok", _latent(location="anywhere", avoid_branch=True), p, rng)) == "yes"
    assert top(teacher.label("location_ok", _latent(location="anywhere", avoid_branch=True), dict(PROGRAM, campus="Thanh Hóa"), rng)) == "no"


def test_dataset_programs_have_no_nan_cells():
    import pandas as pd

    programs = pd.read_csv("data/processed/programs.csv", dtype={"program_code": str, "major_code": str})
    fixed = programs.astype(object).where(programs.notna(), None)
    assert not any(isinstance(v, float) and v != v for v in fixed.campus)


def test_self_assessment_and_family_wishes_are_read_from_text():
    from uniadvisor.slm.infer import _family, _self_assessed

    assert _self_assessed("Toán là môn mạnh nhất của em. Em yếu môn Lý.") == ({"TO"}, {"LI"})
    assert _self_assessed("Tiếng Anh em rất kém.")[1] == {"N1"}
    assert _self_assessed("Em sợ nhất là môn tiếng Anh.")[1] == {"N1"}
    assert _self_assessed("Em có IELTS 6.5.")[0] == {"N1"}
    assert _self_assessed("Em thích Toán nhưng điểm Toán em chưa tốt.") == (set(), {"TO"})
    assert _self_assessed("e hoc tot mon hoa. mon van e hoc kem") == ({"HO"}, {"VA"})  # per sentence
    assert _self_assessed("Nhà em có 3 anh chị em.") == (set(), set())
    assert _family("Bố mẹ bắt em học Du lịch nhưng em không muốn.") == ({"du_lich"}, set())
    assert _family("Mẹ em muốn em học Vật lý, còn em thì không thích lắm.")[0] == {"khoa_hoc_tn"}
    assert _family("Gia đình định hướng em học giáo dục tiểu học và em không phản đối.") == (set(), {"su_pham"})


def test_heuristic_ability_follows_the_rubric():
    j = HeuristicJudge()
    design = dict(PROGRAM, field="thiet_ke")  # core Văn (x2), Toán
    p = StudentProfile(scores={"TO": 9.0, "VA": 8.0}, free_text="")
    assert j.answer([("ability_fit", p, design)])[0].label == "4"   # (2*8 + 9) / 3 = 8.33, not the plain mean 8.5
    lang = dict(PROGRAM, field="ngon_ngu")  # core Anh (x2), Văn
    p = StudentProfile(scores={"N1": 6.0, "VA": 7.0}, free_text="Tiếng Anh em rất kém.")
    assert j.answer([("ability_fit", p, lang)])[0].label == "1"     # 6.33 -> 2, weak English -> 1
    p = StudentProfile(scores={"TO": 9.0}, free_text="Em yếu môn Lý.")  # Lý is not core for languages
    assert j.answer([("ability_fit", p, lang)])[0].label == INSUFFICIENT


def test_heuristic_interest_family_rules():
    j = HeuristicJudge()
    tourism = dict(PROGRAM, field="du_lich")
    forced = StudentProfile(scores={}, free_text="Em muốn học quy hoạch. Bố mẹ bắt em học Du lịch nhưng em không muốn.")
    assert j.answer([("interest_fit", forced, tourism)])[0].label == "2"
    only_dislike = StudentProfile(scores={}, free_text="Em sợ đứng trước đông người. Em không thích viết lách.")
    assert j.answer([("interest_fit", only_dislike, dict(PROGRAM, field="ky_thuat"))])[0].label == "3"


def test_field_of_matches_whole_words():
    from uniadvisor.build.fields import field_of

    assert field_of("Thiết kế thời trang") == "thiet_ke"   # "trang" contains "rang" (dentistry)
    assert field_of("Tâm lý học") == "xa_hoi"              # "tâm lý học" contains "y học" (medicine)
    assert field_of("Răng Hàm Mặt") == "y_duoc"
    assert field_of("Y khoa") == "y_duoc"


def test_teacher_counts_the_english_self_assessment():
    rng = random.Random(5)
    top = lambda d: max(d, key=d.get)  # noqa: E731
    lang = dict(PROGRAM, field="ngon_ngu")
    z = _latent(scores={"N1": 7.0, "VA": 7.0, "TO": 7.0}, english="weak")
    assert top(teacher.label("ability_fit", z, lang, rng)) == "2"   # 7.0 -> 3, weak English -> 2


def test_risk_keywords_and_negation():
    from uniadvisor.slm.infer import HeuristicJudge
    from uniadvisor.slm.state import StudentProfile
    j = HeuristicJudge()
    lab = lambda t: j.answer([("risk_tolerance", StudentProfile(free_text=t), None)])[0].label  # noqa: E731
    assert lab("thử thách") == "mao_hiem"
    assert lab("muốn thử thách, không cần an toàn") == "mao_hiem"
    assert lab("em cần chắc chắn đỗ") == "an_toan"


def test_newest_message_wins_on_place_and_risk():
    from uniadvisor.slm.infer import focus, mentions
    from uniadvisor.slm.state import StudentProfile
    p = StudentProfile(free_text="Em muốn học CNTT ở Hà Nội, cần chắc chắn đỗ.\nhọc ở tp hcm\nthử thách")
    assert focus(p, "location_ok").free_text == "học ở tp hcm"
    assert focus(p, "risk_tolerance").free_text == "thử thách"
    assert focus(p, "interest_fit") is p  # likes add up across messages
    assert mentions("budget_ok", "nhà em lo được 25 triệu") and not mentions("budget_ok", "thử thách")
