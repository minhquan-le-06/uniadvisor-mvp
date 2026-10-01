# backend/: modules 2, 3, 4

The advisor itself, reading the database module 1 builds (`unidata.db.get_db()`). One subpackage per module; task
docs (Vietnamese) in [docs/tasks/](../docs/tasks/).

| Path | Module | What |
|---|---|---|
| `uniadvisor/student/` | 2, understanding the student | `slm/` typed questions, keyword judge, SLM model, training data, evaluation; `intent/` fact reader; `simulated.py` simulated students + an always-right judge |
| `uniadvisor/recommend/` | 3, recommendation | `rules.py` admission rules, `forecast.py` + `backtest.py`, `compare.py` criteria, `optimizer.py`, `advisor.py` (`advise()`, runs the whole pipeline) |
| `uniadvisor/explain/` | 4, explanation | Vietnamese explanations built from module 3's numbers |
| `uniadvisor/api.py`, `cli.py` | all | FastAPI and the `uniadvisor` command |
| `config/` | 2, 3 | `interests.yaml` (student words -> MOET codes), `rules/<year>.yaml` (admission rules per year) |
| `slm_data/` | 2 | rubrics, gold sets; generated splits (`uniadvisor slm-data`) are not in git |
| `tests/` | 2, 3, 4 | `python -m pytest -q backend/tests`; runs on the tiny simulated database where it can |

The Streamlit app is in `app/` (its path is what the deployed app points at).
