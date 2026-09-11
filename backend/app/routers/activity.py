"""GET /api/activity -- spec section 14."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.analytics import engine as eng
from app.analytics.filters import filter_content
from app.models.common import ApiResponse
from app.storage.data_source import get_content_df

router = APIRouter(prefix="/api/activity", tags=["activity"])


def _activity_block(df, period_days: int) -> dict:
    freq = eng.calculate_posting_frequency(df, period_days)
    reels_df = df[df["content_type"] == "reel"] if "content_type" in df.columns else df.iloc[0:0]
    reel_freq = eng.calculate_posting_frequency(reels_df, period_days)
    return {
        "posts_per_day": freq["per_day"], "posts_per_week": freq["per_week"],
        "posts_per_month": freq["per_month"],
        "reels_per_day": reel_freq["per_day"], "reels_per_week": reel_freq["per_week"],
        "reels_per_month": reel_freq["per_month"],
        "activity_by_day": eng.calculate_activity_by_day(df),
        "activity_by_hour": eng.calculate_activity_by_hour(df),
        "most_active_day": eng.most_active_day(df),
        "most_active_hour": eng.most_active_hour(df),
        "active_days": eng.calculate_active_days(df),
        "longest_inactive_period_days": eng.calculate_longest_inactive_period(df),
        "consistency": eng.calculate_activity_consistency(df),
    }


@router.get("")
def get_activity(
    person_a: str = Query(...), person_b: str = Query(...),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
    period_days: int = 30,
) -> ApiResponse:
    content = get_content_df()
    df_a = filter_content(content, person_ids=[person_a], platform=platform,
                           content_type=content_type, date_from=date_from, date_to=date_to)
    df_b = filter_content(content, person_ids=[person_b], platform=platform,
                           content_type=content_type, date_from=date_from, date_to=date_to)
    return ApiResponse.ok({
        "person_a": _activity_block(df_a, period_days),
        "person_b": _activity_block(df_b, period_days),
    })
