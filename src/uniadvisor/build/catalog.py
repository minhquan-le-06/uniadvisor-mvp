"""In-scope schools and programs -> data/processed/schools.csv, programs.csv, history.csv.

A program is in scope when its school is in config/scope.yaml, it has a THPT cutoff on the 30-point
scale in the latest year (so a forecast is possible), and at least one exam-only combination.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import yaml

from uniadvisor.build.fields import FIELDS, field_of
from uniadvisor.build.unipilot import combo_parts, exam_combos, table
from uniadvisor.engine.dist import PROVENANCE_RANK
from uniadvisor.paths import CONFIG, PROCESSED, ensure_dirs
from uniadvisor.text import clean, fold, split_combos

LATEST = 2026


def parse_tuition(text: str) -> tuple[float | None, float | None, str]:
    """'35.000.000 - 45.000.000' -> (35e6, 45e6). Per-credit or per-semester prices are flagged, not converted."""
    t = fold(text)
    if not t:
        return None, None, ""
    nums = [float(n.replace(".", "").replace(",", "")) for n in re.findall(r"\d[\d\.,]*\d", t)]
    nums = [n for n in nums if n >= 1_000_000]
    if not nums:
        return None, None, "unparsed"
    unit = "per_credit" if "tin chi" in t else ("per_semester" if "hoc ky" in t or "ky" in t.split() else "per_year")
    return min(nums), max(nums), unit


def program_kind(name: str, kind_src: str = "") -> str:
    f = fold(name)
    if kind_src in ("international", "advanced", "high_quality"):
        return kind_src
    if any(w in f for w in ("lien ket", "song bang", "dai hoc troy", "west of england", "quoc te", "co-op", "twinning")):
        return "international"
    if "tien tien" in f or re.search(r"\bct tien tien\b", f):
        return "advanced"
    if "chat luong cao" in f or re.search(r"\bclc\b", f):
        return "high_quality"
    return "standard"


def campus_of(name: str) -> str | None:
    m = re.search(r"(?:phân hiệu|cơ sở|campus|học tại)\s+(?:tại\s+)?([A-ZĐÂ][^\)\(,;]{2,30})", name, flags=re.IGNORECASE)
    return clean(m.group(1)) if m else None


def conditions_of(name: str, kind: str, field: str | None, major_code: str) -> list[str]:
    f = fold(name)
    out = []
    if kind in ("advanced", "international") or "tieng anh" in f or "english" in f:
        out.append("Học bằng tiếng Anh (thường cần trình độ tiếng Anh tốt, có thể yêu cầu IELTS/chứng chỉ khi nhập học)")
    if kind == "international":
        out.append("Chương trình liên kết/quốc tế: học phí cao hơn chương trình chuẩn")
    if field == "su_pham" or major_code.startswith("71402"):
        out.append("Sư phạm: không nhận thí sinh bị dị hình, dị tật, nói ngọng, nói lắp; điểm sàn của Bộ")
    if field == "y_duoc":
        out.append("Khối sức khỏe: có ngưỡng điểm sàn của Bộ")
    m = re.search(r"thí sinh (nam|nữ)", name, flags=re.IGNORECASE)
    if m:
        out.append(f"Chỉ tuyển thí sinh {m.group(1).lower()}")
    if campus_of(name):
        out.append(f"Học tại {campus_of(name)}")
    return out


def _unipilot_programs() -> pd.DataFrame:
    p = table("program")
    p = p[p.year == str(LATEST)].copy()
    m = table("program_admission_method")
    thpt_labels = m[m.method_code == "100"][["program_id", "method_label"]]
    sc = table("program_subject_combo").merge(thpt_labels, on=["program_id", "method_label"])
    combos = sc.groupby("program_id").combo_code.apply(lambda s: ";".join(dict.fromkeys(s)))
    p["combos_thpt"] = p.id.map(combos).fillna("")
    return p


def _pick_unipilot(up: pd.DataFrame, school: str, code: str, name: str) -> pd.Series | None:
    cand = up[(up.school_code == school) & (up.program_code == code)]
    if cand.empty:
        cand = up[(up.school_code == school) & (up.name_vi.map(fold) == fold(name))]
    if cand.empty:
        return None
    if len(cand) > 1:
        fn = set(fold(name).split())
        cand = cand.assign(sim=cand.name_vi.map(lambda n: len(fn & set(fold(n).split())))).sort_values("sim", ascending=False)
    return cand.iloc[0]


def build() -> dict:
    ensure_dirs()
    scope = yaml.safe_load((CONFIG / "scope.yaml").read_text(encoding="utf-8"))
    city_of = {code: city for city, codes in scope["candidates"].items() for code in codes}
    cut = pd.read_csv(PROCESSED / "cutoffs.csv", dtype={"program_code": str, "key_code": str}, keep_default_na=False)
    cut["score"] = cut.score.astype(float)
    cut["scale"] = cut.scale.astype(int)
    dmeta = pd.read_csv(PROCESSED / "distributions_meta.csv")
    prov = {(r.combo, int(r.year)): r.provenance for r in dmeta.itertuples(index=False)}
    exam = exam_combos()
    all_parts = combo_parts()
    up = _unipilot_programs()
    schools_src = table("school").set_index("id")

    latest30 = cut[(cut.year == LATEST) & (cut.scale == 30) & cut.school_code.isin(city_of)]
    per_school = latest30.groupby("school_code").size()
    keep_schools = per_school[per_school >= scope["min_programs_2026"]].sort_values(ascending=False).index[: scope["max_schools"]]
    dropped = sorted(set(city_of) - set(keep_schools))

    programs, reasons = [], []
    for r in latest30[latest30.school_code.isin(keep_schools)].itertuples(index=False):
        u = _pick_unipilot(up, r.school_code, r.program_code, r.program_name)
        combos = split_combos(u.combos_thpt) if u is not None and u.combos_thpt else []
        hist_combos = cut[(cut.school_code == r.school_code) & (cut.key_code == r.key_code)].combos
        for c in hist_combos:
            combos += [x for x in split_combos(c) if x not in combos]
        exam_ok = [c for c in combos if c in exam]
        if combos and not exam_ok:
            reasons.append(dict(school_code=r.school_code, key_code=r.key_code, reason="only talent-test / unknown combos: " + ";".join(combos)))
            continue
        ref = sorted(exam_ok, key=lambda c: PROVENANCE_RANK.get(prov.get((c, LATEST), "year_shift"), 9))
        ref = [c for c in ref if (c, LATEST) in prov]
        if not ref:
            reasons.append(dict(school_code=r.school_code, key_code=r.key_code, reason="no score distribution for any combo"))
            continue
        major_code = (u.major_code if u is not None else "") or (r.program_code if re.fullmatch(r"7\d{6}", r.program_code or "") else "")
        name = r.program_name
        kind = program_kind(name, u.program_kind if u is not None else "")
        field = field_of(name, major_code)
        hist = cut[(cut.school_code == r.school_code) & (cut.key_code == r.key_code) & (cut.scale == 30)].sort_values("year")
        tuition = [parse_tuition(t) for t in hist.tuition_raw[::-1] if t]
        tmin, tmax, tunit = next(((a, b, u_) for a, b, u_ in tuition if a), (None, None, ""))
        school = schools_src.loc[r.school_code] if r.school_code in schools_src.index else None
        programs.append(dict(
            program_id=f"{r.school_code}:{r.key_code}",
            school_code=r.school_code,
            school_name=clean(school.name_vi) if school is not None else r.school_code,
            city=city_of[r.school_code],
            campus=campus_of(name) or "",
            program_code=r.program_code,
            program_name=name,
            major_code=major_code,
            field=field or "",
            field_name=FIELDS.get(field or "", ""),
            kind=kind,
            combos=";".join(exam_ok),
            reference_combo=ref[0],
            reference_provenance=prov[(ref[0], LATEST)],
            quota_2026=int(u.quota) if u is not None and str(u.quota).isdigit() else None,
            tuition_min=tmin, tuition_max=tmax, tuition_unit=tunit,
            conditions=" | ".join(conditions_of(name, kind, field, major_code)),
            years_with_cutoff=int(hist.year.nunique()),
            cutoff_2026=float(r.score),
            status_2026=r.status,
            source_url=r.url,
        ))
    prog = pd.DataFrame(programs)
    # the same program sometimes appears under two codes (e.g. '7520207AT' and '7520207_AT'):
    # same school + same name + same latest cutoff -> keep the one with the longest history
    prog["_name"] = prog.program_name.map(fold)
    prog = prog.sort_values("years_with_cutoff", ascending=False).drop_duplicates(["school_code", "_name", "cutoff_2026"]).drop(columns="_name")
    prog = prog.sort_values(["school_code", "program_id"]).reset_index(drop=True)
    # tuition fallback: school median of per-year prices, marked as imputed
    per_year = prog[prog.tuition_unit == "per_year"]
    med = per_year.groupby("school_code").tuition_min.median()
    prog["tuition_imputed"] = prog.tuition_min.isna() | (prog.tuition_unit != "per_year")
    fill = prog.school_code.map(med)
    prog.loc[prog.tuition_imputed, "tuition_min"] = fill[prog.tuition_imputed]
    prog.loc[prog.tuition_imputed, "tuition_max"] = fill[prog.tuition_imputed]

    history = cut[cut.scale == 30].merge(prog[["program_id", "school_code", "program_code"]].assign(key_code=prog.program_id.str.split(":", n=1).str[1]),
                                          on=["school_code", "key_code"], how="inner", suffixes=("", "_p"))
    history = history[["program_id", "year", "score", "status", "chosen_source", "score_vnexpress", "score_vietnamnet", "score_tuyensinh247", "n_sources", "method_evidence", "several_rows", "url"]]

    schools = []
    for code in keep_schools:
        s = schools_src.loc[code] if code in schools_src.index else None
        sp = prog[prog.school_code == code]
        schools.append(dict(school_code=code, name=clean(s.name_vi) if s is not None else code, city=city_of[code],
                            short_name=clean(s.short_name) if s is not None else "", website=clean(s.website) if s is not None else "",
                            address=clean(s.address) if s is not None else "", n_programs=len(sp),
                            median_tuition=float(sp.tuition_min.median()) if sp.tuition_min.notna().any() else None))
    pd.DataFrame(schools).to_csv(PROCESSED / "schools.csv", index=False, encoding="utf-8")
    prog.to_csv(PROCESSED / "programs.csv", index=False, encoding="utf-8")
    history.to_csv(PROCESSED / "history.csv", index=False, encoding="utf-8")
    pd.DataFrame(reasons).to_csv(PROCESSED / "programs_excluded.csv", index=False, encoding="utf-8")
    pd.DataFrame({"school_code": dropped}).assign(reason="fewer than min usable 30-point THPT cutoffs in the latest year (e.g. switched to a 100-point combined scale) or not found").to_csv(
        PROCESSED / "schools_excluded.csv", index=False, encoding="utf-8")
    return {
        "schools": len(schools), "schools_by_city": pd.DataFrame(schools).city.value_counts().to_dict(),
        "schools_excluded": dropped, "programs": len(prog), "programs_excluded": len(reasons),
        "history_rows": len(history), "years_with_cutoff": prog.years_with_cutoff.value_counts().sort_index().to_dict(),
        "reference_provenance": prog.reference_provenance.value_counts().to_dict(),
        "tuition_imputed": int(prog.tuition_imputed.sum()), "field_missing": int((prog.field == "").sum()),
        "_unused": len(all_parts),
    }
