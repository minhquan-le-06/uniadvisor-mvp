import itertools
import random

import numpy as np
import pytest

from uniadvisor.engine.dist import GRID, ScoreDistributions, cdf_from_bins, fit_affine, mean_of, quantile, transform
from uniadvisor.engine.forecast import ForecastParams, admit_probability, forecast_program
from uniadvisor.optimizer import Item, expected_value, optimise


def _normal_cdf(mu, sd):
    from scipy.stats import norm

    f = norm.cdf((GRID - mu) / sd)
    f[-1] = 1.0
    return f


def test_cdf_from_bins_is_a_cdf():
    bins = np.arange(0, 31)
    counts = np.exp(-((bins - 20) ** 2) / 20) * 1000
    f = cdf_from_bins(bins, counts)
    assert f[0] == pytest.approx(0, abs=1e-6) and f[-1] == 1.0 and np.all(np.diff(f) >= -1e-12)
    assert quantile(f, 0.5) == pytest.approx(20.5, abs=0.3)   # bins are [k, k+1)


def test_affine_fit_recovers_anchors():
    base = _normal_cdf(19, 3)
    # anchors of N(17, 4): an exact affine image of the base (a = 17 - 19*4/3, b = 4/3)
    a, b = fit_affine(base, [("p50", 17.0), ("p75", 19.70), ("p90", 22.13)])
    assert b == pytest.approx(4 / 3, abs=0.02)
    moved = transform(base, a, b)
    assert quantile(moved, 0.5) == pytest.approx(17.0, abs=0.05)
    assert quantile(moved, 0.9) == pytest.approx(22.13, abs=0.05)
    shifted = transform(base, *fit_affine(base, [("mean", 20.9)]))
    assert mean_of(shifted) == pytest.approx(20.9, abs=0.05)


def _dists(trusted_2025: bool):
    cdfs = {("A00", 2025): _normal_cdf(17, 3), ("A00", 2026): _normal_cdf(19, 3)}
    from uniadvisor.engine.dist import DistInfo

    meta = {("A00", 2025): DistInfo("A00", 2025, "observed" if trusted_2025 else "anchored", None, ""),
            ("A00", 2026): DistInfo("A00", 2026, "observed", None, "")}
    return ScoreDistributions(cdfs, meta)


def test_forecast_equates_only_trusted_years():
    hist = {2025: 22.0, 2026: 24.0}
    p = ForecastParams(recency=1.0, sigma_by_history={1: 1.0, 2: 1.0, 3: 1.0})
    trusted = forecast_program("x", "A00", hist, 2027, _dists(True), p)
    untrusted = forecast_program("x", "A00", hist, 2027, _dists(False), p)
    # 22 in a mean-17 year is the same percentile as 24 in a mean-19 year -> equated average is 24
    assert trusted.score == pytest.approx(24.0, abs=0.1) and trusted.equated == [True, False]
    assert untrusted.score == pytest.approx(23.0, abs=0.01) and untrusted.equated == [False, False]


def test_admit_probability_properties():
    fc = forecast_program("x", "A00", {2026: 24.0}, 2027, _dists(True), ForecastParams())
    ps = [admit_probability(fc, t) for t in (20, 23, 24, 25, 28)]
    assert all(np.diff(ps) > 0) and ps[2] == pytest.approx(0.5, abs=1e-6)
    # score uncertainty pulls probabilities towards 0.5
    assert admit_probability(fc, 26, student_sd=2.0) < admit_probability(fc, 26)
    lo, hi = fc.interval(0.8)
    assert lo < fc.score < hi


def _brute(items, k, min_safe, max_per_school):
    best, best_set = -1, None
    for r in range(1, k + 1):
        for combo in itertools.combinations(items, r):
            if sum(i.safe for i in combo) < min_safe:
                continue
            if max(sum(1 for i in combo if i.school == s) for s in {i.school for i in combo}) > max_per_school:
                continue
            ordered = sorted(combo, key=lambda it: -it.u)
            v = expected_value(ordered)
            if v > best:
                best, best_set = v, ordered
    return best, best_set


@pytest.mark.parametrize("seed", range(8))
def test_optimiser_matches_brute_force(seed):
    rng = random.Random(seed)
    items = [Item(f"p{i}", round(rng.uniform(0.05, 0.99), 3), round(rng.uniform(0.1, 1), 3), False, rng.choice("AB")) for i in range(8)]
    for it in items:
        it.safe = it.p >= 0.8
    k, min_safe = 4, 1
    best, _ = _brute(items, k, min_safe, max_per_school=4)
    got = optimise(items, k_max=k, min_safe=min_safe, max_per_school=4)
    if best >= 0:
        assert expected_value(got) == pytest.approx(best, abs=1e-9)
        assert [i.u for i in got] == sorted((i.u for i in got), reverse=True)
        assert sum(i.safe for i in got) >= min_safe


def test_order_by_utility_is_optimal_for_fixed_set():
    a, b = Item("a", 0.3, 0.9, False, "X"), Item("b", 0.9, 0.5, True, "Y")
    assert expected_value([a, b]) > expected_value([b, a])


def test_max_per_school():
    items = [Item(f"a{i}", 0.9, 0.9 - i * 0.01, True, "A") for i in range(6)] + [Item("b", 0.5, 0.3, False, "B")]
    got = optimise(items, k_max=6, min_safe=1, max_per_school=3)
    assert sum(i.school == "A" for i in got) <= 3
