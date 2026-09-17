"""Tests the merge logic in evaluation/utils/gt_adapter.py against
monkeypatched ground-truth loads -- never against real files."""

from __future__ import annotations

from evaluation.utils import gt_adapter


def test_sentiment_ground_truth_merges_posts_comments_and_dedicated_file(monkeypatch):
    def fake_load(filename):
        return {
            "posts_ground_truth.json": [{"content_id": "p1", "expected_sentiment": "Positive"}],
            "comments_ground_truth.json": [{"comment_id": "c1", "expected_sentiment": "Negative"}],
            "sentiment_ground_truth.json": [{"record_id": "p2", "record_type": "post", "human_label": "Neutral"}],
        }.get(filename, [])

    monkeypatch.setattr(gt_adapter, "load_ground_truth", fake_load)
    merged = gt_adapter.sentiment_ground_truth()
    ids = {r["record_id"] for r in merged}
    assert ids == {"p1", "c1", "p2"}


def test_dedicated_file_wins_on_conflicting_record_id(monkeypatch):
    def fake_load(filename):
        return {
            "posts_ground_truth.json": [{"content_id": "p1", "expected_sentiment": "Positive"}],
            "comments_ground_truth.json": [],
            "sentiment_ground_truth.json": [{"record_id": "p1", "record_type": "post", "human_label": "Negative"}],
        }.get(filename, [])

    monkeypatch.setattr(gt_adapter, "load_ground_truth", fake_load)
    merged = gt_adapter.sentiment_ground_truth()
    assert len(merged) == 1
    assert merged[0]["human_label"] == "Negative"  # the dedicated file's label, not the derived one


def test_issues_ground_truth_from_comments_file(monkeypatch):
    def fake_load(filename):
        return {
            "comments_ground_truth.json": [{"comment_id": "c1", "expected_issues": ["Roads", "Water"]}],
            "issues_ground_truth.json": [],
        }.get(filename, [])

    monkeypatch.setattr(gt_adapter, "load_ground_truth", fake_load)
    merged = gt_adapter.issues_ground_truth()
    assert merged == [{"record_id": "c1", "human_issues": ["Roads", "Water"]}]
