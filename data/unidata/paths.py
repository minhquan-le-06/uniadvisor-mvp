"""Where things live. Override the repo folder with UNIADVISOR_ROOT and the UniPilotData export folder with UNIPILOT_OUT."""

from __future__ import annotations

import os
from pathlib import Path


def _root() -> Path:
    """The repo folder: UNIADVISOR_ROOT if set, else the source checkout (data/unidata/paths.py), else the current
    folder (a non-editable install puts this file in site-packages, away from data/ and backend/)."""
    if os.environ.get("UNIADVISOR_ROOT"):
        return Path(os.environ["UNIADVISOR_ROOT"]).resolve()
    here = Path(__file__).resolve().parents[2]
    return here if (here / "pyproject.toml").is_file() and (here / "backend").is_dir() else Path.cwd().resolve()


ROOT = _root()

# module 1 (data/): code in data/unidata/, its config, and the data it collects and builds
DATA = ROOT / "data"
DATA_CONFIG = DATA / "config"  # scope.yaml, sources.yaml, fields.yaml
RAW = DATA / "raw"  # HTTP cache, one file per request
INBOX = DATA / "inbox"  # files a person drops in by hand (e.g. per-candidate score CSVs from Kaggle)
MANUAL = DATA / "manual"  # hand-entered facts with a cited source
COLLECTED = DATA / "collected"  # parsed rows straight from each source, before cleaning
DB = DATA / "db"  # the real database the app reads (schema: db/schema.py, docs/DATA.md)
SIM = DATA / "sim"  # simulated databases, one folder each, same schema (never read by the app by default)
# modules 2-4 (backend/): code in backend/uniadvisor/, config, and the SLM's data
BACKEND = ROOT / "backend"
BACKEND_CONFIG = BACKEND / "config"  # interests.yaml (module 2), rules/<year>.yaml (module 3)
RULES = BACKEND_CONFIG / "rules"
SLM_DATA = BACKEND / "slm_data"  # rubrics, gold sets, generated training splits (module 2)
SUGGEST_CONFIG = BACKEND_CONFIG / "suggest"  # group suggester: group -> O*NET occupations, O*NET files (module 2)
SUGGEST_DATA = BACKEND / "suggest_data"  # group suggester: frozen generated train / test sets (module 2)

# shared run outputs
ARTIFACTS = ROOT / "artifacts"  # everything a pipeline run produces
MODELS = ARTIFACTS / "models"  # fitted forecast parameters, trained SLM (models/slm/)
REPORTS = ARTIFACTS / "reports"  # data report, backtest, SLM evaluations
BUILD = ARTIFACTS / "build"  # build intermediates and checks: all-source cutoff consensus, exclusions, problems

# Copy of the UniPilotData step-1 export the build reads (school, program, combos). Point UNIPILOT_OUT
# at a fresh `unipilot export --to out` folder to refresh it.
UNIPILOT_OUT = Path(os.environ.get("UNIPILOT_OUT", DATA / "unipilot"))


def ensure_dirs() -> None:
    for p in (RAW, INBOX, MANUAL, COLLECTED, DB, SLM_DATA, MODELS, REPORTS, BUILD):
        p.mkdir(parents=True, exist_ok=True)
