"""
GET /api/proof -- the evidence/audit trail behind a KPI card's number.

Never a new calculation: every branch here calls the exact same
app.analytics.engine function the KPI itself was built from (spec
sections 42/47's "every number traces back to a raw record" principle,
extended from individual posts to the aggregate KPIs themselves), then
also hands back the underlying rows so the number can be spot-checked by
hand against the real post/comment.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.analytics import engine as eng
from app.analytics.filters import filter_content
from app.models.common import ApiResponse
from app.storage.data_source import get_content_df, get_profiles_df, latest_followers

router = APIRouter(prefix="/api/proof", tags=["proof"])

_CONTENT_TYPE_FOR_METRIC = {"posts": "post", "reels": "reel", "videos": "video", "photos": "photo"}

FORMULAS = {
    "followers": "The most recent profile scrape snapshot's follower count (data/processed/profiles.parquet).",
    "total_content": "Count of every post/reel/video/photo in the filtered window.",
    "posts": "Count of rows where content_type == 'post'.",
    "reels": "Count of rows where content_type == 'reel'.",
    "videos": "Count of rows where content_type == 'video'.",
    "photos": "Count of rows where content_type == 'photo'.",
    "average_likes": "sum(likes) / count(posts with a likes value).",
    "median_likes": "The middle value of every post's likes, sorted.",
    "total_likes": "sum(likes) across every post with a likes value.",
    "average_comments": "sum(comments_count) / count(posts with a comments value).",
    "total_comments_count": "sum(comments_count) across every post with a comments value.",
    "average_engagement": (
        "mean(reactions_total -- falling back to likes only when reactions_total itself is "
        "missing -- + comments_count + shares), computed per post, only summing components "
        "that actually exist on that row."
    ),
    "total_engagement": (
        "sum(reactions_total -- falling back to likes only when reactions_total itself is "
        "missing -- + comments_count + shares), computed per post, only summing components "
        "that actually exist on that row."
    ),
    "engagement_rate": "average_engagement / followers * 100.",
    "view_engagement": (
        "sum(view_count) across every post and reel (content_type in ('post', 'reel')). "
        "Real for Instagram Reels (scraped off the profile's Reels tab) and Facebook; still "
        "N/A for Instagram photos/carousels, which never show a view count at all."
    ),
    "posts_per_day": "count(all posts in the filtered window) / period_days.",
    "posts_per_week": "posts_per_day * 7.",
    "reels_per_week": "count(reels in the filtered window) / period_days * 7.",
    "active_days": "Count of distinct calendar dates with at least one post.",
    "longest_inactive_period_days": "The largest gap, in days, between two consecutive posts (sorted by publish time).",
    "median_interval_hours": "The median gap, in hours, between consecutive posts (sorted by publish time).",
    "most_active_day": "The day of the week with the most posts (all 7 days counted, ties broken by whichever the count scan reaches first).",
    "most_active_hour": "The hour of day (0-23, local display timezone) with the most posts (ties broken the same way).",
}

_ROW_COLUMNS = ["content_id", "platform", "content_type", "published_at", "likes",
                "comments_count", "reactions_total", "shares", "view_count", "content_url", "author"]


def _rows(df: pd.DataFrame, sort_by: str | None = None) -> list[dict]:
    cols = [c for c in _ROW_COLUMNS if c in df.columns]
    out = df[cols]
    if sort_by and sort_by in out.columns:
        out = out.sort_values(sort_by, ascending=False, na_position="last")
    return out.where(pd.notnull(out), None).to_dict(orient="records")


@router.get("")
def get_proof(
    person_id: str = Query(...), metric: str = Query(...),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
    period_days: int = 30,
) -> ApiResponse:
    formula = FORMULAS.get(metric)
    if formula is None:
        raise HTTPException(status_code=400, detail=f"No proof available for metric '{metric}'")

    content = get_content_df()
    profiles = get_profiles_df()
    df = filter_content(content, person_ids=[person_id], platform=platform,
                         content_type=content_type, date_from=date_from, date_to=date_to)
    person_name = str(df["person_name"].iloc[0]) if not df.empty else person_id
    followers = latest_followers(profiles, person_id)

    base = {"person_id": person_id, "person_name": person_name, "metric": metric, "formula": formula}

    if metric == "followers":
        snap = profiles[profiles["person_id"] == person_id].sort_values("finished_at") \
            if not profiles.empty else profiles
        record_cols = [c for c in ["run_id", "platform", "followers", "followers_raw", "finished_at"]
                       if not snap.empty and c in snap.columns]
        records = snap.tail(1)[record_cols].where(pd.notnull(snap.tail(1)[record_cols]), None).to_dict(orient="records") \
            if not snap.empty else []
        return ApiResponse.ok({**base, "value": followers, "records": records})

    if metric in _CONTENT_TYPE_FOR_METRIC:
        subset = df[df["content_type"] == _CONTENT_TYPE_FOR_METRIC[metric]] if not df.empty else df
        return ApiResponse.ok({**base, "value": eng.calculate_total_content(subset),
                                "records": _rows(subset, sort_by="published_at")})

    if metric == "total_content":
        return ApiResponse.ok({**base, "value": eng.calculate_total_content(df),
                                "records": _rows(df, sort_by="published_at")})

    if metric in ("average_likes", "median_likes"):
        fn = eng.calculate_average_likes if metric == "average_likes" else eng.calculate_median_likes
        value = fn(df)
        contributing = df.dropna(subset=["likes"]) if "likes" in df.columns else df.iloc[0:0]
        return ApiResponse.ok({
            **base, "value": value,
            "sum": float(contributing["likes"].sum()) if not contributing.empty else None,
            "count": int(len(contributing)),
            "records": _rows(contributing, sort_by="likes"),
        })

    if metric == "total_likes":
        value = eng.calculate_sum_likes(df)
        contributing = df.dropna(subset=["likes"]) if "likes" in df.columns else df.iloc[0:0]
        return ApiResponse.ok({
            **base, "value": value,
            "count": int(len(contributing)),
            "records": _rows(contributing, sort_by="likes"),
        })

    if metric == "average_comments":
        value = eng.calculate_average_comments(df)
        contributing = df.dropna(subset=["comments_count"]) if "comments_count" in df.columns else df.iloc[0:0]
        return ApiResponse.ok({
            **base, "value": value,
            "sum": float(contributing["comments_count"].sum()) if not contributing.empty else None,
            "count": int(len(contributing)),
            "records": _rows(contributing, sort_by="comments_count"),
        })

    if metric == "total_comments_count":
        value = eng.calculate_sum_comments(df)
        contributing = df.dropna(subset=["comments_count"]) if "comments_count" in df.columns else df.iloc[0:0]
        return ApiResponse.ok({
            **base, "value": value,
            "count": int(len(contributing)),
            "records": _rows(contributing, sort_by="comments_count"),
        })

    if metric == "average_engagement":
        value = eng.calculate_average_engagement(df)
        with_eng = eng.with_engagement(df)
        contributing = with_eng.dropna(subset=["engagement"])
        return ApiResponse.ok({
            **base, "value": value,
            "sum": float(contributing["engagement"].sum()) if not contributing.empty else None,
            "count": int(len(contributing)),
            "records": _rows(contributing, sort_by="engagement"),
        })

    if metric == "total_engagement":
        value = eng.calculate_sum_engagement(df)
        with_eng = eng.with_engagement(df)
        contributing = with_eng.dropna(subset=["engagement"])
        return ApiResponse.ok({
            **base, "value": value,
            "count": int(len(contributing)),
            "records": _rows(contributing, sort_by="engagement"),
        })

    if metric == "view_engagement":
        subset = df[df["content_type"].isin(["post", "reel"])] if not df.empty else df
        value = eng.calculate_sum_views(subset)
        contributing = subset.dropna(subset=["view_count"]) if "view_count" in subset.columns else subset.iloc[0:0]
        return ApiResponse.ok({
            **base, "value": value,
            "count": int(len(contributing)),
            "records": _rows(contributing, sort_by="view_count"),
        })

    if metric == "engagement_rate":
        avg_engagement = eng.calculate_average_engagement(df)
        value = eng.calculate_engagement_rate(df, followers)
        with_eng = eng.with_engagement(df)
        contributing = with_eng.dropna(subset=["engagement"])
        return ApiResponse.ok({
            **base, "value": value, "average_engagement": avg_engagement, "followers": followers,
            "count": int(len(contributing)),
            "records": _rows(contributing, sort_by="engagement"),
        })

    if metric in ("posts_per_day", "posts_per_week", "reels_per_week"):
        subset = df[df["content_type"] == "reel"] if metric == "reels_per_week" and not df.empty else df
        freq = eng.calculate_posting_frequency(subset, period_days)
        value = freq["per_week"] if metric != "posts_per_day" else freq["per_day"]
        return ApiResponse.ok({
            **base, "value": value, "count": eng.calculate_total_content(subset), "period_days": period_days,
            "records": _rows(subset, sort_by="published_at"),
        })

    if metric == "active_days":
        return ApiResponse.ok({**base, "value": eng.calculate_active_days(df),
                                "records": _rows(df, sort_by="published_at")})

    if metric in ("longest_inactive_period_days", "median_interval_hours"):
        d = df.copy()
        d["_dt"] = eng.published_datetime_series(d) if not d.empty else d
        d = d.dropna(subset=["_dt"]).sort_values("_dt") if not d.empty else d
        gap_rows = d.to_dict(orient="records") if not d.empty else []
        gaps = []
        for prev, curr in zip(gap_rows, gap_rows[1:]):
            gap_days = (curr["_dt"] - prev["_dt"]).total_seconds() / 86400
            gaps.append({
                "from_content_id": prev.get("content_id"), "from_date": prev["_dt"].isoformat(),
                "to_content_id": curr.get("content_id"), "to_date": curr["_dt"].isoformat(),
                "gap_days": round(gap_days, 2), "gap_hours": round(gap_days * 24, 2),
            })
        if metric == "longest_inactive_period_days":
            value = eng.calculate_longest_inactive_period(df)
            gaps.sort(key=lambda g: g["gap_days"], reverse=True)
        else:
            value = eng.calculate_activity_consistency(df).get("median_interval_hours")
            gaps.sort(key=lambda g: g["gap_hours"], reverse=True)
        return ApiResponse.ok({**base, "value": value, "count": len(gaps), "records": gaps})

    if metric in ("most_active_day", "most_active_hour"):
        if metric == "most_active_day":
            counts = eng.calculate_activity_by_day(df)
            value = eng.most_active_day(df)
            records = [{"label": k, "count": v} for k, v in counts.items()]
        else:
            counts = eng.calculate_activity_by_hour(df)
            value = eng.most_active_hour(df)
            records = [{"label": f"{k}:00", "count": v} for k, v in sorted(counts.items())]
        records.sort(key=lambda r: r["count"], reverse=True)
        return ApiResponse.ok({**base, "value": value, "records": records})

    raise HTTPException(status_code=400, detail=f"No proof available for metric '{metric}'")
