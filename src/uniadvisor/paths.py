"""Where things live. Override the UniPilotData export folder with UNIPILOT_OUT."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
RULES = CONFIG / "rules"
DATA = ROOT / "data"
RAW = DATA / "raw"  # HTTP cache, one file per request (not in git)
INBOX = DATA / "inbox"  # files a person drops in by hand (e.g. per-candidate score CSVs from Kaggle)
MANUAL = DATA / "manual"  # hand-entered facts with a cited source
COLLECTED = DATA / "collected"  # parsed rows straight from each source, before cleaning
PROCESSED = DATA / "processed"  # clean tables the app reads
SLM_DATA = DATA / "slm"
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"

# Copy of the UniPilotData step-1 export the build reads (school, program, combos). Point UNIPILOT_OUT
# at a fresh `unipilot export --to out` folder to refresh it.
UNIPILOT_OUT = Path(os.environ.get("UNIPILOT_OUT", DATA / "unipilot"))


def ensure_dirs() -> None:
    for p in (RAW, INBOX, MANUAL, COLLECTED, PROCESSED, SLM_DATA, MODELS, REPORTS):
        p.mkdir(parents=True, exist_ok=True)
