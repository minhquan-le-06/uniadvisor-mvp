"""Score distributions per (combination, year) on the 30-point scale.

Each distribution is a CDF F(x) = P(total <= x) on a fixed grid 0.00, 0.05, ..., 30.00, plus a
`method` saying how it was built (best first; the database also files each under a provenance class):

  exact        per-candidate scores dropped into data/inbox/ (best)
  observed     real histogram of that combination that year (VnExpress, 1-point bins)
  synthesized  built from that year's real per-subject histograms with a Gaussian copula whose
               correlation is fitted on the observed combinations (stated assumption)
  anchored     the latest shape moved/stretched to match percentiles or a mean the ministry published
  year_shift   the latest shape moved by the average shift of the anchored combinations that year
               (weakest; the forecast treats these years with extra uncertainty)
  simulated    made up for a simulated database (uniadvisor.sim)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from scipy.stats import norm

GRID = np.round(np.arange(0, 30.0001, 0.05), 2)
METHOD_RANK = {"exact": 0, "observed": 1, "synthesized": 2, "anchored": 3, "year_shift": 4, "simulated": 5}
# the provenance class (db/schema.py) each method belongs to
METHOD_PROVENANCE = {"exact": "derived", "observed": "observed", "synthesized": "estimated", "anchored": "estimated",
                     "year_shift": "estimated", "simulated": "simulated"}


# ---------------------------------------------------------------- building CDFs
def cdf_from_bins(bin_low: np.ndarray, counts: np.ndarray) -> np.ndarray:
    """1-point bins [k, k+1) plus an exact-30 bin -> smooth monotone CDF on GRID (PCHIP through bin edges)."""
    order = np.argsort(bin_low)
    bin_low, counts = np.asarray(bin_low, float)[order], np.asarray(counts, float)[order]
    n = counts.sum()
    edges = np.arange(0, 31)
    below = np.array([counts[bin_low < k].sum() / n for k in edges])  # P(total < k)
    f = PchipInterpolator(edges, below)(GRID)
    f = np.clip(np.maximum.accumulate(f), 0, 1)
    f[-1] = 1.0
    return f


def cdf_from_samples(totals: np.ndarray) -> np.ndarray:
    totals = np.clip(np.round(np.asarray(totals, float), 2), 0, 30)
    s = np.sort(totals)
    f = np.searchsorted(s, GRID + 1e-9, side="right") / len(s)
    f[-1] = 1.0
    return f


def quantile(cdf: np.ndarray, p: float | np.ndarray) -> np.ndarray:
    """Inverse of a CDF on GRID (linear between grid points)."""
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    f = np.maximum.accumulate(cdf + np.arange(len(cdf)) * 1e-12)  # strictly increasing for interp
    return np.interp(p, f, GRID)


def mean_of(cdf: np.ndarray) -> float:
    return float(np.trapezoid(1.0 - cdf, GRID))


def transform(cdf: np.ndarray, a: float, b: float) -> np.ndarray:
    """Distribution of a + b * X where X ~ cdf, clipped to [0, 30]."""
    x = (GRID - a) / b
    f = np.interp(x, GRID, cdf, left=0.0, right=1.0)
    f[-1] = 1.0
    return np.maximum.accumulate(f)


def fit_affine(base: np.ndarray, anchors: list[tuple[str, float]]) -> tuple[float, float]:
    """Fit a + b*X to anchors [('p50', 17.6), ('mean', 20.9), ...]. Mean-only -> pure shift."""
    qs = [(float(k[1:]) / 100, v) for k, v in anchors if k.startswith("p")]
    means = [v for k, v in anchors if k == "mean"]
    if len(qs) >= 2:
        x = np.array([quantile(base, p) for p, _ in qs])
        y = np.array([v for _, v in qs])
        b, a = np.polyfit(x, y, 1)
        b = float(np.clip(b, 0.6, 1.6))
        a = float(np.mean(y - b * x))
        return a, b
    if qs:
        p, v = qs[0]
        return float(v - quantile(base, p)), 1.0
    if means:
        return float(means[0] - mean_of(base)), 1.0
    raise ValueError("no anchors")


# ---------------------------------------------------------------- copula synthesis
def subject_quantile_fn(scores: np.ndarray, counts: np.ndarray):  # noqa: ANN201
    order = np.argsort(scores)
    s, c = np.asarray(scores, float)[order], np.asarray(counts, float)[order]
    cum = np.cumsum(c) / c.sum()

    def q(u: np.ndarray) -> np.ndarray:
        idx = np.searchsorted(cum, u, side="left")
        return s[np.clip(idx, 0, len(s) - 1)]

    return q


def synthesize(subject_q: dict[str, callable], subjects: list[str], rho: float, n: int = 200_000, seed: int = 7) -> np.ndarray:
    k = len(subjects)
    cov = np.full((k, k), rho) + np.eye(k) * (1 - rho)
    rng = np.random.default_rng(seed)
    z = rng.multivariate_normal(np.zeros(k), cov, size=n)
    u = norm.cdf(z)
    total = sum(subject_q[s](u[:, i]) for i, s in enumerate(subjects))
    return cdf_from_samples(total)


def ks(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.max(np.abs(a - b)))


# ---------------------------------------------------------------- lookup object
@dataclass
class DistInfo:
    combo: str
    year: int
    method: str
    n: int | None
    note: str


class ScoreDistributions:
    """The database's distributions (Database.distributions builds it from distributions.parquet + .csv)."""

    def __init__(self, cdfs: dict[tuple[str, int], np.ndarray], meta: dict[tuple[str, int], DistInfo]):
        self._cdf = cdfs
        self.meta = meta

    @classmethod
    def from_frames(cls, wide: pd.DataFrame, meta: pd.DataFrame) -> "ScoreDistributions":
        """wide: combo, year, g0..g600 (CDF on GRID); meta: combo, year, method, n, note."""
        cols = [c for c in wide.columns if c not in ("combo", "year")]
        values = wide[cols].to_numpy(float)
        cdfs = {(c, int(y)): values[i] for i, (c, y) in enumerate(zip(wide.combo, wide.year))}
        info = {(r.combo, int(r.year)): DistInfo(r.combo, int(r.year), r.method, None if pd.isna(r.n) else int(r.n), str(r.note))
                for r in meta.itertuples(index=False)}
        return cls(cdfs, info)

    def has(self, combo: str, year: int) -> bool:
        return (combo, year) in self._cdf

    def combos(self, year: int) -> list[str]:
        return sorted(c for c, y in self._cdf if y == year)

    def years(self, combo: str) -> list[int]:
        return sorted(y for c, y in self._cdf if c == combo)

    def cdf_array(self, combo: str, year: int) -> np.ndarray:
        return self._cdf[(combo, year)]

    def share_below(self, combo: str, year: int, score: float) -> float:
        """Fraction of that year's candidates in the combination scoring strictly below `score`."""
        f = self._cdf[(combo, year)]
        return float(np.interp(score - 1e-6, GRID, f, left=0.0, right=1.0))

    def score_at(self, combo: str, year: int, share_below: float) -> float:
        return float(quantile(self._cdf[(combo, year)], share_below))

    def method(self, combo: str, year: int) -> str:
        info = self.meta.get((combo, year))
        return info.method if info else "missing"


def to_z(p: float | np.ndarray) -> np.ndarray:
    return norm.ppf(np.clip(p, 5e-4, 1 - 5e-4))


def default_distributions() -> ScoreDistributions:
    from uniadvisor.db import get_db

    return get_db().distributions
