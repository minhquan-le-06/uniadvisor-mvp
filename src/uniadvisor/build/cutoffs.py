"""Clean THPT-exam cutoffs from both news sources, cross-check them, and flag problems.

Output: data/processed/cutoffs.csv (one row per school x program code x year) and
data/processed/check_problems.csv.

Rules
- VnExpress has a dedicated 'Điểm chuẩn THPT' column -> method is explicit.
- VietNamNet mixes methods; the method is in a free-text note. A row counts as THPT when its note
  says so ('THPT', 'điểm thi', 'tốt nghiệp'). If no row of that school-year mentions any method,
  rows are assumed THPT (evidence 'assumed_no_method_notes') - this is how 2023 lists were published.
  Rows whose note names another method (học bạ, ĐGNL, TSA, V-SAT, kết hợp, quy đổi, ...) are dropped.
- Scale: <= 30 -> 30-point scale (in scope). 30 < s <= 40 -> 40-point (doubled subject), > 40 ->
  100/150-point combined scores: both out of scope for probabilities.
- Two sources agree when they differ by <= 0.05. Equal trust (both 3), so on disagreement we keep
  VnExpress (explicit THPT column) and mark the row 'disputed'.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from uniadvisor.paths import COLLECTED, PROCESSED, ensure_dirs
from uniadvisor.text import clean, fold, parse_score, split_combos

THPT_WORDS = ("thpt", "diem thi", "tot nghiep", "thi tn")
OTHER_PHRASES = ("hoc ba", "danh gia nang luc", "danh gia tu duy", "v-sat", "vsat", "ket hop", "quy doi", "tuong duong",
                 "chung chi", "ielts", "xet tuyen thang", "uu tien xet", "phong van", "nang khieu", "thang diem 100",
                 "thang 100", "hoc tap", "toefl", "a-level", "ib ")
OTHER_TOKENS = {"dgnl", "dgtd", "tsa", "hsa", "apt", "sat", "act", "xttn", "ccqt", "spt", "hb"}
AGREE = 0.05


def scale_of(score: float) -> int:
    return 30 if score <= 30.0 else (40 if score <= 40.0 else 100)


def _method(note: str) -> str:
    """'thpt' / 'other' / 'unknown' (empty note). Any sign of another method wins over 'THPT',
    because combined methods ('kết hợp điểm thi THPT với chứng chỉ') also mention THPT."""
    f = f" {fold(note)} "
    f = re.sub(r"thang diem:?\s*30(?!\d)", " ", f)  # a note that only states the 30-point scale says nothing about the method
    tokens = set(re.findall(r"[a-z0-9-]+", f))
    if any(p in f for p in OTHER_PHRASES) or tokens & OTHER_TOKENS:
        return "other"
    if any(w in f for w in THPT_WORDS):
        return "thpt"
    return "other" if f.strip(" |.-") else "unknown"


def vnexpress_rows() -> pd.DataFrame:
    df = pd.read_csv(COLLECTED / "vnexpress_cutoffs.csv", dtype=str, keep_default_na=False)
    df["score"] = df["thpt_score_raw"].map(parse_score)
    df = df[df.score.notna() & (df.score > 0)].copy()
    df["year"] = df.year.astype(int)
    df["combos"] = df.combos.map(lambda s: ";".join(split_combos(s)))
    df["evidence"] = "explicit_thpt_column"
    return df[["source", "school_code", "year", "program_code", "program_name", "combos", "score", "evidence",
               "other_methods", "tuition_raw", "url", "fetched_at"]]


def vietnamnet_rows() -> pd.DataFrame:
    path = COLLECTED / "vietnamnet_cutoffs.csv"
    if not path.exists():
        return pd.DataFrame(columns=["source", "school_code", "year", "program_code", "program_name", "combos", "score", "evidence", "url", "fetched_at"])
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = df[df.training_type.isin(["2", "2.0", ""])].copy()  # 2 = university level
    df["year"] = df.year.astype(int)
    df["score"] = df.score_raw.map(parse_score)
    df = df[df.score.notna() & (df.score > 0)]
    df["method"] = df.note.map(_method)
    out = []
    for (school, year), g in df.groupby(["school_code", "year"]):
        if (g.method == "thpt").any():
            keep = g[g.method == "thpt"].assign(evidence="note_says_thpt")
        elif (g.method == "other").any():
            keep = g[g.method == "unknown"].assign(evidence="no_note_while_others_named")
            keep = keep.iloc[0:0] if len(keep) > 0.8 * len(g) else keep  # too ambiguous, skip
        else:
            keep = g.assign(evidence="assumed_no_method_notes")
        out.append(keep)
    df = pd.concat(out) if out else df.iloc[0:0]
    df["combos"] = df.combos_raw.map(lambda s: ";".join(split_combos(s)))
    return df[["source", "school_code", "year", "program_code", "program_name", "combos", "score", "evidence", "url", "fetched_at"]]


def _dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """Several rows for one program code in one year (per-combo cutoffs, campuses): keep the lowest
    30-scale score (the easiest way in) and remember that there were several."""
    df = df.copy()
    df["key_code"] = df.program_code.where(df.program_code != "", df.program_name.map(fold))
    df["n_rows"] = df.groupby(["source", "school_code", "year", "key_code"]).score.transform("size")
    df = df.sort_values("score").drop_duplicates(["source", "school_code", "year", "key_code"], keep="first")
    return df


def tuyensinh247_rows() -> pd.DataFrame:
    path = COLLECTED / "tuyensinh247_cutoffs.csv"
    cols = ["source", "school_code", "year", "program_code", "program_name", "combos", "score", "evidence", "url", "fetched_at"]
    if not path.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df["year"] = df.year.astype(int)
    df["score"] = df.score_raw.map(parse_score)
    df = df[df.score.notna() & (df.score > 0)].copy()
    df["evidence"] = "method_alias_diem_thi_thpt"
    return df[cols]


# (short name, frame suffix, trust); earlier = preferred when sources disagree without a majority
SOURCES = (("vne", "vnexpress_cutoffs", 3), ("vnn", "vietnamnet_cutoffs", 3), ("ts", "tuyensinh247_cutoffs", 4))


def _consensus(values: dict[str, float]) -> tuple[float, str, str, str | None]:
    """values: {short source name: score} -> (score, status, chosen source, message about an outlier)."""
    names = list(values)
    if len(names) == 1:
        return values[names[0]], "single_source", names[0], None
    groups = []  # sources whose scores agree within AGREE, in preference order
    for n in names:
        g = [m for m in names if abs(values[m] - values[n]) <= AGREE]
        groups.append(g)
    best = max(groups, key=len)
    detail = ", ".join(f"{n}={values[n]:g}" for n in names)
    if len(best) == len(names):
        return values[best[0]], "confirmed_2_sources", best[0], None
    if len(best) >= 2:
        return values[best[0]], "confirmed_2_sources", best[0], f"majority kept, one source differs ({detail})"
    return values[names[0]], "disputed", names[0], f"sources disagree ({detail})"


def build() -> dict:
    ensure_dirs()
    frames = {"vne": _dedupe(vnexpress_rows()), "vnn": _dedupe(vietnamnet_rows()), "ts": _dedupe(tuyensinh247_rows())}
    keys = ["school_code", "year", "key_code"]
    merged = None
    for short, df in frames.items():
        df = df.rename(columns={c: f"{c}_{short}" for c in df.columns if c not in keys})
        merged = df if merged is None else merged.merge(df, on=keys, how="outer")
    # rows only tuyensinh247 has are used for cross-checking only: they never add a program-year on their own
    merged = merged[merged.score_vne.notna() | merged.score_vnn.notna()]

    rows, problems = [], []
    for r in merged.to_dict("records"):
        values = {s: float(r[f"score_{s}"]) for s, _, _ in SOURCES if pd.notna(r.get(f"score_{s}"))}
        score, status, chosen, msg = _consensus(values)
        if msg:
            problems.append(dict(rule="sources_disagree", severity="warning" if status == "disputed" else "info",
                                 school_code=r["school_code"], year=r["year"], program=r["key_code"], message=msg))

        def pick(field: str) -> str:
            for s, _, _ in SOURCES:
                v = r.get(f"{field}_{s}")
                if isinstance(v, str) and v:
                    return v
            return ""

        rows.append(dict(
            school_code=r["school_code"], year=int(r["year"]), program_code=clean(pick("program_code")), program_name=clean(pick("program_name")),
            key_code=r["key_code"], score=float(score), scale=scale_of(float(score)), combos=pick("combos"), status=status,
            chosen_source=dict((s, full) for s, full, _ in SOURCES)[chosen], n_sources=len(values),
            score_vnexpress=values.get("vne", np.nan), score_vietnamnet=values.get("vnn", np.nan), score_tuyensinh247=values.get("ts", np.nan),
            method_evidence=r.get(f"evidence_{chosen}"),
            several_rows=any(r.get(f"n_rows_{s}", 1) not in (1, None) and pd.notna(r.get(f"n_rows_{s}")) and r.get(f"n_rows_{s}") > 1 for s, _, _ in SOURCES),
            tuition_raw=r.get("tuition_raw_vne") if isinstance(r.get("tuition_raw_vne"), str) else "",
            url=r.get(f"url_{chosen}"),
        ))
    cut = pd.DataFrame(rows).sort_values(["school_code", "key_code", "year"])

    # validation
    for r in cut.itertuples(index=False):
        if r.scale != 30:
            problems.append(dict(rule="not_30_point_scale", severity="info", school_code=r.school_code, year=r.year,
                                 program=r.key_code, message=f"score {r.score} looks like a {r.scale}-point scale; no probability"))
        elif r.score < 15:
            problems.append(dict(rule="below_15", severity="warning", school_code=r.school_code, year=r.year,
                                 program=r.key_code, message=f"cutoff {r.score} < 15/30 (check it is the THPT method)"))
    s30 = cut[cut.scale == 30].sort_values("year")
    for (school, key), g in s30.groupby(["school_code", "key_code"]):
        diffs = g.score.diff().abs()
        for yr, d in zip(g.year, diffs):
            if pd.notna(d) and d > 3:
                problems.append(dict(rule="jump_over_3", severity="warning", school_code=school, year=int(yr), program=key,
                                     message=f"year-on-year change {d:.2f} points"))

    cut.to_csv(PROCESSED / "cutoffs.csv", index=False, encoding="utf-8")
    pr = pd.DataFrame(problems)
    pr.to_csv(PROCESSED / "check_problems.csv", index=False, encoding="utf-8")
    summary = {
        "rows": len(cut),
        "by_year_status": cut.groupby(["year", "status"]).size().rename("n").reset_index().to_dict("records"),
        "by_scale": cut.scale.value_counts().to_dict(),
        "problems": pr.groupby("rule").size().to_dict() if len(pr) else {},
    }
    return summary
