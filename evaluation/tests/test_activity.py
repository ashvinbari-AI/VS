"""Calls the REAL backend/app/analytics/engine.py activity functions."""

from __future__ import annotations

from evaluation.evaluators.activity import evaluate_activity_metrics


def test_activity_metrics_all_pass_against_real_production_code():
    result = evaluate_activity_metrics()
    assert result["all_passed"] is True, result["cases"]


def test_total_content_is_four():
    result = evaluate_activity_metrics()
    total_case = next(c for c in result["cases"] if c["metric"] == "total_content")
    assert total_case["expected"] == 4
    assert total_case["actual"] == 4


def test_longest_inactive_period_is_three_days():
    # 01->02 (1 day), 02->05 (3 days), 05->07 (2 days) -> longest gap = 3
    result = evaluate_activity_metrics()
    gap_case = next(c for c in result["cases"] if c["metric"] == "longest_inactive_period_days")
    assert gap_case["expected"] == 3.0
