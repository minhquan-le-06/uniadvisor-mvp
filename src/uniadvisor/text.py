"""Small text helpers for Vietnamese."""

from __future__ import annotations

import re
import unicodedata


def fold(text: str | None) -> str:
    """Lowercase, strip diacritics (đ -> d), collapse spaces. Used for matching, never for display."""
    if not text:
        return ""
    t = unicodedata.normalize("NFD", str(text))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = t.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"\s+", " ", t).strip()


def clean(text: str | None) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(text))).strip()


def parse_score(text: str | None) -> float | None:
    """'28,69' / '28.69' / ' 29.01 ' -> float. Returns None for anything that is not a single number."""
    if text is None:
        return None
    t = clean(str(text)).replace(",", ".")
    if not re.fullmatch(r"\d{1,3}(\.\d+)?", t):
        return None
    return float(t)


def split_combos(text: str | None) -> list[str]:
    """'A00; A01, D07' -> ['A00', 'A01', 'D07'] (keeps only code-shaped tokens)."""
    if not text:
        return []
    out: list[str] = []
    for tok in re.split(r"[;,/\s]+", str(text).upper()):
        tok = tok.strip()
        if re.fullmatch(r"[A-Z][A-Z0-9]{2}", tok) and tok not in out:
            out.append(tok)
    return out
