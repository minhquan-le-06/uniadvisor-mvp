"""Build the SLM dataset: synthetic students x REAL programs x typed questions, soft labels.

Splits are by university (a school's programs appear in one split only) so the test set measures
generalisation to unseen schools; students are split too and only paired with programs of their
split. Exact duplicates are removed and no free text from train appears in val/test.

Outputs in backend/slm_data/:
  train.jsonl / val.jsonl / test.jsonl   one example per line (see `example()`)
  latents.jsonl                           hidden attributes per synthetic student (audit only)
  rubrics.md                              the written rubric per question (for labellers and LLM teachers)
  gold_to_label.csv                       ~300 test examples for HUMAN labelling (never trained on)
  stats.json
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter

import numpy as np
import pandas as pd

from unidata.db import get_db, require_real
from unidata.paths import SLM_DATA
from uniadvisor.student.slm import teacher
from uniadvisor.student.slm.questions import INSUFFICIENT, PROFILE_QUESTIONS, PROGRAM_QUESTIONS, QUESTIONS
from uniadvisor.student.slm.state import StudentProfile, model_input
from uniadvisor.student.slm.synth import ProfileGenerator

SPLITS = {"train": 0.7, "val": 0.15, "test": 0.15}


def split_schools(schools: list[str], seed: int) -> dict[str, str]:
    rng = random.Random(seed)
    s = sorted(schools)
    rng.shuffle(s)
    n = len(s)
    n_val, n_test = max(2, round(n * SPLITS["val"])), max(2, round(n * SPLITS["test"]))
    out = {c: "val" for c in s[:n_val]}
    out.update({c: "test" for c in s[n_val:n_val + n_test]})
    out.update({c: "train" for c in s[n_val + n_test:]})
    return out


def score_band(scores: dict[str, float]) -> str:
    m = float(np.mean(list(scores.values())))
    return "<6" if m < 6 else "6-7.5" if m < 7.5 else "7.5-8.5" if m < 8.5 else ">=8.5"


def _programs_for(z, pool: pd.DataFrame, k: int, rng: random.Random) -> list[dict]:
    chosen: list[dict] = []
    by_field = {f: g for f, g in pool.groupby("field")}

    def take(frame: pd.DataFrame | None) -> None:
        if frame is not None and len(frame):
            row = frame.iloc[rng.randrange(len(frame))].to_dict()
            if row["program_id"] not in {c["program_id"] for c in chosen}:
                chosen.append(row)

    for f, _ in z.interests[:2]:
        take(by_field.get(f))
    if z.dislikes:
        take(by_field.get(rng.choice(z.dislikes)))
    if z.parent_field:
        take(by_field.get(z.parent_field))
    if rng.random() < 0.35:
        take(pool[pool.conditions.fillna("").str.len() > 0])
    while len(chosen) < k:
        take(pool)
    return chosen[:k]


def example(qid: str, profile: StudentProfile, program: dict | None, soft: dict[str, float], split: str, meta: dict) -> dict:
    q = next(x for x in QUESTIONS if x.id == qid)
    a, b = model_input(q.text_vi, profile, program)
    hard = max(soft, key=soft.get)
    return {
        "question": qid, "kind": q.kind, "split": split, "text_a": a, "text_b": b,
        "soft_label": {k: round(v, 4) for k, v in soft.items()}, "label": hard, **meta,
        "program_id": program["program_id"] if program else None,
        "school_code": program["school_code"] if program else None,
    }


def build(n_students: int = 4000, programs_per_student: int = 4, seed: int = 13, gold_size: int = 300) -> dict:
    SLM_DATA.mkdir(parents=True, exist_ok=True)
    db = get_db()
    require_real(db, "building the SLM dataset (students are paired with real programs)")
    programs = db.catalog
    school_split = split_schools(programs.school_code.unique().tolist(), seed)
    pools = {s: programs[programs.school_code.map(school_split) == s] for s in SPLITS}
    gen = ProfileGenerator(seed)
    rng = random.Random(seed + 1)
    rows: dict[str, list[dict]] = {s: [] for s in SPLITS}
    latents = []
    seen: set[str] = set()
    for i in range(n_students):
        split = rng.choices(list(SPLITS), weights=list(SPLITS.values()))[0]
        z = gen.latent()
        text = gen.text(z)
        profile = StudentProfile(scores=z.scores, province=z.province, gender=z.gender, score_kind=z.score_kind, free_text=text)
        meta = {"student_id": f"s{i:05d}", "region": z.region, "track": "+".join(sorted(k for k in z.scores if k not in ("TO", "VA"))),
                "score_band": score_band(z.scores), "voice": z.voice}
        latents.append({"student_id": meta["student_id"], "split": split, "free_text": text, **z.to_dict()})
        for q in PROFILE_QUESTIONS:
            rows[split].append(example(q.id, profile, None, teacher.label(q.id, z, None, rng), split, meta))
        for p in _programs_for(z, pools[split], programs_per_student, rng):
            for q in PROGRAM_QUESTIONS:
                rows[split].append(example(q.id, profile, p, teacher.label(q.id, z, p, rng), split, meta))

    # the frozen gold set (backend/slm_data/gold_frozen.jsonl) is the fixed evaluation set: its students' texts never
    # appear in any split, so regenerating the data can neither break the gold labels nor leak them into training
    frozen_path = SLM_DATA / "gold_frozen.jsonl"
    frozen = [json.loads(line) for line in open(frozen_path, encoding="utf-8")] if frozen_path.exists() else None
    gold_texts = {r["latent"]["free_text"] for r in frozen} if frozen else set()
    free_text = {z["student_id"]: z["free_text"] for z in latents}

    # dedupe + no train free text in val/test
    train_texts = {r["text_a"] for r in rows["train"]}
    stats: dict = {"schools_per_split": Counter(school_split.values()), "dropped_leak": 0, "dropped_dup": 0, "dropped_gold": 0}
    for split in SPLITS:
        kept = []
        for r in rows[split]:
            if free_text[r["student_id"]] in gold_texts:
                stats["dropped_gold"] += 1
                continue
            key = hashlib.sha1((r["question"] + r["text_a"] + r["text_b"]).encode()).hexdigest()
            if key in seen:
                stats["dropped_dup"] += 1
                continue
            if split != "train" and r["text_a"] in train_texts:
                stats["dropped_leak"] += 1
                continue
            seen.add(key)
            r["id"] = key[:16]
            kept.append(r)
        rows[split] = kept
        with open(SLM_DATA / f"{split}.jsonl", "w", encoding="utf-8") as f:
            for r in kept:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(SLM_DATA / "latents.jsonl", "w", encoding="utf-8") as f:
        for z in latents:
            f.write(json.dumps(z, ensure_ascii=False) + "\n")
    # the exact program rows the texts were rendered from (evaluation rebuilds inputs from these)
    programs.assign(split=programs.school_code.map(school_split)).to_csv(SLM_DATA / "programs_snapshot.csv", index=False, encoding="utf-8")

    # rubric + gold template
    md = ["# SLM question rubrics\n", "Every question also allows **insufficient** (not enough information).\n"]
    for q in QUESTIONS:
        md += [f"\n## {q.id} ({q.kind}, {q.scope})\n", f"**Question:** {q.text_vi}\n",
               "**Labels:** " + ", ".join(f"`{a}` = {b}" for a, b in zip(q.labels, q.labels_vi)) + f", `{INSUFFICIENT}`\n",
               f"\n{q.rubric}\n"]
    (SLM_DATA / "rubrics.md").write_text("\n".join(md), encoding="utf-8")
    if frozen:
        gold = pd.DataFrame(frozen)
    else:
        test = pd.DataFrame(rows["test"])
        per_q = max(1, gold_size // len(QUESTIONS))
        gold = pd.concat([g.sample(min(per_q, len(g)), random_state=seed) for _, g in test.groupby("question")])
    gold = gold.assign(options=gold.question.map(lambda q: " | ".join(next(x for x in QUESTIONS if x.id == q).all_labels)),
                       human_label="", labeller="", note="")
    gold[["id", "question", "options", "text_a", "text_b", "human_label", "labeller", "note"]].to_csv(
        SLM_DATA / "gold_to_label.csv", index=False, encoding="utf-8-sig")

    for split in SPLITS:
        df = pd.DataFrame(rows[split])
        stats[split] = {"examples": len(df), "students": int(df.student_id.nunique()),
                        "label_dist": {q: g.label.value_counts(normalize=True).round(3).to_dict() for q, g in df.groupby("question")},
                        "mean_max_soft": round(float(df.soft_label.map(lambda d: max(d.values())).mean()), 3)}
    stats["schools_per_split"] = dict(stats["schools_per_split"])
    (SLM_DATA / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    return stats
