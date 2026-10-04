"""The trained model applied to one student: ranked nhóm ngành with reasons (docs/MODEL.md, "Output").

Always the top 5 groups (it was "at least 3, more if within 0.6 of the best"; the reviewed cases showed the right
second direction of a mixed student often sits at 4-5); ties go to the group with more programs, then the lower
code. Reasons are the inputs that pushed a group above the others most. No answers, no suggestions.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from uniadvisor.student import suggest as sg
from uniadvisor.student.form.options import SUBJECTS
from uniadvisor.student.suggest import features as F
from uniadvisor.student.suggest.model import Model
from uniadvisor.student.suggest.priors import Priors

SHOWN = 5


class Suggester:
    def __init__(self, model: Model, priors: Priors | None = None):
        self.m = model
        self.p = priors or Priors()
        if self.p.groups != model.groups:
            raise ValueError("the model and priors.json list different groups: rebuild priors and retrain")
        self.f = F.Featurizer(model.idf)

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
        return self.m.proba(*self.inputs(answers))

    def ranked(self, proba_row: np.ndarray) -> list[int]:
        """Group indices, best first, with the stable tie-break (more programs, then lower code)."""
        return sorted(range(len(proba_row)), key=lambda k: (-proba_row[k], -self.p.n_programs[k], self.m.groups[k]))

    def suggest(self, a: dict) -> list[dict]:
        if not any(F.answered(a)):
            return []
        X, A, C = self.inputs([a])
        P = self.m.proba(X, A, C)[0]
        return [{"code": self.m.groups[k], "score": round(float(P[k]), 4), "reasons": self.reasons(a, X, A, C, k)}
                for k in self.ranked(P)[:SHOWN]]

    def breakdown(self, a: dict, top: int = 10) -> dict:
        """For diagnosis: the score z_k of the `top` best groups split into its parts (docs/MODEL.md, H),
        z_k = ticked answers + text + bias + alpha a_k + beta c_k, with f(x)_k = softmax(z)_k. Only differences between
        groups matter. Also the student's RIASEC profile and the text as the model reads it."""
        X, A, C = self.inputs([a])
        x = X.getrow(0)
        mask = x.indices >= F.TEXT_OFFSET
        W = self.m.W
        answers_part = W[:, x.indices[~mask]] @ x.data[~mask]
        text_part = W[:, x.indices[mask]] @ x.data[mask]
        z = answers_part + text_part + self.m.b + self.m.alpha * A[0] + self.m.beta * C[0]
        P = self.m.proba(X, A, C)[0]
        order = self.ranked(P)
        shown = set(order[:SHOWN])
        rows = [{"rank": i + 1, "code": self.m.groups[k], "p": float(P[k]), "z": float(z[k]),
                 "answers": float(answers_part[k]), "text": float(text_part[k]), "bias": float(self.m.b[k]),
                 "a": float(A[0, k]), "alpha_a": float(self.m.alpha * A[0, k]),
                 "c": float(C[0, k]), "beta_c": float(self.m.beta * C[0, k]), "shown": k in shown}
                for i, k in enumerate(order[:top])]
        u = self.p.student_profile(a.get("work_types") or [], F.hobby_types(a))
        return {"rows": rows, "alpha": self.m.alpha, "beta": self.m.beta,
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
