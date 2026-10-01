"""MOET's catalog of majors (data/manual/moet_majors.csv, from collect/moet.py) and matching programs to it.

Schools list programs under their own codes (BKA "IT1", NEU "7340101_CLC"...); about a third of ours carry no
MOET code. `match_name` finds the MOET ngành whose official name the program name starts with, after removing
what schools add around it (programme type, language, campus, specialisation). Its accuracy is measured on the
programs that do have a code (`evaluate`); matched codes are stored as estimates.
"""

from __future__ import annotations

import re
from functools import lru_cache

import pandas as pd

from unidata.paths import MANUAL
from unidata.text import fold

# words schools put around the official name; removed before matching (on the folded name, whole words).
# Never a bare word that also starts real names: "tai" (tại = at) is also "tài chính", "he" (hệ) is "hệ thống".
_NOISE = (
    r"\(.*?\)", r"\[.*?\]", r"\*",
    r"\bchuong trinh (?:dao tao )?(?:tien tien|chat luong cao|clc|chuan|dac biet|lien ket|quoc te|tai nang|ky su|"
    r"cu nhan|dinh huong nghe nghiep|dinh huong ung dung|nghien cuu)\b", r"\b(?:ct|cttt|ctdt|clc|nganh)\b",
    r"\bchat luong cao\b", r"\btien tien\b", r"\b(?:hoc|day) bang tieng (?:anh|phap|nhat|trung|han|duc)\b",
    r"\blien ket(?: quoc te)?\b", r"\bsong bang\b", r"[,;-]? ?\bchuyen nganh\b.*$", r"\bphan hieu\b.*$",
)
# Vietnamese writes some words with i or y ("quản lí" / "quản lý", "kĩ" / "kỹ", "mĩ" / "mỹ")
_IY = {"li": "ly", "ki": "ky", "mi": "my"}


def name_key(s: str) -> str:
    """A program or ngành name reduced to what identifies the major (folded, school additions removed)."""
    t = fold(s)
    for pattern in _NOISE:
        t = re.sub(pattern, " ", t)
    words = re.sub(r"[^a-z0-9]+", " ", t).split()
    return " ".join(_IY.get(w, w) for w in words)


@lru_cache(maxsize=1)
def catalog() -> pd.DataFrame:
    return pd.read_csv(MANUAL / "moet_majors.csv", dtype=str, keep_default_na=False)


@lru_cache(maxsize=1)
def _majors() -> dict[str, str]:
    """normalised official ngành name -> code (names shared by two codes are left out: ambiguous)."""
    m = catalog()
    m = m[m.level == "nganh"].assign(key=lambda d: d.name.map(name_key))
    m = m[~m.key.duplicated(keep=False)]
    return dict(zip(m.key, m.code))


def current_code(code: str) -> str:
    """A renumbered major's former code -> its current code (Thông tư 09/2022 renumbered five)."""
    m = catalog()
    former = dict(zip(m.former_code, m.code))
    return former.get(code, code)


def match_name(name: str) -> str | None:
    """The MOET code whose official ngành name equals the program's name once the school's additions are removed
    (programme type, language of instruction, specialisation, campus), or None. Only exact matches: on programs
    with a known code they were right 99.6% of the time, "starts with an official name" only 41%."""
    key = name_key(name)
    return _majors().get(key) if key else None


def evaluate(programs: pd.DataFrame) -> dict:
    """Accuracy of match_name on programs whose MOET code is known (columns name, major_code)."""
    known = programs[programs.major_code.fillna("").str.fullmatch(r"7\d{6}")]
    hits = [(match_name(n), current_code(c)) for n, c in zip(known.name, known.major_code)]
    hits = [(m, c) for m, c in hits if m]
    return {"programs_with_code": len(known), "matched": len(hits),
            "same_major": round(sum(m == c for m, c in hits) / max(1, len(hits)), 4),
            "same_group": round(sum(m[:5] == c[:5] for m, c in hits) / max(1, len(hits)), 4),
            "wrong": sorted({(m, c) for m, c in hits if m != c})}
