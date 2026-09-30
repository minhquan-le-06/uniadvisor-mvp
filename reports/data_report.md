# Data report (generated 2026-09-30)

MVP scope: THPT exam-score method, universities in Hà Nội and TP.HCM, cutoff history 2023-2026, advice for 2027.

## Sources

| Source | Trust | What | Rows collected |
|---|---|---|---|
| VietNamNet cutoff API | 3 (major news) | cutoffs 2023-2026, all methods mixed, method in a free-text note | 9555 |
| VnExpress tra cứu đại học | 3 (major news) | cutoffs 2025-2026 with a THPT column, tuition | 4438 |
| VnExpress phổ điểm 2026 | 3 | per-subject (0.25 bins) and 13 per-combination (1-point bins) score histograms | 2026 only |
| Ministry figures quoted in news (data/manual/distribution_anchors.csv) | 5 (hand-entered, quoted) | 2025 p50/p75/p90 for 7 combinations; 2023-2024 means | 28 |
| UniPilotData step-1 export | 4 (aggregator) | school details, 2026 programs, quotas, THPT combinations | 1666 programs matched |
| Per-candidate score files in data/inbox/ (not in git; e.g. github.com/sdgedfegw/du-lieu-diem-thi) | 4 (public Ministry results, compiled) | exact score distributions per combination | 2023, 2024, 2025, 2026 (up to 908,866 candidates per combination) |

## Cutoffs (30-point THPT method)

| year | confirmed_2_sources | disputed | single_source |
|---|---|---|---|
| 2023 | 0 | 0 | 1506 |
| 2024 | 0 | 0 | 1553 |
| 2025 | 619 | 44 | 1132 |
| 2026 | 1425 | 85 | 233 |

`confirmed_2_sources` = both news sources agree within 0.05; `disputed` = they differ (VnExpress kept, flagged in the app); `single_source` = only one source has it (2023-2024 always, VnExpress has no older years).

Excluded as not comparable: 324 rows on a 40-point scale (doubled subject) and 480 rows on 100/150-point combined scales.

Validation problems: jump_over_3: 375, not_30_point_scale: 804, sources_disagree: 155 (see data/processed/check_problems.csv).

## Scope

48 schools (Hà Nội: 28, TP. Hồ Chí Minh: 20), 1666 programs.

Programs by years of cutoff history: 1 năm: 447, 2 năm: 272, 3 năm: 170, 4 năm: 777.

Tuition known from a source for 756 programs (45%); 182 use their school's median (marked 'ước tính' in the app); 728 unknown.

Schools dropped: DTT, FBU, IUH, KMA, KSA, PKA, QSB, QSK, QSQ, QSX, SPS, TMU. Reason: fewer than min usable 30-point THPT cutoffs in the latest year (e.g. switched to a 100-point combined scale) or not found

## Score distributions

| year | provenance | combinations |
|---|---|---|
| 2023 | exact | 79 |
| 2024 | exact | 79 |
| 2025 | exact | 133 |
| 2026 | exact | 139 |
| 2026 | synthesized | 47 |

- `observed`: real 2026 histograms. `synthesized`: 2026 combinations without a published histogram, built from the real per-subject histograms (Gaussian copula + selection correction; leave-one-out KS vs observed ≈ 0.162). `anchored`/`year_shift`: the 2026 shape moved to match published percentiles/means (weak).
- `exact`: built from per-candidate score files (data/inbox/). The 2026 file matches VnExpress's per-subject candidate counts exactly.

## Backtest (forecast 2025 and 2026 from earlier years)

- Cutoff MAE 1.373 points (naive 'same as last year': 1.369); within ±1 point: 53%.
- Chosen: equate=never, recency=0.2. Exact per-candidate distributions for [2023, 2024, 2025] are loaded. Same-percentile equating was still worse than comparing raw cutoffs, even onto the target year's own distribution, so the engine does not equate (chosen by the grid above).
- Same-percentile equating onto the target year's own distribution: MAE 1.55 (vs raw 1.369). It helps mid-range programs but fails at both ends: selective programs stay sticky in points and low ones sit on the ministry floors.
- P(admit) calibration (cross-fitted): Brier 0.119, ECE 0.0562. By bucket (predicted → actual): safe 92% → 95%; match 63% → 74%; reach 27% → 37%; unlikely 6% → 10%.
- Predictions are slightly conservative because cutoffs dropped in the 2025 reform year.

## SLM training data

- 61336 / 12953 / 13706 examples (train/val/test), split by university ({'val': 7, 'test': 7, 'train': 34}), synthetic students × real programs × 7 typed questions.
- Labels come from the rubric teacher (5 simulated annotators → soft labels). They are only as good as the generator's phrase banks: a model trained on them must be checked on the **human gold set** (data/slm/gold_to_label.csv → gold_labeled.csv) before being trusted, and ideally retrained on LLM-teacher labels (`uniadvisor slm-relabel`).

## Known gaps (priority order)

1. **A better cutoff model.** Exact distributions did not beat 'same as last year'; the next gains need other signals (quota history, applicant counts per program, per-combination cutoffs), not better distributions.
2. **Quota history.** Only 2026 quotas are known, so the quota adjustment in the forecast is off (kappa = 0).
3. **Tuition** for ~half the programs is a school-level estimate; the đề án (UniPilotData step 6) has the real figures.
4. **Combination-specific cutoffs.** When a program sets different cutoffs per combination, the lowest is kept.
5. **Employment outcomes** are not collected; the 'job/income' priority falls back to selectivity.
6. **Human gold labels** for the SLM do not exist yet (template exported).
