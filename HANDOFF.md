# Hand-off (state as of 2026-09-29, after the cloud verification session)

Setup on a fresh machine (Linux cloud, Python 3.11+):

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"            # add ".[slm]" only if you will run the SLM (pulls torch)
uniadvisor slm-data                # regenerates data/slm/*.jsonl (not in git, ~40 s)
python -m pytest -q                # 39 tests pass (1 skips without torch)
```

Everything the app needs is committed (`data/processed`, `data/collected`, `data/unipilot`,
`models/forecast_params.json`). Re-collecting from the news sites is not needed.

## Verified in the cloud session

- `uniadvisor build` is now reproducible across platforms (stable sorts with explicit tie-breaks);
  the committed data was rebuilt on Linux. Backtest unchanged: MAE 1.373.
- SLM training/eval/inference code path: end-to-end run with a tiny random local base model
  (Hugging Face was blocked there), including the Kaggle notebook flow from the unzipped bundle
  on Python 3.11 with `pip install -e . --no-deps`. `requires-python` lowered to >=3.11 for Kaggle.
- Keyword baseline recorded: `reports/slm_eval_heuristic_test.json` (overall accuracy 0.833).
  The trained SLM must beat this per question.
- Streamlit app driven in real headless Chromium (consent → scores form → free text → results,
  compare tab, CSV download): no app exceptions. Fixed the bucket metric, which left out "Khó đỗ".

## Remaining work

1. Train on Kaggle: `uniadvisor kaggle-bundle`, then kaggle/README.md; unzip the result into
   `models/slm/` and run `uniadvisor slm-eval --judge slm` to compare with the baseline.
2. Data upgrades, in order of value: per-candidate score files for 2023-2025 in data/inbox/
   (switches on percentile equating), quota history, real tuition from the đề án, human gold labels.
   See reports/data_report.md.
