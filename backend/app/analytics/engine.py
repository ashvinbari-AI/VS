"""
Deterministic analytics (spec section 31). No LLM call happens anywhere in
this file -- every number here is plain pandas/statistics arithmetic, so the
same input always produces the same output.

Convention used everywhere: a metric that cannot be computed because the
underlying field doesn't exist for this data returns None (renders "N/A" in
the API/UI), never 0 or NaN. An empty-but-present column (e.g. shares==0 for
every FB post that genuinely got no shares) is a real 0, and stays 0.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Engagement
# ---------------------------------------------------------------------------


def compute_engagement_series(df: pd.DataFrame) -> pd.Series:
    """engagement = reactions (falling back to likes if no reactions_total) +
    comments + shares -- only summing components that actually exist per row.

    Deliberately NOT "likes + comments + shares + reactions" as a literal
    sum: on both platforms `likes` IS the like-type reaction, so adding it to
    reactions_total would double-count it. reactions_total already covers
    likes (and, on Facebook, every other reaction type); it's used first and
    `likes` is only a fallback when reactions_total itself is missing.
    """
    if df.empty:
        return pd.Series(dtype="float64")

    def row_engagement(row: pd.Series) -> float | None:
        reaction = row.get("reactions_total")
        if pd.isna(reaction):
            reaction = row.get("likes")
        comments = row.get("comments_count")
        shares = row.get("shares")
        parts = [v for v in (reaction, comments, shares) if v is not None and not pd.isna(v)]
        if not parts:
            return None
        return float(sum(parts))

    return df.apply(row_engagement, axis=1)


def with_engagement(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["engagement"] = compute_engagement_series(df)
    return df


# ---------------------------------------------------------------------------
# Basic counts / central tendency
# ---------------------------------------------------------------------------


def _safe_mean(series: pd.Series) -> float | None:
    s = series.dropna()
    if s.empty:
        return None
    return round(float(s.mean()), 2)


def _safe_median(series: pd.Series) -> float | None:
    s = series.dropna()
    if s.empty:
        return None
    return round(float(s.median()), 2)


def _safe_percentile(series: pd.Series, q: float) -> float | None:
    s = series.dropna()
    if s.empty:
        return None
    return round(float(s.quantile(q)), 2)


def _safe_sum(series: pd.Series) -> float | None:
    s = series.dropna()
    if s.empty:
        return None
    return round(float(s.sum()), 2)


def calculate_total_content(df: pd.DataFrame) -> int:
    return int(len(df))


def calculate_average_likes(df: pd.DataFrame) -> float | None:
    return _safe_mean(df["likes"]) if "likes" in df else None


def calculate_median_likes(df: pd.DataFrame) -> float | None:
    return _safe_median(df["likes"]) if "likes" in df else None


def calculate_average_comments(df: pd.DataFrame) -> float | None:
    return _safe_mean(df["comments_count"]) if "comments_count" in df else None


def calculate_median_comments(df: pd.DataFrame) -> float | None:
    return _safe_median(df["comments_count"]) if "comments_count" in df else None


def calculate_average_shares(df: pd.DataFrame) -> float | None:
    return _safe_mean(df["shares"]) if "shares" in df else None


def calculate_median_shares(df: pd.DataFrame) -> float | None:
    return _safe_median(df["shares"]) if "shares" in df else None


def calculate_sum_likes(df: pd.DataFrame) -> float | None:
    return _safe_sum(df["likes"]) if "likes" in df else None


def calculate_sum_comments(df: pd.DataFrame) -> float | None:
    return _safe_sum(df["comments_count"]) if "comments_count" in df else None


def calculate_sum_shares(df: pd.DataFrame) -> float | None:
    return _safe_sum(df["shares"]) if "shares" in df else None


def calculate_sum_views(df: pd.DataFrame) -> float | None:
    """sum(view_count) over whatever rows the caller already filtered to
    (e.g. content_type == 'post'). Real for Instagram Reels (the scraper's
    Reels-tab view-count collector -- see ingestion/normalize.py) and for
    Facebook; still None/N/A for Instagram photos/carousels, which Instagram
    never exposes a view count for at all -- never a fabricated 0."""
    return _safe_sum(df["view_count"]) if "view_count" in df else None


def calculate_average_engagement(df: pd.DataFrame) -> float | None:
    eng = compute_engagement_series(df)
    return _safe_mean(eng)


def calculate_sum_engagement(df: pd.DataFrame) -> float | None:
    eng = compute_engagement_series(df)
    return _safe_sum(eng)


def calculate_median_engagement(df: pd.DataFrame) -> float | None:
    eng = compute_engagement_series(df)
    return _safe_median(eng)


def calculate_p90_engagement(df: pd.DataFrame) -> float | None:
    eng = compute_engagement_series(df)
    return _safe_percentile(eng, 0.90)


def calculate_p95_engagement(df: pd.DataFrame) -> float | None:
    eng = compute_engagement_series(df)
    return _safe_percentile(eng, 0.95)


def calculate_top10_percent_avg_engagement(df: pd.DataFrame) -> float | None:
    eng = compute_engagement_series(df).dropna()
    if eng.empty:
        return None
    n = max(1, math.ceil(len(eng) * 0.10))
    return round(float(eng.sort_values(ascending=False).head(n).mean()), 2)


def calculate_engagement_rate(df: pd.DataFrame, followers: int | None) -> float | None:
    """(average engagement / followers) * 100, or None if followers unknown."""
    if not followers:
        return None
    avg_eng = calculate_average_engagement(df)
    if avg_eng is None:
        return None
    return round(avg_eng / followers * 100, 4)


def calculate_engagement_per_1000_followers(df: pd.DataFrame, followers: int | None) -> float | None:
    if not followers:
        return None
    avg_eng = calculate_average_engagement(df)
    if avg_eng is None:
        return None
    return round(avg_eng / followers * 1000, 2)


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------


def published_datetime_series(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["published_at"], errors="coerce", utc=True)


# Backward-compatible internal alias used within this module.
_published_dt = published_datetime_series


def calculate_posting_frequency(df: pd.DataFrame, period_days: int) -> dict[str, float | None]:
    total = len(df)
    if period_days <= 0 or total == 0:
        return {"per_day": None, "per_week": None, "per_month": None}
    per_day = total / period_days
    return {
        "per_day": round(per_day, 3),
        "per_week": round(per_day * 7, 2),
        "per_month": round(per_day * 30, 2),
    }


def calculate_activity_by_day(df: pd.DataFrame) -> dict[str, int]:
    """Mon..Sun post counts. Always returns all 7 keys (0 where no posts)."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    counts = {d: 0 for d in days}
    if df.empty:
        return counts
    dt = _published_dt(df).dropna()
    for idx in dt.dt.dayofweek:
        counts[days[idx]] += 1
    return counts


def calculate_activity_by_hour(df: pd.DataFrame) -> dict[int, int]:
    """0..23 (local hour, expects published_at_local already converted by caller)."""
    counts = {h: 0 for h in range(24)}
    if df.empty:
        return counts
    # Prefer published_at_local, but only if it actually has data -- the
    # column can exist and be all-null (e.g. before normalize.py computed
    # it), in which case falling back to UTC published_at is more useful
    # than reporting an all-zero hour distribution.
    use_local = "published_at_local" in df.columns and df["published_at_local"].notna().any()
    col = "published_at_local" if use_local else "published_at"
    dt = pd.to_datetime(df[col], errors="coerce", utc=False)
    for h in dt.dropna().dt.hour:
        counts[int(h)] += 1
    return counts


def most_active_day(df: pd.DataFrame) -> str | None:
    counts = calculate_activity_by_day(df)
    if not any(counts.values()):
        return None
    return max(counts, key=counts.get)


def most_active_hour(df: pd.DataFrame) -> int | None:
    counts = calculate_activity_by_hour(df)
    if not any(counts.values()):
        return None
    return max(counts, key=counts.get)


def calculate_active_days(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    dt = _published_dt(df).dropna()
    return int(dt.dt.date.nunique())


def calculate_longest_inactive_period(df: pd.DataFrame) -> float | None:
    """Longest gap, in days, between consecutive posts."""
    if df.empty or len(df) < 2:
        return None
    dt = _published_dt(df).dropna().sort_values()
    if len(dt) < 2:
        return None
    gaps = dt.diff().dropna().dt.total_seconds() / 86400
    if gaps.empty:
        return None
    return round(float(gaps.max()), 2)


def calculate_posting_interval_stats(df: pd.DataFrame) -> dict[str, float | None]:
    """Median interval + stdev of intervals between posts, in hours."""
    if df.empty or len(df) < 2:
        return {"median_interval_hours": None, "stdev_interval_hours": None}
    dt = _published_dt(df).dropna().sort_values()
    if len(dt) < 2:
        return {"median_interval_hours": None, "stdev_interval_hours": None}
    gaps_hours = dt.diff().dropna().dt.total_seconds() / 3600
    return {
        "median_interval_hours": round(float(gaps_hours.median()), 2),
        "stdev_interval_hours": round(float(gaps_hours.std()), 2) if len(gaps_hours) > 1 else None,
    }


# ---------------------------------------------------------------------------
# Distributions
# ---------------------------------------------------------------------------


def calculate_content_type_distribution(df: pd.DataFrame) -> dict[str, int]:
    if df.empty or "content_type" not in df:
        return {}
    return df["content_type"].value_counts(dropna=False).to_dict()


def calculate_platform_distribution(df: pd.DataFrame) -> dict[str, int]:
    if df.empty or "platform" not in df:
        return {}
    return df["platform"].value_counts(dropna=False).to_dict()


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def calculate_top_content(df: pd.DataFrame, n: int = 10) -> list[dict[str, Any]]:
    if df.empty:
        return []
    df = with_engagement(df)
    top = df.sort_values("engagement", ascending=False, na_position="last").head(n)
    return top.to_dict(orient="records")


def calculate_bottom_content(df: pd.DataFrame, n: int = 10) -> list[dict[str, Any]]:
    if df.empty:
        return []
    df = with_engagement(df)
    valid = df.dropna(subset=["engagement"])
    bottom = valid.sort_values("engagement", ascending=True).head(n)
    return bottom.to_dict(orient="records")


def calculate_high_performance_content(df: pd.DataFrame, percentile: float = 0.95) -> list[dict[str, Any]]:
    """Statistical outliers (engagement > P{percentile}) -- labeled
    HIGH-PERFORMANCE CONTENT, never 'viral' (spec section 67)."""
    if df.empty:
        return []
    df = with_engagement(df)
    threshold = _safe_percentile(df["engagement"], percentile)
    if threshold is None:
        return []
    return df[df["engagement"] > threshold].to_dict(orient="records")


# ---------------------------------------------------------------------------
# Diversity / consistency (spec sections 65-66)
# ---------------------------------------------------------------------------


def calculate_narrative_diversity(narrative_counts: dict[str, int]) -> dict[str, Any]:
    total = sum(narrative_counts.values())
    if total == 0:
        return {"unique_narratives": 0, "entropy": None, "dominant_pct": None, "top3_pct": None}
    probs = [c / total for c in narrative_counts.values() if c > 0]
    entropy = round(-sum(p * math.log2(p) for p in probs), 3)
    sorted_counts = sorted(narrative_counts.values(), reverse=True)
    dominant_pct = round(sorted_counts[0] / total * 100, 2)
    top3_pct = round(sum(sorted_counts[:3]) / total * 100, 2)
    return {
        "unique_narratives": len(narrative_counts),
        "entropy": entropy,
        "dominant_pct": dominant_pct,
        "top3_pct": top3_pct,
    }


def calculate_activity_consistency(df: pd.DataFrame) -> dict[str, float | None]:
    interval_stats = calculate_posting_interval_stats(df)
    return {
        **interval_stats,
        "longest_gap_days": calculate_longest_inactive_period(df),
    }


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


def calculate_comment_statistics(comments_df: pd.DataFrame, content_df: pd.DataFrame) -> dict[str, Any]:
    total_comments = int(len(comments_df))
    per_post = (
        comments_df.groupby("content_id").size() if not comments_df.empty and "content_id" in comments_df
        else pd.Series(dtype="int64")
    )
    return {
        "total_comments": total_comments,
        "average_comments_per_post": _safe_mean(per_post) if not per_post.empty else (
            0 if len(content_df) else None),
        "median_comments_per_post": _safe_median(per_post) if not per_post.empty else (
            0 if len(content_df) else None),
    }
