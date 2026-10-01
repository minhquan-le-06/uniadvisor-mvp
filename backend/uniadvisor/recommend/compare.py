"""Multi-criteria comparison: turn engine numbers + SLM answers into criteria scores in [0, 1],
weight them by the student's goal profile, and say which criteria each program wins or loses on."""

from __future__ import annotations

import numpy as np

from uniadvisor.student.slm.infer import Answer
from uniadvisor.student.slm.questions import INSUFFICIENT

CRITERIA = {
    "fit": "Hợp sở thích",
    "ability": "Hợp năng lực",
    "tuition": "Học phí",
    "location": "Địa điểm",
    "selectivity": "Độ cạnh tranh / uy tín",
}
BASE_WEIGHTS = {"fit": 0.35, "ability": 0.15, "tuition": 0.15, "location": 0.15, "selectivity": 0.20}
PRIORITY_TO_CRITERION = {
    "nganh_yeu_thich": "fit",
    "truong_danh_tieng": "selectivity",
    "hoc_phi_thap": "tuition",
    "gan_nha": "location",
    # No employment data in the MVP: selectivity is used as the (weak) proxy and the UI says so.
    "viec_lam_thu_nhap": "selectivity",
}
NEUTRAL = 0.5


def weights_for(top_priority: str | None, override: dict[str, float] | None = None) -> dict[str, float]:
    w = dict(BASE_WEIGHTS)
    if override:
        w.update({k: float(v) for k, v in override.items() if k in w})
    elif top_priority in PRIORITY_TO_CRITERION:
        w[PRIORITY_TO_CRITERION[top_priority]] *= 2.5
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


def _level01(a: Answer | None) -> float:
    if a is None:
        return NEUTRAL
    lvl = a.expected_level()
    if lvl is None:
        return NEUTRAL
    suff = 1 - a.p(INSUFFICIENT)
    return float(suff * (lvl - 1) / 4 + (1 - suff) * NEUTRAL)


def _yes01(a: Answer | None, prior: float = NEUTRAL) -> float:
    if a is None:
        return prior
    return float(a.p("yes") + a.p(INSUFFICIENT) * prior)


def criteria(program: dict, forecast_score: float | None, answers: dict[str, Answer], tuition_rank: float | None) -> dict[str, float]:
    """tuition_rank: 0 = cheapest in the candidate set, 1 = most expensive (used when budget is unknown)."""
    tuition_prior = NEUTRAL if tuition_rank is None else 1.0 - 0.6 * tuition_rank
    sel = NEUTRAL if forecast_score is None else float(np.clip((forecast_score - 15.0) / 14.0, 0, 1))
    return {
        "fit": _level01(answers.get("interest_fit")),
        "ability": _level01(answers.get("ability_fit")),
        "tuition": _yes01(answers.get("budget_ok"), tuition_prior),
        "location": _yes01(answers.get("location_ok"), 0.6),
        "selectivity": sel,
    }


def utility(crit: dict[str, float], weights: dict[str, float], conditions: Answer | None) -> float:
    u = sum(weights[k] * crit[k] for k in weights)
    if conditions is not None:
        u *= 1.0 - 0.8 * conditions.p("no")  # a program the student cannot meet is nearly worthless to them
    return float(np.clip(u, 0, 1))


def wins_losses(crit: dict[str, float], others: list[dict[str, float]], margin: float = 0.15) -> tuple[list[str], list[str]]:
    wins, losses = [], []
    if not others:
        return wins, losses
    for k in CRITERIA:
        med = float(np.median([o[k] for o in others]))
        if crit[k] >= med + margin:
            wins.append(CRITERIA[k])
        elif crit[k] <= med - margin:
            losses.append(CRITERIA[k])
    return wins, losses
