"""GET /api/overview -- spec sections 11/12. Top KPI cards + the six
overview charts, computed for every selected person (2..N) over the filtered window."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.analytics import engine as eng
from app.analytics.filters import filter_content
from app.models.common import ApiResponse
from app.routers.people_params import parse_person_ids
from app.storage.data_source import get_comments_df, get_content_df, get_profiles_df, latest_followers

router = APIRouter(prefix="/api/overview", tags=["overview"])


def _person_kpis(df, comments_df, followers) -> dict:
    type_dist = eng.calculate_content_type_distribution(df)
    return {
        "followers": followers,
        "total_content": eng.calculate_total_content(df),
        "posts": type_dist.get("post", 0),
        "reels": type_dist.get("reel", 0),
        "videos": type_dist.get("video", 0),
        "photos": type_dist.get("photo", 0),
        "average_likes": eng.calculate_average_likes(df),
        "median_likes": eng.calculate_median_likes(df),
        "total_likes": eng.calculate_sum_likes(df),
        "average_comments": eng.calculate_average_comments(df),
        "median_comments": eng.calculate_median_comments(df),
        "total_comments_count": eng.calculate_sum_comments(df),
        "average_engagement": eng.calculate_average_engagement(df),
        "total_engagement": eng.calculate_sum_engagement(df),
        "engagement_rate": eng.calculate_engagement_rate(df, followers),
        "view_engagement": eng.calculate_sum_views(df[df["content_type"].isin(["post", "reel"])]) if not df.empty else None,
        "total_comments": int(len(comments_df)) if comments_df is not None else None,
    }


@router.get("")
def get_overview(
    person_ids: list[str] = Query(...),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
) -> ApiResponse:
    ids = parse_person_ids(person_ids)
    content = get_content_df()
    comments = get_comments_df()
    profiles = get_profiles_df()

    dfs = {
        pid: filter_content(content, person_ids=[pid], platform=platform,
                            content_type=content_type, date_from=date_from, date_to=date_to)
        for pid in ids
    }
    person_comments = {
        pid: comments[comments["person_id"] == pid] if not comments.empty else comments
        for pid in ids
    }
    followers = {pid: latest_followers(profiles, pid) for pid in ids}

    kpis = {pid: _person_kpis(dfs[pid], person_comments[pid], followers[pid]) for pid in ids}

    # 1. Content activity timeline (daily post counts, every person).
    # Rows are {"date": ..., <person_id>: value, ...} so a chart can use each
    # person_id directly as a series dataKey.
    def daily_counts(df):
        if df.empty:
            return {}
        dt = eng.published_datetime_series(df).dropna()
        return dt.dt.date.astype(str).value_counts().sort_index().to_dict()

    timelines = {pid: daily_counts(dfs[pid]) for pid in ids}
    all_dates = sorted(set().union(*timelines.values()))
    content_timeline = [{"date": d, **{pid: timelines[pid].get(d, 0) for pid in ids}} for d in all_dates]

    # 2. Engagement timeline (daily avg engagement)
    def daily_engagement(df):
        if df.empty:
            return {}
        df = eng.with_engagement(df)
        dt = eng.published_datetime_series(df)
        tmp = df.assign(_date=dt.dt.date.astype(str))
        return tmp.groupby("_date")["engagement"].mean().round(1).to_dict()

    engagement_daily = {pid: daily_engagement(dfs[pid]) for pid in ids}
    all_eng_dates = sorted(set().union(*engagement_daily.values()))
    engagement_timeline = [{"date": d, **{pid: engagement_daily[pid].get(d) for pid in ids}}
                           for d in all_eng_dates]

    # 3. Platform distribution
    platform_distribution = {pid: eng.calculate_platform_distribution(dfs[pid]) for pid in ids}

    # 4. Content type distribution
    content_type_distribution = {pid: eng.calculate_content_type_distribution(dfs[pid]) for pid in ids}

    # 5. Engagement comparison (grouped bar: total likes/comments/shares/engagement)
    engagement_comparison = {
        pid: {
            "total_likes": eng.calculate_sum_likes(dfs[pid]),
            "total_comments": eng.calculate_sum_comments(dfs[pid]),
            "total_shares": eng.calculate_sum_shares(dfs[pid]),
            "total_engagement": eng.calculate_sum_engagement(dfs[pid]),
        }
        for pid in ids
    }

    # 6. Top performing content (all selected people combined, top 10 by engagement)
    combined = eng.with_engagement(content) if not content.empty else content
    if not combined.empty:
        combined = combined[combined["person_id"].isin(ids)]
        top = combined.sort_values("engagement", ascending=False, na_position="last").head(10)
        top_content = top[["person_id", "person_name", "platform", "content_type",
                            "published_at", "likes", "comments_count", "engagement",
                            "content_id", "content_url"]].to_dict(orient="records")
    else:
        top_content = []

    return ApiResponse.ok({
        "person_ids": ids,
        "kpis": kpis,
        "charts": {
            "content_activity_timeline": content_timeline,
            "engagement_timeline": engagement_timeline,
            "platform_distribution": platform_distribution,
            "content_type_distribution": content_type_distribution,
            "engagement_comparison": engagement_comparison,
            "top_content": top_content,
        },
    })
