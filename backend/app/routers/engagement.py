"""GET /api/engagement -- spec sections 15/16."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.analytics import engine as eng
from app.analytics.filters import filter_content
from app.models.common import ApiResponse
from app.storage.data_source import get_content_df, get_profiles_df, latest_followers

router = APIRouter(prefix="/api/engagement", tags=["engagement"])


def _engagement_block(df, followers) -> dict:
    return {
        "total_engagement": (
            None if (s := eng.compute_engagement_series(df)).empty else round(float(s.sum()), 1)
        ),
        "average_engagement": eng.calculate_average_engagement(df),
        "median_engagement": eng.calculate_median_engagement(df),
        "engagement_rate_pct": eng.calculate_engagement_rate(df, followers),
        "engagement_per_1000_followers": eng.calculate_engagement_per_1000_followers(df, followers),
        "average_likes": eng.calculate_average_likes(df),
        "median_likes": eng.calculate_median_likes(df),
        "average_comments": eng.calculate_average_comments(df),
        "median_comments": eng.calculate_median_comments(df),
        "average_shares": eng.calculate_average_shares(df),
        "median_shares": eng.calculate_median_shares(df),
        "p90_engagement": eng.calculate_p90_engagement(df),
        "p95_engagement": eng.calculate_p95_engagement(df),
        "top10_percent_avg_engagement": eng.calculate_top10_percent_avg_engagement(df),
        "followers": followers,
        "data_quality": {
            "shares_available": bool(df["shares"].notna().any()) if "shares" in df and len(df) else False,
            "followers_available": followers is not None,
        },
    }


@router.get("")
def get_engagement(
    person_a: str = Query(...), person_b: str = Query(...),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
) -> ApiResponse:
    content = get_content_df()
    profiles = get_profiles_df()
    df_a = filter_content(content, person_ids=[person_a], platform=platform,
                           content_type=content_type, date_from=date_from, date_to=date_to)
    df_b = filter_content(content, person_ids=[person_b], platform=platform,
                           content_type=content_type, date_from=date_from, date_to=date_to)
    followers_a = latest_followers(profiles, person_a)
    followers_b = latest_followers(profiles, person_b)
    return ApiResponse.ok({
        "person_a": _engagement_block(df_a, followers_a),
        "person_b": _engagement_block(df_b, followers_b),
    })
