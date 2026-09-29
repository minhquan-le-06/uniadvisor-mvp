"""tuyensinh247 cutoff pages (trust 4, aggregator): the latest year's THPT cutoffs, used as a third
source to cross-check the two news sources. The page embeds its records as JSON:
{"code": "BF1", "name": ..., "block": "A00; B00", "mark": 24.56, "year": 2026, "admission_alias": "diem-thi-thpt", ...}
Older years are only reachable through an endpoint robots.txt disallows (/tsBenchmarking/ajaxGetMore),
so they are not collected.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Iterator

from uniadvisor.fetch import PoliteClient
from uniadvisor.paths import MANUAL, UNIPILOT_OUT
from uniadvisor.text import clean, split_combos

SOURCE = "tuyensinh247_cutoffs"
RECORD = re.compile(r'\{"id":\d+,"school_id":\d+,"code":.*?"admission_alias":"[^"]*"')


def school_pages(codes: list[str]) -> dict[str, str]:
    """code -> cutoff page URL: data/manual/tuyensinh247_pages.csv, else derived from the school-info
    URLs a local UniPilotData database already downloaded."""
    saved = MANUAL / "tuyensinh247_pages.csv"
    if saved.exists():
        with open(saved, encoding="utf-8") as f:
            rows = [line.strip().split(",", 1) for line in f.readlines()[1:] if line.strip()]
        found = {c: u for c, u in rows if c in codes}
        if found:
            return found
    db = UNIPILOT_OUT.parent / "data" / "unipilot.db"
    if not db.exists():
        return {}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    out = {}
    for (url,) in con.execute("select distinct url from downloaded_file where url like '%diemthi.tuyensinh247.com/thong-tin-%'"):
        m = re.search(r"/thong-tin-([a-z0-9-]+)-([A-Za-z0-9]+)\.html$", url)
        if m and m.group(2).upper() in codes:
            out[m.group(2).upper()] = f"https://diemthi.tuyensinh247.com/diem-chuan/{m.group(1)}-{m.group(2)}.html"
    con.close()
    return out


def parse(html: str) -> Iterator[dict]:
    text = html.replace('\\"', '"')
    seen = set()
    for m in RECORD.finditer(text):
        try:
            rec = json.loads(m.group(0) + "}")
        except json.JSONDecodeError:
            continue
        key = (rec.get("code"), rec.get("name"), rec.get("mark"), rec.get("admission_alias"))
        if key in seen:
            continue
        seen.add(key)
        yield rec


def school_rows(client: PoliteClient, code: str, url: str) -> Iterator[dict]:
    r = client.get(url)
    if r.status != 200:
        return
    for rec in parse(r.text):
        if rec.get("admission_alias") != "diem-thi-thpt":
            continue
        yield {"source": SOURCE, "school_code": code, "year": int(rec.get("year") or 0), "program_code": clean(rec.get("code")),
               "program_name": clean(rec.get("name")), "combos": ";".join(split_combos(rec.get("block"))),
               "score_raw": str(rec.get("mark")), "url": r.url, "fetched_at": r.fetched_at}
