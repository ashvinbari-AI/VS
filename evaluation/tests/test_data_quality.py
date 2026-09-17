"""SYNTHETIC TEST DATA."""

from __future__ import annotations

import pandas as pd

from evaluation.evaluators.data_quality import evaluate_comments_quality, evaluate_content_quality


def test_empty_dataframe_reports_none_not_crash():
    result = evaluate_content_quality(pd.DataFrame())
    assert result["total_records"] == 0
    assert result["data_quality_pct"] is None


def test_all_valid_records_score_100():
    df = pd.DataFrame([
        {"content_id": "p1", "likes": 10, "comments_count": 2, "shares": 0,
         "published_at": "2026-01-01T00:00:00+00:00", "content_url": "https://example.com/p1"},
        {"content_id": "p2", "likes": 20, "comments_count": 4, "shares": 1,
         "published_at": "2026-01-02T00:00:00+00:00", "content_url": "https://example.com/p2"},
    ])
    result = evaluate_content_quality(df)
    assert result["data_quality_pct"] == 100.0
    assert result["invalid_records"] == 0


def test_duplicate_content_id_flagged_invalid():
    df = pd.DataFrame([{"content_id": "p1", "likes": 1}, {"content_id": "p1", "likes": 2}])
    result = evaluate_content_quality(df)
    assert result["checks"]["duplicate_content_id"] == 1
    assert result["invalid_records"] == 1  # only the second occurrence is flagged


def test_negative_likes_flagged():
    df = pd.DataFrame([{"content_id": "p1", "likes": -5}])
    result = evaluate_content_quality(df)
    assert result["checks"]["negative_likes"] == 1
    assert result["invalid_records"] == 1


def test_missing_content_id_flagged():
    df = pd.DataFrame([{"content_id": None, "likes": 5}])
    result = evaluate_content_quality(df)
    assert result["checks"]["missing_content_id"] == 1


def test_invalid_url_flagged_but_none_is_not_invalid():
    df = pd.DataFrame([{"content_id": "p1", "content_url": "not-a-url"},
                        {"content_id": "p2", "content_url": None}])
    result = evaluate_content_quality(df)
    assert result["checks"]["invalid_content_url"] == 1  # only the malformed one, not the missing one


def test_score_formula_is_documented():
    result = evaluate_content_quality(pd.DataFrame([{"content_id": "p1", "likes": 1}]))
    assert "methodology" in result


def test_comments_quality_negative_like_count():
    df = pd.DataFrame([{"comment_id": "c1", "like_count": -1}])
    result = evaluate_comments_quality(df)
    assert result["checks"]["negative_like_count"] == 1
