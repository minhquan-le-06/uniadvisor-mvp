"""Behaviour checks for the group suggester, reviewed by a person (docs/MODEL.md, "Evaluation").

Following CheckList (Ribeiro et al. 2020), accuracy on the test set is not the whole story: a person reviews the
model's suggestions for many answer sets and the verdicts become checks that every later model is scored on.

1. `make_cases` writes review cases (backend/suggest_data/review_cases.jsonl): answer sets of four kinds. The case
   generator only has to cover the answer space; what a case should get is decided by the reviewer, not here.
   - clear: the answers of a student who fits one group (its most lifted subjects in the admission data, its top
     O*NET types, hobbies of those types, the workplace most often picked for it in the training set);
   - mixed: subjects from one group, work types and hobbies from another;
   - sparse: only one or two questions answered;
   - text: a clear case plus the free text of a test-set student of that group.
2. The reviewer (app/review_suggest.py, `uniadvisor suggest-review`) sees each case with the current top 5, unticks
   the groups that do not fit and adds the ones that should be there. Verdicts go to expectations.jsonl at once.
3. `check(suggester)` scores a model on every verdict: each added group must be in the top k (5 unless the verdict
   says otherwise), no unticked group may be in the top 3, and at least one kept group must stay in the top 5.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import numpy as np

from uniadvisor.student import suggest as sg
from uniadvisor.student.form.options import SUBJECTS
from unidata.paths import SUGGEST_DATA

CASES = SUGGEST_DATA / "review_cases.jsonl"
EXPECTATIONS = SUGGEST_DATA / "expectations.jsonl"
TYPES = ["R", "I", "A", "S", "E", "C"]
KINDS = {"clear": 0.4, "mixed": 0.2, "sparse": 0.2, "text": 0.2}
SEED = 7


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _profile(g: int, p, places: dict, rng: random.Random) -> dict:  # noqa: ANN001
    """Answers of a student who fits group index g."""
    lifted = [p.subjects[i] for i in np.argsort(-p.lift[:, g], kind="stable")[:4]]
    types = [TYPES[i] for i in np.argsort(-p.prof[g], kind="stable")[:2]]
    hobbies = [h for h, (_, t) in sg.HOBBIES.items() if t in types]
    code = p.groups[g]
    out = {"subjects": rng.sample(lifted, rng.choice([2, 3])),
           "work_types": rng.sample(types, rng.choice([1, 2])),
           "hobbies": rng.sample(hobbies, min(len(hobbies), rng.choice([1, 2, 3])))}
    if places.get(code) and rng.random() < 0.7:
        out["workplace"] = [places[code]]
    return out


def make_cases(n: int = 60, seed: int = SEED, extend: bool = False) -> list[dict]:
    """n generated cases. extend=True appends n new ones (own RNG stream, ids after the last C id) and keeps every
    existing case, so earlier verdicts stay attached to the same answers."""
    from uniadvisor.student.suggest.priors import Priors

    p = Priors()
    old = read(CASES) if CASES.exists() else []
    start = max((int(c["id"][1:]) for c in old if c["id"].startswith("C")), default=0) if extend else 0
    # start 0 = the original stream; cases also depend on train.jsonl (workplaces), so a full regeneration after a
    # training-set change gives different answers: use extend to add cases once verdicts exist
    rng = random.Random(seed if start == 0 else seed * 1000 + start)
    train = read(SUGGEST_DATA / "train.jsonl")
    places = {}
    for code in p.groups:
        c = Counter(w for r in train if code in r["groups"] for w in r["answers"].get("workplace") or [])
        places[code] = c.most_common(1)[0][0] if c else None
    texts: dict[str, list[str]] = {}
    for r in read(SUGGEST_DATA / "testset.jsonl"):
        t = (r["answers"].get("dream") or "").strip()
        if t:
            texts.setdefault(r["groups"][0], []).append(t)
    order = list(range(len(p.groups)))
    rng.shuffle(order)
    kinds = rng.choices(list(KINDS), weights=list(KINDS.values()), k=n)
    cases = []
    for i, kind in enumerate(kinds):
        g = order[i % len(order)]
        a = _profile(g, p, places, rng)
        if kind == "mixed":
            h = rng.choice([x for x in order if x != g])
            b = _profile(h, p, places, rng)
            a = {"subjects": a["subjects"], "work_types": b["work_types"], "hobbies": b["hobbies"],
                 **({"workplace": b["workplace"]} if "workplace" in b else {})}
        elif kind == "sparse":
            keep = rng.sample([k for k in a if a[k]], rng.choice([1, 2]))
            a = {k: a[k] for k in keep}
        elif kind == "text":
            pool = texts.get(p.groups[g])
            if pool:
                a["text"] = rng.choice(pool)
            else:
                kind = "clear"
        cases.append({"id": f"C{start + i + 1:03d}", "kind": kind, "answers": a})
    keep = old if extend else [c for c in old if c["kind"] == "user"]      # the reviewer's own cases are never dropped
    cases = keep + cases
    write(CASES, cases)
    return cases


def describe(a: dict) -> list[tuple[str, str]]:
    """(question, answer) in Vietnamese, for the reviewer."""
    return [
        ("Môn thích/học tốt", ", ".join(SUBJECTS.get(s, s) for s in a.get("subjects") or []) or "-"),
        ("Thích làm việc với", "; ".join(sg.WORK_TYPES[t] for t in a.get("work_types") or []) or "-"),
        ("Lúc rảnh", "; ".join(sg.HOBBIES[h][0] for h in a.get("hobbies") or []) or "-"),
        ("Muốn làm việc ở", "; ".join(sg.WORKPLACES[w] for w in a.get("workplace") or []) or "-"),
        ("Mơ ước, sở thích khác", " ".join(str(a.get(k) or "") for k in ("text", "dream", "other")).strip() or "-"),
    ]


def save_verdict(v: dict) -> None:
    """Insert or replace the verdict of case v["id"]."""
    rows = [r for r in read(EXPECTATIONS) if r["id"] != v["id"]]
    rows.append(v)
    rows.sort(key=lambda r: r["id"])
    write(EXPECTATIONS, rows)


def check_one(order: list[str], v: dict) -> dict:
    """order: group codes best first. Returns the three checks (None when the verdict has nothing to check)."""
    k = v.get("k", 5)
    added, dropped, kept = v.get("added") or [], v.get("dropped") or [], v.get("kept") or []
    return {"added_in_top": all(c in order[:k] for c in added) if added else None,
            "dropped_out_of_top3": not any(c in order[:3] for c in dropped) if dropped else None,
            "kept_in_top5": any(c in order[:5] for c in kept) if kept else None}


def check(s) -> dict:  # noqa: ANN001
    """Pass rates of a Suggester on every saved verdict, and the failing cases."""
    verdicts = read(EXPECTATIONS)
    if not verdicts:
        return {"n": 0}
    P = s.proba([v["answers"] for v in verdicts])
    totals: Counter = Counter()
    passed: Counter = Counter()
    failing = []
    for row, v in zip(P, verdicts):
        order = [s.m.groups[i] for i in s.ranked(row)]
        res = check_one(order, v)
        ok = all(x is not False for x in res.values())
        for name, x in res.items():
            if x is not None:
                totals[name] += 1
                passed[name] += x
        if not ok:
            failing.append({"id": v["id"], "top5": order[:5], **{k: x for k, x in res.items() if x is False}})
    cases_ok = len(verdicts) - len(failing)
    return {"n": len(verdicts), "cases_passed": round(cases_ok / len(verdicts), 4),
            **{name: f"{passed[name]}/{totals[name]}" for name in totals}, "failing": failing}
