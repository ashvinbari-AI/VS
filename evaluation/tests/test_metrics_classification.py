"""SYNTHETIC TEST DATA -- hand-checkable, not real political content."""

from __future__ import annotations

from evaluation.metrics.classification import (
    bootstrap_ci, classification_report, cohens_kappa, confusion_matrix,
    multilabel_micro_macro, precision_recall_f1, safe_divide,
)


def test_safe_divide_handles_zero_denominator():
    assert safe_divide(5, 0) is None
    assert safe_divide(0, 0) is None
    assert safe_divide(5, 10) == 0.5


def test_precision_recall_f1_known_values():
    # tp=8, fp=2, fn=2 -> precision=0.8, recall=0.8, f1=0.8
    stats = precision_recall_f1(8, 2, 2)
    assert stats["precision"] == 0.8
    assert stats["recall"] == 0.8
    assert stats["f1"] == 0.8


def test_precision_recall_f1_zero_tp_is_safe():
    stats = precision_recall_f1(0, 0, 0)
    assert stats["precision"] is None
    assert stats["recall"] is None
    assert stats["f1"] is None


def test_confusion_matrix_counts():
    y_true = ["A", "A", "B", "B"]
    y_pred = ["A", "B", "B", "B"]
    cm = confusion_matrix(y_true, y_pred, labels=["A", "B"])
    assert cm["matrix"]["A"]["A"] == 1
    assert cm["matrix"]["A"]["B"] == 1
    assert cm["matrix"]["B"]["B"] == 2
    assert cm["matrix"]["B"]["A"] == 0


def test_classification_report_perfect_predictions():
    y_true = ["Positive", "Negative", "Neutral"]
    y_pred = ["Positive", "Negative", "Neutral"]
    report = classification_report(y_true, y_pred)
    assert report["accuracy"] == 1.0
    assert report["macro_f1"] == 1.0
    assert report["weighted_f1"] == 1.0


def test_classification_report_all_wrong():
    y_true = ["Positive", "Positive"]
    y_pred = ["Negative", "Negative"]
    report = classification_report(y_true, y_pred)
    assert report["accuracy"] == 0.0


def test_classification_report_rejects_mismatched_lengths():
    import pytest
    with pytest.raises(ValueError):
        classification_report(["A"], ["A", "B"])


def test_multilabel_micro_macro_full_match_is_perfect():
    y_true = [{"Roads", "Water"}, {"Electricity"}]
    y_pred = [{"Roads", "Water"}, {"Electricity"}]
    report = multilabel_micro_macro(y_true, y_pred)
    assert report["micro_f1"] == 1.0
    assert report["macro_f1"] == 1.0


def test_multilabel_micro_macro_partial_match():
    y_true = [{"Roads", "Water"}]
    y_pred = [{"Roads"}]  # missed "Water"
    report = multilabel_micro_macro(y_true, y_pred)
    assert report["per_label"]["Water"]["fn"] == 1
    assert report["per_label"]["Roads"]["tp"] == 1


def test_cohens_kappa_perfect_agreement():
    rater_a = ["Positive", "Negative", "Neutral", "Positive"]
    rater_b = ["Positive", "Negative", "Neutral", "Positive"]
    assert cohens_kappa(rater_a, rater_b) == 1.0


def test_cohens_kappa_mismatched_lengths_returns_none():
    assert cohens_kappa(["A"], ["A", "B"]) is None
    assert cohens_kappa([], []) is None


def test_bootstrap_ci_is_deterministic_given_seed():
    y_true = ["Positive"] * 8 + ["Negative"] * 2
    y_pred = ["Positive"] * 7 + ["Negative"] * 3

    def accuracy(t, p):
        return sum(1 for a, b in zip(t, p) if a == b) / len(t)

    result_1 = bootstrap_ci(y_true, y_pred, accuracy, n_boot=200, seed=42)
    result_2 = bootstrap_ci(y_true, y_pred, accuracy, n_boot=200, seed=42)
    assert result_1 == result_2
    assert result_1["lower"] <= result_1["point_estimate"] <= result_1["upper"]


def test_bootstrap_ci_empty_input():
    result = bootstrap_ci([], [], lambda t, p: 1.0)
    assert result["point_estimate"] is None
