"""Human gold labels: load the template, merge saved labels, save after every answer.

backend/slm_data/gold_to_label.csv   template written by `uniadvisor slm-data` (never used for training)
backend/slm_data/gold_labeled.csv    what the labelling tool writes; `uniadvisor slm-eval --gold` reads it
backend/slm_data/gold_frozen.jsonl   the gold rows as labelled (text, latent student, program); evaluation uses these, so
                             regenerating the synthetic data never invalidates labels
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from unidata.paths import SLM_DATA

TEMPLATE = SLM_DATA / "gold_to_label.csv"
LABELED = SLM_DATA / "gold_labeled.csv"
COLUMNS = ["id", "question", "options", "text_a", "text_b", "human_label", "labeller", "note"]
FILLED = ["human_label", "labeller", "note"]


def load(template: Path = TEMPLATE, labeled: Path = LABELED) -> pd.DataFrame:
    """The template with any labels already saved in `labeled` filled in (matched by id)."""
    df = pd.read_csv(template, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if labeled.exists():
        done = pd.read_csv(labeled, dtype=str, keep_default_na=False, encoding="utf-8-sig").set_index("id")
        for col in FILLED:
            if col in done:
                df[col] = df.id.map(done[col]).fillna(df[col])
    return df[COLUMNS].reset_index(drop=True)


def save(df: pd.DataFrame, labeled: Path = LABELED) -> None:
    """Write all rows (labelled or not) atomically, so a crash never leaves a half-written file."""
    tmp = labeled.with_suffix(".tmp")
    df[COLUMNS].to_csv(tmp, index=False, encoding="utf-8-sig")
    os.replace(tmp, labeled)


def progress(df: pd.DataFrame) -> pd.DataFrame:
    """Labelled / total per question."""
    done = df.human_label.str.strip() != ""
    return pd.DataFrame({"done": done.groupby(df.question).sum(), "total": df.groupby("question").size()}).astype(int)


def unmatched_ids(df: pd.DataFrame, test: Path = SLM_DATA / "test.jsonl") -> int | None:
    """How many gold ids are missing from the local test split (None when it has not been generated).
    Non-zero means backend/slm_data is stale: run `uniadvisor slm-data` or `slm-eval --gold` will skip rows."""
    frozen = test.parent / "gold_frozen.jsonl"
    source = frozen if frozen.exists() else test  # a frozen gold set does not depend on the current test split
    if not source.exists():
        return None
    ids = {json.loads(line)["id"] for line in open(source, encoding="utf-8")}
    return int((~df.id.isin(ids)).sum())
