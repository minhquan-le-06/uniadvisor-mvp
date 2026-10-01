"""Rubric teacher: labels (latent student, real program, question) following slm/questions.py rubrics.

It returns a *soft* label: K simulated annotators each apply the rubric, and each can slip (the
chance grows when the signal in the text is only implied, contradictory, or borderline). The soft
label is the vote share, like several passes of a teacher LLM. `slm/llm_teacher.py` can relabel the
same texts with a real LLM from the rubric alone; both write the same format.
"""

from __future__ import annotations

import random

from uniadvisor.slm.questions import BY_ID, DEFAULT_CORE, INSUFFICIENT
from uniadvisor.slm.synth import CORE_SUBJECTS, HUB_OF_REGION, RELATED, Latent

N_ANNOTATORS = 5


def _mix(votes: list[str], labels: tuple[str, ...]) -> dict[str, float]:
    out = {k: 0.0 for k in labels}
    for v in votes:
        out[v] += 1.0 / len(votes)
    return out


def _vote(truth: str, labels: tuple[str, ...], slip: float, rng: random.Random, kind: str, alt: str | None = None) -> dict[str, float]:
    """Each annotator gives `truth`, or slips with probability `slip` to a plausible neighbour."""
    votes = []
    for _ in range(N_ANNOTATORS):
        if rng.random() >= slip:
            votes.append(truth)
            continue
        if alt is not None:
            votes.append(alt)
        elif kind == "score" and truth != INSUFFICIENT:
            lvl = int(truth) + rng.choice([-1, 1])
            votes.append(str(min(5, max(1, lvl))))
        elif kind == "bool" and truth != INSUFFICIENT:
            votes.append(rng.choice(["yes" if truth == "no" else "no", INSUFFICIENT]))
        else:
            votes.append(rng.choice([x for x in labels if x != truth]))
    return _mix(votes, labels)


# ------------------------------------------------------------------ per question
def risk_tolerance(z: Latent, rng: random.Random) -> dict[str, float]:
    labels = BY_ID["risk_tolerance"].all_labels
    if z.risk is None:
        return _vote(INSUFFICIENT, labels, 0.05, rng, "choice", alt="can_bang")
    if z.risk_conflict:
        return _vote(INSUFFICIENT, labels, 0.5, rng, "choice", alt=z.risk)
    return _vote(z.risk, labels, 0.08, rng, "choice", alt="can_bang" if z.risk != "can_bang" else INSUFFICIENT)


def top_priority(z: Latent, rng: random.Random) -> dict[str, float]:
    labels = BY_ID["top_priority"].all_labels
    if z.priority is None:
        return _vote(INSUFFICIENT, labels, 0.08, rng, "choice")
    return _vote(z.priority, labels, 0.08, rng, "choice", alt=INSUFFICIENT)


def interest_fit(z: Latent, p: dict, rng: random.Random) -> dict[str, float]:
    labels = BY_ID["interest_fit"].all_labels
    f = p.get("field") or ""
    stated = dict(z.interests)
    if not stated and not z.dislikes and not z.parent_field:
        return _vote(INSUFFICIENT, labels, 0.05, rng, "score", alt="3")
    if f in z.dislikes:
        return _vote("1", labels, 0.1, rng, "score")
    if f in stated:
        return _vote("5" if stated[f] >= 1.0 else "4", labels, 0.1 if stated[f] >= 1.0 else 0.3, rng, "score",
                     alt="4" if stated[f] >= 1.0 else "5")
    if any(f in RELATED.get(g, []) for g in stated):
        return _vote("4", labels, 0.3, rng, "score", alt="3")
    if f and f == z.parent_field:
        return _vote("3" if z.accepts_parent else "2", labels, 0.25, rng, "score")
    if stated:
        return _vote("2", labels, 0.25, rng, "score", alt="3")
    return _vote("3", labels, 0.25, rng, "score", alt=INSUFFICIENT)


def _level(x: float) -> str:
    return "5" if x >= 8.5 else "4" if x >= 7.5 else "3" if x >= 6.5 else "2" if x >= 5.0 else "1"


def ability_fit(z: Latent, p: dict, rng: random.Random) -> dict[str, float]:
    labels = BY_ID["ability_fit"].all_labels
    core = CORE_SUBJECTS.get(p.get("field") or "", DEFAULT_CORE)
    have = [z.scores[s] for s in core if s in z.scores]
    # the English self-assessment ("Tiếng Anh em rất kém", "Em có IELTS 6.5") is a statement about English too
    strong = set(z.strong) | ({"N1"} if z.english in ("good", "ielts") else set())
    weak = set(z.weak) | ({"N1"} if z.english == "weak" else set())
    said_strong = [s for s in core if s in strong]
    said_weak = [s for s in core if s in weak]
    if not have and not said_strong and not said_weak:
        return _vote(INSUFFICIENT, labels, 0.1, rng, "score", alt="3")
    if have:
        # the most important core subject counts double
        w = [2.0 if s == core[0] else 1.0 for s in core if s in z.scores]
        x = sum(a * b for a, b in zip(have, w)) / sum(w)
        lvl = int(_level(x))
        lvl += 1 if said_strong and lvl < 5 else 0
        lvl -= 1 if said_weak and lvl > 1 else 0
        border = min(abs(x - t) for t in (5.0, 6.5, 7.5, 8.5))
        return _vote(str(lvl), labels, 0.3 if border < 0.25 else 0.1, rng, "score")
    return _vote("4" if said_strong else "2", labels, 0.3, rng, "score")


def budget_ok(z: Latent, p: dict, rng: random.Random) -> dict[str, float]:
    labels = BY_ID["budget_ok"].all_labels
    tmin, tmax = p.get("tuition_min"), p.get("tuition_max")
    known = tmin is not None and tmin == tmin
    if z.budget_kind is None or not known:
        return _vote(INSUFFICIENT, labels, 0.05, rng, "bool")
    if z.budget_kind == "rich":
        return _vote("yes", labels, 0.05, rng, "bool")
    if z.budget_kind == "poor":
        if tmax <= 15e6:
            return _vote("yes", labels, 0.2, rng, "bool")
        if tmin > 25e6:
            return _vote("no", labels, 0.1, rng, "bool")
        return _vote("no", labels, 0.5, rng, "bool", alt="yes")
    if tmax <= z.budget:
        return _vote("yes", labels, 0.05, rng, "bool")
    if tmin > 1.1 * z.budget:
        return _vote("no", labels, 0.05, rng, "bool")
    return _vote("yes", labels, 0.5, rng, "bool", alt="no")


def location_ok(z: Latent, p: dict, rng: random.Random) -> dict[str, float]:
    labels = BY_ID["location_ok"].all_labels
    city = p.get("city")
    campus = p.get("campus")
    branch = isinstance(campus, str) and campus.strip() != ""  # NaN is truthy: never use bool() on a cell
    if z.avoid_branch and branch:
        return _vote("no", labels, 0.1, rng, "bool")
    if z.location is None:
        return _vote(INSUFFICIENT, labels, 0.05, rng, "bool")
    if z.location == "anywhere":
        return _vote("yes", labels, 0.05, rng, "bool")
    if z.location == "no_big_city":
        return _vote("no", labels, 0.15, rng, "bool")
    if z.location.startswith("city:"):
        return _vote("yes" if (city == z.location.split(":", 1)[1] and not branch) else "no", labels, 0.05, rng, "bool")
    hub = HUB_OF_REGION[z.region]  # near_home
    if hub is None:
        return _vote(INSUFFICIENT, labels, 0.3, rng, "bool", alt="no")
    return _vote("yes" if city == hub and not branch else "no", labels, 0.1, rng, "bool")


def conditions_ok(z: Latent, p: dict, rng: random.Random) -> dict[str, float]:
    labels = BY_ID["conditions_ok"].all_labels
    cond = str(p.get("conditions") or "").lower()
    if not cond or cond == "nan":
        return _vote("yes", labels, 0.03, rng, "bool")
    verdicts = []  # (label, slip)
    if "tiếng anh" in cond:
        en = z.scores.get("N1")
        if z.english in ("good", "ielts") or (en is not None and en >= 7.0):
            verdicts.append(("yes", 0.08))
        elif z.english == "weak" or (en is not None and en < 5.0):
            verdicts.append(("no", 0.08))
        elif en is not None:
            verdicts.append(("yes", 0.45))
        else:
            verdicts.append((INSUFFICIENT, 0.15))
    if "sư phạm" in cond:
        verdicts.append(("no", 0.1) if z.speech_issue else ("yes", 0.08))
    if "chỉ tuyển thí sinh nam" in cond or "chỉ tuyển thí sinh nữ" in cond:
        need = "nam" if "thí sinh nam" in cond else "nu"
        verdicts.append((INSUFFICIENT, 0.1) if z.gender is None else (("yes" if z.gender == need else "no"), 0.03))
    if "học tại" in cond:
        verdicts.append(("no", 0.1) if z.avoid_branch else ("yes", 0.15))
    if not verdicts:  # only informational conditions (fees, ministry floors)
        return _vote("yes", labels, 0.05, rng, "bool")
    for want in ("no", INSUFFICIENT, "yes"):
        for lab, slip in verdicts:
            if lab == want:
                return _vote(lab, labels, slip, rng, "bool")
    raise AssertionError


PROFILE_FNS = {"risk_tolerance": risk_tolerance, "top_priority": top_priority}
PROGRAM_FNS = {"interest_fit": interest_fit, "ability_fit": ability_fit, "budget_ok": budget_ok,
               "location_ok": location_ok, "conditions_ok": conditions_ok}


def label(question_id: str, z: Latent, program: dict | None, rng: random.Random) -> dict[str, float]:
    if question_id in PROFILE_FNS:
        return PROFILE_FNS[question_id](z, rng)
    return PROGRAM_FNS[question_id](z, program, rng)
