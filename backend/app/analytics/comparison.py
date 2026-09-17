"""
comparison.py (spec section 32) -- all numeric comparison is plain Python/
pandas here. No LLM is ever consulted to decide a number or a winner.

Metric "winner" rule (spec sections 13/63): a winner is only declared for
metrics where a direction is genuinely defensible (MORE_IS_BETTER /
LESS_IS_BETTER). Anything context-dependent (peak posting hour, most active
day, etc.) is tagged NEUTRAL and the comparison table shows both values with
no winner column entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.analytics import engine as eng


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    direction: str  # "higher_better" | "lower_better" | "neutral"


METRIC_REGISTRY: list[MetricSpec] = [
    MetricSpec("followers", "Followers", "higher_better"),
    MetricSpec("total_content", "Total Content", "higher_better"),
    MetricSpec("posts", "Posts", "higher_better"),
    MetricSpec("reels", "Reels", "higher_better"),
    MetricSpec("videos", "Videos", "higher_better"),
    MetricSpec("total_likes", "Total Likes", "higher_better"),
    MetricSpec("total_comments", "Total Comments", "higher_better"),
    MetricSpec("total_engagement", "Total Engagement", "higher_better"),
    MetricSpec("engagement_rate", "Engagement Rate", "higher_better"),
    MetricSpec("posting_frequency_per_day", "Posting Frequency (per day)", "neutral"),
    MetricSpec("peak_posting_hour", "Peak Posting Hour", "neutral"),
    MetricSpec("longest_inactive_period_days", "Longest Inactive Period (days)", "neutral"),
]


def _winner(a: float | None, b: float | None, direction: str, id_a: str, id_b: str) -> str | None:
    if direction == "neutral" or a is None or b is None:
        return None
    if a == b:
        return None
    if direction == "higher_better":
        return id_a if a > b else id_b
    if direction == "lower_better":
        return id_a if a < b else id_b
    return None


def build_person_metrics(df, comments_df, followers: int | None, period_days: int) -> dict[str, Any]:
    type_dist = eng.calculate_content_type_distribution(df)
    freq = eng.calculate_posting_frequency(df, period_days)
    hour = eng.most_active_hour(df)
    return {
        "followers": followers,
        "total_content": eng.calculate_total_content(df),
        "posts": type_dist.get("post", 0),
        "reels": type_dist.get("reel", 0),
        "videos": type_dist.get("video", 0),
        "total_likes": eng.calculate_sum_likes(df),
        "total_comments": eng.calculate_sum_comments(df),
        "total_engagement": eng.calculate_sum_engagement(df),
        # Not in METRIC_REGISTRY (the comparison table shows totals, not
        # these) -- kept for the Normalized Analytics Index radar below,
        # which wants per-post averages for its "Engagement"/"Comment
        # response" dimensions (a account that just posts more shouldn't
        # look more "engaging" there -- that's what "Content volume"
        # already measures).
        "average_engagement": eng.calculate_average_engagement(df),
        "average_comments": eng.calculate_average_comments(df),
        "engagement_rate": eng.calculate_engagement_rate(df, followers),
        "posting_frequency_per_day": freq["per_day"],
        "active_days": eng.calculate_active_days(df),
        "peak_posting_hour": hour,
        "longest_inactive_period_days": eng.calculate_longest_inactive_period(df),
    }


def calculate_comparison_metrics(
    person_a_id: str, person_b_id: str,
    df_a, df_b, comments_a, comments_b,
    followers_a: int | None, followers_b: int | None,
    period_days: int,
) -> dict[str, Any]:
    metrics_a = build_person_metrics(df_a, comments_a, followers_a, period_days)
    metrics_b = build_person_metrics(df_b, comments_b, followers_b, period_days)

    differences: dict[str, float | None] = {}
    pct_changes: dict[str, float | None] = {}
    comparisons: dict[str, dict[str, Any]] = {}

    for spec in METRIC_REGISTRY:
        a_val = metrics_a.get(spec.key)
        b_val = metrics_b.get(spec.key)
        if isinstance(a_val, (int, float)) and isinstance(b_val, (int, float)):
            differences[spec.key] = round(a_val - b_val, 4)
            pct_changes[spec.key] = (
                round((a_val - b_val) / b_val * 100, 2) if b_val not in (0, None) else None
            )
        else:
            differences[spec.key] = None
            pct_changes[spec.key] = None
        comparisons[spec.key] = {
            "label": spec.label,
            "direction": spec.direction,
            "person_a": a_val,
            "person_b": b_val,
            "winner": _winner(a_val, b_val, spec.direction, person_a_id, person_b_id),
        }

    return {
        "person_a": metrics_a,
        "person_b": metrics_b,
        "differences": differences,
        "percentage_changes": pct_changes,
        "comparisons": comparisons,
    }
