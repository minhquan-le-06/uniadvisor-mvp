"""Build per-(combination, year) score distributions -> artifacts/build/distributions.parquet.

Order of preference per (combo, year): exact (inbox) > observed > synthesized > anchored > year_shift.
See engine/dist.py for what each method means. Writes artifacts/build/distributions.parquet + .csv;
the catalog step copies them into the database.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

from uniadvisor.build.unipilot import FOREIGN_LANGS, exam_combos
from uniadvisor.engine.dist import (
    GRID,
    cdf_from_bins,
    cdf_from_samples,
    fit_affine,
    ks,
    mean_of,
    quantile,
    subject_quantile_fn,
    synthesize,
    transform,
)
from uniadvisor.paths import BUILD, COLLECTED, INBOX, MANUAL, REPORTS, ensure_dirs
from uniadvisor.text import fold

log = logging.getLogger(__name__)
LATEST = 2026
SUBJECT_ALIASES = {"KTPL": "GDKTPL"}

# column names seen in public per-candidate score files -> subject codes
INBOX_COLUMNS = {
    "toan": "TO", "ngu van": "VA", "van": "VA", "ngoai ngu": "N1", "tieng anh": "N1",
    "vat li": "LI", "vat ly": "LI", "li": "LI", "ly": "LI", "hoa hoc": "HO", "hoa": "HO",
    "sinh hoc": "SI", "sinh": "SI", "lich su": "SU", "su": "SU", "dia li": "DI", "dia ly": "DI", "dia": "DI",
    "gdcd": "GD", "tin hoc": "TI", "tin": "TI", "gdktpl": "GDKTPL", "giao duc kinh te va phap luat": "GDKTPL",
    "kinh te phap luat": "GDKTPL", "cong nghe cong nghiep": "CNCN", "cong nghe nong nghiep": "CNNN",
}


POOLED_LANGUAGE_COPIES = {"D03", "D04"}


def _core_count(subjects: list[str]) -> int:
    """How many compulsory subjects (Toán, Ngữ văn) the combo has: 1 or 2."""
    return sum(s in ("TO", "VA") for s in subjects)


def _subject_for(subject: str) -> str:
    """Other foreign languages use the pooled 'Ngoại ngữ' histogram (VnExpress does not split them)."""
    return "N1" if subject in FOREIGN_LANGS else subject


def _inbox_key(column: str) -> str:
    """'NguVan', 'ngu_van', 'Ngữ văn' -> 'nguvan' (headers differ in case, spacing and diacritics)."""
    return re.sub(r"[^a-z0-9]", "", fold(str(column)))


_INBOX_KEYS = {_inbox_key(k): v for k, v in INBOX_COLUMNS.items()}


def load_inbox_scores() -> dict[int, pd.DataFrame]:
    """data/inbox/*<year>*.csv with one row per candidate -> {year: frame of subject columns}.
    Several files for one year are concatenated. Files named '*ct2006*' are skipped: in 2025 they hold the
    candidates who re-sat the old-curriculum exam, a different test that would distort that year."""
    frames: dict[int, list[pd.DataFrame]] = {}
    for path in sorted(Path(INBOX).glob("*.csv")):
        m = re.search(r"(20\d\d)", path.name)
        if not m:
            continue
        if "ct2006" in path.name.lower():
            log.info("inbox scores %s: skipped (old-curriculum exam)", path.name)
            continue
        df = pd.read_csv(path, low_memory=False, encoding="utf-8-sig")
        rename = {c: _INBOX_KEYS[_inbox_key(c)] for c in df.columns if _inbox_key(c) in _INBOX_KEYS}
        if len(set(rename.values())) < 3:
            log.warning("inbox scores %s: fewer than 3 known subject columns, skipped (columns: %s)", path.name, list(df.columns)[:12])
            continue
        df = df[list(rename)].rename(columns=rename).apply(pd.to_numeric, errors="coerce")
        frames.setdefault(int(m.group(1)), []).append(df)
        log.info("inbox scores %s: %d candidates, subjects %s", path.name, len(df), sorted(df.columns))
    return {year: pd.concat(fs, ignore_index=True) for year, fs in frames.items()}


def build(rho_grid: np.ndarray | None = None) -> dict:
    ensure_dirs()
    combos = exam_combos()
    years = [2023, 2024, 2025, LATEST]
    cdfs: dict[tuple[str, int], np.ndarray] = {}
    meta: list[dict] = []
    report: dict = {}

    # --- latest year: observed combos. VnExpress pools every foreign language, so D03 (French) and
    # D04 (Chinese) come back identical to D01: those two are not real observations and are skipped.
    ch = pd.read_csv(COLLECTED / "vnexpress_combo_hist.csv")
    ch = ch[~ch.combo.isin(POOLED_LANGUAGE_COPIES)]
    observed = {}
    for combo, g in ch[ch.year == LATEST].groupby("combo"):
        observed[combo] = cdf_from_bins(g.bin_low.to_numpy(), g["count"].to_numpy())
        n = int(g["count"].sum())
        cdfs[(combo, LATEST)] = observed[combo]
        meta.append(dict(combo=combo, year=LATEST, method="observed", n=n,
                         note=f"VnExpress phổ điểm {LATEST}, 1-point bins, {n} candidates"))

    # --- latest year: per-subject marginals and copula fit
    sh = pd.read_csv(COLLECTED / "vnexpress_subject_hist.csv")
    sh["subject"] = sh["subject"].replace(SUBJECT_ALIASES)
    sh = sh[sh.year == LATEST]
    subject_q = {s: subject_quantile_fn(g.score.to_numpy(), g["count"].to_numpy()) for s, g in sh.groupby("subject") if g["count"].sum() > 1000}

    def can_synth(subjects: list[str]) -> bool:
        return all(_subject_for(s) in subject_q for s in subjects)

    # Candidates self-select into electives (A00 takers are stronger at maths than all maths takers),
    # so a copula on whole-population subject histograms is biased. We correct it with an affine map
    # a + b*X fitted on the observed combos of the same class (1 or 2 compulsory subjects) and report
    # the leave-one-out error honestly. The engine prefers observed combos as a program's reference,
    # so synthesized ones are only a fallback.
    def synth(subjects: list[str], n: int = 200_000) -> np.ndarray:
        return synthesize(subject_q, [_subject_for(s) for s in subjects], rho, n=n)

    rho = 0.5  # KS is flat in rho (0.3-0.8) once the affine correction is applied; see report
    ps = np.linspace(0.05, 0.95, 19)
    fit_set = [c for c in observed if c in combos and can_synth(combos[c])]
    raw = {c: synth(combos[c], 80_000) for c in fit_set}
    affine = {}
    for c in fit_set:
        b, a = np.polyfit(quantile(raw[c], ps), quantile(observed[c], ps), 1)
        affine[c] = (float(a), float(b), _core_count(combos[c]))
    loo = {}
    for c in fit_set:
        same = [(a, b) for k, (a, b, cls) in affine.items() if k != c and cls == affine[c][2]]
        a, b = np.mean([x[0] for x in same]), np.mean([x[1] for x in same])
        loo[c] = round(ks(transform(raw[c], a, b), observed[c]), 3)
    class_fit = {}
    for cls in {v[2] for v in affine.values()}:
        vals = [(a, b) for a, b, k in affine.values() if k == cls]
        class_fit[cls] = (float(np.mean([v[0] for v in vals])), float(np.mean([v[1] for v in vals])))
    report["copula"] = {
        "rho": rho,
        "raw_ks_vs_observed": {c: round(ks(raw[c], observed[c]), 3) for c in fit_set},
        "affine_per_observed_combo": {c: [round(a, 2), round(b, 3), cls] for c, (a, b, cls) in affine.items()},
        "class_correction": {str(k): [round(a, 2), round(b, 3)] for k, (a, b) in class_fit.items()},
        "leave_one_out_ks": loo,
        "leave_one_out_ks_mean": round(float(np.mean(list(loo.values()))), 3),
    }
    log.info("synthesized combos: leave-one-out KS mean %.3f", report["copula"]["leave_one_out_ks_mean"])

    for combo, subjects in combos.items():
        if (combo, LATEST) in cdfs or not can_synth(subjects):
            continue
        a, b = class_fit.get(_core_count(subjects), (0.0, 1.0))
        cdfs[(combo, LATEST)] = transform(synth(subjects), a, b)
        meta.append(dict(combo=combo, year=LATEST, method="synthesized", n=None,
                         note=f"copula on {LATEST} subject histograms (rho={rho}) + class correction a={a:.2f} b={b:.3f}; "
                              f"leave-one-out KS on observed combos ~{report['copula']['leave_one_out_ks_mean']}"))

    # --- exact distributions from per-candidate files (any year, overrides everything)
    for year, df in load_inbox_scores().items():
        for combo, subjects in combos.items():
            cols = [_subject_for(s) for s in subjects]
            if not all(c in df.columns for c in cols):
                continue
            totals = df[cols].dropna()
            if len(totals) < 2000:
                continue
            cdfs[(combo, year)] = cdf_from_samples(totals.sum(axis=1).to_numpy())
            meta = [m for m in meta if not (m["combo"] == combo and m["year"] == year)]
            meta.append(dict(combo=combo, year=year, method="exact", n=len(totals), note="per-candidate file in data/inbox"))

    # --- earlier years: anchored to published stats, else shifted like the anchored ones
    anchors = pd.read_csv(MANUAL / "distribution_anchors.csv")
    report["anchored"] = {}
    for year in [y for y in years if y != LATEST]:
        fits = {}
        for combo, g in anchors[anchors.year == year].groupby("combo"):
            if (combo, LATEST) not in cdfs or (combo, year) in cdfs:
                continue
            base = cdfs[(combo, LATEST)]
            pairs = list(zip(g.stat, g.value))
            a, b = fit_affine(base, pairs)
            fits[combo] = (a, b)
            cdfs[(combo, year)] = transform(base, a, b)
            resid = {k: round(float((quantile(cdfs[(combo, year)], float(k[1:]) / 100) if k.startswith("p") else mean_of(cdfs[(combo, year)])) - v), 3) for k, v in pairs}
            meta.append(dict(combo=combo, year=year, method="anchored", n=None,
                             note=f"{LATEST} shape, a={a:.2f} b={b:.3f} fitted to {', '.join(k for k, _ in pairs)}; residuals {resid}"))
            report["anchored"][f"{combo}-{year}"] = {"a": round(a, 3), "b": round(b, 3), "residuals": resid}
        if not fits:
            continue
        a_bar = float(np.mean([a for a, _ in fits.values()]))
        b_bar = float(np.mean([b for _, b in fits.values()]))
        for combo in combos:
            if (combo, LATEST) in cdfs and (combo, year) not in cdfs:
                cdfs[(combo, year)] = transform(cdfs[(combo, LATEST)], a_bar, b_bar)
                meta.append(dict(combo=combo, year=year, method="year_shift", n=None,
                                 note=f"{LATEST} shape moved like the anchored combos of {year} ({', '.join(sorted(fits))}): a={a_bar:.2f} b={b_bar:.3f}"))

    # --- save
    keys = sorted(cdfs)
    wide = pd.DataFrame([cdfs[k] for k in keys], columns=[f"g{i}" for i in range(len(GRID))])
    wide.insert(0, "year", [k[1] for k in keys])
    wide.insert(0, "combo", [k[0] for k in keys])
    wide.to_parquet(BUILD / "distributions.parquet", index=False)
    m = pd.DataFrame(meta)
    stats = []
    for r in m.itertuples(index=False):
        f = cdfs[(r.combo, r.year)]
        stats.append(dict(mean=round(mean_of(f), 2), p50=round(float(quantile(f, .5)), 2),
                          p75=round(float(quantile(f, .75)), 2), p90=round(float(quantile(f, .9)), 2)))
    m = pd.concat([m, pd.DataFrame(stats)], axis=1).sort_values(["combo", "year"])
    m.to_csv(BUILD / "distributions.csv", index=False, encoding="utf-8")
    report["counts"] = m.groupby(["year", "method"]).size().rename("n").reset_index().to_dict("records")
    (REPORTS / "distributions.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report
