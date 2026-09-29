"""HTTP API.  uvicorn uniadvisor.api:app --reload

POST /advise          profile -> ordered list, probabilities, explanations, clarifying questions
GET  /programs        in-scope programs (filter by school / field / city)
GET  /programs/{id}   one program with its cutoff history and sources
GET  /health          data + model status
Nothing is stored: requests are processed in memory only (Decree 13/2023: no personal data is kept
without explicit consent).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from uniadvisor import __version__
from uniadvisor.advisor import advise, catalog
from uniadvisor.explain import DISCLAIMER
from uniadvisor.kb.rules import DEFAULT_RULESET, load_rules
from uniadvisor.slm.infer import get_judge
from uniadvisor.slm.state import StudentProfile

app = FastAPI(title="UniAdvisor", version=__version__, description="Tư vấn đặt nguyện vọng xét tuyển đại học bằng điểm thi THPT")


class ProfileIn(BaseModel):
    scores: dict[str, Annotated[float, Field(ge=0, le=10)]] = Field(..., min_length=1, examples=[{"TO": 8.4, "VA": 7.0, "LI": 8.0, "N1": 8.2}],
                                                                    description="subject code -> score 0..10")
    province: str | None = None
    area: str = Field("KV3", pattern="^(KV1|KV2-NT|KV2|KV3)$")
    category: str = Field("none", pattern="^(none|UT1|UT2)$")
    gender: str | None = Field(None, pattern="^(nam|nu)$")
    score_kind: str = Field("actual", pattern="^(actual|mock)$")
    free_text: str = ""
    years_since_graduation: int = 0
    answers: dict[str, str] = Field(default_factory=dict, description="answers to clarifying questions, question_id -> label")
    k: int | None = Field(None, ge=1, le=15, description="number of wishes to return")
    weights: dict[str, float] | None = None


def _program_out(ev: dict) -> dict:
    p = ev["program"]
    fc = ev["forecast"]
    return {
        "program_id": p["program_id"], "school_code": p["school_code"], "school_name": p["school_name"],
        "program_name": p["program_name"], "city": p["city"], "combo": ev["combo"], "total": ev["total"],
        "forecast_cutoff": fc.score, "cutoff_interval_80": ev["cutoff_interval"], "history": dict(zip(fc.years, fc.past_scores)),
        "p_admit": round(ev["p_admit"], 4), "bucket": ev["bucket"], "criteria": {k: round(v, 3) for k, v in ev["criteria"].items()},
        "utility": round(ev["utility"], 4), "confidence": ev["confidence"], "confidence_reasons": ev["confidence_reasons"],
        "soft_judgments": {q: {"label": a.label, "confidence": round(a.confidence, 3), "source": a.source, "uncertain": a.escalate}
                           for q, a in ev["answers"].items()},
        "explanation": ev["explanation"], "flags": ev["flags"],
        "tuition_vnd_per_year": [p.get("tuition_min"), p.get("tuition_max")], "tuition_estimated": bool(p.get("tuition_imputed")),
        "source_url": p.get("source_url"),
    }


@app.post("/advise")
def post_advise(body: ProfileIn) -> dict:
    profile = StudentProfile(**body.model_dump(exclude={"k", "weights"}))
    a = advise(profile, k_max=body.k, weights_override=body.weights)
    return {
        "ruleset": a.ruleset, "target_year": a.target_year, "judge": a.judge,
        "profile_judgments": {q: {"label": x.label, "confidence": round(x.confidence, 3), "source": x.source} for q, x in a.profile_answers.items()},
        "clarifying_questions": a.clarify, "weights": a.weights, "constraints": a.constraints,
        "list": [_program_out(ev) for ev in a.chosen], "alternatives": [_program_out(ev) for ev in a.alternatives],
        "p_admitted_somewhere": round(a.p_any, 4), "expected_utility": round(a.expected_value, 4),
        "summary": a.summary, "notes": a.notes, "disclaimer": DISCLAIMER,
    }


@app.get("/programs")
def get_programs(school: str | None = None, field: str | None = None, city: str | None = None, limit: int = 200) -> list[dict]:
    prog, _ = catalog()
    df = prog
    if school:
        df = df[df.school_code == school.upper()]
    if field:
        df = df[df.field == field]
    if city:
        df = df[df.city == city]
    return df.head(limit).to_dict("records")


@app.get("/programs/{program_id}")
def get_program(program_id: str) -> dict:
    prog, hist = catalog()
    row = prog[prog.program_id == program_id]
    if row.empty:
        raise HTTPException(404, "unknown program")
    return {**row.iloc[0].to_dict(), "history": hist.get(program_id, {})}


@app.get("/health")
def health() -> dict:
    prog, _ = catalog()
    r = load_rules(DEFAULT_RULESET)
    return {"version": __version__, "programs": len(prog), "schools": int(prog.school_code.nunique()),
            "ruleset": r["ruleset"], "ruleset_status": r.get("status"), "judge": get_judge().name}
