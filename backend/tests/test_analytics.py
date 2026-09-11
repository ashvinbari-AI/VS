"""Spec section 59's explicit must-not-crash cases, plus median/engagement
correctness. These pin down real bugs found while validating against the
project's actual scraped Instagram data (see also test_normalize.py)."""

from __future__ import annotations

import pandas as pd

from app.analytics import engine as eng


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_engagement_survives_null_shares():
    df = _df([
        {"likes": 100, "comments_count": 10, "shares": None, "reactions_total": 100},
        {"likes": 50, "comments_count": 5, "shares": 3, "reactions_total": 50},
    ])
    series = eng.compute_engagement_series(df)
    assert list(series) == [110.0, 58.0]


def test_engagement_all_null_returns_none_not_crash():
    df = _df([{"likes": None, "comments_count": None, "shares": None, "reactions_total": None}])
    series = eng.compute_engagement_series(df)
    assert series.iloc[0] is None


def test_engagement_rate_none_when_followers_missing():
    df = _df([{"likes": 100, "comments_count": 10, "shares": None, "reactions_total": 100}])
    assert eng.calculate_engagement_rate(df, None) is None
    assert eng.calculate_engagement_rate(df, 0) is None
    assert eng.calculate_engagement_rate(df, 1000) is not None


def test_median_not_distorted_the_same_way_as_average_by_outlier():
    df = _df([
        {"likes": 100}, {"likes": 110}, {"likes": 90}, {"likes": 105}, {"likes": 100000},
    ])
    avg = eng.calculate_average_likes(df)
    median = eng.calculate_median_likes(df)
    assert avg > median  # the viral post drags the mean up, not the median
    assert median == 105.0


def test_comment_statistics_empty_dataframe_does_not_crash():
    empty_comments = pd.DataFrame(columns=["content_id"])
    empty_content = pd.DataFrame(columns=["content_id"])
    stats = eng.calculate_comment_statistics(empty_comments, empty_content)
    assert stats["total_comments"] == 0


def test_activity_by_day_always_has_all_seven_days():
    df = _df([{"published_at": "2026-01-05T10:00:00+00:00"}])  # a Monday
    counts = eng.calculate_activity_by_day(df)
    assert set(counts.keys()) == {"Monday", "Tuesday", "Wednesday", "Thursday",
                                   "Friday", "Saturday", "Sunday"}
    assert counts["Monday"] == 1


def test_activity_by_hour_falls_back_to_utc_when_local_column_is_all_null():
    """Regression: an all-null published_at_local column must not silently
    produce an all-zero hour distribution just because the column exists."""
    df = _df([
        {"published_at": "2026-01-05T08:15:00+00:00", "published_at_local": None},
        {"published_at": "2026-01-05T08:45:00+00:00", "published_at_local": None},
    ])
    counts = eng.calculate_activity_by_hour(df)
    assert counts[8] == 2


def test_p90_and_top10_percent_engagement():
    df = _df([{"likes": v, "comments_count": 0, "shares": 0, "reactions_total": v}
              for v in range(1, 101)])
    p90 = eng.calculate_p90_engagement(df)
    assert p90 is not None and p90 >= 89
    top10 = eng.calculate_top10_percent_avg_engagement(df)
    assert top10 > p90


def test_narrative_diversity_entropy_zero_when_single_category():
    result = eng.calculate_narrative_diversity({"Development": 10})
    assert result["unique_narratives"] == 1
    assert result["entropy"] == 0
    assert result["dominant_pct"] == 100.0
