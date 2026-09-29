"""Read the UniPilotData step-1 CSV export (schools, 2026 programs, combos, majors)."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from uniadvisor.paths import UNIPILOT_OUT

EXCLUDED_SUBJECTS = {"NK", "KHTN", "KHXH", "NN"}  # talent tests and pre-2025 combined tests
FOREIGN_LANGS = {"N1", "N2", "N3", "N4", "N5", "N6", "N7"}


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(UNIPILOT_OUT / f"{name}.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)


@lru_cache(maxsize=None)
def table(name: str) -> pd.DataFrame:
    return _read(name)


@lru_cache(maxsize=1)
def combo_parts() -> dict[str, list[str]]:
    """combo code -> its 3 subject codes (2026 list; all weights are 1 there)."""
    p = table("subject_combo_part").copy()
    p["position"] = p["position"].astype(int)
    out: dict[str, list[str]] = {}
    for code, g in p.sort_values("position").groupby("combo_code"):
        subjects = list(g["subject_code"])
        if len(subjects) == 3:
            out[code] = subjects
    return out


def exam_combos() -> dict[str, list[str]]:
    """Combos that use only national-exam subjects (no talent test)."""
    return {c: s for c, s in combo_parts().items() if not (set(s) & EXCLUDED_SUBJECTS)}


@lru_cache(maxsize=1)
def subject_names() -> dict[str, str]:
    s = table("subject")
    return dict(zip(s["code"], s["name_vi"]))
