"""Simulated students for testing the recommendation engine (module 3) without depending on module 2.

Each student has what the intake form gives (scores, province, priority area and group, gender, real or mock
scores), the free text a student would write, and `intent`: the facts that text states, taken from the
generator's hidden attributes. Feeding `intent` to the engine is an oracle module 2, so engine tests measure
the engine alone; feeding `free_text` through the real reader measures both.

Scores are drawn from the real 2026 per-subject histograms (slm/synth.py ScoreSampler). Priority area and
group are drawn per province (big cities are mostly KV3). Written to data/sim/<name>/ (git-ignored) with a
manifest naming the generator and seed; ids start with SIM-.

    uniadvisor sim students --n 5000 --seed 0        # data/sim/students-0/students.jsonl
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from unidata.db.schema import SIM_PREFIX
from uniadvisor.student.intent.evaluate import truth
from uniadvisor.student.slm.synth import ProfileGenerator

VERSION = 1
CITIES = {"Hà Nội", "TP. Hồ Chí Minh", "Hải Phòng", "Đà Nẵng", "Cần Thơ", "Huế"}
AREA_WEIGHTS = {  # (KV3, KV2, KV2-NT, KV1)
    "city": (0.7, 0.2, 0.1, 0.0),
    "province": (0.0, 0.35, 0.4, 0.25),
}
AREAS = ("KV3", "KV2", "KV2-NT", "KV1")
CATEGORIES = (("none", 0.95), ("UT2", 0.04), ("UT1", 0.01))


def _jsonable(v):  # noqa: ANN001, ANN202
    return sorted(v) if isinstance(v, set) else v


def generate(n: int, seed: int = 0) -> list[dict]:
    gen = ProfileGenerator(seed)
    rng = random.Random(seed + 7)  # its own stream: the texts match ProfileGenerator(seed) exactly
    out = []
    for i in range(n):
        z = gen.latent()
        text = gen.text(z)
        kind = "city" if z.province in CITIES else "province"
        area = rng.choices(AREAS, weights=AREA_WEIGHTS[kind])[0]
        category = rng.choices([c for c, _ in CATEGORIES], weights=[w for _, w in CATEGORIES])[0]
        t = truth(z)
        out.append({
            "student_id": f"{SIM_PREFIX}S{i:05d}", "scores": z.scores, "score_kind": z.score_kind,
            "province": z.province, "region": z.region, "area": area, "category": category, "gender": z.gender,
            "free_text": text, "voice": z.voice,
            "intent": {k: _jsonable(v) for k, v in t.items() if k != "implied"},
            "interest_fields": [f for f, _ in z.interests],
        })
    return out


def write(students: list[dict], out: Path, seed: int) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "students.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for s in students:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    totals = [sum(sorted(s["scores"].values(), reverse=True)[:3]) for s in students]
    manifest = {
        "kind": "simulated", "what": "students",
        "generator": {"name": "uniadvisor.student.simulated", "version": VERSION, "seed": seed},
        "count": len(students),
        "area": dict(Counter(s["area"] for s in students)),
        "score_kind": dict(Counter(s["score_kind"] for s in students)),
        "best_three_subjects_total": {q: round(sorted(totals)[int(q * (len(totals) - 1))], 2) for q in (0.1, 0.5, 0.9)},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return out


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in open(path / "students.jsonl", encoding="utf-8")]


def profile(student: dict):  # noqa: ANN201
    """The StudentProfile the intake form would produce for a simulated student."""
    from uniadvisor.student.slm.state import StudentProfile

    return StudentProfile(scores=student["scores"], province=student["province"], area=student["area"],
                          category=student["category"], gender=student["gender"], score_kind=student["score_kind"],
                          free_text=student["free_text"])


class OracleJudge:
    """A module 2 that is always right: answers the typed questions from a simulated student's true facts
    (matched by free text), so engine tests measure module 3 alone. ability_fit follows the keyword rules, which
    work on the scores. Same rubric as slm/teacher.py, without the simulated annotators' slips."""

    name = "oracle"

    def __init__(self, students: list[dict]):
        from uniadvisor.student.slm.infer import HeuristicJudge

        self.by_text = {s["free_text"]: s for s in students}
        self.rules = HeuristicJudge()

    def answer(self, items: list) -> list:
        return [self._one(q, p, prog) for q, p, prog in items]

    def _one(self, qid: str, profile, program: dict | None):  # noqa: ANN001, ANN202
        from uniadvisor.student.slm.infer import Answer
        from uniadvisor.student.slm.questions import BY_ID, INSUFFICIENT

        s = self.by_text.get(profile.free_text)
        if s is None:
            raise KeyError("OracleJudge: not a simulated student (free text not found)")
        if qid == "ability_fit":
            return self.rules.answer([(qid, profile, program)])[0]
        label = getattr(self, qid)(s, s["intent"], program or {}) or INSUFFICIENT
        probs = {lab: float(lab == label) for lab in BY_ID[qid].all_labels}
        return Answer(qid, probs, label, 1.0, label == INSUFFICIENT, self.name)

    # one method per question: the label, or None when the facts do not decide it
    @staticmethod
    def risk_tolerance(s: dict, t: dict, p: dict) -> str | None:
        return t["risk"]

    @staticmethod
    def top_priority(s: dict, t: dict, p: dict) -> str | None:
        return t["priority"]

    @staticmethod
    def interest_fit(s: dict, t: dict, p: dict) -> str | None:
        from unidata.build.fields import field_of_code
        from uniadvisor.student.intent import covers

        code, field = p.get("major_code") or "", p.get("field") or ""

        def takes(codes: list[str]) -> bool:
            return any(covers(c, code) if code else field_of_code(c) == field for c in codes)

        if takes(t["dislikes"]):
            return "1"
        if takes(t["interests"]):
            return "5"
        if code and any(code[:3] == c[:3] for c in t["interests"]):
            return "4"                                   # same MOET lĩnh vực as a stated interest
        if t["family"] and takes(t["family"]):
            return "3" if t["family_agrees"] else "2"
        if t["interests"]:
            return "2"
        return "3" if (t["dislikes"] or t["family"]) else None

    @staticmethod
    def budget_ok(s: dict, t: dict, p: dict) -> str | None:
        tmin, tmax, b = p.get("tuition_min"), p.get("tuition_max"), t["budget"]
        if b is None or tmin is None or tmin != tmin:
            return None
        if b == "rich":
            return "yes"
        limit = 15e6 if b == "poor" else float(b)
        return "yes" if tmax <= limit else "no"

    @staticmethod
    def location_ok(s: dict, t: dict, p: dict) -> str | None:
        from uniadvisor.student.slm.synth import HUB_OF_REGION

        campus = p.get("campus")
        branch = isinstance(campus, str) and campus.strip() != ""
        loc = t["location"]
        if t["avoid_branch"] and branch:
            return "no"
        if loc is None:
            return None
        if loc == "anywhere":
            return "yes"
        if loc == "no_big_city":
            return "no"
        want = loc.split(":", 1)[1] if loc.startswith("city:") else HUB_OF_REGION.get(s["region"])
        if want is None:
            return None
        return "yes" if p.get("city") == want and not branch else "no"

    @staticmethod
    def conditions_ok(s: dict, t: dict, p: dict) -> str | None:
        cond = str(p.get("conditions") or "").lower()
        if not cond or cond == "nan":
            return "yes"
        verdicts = []
        if "tiếng anh" in cond:
            en = s["scores"].get("N1")
            if t["english"] in ("good", "ielts") or (en is not None and en >= 7.0):
                verdicts.append("yes")
            elif t["english"] == "weak" or (en is not None and en < 5.0):
                verdicts.append("no")
            else:
                verdicts.append(None if en is None else "yes")
        if "sư phạm" in cond:
            verdicts.append("no" if t["speech_issue"] else "yes")
        if "chỉ tuyển thí sinh nam" in cond or "chỉ tuyển thí sinh nữ" in cond:
            need = "nam" if "thí sinh nam" in cond else "nu"
            verdicts.append(None if s["gender"] is None else ("yes" if s["gender"] == need else "no"))
        if "học tại" in cond:
            verdicts.append("no" if t["avoid_branch"] else "yes")
        if "no" in verdicts:
            return "no"
        return None if None in verdicts else "yes"
