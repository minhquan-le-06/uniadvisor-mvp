# data/: module 1 (dữ liệu)

Everything module 1 owns: the code that collects and builds the database, its config, its tests, and the data.
Task doc (Vietnamese): [docs/tasks/module-1-data.md](../docs/tasks/module-1-data.md). Schema: [docs/DATA.md](../docs/DATA.md).

| Folder | What | In git |
|---|---|---|
| `unidata/` | the Python package: `collect/` scrapers, `build/` cleaning and catalog, `db/` schema + loader + checks, `sim/` simulated databases, `dist.py`, `paths.py` | yes |
| `config/` | `scope.yaml` (schools, regions), `sources.yaml`, `fields.yaml` (MOET code -> app field) | yes |
| `tests/` | `python -m pytest -q data/tests` runs module 1's tests alone | yes |
| `manual/`, `unipilot/` | inputs: hand-entered facts with a source, the UniPilotData export | yes |
| `collected/` | parsed rows per source, before cleaning | yes |
| `db/` | **the database** every other module reads (`unidata.db.get_db()`) | yes |
| `sim/` | simulated databases and students (`uniadvisor sim ...`), rebuilt from their seed | yes |
| `raw/`, `inbox/` | HTTP cache; per-candidate score files (`fetch-scores`; check sizes, GitHub rejects files over 100 MB) | yes |

Yearly refresh: `uniadvisor collect` → `fetch-scores` → `build` → `check-db` → `backtest` → `report`.
`unidata` never imports `uniadvisor`; the other modules depend on this one through the schema and `get_db()`.
