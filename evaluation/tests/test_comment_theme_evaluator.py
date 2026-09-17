"""SYNTHETIC TEST DATA."""

from __future__ import annotations

from evaluation.evaluators.comments import evaluate_comment_theme


def test_comment_theme_basic():
    gt = [{"comment_id": "c1", "human_label": "Praise"}, {"comment_id": "c2", "human_label": "Question"}]
    cache = {"comment:c1": {"theme": "Praise"}, "comment:c2": {"theme": "Criticism"}}
    report = evaluate_comment_theme(gt, cache)
    assert report["n"] == 2
    assert report["accuracy"] == 0.5
    assert report["errors"][0]["comment_id"] == "c2"
