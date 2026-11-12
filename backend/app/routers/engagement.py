"""GET /api/engagement -- spec sections 15/16."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Query

from app.analytics import engine as eng
from app.analytics.filters import filter_content
from app.models.common import ApiResponse
from app.routers.people_params import parse_person_ids
from app.storage.data_source import get_content_df, get_profiles_df, latest_followers

router = APIRouter(prefix="/api/engagement", tags=["engagement"])

_TOP_CONTENT_COLUMNS = ["content_id", "person_id", "person_name", "platform", "content_type",
                        "published_at", "likes", "comments_count", "engagement", "content_url"]


def _top_by_type(df: pd.DataFrame, content_type: str, n: int = 3) -> list[dict]:
    """Top-N by engagement within one content_type, all selected people pooled
    together (spec section 67: labeled by rank/engagement, never 'viral')."""
    if df.empty:
        return []
    subset = eng.with_engagement(df[df["content_type"] == content_type])
    subset = subset.dropna(subset=["engagement"]).sort_values("engagement", ascending=False).head(n)
    if subset.empty:
        return []
    cols = [c for c in _TOP_CONTENT_COLUMNS if c in subset.columns]
    out = subset[cols]
    return out.where(pd.notnull(out), None).to_dict(orient="records")


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
    person_ids: list[str] = Query(...),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
) -> ApiResponse:
    ids = parse_person_ids(person_ids)
    content = get_content_df()
    profiles = get_profiles_df()
    dfs = {
        pid: filter_content(content, person_ids=[pid], platform=platform,
                            content_type=content_type, date_from=date_from, date_to=date_to)
        for pid in ids
    }

    non_empty = [df for df in dfs.values() if not df.empty]
    combined = pd.concat(non_empty, ignore_index=True) if non_empty else next(iter(dfs.values()))
    top_posts = _top_by_type(combined, "post")
    top_reels = _top_by_type(combined, "reel")

    return ApiResponse.ok({
        "person_ids": ids,
        "people": {pid: _engagement_block(dfs[pid], latest_followers(profiles, pid)) for pid in ids},
        "top_posts": top_posts,
        "top_reels": top_reels,
    })
