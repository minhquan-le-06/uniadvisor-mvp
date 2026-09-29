# Hand-off (state as of 2026-09-29)

Setup on a fresh machine (Linux cloud):

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"            # add ".[slm]" only if you will run the SLM (pulls torch)
uniadvisor slm-data                # regenerates data/slm/*.jsonl (not in git, ~40 s)
python -m pytest -q                # 39 tests should pass
```

Everything the app needs is committed (`data/processed`, `data/collected`, `data/unipilot`,
`models/forecast_params.json`). Re-collecting from the news sites is not needed.

Remaining work:
1. Tiny end-to-end SLM training check so a bug does not waste a Kaggle run:
   `uniadvisor slm-train --limit 300 --eval-limit 200 --epochs 1 --bs 16 --out models/slm_smoke`
   (the earlier 2,500-example CPU run was stopped: too slow on the laptop).
2. `uniadvisor slm-eval --judge heuristic` to record the keyword baseline the SLM must beat.
3. `uniadvisor kaggle-bundle`, then train on Kaggle (kaggle/README.md); unzip result into models/slm/.
4. Visual check of the Streamlit app (`uniadvisor app`); a headless AppTest of the full flow already passed.
5. Data upgrades, in order of value: per-candidate score files for 2023-2025 in data/inbox/
   (switches on percentile equating), quota history, real tuition from the đề án, human gold labels.
   See reports/data_report.md.
