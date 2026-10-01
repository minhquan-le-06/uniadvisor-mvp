"""Where things live. Override the repo folder with UNIADVISOR_ROOT and the UniPilotData export folder with UNIPILOT_OUT."""

from __future__ import annotations

import os
from pathlib import Path


def _root() -> Path:
    """The repo folder: UNIADVISOR_ROOT if set, else the source checkout, else the current folder (a
    non-editable install puts this file in site-packages, away from config/ and data/)."""
    if os.environ.get("UNIADVISOR_ROOT"):
        return Path(os.environ["UNIADVISOR_ROOT"]).resolve()
    here = Path(__file__).resolve().parents[2]
    return here if (here / "config").is_dir() else Path.cwd().resolve()


ROOT = _root()
CONFIG = ROOT / "config"
RULES = CONFIG / "rules"
DATA = ROOT / "data"
RAW = DATA / "raw"  # HTTP cache, one file per request (not in git)
INBOX = DATA / "inbox"  # files a person drops in by hand (e.g. per-candidate score CSVs from Kaggle)
MANUAL = DATA / "manual"  # hand-entered facts with a cited source
COLLECTED = DATA / "collected"  # parsed rows straight from each source, before cleaning
DB = DATA / "db"  # the real database the app reads (schema: db/schema.py, docs/DATA.md)
SIM = DATA / "sim"  # simulated databases, one folder each, same schema (never read by the app by default)
SLM_DATA = DATA / "slm"
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
