# Hand-off (state as of 2026-09-29)

Setup on a fresh machine (Python 3.11+, run from the project root; `.venv/Scripts/` on Windows):

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"            # add ".[slm]" only if you will run the SLM (pulls torch)
uniadvisor slm-data                # regenerates data/slm/*.jsonl (not in git, ~40 s)
python -m pytest -q                # 49 tests pass (1 skips without torch)
```

Everything the app needs is committed (`data/processed`, `data/collected`, `data/unipilot`,
`models/forecast_params.json`). Re-collecting from the news sites is not needed. The trained SLM
(`models/slm/`) lives only on the owner's machine: `adapter.pt` is git-ignored.

## Done

- Build is reproducible across platforms (stable sorts with explicit tie-breaks). Backtest MAE 1.373.
- Streamlit app driven end to end in headless Chromium: no exceptions. Bucket metric now includes "Khó đỗ".
- Kaggle notebook finds the bundle whether Kaggle unzipped it or not; `requires-python` is >=3.11.
- First Kaggle run (3 epochs) trained and evaluated. On the test split (first 3,000 rows): SLM 0.782,
  keywords 0.815, **hybrid 0.889**. Per-question table in README.md → "SLM".
- `HybridJudge` (slm/infer.py) routes location_ok, risk_tolerance, budget_ok to the SLM and the rest to
  the keyword rules; it is what the app and API use whenever `models/slm/` loads.
  `uniadvisor slm-eval --judge hybrid|slm|heuristic|auto`.

- 2026 rules verified by the owner (`verified: true`). Fixed: 'unlikely' programs were recommended;
  API accepted scores outside 0-10; SLM training texts said 'Nơi học: nan' for ~90% of rows (the app
  showed the city), so the next retrain trains on the same text the app sends.

## Next, in order of value

1. **Human gold labels** (the real test; every number so far is agreement with synthetic labels).
   `uniadvisor slm-data`, then `uniadvisor label` (294 rows, 42 per question; saves to
   `data/slm/gold_labeled.csv` after every click). Then `uniadvisor slm-eval --judge hybrid --gold
   data/slm/gold_labeled.csv` and the same with `--judge heuristic`. Re-pick the routing if a question flips.
2. **Per-candidate score files for 2023-2025** in `data/inbox/`, then `uniadvisor build` and
   `uniadvisor backtest`. Switches on percentile equating; biggest forecast upgrade.
3. **interest_fit** is the weakest question (0.65 with the rules, 0.46 with the SLM; the SLM is right
   94% of the time when confident but is rarely confident). Try a Kaggle retrain with `--epochs 5`, or
   LLM-teacher labels (`uniadvisor slm-relabel`), and re-evaluate.
4. Deployment, if wanted: the app needs `models/slm/adapter.pt` + `config.json` (~7 MB) and Hugging Face
   access for the base model; without them it falls back to the keyword judge.
5. Other data upgrades: quota history, real tuition from the đề án. See reports/data_report.md.
