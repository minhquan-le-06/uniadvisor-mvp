"""MOET's catalog of university majors (Danh mục thống kê ngành đào tạo, trình độ đại học).

Source: Thông tư 09/2022/TT-BGDĐT (06/06/2022, in force 22/07/2022), Phụ lục I. The official text is a scanned PDF
(no text layer: tulieuvankien.dangcongsan.vn), so the table is read from hoatieu.vn's transcription of the appendix,
which matched the scan row by row where checked (appendix page 2, 7140212-7140236).

The code is the taxonomy: 7 = university level; digits 1-3 = lĩnh vực (748 Máy tính và công nghệ thông tin),
1-5 = nhóm ngành (74802 Công nghệ thông tin), 1-7 = ngành (7480201 Công nghệ thông tin).
Output: data/manual/moet_majors.csv (code, level, name, parent, former_code, note, source, url).
"""

from __future__ import annotations

import html
import re

import pandas as pd

from uniadvisor.fetch import PoliteClient
from uniadvisor.paths import MANUAL

URL = "https://hoatieu.vn/phap-luat/danh-muc-cac-nganh-dao-tao-trinh-do-dai-hoc-215006"
SOURCE = "moet_tt09_2022"
OUT = MANUAL / "moet_majors.csv"
LEVELS = {3: "linh_vuc", 5: "nhom_nganh", 7: "nganh"}


def _cells(row: str) -> list[str]:
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.S)]


def parse(page: str) -> pd.DataFrame:
    """Rows of the appendix table: (code, name, effect, note) with codes of 3, 5 or 7 digits starting with 7."""
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.S):
        c = _cells(tr) + ["", "", ""]
        if re.fullmatch(r"7\d{2}(?:\d{2}){0,2}", c[0]):
            rows.append(dict(code=c[0], name=c[1], note=" ".join(x for x in c[2:4] if x)))
    df = pd.DataFrame(rows)
    df["level"] = df.code.str.len().map(LEVELS)
    df["parent"] = df.code.map(lambda c: c[: len(c) - 2] if len(c) > 3 else "")
    # renumbered majors: "Sửa mã ngành (mã cũ là 729008)", "Ngành chuyển đến ... (mã cũ là 7140207)"
    df["former_code"] = df.note.str.extract(r"mã cũ là (\d+)", expand=False).fillna("")
    # the old code of a major that moved stays listed with "Chuyển đến nhóm ngành ...": not a major of its own any more
    moved = df.code.isin(set(df.former_code) - {""})
    df = df[~moved].reset_index(drop=True)
    df["source"], df["url"] = SOURCE, URL
    return df[["code", "level", "name", "parent", "former_code", "note", "source", "url"]]


def collect(client: PoliteClient | None = None) -> pd.DataFrame:
    df = parse((client or PoliteClient()).get(URL).text)
    problems = check(df)
    if problems:
        raise ValueError("MOET catalog looks wrong: " + "; ".join(problems))
    df.to_csv(OUT, index=False, encoding="utf-8")
    return df


def check(df: pd.DataFrame) -> list[str]:
    problems = []
    if df.code.duplicated().any():
        problems.append(f"duplicate codes {df.code[df.code.duplicated()].tolist()[:5]}")
    orphans = df[(df.parent != "") & ~df.parent.isin(df.code)]
    if len(orphans):
        problems.append(f"codes without a parent level: {orphans.code.tolist()[:5]}")
    counts = df.level.value_counts().to_dict()
    if counts.get("linh_vuc", 0) < 20 or counts.get("nganh", 0) < 300:
        problems.append(f"too few rows {counts} (page layout changed?)")
    return problems
