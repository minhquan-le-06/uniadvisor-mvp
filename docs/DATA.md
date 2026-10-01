# Data: the database and how it is made

Everything the app, API, engine and SLM read is one **database**: a folder of CSV tables, the score
distributions in `distributions.parquet`, and `manifest.json`. The real one is `data/db/`. Simulated ones live
in `data/sim/<name>/` with the same schema. `uniadvisor.db` loads and checks them; `src/uniadvisor/db/schema.py`
is the schema the loader enforces, and this page explains it.

```
data/manual/ data/unipilot/ data/collected/   inputs (hand-entered, UniPilotData export, parsed per source)
        |  uniadvisor build
        v
artifacts/build/                              intermediates and checks: cutoff consensus over every source and
        |                                     scale, distributions, exclusions, validation problems
        v
data/db/                                      the real database (committed; the deployed app reads only this)
data/sim/<name>/                              simulated databases (git-ignored; rebuilt from their seed)
```

## Using it

```python
from uniadvisor.db import get_db, load
db = get_db()                      # data/db/, or the folder in UNIADVISOR_DB
db.catalog                         # one row per program: school, city, latest cutoff + status, quota, fee
db.history["BKA:IT1"]              # {year: cutoff}
db.combos["A00"]                   # ["TO", "LI", "HO"]
db.distributions                   # engine.dist.ScoreDistributions
db["cutoffs"]                      # any table as a DataFrame
```

`advise(profile, db=...)`, `backtest.run(db=...)` and the rules take a database explicitly; without one they use
`get_db()`. Tests use the tiny simulated world (`tests/conftest.py`: `tiny_db`, `use_tiny`).

```bash
uniadvisor check-db                    # check data/db/ against the schema, print counts and provenance
uniadvisor sim tiny                    # data/sim/tiny/: 3 schools, 12 programs
UNIADVISOR_DB=data/sim/tiny uniadvisor app    # the app on it (the sidebar warns the data is simulated)
uniadvisor sim season --seed 3 [--reform]     # the real database plus a simulated 2027 season
```

## Provenance: telling real and simulated data apart

Every fact (cutoff, quota, fee, distribution) has a `provenance`:

| Class | Meaning | Examples | Shown to students | Backtest, gold set | Training, tests |
|---|---|---|---|---|---|
| observed | published by a source (`source`, `url`) | cutoffs, 2026 quotas, fees from VnExpress | yes | yes | yes |
| derived | a fixed rule applied to observed values | exact distributions from per-candidate scores | yes | yes | yes |
| estimated | a model fills a missing real value; its error is measured | school-median fees, synthesized distributions | yes, as "ước tính" | no | yes |
| simulated | made up from scratch to train or test | everything `uniadvisor.sim` generates | never | never | yes |

A missing fact has **no row** (no fee row = tuition unknown), so "missing" is never a provenance; the catalog
view reports it as `tuition_provenance = missing`.

The loader enforces the boundary:
- `manifest.json` says `kind: real` or `kind: simulated`. A simulated one names its generator and seed.
- A real database may not contain `simulated` rows or `SIM-` ids. In a simulated one every `school_code` and
  `program_id` starts with `SIM-`, so it can never be joined to a real row by accident.
- Steps that must use real data refuse a simulated database: saving backtest parameters, the data report,
  building the SLM dataset, and simulating a season (it starts from real cutoffs).

## Tables

| Table | Key | One row is | Notes |
|---|---|---|---|
| `schools` | school_code | a university in scope | city: Hà Nội or TP. Hồ Chí Minh |
| `programs` | program_id | a program admitting by THPT exam score, 30-point scale | `<school_code>:<program code>`; `combos` is a `;` list; `reference_combo` places the cutoff in a distribution |
| `cutoffs` | program_id, year, combo | an admission cutoff | `combo` empty = the program's single cutoff (all rows today); `status`: confirmed_2_sources, disputed, single_source; `lowest_of_several`: the source listed several cutoffs and the lowest was kept |
| `quotas` | program_id, year | an admission quota (chỉ tiêu) | 2026 only today |
| `tuition` | program_id, year | a fee per academic year in VND | `method` says how an estimate was made (`school_median`) |
| `combos` | combo | an exam-only subject combination | three subjects, all weights 1 |
| `distributions` | combo, year | a score distribution's metadata | `method`: exact, observed, synthesized, anchored, year_shift, simulated (engine/dist.py); the CDF itself is the matching row of `distributions.parquet` (columns g0..g600: P(total ≤ 0.05·i)) |

Rules the loader checks on top of the columns: keys are unique, references resolve (a program's school, a
cutoff's program, a combination), every program has a cutoff and a distribution for its reference combination,
scores are within 0-30, fees satisfy 0 < min ≤ max, and every CDF runs from 0 to 1 without decreasing.

## Changing the schema

1. Add the column or table to `db/schema.py` (the loader rejects unknown columns, so data cannot drift ahead of
   the schema) and describe it in the table above.
2. Fill it in the build (`build/catalog.py`) and in `sim/tiny.py`, so tests cover it.
3. Planned additions this layout leaves room for: per-combination cutoffs (rows with `combo` set), quota and
   tuition history (more years in `quotas` / `tuition`), applicant counts (a new `applicants` table keyed like
   `quotas`).
