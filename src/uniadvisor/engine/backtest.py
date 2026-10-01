"""Backtest the baseline forecast on past years and fit its parameters.

For each target year T (2025, 2026) and each program with a real cutoff in T and >= 1 earlier year:
forecast T from years < T only, and compare with the actual cutoff.

Compared models
  engine        percentile equating only between trusted distributions, recency-weighted (what the app uses)
  naive         'same cutoff as last year'
  ablation      percentile equating through every distribution, including approximated ones
Fitted on the residuals: recency (grid), Student-t df (MLE), scale per number of history years.
Calibration of P(admit) is cross-fitted (scale fitted on the other half of the schools): students
are placed at -4..+4 points around the forecast; outcome = total >= actual cutoff.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

from uniadvisor.db import Database, get_db, require_real
from uniadvisor.engine.dist import ScoreDistributions
from uniadvisor.engine.forecast import ForecastParams, admit_probability, forecast_program
from uniadvisor.kb.rules import load_rules
from uniadvisor.paths import REPORTS

TARGETS = (2025, 2026)


def _fold(school: str) -> int:
    return int(hashlib.md5(school.encode()).hexdigest(), 16) % 2


def _histories(db: Database) -> tuple[pd.DataFrame, dict[str, dict[int, float]]]:
    return db.catalog, db.history


def residuals(prog: pd.DataFrame, hist: dict, dists: ScoreDistributions, params: ForecastParams, pre_results: bool = True) -> pd.DataFrame:
    """pre_results: map onto T-1's distribution (the year's own distribution is not known yet)."""
    rows = []
    for p in prog.itertuples(index=False):
        h = hist.get(p.program_id, {})
        for T in TARGETS:
            if T not in h:
                continue
            dist_year = T - 1 if pre_results else T
            fc = forecast_program(p.program_id, p.reference_combo, h, T, dists, params, dist_year=dist_year)
            if fc is None:
                continue
            prev = max(y for y in h if y < T)
            rows.append(dict(program_id=p.program_id, school_code=p.school_code, target=T, n_years=fc.n_years,
                             score_actual=h[T], score_forecast=fc.score, score_naive=h[prev],
                             resid=h[T] - fc.score, any_equated=any(fc.equated), fold=_fold(p.school_code)))
    return pd.DataFrame(rows)


def fit_t(res: pd.DataFrame, df: float | None = None) -> tuple[float, dict[int, float]]:
    r = res.resid.to_numpy()
    if df is None:
        df, _, _ = student_t.fit(r, floc=0.0)
        df = float(np.clip(df, 2.5, 30))
    scales = {}
    for k in (1, 2, 3):
        g = res[res.n_years >= 3] if k == 3 else res[res.n_years == k]
        if len(g) >= 30:
            _, _, sc = student_t.fit(g.resid.to_numpy(), fdf=df, floc=0.0)
            scales[k] = float(sc)
    for k in (1, 2, 3):
        scales.setdefault(k, scales.get(k - 1) or (max(scales.values()) if scales else 1.4))
    return df, scales


def calibration(res: pd.DataFrame, prog: pd.DataFrame, hist: dict, dists: ScoreDistributions,
                params_by_fold: dict[int, ForecastParams]) -> dict:
    buckets = load_rules()["risk_buckets"]
    ref = dict(zip(prog.program_id, prog.reference_combo))
    preds, outs = [], []
    for r in res.itertuples(index=False):
        fc = forecast_program(r.program_id, ref[r.program_id], hist[r.program_id], r.target, dists,
                              params_by_fold[1 - r.fold], dist_year=r.target - 1)
        for d in np.arange(-4, 4.01, 0.5):
            t = fc.score + d
            if 0 < t <= 30:
                preds.append(admit_probability(fc, t))
                outs.append(float(t >= r.score_actual))
    p, y = np.array(preds), np.array(outs)
    edges = np.linspace(0, 1, 11)
    table, ece = [], 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        if m.sum():
            table.append(dict(bin=f"{lo:.1f}-{hi:.1f}", n=int(m.sum()), mean_pred=round(float(p[m].mean()), 3), admit_rate=round(float(y[m].mean()), 3)))
            ece += m.sum() / len(p) * abs(p[m].mean() - y[m].mean())
    rows = []
    for name, lo, hi in (("safe", buckets["safe"], 1.01), ("match", buckets["match"], buckets["safe"]),
                         ("reach", buckets["reach"], buckets["match"]), ("unlikely", 0.0, buckets["reach"])):
        m = (p >= lo) & (p < hi)
        if m.sum():
            rows.append(dict(bucket=name, n=int(m.sum()), mean_pred=round(float(p[m].mean()), 3), admit_rate=round(float(y[m].mean()), 3)))
    return {"n": int(len(p)), "brier": round(float(np.mean((p - y) ** 2)), 4), "ece": round(float(ece), 4), "reliability": table, "buckets": rows}


def errors(frame: pd.DataFrame) -> dict:
    e, n = frame.score_actual - frame.score_forecast, frame.score_actual - frame.score_naive
    return {"n": int(len(frame)), "mae": round(float(e.abs().mean()), 3), "bias": round(float(e.mean()), 3),
            "within_1pt": round(float((e.abs() <= 1).mean()), 3), "naive_mae": round(float(n.abs().mean()), 3),
            "naive_within_1pt": round(float((n.abs() <= 1).mean()), 3)}


def run(save: bool = True, db: Database | None = None) -> dict:
    """save: write the fitted parameters and reports (real database only; a simulated one can be backtested
    with save=False, e.g. to check the engine against a known truth)."""
    db = db or get_db()
    if save:
        require_real(db, "saving forecast parameters and backtest reports")
    dists = db.distributions
    prog, hist = _histories(db)

    # equating is a choice the data has to earn: with exact 2023-2026 distributions, same-percentile
    # equating was still worse than raw scores (selective programs stay sticky in points, low ones sit on floors)
    grid = {(eq, rec): float(residuals(prog, hist, dists, ForecastParams(recency=rec, equate=eq)).resid.abs().mean())
            for eq in ("never", "trusted") for rec in (0.0, 0.2, 0.35, 0.5, 0.7, 1.0)}
    # keep some history when it costs < 1% MAE: damps one-year spikes at no real accuracy cost;
    # prefer not equating unless it wins by more than that margin
    ok = [k for k, v in grid.items() if v <= 1.01 * min(grid.values())]
    eq = "never" if any(e == "never" for e, _ in ok) else "trusted"
    best = max(r for e, r in ok if e == eq)
    base = ForecastParams(recency=best, equate=eq)
    res = residuals(prog, hist, dists, base)
    df, scales = fit_t(res)
    final = replace(base, df=df, sigma_by_history=scales)
    params_by_fold = {}
    for f in (0, 1):
        _, sc = fit_t(res[res.fold == f], df)
        params_by_fold[f] = replace(final, sigma_by_history=sc)
    calib = calibration(res, prog, hist, dists, params_by_fold)
    ablation = residuals(prog, hist, dists, replace(final, equate="always"))
    # equating onto the target year's own distribution (known before cutoffs, since exam results come first)
    own_year = residuals(prog, hist, dists, replace(final, equate="trusted"), pre_results=False)
    exact_past = sorted({y for (_, y), info in dists.meta.items() if info.method == "exact" and y < max(TARGETS)})

    report = {
        "grid_mae": {f"{e}/recency={r}": round(v, 4) for (e, r), v in grid.items()},
        "chosen": asdict(final),
        "engine_pre_results": {"all": errors(res), **{f"target_{T}": errors(res[res.target == T]) for T in TARGETS},
                               **{f"history_{k}y": errors(res[res.n_years == k]) for k in sorted(res.n_years.unique())},
                               "rows_with_percentile_equating": int(res.any_equated.sum())},
        "ablation_equate_always": {"all": errors(ablation), **{f"target_{T}": errors(ablation[ablation.target == T]) for T in TARGETS}},
        "ablation_equate_onto_target_year": {"all": errors(own_year), **{f"target_{T}": errors(own_year[own_year.target == T]) for T in TARGETS}},
        "calibration_cross_fitted": calib,
        "exact_past_years": exact_past,
        "note": (f"Exact per-candidate distributions for {exact_past} are loaded. Same-percentile equating was still worse "
                 "than comparing raw cutoffs, even onto the target year's own distribution, so the engine does not equate "
                 "(chosen by the grid above)." if exact_past else
                 "Only approximated distributions exist for past years; equating through them hurts, so the engine compares "
                 "raw cutoffs. Add per-candidate score files to data/inbox/ and rebuild to test equating on real data."),
    }
    if save:
        final.save()
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "backtest.json").write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
        res.to_csv(REPORTS / "backtest_residuals.csv", index=False)
    return report
