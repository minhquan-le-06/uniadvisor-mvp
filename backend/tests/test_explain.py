"""Module 4 explanations use only the values already present in an evaluation."""

from types import SimpleNamespace

from uniadvisor.explain import alternative_reason, confidence_label, list_summary, program_explanation, ranking_reasons


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
