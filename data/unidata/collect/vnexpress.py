"""VnExpress (trust 3): cutoffs 2025-2026 with a dedicated THPT column + tuition, and the 2026
score histograms (per subject in 0.25 steps, per combination in 1-point steps)."""

from __future__ import annotations

import json
import re
from typing import Iterator

from lxml import html as lxml_html

from unidata.fetch import PoliteClient
from unidata.text import clean, split_combos

SOURCE_CUTOFFS = "vnexpress_cutoffs"
SOURCE_DIST = "vnexpress_distributions"
BASE = "https://diemthi.vnexpress.net"
XHR = {"X-Requested-With": "XMLHttpRequest"}

# subject ids used by /tuyensinh/index/export2 -> our subject codes (same codes as UniPilotData)
SUBJECT_IDS = {1: "TO", 2: "VA", 3: "N1", 4: "LI", 5: "HO", 6: "SU", 7: "DI", 8: "SI", 9: "GD",
               10: "TI", 11: "CNCN", 12: "CNNN", 13: "GDKTPL"}
OBSERVED_COMBOS_2026 = ["A00", "A01", "A02", "B00", "B03", "B08", "C00", "C03", "C04",
                        "D01", "D03", "D04", "D07", "D08", "D09"]


def find_school_id(client: PoliteClient, code: str) -> tuple[int | None, str | None]:
    r = client.get(f"{BASE}/tra-cuu-dai-hoc/loadcollegev2", params={"input_college": code}, headers=XHR)
    if r.status != 200:
        return None, None
    try:
        frag = r.json().get("html") or ""
    except json.JSONDecodeError:
        return None, None
    for m in re.finditer(r'data-id="(\d+)"[^>]*data-name="([^"]*)"[^>]*data-text="([^"]*)"', frag):
        sid, name, text = m.groups()
        if text.split(" - ")[0].strip().upper() == code.upper():
            return int(sid), clean(lxml_html.fromstring(f"<p>{name}</p>").text_content())
    return None, None


def _cell_text(td) -> str:  # noqa: ANN001
    for br in td.xpath(".//br"):
        br.tail = "\n" + (br.tail or "")
    return td.text_content()


def parse_benchmark_table(fragment: str) -> Iterator[dict]:
    if "<table" not in fragment:
        return
    doc = lxml_html.fromstring(fragment)
    for tr in doc.xpath("//tr[contains(@class,'university__benchmark')]"):
        tds = tr.xpath("./td")
        if len(tds) < 3:
            continue
        name_el = tds[0].xpath(".//strong//a")
        code_el = tds[0].xpath(".//span[contains(@style,'display: block')]")
        combos = []
        for a in tds[1].xpath(".//a"):
            combos += split_combos(a.text_content())
        if not combos:
            combos = split_combos(tds[1].text_content())
        score = tds[2].xpath(".//span")
        yield {
            "program_name": clean(name_el[0].text_content() if name_el else tds[0].text_content()),
            "program_code": clean(code_el[0].text_content()) if code_el else "",
            "combos": ";".join(combos),
            "thpt_score_raw": clean(score[0].text_content()) if score else clean(tds[2].text_content()),
            "other_methods": clean(_cell_text(tds[3]).replace("\n", " | ")) if len(tds) > 3 else "",
            "tuition_raw": clean(tds[4].text_content()) if len(tds) > 4 else "",
        }


def school_year_rows(client: PoliteClient, code: str, vne_id: int, year: int) -> Iterator[dict]:
    url = f"{BASE}/tra-cuu-dai-hoc/loadbenchmark/id/{vne_id}/year/{year}/sortby/1/block_name/-1"
    r = client.get(url, headers=XHR)
    if r.status != 200:
        return
    try:
        fragment = r.json().get("html") or ""
    except json.JSONDecodeError:
        return
    for row in parse_benchmark_table(fragment):
        yield {"source": SOURCE_CUTOFFS, "school_code": code.upper(), "vne_id": vne_id, "year": year,
               **row, "url": r.url, "fetched_at": r.fetched_at}


def _echarts_arrays(text: str) -> tuple[list[str], list[int]]:
    cats = re.search(r"var categories = (\[[^\]]*\])", text)
    vals = re.search(r"var dataValues = (\[[^\]]*\])", text)
    if not cats or not vals:
        return [], []
    return json.loads(cats.group(1)), json.loads(vals.group(1))


def combo_histograms(client: PoliteClient, year: int = 2026) -> Iterator[dict]:
    """1-point bins: count of candidates with combo total in [k, k+1) (k=30 means exactly 30)."""
    for combo in OBSERVED_COMBOS_2026:
        r = client.get(f"{BASE}/tuyensinh/index/exporttohop", params={"score": combo, "area": "", "college": ""}, headers=XHR)
        cats, vals = _echarts_arrays(r.text)
        for c, v in zip(cats, vals):
            yield {"source": SOURCE_DIST, "combo": combo, "year": year, "bin_low": float(c), "bin_width": 1.0,
                   "count": int(v), "url": r.url, "fetched_at": r.fetched_at}


def subject_histograms(client: PoliteClient, year: int = 2026) -> Iterator[dict]:
    """0.25 steps: count of candidates with exactly that subject score."""
    for sid, subject in SUBJECT_IDS.items():
        r = client.get(f"{BASE}/tuyensinh/index/export2", params={"score": sid, "area": "", "college": ""}, headers=XHR)
        cats, vals = _echarts_arrays(r.text)
        for c, v in zip(cats, vals):
            yield {"source": SOURCE_DIST, "subject": subject, "year": year, "score": float(c), "count": int(v),
                   "url": r.url, "fetched_at": r.fetched_at}
