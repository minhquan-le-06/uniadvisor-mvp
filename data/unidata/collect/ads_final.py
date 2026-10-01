"""Older THPT cutoffs (2018-2024) from the ADS_Final student project (github.com/HTNam1710/ADS_Final,
trust 4: a scraped aggregate, like tuyensinh247). It adds 2018-2022, which no news source still serves,
and a second opinion on 2023-2024, where VietNamNet is otherwise alone. The same files are copied into
github.com/mduchd/DSS_Dataset.

One CSV row per (program, combination); 'Loại điểm' is 'THPTQG' or 'THPTQG - Thang 40' (doubled subject,
40-point scale, which the cleaning step marks out of scope). Only schools in data/config/scope.yaml are kept.
"""

from __future__ import annotations

import io
from typing import Iterator

import pandas as pd

from unidata.fetch import PoliteClient
from unidata.text import clean, split_combos

SOURCE = "ads_final_cutoffs"
BASE = "https://raw.githubusercontent.com/HTNam1710/ADS_Final/main/Data/"
FILES = ("diem_chuan_2018-2023_full.csv", "Model%20Data/diemchuan2024.csv")
COLUMNS = {"Mã trường xét tuyển": "school_code", "Mã xét tuyển": "program_code", "Tên Ngành": "program_name",
           "Loại điểm": "score_type", "Tổ hợp": "combo", "Điểm chuẩn": "score_raw", "Ghi chú": "note", "Năm": "year"}


def rows(client: PoliteClient, codes: list[str]) -> Iterator[dict]:
    for name in FILES:
        r = client.get(BASE + name)
        if r.status != 200:
            raise RuntimeError(f"ADS_Final: HTTP {r.status} for {name}")
        df = pd.read_csv(io.StringIO(r.text), dtype=str, keep_default_na=False).rename(columns=COLUMNS)
        df = df[df.school_code.isin(codes) & df.score_type.str.startswith("THPTQG")]
        keys = ["school_code", "year", "program_code", "program_name", "score_raw", "note"]
        for k, g in df.groupby(keys, sort=True):
            rec = dict(zip(keys, k))
            combos = sorted({c for s in g.combo for c in split_combos(s)})
            yield {"source": SOURCE, "school_code": rec["school_code"], "year": int(rec["year"]),
                   "program_code": clean(rec["program_code"]), "program_name": clean(rec["program_name"]),
                   "combos": ";".join(combos), "score_raw": rec["score_raw"], "score_type": g.score_type.iloc[0],
                   "note": clean(rec["note"]), "url": r.url, "fetched_at": r.fetched_at}
