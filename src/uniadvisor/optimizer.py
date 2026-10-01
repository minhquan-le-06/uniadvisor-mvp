"""Choose and order the application list to maximise expected utility.

    E = sum_i p_i * prod_{j before i} (1 - p_j) * u_i

In Vietnam a student is admitted to the highest-ranked wish whose cutoff they pass, and each p_i does
not depend on the order. Swapping two neighbours i, j changes E by p_i p_j (u_i - u_j), so for a fixed
set the best order is by utility, descending. What remains is *which* programs to include: an exact
dynamic programme over the utility-sorted candidates, with KB constraints (max number of wishes,
at least N 'safe' wishes, at most M wishes per school).

Ties: utilities within TIE of each other are within the precision of the soft judgments, so the order
between them is noise. The utility-sorted list is cut into groups whose members are all within TIE of the
group's best, and inside a group the higher forecast cutoff goes first (aim high, keep the easier program
as the fallback below it). Otherwise a near-certain program placed high makes every wish below it almost
worthless while being no clearer a preference than they are.

Assumes the p_i are independent given the student's score (cutoff errors differ per program); the
student's own score uncertainty makes them positively correlated, so P(admitted somewhere) is an
optimistic upper estimate when the score is a mock-exam estimate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Item:
    key: str
    p: float        # admission probability
    u: float        # utility in [0, 1]
    safe: bool
    school: str
    cutoff: float = 0.0  # forecast cutoff, breaks near-ties in utility (higher first)


TIE = 0.05


def expected_value(items: list[Item]) -> float:
    e, miss = 0.0, 1.0
    for it in items:
        e += miss * it.p * it.u
        miss *= 1 - it.p
    return e


def p_any(items: list[Item]) -> float:
    return 1.0 - float(np.prod([1 - it.p for it in items])) if items else 0.0


def _dp(items: list[Item], k_max: int, min_safe: int) -> list[Item]:
    n = len(items)
    NEG = -1e9
    # g[i][k][r]: best E from items[i:] using at most k slots while r more safe items are required
    g = np.full((n + 1, k_max + 1, min_safe + 1), NEG)
    g[n, :, 0] = 0.0
    take = np.zeros((n, k_max + 1, min_safe + 1), dtype=bool)
    for i in range(n - 1, -1, -1):
        it = items[i]
        for k in range(k_max + 1):
            for r in range(min_safe + 1):
                best = g[i + 1, k, r]
                if k >= 1:
                    r2 = max(0, r - (1 if it.safe else 0))
                    rest = g[i + 1, k - 1, r2]
                    if rest > NEG / 2:
                        val = it.p * it.u + (1 - it.p) * rest
                        if val > best + 1e-12:
                            best = val
                            take[i, k, r] = True
                g[i, k, r] = best
    chosen, k, r = [], k_max, min_safe
    if g[0, k, r] <= NEG / 2:  # constraint infeasible (not enough safe options): relax it
        return _dp(items, k_max, max(0, min_safe - 1)) if min_safe > 0 else []
    for i in range(n):
        if k >= 1 and take[i, k, r]:
            chosen.append(items[i])
            r = max(0, r - (1 if items[i].safe else 0))
            k -= 1
    return chosen


def order(items: list[Item]) -> list[Item]:
    """Utility descending, then within each group of near-equal utility (TIE) by cutoff descending."""
    rest = sorted(items, key=lambda it: (-it.u, -it.p, it.key))
    out: list[Item] = []
    while rest:
        top = rest[0].u
        group = [it for it in rest if it.u >= top - TIE]
        rest = rest[len(group):]
        out += sorted(group, key=lambda it: (-it.cutoff, -it.u, it.key))
    return out


def optimise(candidates: list[Item], k_max: int = 10, min_safe: int = 2, max_per_school: int = 4) -> list[Item]:
    items = sorted(candidates, key=lambda it: (-it.u, -it.p, it.key))
    banned: set[str] = set()
    for _ in range(50):
        chosen = _dp([it for it in items if it.key not in banned], k_max, min_safe)
        per_school: dict[str, list[Item]] = {}
        for it in chosen:
            per_school.setdefault(it.school, []).append(it)
        over = [sorted(v, key=lambda it: it.p * it.u)[0] for v in per_school.values() if len(v) > max_per_school]
        if not over:
            return order(chosen)
        banned |= {it.key for it in over}
    return order(chosen)
