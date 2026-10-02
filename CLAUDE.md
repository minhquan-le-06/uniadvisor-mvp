# UniAdvisor: working notes

University application advisor (nguyện vọng) for Vietnamese grade-12 students: rules (KB) + statistical engine +
a small typed-head language model (SLM) for soft judgments only. Spec: [docs/MVP.md](docs/MVP.md). Current status,
results and roadmap: [docs/HANDOFF.md](docs/HANDOFF.md). The system is 4 modules, one task doc each (Vietnamese, for the team):
[docs/tasks/](docs/tasks/) (data, student understanding, recommendation, explanation). Read [artifacts/reports/data_report.md](artifacts/reports/data_report.md)
before trusting any number.

## Commands (run from the repo root; Windows venv shown, use `.venv/bin/` elsewhere)

```bash
.venv/Scripts/python -m pip install -e ".[dev]"     # add ",slm" to run the SLM (pulls torch)
.venv/Scripts/python -m pytest -q                   # ~90 s; 141 pass (data/tests alone: module 1)
.venv/Scripts/uniadvisor slm-data                   # regenerates backend/slm_data/*.jsonl (~40 s); needed by SLM tests/eval
.venv/Scripts/uniadvisor app                        # Streamlit chat, http://localhost:8501
.venv/Scripts/uniadvisor serve                      # FastAPI, http://localhost:8000/docs
.venv/Scripts/uniadvisor advise --scores "TO=8.4,VA=7,LI=8,N1=8.2" --province "Nghệ An" --area KV2-NT --text "..."
.venv/Scripts/uniadvisor slm-eval --judge hybrid --gold backend/slm_data/gold_llm.csv   # judges: auto|hybrid|slm|heuristic
```

Data pipeline (yearly refresh): `collect` → `fetch-scores` (optional, ~350 MB into data/inbox/) → `build` →
`check-db` → `backtest` → `report` → `slm-data`. Simulated data: `sim tiny`, `sim season` (databases), `sim students`
(students with their true facts; `uniadvisor.student.simulated.OracleJudge` answers from those facts). Module 2's fact reader: `intent-eval`. Other commands:
`slm-train`, `slm-relabel`, `kaggle-bundle`, `label`, `gold-llm`. All are in `backend/uniadvisor/cli.py`.

## Layout

| Path | What | In git |
|---|---|---|
| `data/unidata/` | **module 1** package: `db/` the database (schema, loader, checks), `collect/` scrapers, `build/` cleaning + catalog + MOET codes + fields, `sim/` simulated databases, `dist.py` score distributions, `paths.py` (every path comes from here), `testing.py` shared pytest fixtures. Never imports `uniadvisor` | yes |
| `backend/uniadvisor/` | **modules 2-4** package: `student/` (module 2: `slm/` judges + model + data + eval, `intent/` fact reader, `form/` guided chat logic (answers -> student JSON, docs/STUDENT_SCHEMA.md), `suggest/` "Em chưa biết" group suggester (docs/MODEL.md, not trained yet), `simulated.py` simulated students + OracleJudge), `recommend/` (module 3: `rules.py`, `forecast.py`, `backtest.py`, `compare.py`, `optimizer.py`, `advisor.py` runs it all), `explain/` (module 4), `api.py`, `cli.py` | yes |
| `data/tests/`, `backend/tests/` | pytest suites per side; fixtures from `unidata.testing` | yes |
| `app/` | `streamlit_app.py` (the deployed app), `pages/hoi_dap.py` (module 2's guided chat, trial page; `?debug=1` shows the JSON), `label_gold.py` (gold labelling tool) | yes |
| `data/config/` | module 1: `scope.yaml`, `sources.yaml`, `fields.yaml` (MOET code -> app field) | yes |
| `backend/config/` | `interests.yaml` (module 2: student words -> MOET codes), `rules/<year>.yaml` (module 3, versioned per admission year) | yes |
| `data/manual/` → `data/collected/` → `data/db/` | hand-entered facts → parsed rows per source → **the database** the app reads ([docs/DATA.md](docs/DATA.md)) | yes |
| `data/sim/<name>/` | simulated databases and students, same schema, `SIM-` ids; rebuilt from the seed in their manifest | yes |
| `data/unipilot/` | UniPilotData step-1 export (schools, programs, combos) | yes |
| `backend/slm_data/` | rubrics, gold set (`gold_frozen.jsonl`, `gold_llm.csv`, `gold_to_label.csv`); `*.jsonl` splits are regenerated | yes |
| `data/raw/`, `data/inbox/` | HTTP cache; per-candidate score files | yes |
| `artifacts/models/` | `forecast_params.json`; `artifacts/models/slm/` = trained SLM (`config.json`, `metrics.json`, `adapter.pt`) | yes |
| `artifacts/build/` | build intermediates: cutoff consensus over all sources, distributions, exclusions, problems | yes |
| `artifacts/reports/` | data report, backtest, SLM eval results | yes |
| `docs/` | MVP spec, deploy guide, hand-off/status, team report; `docs/tasks/` = one task doc per module; `docs/kaggle/` = GPU training guide + notebook | yes |

Keep the root lean: new outputs go under `artifacts/`, new docs under `docs/`, scratch outside the repo
(old snapshots live in `../MLAI_test_archive/`). Code takes folder paths from `unidata/paths.py`. Module 1 code goes in `data/unidata/`, modules 2-4 in
`backend/uniadvisor/<module>/`.

The app uses `HybridJudge` when `artifacts/models/slm/adapter.pt` + `config.json` exist, otherwise `HeuristicJudge` (keyword
rules). The deployed app (Streamlit Community Cloud) has no adapter, so it runs the keyword judge.

## Ground rules

- Anything with a verifiable answer (eligibility, priority points, probabilities, ordering) is rules/statistics. The
  SLM never computes probabilities or regulation facts. Explanations use engine numbers only.
- Same input → same output for rules/statistics. Builds use stable sorts with explicit tie-breaks.
- Read data only through `unidata.db` (`get_db()`, or a `db=` argument). Every fact carries a provenance
  (observed / derived / estimated / simulated); simulated data never enters `data/db/`. Test with the tiny
  simulated world (`tiny_db` / `use_tiny` fixtures), not by mocking files. New columns go in `db/schema.py` first.
- UI text is Vietnamese; code, comments and docs are English.
- Nothing a student enters is stored (Decree 13/2023). Everything else is committed, data included; only `.env`, `.venv/`,
  secrets (`.streamlit/secrets.toml`, `backend/slm_data/gemini_keys.txt`) and Python caches are ignored. GitHub rejects files
  over 100 MB: check sizes before committing large downloads (e.g. `fetch-scores` files in `data/inbox/`).
- Measure every SLM or keyword-rule change on the frozen gold set and re-pick `SLM_QUESTIONS` (`slm/infer.py`)
  after each retrain. Update the README results table and docs/HANDOFF.md when numbers change.

## Gotchas

- pandas 3: `df.where(df.notna(), None)` keeps NaN in string columns; use `df.astype(object).where(...)`.
- A program's field comes from its MOET major code (data/config/fields.yaml; MOET's code is the taxonomy: digits 1-3
  lĩnh vực, 1-5 nhóm ngành, 1-7 ngành). Name keywords only fill in without a code. Rules keyed on MOET groups (floors,
  sư phạm / health conditions) use the code when there is one, never the field (field su_pham also covers 71401).
- Keyword matching (program fields, free text) is on whole words. Substring matching put "Thiết kế thời trang"
  ("rang") and "Tâm lý học" ("y học") under health.
- Gold ids hash the row text. Gold rows are frozen in `backend/slm_data/gold_frozen.jsonl` (text, latent, program), so
  regenerating synthetic data does not invalidate labels. Their students are excluded from training.
- The teacher and the dataset sampler share one RNG stream: any teacher change reshuffles later pairings.
- ADS_Final (2018-2024 cutoffs) has correct scores but sometimes wrong program names. Code reuse is detected by name
  mismatch AND a > 2.5-point jump, never by name alone (`catalog._drop_reused_codes`). Its 'Thang 40' label marks
  40-point rows even when the number is <= 30.
- The 2025 `ct2006` score file (old-curriculum exam) is skipped by the importer on purpose.
- `data/inbox/` is empty on most machines, so `build` keeps the exact distributions in `artifacts/build/` instead of
  rebuilding them from approximations; `fetch-scores` first to rebuild them.
- Percentile equating fails at the tails (selective programs stay sticky in points; low ones sit on ministry floors).
  The backtest picks equate on/off from measured MAE; it currently picks `never`.
- The SLM is poor at score arithmetic: keep ability_fit on the rules.
- Avoid shell heredoc/sed edits containing backslash escapes (they corrupted regexes before); use the Edit tool.

## Cloud sessions

- Blocked: huggingface.co, download.pytorch.org, kaggle.com, the news sites. torch installs from PyPI. Smoke-test SLM
  code paths with a tiny local random BERT (`--base <dir>`), not the real base model.
- Reachable: GitHub (anonymous clone of public repos) and media.githubusercontent.com (LFS; `fetch-scores` uses it).
- Chromium + global Playwright are installed: drive Streamlit with Node Playwright (`createRequire(npm root -g)`).
  The chat sidebar also has a "Bắt đầu lại" button, so select the primary button by `data-testid=stBaseButton-primary`.
