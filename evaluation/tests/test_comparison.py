"""Calls the REAL backend/app/analytics/comparison.py comparison engine."""

from __future__ import annotations

from evaluation.evaluators.comparison import evaluate_comparison_scenarios


def test_all_comparison_scenarios_pass_against_real_production_code():
    result = evaluate_comparison_scenarios()
    assert result["all_passed"] is True, result["scenarios"]


def test_person_b_wins_content_volume_person_a_wins_average_likes():
    result = evaluate_comparison_scenarios()
    scenario = next(s for s in result["scenarios"]
                     if s["scenario"] == "person_a_more_content_person_b_more_comments")
    checks_by_metric = {c["metric"]: c for c in scenario["checks"]}
    assert checks_by_metric["total_content"]["actual_winner"] == "person_b"
    assert checks_by_metric["average_likes"]["actual_winner"] == "person_a"


def test_equal_values_produce_no_winner():
    result = evaluate_comparison_scenarios()
    scenario = next(s for s in result["scenarios"] if s["scenario"] == "equal_likes_no_winner")
    checks_by_metric = {c["metric"]: c for c in scenario["checks"]}
    assert checks_by_metric["average_likes"]["actual_winner"] is None


def test_zero_followers_never_produces_a_fabricated_engagement_rate():
    result = evaluate_comparison_scenarios()
    scenario = next(s for s in result["scenarios"] if s["scenario"] == "both_zero_followers")
    checks_by_metric = {c["metric"]: c for c in scenario["checks"]}
    assert checks_by_metric["engagement_rate"]["actual_winner"] is None
