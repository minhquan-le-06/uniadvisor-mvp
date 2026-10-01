"""Evaluate a judge (fine-tuned SLM or the keyword baseline) on the synthetic test split or on the
human-labelled gold set.

  uniadvisor slm-eval --judge heuristic
  uniadvisor slm-eval --judge slm --model artifacts/models/slm
  uniadvisor slm-eval --judge slm --gold data/slm/gold_labeled.csv     # human labels, never trained on
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

from uniadvisor.paths import SLM_DATA
from uniadvisor.slm.infer import DEFAULT_THRESHOLD, HeuristicJudge
from uniadvisor.slm.metrics import by_group, summarize
from uniadvisor.slm.questions import BY_ID, INSUFFICIENT
from uniadvisor.slm.state import StudentProfile


def _load(split: str, data: Path) -> list[dict]:
    return [json.loads(line) for line in open(data / f"{split}.jsonl", encoding="utf-8")]


def load_frozen(data: Path = SLM_DATA) -> list[dict] | None:
    """The gold rows exactly as labelled (text, latent student, program), or None if not frozen yet.
    Evaluating on these keeps gold labels valid when the synthetic dataset is regenerated."""
    path = data / "gold_frozen.jsonl"
    return [json.loads(line) for line in open(path, encoding="utf-8")] if path.exists() else None


def evaluate(judge, split: str = "test", gold: Path | None = None, limit: int | None = None, data: Path = SLM_DATA) -> dict:  # noqa: ANN001
    frozen = load_frozen(data) if gold is not None else None
    if frozen is not None:
        latents = {r["student_id"]: r["latent"] for r in frozen}
        progs = {r["program_id"]: r["program"] for r in frozen if r["program_id"]}
        rows = frozen
    else:
        rows = _load(split, data)
        latents = {z["student_id"]: z for z in map(json.loads, open(data / "latents.jsonl", encoding="utf-8"))}
        snap = pd.read_csv(data / "programs_snapshot.csv", dtype={"program_code": str, "major_code": str})
        snap = snap.astype(object).where(snap.notna(), None)
        progs = {r["program_id"]: r for r in snap.to_dict("records")}
    if gold is not None:
        g = pd.read_csv(gold, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        g = g[g.human_label.str.strip() != ""]
        labels = dict(zip(g.id, g.human_label.str.strip()))
        rows = [dict(r, label=labels[r["id"]]) for r in rows if r["id"] in labels]
    if limit:
        rows = rows[:limit]
    items = []
    for r in rows:
        z = latents[r["student_id"]]
        p = StudentProfile(scores=z["scores"], province=z["province"], gender=z["gender"], score_kind=z["score_kind"], free_text=z["free_text"])
        items.append((r["question"], p, progs.get(r["program_id"]) if r["program_id"] else None))
    answers = []
    chunk = 512
    t0 = time.time()
    for s in range(0, len(items), chunk):  # in chunks, so long CPU runs show progress instead of looking frozen
        answers += judge.answer(items[s:s + chunk])
        if len(items) > chunk:
            done = min(s + chunk, len(items))
            eta = (time.time() - t0) / done * (len(items) - done)
            print(f"[slm-eval] {done}/{len(items)} rows, ~{eta / 60:.0f} min left", file=sys.stderr, flush=True)
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
