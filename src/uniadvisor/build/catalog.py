"""In-scope schools and programs -> the database (data/db/, schema in db/schema.py).

A program is in scope when its school is in config/scope.yaml, it has a THPT cutoff on the 30-point
scale in the latest year (so a forecast is possible), and at least one exam-only combination.
Reads the build intermediates in artifacts/build/ (cutoff consensus, distributions) and the UniPilotData
export; writes what was left out to artifacts/build/ too.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import yaml

from uniadvisor.build.fields import FIELDS, field_of
from uniadvisor.build.unipilot import exam_combos, table
from uniadvisor import db as database
from uniadvisor.engine.dist import METHOD_PROVENANCE, METHOD_RANK
from uniadvisor.paths import BUILD, CONFIG, DB, ensure_dirs
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
        cand = cand.assign(sim=cand.name_vi.map(lambda n: len(fn & set(fold(n).split())))).sort_values("sim", ascending=False, kind="stable")
    return cand.iloc[0]


# words shared by many unrelated program names; ignored when comparing two names
_GENERIC = set("nganh chuong trinh ky thuat cong nghe khoa hoc quan tri va cua clc chat luong cao tien tien dai tra "
               "chuan tieng ngon ngu lien ket quoc te dac biet tai ha noi tp hcm co so phan hieu".split())
REUSE_JUMP = 2.5  # points


def _name_tokens(name: str) -> set[str]:
    toks = set(re.sub(r"[^a-z0-9 ]", " ", fold(name)).split())
    return (toks - _GENERIC) or toks


def same_name(a: str, b: str) -> bool:
    """Loose match: at least half of the shorter name's distinctive words appear in the other one."""
    ta, tb = _name_tokens(a), _name_tokens(b)
    return not ta or not tb or len(ta & tb) >= 0.5 * min(len(ta), len(tb))


def _drop_reused_codes(history: pd.DataFrame, current_name: dict[str, str]) -> pd.DataFrame:
    """Schools reuse program codes (XDA29: 'Quản lý xây dựng' in 2021, 'Khoa học máy tính' in 2026).
    Walking back from the latest year, the first year whose name differs from the current one AND whose
    cutoff jumps > REUSE_JUMP from the next kept year ends the history: that year and all older ones go.
    A name difference alone is not enough (one aggregate mislabels names while its scores are right)."""
    keep = []
    for pid, g in history.sort_values("year", ascending=False).groupby("program_id", sort=False):
        last = None
        for r in g.itertuples():
            if last is not None and not same_name(r.program_name, current_name[pid]) and abs(r.score - last) > REUSE_JUMP:
                break
            keep.append(r.Index)
            last = r.score
    return history.loc[sorted(keep)]


def build(out=DB) -> dict:  # noqa: ANN001
    ensure_dirs()
    scope = yaml.safe_load((CONFIG / "scope.yaml").read_text(encoding="utf-8"))
    city_of = {code: city for city, codes in scope["candidates"].items() for code in codes}
    cut = pd.read_csv(BUILD / "cutoffs_consensus.csv", dtype={"program_code": str, "key_code": str}, keep_default_na=False)
    cut["score"] = cut.score.astype(float)
    cut["scale"] = cut.scale.astype(int)
    dmeta = pd.read_csv(BUILD / "distributions.csv")
    method = {(r.combo, int(r.year)): r.method for r in dmeta.itertuples(index=False)}
    exam = exam_combos()
    up = _unipilot_programs()
    schools_src = table("school").set_index("id")

    latest30 = cut[(cut.year == LATEST) & (cut.scale == 30) & cut.school_code.isin(city_of)]
    per_school = latest30.groupby("school_code").size()
    keep_schools = per_school[per_school >= scope["min_programs_2026"]].sort_values(ascending=False, kind="stable").index[: scope["max_schools"]]
    dropped = sorted(set(city_of) - set(keep_schools))

    programs, reasons = [], []
    for r in latest30[latest30.school_code.isin(keep_schools)].itertuples(index=False):
        u = _pick_unipilot(up, r.school_code, r.program_code, r.program_name)
        combos = split_combos(u.combos_thpt) if u is not None and u.combos_thpt else []
        # combinations offered in recent years only (2018-2022 rows list combinations since dropped)
        hist_combos = cut[(cut.school_code == r.school_code) & (cut.key_code == r.key_code) & (cut.year >= min(scope["history_years"]))].combos
        for c in hist_combos:
            combos += [x for x in split_combos(c) if x not in combos]
        exam_ok = [c for c in combos if c in exam]
        if combos and not exam_ok:
            reasons.append(dict(school_code=r.school_code, key_code=r.key_code, reason="only talent-test / unknown combos: " + ";".join(combos)))
            continue
        ref = sorted(exam_ok, key=lambda c: METHOD_RANK.get(method.get((c, LATEST), "year_shift"), 9))
        ref = [c for c in ref if (c, LATEST) in method]
        if not ref:
            reasons.append(dict(school_code=r.school_code, key_code=r.key_code, reason="no score distribution for any combo"))
            continue
        major_code = (u.major_code if u is not None else "") or (r.program_code if re.fullmatch(r"7\d{6}", r.program_code or "") else "")
        name = r.program_name
        kind = program_kind(name, u.program_kind if u is not None else "")
        field = field_of(name, major_code)
        hist = cut[(cut.school_code == r.school_code) & (cut.key_code == r.key_code) & (cut.scale == 30)].sort_values("year")
        fees = [(y, *parse_tuition(t)) for y, t in zip(hist.year[::-1], hist.tuition_raw[::-1]) if t]
        fee_year, tmin, tmax, tunit = next(((y, a, b, u_) for y, a, b, u_ in fees if a), (None, None, None, ""))
        programs.append(dict(
            program_id=f"{r.school_code}:{r.key_code}",
            school_code=r.school_code,
            program_code=r.program_code,
            name=name,
            major_code=major_code,
            field=field or "",
            kind=kind,
            campus=campus_of(name) or "",
            combos=";".join(exam_ok),
            reference_combo=ref[0],
            conditions=" | ".join(conditions_of(name, kind, field, major_code)),
            source_url=r.url,
            # used below, not stored in the programs table
            _quota=int(u.quota) if u is not None and str(u.quota).isdigit() else None,
            _fee=(int(fee_year), tmin, tmax) if tunit == "per_year" else None,
            _years=int(hist.year.nunique()), _cutoff=float(r.score), _status=r.status,
        ))
    prog = pd.DataFrame(programs)
    # the same program sometimes appears under two codes (e.g. '7520207AT' and '7520207_AT'):
    # same school + same name + same latest cutoff -> keep the one with the longest history,
    # then the best-confirmed one; program_id breaks remaining ties so the build is reproducible
    prog["_name"] = prog.name.map(fold)
    prog["_rank"] = prog._status.map({"confirmed_2_sources": 0, "single_source": 1}).fillna(2)
    prog = (prog.sort_values(["_years", "_rank", "program_id"], ascending=[False, True, True], kind="stable")
            .drop_duplicates(["school_code", "_name", "_cutoff"]))
    prog = prog.sort_values(["school_code", "program_id"]).reset_index(drop=True)

    # cutoff history: the in-scope 30-point rows, cut where a program code was reused for another program
    history = cut[cut.scale == 30].merge(prog[["program_id", "school_code"]].assign(key_code=prog.program_id.str.split(":", n=1).str[1]),
                                          on=["school_code", "key_code"], how="inner")
    history = _drop_reused_codes(history, dict(zip(prog.program_id, prog.name)))
    cutoffs = pd.DataFrame(dict(
        program_id=history.program_id, year=history.year, combo="", score=history.score, status=history.status,
        n_sources=history.n_sources, lowest_of_several=history.several_rows, provenance="observed",
        source=history.chosen_source, url=history.url))

    # tuition: the latest per-year price a source gave; else the school's median of those, as an estimate
    observed = prog[prog._fee.notna()]
    fees = pd.DataFrame([dict(program_id=pid, year=f[0], min_vnd=f[1], max_vnd=f[2], provenance="observed", method="",
                              source="vnexpress_cutoffs") for pid, f in zip(observed.program_id, observed._fee)])
    med = fees.assign(school_code=fees.program_id.str.split(":").str[0]).groupby("school_code").min_vnd.median()
    estimated = prog[prog._fee.isna() & prog.school_code.isin(med.index)]
    fees = pd.concat([fees, pd.DataFrame(dict(program_id=estimated.program_id, year=LATEST, min_vnd=estimated.school_code.map(med),
                                              max_vnd=estimated.school_code.map(med), provenance="estimated",
                                              method="school_median", source=""))], ignore_index=True)
    quotas = prog[prog._quota.notna()]
    quotas = pd.DataFrame(dict(program_id=quotas.program_id, year=LATEST, quota=quotas._quota.astype(int),
                               provenance="observed", source="unipilot_step1"))

    schools = []
    for code in keep_schools:
        sc = schools_src.loc[code] if code in schools_src.index else None
        schools.append(dict(school_code=code, name=clean(sc.name_vi) if sc is not None else code, city=city_of[code],
                            short_name=clean(sc.short_name) if sc is not None else "", website=clean(sc.website) if sc is not None else "",
                            address=clean(sc.address) if sc is not None else ""))
    combos = pd.DataFrame([dict(combo=c, subject_1=s[0], subject_2=s[1], subject_3=s[2]) for c, s in sorted(exam.items())])
    dmeta = dmeta[dmeta.combo.isin(exam)].assign(provenance=dmeta.method.map(METHOD_PROVENANCE))
    cdfs = pd.read_parquet(BUILD / "distributions.parquet")
    cdfs = cdfs[cdfs.combo.isin(exam)]

    db = database.write(out, {
        "schools": pd.DataFrame(schools),
        "programs": prog[[c for c in prog.columns if not c.startswith("_")]],
        "cutoffs": cutoffs, "quotas": quotas, "tuition": fees, "combos": combos, "distributions": dmeta,
    }, cdfs, {"kind": "real", "name": "real", "latest_year": LATEST, "admission_year": scope["admission_year"],
              "description": f"{len(schools)} schools in {', '.join(scope['regions'])}; THPT exam-score method, 30-point scale"})
    pd.DataFrame(reasons).to_csv(BUILD / "programs_excluded.csv", index=False, encoding="utf-8")
    pd.DataFrame({"school_code": dropped}).assign(reason="fewer than min usable 30-point THPT cutoffs in the latest year (e.g. switched to a 100-point combined scale) or not found").to_csv(
        BUILD / "schools_excluded.csv", index=False, encoding="utf-8")
    cat = db.catalog
    return {
        "schools": len(schools), "schools_by_city": pd.DataFrame(schools).city.value_counts().to_dict(),
        "schools_excluded": dropped, "programs": len(cat), "programs_excluded": len(reasons),
        "cutoff_rows": len(cutoffs), "years_with_cutoff": cat.years_with_cutoff.value_counts().sort_index().to_dict(),
        "tuition": cat.tuition_provenance.value_counts().to_dict(), "field_missing": int(cat.field.isna().sum()),
    }
