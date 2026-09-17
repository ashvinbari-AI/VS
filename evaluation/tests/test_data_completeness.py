"""SYNTHETIC TEST DATA."""

from __future__ import annotations

import pandas as pd

from evaluation.evaluators.data_completeness import (
    evaluate_content_completeness, field_completeness, record_completeness,
)


def test_record_completeness_all_found():
    result = record_completeness({"a", "b", "c"}, {"a", "b", "c", "d"})
    assert result["completeness_pct"] == 100.0
    assert result["missing_count"] == 0
    assert result["extra_count"] == 1


def test_record_completeness_some_missing():
    result = record_completeness({"a", "b", "c", "d"}, {"a", "b"})
    assert result["completeness_pct"] == 50.0
    assert set(result["missing"]) == {"c", "d"}


def test_record_completeness_no_manifest_is_not_none_but_flagged():
    result = record_completeness(set(), {"a", "b"})
    assert result["completeness_pct"] is None
    assert "note" in result


def test_field_completeness_reports_non_null_pct():
    df = pd.DataFrame([{"likes": 10, "caption": "x"}, {"likes": None, "caption": "y"},
                        {"likes": 20, "caption": None}])
    result = field_completeness(df, ["likes", "caption"])
    assert result["likes"]["completeness_pct"] == round(2 / 3 * 100, 2)
    assert result["caption"]["completeness_pct"] == round(2 / 3 * 100, 2)


def test_field_completeness_missing_column_reports_zero_not_crash():
    df = pd.DataFrame([{"likes": 10}])
    result = field_completeness(df, ["shares"])
    assert result["shares"]["completeness_pct"] is None
    assert "note" in result["shares"]


def test_evaluate_content_completeness_end_to_end():
    df = pd.DataFrame([
        {"content_id": "p1", "content_type": "post", "published_at": "2026-01-01", "caption": "a",
         "likes": 10, "comments_count": 2},
        {"content_id": "p2", "content_type": "reel", "published_at": "2026-01-02", "caption": None,
         "likes": 20, "comments_count": 5},
    ])
    gt = [{"content_id": "p1"}, {"content_id": "p3"}]  # p3 is missing from production
    result = evaluate_content_completeness(df, gt)
    assert result["total_posts"] == 2
    assert result["record_completeness"]["completeness_pct"] == 50.0
    assert result["record_completeness"]["missing"] == ["p3"]
