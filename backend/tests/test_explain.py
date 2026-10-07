"""Module 4 explanations use only the values already present in an evaluation."""

from types import SimpleNamespace

from uniadvisor.explain import (alternative_reason, confidence_label, enrich_advice, list_summary,
                                program_explanation, ranking_reasons, triple_explanation)


def _row(name: str, program_id: str, utility: float, probability: float, bucket: str = "match", **criteria):
    values = {"fit": 0.5, "ability": 0.5, "tuition": 0.5, "location": 0.5, "selectivity": 0.5}
    values.update(criteria)
    return {
        "program": {"program_id": program_id, "program_name": name, "school_code": "TST"},
        "utility": utility,
        "p_admit": probability,
        "bucket": bucket,
        "criteria": values,
    }


def test_program_explanation_keeps_student_and_reference_combinations_separate():
    fc = SimpleNamespace(target_year=2027, score=24.0, years=[2025, 2026], past_scores=[23.0, 24.5],
                         top_share=0.14, ref_combo="A00", dist_year=2026)
    ev = {
        **_row("Kỹ thuật", "P1", 0.7, 0.6), "forecast": fc, "cutoff_interval": (22.0, 26.0),
        "combo": "A01", "raw_total": 22.5, "priority": 0.0, "total": 22.5, "wins": [], "losses": [], "flags": [],
    }
    text = program_explanation(ev)
    assert "tổ hợp A01: 22.50" in text
    assert "tổ hợp tham chiếu A00" in text
    assert "tổ hợp A01: 22.50" not in text[text.index("tổ hợp tham chiếu A00"):]


def test_confidence_uses_forecast_uncertainty_not_number_of_years():
    high, high_reasons = confidence_label(1.2, "confirmed_2_sources", 0, False)
    low, low_reasons = confidence_label(1.8, "disputed", 1, True)
    assert high == "cao" and "±1.20" in high_reasons[0]
    assert low == "thấp" and "±1.80" in low_reasons[0]


def test_summary_and_per_rank_reason_name_the_actual_ordering_criteria():
    first = _row("A", "P1", 0.80, 0.40, tuition=0.9, selectivity=0.8)
    second = _row("B", "P2", 0.70, 0.90, tuition=0.3, selectivity=0.4)
    weights = {"fit": 0.2, "ability": 0.1, "tuition": 0.4, "location": 0.1, "selectivity": 0.2}
    reasons = ranking_reasons([first, second], weights)
    summary = list_summary([first, second], 0.94, 0.5, 1, "actual", weights)
    assert "Học phí" in reasons[0]
    assert "Học phí" in summary
    assert "hợp em nhất" not in summary


def test_unlikely_alternative_reports_the_automatic_exclusion_rule():
    chosen = [_row("A", "P1", 0.8, 0.9, "safe")]
    alt = _row("B", "P2", 0.6, 0.08, "unlikely")
    text = alternative_reason(alt, chosen, {"fit": 1.0}, min_safe=1, max_per_school=4)
    assert "không được tự động" in text and "khó đỗ" in text


def test_triple_explanation_is_built_from_the_numeric_cluster():
    fc = SimpleNamespace(score=24.0)
    first = {**_row("A", "P1", 0.8, 0.9, "safe", fit=0.9, ability=0.7), "forecast": fc, "combo": "A00", "total": 25.0, "flags": []}
    second = {**_row("B", "P2", 0.6, 0.5, "match", fit=0.5, ability=0.6), "forecast": fc, "combo": "A00", "total": 25.0, "flags": []}
    text = triple_explanation(first, "fit", [first, second])
    assert set(text) == {"cross_criteria", "intra_criterion", "user_fit"}
    assert "Hợp sở thích" in text["cross_criteria"] and "90%" in text["user_fit"]


def test_only_estimated_fees_are_called_estimates_in_module4(tiny_db):
    """Confidence wording is Module 4 output, so it is checked here rather than in Module 3's suite."""
    from uniadvisor.recommend.advisor import advise
    from uniadvisor.recommend.forecast import ForecastParams
    from uniadvisor.student.slm.infer import HeuristicJudge
    from uniadvisor.student.slm.state import StudentProfile

    profile = StudentProfile(
        scores={"TO": 9.0, "VA": 9.0, "LI": 9.0, "HO": 9.0, "SU": 9.0, "DI": 9.0},
        answers={"risk_tolerance": "can_bang", "top_priority": "nganh_yeu_thich"},
    )
    advice = enrich_advice(advise(profile, judge=HeuristicJudge(), db=tiny_db, params=ForecastParams(), k_max=12))
    by_id = {row["program"]["program_id"]: row for row in advice.chosen + advice.alternatives}
    estimated = "học phí là ước tính theo mức chung của trường"
    assert estimated in by_id["SIM-HN1:CE"]["confidence_reasons"]
    assert estimated not in by_id["SIM-HC1:EDU-MATH"]["confidence_reasons"]
    assert estimated not in by_id["SIM-HN1:IT"]["confidence_reasons"]


def test_enrich_advice_restores_the_fields_expected_by_the_presentation():
    chosen = [_row("A", "P1", 0.8, 0.9, "safe"), _row("B", "P2", 0.7, 0.7)]
    alternative = _row("C", "P3", 0.4, 0.1, "unlikely")
    fc = SimpleNamespace(target_year=2027, score=24.0, years=[2026], past_scores=[24.0], top_share=float("nan"), ref_combo="A00", dist_year=2026)
    for row in [*chosen, alternative]:
        row.update({"forecast": fc, "cutoff_interval": (22.0, 26.0), "combo": "A00", "raw_total": 24.0,
                    "priority": 0.0, "total": 24.0, "flags": []})
    profile = SimpleNamespace(free_text="")
    advice = SimpleNamespace(chosen=chosen, alternatives=[alternative], profile=profile,
                             weights={"fit": 0.2, "ability": 0.2, "tuition": 0.2, "location": 0.2, "selectivity": 0.2},
                             constraints={"min_safe": 1})
    enrich_advice(advice)
    assert all(row["explanation"] and row["ranking_reason"] for row in chosen)
    assert alternative["alternative_reason"] and "wins" in alternative and "judgment_evidence" in alternative
