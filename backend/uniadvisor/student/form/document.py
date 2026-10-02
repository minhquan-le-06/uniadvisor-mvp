"""The student's answers -> the JSON module 3 receives (docs/STUDENT_SCHEMA.md), and the checks that JSON must pass.

`Answers` holds what the guided chat collected, every field optional; `build` turns it into the document, filling
the defaults listed in `assumed`; `problems` checks a document against every rule of the schema (module 3 can call
it on what it receives). Nothing here stores anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from uniadvisor.student.form.options import (
    AREAS, CATEGORIES, FIRST_GRADUATION_YEAR, GENDERS, LANGUAGES, MAX_INTERESTS, MAX_PRIORITIES, NEAREST_CITY,
    NOTICES, PRIORITIES, PROVINCES, REQUIRED_SUBJECTS, RISKS, SCHEMA_VERSION, STRENGTHS, SUBJECTS, default_ruleset,
    target_year,
)
from uniadvisor.student.form.picker import Picker
from uniadvisor.student.form.scores import ScoreEntry, on_step

KEYS = ("meta", "profile", "interests", "dislikes", "family", "budget", "location", "risk", "priorities", "assumed")
ANYWHERE = "anywhere"
NEAR_HOME = "near_home"


@dataclass
class Answers:
    """What the student answered. None / empty = not answered (skipped or "Em không biết")."""

    scores: list[ScoreEntry] = field(default_factory=list)   # Toán, Văn and 2 electives
    scores_official: bool = False      # the student says these are their official exam scores
    gender: str | None = None
    province: str | None = None
    area: str | None = None
    category: str | None = None
    graduation_year: int | None = None
    interests: list[tuple[str, str]] = field(default_factory=list)   # (code, strength)
    dislikes: list[str] = field(default_factory=list)
    family_codes: list[str] = field(default_factory=list)
    family_agrees: bool | None = None
    budget_kind: str | None = None     # None | "amount" | "no_limit"
    budget_million: float | None = None
    budget_strict: bool = False
    location: str | None = None        # None | a city | NEAR_HOME | ANYWHERE
    main_campus_only: bool = False
    risk: str | None = None
    priorities: list[str] = field(default_factory=list)

    def score_problems(self) -> list[str]:
        """Why the scores cannot be used yet (Vietnamese, shown to the student); empty when they can."""
        out = []
        subjects = [e.subject for e in self.scores]
        if len(self.scores) != 4 or subjects[:2] != list(REQUIRED_SUBJECTS) or len(set(subjects)) != 4:
            out.append("Em cần nhập điểm Toán, Văn và 2 môn tự chọn khác nhau.")
        elif sum(s in LANGUAGES for s in subjects) > 1:
            out.append("Em chỉ thi một môn ngoại ngữ thôi.")
        return out + [p for e in self.scores if (p := e.problem())]

    def missing(self) -> list[str]:
        """Required answers still missing or invalid (Vietnamese, shown to the student)."""
        out = self.score_problems()
        if self.gender not in GENDERS:
            out.append("Em cho mình biết giới tính nhé.")
        return out


def build(a: Answers, p: Picker, year: int | None = None, ruleset: str | None = None) -> tuple[dict, list[str]]:
    """(the JSON document, the notices to show the student about defaults). Raises ValueError if a required answer
    is missing (`Answers.missing`)."""
    if missing := a.missing():
        raise ValueError("; ".join(missing))
    year = year or target_year()
    assumed: list[dict] = []

    def default(path: str, value):  # noqa: ANN001, ANN202
        assumed.append({"field": path, "value": value, "reason": "not_given"})
        return value

    exact = all(e.mode == "exact" for e in a.scores)
    profile = {
        "scores": {e.subject: e.score() for e in a.scores},
        "score_kind": "actual" if exact and a.scores_official else "mock",
        "province": a.province if a.province in PROVINCES else None,
        "area": a.area if a.area in AREAS else default("profile.area", "KV3"),
        "category": a.category if a.category in CATEGORIES else default("profile.category", "none"),
        "gender": a.gender,
        "graduation_year": a.graduation_year if a.graduation_year else default("profile.graduation_year", year),
    }

    interests, seen = [], set()
    for code, strength in a.interests:
        if code not in seen and len(interests) < MAX_INTERESTS:
            interests.append({"code": code, "strength": strength})
            seen.add(code)
    dislikes = [{"code": c} for c in dict.fromkeys(a.dislikes) if c not in seen]
    family = ({"codes": list(dict.fromkeys(a.family_codes)), "student_agrees": a.family_agrees}
              if a.family_codes else None)

    budget = None
    if a.budget_kind == "no_limit":
        budget = {"max_million_per_year": None, "strict": False}
    elif a.budget_kind == "amount" and a.budget_million and a.budget_million > 0:
        budget = {"max_million_per_year": float(a.budget_million), "strict": bool(a.budget_strict)}

    location = None
    if a.location or a.main_campus_only:
        if a.location in p.cities:
            cities = [a.location]
        elif a.location == NEAR_HOME and NEAREST_CITY.get(profile["province"]) in p.cities:
            cities = [NEAREST_CITY[profile["province"]]]
        else:                           # "Ở đâu cũng được", or only "chỉ cơ sở chính" ticked
            cities = list(p.cities)
        location = {"cities": cities, "main_campus_only": bool(a.main_campus_only)}

    doc = {
        "meta": {"schema_version": SCHEMA_VERSION, "target_year": year, "ruleset": ruleset or default_ruleset()},
        "profile": profile,
        "interests": interests,
        "dislikes": dislikes,
        "family": family,
        "budget": budget,
        "location": location,
        "risk": a.risk if a.risk in RISKS else None,
        "priorities": list(dict.fromkeys(x for x in a.priorities if x in PRIORITIES))[:MAX_PRIORITIES],
        "assumed": assumed,
    }
    return doc, [NOTICES[x["field"]] for x in assumed]


def problems(doc: dict, p: Picker | None = None) -> list[str]:
    """Every way `doc` breaks docs/STUDENT_SCHEMA.md (English, for developers). Empty = valid. With a picker, codes
    and cities are also checked against the database."""
    out: list[str] = []
    missing = [k for k in KEYS if k not in doc]
    if missing:
        return [f"missing keys: {missing}"]
    if extra := sorted(set(doc) - set(KEYS)):
        out.append(f"unknown keys: {extra}")

    meta = doc["meta"] or {}
    if meta.get("schema_version") != SCHEMA_VERSION:
        out.append("meta.schema_version must be 1")
    year = meta.get("target_year")
    if not isinstance(year, int):
        out.append("meta.target_year must be an integer")
        year = 9999
    if not isinstance(meta.get("ruleset"), str) or not meta.get("ruleset"):
        out.append("meta.ruleset must be a non-empty string")

    pr = doc["profile"] or {}
    scores = pr.get("scores") or {}
    keys = list(scores)
    if len(keys) != 4 or not set(REQUIRED_SUBJECTS) <= set(keys) or not set(keys) <= set(SUBJECTS):
        out.append(f"profile.scores must have TO, VA and 2 different electives, got {keys}")
    if sum(k in LANGUAGES for k in keys) > 1:
        out.append("profile.scores: at most one foreign language")
    for k, v in scores.items():
        if not isinstance(v, (int, float)) or not 0 <= v <= 10 or (k in SUBJECTS and not on_step(v, k)):
            out.append(f"profile.scores.{k} = {v!r}: must be 0-10 on the subject's step")
    _enum(out, "profile.score_kind", pr.get("score_kind"), ("actual", "mock"))
    _enum(out, "profile.province", pr.get("province"), PROVINCES, nullable=True)
    _enum(out, "profile.area", pr.get("area"), AREAS)
    _enum(out, "profile.category", pr.get("category"), CATEGORIES)
    _enum(out, "profile.gender", pr.get("gender"), GENDERS)
    gy = pr.get("graduation_year")
    if not isinstance(gy, int) or not FIRST_GRADUATION_YEAR <= gy <= year:
        out.append(f"profile.graduation_year = {gy!r}: must be {FIRST_GRADUATION_YEAR}..target_year")

    def code_ok(where: str, code) -> None:  # noqa: ANN001
        if not isinstance(code, str) or len(code) not in (5, 7) or not code.isdigit():
            out.append(f"{where} = {code!r}: must be a 5- or 7-digit MOET code")
        elif p is not None and not p.has(code):
            out.append(f"{where} = {code!r}: not in the picker (no program in the database)")

    interests = doc["interests"] if isinstance(doc["interests"], list) else []
    if not isinstance(doc["interests"], list) or len(interests) > MAX_INTERESTS:
        out.append(f"interests must be a list of at most {MAX_INTERESTS}")
    for i, x in enumerate(interests):
        code_ok(f"interests[{i}].code", x.get("code"))
        _enum(out, f"interests[{i}].strength", x.get("strength"), STRENGTHS)
    dislikes = doc["dislikes"] if isinstance(doc["dislikes"], list) else []
    if not isinstance(doc["dislikes"], list):
        out.append("dislikes must be a list")
    for i, x in enumerate(dislikes):
        code_ok(f"dislikes[{i}].code", x.get("code"))
    liked = [x.get("code") for x in interests]
    disliked = [x.get("code") for x in dislikes]
    if len(set(liked)) != len(liked) or len(set(disliked)) != len(disliked):
        out.append("interests and dislikes must not repeat a code")
    if both := sorted(set(liked) & set(disliked)):
        out.append(f"codes in both interests and dislikes: {both}")

    fam = doc["family"]
    if fam is not None:
        codes = fam.get("codes")
        if not isinstance(codes, list) or not codes:
            out.append("family.codes must be a non-empty list")
        for i, c in enumerate(codes or []):
            code_ok(f"family.codes[{i}]", c)
        if fam.get("student_agrees") not in (True, False, None):
            out.append("family.student_agrees must be true, false or null")

    b = doc["budget"]
    if b is not None:
        m = b.get("max_million_per_year")
        if m is not None and (not isinstance(m, (int, float)) or m <= 0):
            out.append("budget.max_million_per_year must be > 0 or null")
        if not isinstance(b.get("strict"), bool):
            out.append("budget.strict must be a boolean")
        elif m is None and b["strict"]:
            out.append("budget.strict must be false when there is no limit")

    loc = doc["location"]
    if loc is not None:
        cities = loc.get("cities")
        if not isinstance(cities, list) or not cities or len(set(cities)) != len(cities):
            out.append("location.cities must be a non-empty list without repeats")
        elif p is not None and not set(cities) <= set(p.cities):
            out.append(f"location.cities {cities}: not all in scope {list(p.cities)}")
        if not isinstance(loc.get("main_campus_only"), bool):
            out.append("location.main_campus_only must be a boolean")

    _enum(out, "risk", doc["risk"], RISKS, nullable=True)
    pri = doc["priorities"]
    if not isinstance(pri, list) or len(pri) > MAX_PRIORITIES or len(set(pri)) != len(pri):
        out.append(f"priorities must be a list of at most {MAX_PRIORITIES} without repeats")
    for i, x in enumerate(pri if isinstance(pri, list) else []):
        _enum(out, f"priorities[{i}]", x, PRIORITIES)

    if not isinstance(doc["assumed"], list):
        out.append("assumed must be a list")
    for i, x in enumerate(doc["assumed"] if isinstance(doc["assumed"], list) else []):
        if set(x) != {"field", "value", "reason"} or x.get("reason") != "not_given":
            out.append(f"assumed[{i}] must be {{field, value, reason: not_given}}")
    return out


def _enum(out: list[str], where: str, value, allowed, nullable: bool = False) -> None:  # noqa: ANN001
    if value is None and nullable:
        return
    if value not in allowed:
        out.append(f"{where} = {value!r}: must be one of {list(allowed)}{' or null' if nullable else ''}")
