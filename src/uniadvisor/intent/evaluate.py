"""Score the intent reader fact by fact against synthetic students whose true facts are known (slm/synth.py Latent).

For a fact with one value (budget, location, risk, ...): of the students whose text states it, how many were read
right, read as something else, or missed; of those whose text does not state it, how many got a value anyway.
For areas of study (MOET codes): which programs the read codes take in versus the true codes, over the database's
programs with a MOET code, as precision and recall.

The texts come from the generator's phrase banks, so these numbers say how well the reader covers that phrasing,
not how it does on real students. The interest lexicon (config/interests.yaml) is written independently of the
phrase banks; today's field-level reading (slm/infer.py) uses the phrase banks themselves.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache

import numpy as np

from uniadvisor.db import Database, get_db
from uniadvisor.intent import StudentIntent, covers
from uniadvisor.intent.keywords import extract
from uniadvisor.slm.synth import Latent, ProfileGenerator

SINGLE = ("budget", "location", "avoid_branch", "risk", "priority", "english", "speech_issue", "family_agrees")
AREAS = ("interests", "dislikes", "family")


def truth(z: Latent) -> dict:
    """The facts a student's text states, from the generator's hidden attributes (None: not stated)."""
    return {
        "interests": {c for cs in z.interest_codes for c in cs},
        "dislikes": {c for cs in z.dislike_codes for c in cs},
        "family": set(z.parent_codes),
        "family_agrees": z.accepts_parent if z.parent_field else None,
        "budget": z.budget if z.budget_kind == "number" else z.budget_kind,
        "location": z.location,
        "avoid_branch": True if z.avoid_branch else None,
        "risk": None if z.risk_conflict else z.risk,    # two attitudes in one text: the reader should not pick one
        "priority": z.priority,
        "english": z.english,
        "speech_issue": True if z.speech_issue else None,
        "strong": set(z.strong) - {"N1"},                # English is its own fact
        "weak": set(z.weak) - {"N1"},
        "implied": [c < 1.0 for _, c in z.interests],
    }


def read(intent: StudentIntent) -> dict:
    v = lambda f: None if f is None else f.value  # noqa: E731
    return {
        "interests": intent.codes("interests"), "dislikes": intent.codes("dislikes"),
        "family": set(intent.family.codes) if intent.family else set(), "family_agrees": intent.family_agrees,
        **{k: v(getattr(intent, k)) for k in SINGLE if k != "family_agrees"},
        "strong": set(intent.strong), "weak": set(intent.weak),
    }


def _same(fact: str, t, r) -> bool:  # noqa: ANN001
    if fact == "budget" and isinstance(t, float) and isinstance(r, float):
        return abs(t - r) < 0.5e6
    return t == r


class _Programs:
    """The database's MOET-coded programs, and which of them a set of area codes takes in."""

    def __init__(self, db: Database):
        codes = db["programs"].major_code.fillna("").astype(str)
        self.codes = codes[codes != ""].to_numpy()

    @lru_cache(maxsize=4096)  # noqa: B019 - one instance per evaluation
    def mask(self, code: str) -> np.ndarray:
        return np.array([covers(code, c) for c in self.codes])

    def taken(self, codes: set[str]) -> np.ndarray:
        m = np.zeros(len(self.codes), dtype=bool)
        for c in codes:
            m |= self.mask(c)
        return m


def evaluate(n_students: int = 2000, seed: int = 99, db: Database | None = None) -> dict:
    db = db or get_db()
    progs = _Programs(db)
    gen = ProfileGenerator(seed)
    single = {f: Counter() for f in SINGLE}
    areas = {f: Counter() for f in AREAS}
    subjects = {f: Counter() for f in ("strong", "weak")}
    implied = Counter()
    examples: dict[str, list] = {}
    for _ in range(n_students):
        z = gen.latent()
        text = gen.text(z)
        t, r = truth(z), read(extract(text))
        for f in SINGLE:
            c = single[f]
            if t[f] is None:
                c["unstated"] += 1
                c["false_read"] += r[f] is not None
            else:
                c["stated"] += 1
                key = "right" if _same(f, t[f], r[f]) else "missed" if r[f] is None else "wrong"
                c[key] += 1
                if key != "right" and len(examples.setdefault(f, [])) < 5:
                    examples[f].append({"text": text, "truth": t[f], "read": r[f]})
        for f in AREAS:
            c = areas[f]
            tm, rm = progs.taken(t[f]), progs.taken(r[f])
            if not t[f]:
                c["unstated"] += 1
                c["false_read"] += bool(r[f])
                continue
            c["stated"] += 1
            c["missed"] += not r[f]
            c["true_programs"] += int(tm.sum())
            c["read_programs"] += int(rm.sum())
            c["both"] += int((tm & rm).sum())
            c["exact"] += bool(tm.sum()) and bool((tm == rm).all())
            if not (tm & rm).any() and len(examples.setdefault(f, [])) < 5:
                examples[f].append({"text": text, "truth": sorted(t[f]), "read": sorted(r[f])})
        for f in ("strong", "weak"):
            subjects[f]["true"] += len(t[f])
            subjects[f]["read"] += len(r[f])
            subjects[f]["both"] += len(t[f] & r[f])
        if len(t["implied"]) == 1 and len(r["interests"]) and len(extract(text).interests) == 1:
            implied["n"] += 1
            implied["right"] += extract(text).interests[0].implied == t["implied"][0]

    def rate(a: int, b: int) -> float | None:
        return round(a / b, 3) if b else None

    out = {"students": n_students, "seed": seed, "database": db.name, "programs_with_code": len(progs.codes), "single": {}, "areas": {}}
    for f, c in single.items():
        out["single"][f] = {"stated": c["stated"], "right": rate(c["right"], c["stated"]), "wrong": rate(c["wrong"], c["stated"]),
                            "missed": rate(c["missed"], c["stated"]), "unstated": c["unstated"],
                            "false_read": rate(c["false_read"], c["unstated"])}
    for f, c in areas.items():
        out["areas"][f] = {"stated": c["stated"], "precision": rate(c["both"], c["read_programs"]),
                           "recall": rate(c["both"], c["true_programs"]), "exact": rate(c["exact"], c["stated"]),
                           "missed": rate(c["missed"], c["stated"]), "unstated": c["unstated"],
                           "false_read": rate(c["false_read"], c["unstated"])}
    out["subjects"] = {f: {"precision": rate(c["both"], c["read"]), "recall": rate(c["both"], c["true"])} for f, c in subjects.items()}
    out["implied_flag"] = {"n": implied["n"], "right": rate(implied["right"], implied["n"])}
    out["examples"] = examples
    return out


LABELS = {"budget": "Budget (amount, or poor / rich)", "location": "Location", "avoid_branch": "Main campus only",
          "risk": "Risk attitude", "priority": "Top priority", "english": "English level", "speech_issue": "Speech difficulty",
          "family_agrees": "Goes along with the family's wish", "interests": "Interests", "dislikes": "Dislikes",
          "family": "Family's wish", "strong": "Strong subjects", "weak": "Weak subjects"}


def markdown(r: dict) -> str:
    pct = lambda x: "-" if x is None else f"{x:.0%}"  # noqa: E731
    lines = [
        "# Intent reader: fact-by-fact evaluation", "",
        f"{r['students']} synthetic students (seed {r['seed']}), keyword reader (`uniadvisor.intent.keywords`). "
        "Regenerate with `uniadvisor intent-eval`. The texts come from the generator's phrase banks: these numbers "
        "measure coverage of that phrasing, not accuracy on real students.", "",
        "## Facts with one value", "",
        "| Fact | Stated | Read right | Read wrong | Missed | Not stated | Read anyway |", "|---|---|---|---|---|---|---|",
    ]
    for f, s in r["single"].items():
        lines.append(f"| {LABELS[f]} | {s['stated']} | {pct(s['right'])} | {pct(s['wrong'])} | {pct(s['missed'])} | "
                     f"{s['unstated']} | {pct(s['false_read'])} |")
    lines += [
        "", "## Areas of study (MOET codes)", "",
        f"Judged by the programs the codes take in, over the {r['programs_with_code']} programs with a MOET code: "
        "precision = of the programs the read codes take in, the share the true codes also take in; recall = the reverse; "
        "exact = the same programs.", "",
        "| Fact | Stated | Precision | Recall | Exact | Missed | Not stated | Read anyway |", "|---|---|---|---|---|---|---|---|",
    ]
    for f, s in r["areas"].items():
        lines.append(f"| {LABELS[f]} | {s['stated']} | {pct(s['precision'])} | {pct(s['recall'])} | {pct(s['exact'])} | "
                     f"{pct(s['missed'])} | {s['unstated']} | {pct(s['false_read'])} |")
    lines += ["", "## Subjects", "", "| Fact | Precision | Recall |", "|---|---|---|"]
    for f, s in r["subjects"].items():
        lines.append(f"| {LABELS[f]} | {pct(s['precision'])} | {pct(s['recall'])} |")
    lines += ["", f"Stated vs hobby (one interest, read as one): {pct(r['implied_flag']['right'])} right "
              f"({r['implied_flag']['n']} students).", ""]
    return "\n".join(lines)
