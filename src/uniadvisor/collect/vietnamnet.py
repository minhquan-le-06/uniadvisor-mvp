"""VietNamNet cutoff lookup (trust 3). One API call per school x year x page.

The API mixes every admission method in one list; the method is only in a free-text `note`.
We store every row as-is here. build/cutoffs.py decides which rows are THPT-exam cutoffs.
"""

from __future__ import annotations

from typing import Iterator

from uniadvisor.fetch import PoliteClient
from uniadvisor.text import clean

SOURCE = "vietnamnet_cutoffs"
API = "https://vietnamnet.vn/newsapi-edu/UniversityDetail/GetDetail"
PAGE_ID = "49ff289efde0446f9ae2f5c385595744"
COMPONENT_ID = "COMPONENT002302"
PAGE_SIZE = 25


def _page(client: PoliteClient, code: str, year: int, page: int) -> tuple[dict, str, str]:
    params = dict(pageId=PAGE_ID, componentId=COMPONENT_ID, keyword=code, year=year,
                  pageSize=PAGE_SIZE, pageIndex=page, typeOfTraining=0, subjectGroup="")
    r = client.get(API, params=params)
    if r.status != 200:
        return {}, r.url, r.fetched_at
    return (r.json().get("data") or {}).get("model") or {}, r.url, r.fetched_at


def school_year_rows(client: PoliteClient, code: str, year: int) -> Iterator[dict]:
    model, url, fetched_at = _page(client, code, year, 0)
    schools = model.get("universitySchool") or []
    match = next((s for s in schools if (s.get("code") or "").upper() == code.upper()), None)
    if match is None:
        return
    pages = int(model.get("totalPage") or 1)
    models = [(model, url, fetched_at)]
    for p in range(1, pages):
        models.append(_page(client, code, year, p))
    seen: set[tuple] = set()
    for m, u, f in models:
        for row in m.get("schoolScores") or []:
            key = (row.get("code"), row.get("name"), row.get("score"), row.get("subjectGroup"), row.get("note"))
            if key in seen:
                continue
            seen.add(key)
            yield {
                "source": SOURCE,
                "school_code": code.upper(),
                "school_name_src": clean(match.get("name")),
                "province_src": clean(match.get("provinceName")),
                "year": year,
                "program_code": clean(row.get("code")),
                "program_name": clean(row.get("name")),
                "score_raw": clean(row.get("score")),
                "combos_raw": clean(row.get("subjectGroup")),
                "note": clean(row.get("note")),
                "training_type": row.get("typeOfTraining"),
                "url": u,
                "fetched_at": f,
            }
