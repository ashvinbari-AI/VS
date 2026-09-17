"""SYNTHETIC TEST DATA."""

from __future__ import annotations

from evaluation.evaluators.field_accuracy import (
    evaluate_content_type_classification, evaluate_post_fields,
)


def test_correct_and_incorrect_fields_counted_separately():
    gt = [{"content_id": "p1", "likes": 100, "caption": "hello"}]
    production = [{"content_id": "p1", "likes": 100, "caption": "goodbye"}]  # likes right, caption wrong
    result = evaluate_post_fields(gt, production, fields=["likes", "caption"])
    assert result["per_field"]["likes"]["correct"] == 1
    assert result["per_field"]["likes"]["incorrect"] == 0
    assert result["per_field"]["caption"]["correct"] == 0
    assert result["per_field"]["caption"]["incorrect"] == 1
    assert len(result["per_field"]["caption"]["mismatches"]) == 1


def test_missing_production_record_counts_as_missing_not_incorrect():
    gt = [{"content_id": "not_in_production", "likes": 100}]
    result = evaluate_post_fields(gt, [], fields=["likes"])
    assert result["per_field"]["likes"]["missing"] == 1
    assert result["per_field"]["likes"]["incorrect"] == 0


def test_comments_ground_truth_field_name_maps_to_comments_count():
    gt = [{"content_id": "p1", "comments": 50}]
    production = [{"content_id": "p1", "comments_count": 50}]
    result = evaluate_post_fields(gt, production, fields=["comments"])
    assert result["per_field"]["comments"]["correct"] == 1


def test_both_none_counts_as_correct_agreement_on_unavailable():
    gt = [{"content_id": "p1", "shares": None}]
    production = [{"content_id": "p1", "shares": None}]
    result = evaluate_post_fields(gt, production, fields=["shares"])
    assert result["per_field"]["shares"]["correct"] == 1


def test_content_type_classification_confusion_and_f1():
    gt = [{"content_id": "p1", "content_type": "reel"}, {"content_id": "p2", "content_type": "post"}]
    production = [{"content_id": "p1", "content_type": "reel"}, {"content_id": "p2", "content_type": "video"}]
    report = evaluate_content_type_classification(gt, production)
    assert report["accuracy"] == 0.5
    assert report["confusion_matrix"]["matrix"]["post"]["video"] == 1


def test_content_type_classification_no_overlap_reports_zero_n():
    report = evaluate_content_type_classification([{"content_id": "gone", "content_type": "post"}], [])
    assert report["n"] == 0
