"""The nhóm ngành -> ngành picker (interests, dislikes and family share it), and the "Gõ tên ngành em nghĩ tới" search.

Only what the database offers is listed: the nhóm ngành with at least one program and the ngành our schools teach.
A group's program count uses `covers`, so it counts exactly the programs module 3 will match to that code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from uniadvisor.student.intent import covers
from unidata.db import Database, get_db
from unidata.text import fold


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

    @property
    def label(self) -> str:
        """What the dropdown shows; the lĩnh vực is part of it so the dropdown's search finds it."""
        return f"{self.name} ({self.n_programs} ngành) · {self.field_name}"


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
        """The name to show; MOET's "Khác" groups (code xxx90: the leftover majors of a lĩnh vực) say whose."""
        item = self._by_code.get(code)
        if isinstance(item, Group) and item.name == "Khác":
            return f"Khác thuộc lĩnh vực {item.field_name}"
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
    groups = []
    for code, g in c.groupby("moet_group_code", sort=True):
        majors = tuple(Major(str(mc), str(m.major_name.iloc[0]), len(m)) for mc, m in g.groupby("major_code", sort=True))
        n = sum(covers(str(code), mc) for mc in codes)
        if n == 0:          # every program of the group is filed under another field; reachable by its ngành
            n = len(g)
        groups.append(Group(str(code), str(g.moet_group.iloc[0]), str(g.moet_field_code.iloc[0]),
                            str(g.moet_field.iloc[0]), n, majors))
    groups.sort(key=lambda x: (x.field_code, x.code))
    cities = tuple(sorted(db.catalog.city.dropna().unique(), key=fold))
    return Picker(tuple(groups), cities)


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
    if len(q) >= 2:
        pattern = re.compile(rf"\b{re.escape(q)}\b")
        for g in p.groups:
            if pattern.search(fold(g.name)):
                add(g.code)
        for g in p.groups:
            for m in g.majors:
                if pattern.search(fold(m.name)):
                    add(m.code)
    return out[:limit]
