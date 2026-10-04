"""Where the training set's writer (Qwen) may have taught the suggester a habit instead of a fact (docs/MODEL.md).

Found by hand first: Qwen's students tick Toán far less often than Gemini's test students (16% vs 48%), and its
medicine students almost never do, so the model learned "Toán -> not medicine" although Y khoa admits on B00. This
report looks for the same kind of gap everywhere, two ways:

1. per answer option: how often students who answered that question tick it, in the training set (Qwen) and in the
   test set (Gemini, another model family). Large gaps are one model's habit;
2. per group and subject: how often the group's training students tick the subject against the share of the group's
   admission combinations that contain it (real data). A subject in nearly all of a group's combinations that its
   students rarely tick is a likely wrong lesson.

`uniadvisor suggest-audit` -> artifacts/reports/suggest_bias.md
"""

from __future__ import annotations

from collections import Counter

from uniadvisor.student import suggest as sg
from uniadvisor.student.form.options import SUBJECTS
from uniadvisor.student.suggest.review import read
from unidata.paths import SUGGEST_DATA

OPTIONS = {"subjects": SUBJECTS, "work_types": sg.WORK_TYPES, "hobbies": {k: v[0] for k, v in sg.HOBBIES.items()},
           "workplace": sg.WORKPLACES}


def tick_rates(rows: list[dict], key: str) -> dict[str, float]:
    answered = [r["answers"] for r in rows if r["answers"].get(key)]
    c = Counter(o for a in answered for o in a[key])
    return {o: c[o] / max(len(answered), 1) for o in OPTIONS[key]}


def admission_shares(db=None) -> dict[str, dict[str, float]]:  # noqa: ANN001
    """group -> subject -> share of the group's programs' admission combinations that contain the subject."""
    from uniadvisor.student.form import picker
    from unidata.db import get_db

    db = db or get_db()
    groups = {g.code for g in picker(db).groups}
    combos = db.combos
    sums: dict[str, Counter] = {}
    counts: Counter = Counter()
    for r in db.catalog.itertuples():
        if r.moet_group_code not in groups:
            continue
        cs = r.combos if isinstance(r.combos, (list, tuple)) else str(r.combos or "").replace(";", ",").split(",")
        cs = [x.strip() for x in cs if x.strip() in combos]
        if not cs:
            continue
        counts[r.moet_group_code] += 1
        s = sums.setdefault(r.moet_group_code, Counter())
        for subj in SUBJECTS:
            s[subj] += sum(subj in combos[x] for x in cs) / len(cs)
    return {g: {subj: sums[g][subj] / counts[g] for subj in SUBJECTS} for g in sums}


def report(db=None) -> str:  # noqa: ANN001
    from uniadvisor.student.form import picker
    from unidata.db import get_db

    db = db or get_db()
    p = picker(db)
    train, test = read(SUGGEST_DATA / "train.jsonl"), read(SUGGEST_DATA / "testset.jsonl")
    out = ["# Suggester: possible habits of the training-set writer", "",
           f"Training set (Qwen): {len(train)} students; test set (Gemini): {len(test)}. Rates are over the students "
           "who answered that question.", "", "## 1. Each option: training vs test", "",
           "| Question | Option | Train | Test | Ratio |", "|---|---|---|---|---|"]
    gaps = []
    for key, names in OPTIONS.items():
        tr, te = tick_rates(train, key), tick_rates(test, key)
        for o, name in names.items():
            if max(tr[o], te[o]) < 0.03:
                continue
            ratio = (tr[o] + 0.01) / (te[o] + 0.01)
            gaps.append((abs(__import__("math").log(ratio)), key, name, tr[o], te[o], ratio))
    for _, key, name, a, b, ratio in sorted(gaps, reverse=True)[:20]:
        out.append(f"| {key} | {name} | {a:.0%} | {b:.0%} | {ratio:.2f} |")
    out += ["", "Ratio < 1: Qwen ticks it less than Gemini; > 1: more. The 20 largest gaps are shown.", "",
            "## 2. Subjects per group: training students vs admission combinations", "",
            "A subject in at least 60% of a group's combinations that fewer than 30% of its training students tick.",
            "", "| Group | Subject | In combinations | Ticked in training |", "|---|---|---|---|"]
    shares = admission_shares(db)
    flagged = []
    for g, subj_share in shares.items():
        mine = [r for r in train if g in r["groups"]]
        if not mine:
            continue
        ticked = tick_rates(mine, "subjects")
        for subj, share in subj_share.items():
            if share >= 0.6 and ticked[subj] < 0.3:
                flagged.append((share - ticked[subj], g, subj, share, ticked[subj]))
    for _, g, subj, share, t in sorted(flagged, reverse=True):
        out.append(f"| {g} {p.name(g)} | {SUBJECTS[subj]} | {share:.0%} | {t:.0%} |")
    by_subject = Counter(subj for _, _, subj, _, _ in flagged)
    out += ["", f"{len(flagged)} group-subject pairs flagged; by subject: "
            + ", ".join(f"{SUBJECTS[s]} {n}" for s, n in by_subject.most_common()) + "."]
    return "\n".join(out) + "\n"
