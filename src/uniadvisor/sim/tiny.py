"""A tiny simulated world for tests: 3 schools, 12 programs, cutoffs 2022-2026, 5 combinations.

Small enough to check by hand, and it covers what the advisor branches on: two cities, every program kind,
ministry floors (medicine, nursing, teacher training), an English-taught program, a program with one year
of history, a disputed latest cutoff, fees that are simulated, estimated (school median) or missing, and MOET
major codes that are observed, estimated (matched by name) or missing. The majors table is MOET's real catalog.

    from uniadvisor.sim import tiny
    db = tiny.build()                 # in memory
    db = tiny.build(out=tmp_path)     # also written to a folder
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from uniadvisor import db as database
from uniadvisor.build import majors as moet
from uniadvisor.engine.dist import GRID, mean_of, quantile

VERSION = 2  # 2: MOET majors and major-code provenance
YEARS = (2022, 2023, 2024, 2025, 2026)

SCHOOLS = [
    ("SIM-HN1", "Trường Đại học Mô phỏng Kỹ thuật", "SIMTECH", "Hà Nội"),
    ("SIM-HN2", "Trường Đại học Mô phỏng Kinh tế", "SIMECON", "Hà Nội"),
    ("SIM-HC1", "Trường Đại học Mô phỏng Y - Sư phạm", "SIMMED", "TP. Hồ Chí Minh"),
]
COMBOS = {"A00": ("TO", "LI", "HO"), "A01": ("TO", "LI", "N1"), "B00": ("TO", "HO", "SI"),
          "C00": ("VA", "SU", "DI"), "D01": ("TO", "VA", "N1")}
# program_id, name, major_code, field, kind, combos, reference combo, cutoff level 2026, fee (million VND/year or None),
# conditions
PROGRAMS = [
    ("SIM-HN1:IT", "Công nghệ thông tin", "7480201", "cntt", "standard", "A00;A01", "A00", 25.5, 30, ""),
    ("SIM-HN1:EE", "Kỹ thuật điện tử - viễn thông", "7520207", "ky_thuat", "standard", "A00;A01", "A00", 23.0, 30, ""),
    ("SIM-HN1:CS-EN", "Khoa học máy tính (chương trình tiên tiến, học bằng tiếng Anh)", "7480101", "cntt", "advanced",
     "A01;D01", "A01", 26.5, 60, "Học bằng tiếng Anh (thường cần trình độ tiếng Anh tốt, có thể yêu cầu IELTS/chứng chỉ khi nhập học)"),
    ("SIM-HN1:CE", "Kỹ thuật xây dựng", "7580201", "xay_dung", "standard", "A00;A01", "A00", 19.0, None, ""),
    ("SIM-HN2:ECO", "Kinh tế", "7310101", "kinh_te", "standard", "A00;A01;D01", "D01", 24.0, 25, ""),
    ("SIM-HN2:FIN", "Tài chính - Ngân hàng", "7340201", "tai_chinh", "high_quality", "A00;D01", "D01", 25.0, 45, ""),
    ("SIM-HN2:MKT", "Marketing", "7340115", "kinh_te", "standard", "A01;D01", "D01", 26.0, None, ""),
    ("SIM-HN2:ENG", "Ngôn ngữ Anh (liên kết quốc tế)", "7220201", "ngon_ngu", "international", "D01", "D01", 22.0, 120,
     "Học bằng tiếng Anh (thường cần trình độ tiếng Anh tốt, có thể yêu cầu IELTS/chứng chỉ khi nhập học) | "
     "Chương trình liên kết/quốc tế: học phí cao hơn chương trình chuẩn"),
    ("SIM-HC1:MD", "Y khoa", "7720101", "y_duoc", "standard", "B00", "B00", 26.0, 70, "Khối sức khỏe: có ngưỡng điểm sàn của Bộ"),
    ("SIM-HC1:NUR", "Điều dưỡng", "7720301", "y_duoc", "standard", "B00", "B00", 19.0, 30, "Khối sức khỏe: có ngưỡng điểm sàn của Bộ"),
    ("SIM-HC1:EDU-MATH", "Sư phạm Toán học", "7140209", "su_pham", "standard", "A00;A01", "A00", 25.0, None,
     "Sư phạm: không nhận thí sinh bị dị hình, dị tật, nói ngọng, nói lắp; điểm sàn của Bộ"),
    ("SIM-HC1:EDU-LIT", "Sư phạm Ngữ văn", "7140217", "su_pham", "standard", "C00;D01", "C00", 26.5, None,
     "Sư phạm: không nhận thí sinh bị dị hình, dị tật, nói ngọng, nói lắp; điểm sàn của Bộ"),
]
NEW_PROGRAM = "SIM-HN2:MKT"        # only one year of cutoffs
DISPUTED = "SIM-HN1:EE"            # sources disagree on the latest cutoff
NO_FEE_SCHOOL = "SIM-HC1"
CODE_ESTIMATED = "SIM-HN2:MKT"     # its MOET code was matched by name
NO_CODE = "SIM-HC1:EDU-LIT"        # no MOET code: its field comes from name keywords          # its two teacher-training programs have no fee and no school median: missing
# combination -> (mean, sd) of the 3-subject total; the same every year (a stable exam)
SCORE_SHAPE = {"A00": (20.5, 3.6), "A01": (20.0, 3.7), "B00": (19.5, 3.8), "C00": (19.0, 4.0), "D01": (19.8, 3.9)}


def _cdf(mu: float, sd: float) -> np.ndarray:
    f = (norm.cdf((GRID - mu) / sd) - norm.cdf(-mu / sd)) / (norm.cdf((30 - mu) / sd) - norm.cdf(-mu / sd))
    f = np.clip(f, 0, 1)
    f[-1] = 1.0
    return f


def tables(seed: int = 0) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict]:
    rng = np.random.default_rng(seed)
    schools = pd.DataFrame([dict(school_code=c, name=n, short_name=s, city=city, website="", address="")
                            for c, n, s, city in SCHOOLS])
    programs = pd.DataFrame([dict(program_id=pid, school_code=pid.split(":")[0], program_code=pid.split(":")[1], name=name,
                                  major_code="" if pid == NO_CODE else major,
                                  major_code_provenance="" if pid == NO_CODE else "estimated" if pid == CODE_ESTIMATED else "observed",
                                  major_code_method="moet_name" if pid == CODE_ESTIMATED else "",
                                  field=field, field_method="name_keywords" if pid == NO_CODE else "major_code",
                                  kind=kind, campus="", combos=combos, reference_combo=ref, conditions=cond, source_url="")
                             for pid, name, major, field, kind, combos, ref, _, _, cond in PROGRAMS])
    cut = []
    for pid, *_, level, _fee, _cond in PROGRAMS:
        years = YEARS[-1:] if pid == NEW_PROGRAM else YEARS
        # a random walk that ends at the 2026 level: walk backwards with steps of about 1 point
        steps = rng.normal(0.3, 1.0, len(years) - 1)
        scores = level - np.concatenate([[0.0], np.cumsum(steps[::-1])])[::-1]
        for y, s in zip(years, scores):
            disputed = pid == DISPUTED and y == YEARS[-1]
            cut.append(dict(program_id=pid, year=y, combo="", score=round(float(np.clip(s, 15, 29.5)), 2),
                            status="disputed" if disputed else "confirmed_2_sources", n_sources=2,
                            lowest_of_several=False, provenance="simulated", source="uniadvisor.sim.tiny", url=""))
    quotas = pd.DataFrame([dict(program_id=pid, year=YEARS[-1], quota=int(rng.integers(5, 30)) * 10, provenance="simulated",
                                source="uniadvisor.sim.tiny") for pid, *_ in PROGRAMS])
    fees = [dict(program_id=pid, year=YEARS[-1], min_vnd=fee * 1e6, max_vnd=fee * 1e6, provenance="simulated", method="",
                 source="uniadvisor.sim.tiny") for pid, *_, fee, _cond in PROGRAMS if fee is not None]
    known = pd.DataFrame(fees).assign(school=lambda d: d.program_id.str.split(":").str[0])
    med = known.groupby("school").min_vnd.median()
    for pid, *_, fee, _cond in PROGRAMS:
        school = pid.split(":")[0]
        if fee is None and school in med.index and school != NO_FEE_SCHOOL:   # the same rule as the real build
            fees.append(dict(program_id=pid, year=YEARS[-1], min_vnd=med[school], max_vnd=med[school], provenance="estimated",
                             method="school_median", source=""))
    combos = pd.DataFrame([dict(combo=c, subject_1=s[0], subject_2=s[1], subject_3=s[2]) for c, s in COMBOS.items()])
    rows, meta = [], []
    for combo, (mu, sd) in SCORE_SHAPE.items():
        for y in YEARS:
            f = _cdf(mu, sd)
            rows.append([combo, y, *f])
            meta.append(dict(combo=combo, year=y, method="simulated", provenance="simulated", n=200_000,
                             note=f"truncated normal mean {mu} sd {sd}", mean=round(mean_of(f), 2),
                             p50=round(float(quantile(f, .5)), 2), p75=round(float(quantile(f, .75)), 2),
                             p90=round(float(quantile(f, .9)), 2)))
    cdfs = pd.DataFrame(rows, columns=["combo", "year", *[f"g{i}" for i in range(len(GRID))]])
    manifest = {"kind": "simulated", "name": "tiny", "latest_year": YEARS[-1],
                "description": "3 schools, 12 programs, cutoffs 2022-2026: a hand-sized world for tests",
                "generator": {"name": "uniadvisor.sim.tiny", "version": VERSION, "seed": seed}}
    t = {"schools": schools, "programs": programs, "cutoffs": pd.DataFrame(cut), "quotas": quotas,
         "tuition": pd.DataFrame(fees), "combos": combos, "distributions": pd.DataFrame(meta),
         "majors": moet.catalog().assign(provenance="observed")}
    return t, cdfs, manifest


def build(out: Path | str | None = None, seed: int = 0) -> database.Database:
    t, cdfs, manifest = tables(seed)
    return database.write(out, t, cdfs, manifest) if out else database.from_tables(t, cdfs, manifest)
