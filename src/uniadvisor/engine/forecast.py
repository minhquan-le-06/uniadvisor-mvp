"""Baseline cutoff forecast and admission probability.

For a program with reference combination c and target year T (D = latest year with a distribution
of c, used as the target year's scale until T's own distribution is published):

  1. Put every past cutoff s_y on D's scale by *percentile equating*
         s_y->D = F_D^-1( F_y(s_y) )          when both F_y and F_D are trustworthy (exact/observed)
         s_y->D = s_y                          otherwise (scores assumed comparable)
     Whether to equate at all is chosen by the backtest (ForecastParams.equate). Equating through
     approximated distributions (anchored / year_shift) was worse than not equating, and so was
     equating through the exact 2023-2026 per-candidate distributions (data/inbox/): cutoffs of
     selective programs stay sticky in points and low ones sit on the ministry floors.
  2. s* = sum_y w_y s_y->D / sum_y w_y,  w_y = recency^(T-1-y)      (+ quota adjustment when known)
  3. Uncertainty: Student-t with scale sigma(n history years) fitted on backtest residuals.
  4. P(admit | student total t) = P(t >= next cutoff) = T_nu((t - s*) / sqrt(sigma^2 + sd_student^2))

Because a program's cutoff is shared by all its combinations and F_D is monotone, comparing the
student's percentile F_D(t) with the forecast cutoff percentile F_D(s*) is the same comparison as
t vs s*; the percentile view (top X% of candidates) is reported for explanations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import t as student_t

from uniadvisor.engine.dist import ScoreDistributions
from uniadvisor.paths import MODELS

TRUSTED = {"exact", "observed"}


@dataclass
class ForecastParams:
    recency: float = 0.2
    kappa_quota: float = 0.0                 # points per log quota ratio (0 until quota history exists)
    sigma_by_history: dict[int, float] = field(default_factory=lambda: {1: 1.5, 2: 1.4, 3: 1.3})
    df: float = 4.0                          # Student-t degrees of freedom (heavy tails seen in backtest)
    bias: float = 0.0                        # added to s*; kept 0 (the year-to-year bias changes sign)
    sigma_floor: float = 0.5
    equate: str = "trusted"                  # trusted | never (chosen by the backtest) | always (ablation only)

    def sigma(self, n_years: int) -> float:
        k = max(1, min(n_years, max(self.sigma_by_history)))
        return max(self.sigma_by_history.get(k, max(self.sigma_by_history.values())), self.sigma_floor)

    def save(self, path=None) -> None:  # noqa: ANN001
        path = path or MODELS / "forecast_params.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path=None) -> "ForecastParams":  # noqa: ANN001
        path = path or MODELS / "forecast_params.json"
        if not path.exists():
            return cls()
        d = json.loads(path.read_text(encoding="utf-8"))
        d["sigma_by_history"] = {int(k): v for k, v in d["sigma_by_history"].items()}
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Forecast:
    program_id: str
    target_year: int
    ref_combo: str
    score: float              # forecast cutoff (30-point scale, on dist_year's scale)
    sigma: float
    df: float
    n_years: int
    years: list[int]
    past_scores: list[float]
    equated: list[bool]       # whether each past year was percentile-equated
    dist_year: int
    top_share: float          # share of dist_year candidates in ref_combo at or above the forecast cutoff

    def interval(self, level: float = 0.8) -> tuple[float, float]:
        q = student_t.ppf(0.5 + level / 2, self.df) * self.sigma
        return round(self.score - q, 2), round(self.score + q, 2)


def forecast_program(program_id: str, ref_combo: str, history: dict[int, float], target_year: int,
                     dists: ScoreDistributions, params: ForecastParams,
                     quotas: dict[int, float] | None = None, dist_year: int | None = None) -> Forecast | None:
    """history: {year: cutoff score (30-point)}; only years < target_year are used."""
    years = sorted(y for y in history if y < target_year)
    if not years:
        return None
    if dist_year is None:
        avail = [y for y in dists.years(ref_combo) if y <= target_year]
        dist_year = max(avail) if avail else max(years)
    target_ok = dists.provenance(ref_combo, dist_year) in TRUSTED
    adj, eq = [], []
    for y in years:
        s = history[y]
        trusted_pair = target_ok and dists.provenance(ref_combo, y) in TRUSTED
        do = params.equate == "always" or (params.equate == "trusted" and trusted_pair)
        if y != dist_year and do and dists.has(ref_combo, y) and dists.has(ref_combo, dist_year):
            adj.append(dists.score_at(ref_combo, dist_year, dists.share_below(ref_combo, y, s)))
            eq.append(True)
        else:
            adj.append(s)
            eq.append(False)
    w = np.array([params.recency ** (target_year - 1 - y) for y in years], float)
    if params.recency == 0:
        w = np.array([1.0 if y == years[-1] else 0.0 for y in years])
    score = float(np.dot(w, adj) / w.sum()) + params.bias
    if quotas and params.kappa_quota and quotas.get(target_year) and quotas.get(target_year - 1):
        score -= params.kappa_quota * float(np.log(quotas[target_year] / quotas[target_year - 1]))
    score = float(np.clip(score, 0, 30))
    top = 1 - dists.share_below(ref_combo, dist_year, score) if dists.has(ref_combo, dist_year) else float("nan")
    return Forecast(program_id, target_year, ref_combo, round(score, 2), params.sigma(len(years)), params.df, len(years),
                    years, [float(history[y]) for y in years], eq, dist_year, float(top))


def admit_probability(fc: Forecast, student_total: float, student_sd: float = 0.0) -> float:
    """P(student total >= next cutoff). student_sd > 0 when the total is an estimate (mock exams)."""
    scale = float(np.sqrt(fc.sigma ** 2 + student_sd ** 2))
    return float(student_t.cdf((student_total - fc.score) / scale, fc.df))
