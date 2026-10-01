# Hand-off (state as of 2026-09-30)

All work is on branch `claude/ecstatic-pasteur-9qby7f`, open as PR
https://github.com/minhquan-le-06/uniadvisor-mvp/pull/1 (not merged yet). Read this file, then README.md
and reports/data_report.md.

## Setup (Python 3.11+, run everything from the project root; `.venv/Scripts/` on Windows)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"            # add ".[slm]" to run the SLM (pulls torch)
uniadvisor slm-data                # regenerates data/slm/*.jsonl (not in git, ~40 s)
python -m pytest -q                # 50 pass (1 skips without torch)
uniadvisor fetch-scores            # optional: per-candidate scores 2023-2026 into data/inbox/ (~350 MB,
                                   # git-ignored); needed only to rebuild the distributions exactly
```

Committed: `data/processed`, `data/collected`, `data/unipilot`, `models/forecast_params.json`. Not committed:
`data/inbox/` (per-candidate files), `data/slm/*.jsonl`, `models/slm/adapter.pt` (the trained SLM lives only
on the owner's Windows machine, in `models/slm/`).

## Current state

| Component | State |
|---|---|
| Data | 48 schools (HN 28, HCM 20), 1,666 programs, cutoffs 2018-2026 from 4 sources (2018-2022 ADS_Final only); exact score distributions 2023-2026 (1.0-1.2 M candidates/year) |
| Rules | 2026 verified by the owner (`verified: true`); 2027 is a draft inheriting 2026 |
| Forecast | MAE 1.373 ≈ naive "last year's cutoff" (1.369). Percentile equating with exact data is worse (1.55), so the backtest picks `equate=never`. P(admit) calibrated: Brier 0.119, ECE 0.056 |
| Optimizer | tested vs brute force; never recommends "unlikely" (< 15%) programs |
| SLM | Third Kaggle run (fixed teacher, 5 epochs, DDP on 2×T4, ~24 min, VRAM ~14/15 GB per GPU) is the current model (owner's `models/slm/`). On Gemini's gold labels: keywords 0.823 (after rubric fixes), SLM 0.765, hybrid ≈ 0.86 with `SLM_QUESTIONS` = location_ok, risk_tolerance, budget_ok, conditions_ok. Weakest: interest_fit (0.55). The teacher changed since (English self-assessment counts for ability_fit; 48 program fields fixed), so the next retrain trains on slightly better labels |
| App / API | Streamlit chat + FastAPI both tested (headless Chromium, TestClient); not deployed |
| Labelling | Gemini labelled all 294 gold rows (`data/slm/gold_llm.csv`); interest_fit (42) and 8 ability_fit rows need `gold-llm --redo interest_fit,ability_fit` after the rubric fixes. The gold set is frozen in `data/slm/gold_frozen.jsonl` (evaluation reads it; its students are excluded from training). 0/294 human labels |

## Next, in order of value

1. **Owner: label the gold set** (`uniadvisor slm-data`, then `uniadvisor gold-llm` with Gemini keys and/or `uniadvisor label`; guide in
   data/slm/LABELLING.md), commit `data/slm/gold_labeled.csv`, then run
   `uniadvisor slm-eval --judge hybrid|heuristic|slm --gold data/slm/gold_labeled.csv`. Re-pick `SLM_QUESTIONS`
   in slm/infer.py (or `"route"` in models/slm/config.json) if a question flips. Fix rubrics from the notes.
2. **Owner: merge PR #1.**
3. **Forecast signals beyond last year's cutoff.** Better distributions and 2018-2022 history did not help; next try quota history
   2023-2025 (turns on `kappa_quota`), applicant counts per program, per-combination cutoffs.
4. **(done 2026-10-01)** Retrain the SLM on Kaggle (kaggle/README.md). Training texts no longer say "Nơi học: nan" (fixed after
   the first run), so a retrain is worth it; try `--epochs 5` for interest_fit (weakest: 0.65 rules / 0.46 SLM).
5. Out of MVP scope (owner decision, 2026-09-30): real tuition from each school's đề án. 910 programs keep a
   school-level estimate; budget_ok judges against it or says insufficient when tuition is unknown.
6. Deployment if wanted: needs `models/slm/` (~7 MB) and Hugging Face access, else keyword fallback.

## Cloud-environment notes (for the next Claude session)

- The container's default `python3` is 3.11 and fine now; `python3.12` also exists.
- Blocked: huggingface.co, download.pytorch.org, kaggle.com, the news sites. torch installs from PyPI. SLM
  code paths can be smoke-tested with a tiny local random BERT (`--base <dir>`), not the real base model.
- Reachable: GitHub (anonymous clone of public repos) and media.githubusercontent.com (serves LFS files;
  `fetch-scores` uses it).
- Chromium + global Playwright are installed: drive Streamlit with Node Playwright
  (`createRequire(npm root -g)`); in the chat app the sidebar also has a "Bắt đầu lại" button, so select the
  primary button by `data-testid=stBaseButton-primary`.
- Avoid shell heredoc edits containing backslash escapes (caused corrupted regexes before); use the Edit tool.

## Decisions and findings worth remembering

- Build is reproducible across platforms: stable sorts with explicit tie-breaks (program dedupe prefers
  longest history, then best-confirmed row, then program_id).
- Percentile equating fails at the tails: selective programs stay sticky in points; low ones sit on the
  ministry floors. The backtest grid chooses equate on/off from measured MAE.
- ADS_Final (2018-2024 cutoffs) has correct scores but wrong program names in some years (BKA IT1 2019 named
  "Kỹ thuật xây dựng"). So code reuse is detected by name mismatch AND a > 2.5-point jump, never name alone
  (`catalog._drop_reused_codes`). Its 'Thang 40' label marks 40-point rows even when the number is <= 30.
- The 2025 `ct2006` score file (old-curriculum exam) is skipped by the importer on purpose.
- The SLM is poor at score arithmetic (ability_fit 0.47): keep that question on the rules.
- Gold ids hash the row text. The gold rows are frozen in `data/slm/gold_frozen.jsonl` (text, latent, program), so
  regenerating the synthetic data no longer invalidates labels; teacher labels for them are recomputed on the fly.
- The teacher and the dataset sampler share one RNG stream: any teacher change reshuffles later pairings.
- pandas 3: `df.where(df.notna(), None)` keeps NaN in string columns; use `df.astype(object).where(...)`.
- Keyword matching (program fields, free text) is on whole words: substring matching put "Thiết kế thời trang"
  ("rang") and "Tâm lý học" ("y học") under health.
