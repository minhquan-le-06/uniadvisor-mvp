"""Module 2's "Em chưa biết" group suggester (docs/MODEL.md): maths, plumbing, and the shipped model."""

import numpy as np
from scipy import sparse

from uniadvisor.student import suggest as sg
from uniadvisor.student.suggest import features as F
from uniadvisor.student.suggest.model import Model, fit, loss, softmax, targets
from uniadvisor.student.suggest.priors import Priors
from uniadvisor.student.suggest.suggester import Suggester


def small(seed: int = 0, n: int = 6, k: int = 4, d: int = 7):
    rng = np.random.default_rng(seed)
    X = sparse.csr_matrix(rng.random((n, d)) * (rng.random((n, d)) < 0.5))
    A, C = rng.random((n, k)), rng.random((n, k))
    Y = targets([[f"g{rng.integers(k)}"] for _ in range(n)], [f"g{i}" for i in range(k)])
    return X, A, C, Y


def test_targets_split_each_student_equally_over_its_groups():
    Y = targets([["a", "b"], ["c"]], ["a", "b", "c"])
    assert np.allclose(Y, [[0.5, 0.5, 0], [0, 0, 1]])


def test_gradient_matches_finite_differences():
    X, A, C, Y = small()
    k, d = Y.shape[1], X.shape[1]
    rng = np.random.default_rng(1)
    m = Model(rng.normal(size=(k, d)) * 0.1, rng.normal(size=k) * 0.1, 0.7, 1.3, np.ones(F.TEXT_DIM), [f"g{i}" for i in range(k)])
    lam = 0.01
    G = (m.proba(X, A, C) - Y) / len(Y)
    analytic = {"W": np.asarray((X.T @ G).T) + 2 * lam * m.W, "alpha": float((G * A).sum()), "beta": float((G * C).sum())}
    eps = 1e-6
    for name, idx in (("W", (1, 2)), ("W", (3, 0)), ("alpha", None), ("beta", None)):
        def at(delta):  # noqa: ANN001, ANN202
            mm = Model(m.W.copy(), m.b.copy(), m.alpha, m.beta, m.idf, m.groups)
            if idx is None:
                setattr(mm, name, getattr(mm, name) + delta)
            else:
                mm.W[idx] += delta
            return loss(mm, X, A, C, Y, lam)
        numeric = (at(eps) - at(-eps)) / (2 * eps)
        expected = analytic[name][idx] if idx is not None else analytic[name]
        assert abs(numeric - expected) < 1e-5


def test_training_lowers_the_loss_and_is_deterministic():
    X, A, C, Y = small(n=40)
    groups = [f"g{i}" for i in range(Y.shape[1])]
    m1 = fit(X, A, C, Y, groups, np.ones(F.TEXT_DIM), epochs=30, batch=8)
    m2 = fit(X, A, C, Y, groups, np.ones(F.TEXT_DIM), epochs=30, batch=8)
    assert m1.history[-1]["train_loss"] < m1.history[0]["train_loss"]
    assert np.allclose(m1.W, m2.W)


def test_softmax_rows_sum_to_one():
    assert np.allclose(softmax(np.array([[1000.0, 0.0], [1.0, 2.0]])).sum(axis=1), 1)


def test_features_fold_text_and_mark_answered_questions():
    f = F.Featurizer().fit([{"dream": "lam game"}])
    X = f.transform([{"subjects": ["TI"], "dream": "Làm GAME"}, {}])
    assert X[0, F.OFFSETS["subjects"] + F.SUBJ.index("TI")] == 1
    assert X[0, F.OFFSETS["answered"] + F.QUESTIONS.index("text")] == 1
    assert X[1].nnz == 0
    assert F.normalise("Em ko bit j") == "em khong biet gi"


def test_priors_point_to_the_expected_groups():
    p = Priors()
    top = [p.groups[i] for i in np.argsort(-p.subject_fit(["SI", "HO"]))[:5]]
    assert any(g.startswith("772") for g in top)                 # health
    assert p.work_fit(np.zeros(6)).max() == 0                     # nothing ticked
    e = p.work_fit(p.student_profile(["E"], []))
    assert p.groups[int(np.argmax(e))] in {"73401", "78101", "78102", "73404", "73801"}


def test_suggest_shows_three_to_five_and_nothing_for_no_answers():
    p = Priors()
    k = len(p.groups)
    s = Suggester(Model(np.zeros((k, F.DIM)), np.zeros(k), 1.0, 1.0, np.ones(F.TEXT_DIM), p.groups), p)
    out = s.suggest({"subjects": ["TI", "LI"], "work_types": ["I"]})
    assert 3 <= len(out) <= 5
    assert all(o["reasons"] for o in out)
    assert s.suggest({}) == []


def test_confident_learning_flags_only_students_whose_own_groups_are_not_confident():
    from uniadvisor.student.suggest.train import label_issues
    # 3 groups; thresholds come out as t = mean P of each group over its own students
    P = np.array([[0.8, 0.1, 0.1],     # group 0, confident in 0: kept
                  [0.6, 0.3, 0.1],     # group 0, confident in 0: kept
                  [0.1, 0.8, 0.1],     # group 1, confident in 1: kept
                  [0.9, 0.05, 0.05],   # labelled 1, only 0 confident: issue
                  [0.3, 0.3, 0.4],     # group 2, confident in 2: kept
                  [0.2, 0.2, 0.2]])    # labelled 2, nothing confident: kept (no better group either)
    labels = [[0], [0], [1], [1], [2], [2]]
    issues, t = label_issues(P, labels)
    assert np.allclose(t, [0.7, (0.8 + 0.05) / 2, 0.3])
    assert issues == [3]
    # a two-group student is kept when either of its groups is confident
    assert label_issues(P, [[0], [0], [1], [1, 0], [2], [2]])[0] == []


def test_test_rows_marked_n_are_left_out(tmp_path):
    from uniadvisor.student.suggest.train import reviewed
    f = tmp_path / "review.csv"
    f.write_text("﻿id,nhom_nganh,tra_loi,dung (y/n),ghi_chu\na,x,x,y,\nb,x,x, N ,sai\nc,x,x,,\n", encoding="utf-8")
    g = tmp_path / "review_sample.csv"
    g.write_text("id,nhom_nganh,tra_loi,dung (y/n),ghi_chu\nc,x,x,y,\n", encoding="utf-8")
    kept, info = reviewed([{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}], [f, g, tmp_path / "missing.csv"])
    assert [r["id"] for r in kept] == ["a", "c", "d"]
    assert info == {"marked_y": 2, "marked_n": 1, "unchecked": 1}


def test_the_shipped_model_suggests_fitting_groups():
    assert sg.available()
    it = sg.suggest({"subjects": ["TO", "TI"], "work_types": ["I"], "hobbies": ["code"],
                     "text": "em muon lam lap trinh vien phan mem"})
    assert 3 <= len(it) <= 5
    assert {"74801", "74802"} & {s["code"] for s in it[:2]}
    assert all(s["reasons"] for s in it)
    assert it == sg.suggest({"subjects": ["TO", "TI"], "work_types": ["I"], "hobbies": ["code"],
                             "text": "em muon lam lap trinh vien phan mem"})


def test_the_shipped_model_reads_free_text_alone_and_gives_nothing_for_nothing():
    it = sg.suggest({"text": "Em muốn làm bác sĩ chữa bệnh cứu người"})
    assert "77201" in {s["code"] for s in it}
    assert sg.suggest({}) == []
    assert sg.suggest({"subjects": [], "text": "  "}) == []


def test_guided_chat_em_chua_biet_suggests_and_adds_the_ticked_groups():
    from streamlit.testing.v1 import AppTest

    from unidata.paths import ROOT

    at = AppTest.from_file(str(ROOT / "app" / "pages" / "hoi_dap.py"), default_timeout=180).run()
    at.selectbox(key="f_e1").set_value("LI").run()
    at.selectbox(key="f_e2").set_value("TI").run()
    for i, v in enumerate([8.4, 7.0, 8.5, 9.0]):
        at.number_input(key=f"f_v{i}").set_value(v)
    at.button(key="f_next_scores").click().run()
    at.radio(key="f_gender").set_value("nam")
    at.button(key="f_next_about").click().run()
    at.button(key="f_unsure").click().run()
    at.multiselect(key="f_qz_work").set_value(["I", "R"])
    at.text_input(key="f_qz_dream").set_value("em thich lam robot va lap trinh dieu khien")
    at.button(key="f_qz_go").click().run()
    shown = [c.key for c in at.checkbox if c.key.startswith("f_sg_")]
    assert 3 <= len(shown) <= 5 and "f_sg_75201" in shown       # robots: Kỹ thuật cơ khí (Kỹ thuật Robot)
    at.button(key="f_sg_ok").click().run()
    assert not at.exception
    assert any("Kỹ thuật cơ khí" in m.value for m in at.markdown)
