"""SYNTHETIC TEST DATA."""

from __future__ import annotations

from evaluation.evaluators.duplicates import evaluate_duplicates, production_predicts_duplicate


def test_same_id_predicted_duplicate():
    assert production_predicts_duplicate("ig_abc", "ig_abc") is True


def test_different_id_predicted_not_duplicate():
    assert production_predicts_duplicate("ig_abc", "ig_xyz") is False


def test_empty_ground_truth_reports_none_not_zero():
    result = evaluate_duplicates([])
    assert result["n_pairs"] == 0
    assert result["precision"] is None


def test_true_positive_and_true_negative():
    pairs = [
        {"content_id_a": "ig_abc", "content_id_b": "ig_abc", "is_duplicate": True},   # TP
        {"content_id_a": "ig_abc", "content_id_b": "ig_xyz", "is_duplicate": False},  # TN
    ]
    result = evaluate_duplicates(pairs)
    assert result["tp"] == 1
    assert result["tn"] == 1
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0


def test_false_negative_when_human_says_duplicate_but_ids_differ():
    """Honest limitation: production can't catch a same-post-different-id
    duplicate -- this must show up as a false negative, not be hidden."""
    pairs = [{"content_id_a": "ig_abc", "content_id_b": "ig_abc_reimport", "is_duplicate": True}]
    result = evaluate_duplicates(pairs)
    assert result["fn"] == 1
    assert result["recall"] == 0.0
    assert result["errors"][0]["error_type"] == "false_negative"


def test_false_positive_would_require_same_id_but_human_says_not_duplicate():
    pairs = [{"content_id_a": "ig_abc", "content_id_b": "ig_abc", "is_duplicate": False}]
    result = evaluate_duplicates(pairs)
    assert result["fp"] == 1
    assert result["errors"][0]["error_type"] == "false_positive"
