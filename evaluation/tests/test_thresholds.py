"""Tests against the REAL evaluation/config/thresholds.yaml shipped with
this project -- not a synthetic copy -- so a threshold edit is caught by
these tests too."""

from __future__ import annotations

from evaluation.config.thresholds import get_threshold, status_for


def test_thresholds_yaml_loads_and_has_expected_categories():
    assert get_threshold("data", "completeness_pct") is not None
    assert get_threshold("nlp", "sentiment_f1") is not None


def test_status_for_none_value_is_not_evaluated_never_a_silent_pass():
    assert status_for("nlp", "sentiment_f1", None) == "NOT_EVALUATED"


def test_status_for_above_pass_threshold():
    assert status_for("data", "completeness_pct", 99) == "PASS"


def test_status_for_between_warn_and_pass_is_warning():
    assert status_for("data", "completeness_pct", 90) == "WARNING"


def test_status_for_below_warn_is_fail():
    assert status_for("data", "completeness_pct", 10) == "FAIL"


def test_status_for_unknown_metric_is_not_evaluated():
    assert status_for("nonexistent", "metric", 100) == "NOT_EVALUATED"
