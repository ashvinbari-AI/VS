"""SYNTHETIC TEST DATA -- mirrors spec section 22's own worked example."""

from __future__ import annotations

from evaluation.evaluators.issues import evaluate_issues


def test_multi_label_full_match_is_a_pass_not_penalized_for_extra_labels():
    gt = [{"record_id": "c1", "human_issues": ["Roads", "Water"]}]
    cache = {"comment:c1": {"issues": ["Roads", "Water"]}}
    report = evaluate_issues(gt, cache)
    assert report["micro_f1"] == 1.0
    assert report["errors"] == []


def test_partial_match_reports_missed_and_extra_separately():
    gt = [{"record_id": "c1", "human_issues": ["Roads", "Water"]}]
    cache = {"comment:c1": {"issues": ["Roads", "Electricity"]}}
    report = evaluate_issues(gt, cache)
    assert report["errors"][0]["missed"] == ["Water"]
    assert report["errors"][0]["extra"] == ["Electricity"]


def test_empty_human_issues_list_is_a_valid_negative_case():
    gt = [{"record_id": "c1", "human_issues": []}]
    cache = {"comment:c1": {"issues": []}}
    report = evaluate_issues(gt, cache)
    assert report["errors"] == []
