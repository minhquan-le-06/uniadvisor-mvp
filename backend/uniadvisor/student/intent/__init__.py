"""Module 2: what a student wants, read once from their text as facts they can see and correct.

Every fact keeps the sentence it came from, so the app can show "Mình hiểu là ..." with the student's own words and
ask about a fact once instead of judging it again for every program. A fact the text does not state is None.

Areas of study are MOET codes (data/manual/moet_majors.csv): normally a nhóm ngành (5 digits); a ngành (7) where its
nhóm ngành also holds things the student did not mean; a lĩnh vực (3) for something that broad. `covers` says which
programs a code takes in. The reader is `uniadvisor.student.intent.keywords.extract`; `uniadvisor.student.intent.evaluate` scores
it fact by fact against synthetic students whose true facts are known.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Fact:
    value: Any
    evidence: str            # the student's sentence it was read from


@dataclass(frozen=True)
class Interest:
    codes: tuple[str, ...]   # MOET codes
    evidence: str
    implied: bool = False    # read from a hobby ("hay tự viết code") rather than a stated wish


@dataclass
class StudentIntent:
    interests: list[Interest] = field(default_factory=list)
    dislikes: list[Interest] = field(default_factory=list)
    family: Interest | None = None            # what the family wants the student to study
    family_agrees: bool | None = None         # whether the student goes along with it
    budget: Fact | None = None                # VND per year (float), or "poor" / "rich" when no number is given
    location: Fact | None = None              # city:<name> | near_home | anywhere | no_big_city
    avoid_branch: Fact | None = None          # True: only the main campus
    risk: Fact | None = None                  # an_toan | can_bang | mao_hiem
    priority: Fact | None = None              # nganh_yeu_thich | truong_danh_tieng | hoc_phi_thap | gan_nha | viec_lam_thu_nhap
    english: Fact | None = None               # good | weak | ielts
    speech_issue: Fact | None = None          # True: a speech difficulty (matters for sư phạm)
    strong: dict[str, str] = field(default_factory=dict)   # subject code -> sentence
    weak: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def codes(self, which: str = "interests") -> set[str]:
        return {c for i in getattr(self, which) for c in i.codes}


def covers(code: str, major_code: str | None) -> bool:
    """Whether the area `code` takes in a program with this MOET major code: the code is a prefix of it, and
    data/config/fields.yaml does not move the program to another field (744 Khoa học tự nhiên does not take in 7440112
    Hóa học, which the app files under sinh_hoa)."""
    from unidata.build.fields import field_of_code

    major_code = (major_code or "").strip()
    if not major_code.startswith(code):
        return False
    own = field_of_code(code)
    return own is None or field_of_code(major_code) == own


def extract(text: str) -> StudentIntent:
    from uniadvisor.student.intent.keywords import extract as keyword_extract

    return keyword_extract(text)
