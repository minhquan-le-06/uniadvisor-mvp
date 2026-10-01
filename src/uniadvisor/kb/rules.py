"""Deterministic admission rules. Everything here has one correct answer and is unit-tested."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import yaml

from uniadvisor.paths import RULES

DEFAULT_RULESET = "2027-draft"


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


@lru_cache(maxsize=None)
def load_rules(ruleset: str = DEFAULT_RULESET) -> dict:
    data = yaml.safe_load((RULES / f"{ruleset}.yaml").read_text(encoding="utf-8"))
    if data.get("inherits"):
        data = _merge(load_rules(data["inherits"]), {k: v for k, v in data.items() if k != "inherits"})
    return data


# ------------------------------------------------------------------ priority points
def priority_points(raw_total: float, area: str = "KV3", category: str = "none", years_since_graduation: int = 0,
                    ruleset: str = DEFAULT_RULESET) -> float:
    """Điểm ưu tiên on the 30-point scale, with the >= 22.5 taper (from 2025)."""
    r = load_rules(ruleset)["priority"]
    area_pts = r["area"].get(area, 0.0) if years_since_graduation <= r["area_valid_years_after_graduation"] else 0.0
    base = area_pts + r["category"].get(category, 0.0)
    if raw_total >= r["taper_from"]:
        base = (30.0 - raw_total) / r["taper_denominator"] * base
    return round(max(base, 0.0), 2)


# ------------------------------------------------------------------ combos and eligibility
def _combos(combos: dict[str, list[str]] | None) -> dict[str, list[str]]:
    if combos is not None:
        return combos
    from uniadvisor.db import get_db

    return get_db().combos


def combo_total(scores: dict[str, float], combo: str, combos: dict[str, list[str]] | None = None) -> float | None:
    """Sum of the combination's 3 subjects, or None if the student lacks one of them.
    Scores are keyed by subject code; the foreign-language score sits under its own code
    (N1 English, N3 French, N4 Chinese, ...), so D01 needs N1 and D03 needs N3.
    combos: combination -> subjects (default: the database's combos table)."""
    parts = _combos(combos).get(combo)
    if not parts:
        return None
    vals = [scores.get(s) for s in parts]
    if any(v is None for v in vals):
        return None
    return round(float(sum(vals)), 2)


def student_combos(scores: dict[str, float], combos: dict[str, list[str]] | None = None) -> dict[str, float]:
    """Every exam combination the student can use, with its raw total."""
    combos = _combos(combos)
    out = {}
    for combo in combos:
        t = combo_total(scores, combo, combos)
        if t is not None:
            out[combo] = t
    return out


@dataclass
class Eligibility:
    eligible: bool
    combo: str | None = None          # best combination for this program
    raw_total: float | None = None
    priority: float = 0.0
    total: float | None = None        # raw + priority, what is compared with the cutoff
    reasons: list[str] = field(default_factory=list)


def floor_for(major_code: str, field_: str, ruleset: str = DEFAULT_RULESET) -> tuple[float, str] | None:
    floors = load_rules(ruleset)["floors"]
    best = None
    for key, f in floors.items():
        if not isinstance(f, dict):
            continue
        if any(str(major_code or "").startswith(p) for p in f["major_prefixes"]):
            if best is None or f["min_total"] > best[0]:
                best = (f["min_total"], f["note"])
    if best is None and field_ == "su_pham":
        f = floors["teacher_training"]
        best = (f["min_total"], f["note"])
    return best


def eligibility(program: dict, scores: dict[str, float], area: str = "KV3", category: str = "none",
                years_since_graduation: int = 0, gender: str | None = None, ruleset: str = DEFAULT_RULESET,
                combo_parts: dict[str, list[str]] | None = None) -> Eligibility:
    """Which of the program's combinations the student can use, the best total, and hard rule checks."""
    combo_parts = _combos(combo_parts)
    combos = [c for c in str(program.get("combos") or "").split(";") if c]
    mine = {c: combo_total(scores, c, combo_parts) for c in combos}
    mine = {c: t for c, t in mine.items() if t is not None}
    if not mine:
        return Eligibility(False, reasons=[f"Không có tổ hợp phù hợp (ngành xét: {', '.join(combos) or '?'})"])
    combo = max(mine, key=mine.get)
    raw = mine[combo]
    pri = priority_points(raw, area, category, years_since_graduation, ruleset)
    total = round(raw + pri, 2)
    reasons = []
    ok = True
    fl = floor_for(str(program.get("major_code") or ""), str(program.get("field") or ""), ruleset)
    if fl and total < fl[0]:
        ok = False
        reasons.append(f"Dưới ngưỡng sàn của Bộ ({fl[1]}: {fl[0]})")
    cond = str(program.get("conditions") or "").lower()
    if gender and "chỉ tuyển thí sinh nam" in cond and gender == "nu":
        ok, reasons = False, reasons + ["Chỉ tuyển thí sinh nam"]
    if gender and "chỉ tuyển thí sinh nữ" in cond and gender == "nam":
        ok, reasons = False, reasons + ["Chỉ tuyển thí sinh nữ"]
    return Eligibility(ok, combo, raw, pri, total, reasons)


# ------------------------------------------------------------------ buckets and list constraints
def risk_bucket(p: float, ruleset: str = DEFAULT_RULESET) -> str:
    b = load_rules(ruleset)["risk_buckets"]
    if p >= b["safe"]:
        return "safe"
    if p >= b["match"]:
        return "match"
    if p >= b["reach"]:
        return "reach"
    return "unlikely"


BUCKET_VI = {"safe": "An toàn", "match": "Vừa sức", "reach": "Thử thách", "unlikely": "Khó đỗ"}


def list_constraints(risk_tolerance: str | None, ruleset: str = DEFAULT_RULESET) -> dict:
    r = load_rules(ruleset)
    lp = r["list_policy"]
    return {
        "max_choices": min(r["application"]["max_choices"], 15),
        "target_size": lp["target_size"],
        "min_safe": lp["min_safe"].get(risk_tolerance or "", lp["default_min_safe"]),
    }
