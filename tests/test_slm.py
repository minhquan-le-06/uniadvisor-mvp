import random

import pytest

from uniadvisor.slm import teacher
from uniadvisor.slm.infer import HeuristicJudge, _budget, _likes
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
