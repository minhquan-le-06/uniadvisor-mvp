"""Evaluate a judge (fine-tuned SLM or the keyword baseline) on the synthetic test split or on the
human-labelled gold set.

  uniadvisor slm-eval --judge heuristic
  uniadvisor slm-eval --judge slm --model models/slm
  uniadvisor slm-eval --judge slm --gold data/slm/gold_labeled.csv     # human labels, never trained on
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from uniadvisor.paths import SLM_DATA
from uniadvisor.slm.infer import DEFAULT_THRESHOLD, HeuristicJudge
from uniadvisor.slm.metrics import by_group, summarize
from uniadvisor.slm.questions import BY_ID, INSUFFICIENT
from uniadvisor.slm.state import StudentProfile


def _load(split: str, data: Path) -> list[dict]:
    return [json.loads(line) for line in open(data / f"{split}.jsonl", encoding="utf-8")]


def evaluate(judge, split: str = "test", gold: Path | None = None, limit: int | None = None, data: Path = SLM_DATA) -> dict:  # noqa: ANN001
    rows = _load(split, data)
    if gold is not None:
        g = pd.read_csv(gold, dtype=str, keep_default_na=False)
        g = g[g.human_label.str.strip() != ""]
        labels = dict(zip(g.id, g.human_label.str.strip()))
        rows = [dict(r, label=labels[r["id"]]) for r in rows if r["id"] in labels]
    if limit:
        rows = rows[:limit]
    latents = {z["student_id"]: z for z in map(json.loads, open(data / "latents.jsonl", encoding="utf-8"))}
    snap = pd.read_csv(data / "programs_snapshot.csv", dtype={"program_code": str, "major_code": str})
    snap = snap.astype(object).where(snap.notna(), None)
    progs = {r["program_id"]: r for r in snap.to_dict("records")}
    items = []
    for r in rows:
        z = latents[r["student_id"]]
        p = StudentProfile(scores=z["scores"], province=z["province"], gender=z["gender"], score_kind=z["score_kind"], free_text=z["free_text"])
        items.append((r["question"], p, progs.get(r["program_id"]) if r["program_id"] else None))
    answers = judge.answer(items)
    recs = []
    for r, a in zip(rows, answers):
        rec = {"question": r["question"], "label": r["label"], "pred": a.label, "conf": a.confidence,
               "region": r.get("region"), "track": r.get("track"), "score_band": r.get("score_band")}
        if BY_ID[r["question"]].kind == "score" and INSUFFICIENT not in (a.label, r["label"]):
            rec["abs_level_err"] = abs(int(a.label) - int(r["label"]))
        recs.append(rec)
    df = pd.DataFrame(recs)
    thresholds = getattr(judge, "thresholds", None) or {q: DEFAULT_THRESHOLD for q in BY_ID}
    return {"judge": getattr(judge, "name", "?"), "split": "gold" if gold else split, "n": len(df),
            "per_question": summarize(df, thresholds), "by_group": by_group(df),
            "overall_accuracy": round(float((df.pred == df.label).mean()), 4)}


def compare_judges(limit: int | None = None) -> dict:
    out = {"heuristic": evaluate(HeuristicJudge(), limit=limit)}
    try:
        from uniadvisor.slm.infer import HybridJudge, load_slm

        slm = load_slm()
        if slm is not None:
            out["slm"] = evaluate(slm, limit=limit)
            out["hybrid"] = evaluate(HybridJudge(slm), limit=limit)
    except Exception as e:  # noqa: BLE001
        out["slm_error"] = str(e)
    return out
