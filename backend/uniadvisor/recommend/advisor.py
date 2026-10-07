"""End-to-end advice: profile -> criteria-based program clusters and numeric radar data."""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from uniadvisor import explain
from uniadvisor.recommend import compare, rules
from unidata.db import Database, get_db
from uniadvisor.recommend.forecast import ForecastParams, admit_probability, forecast_program
from uniadvisor.recommend.optimizer import Item, expected_value, optimise, p_any_monte_carlo
from uniadvisor.student.slm.infer import Answer, HeuristicJudge, get_judge
from uniadvisor.student.slm.questions import BY_ID, PROFILE_QUESTIONS, PROGRAM_QUESTIONS
from uniadvisor.student.slm.state import StudentProfile

MOCK_SCORE_SD = 1.2
MIN_P = 0.10
MAX_SLM_CANDIDATES = 120


@dataclass
class Advice:
    profile: StudentProfile
    ruleset: str
    target_year: int
    profile_answers: dict[str, Answer]
    clarify: list[dict]
    weights: dict[str, float]
    constraints: dict
    # --- Cấu trúc đầu ra mới theo đặc trưng ---
    criteria_ranking: list[dict]          # 5 đặc trưng đã sắp xếp theo input người dùng
    criteria_clusters: dict               # 5 cụm, mỗi cụm gồm 6-10 ngành (chính + phụ)
    radar_benchmark: dict[str, float]     # Tọa độ ngũ giác kỳ vọng của thí sinh
    # --- Tương thích ngược ---
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
            "Dự báo điểm chuẩn": r["forecast"].score, "P(đỗ)": round(r["p_admit"], 3),
            "Nhóm": rules.BUCKET_VI[r["bucket"]],
            **{compare.CRITERIA[k]: round(v, 2) for k, v in r["criteria"].items()},
            "Độ phù hợp (u)": round(r["utility"], 3), "Độ tin cậy": r["confidence"],
        } for i, r in enumerate(rows)])

    def cluster_table(self, criterion_key: str) -> pd.DataFrame:
        """Xuất bảng danh sách 6-10 ngành theo một đặc trưng cụ thể."""
        cluster = self.criteria_clusters.get(criterion_key, {})
        programs = cluster.get("programs", [])
        return pd.DataFrame([{
            "Loại": "Chính" if r.get("is_core") else "Phụ (gần tâm)",
            "Trường": r["program"]["school_name"],
            "Ngành": r["program"]["program_name"],
            "Tổ hợp": r["combo"],
            "Điểm xét": r["total"],
            "Điểm chuẩn dự báo": r["forecast"].score,
            "P(đỗ)": round(r["p_admit"], 3),
            "Điểm đặc trưng": round(r["criteria"][criterion_key], 2),
            "Hợp năng lực": round(r["criteria"]["ability"], 2),
        } for r in programs])


def advise(profile: StudentProfile, target_year: int = 2027, ruleset: str = rules.DEFAULT_RULESET,
           k_max: int | None = None, weights_override: dict[str, float] | None = None, judge=None,
           db: Database | None = None, params: ForecastParams | None = None) -> Advice:
    judge = judge or get_judge()
    db = db or get_db()
    prog, hist, dists = db.catalog, db.history, db.distributions
    params = params or ForecastParams.load()
    notes = []

    # 1. Profile-level soft judgments & Sắp xếp thứ tự 5 đặc trưng theo input
    pa = dict(zip([q.id for q in PROFILE_QUESTIONS], judge.answer([(q.id, profile, None) for q in PROFILE_QUESTIONS])))
    risk = pa["risk_tolerance"].label if not pa["risk_tolerance"].escalate else None
    prio = pa["top_priority"].label if not pa["top_priority"].escalate else None
    cons = rules.list_constraints(risk, ruleset)
    k = min(k_max or cons["target_size"], cons["max_choices"])
    weights = compare.weights_for(prio, weights_override)
    if prio == "viec_lam_thu_nhap":
        notes.append("Chưa có dữ liệu việc làm/thu nhập theo ngành trong MVP; tạm dùng độ cạnh tranh của ngành làm đại diện.")

    # Sắp xếp thứ tự ưu tiên 5 đặc trưng cho giao diện
    criteria_ranking = compare.rank_criteria_by_user(profile, top_priority=prio)

    # 2. Lọc tất định (Rules & Eligibility) + Dự báo điểm chuẩn & Xác suất
    sd = MOCK_SCORE_SD if profile.score_kind == "mock" else 0.0
    evals = []
    n_eligible = 0
    for p in prog.to_dict("records"):
        el = rules.eligibility(p, profile.scores, profile.area, profile.category, profile.years_since_graduation, profile.gender, ruleset, db.combos)
        if not el.eligible:
            continue
        n_eligible += 1
        fc = forecast_program(p["program_id"], p["reference_combo"], hist.get(p["program_id"], {}), target_year, dists, params)
        if fc is None:
            continue
        pr = admit_probability(fc, el.total, sd)
        if pr < MIN_P:
            continue
        evals.append({
            "program": p, "combo": el.combo, "raw_total": el.raw_total, "priority": el.priority, "total": el.total,
            "forecast": fc, "cutoff_interval": fc.interval(0.8), "p_admit": pr, "bucket": rules.risk_bucket(pr, ruleset)
        })

    if not evals:
        empty_clusters = {k: {"criterion": k, "name_vi": compare.CRITERIA[k], "programs": []} for k in compare.CRITERIA}
        return Advice(profile, ruleset, target_year, pa, [], weights, cons, criteria_ranking, empty_clusters,
                      {k: 0.5 for k in compare.CRITERIA}, [], [], n_eligible, 0, 0.0, 0.0,
                      "Không tìm thấy ngành nào phù hợp với điểm số và tổ hợp hiện tại.", getattr(judge, "name", "?"), notes)

    # 3. cheap pre-ranking: Cá nhân hóa theo weights và Batching toàn bộ truy vấn
    if len(evals) > MAX_SLM_CANDIDATES:
      pre = HeuristicJudge()

      # 3.1. Batching toàn bộ câu hỏi vào 1 lần gọi duy nhất (tăng tốc gấp 10-30 lần)
      pre_query_items = [
          (q_id, profile, ev["program"])
          for ev in evals
          for q_id in ("interest_fit", "location_ok")
      ]
      pre_answers = pre.answer(pre_query_items)

      # 3.2. Tính điểm sàng lọc cá nhân hóa theo trọng số weights của học sinh
      max_budget = getattr(
          getattr(profile, "budget", None), "max_million_per_year", None
      )
      is_strict_budget = getattr(
          getattr(profile, "budget", None), "strict", False
      )

      keys = []
      for i, ev in enumerate(evals):
        ans_fit = pre_answers[i * 2]
        ans_loc = pre_answers[i * 2 + 1]

        # Chuẩn hóa các điểm thành phần sơ bộ [0, 1]
        fit_score = (ans_fit.expected_level() or 3) / 5.0
        loc_score = ans_loc.p("yes") + 0.5 * ans_loc.p("insufficient")
        sel_score = float(
            np.clip((ev["forecast"].score - 15.0) / 14.0, 0.0, 1.0)
        )

        # Đánh giá học phí sơ bộ theo ngân sách thí sinh
        p_fee = ev["program"].get("tuition_min")
        if max_budget and p_fee:
          if p_fee <= max_budget:
            tui_score = 1.0 - 0.5 * (p_fee / max_budget)
          else:
            tui_score = 0.0 if is_strict_budget else max(0.1, 1.0 - p_fee / (max_budget * 2))
        else:
          tui_score = 0.5

        # Tổng hợp điểm sàng lọc dựa trên trọng số ưu tiên của thí sinh
        composite_key = (
            weights.get("fit", 0.35) * fit_score
            + weights.get("location", 0.15) * loc_score
            + weights.get("tuition", 0.15) * tui_score
            + weights.get("selectivity", 0.20) * sel_score
            + 0.25 * ev["p_admit"]
        )

        # Phạt nặng các ngành vượt trần ngân sách nghiêm ngặt
        if is_strict_budget and max_budget and p_fee and p_fee > max_budget:
          composite_key *= 0.2

        keys.append(composite_key)

      order = np.argsort(keys)[::-1][:MAX_SLM_CANDIDATES]
      evals = [evals[i] for i in sorted(order)]

    # 4. SLM chấm điểm định tính từng ngành & tính vector criteria [0, 1]
    items = [(q.id, profile, ev["program"]) for ev in evals for q in PROGRAM_QUESTIONS]
    answers = judge.answer(items)
    nq = len(PROGRAM_QUESTIONS)
    fees = [ev["program"].get("tuition_min") for ev in evals]
    known = sorted(f for f in fees if f)
    for i, ev in enumerate(evals):
        ev["answers"] = {q.id: answers[i * nq + j] for j, q in enumerate(PROGRAM_QUESTIONS)}
        f = ev["program"].get("tuition_min")
        rank = (np.searchsorted(known, f) / max(1, len(known) - 1)) if f and known else None
        ev["criteria"] = compare.criteria(ev["program"], ev["forecast"].score, ev["answers"], rank)
        ev["utility"] = compare.utility(ev["criteria"], weights, ev["answers"]["conditions_ok"])

    # 5. Phân cụm 6-10 ngành cho từng đặc trưng (gồm 3-5 ngành chính + 3-5 ngành phụ gần tâm)
    criteria_clusters = compare.cluster_programs_by_criteria(evals, core_range=(4, 4), sec_range=(4, 4))

    # Tọa độ biểu đồ ngũ giác chuẩn (Benchmark Polygon) của thí sinh
    radar_benchmark = {k: round(float(np.clip(weights.get(k, 0.2) * 2.5, 0.2, 1.0)), 2) for k in compare.CRITERIA}

    # 6. Giữ lại danh sách tối ưu mặc định (chosen) để tương thích ngược nếu cần
    cand = [Item(ev["program"]["program_id"], ev["p_admit"], ev["utility"], ev["bucket"] == "safe", ev["program"]["school_code"])
            for ev in evals if ev["bucket"] != "unlikely"]
    picked = optimise(cand, k_max=k, min_safe=cons["min_safe"], max_per_school=4)
    by_key = {ev["program"]["program_id"]: ev for ev in evals}
    chosen = [by_key[it.key] for it in picked]
    chosen_keys = {c["program"]["program_id"] for c in chosen}
    alternatives = sorted((ev for ev in evals if ev["program"]["program_id"] not in chosen_keys),
                          key=lambda ev: ev["p_admit"] * ev["utility"], reverse=True)[:10]

    # Gán cờ và nhãn độ tin cậy
    for ev in chosen + alternatives:
        esc = [BY_ID[q].text_vi for q, a in ev["answers"].items() if a.escalate]
        flags = []
        if ev["answers"]["conditions_ok"].p("no") > 0.5:
            flags.append("có thể không đáp ứng điều kiện riêng: " + str(ev["program"].get("conditions")))
        if ev["program"].get("campus"):
            flags.append(f"học tại {ev['program']['campus']}")
        if ev["program"].get("latest_status") == "disputed":
            flags.append(f"hai nguồn công bố điểm chuẩn {ev['program'].get('latest_year')} khác nhau")
        ev["flags"] = flags
        ev["confidence"], ev["confidence_reasons"] = explain.confidence_label(
            ev["forecast"].sigma, ev["program"].get("latest_status") or "", len(esc), ev["program"].get("tuition_provenance") == "estimated")

    # 6. Tính toán P(any) và Expected Value bằng Monte Carlo chuẩn xác
    sd = MOCK_SCORE_SD if profile.score_kind == "mock" else 0.0
    pa_, exp_val = p_any_monte_carlo(chosen, student_sd=sd, n_sims=5000)

    summary = explain.list_summary(
        chosen, pa_, exp_val, cons["min_safe"], profile.score_kind, weights
    )

    return Advice(
        profile=profile, ruleset=ruleset, target_year=target_year, profile_answers=pa, clarify=[],
        weights=weights, constraints=cons, criteria_ranking=criteria_ranking, criteria_clusters=criteria_clusters,
        radar_benchmark=radar_benchmark, chosen=chosen, alternatives=alternatives, n_eligible=n_eligible,
        n_candidates=len(evals), p_any=pa_, expected_value=exp_val, summary=summary,
        judge=getattr(judge, "name", "?"), notes=notes
    )
