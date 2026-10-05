"""The nhóm ngành -> ngành picker (interests, dislikes and family share it), and the "Gõ tên ngành em nghĩ tới" search.

Only what the database offers is listed: the nhóm ngành with at least one program and the ngành our schools teach.
A group's program count uses `covers`, so it counts exactly the programs module 3 will match to that code.

What students see for a group is its label in backend/config/group_labels.csv when it has one (MOET's names often
hide what students and the media call a field: KHMT and AI sit in "Máy tính", Khoa học dữ liệu in "Toán học"), else
MOET's name; MOET's name stays shown beside it. Display only: codes, the student JSON and the database are unchanged.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field

from uniadvisor.student.intent import covers
from unidata.db import Database, get_db
from unidata.paths import BACKEND_CONFIG
from unidata.text import fold

LABELS = BACKEND_CONFIG / "group_labels.csv"


@dataclass(frozen=True)
class Major:
    code: str            # 7-digit MOET ngành
    name: str
    n_programs: int


@dataclass(frozen=True)
class Group:
    code: str            # 5-digit MOET nhóm ngành
    name: str
    field_code: str      # 3-digit lĩnh vực
    field_name: str
    n_programs: int
    majors: tuple[Major, ...]
    display: str = ""            # what students see (group_labels.csv); "" = the MOET name
    aliases: tuple[str, ...] = ()

    @property
    def moet_name(self) -> str:
        """MOET's name; its "Khác" groups (code xxx90: the leftover majors of a lĩnh vực) say whose."""
        return f"Khác thuộc lĩnh vực {self.field_name}" if self.name == "Khác" else self.name

    @property
    def shown(self) -> str:
        return self.display or self.moet_name

    @property
    def label(self) -> str:
        """What the dropdown shows; MOET's name and the lĩnh vực are part of it so the dropdown's search finds them."""
        moet = f" · nhóm {self.moet_name}" if self.display else ""
        return f"{self.shown} ({self.n_programs} ngành){moet} · {self.field_name}"

    def caption(self, n: int = 3) -> str:
        """The grey line under a suggestion: MOET's name when the label differs, then the majors the label does not
        already name, most-taught first."""
        best = sorted(self.majors, key=lambda m: (-m.n_programs, m.code))
        rest = [m for m in best if fold(m.name) not in fold(self.display)] if self.display else best
        parts = [f"Tên nhóm ngành của Bộ GD&ĐT: {self.moet_name}"] if self.display else []
        if rest:
            more = f" và {len(rest) - n} ngành khác" if len(rest) > n else ""
            parts.append(("Còn có" if self.display else "Gồm") + ": " + ", ".join(m.name for m in rest[:n]) + more)
        return " · ".join(parts)

    def examples(self, n: int = 3) -> str:
        """The n majors taught by the most programs (ties: lower code), e.g. Marketing before Quản trị - Luật."""
        best = sorted(self.majors, key=lambda m: (-m.n_programs, m.code))
        more = f" và {len(best) - n} ngành khác" if len(best) > n else ""
        return ", ".join(m.name for m in best[:n]) + more


@dataclass(frozen=True)
class Picker:
    groups: tuple[Group, ...]
    cities: tuple[str, ...]
    _by_code: dict = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        for g in self.groups:
            self._by_code[g.code] = g
            for m in g.majors:
                self._by_code[m.code] = m

    def has(self, code: str) -> bool:
        return code in self._by_code

    def group(self, code: str) -> Group:
        """The group a code is or belongs to."""
        return self._by_code[code[:5]]

    def name(self, code: str) -> str:
        """The name to show: a group's label (group_labels.csv) or MOET's name; a ngành's MOET name."""
        item = self._by_code.get(code)
        if isinstance(item, Group):
            return item.shown
        return item.name if item else code

    def moet_name(self, code: str) -> str:
        """MOET's own name, for showing beside the label and for documents that must use it."""
        item = self._by_code.get(code)
        if isinstance(item, Group):
            return item.moet_name
        return item.name if item else code


_CACHE: list[tuple[Database, Picker]] = []


def picker(db: Database | None = None) -> Picker:
    db = db or get_db()
    for d, p in _CACHE:
        if d is db:
            return p
    p = _build(db)
    _CACHE[:] = [(db, p)]
    return p


def _build(db: Database) -> Picker:
    c = db.catalog
    c = c[c.major_code.notna() & c.moet_group_code.notna()]
    codes = c.major_code.astype(str).tolist()
    labels = _labels()
    groups = []
    for code, g in c.groupby("moet_group_code", sort=True):
        majors = tuple(Major(str(mc), str(m.major_name.iloc[0]), len(m)) for mc, m in g.groupby("major_code", sort=True))
        n = sum(covers(str(code), mc) for mc in codes)
        if n == 0:          # every program of the group is filed under another field; reachable by its ngành
            n = len(g)
        label, aliases = labels.get(str(code), ("", ()))
        groups.append(Group(str(code), str(g.moet_group.iloc[0]), str(g.moet_field_code.iloc[0]),
                            str(g.moet_field.iloc[0]), n, majors, label, aliases))
    groups.sort(key=lambda x: (x.field_code, x.code))
    cities = tuple(sorted(db.catalog.city.dropna().unique(), key=fold))
    return Picker(tuple(groups), cities)


def _labels() -> dict[str, tuple[str, tuple[str, ...]]]:
    """group code -> (label, aliases) from group_labels.csv; {} without the file."""
    if not LABELS.exists():
        return {}
    with open(LABELS, encoding="utf-8") as f:
        return {r["group_code"]: (r["label"].strip(), tuple(a.strip() for a in r["aliases"].split(";") if a.strip()))
                for r in csv.DictReader(f)}


def search(query: str, p: Picker | None = None, limit: int = 8) -> list[str]:
    """Picker codes for what the student typed ("IT", "bác sĩ", "kế toán"): the interest keywords first (they know
    students' words), then group and ngành names that contain the typed words."""
    from uniadvisor.student.intent.keywords import _match, _norm, _tokens, lexicon

    p = p or picker()
    query = (query or "").strip()
    if not query:
        return []
    out: list[str] = []

    def add(code: str) -> None:
        if code not in out:
            out.append(code)

    # "học" in front lets the words that count only after a verb ("IT", "y", "luật") match alone
    for _, term in _match(_tokens(_norm(f"học {query}")), lexicon()[1]):
        for code in term.codes:
            if len(code) == 3:
                for g in p.groups:
                    if g.field_code == code:
                        add(g.code)
            elif p.has(code):
                add(code)
            elif p.has(code[:5]):
                add(code[:5])
    q = fold(query)
    for g in p.groups:                   # abbreviations and media terms (KHMT, AI, logistics) of group_labels.csv
        if any(fold(a) == q for a in g.aliases):
            add(g.code)
    if len(q) >= 2:
        pattern = re.compile(rf"\b{re.escape(q)}\b")
        for g in p.groups:
            if pattern.search(fold(g.moet_name)) or pattern.search(fold(g.display)) \
                    or any(pattern.search(fold(a)) for a in g.aliases):
                add(g.code)
        for g in p.groups:
            for m in g.majors:
                if pattern.search(fold(m.name)):
                    add(m.code)
    return out[:limit]
