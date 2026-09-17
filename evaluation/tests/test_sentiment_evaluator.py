"""SYNTHETIC TEST DATA -- fake nlp_cache entries, not real scraped content."""

from __future__ import annotations

from evaluation.evaluators.sentiment import evaluate_sentiment


def test_perfect_agreement():
    gt = [{"record_id": "p1", "record_type": "post", "human_label": "Positive"},
          {"record_id": "p2", "record_type": "post", "human_label": "Negative"}]
    cache = {"p1": {"sentiment": "Positive", "model": "rule_based_v1"},
             "p2": {"sentiment": "Negative", "model": "rule_based_v1"}}
    report = evaluate_sentiment(gt, cache)
    assert report["accuracy"] == 1.0
    assert report["errors"] == []


def test_comment_record_type_uses_comment_prefix_key():
    gt = [{"record_id": "c1", "record_type": "comment", "human_label": "Positive"}]
    cache = {"comment:c1": {"sentiment": "Positive", "model": "gemini:gemini-2.0-flash"}}
    report = evaluate_sentiment(gt, cache)
    assert report["accuracy"] == 1.0
    assert report["models_used"] == ["gemini:gemini-2.0-flash"]


def test_wrong_prediction_recorded_as_error_with_model_labeled():
    gt = [{"record_id": "p1", "record_type": "post", "human_label": "Positive"}]
    cache = {"p1": {"sentiment": "Neutral", "model": "rule_based_v1"}}
    report = evaluate_sentiment(gt, cache)
    assert report["errors"][0]["human_label"] == "Positive"
    assert report["errors"][0]["model_label"] == "Neutral"


def test_unclassified_record_excluded_from_metrics_not_counted_as_wrong():
    gt = [{"record_id": "p1", "record_type": "post", "human_label": "Positive"},
          {"record_id": "not_analyzed_yet", "record_type": "post", "human_label": "Negative"}]
    cache = {"p1": {"sentiment": "Positive", "model": "rule_based_v1"}}
    report = evaluate_sentiment(gt, cache)
    assert report["n"] == 1
    assert report["unclassified"] == 1


def test_no_ground_truth_reports_not_evaluated_note():
    report = evaluate_sentiment([], {})
    assert report["n"] == 0
    assert "note" in report
