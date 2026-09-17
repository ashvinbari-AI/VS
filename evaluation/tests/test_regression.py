"""SYNTHETIC TEST DATA."""

from __future__ import annotations

from evaluation.evaluators.regression import compare_to_baseline, flatten_metrics


def test_flatten_metrics_missing_paths_are_none_not_crash():
    report = {"scraper": {}}  # everything else absent
    tracked = flatten_metrics(report)
    assert all(v is None for v in tracked.values())


def test_flatten_metrics_extracts_nested_value():
    report = {"nlp": {"sentiment": {"macro_f1": 0.87}}}  # matches run.py's actual report["nlp"]["sentiment"] shape
    tracked = flatten_metrics(report)
    assert tracked["nlp.sentiment_macro_f1"] == 0.87


def test_no_baseline_reports_has_baseline_false():
    result = compare_to_baseline({"nlp.sentiment_macro_f1": 0.87}, None)
    assert result["has_baseline"] is False


def test_drop_beyond_threshold_is_flagged_regression():
    current = {"nlp.narrative_macro_f1": 0.81}
    baseline = {"nlp.narrative_macro_f1": 0.87}
    result = compare_to_baseline(current, baseline)
    entry = result["metrics"]["nlp.narrative_macro_f1"]
    assert entry["status"] == "REGRESSION"
    assert entry["diff"] == -6.0  # percentage points, matching spec section 26's own worked example


def test_small_drop_within_threshold_is_stable():
    current = {"nlp.sentiment_macro_f1": 0.86}
    baseline = {"nlp.sentiment_macro_f1": 0.87}
    result = compare_to_baseline(current, baseline)
    assert result["metrics"]["nlp.sentiment_macro_f1"]["status"] == "STABLE"


def test_improvement_flagged():
    current = {"nlp.sentiment_macro_f1": 0.95}
    baseline = {"nlp.sentiment_macro_f1": 0.87}
    result = compare_to_baseline(current, baseline)
    assert result["metrics"]["nlp.sentiment_macro_f1"]["status"] == "IMPROVED"


def test_missing_metric_in_baseline_is_not_comparable():
    result = compare_to_baseline({"new.metric": 0.9}, {"other.metric": 0.5})
    assert result["metrics"]["new.metric"]["status"] == "NOT_COMPARABLE"


def test_save_and_load_baseline_roundtrip(tmp_path, monkeypatch):
    import evaluation.evaluators.regression as regression_module
    monkeypatch.setattr(regression_module, "BASELINE_DIR", tmp_path)
    regression_module.save_as_baseline({"x": 1.0}, run_id="test_run")
    loaded = regression_module.load_baseline(run_id="test_run")
    assert loaded == {"x": 1.0}
