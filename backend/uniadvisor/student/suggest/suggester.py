"""The trained model applied to one student: ranked nhóm ngành with reasons (docs/MODEL.md, "Output").

Always the top 5 groups (it was "at least 3, more if within 0.6 of the best"; the reviewed cases showed the right
second direction of a mixed student often sits at 4-5); ties go to the group with more programs, then the lower
code. Reasons are the inputs that pushed a group above the others most. No answers, no suggestions.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from uniadvisor.student import suggest as sg
from uniadvisor.student.form.options import SUBJECTS
from uniadvisor.student.suggest import features as F
from uniadvisor.student.suggest.model import Model, softmax
from uniadvisor.student.suggest.priors import Priors

SHOWN = 5
# Popularity weight: z_k += POPULARITY * (log places_k - mean). The model learns from students spread evenly over the
# groups, so it has no idea that Kinh doanh takes ~10% of students and Kinh tế học ~3%; adding the log of the real
# share corrects a classifier for a new class prior (Saerens et al. 2002), and a fraction of it only part of the way.
# 0.2 (docs/MODEL.md, "Popularity"): popular groups come up about as often as their share of places at little cost on
# the evenly spread test set; 0.4 and more lets a few large groups crowd the top 5. Prediction only; training ignores it.
POPULARITY = 0.2
# Groups few students choose in real life (under 0.3% of all places: 24 groups such as Công nghệ dệt, may, Thủy sản,
# Lâm nghiệp) lose a further 0.5. The log term above is too gentle at the bottom: Công nghệ dệt, may (4 programs,
# 0.3% of places) was in the top 5 of 14% of random answer sets and the reviewer unticked it in 7 of 8 cases.
UNPOPULAR = (0.003, 0.5)        # (share of places below which, penalty)
# Options whose label names a group act as a keyword for it in generated data (the writer, told the group, ticks the
# option that names it: "Du lịch, tìm hiểu văn hóa, ngoại ngữ" was ticked by 65% of Du lịch's training students
# against 14% of all), a shortcut (Geirhos et al. 2020). Their learned weights are ignored; the free text still counts.
SHORTCUT_OPTIONS = {"hobbies": ["du_lich"]}


class Suggester:
    def __init__(self, model: Model, priors: Priors | None = None, popularity: float = POPULARITY,
                 unpopular: tuple[float, float] = UNPOPULAR, shortcuts: dict | None = None):
        self.p = priors or Priors()
        if self.p.groups != model.groups:
            raise ValueError("the model and priors.json list different groups: rebuild priors and retrain")
        self.f = F.Featurizer(model.idf)
        cols = [F.OFFSETS[q] + F.KEYS[q].index(o) for q, opts in (SHORTCUT_OPTIONS if shortcuts is None else shortcuts).items()
                for o in opts]
        if cols:                         # the same weight for every group = no effect on the probabilities
            W = model.W.copy()
            W[:, cols] = W[:, cols].mean(axis=0)
            model = replace(model, W=W)
        self.m = model
        self.popularity, self.unpopular = popularity, unpopular
        share = np.exp(self.p.log_places) / np.exp(self.p.log_places).sum()
        self.shift = popularity * self.p.log_places - unpopular[1] * (share < unpopular[0])

    @classmethod
    def load(cls, path: Path) -> "Suggester":
        return cls(Model.load(path))

    def inputs(self, answers: list[dict]) -> tuple:
        X = self.f.transform(answers)
        A = np.array([self.p.subject_fit(a.get("subjects") or []) for a in answers])
        C = np.array([self.p.work_fit(self.p.student_profile(a.get("work_types") or [], F.hobby_types(a)))
                      for a in answers])
        return X, A, C

    def proba(self, answers: list[dict]) -> np.ndarray:
        return self.proba_of(*self.inputs(answers))

    def proba_of(self, X, A, C) -> np.ndarray:  # noqa: ANN001
        """softmax(model scores + popularity shift)."""
        return softmax(self.m.scores(X, A, C) + self.shift)

    def ranked(self, proba_row: np.ndarray) -> list[int]:
        """Group indices, best first, with the stable tie-break (more programs, then lower code)."""
        return sorted(range(len(proba_row)), key=lambda k: (-proba_row[k], -self.p.n_programs[k], self.m.groups[k]))

    def suggest(self, a: dict) -> list[dict]:
        if not any(F.answered(a)):
            return []
        X, A, C = self.inputs([a])
        P = self.proba_of(X, A, C)[0]
        return [{"code": self.m.groups[k], "score": round(float(P[k]), 4), "reasons": self.reasons(a, X, A, C, k)}
                for k in self.ranked(P)[:SHOWN]]

    def breakdown(self, a: dict, top: int = 10) -> dict:
        """For diagnosis: the score z_k of the `top` best groups split into its parts (docs/MODEL.md, H),
        z_k = ticked answers + text + bias + alpha a_k + beta c_k + popularity, with f(x)_k = softmax(z)_k. Only
        differences between groups matter. Also the student's RIASEC profile and the text as the model reads it."""
        X, A, C = self.inputs([a])
        x = X.getrow(0)
        mask = x.indices >= F.TEXT_OFFSET
        W = self.m.W
        answers_part = W[:, x.indices[~mask]] @ x.data[~mask]
        text_part = W[:, x.indices[mask]] @ x.data[mask]
        z = answers_part + text_part + self.m.b + self.m.alpha * A[0] + self.m.beta * C[0] + self.shift
        P = self.proba_of(X, A, C)[0]
        order = self.ranked(P)
        shown = set(order[:SHOWN])
        rows = [{"rank": i + 1, "code": self.m.groups[k], "p": float(P[k]), "z": float(z[k]),
                 "answers": float(answers_part[k]), "text": float(text_part[k]), "bias": float(self.m.b[k]),
                 "a": float(A[0, k]), "alpha_a": float(self.m.alpha * A[0, k]),
                 "c": float(C[0, k]), "beta_c": float(self.m.beta * C[0, k]), "popularity": float(self.shift[k]),
                 "shown": k in shown}
                for i, k in enumerate(order[:top])]
        u = self.p.student_profile(a.get("work_types") or [], F.hobby_types(a))
        return {"rows": rows, "alpha": self.m.alpha, "beta": self.m.beta, "popularity": self.popularity,
                "unpopular": self.unpopular,
                "riasec": dict(zip(["R", "I", "A", "S", "E", "C"], u.tolist())),
                "text": F.normalise(F.text_of(a)), "rule": f"top {SHOWN}"}

    def reasons(self, a: dict, X, A, C, k: int, n: int = 2) -> list[str]:  # noqa: ANN001
        """The inputs that raise group k's score above the average group's most, in Vietnamese."""
        x = X.getrow(0)
        W = self.m.W
        found: list[tuple[float, str]] = []
        text_total = 0.0
        for j, v in zip(x.indices, x.data):
            rel = (W[k, j] - W[:, j].mean()) * v
            if j >= F.TEXT_OFFSET:
                text_total += rel
            elif (why := F.describe(j)) and rel > 0:
                found.append((rel, why))
        if text_total > 0:
            snippet = F.text_of(a)
            found.append((text_total, f'em viết "{snippet[:60]}{"..." if len(snippet) > 60 else ""}"'))
        rel_a = self.m.alpha * (A[0, k] - A[0].mean())
        if rel_a > 0 and a.get("subjects"):
            s = max(a["subjects"], key=lambda s: self.p.lift[self.p.subjects.index(s), k] if s in self.p.subjects else 0)
            found.append((rel_a, f"em thích hoặc học tốt {SUBJECTS.get(s, s)}"))
        rel_c = self.m.beta * (C[0, k] - C[0].mean())
        if rel_c > 0 and (a.get("work_types") or a.get("hobbies")):
            u = self.p.student_profile(a.get("work_types") or [], F.hobby_types(a))
            t = ["R", "I", "A", "S", "E", "C"][int(np.argmax(u))]
            found.append((rel_c, "em thích " + sg.WORK_TYPES[t].lower()))
        out: list[str] = []
        for _, why in sorted(found, key=lambda x: -x[0]):
            if why not in out:
                out.append(why)
        return out[:n]
