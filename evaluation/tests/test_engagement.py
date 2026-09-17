"""These call the REAL backend/app/analytics/engine.py functions (via
evaluation.utils.backend_bridge) -- run with the backend's own virtualenv
so pandas is available: backend\\.venv\\Scripts\\pytest ..\\evaluation\\tests"""

from __future__ import annotations

from evaluation.evaluators.engagement import (
    evaluate_average_median, evaluate_engagement_formula, evaluate_engagement_rate_formula,
)


def test_engagement_formula_all_cases_pass_against_real_production_code():
    result = evaluate_engagement_formula()
    assert result["all_passed"] is True, result["cases"]


def test_engagement_formula_missing_everything_is_none_not_zero():
    result = evaluate_engagement_formula()
    all_missing_case = next(c for c in result["cases"] if c["expected"] is None)
    assert all_missing_case["actual"] is None
    assert all_missing_case["status"] == "PASS"


def test_engagement_rate_all_cases_pass_and_never_produce_infinity_or_nan():
    result = evaluate_engagement_rate_formula()
    assert result["all_passed"] is True, result["cases"]
    assert all("Infinity" not in c["status"] and "NaN" not in c["status"] for c in result["cases"])


def test_average_median_matches_independent_arithmetic():
    result = evaluate_average_median()
    assert result["all_passed"] is True, result["cases"]
    by_name = {c["metric"]: c for c in result["cases"]}
    assert by_name["average_likes"]["expected"] == 30.0
    assert by_name["median_likes"]["expected"] == 30.0
