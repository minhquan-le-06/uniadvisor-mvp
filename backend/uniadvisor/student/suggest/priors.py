"""The two scores per group that come from data, not from training (docs/MODEL.md, "Features"):

- a_k(x), subject fit: how much more often group k's admission combinations include each ticked subject than
  combinations overall (lift), capped at 3 and divided by 3, averaged over the ticked subjects. Small groups are pulled
  towards the overall share (10 pseudo-programs).
- c_k(x), work-type fit: the correlation between the student's RIASEC profile (1 per ticked work type, 0.5 per ticked
  hobby's type) and the group's O*NET profile, rescaled to [0, 1], as the O*NET Interest Profiler matches people to
  occupations.
- places_k: how many students group k takes, the sum of its programs' quotas in the latest year (a program without a
  quota counts as its group's median program). The suggester adds tau * (log places_k - mean) to every score: the
  training students are spread evenly over the groups, real students are not (Saerens et al. 2002; suggester.py).
  By field these shares match MOET's 2025 national enrolment (rank correlation 0.81, docs/MODEL.md).

A group's O*NET profile is the mean "Occupational Interests" score (1-7 per RIASEC type, O*NET 31.0, CC BY 4.0,
USDOL/ETA) of the occupations listed for it in backend/config/suggest/onet_groups.csv (hand-made, checked by hand on
2026-10-03; the check is onet_review.csv next to it). `build()` computes both tables once from the database and those
files and saves priors.json (plus group_profiles.csv, for people to read) to artifacts/models/suggester/; the app
only reads priors.json.
"""

from __future__ import annotations

import json

import numpy as np

from unidata.paths import MODELS, SUGGEST_CONFIG

OUT = MODELS / "suggester"
PRIORS = OUT / "priors.json"
TYPES = ["R", "I", "A", "S", "E", "C"]
ONET_TYPES = ["Realistic", "Investigative", "Artistic", "Social", "Enterprising", "Conventional"]
SHRINK = 10          # pseudo-programs pulling a small group's subject shares towards the overall share
LIFT_CAP = 3.0
HOBBY_WEIGHT = 0.5   # the only hand-set number of the model


def group_profiles(groups: list[str]):  # noqa: ANN201
    """group -> mean O*NET interest scores of its occupations (rounded to 2 decimals), as a DataFrame."""
    import pandas as pd

    onet = SUGGEST_CONFIG / "onet"
    occ = pd.read_csv(onet / "occupation_data.csv", dtype=str)
    ci = pd.read_csv(onet / "career_interest_types.csv", dtype=str)
    ci = ci[ci["Scale ID"] == "OI"].assign(v=lambda d: d["Data Value"].astype(float))
    prof = ci.pivot_table(index="O*NET-SOC Code", columns="Element Name", values="v")[ONET_TYPES]
    titles = dict(zip(occ["O*NET-SOC Code"], occ["Title"]))
    table = pd.read_csv(SUGGEST_CONFIG / "onet_groups.csv", dtype=str).set_index("group_code")
    missing = sorted(set(groups) - set(table.index))
    if missing:
        raise SystemExit(f"no O*NET occupations for groups {missing}: update {SUGGEST_CONFIG / 'onet_groups.csv'}")
    rows = []
    for g in groups:
        codes = table.at[g, "onet_codes"].split(";")
        unknown = [c for c in codes if c not in prof.index]
        if unknown:
            raise SystemExit(f"{g}: no O*NET interest profile for {unknown}")
        mean = prof.loc[codes].mean()
        rows.append({"group_code": g, "group_name": table.at[g, "group_name"],
                     "top3": "".join(t[0] for t in mean.sort_values(ascending=False, kind="stable").index[:3]),
                     **{t[0]: float(np.round(mean[t], 2)) for t in ONET_TYPES},
                     "occupations": "; ".join(f"{c} {titles[c]}" for c in codes)})
    return pd.DataFrame(rows)


def build(db=None) -> dict:  # noqa: ANN001
    """Lift table (subject -> group -> lift) and RIASEC profiles (group -> 6 numbers), saved to priors.json."""
    import pandas as pd

    from uniadvisor.student.form import picker
    from uniadvisor.student.form.options import SUBJECTS
    from unidata.db import get_db

    db = db or get_db()
    groups = [g.code for g in picker(db).groups]
    combos = db.combos
    c = db.catalog
    c = c[c.moet_group_code.isin(groups)]
    rows = []
    for r in c.itertuples():
        cs = r.combos if isinstance(r.combos, (list, tuple)) else str(r.combos or "").replace(";", ",").split(",")
        cs = [x.strip() for x in cs if x.strip() in combos]
        if not cs:
            continue
        rows.append({"group": r.moet_group_code, **{s: sum(s in combos[x] for x in cs) / len(cs) for s in SUBJECTS}})
    share = pd.DataFrame(rows)
    base = share[list(SUBJECTS)].mean()
    sums = share.groupby("group")[list(SUBJECTS)].sum()
    counts = share.groupby("group").size()
    lift = {}
    for s in SUBJECTS:
        lift[s] = {}
        for g in groups:
            n = counts.get(g, 0)
            shrunk = ((sums.loc[g, s] if n else 0.0) + SHRINK * base[s]) / (n + SHRINK)
            lift[s][g] = round(float(shrunk / base[s]), 4) if base[s] > 0 else 1.0

    prof = group_profiles(groups)
    riasec = {r.group_code: [float(getattr(r, t)) for t in TYPES] for r in prof.itertuples()}
    out = {"groups": groups, "subjects": list(SUBJECTS), "lift": lift, "riasec": riasec,
           "n_programs": {g: int(counts.get(g, 0)) for g in groups}, **places(db, c, groups)}
    OUT.mkdir(parents=True, exist_ok=True)
    PRIORS.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    prof.to_csv(OUT / "group_profiles.csv", index=False, encoding="utf-8-sig")
    return out


def places(db, catalog, groups: list[str]) -> dict:  # noqa: ANN001
    """{"places": group -> students taken (latest quota year), "places_year", "places_quota_share"}; programs without a
    quota count as their group's median program (the overall median when the group has none)."""
    q = db.tables.get("quotas")
    if q is None or q.empty:               # e.g. a simulated database: every group the same size
        return {"places": {g: 1.0 for g in groups}, "places_year": None, "places_quota_share": 0.0}
    year = int(q.year.max())
    q = q[q.year == year].groupby("program_id").quota.sum()
    c = catalog[["program_id", "moet_group_code"]].copy()
    c["quota"] = c.program_id.map(q)
    known = float(c.quota.notna().mean())
    overall = float(c.quota.median())
    c["quota"] = c.groupby("moet_group_code").quota.transform(lambda x: x.fillna(x.median() if x.notna().any() else overall))
    total = c.groupby("moet_group_code").quota.sum()
    return {"places": {g: round(float(total.get(g, overall)), 1) for g in groups}, "places_year": year,
            "places_quota_share": round(known, 3)}


def load() -> dict:
    return json.loads(PRIORS.read_text(encoding="utf-8"))


class Priors:
    """a(x) and c(x) as arrays over the groups, from the saved tables."""

    def __init__(self, data: dict | None = None):
        data = data or load()
        self.groups: list[str] = data["groups"]
        self.subjects: list[str] = data["subjects"]
        self.lift = np.array([[data["lift"][s][g] for g in self.groups] for s in self.subjects])   # S x K
        self.score = np.minimum(self.lift, LIFT_CAP) / LIFT_CAP
        prof = np.array([data["riasec"][g] for g in self.groups])                                # K x 6
        self.prof = prof - prof.mean(axis=1, keepdims=True)
        self.n_programs = np.array([data["n_programs"][g] for g in self.groups])
        lp = np.log([data["places"][g] for g in self.groups]) if "places" in data else np.zeros(len(self.groups))
        self.log_places = lp - lp.mean()       # 0 = a group of average size

    def subject_fit(self, subjects: list[str]) -> np.ndarray:
        idx = [self.subjects.index(s) for s in subjects if s in self.subjects]
        return self.score[idx].mean(axis=0) if idx else np.zeros(len(self.groups))

    def student_profile(self, work_types: list[str], hobby_types: list[str]) -> np.ndarray:
        u = np.zeros(6)
        for t in work_types:
            u[TYPES.index(t)] += 1.0
        for t in hobby_types:
            u[TYPES.index(t)] += HOBBY_WEIGHT
        return u

    def work_fit(self, u: np.ndarray) -> np.ndarray:
        """Correlation of u with each group profile, in [0, 1]; 0 when nothing was ticked, 0.5 when u is flat."""
        if not u.any():
            return np.zeros(len(self.groups))
        uc = u - u.mean()
        norm = np.linalg.norm(uc)
        if norm == 0:
            return np.full(len(self.groups), 0.5)
        corr = self.prof @ uc / (np.linalg.norm(self.prof, axis=1) * norm)
        return (1 + corr) / 2
