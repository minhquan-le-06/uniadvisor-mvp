"""End-to-end advice: profile -> ordered application list with probabilities and explanations.

Division of labour (MVP.md 'core principle'):
  KB (kb/rules.py)            eligibility, priority points, floors, buckets, list constraints
  engine (engine/*)           cutoff forecast, uncertainty, P(admit)
  SLM (slm/infer.py)          soft judgments only: risk tolerance, priority, interest/ability fit,
                              budget / location / special-condition fit from free text
  optimizer / compare         list selection and ordering, criteria and trade-offs
Same input -> same output for everything except the SLM, which is itself deterministic at inference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd

from uniadvisor import compare, explain
from uniadvisor.engine.dist import default_distributions
from uniadvisor.engine.forecast import ForecastParams, admit_probability, forecast_program
from uniadvisor.kb import rules
from uniadvisor.optimizer import Item, expected_value, optimise, p_any
from uniadvisor.paths import PROCESSED
from uniadvisor.slm.infer import Answer, HeuristicJudge, focus, get_judge
from uniadvisor.slm.questions import BY_ID, PROFILE_QUESTIONS, PROGRAM_QUESTIONS
from uniadvisor.slm.state import StudentProfile

MOCK_SCORE_SD = 1.2        # points on the 3-subject total when the scores are mock-exam estimates
MIN_P = 0.10               # candidates below this are not offered automatically
MAX_SLM_CANDIDATES = 120   # programs sent to the SLM after cheap pre-ranking


@lru_cache(maxsize=1)
def catalog() -> tuple[pd.DataFrame, dict[str, dict[int, float]]]:
    prog = pd.read_csv(PROCESSED / "programs.csv", dtype={"program_code": str, "major_code": str})
    prog = prog.astype(object).where(prog.notna(), None)
    hist = pd.read_csv(PROCESSED / "history.csv")
    h = {pid: dict(zip(g.year.astype(int), g.score.astype(float))) for pid, g in hist.groupby("program_id")}
    return prog, h


@dataclass
class Advice:
    profile: StudentProfile
    ruleset: str
    target_year: int
    profile_answers: dict[str, Answer]
    clarify: list[dict]                   # questions to ask the student (low-confidence answers)
    weights: dict[str, float]
    constraints: dict
    chosen: list[dict]
    alternatives: list[dict]
    n_eligible: int
    n_candidates: int
    p_any: float
    expected_value: float
    summary: str
    judge: str
    notes: list[str] = field(default_factory=list)

    def table(self, rows: list[dict] | None = None) -> pd.DataFrame:
        rows = self.chosen if rows is None else rows
        return pd.DataFrame([{
            "NV": i + 1, "Mã": r["program"]["program_id"], "Trường": r["program"]["school_name"],
            "Ngành": r["program"]["program_name"], "Tổ hợp": r["combo"], "Điểm xét": r["total"],
            "Dự báo điểm chuẩn": r["forecast"].score, "P(đỗ)": round(r["p_admit"], 3), "Nhóm": rules.BUCKET_VI[r["bucket"]],
            **{compare.CRITERIA[k]: round(v, 2) for k, v in r["criteria"].items()},
            "Độ phù hợp (u)": round(r["utility"], 3), "Độ tin cậy": r["confidence"],
        } for i, r in enumerate(rows)])


def _clarifications(answers: dict[str, Answer]) -> list[dict]:
    out = []
    for qid, a in answers.items():
        if a.escalate and a.source != "student":
            q = BY_ID[qid]
            out.append({"question_id": qid, "ask": q.clarify_vi, "options": dict(zip(q.labels, q.labels_vi)),
                        "model_guess": a.label, "confidence": round(a.confidence, 2)})
    return out


def advise(profile: StudentProfile, target_year: int = 2027, ruleset: str = rules.DEFAULT_RULESET,
           k_max: int | None = None, weights_override: dict[str, float] | None = None, judge=None) -> Advice:  # noqa: ANN001
    judge = judge or get_judge()
    prog, hist = catalog()
    dists = default_distributions()
    params = ForecastParams.load()
    notes = []

    # 1. profile-level soft judgments
    pa = dict(zip([q.id for q in PROFILE_QUESTIONS], judge.answer([(q.id, focus(profile, q.id), None) for q in PROFILE_QUESTIONS])))
    risk = pa["risk_tolerance"].label if not pa["risk_tolerance"].escalate else None
    prio = pa["top_priority"].label if not pa["top_priority"].escalate else None
    cons = rules.list_constraints(risk, ruleset)
    k = min(k_max or cons["target_size"], cons["max_choices"])
    weights = compare.weights_for(prio, weights_override, risk)
    if prio == "viec_lam_thu_nhap":
        notes.append("Chưa có dữ liệu việc làm/thu nhập theo ngành trong MVP; tạm dùng độ cạnh tranh của ngành làm đại diện.")

    # 2. deterministic part: eligibility, forecast, probability
    sd = MOCK_SCORE_SD if profile.score_kind == "mock" else 0.0
    evals = []
    n_eligible = 0
    for p in prog.to_dict("records"):
        el = rules.eligibility(p, profile.scores, profile.area, profile.category, profile.years_since_graduation, profile.gender, ruleset)
        if not el.eligible:
            continue
        n_eligible += 1
        fc = forecast_program(p["program_id"], p["reference_combo"], hist.get(p["program_id"], {}), target_year, dists, params)
        if fc is None:
            continue
        pr = admit_probability(fc, el.total, sd)
        if pr < MIN_P:
            continue
        evals.append({"program": p, "combo": el.combo, "raw_total": el.raw_total, "priority": el.priority, "total": el.total,
                      "forecast": fc, "cutoff_interval": fc.interval(0.8), "p_admit": pr, "bucket": rules.risk_bucket(pr, ruleset)})
    if not evals:
        return Advice(profile, ruleset, target_year, pa, _clarifications(pa), weights, cons, [], [], n_eligible, 0, 0.0, 0.0,
                      "Không tìm thấy ngành nào trong phạm vi dữ liệu có xác suất đỗ đủ cao với tổ hợp và điểm hiện tại.",
                      getattr(judge, "name", "?"), notes)

    # 3. cheap pre-ranking (keyword judge) so the SLM only sees a manageable set. Each of reach / match / safe
    # keeps its own share: ranking everything together favours the many easy programs and would drop every
    # reach program before the optimizer sees it. Admission probability is not part of the key (the optimizer
    # weighs it); selectivity is, so the better programs within a bucket come first.
    focused = {q.id: focus(profile, q.id) for q in PROGRAM_QUESTIONS}
    if len(evals) > MAX_SLM_CANDIDATES:
        pre = HeuristicJudge()
        keys = []
        for ev in evals:
            a = pre.answer([("interest_fit", focused["interest_fit"], ev["program"]), ("location_ok", focused["location_ok"], ev["program"])])
            sel = compare.criteria(ev["program"], ev["forecast"].score, {}, None)["selectivity"]
            keys.append((a[0].expected_level() or 3) / 5 + 0.5 * a[1].p("yes") + 0.2 * sel)
        ranked = list(np.argsort(keys, kind="stable")[::-1])
        keep: list[int] = []
        for bucket in ("reach", "match", "safe"):
            keep += [i for i in ranked if evals[i]["bucket"] == bucket][: MAX_SLM_CANDIDATES // 3]
        keep += [i for i in ranked if i not in set(keep)][: MAX_SLM_CANDIDATES - len(keep)]
        evals = [evals[i] for i in sorted(keep)]

    # 4. soft judgments per program
    items = [(q.id, focused[q.id], ev["program"]) for ev in evals for q in PROGRAM_QUESTIONS]
    answers = judge.answer(items)
    nq = len(PROGRAM_QUESTIONS)
    fees = [ev["program"].get("tuition_min") for ev in evals]
    known = sorted(f for f in fees if f)
    for i, ev in enumerate(evals):
        ev["answers"] = {q.id: answers[i * nq + j] for j, q in enumerate(PROGRAM_QUESTIONS)}
        f = ev["program"].get("tuition_min")
        rank = (np.searchsorted(known, f) / max(1, len(known) - 1)) if f and known else None
        ev["criteria"] = compare.criteria(ev["program"], ev["forecast"].score, ev["answers"], rank)
        ev["utility"] = compare.utility(ev["criteria"], weights, ev["answers"]["conditions_ok"], ev["answers"]["location_ok"])

    # 5. choose and order
    # "unlikely" programs are never recommended automatically (rules: risk_buckets); they stay in alternatives
    cand = [Item(ev["program"]["program_id"], ev["p_admit"], ev["utility"], ev["bucket"] == "safe", ev["program"]["school_code"],
                 ev["forecast"].score or 0.0)
            for ev in evals if ev["bucket"] != "unlikely"]
    picked = optimise(cand, k_max=k, min_safe=cons["min_safe"], max_per_school=4)
    by_key = {ev["program"]["program_id"]: ev for ev in evals}
    chosen = [by_key[it.key] for it in picked]
    chosen_keys = {c["program"]["program_id"] for c in chosen}
    alternatives = sorted((ev for ev in evals if ev["program"]["program_id"] not in chosen_keys),
                          key=lambda ev: ev["p_admit"] * ev["utility"], reverse=True)[:10]

    # 6. explanations
    others = [ev["criteria"] for ev in chosen]
    for ev in chosen + alternatives:
        ev["wins"], ev["losses"] = compare.wins_losses(ev["criteria"], [o for o in others if o is not ev["criteria"]])
        esc = [BY_ID[q].text_vi for q, a in ev["answers"].items() if a.escalate]
        flags = []
        if ev["answers"]["conditions_ok"].p("no") > 0.5:
            flags.append("có thể không đáp ứng điều kiện riêng: " + str(ev["program"].get("conditions")))
        if ev["program"].get("campus"):
            flags.append(f"học tại {ev['program']['campus']}")
        if ev["program"].get("status_2026") == "disputed":
            flags.append("hai nguồn công bố điểm chuẩn 2026 khác nhau")
        ev["flags"] = flags
        ev["confidence"], ev["confidence_reasons"] = explain.confidence_label(
            ev["forecast"].n_years, ev["program"].get("status_2026") or "", len(esc), bool(ev["program"].get("tuition_imputed")))
        ev["uncertain_judgments"] = esc
        ev["explanation"] = explain.program_explanation(ev)
    pa_ = p_any(picked)
    summary = explain.list_summary(chosen, pa_, expected_value(picked), cons["min_safe"], profile.score_kind)
    return Advice(profile, ruleset, target_year, pa, _clarifications(pa), weights, cons, chosen, alternatives, n_eligible,
                  len(evals), pa_, expected_value(picked), summary, getattr(judge, "name", "?"), notes)
