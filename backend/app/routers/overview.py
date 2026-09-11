"""GET /api/overview -- spec sections 11/12. Top KPI cards + the six
overview charts, computed for Person A vs Person B over the filtered window."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.analytics import engine as eng
from app.analytics.filters import filter_content
from app.models.common import ApiResponse
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
        "average_comments": eng.calculate_average_comments(df),
        "median_comments": eng.calculate_median_comments(df),
        "average_engagement": eng.calculate_average_engagement(df),
        "engagement_rate": eng.calculate_engagement_rate(df, followers),
        "total_comments": int(len(comments_df)) if comments_df is not None else None,
    }


@router.get("")
def get_overview(
    person_a: str = Query(...), person_b: str = Query(...),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
) -> ApiResponse:
    content = get_content_df()
    comments = get_comments_df()
    profiles = get_profiles_df()

    df_a = filter_content(content, person_ids=[person_a], platform=platform,
                           content_type=content_type, date_from=date_from, date_to=date_to)
    df_b = filter_content(content, person_ids=[person_b], platform=platform,
                           content_type=content_type, date_from=date_from, date_to=date_to)
    comments_a = comments[comments["person_id"] == person_a] if not comments.empty else comments
    comments_b = comments[comments["person_id"] == person_b] if not comments.empty else comments

    followers_a = latest_followers(profiles, person_a)
    followers_b = latest_followers(profiles, person_b)

    kpis = {
        "person_a": _person_kpis(df_a, comments_a, followers_a),
        "person_b": _person_kpis(df_b, comments_b, followers_b),
    }

    # 1. Content activity timeline (daily post counts, both people)
    def daily_counts(df):
        if df.empty:
            return {}
        dt = eng.published_datetime_series(df).dropna()
        return dt.dt.date.astype(str).value_counts().sort_index().to_dict()

    timeline_a, timeline_b = daily_counts(df_a), daily_counts(df_b)
    all_dates = sorted(set(timeline_a) | set(timeline_b))
    content_timeline = [{"date": d, "person_a": timeline_a.get(d, 0), "person_b": timeline_b.get(d, 0)}
                         for d in all_dates]

    # 2. Engagement timeline (daily avg engagement)
    def daily_engagement(df):
        if df.empty:
            return {}
        df = eng.with_engagement(df)
        dt = eng.published_datetime_series(df)
        tmp = df.assign(_date=dt.dt.date.astype(str))
        return tmp.groupby("_date")["engagement"].mean().round(1).to_dict()

    eng_a, eng_b = daily_engagement(df_a), daily_engagement(df_b)
    all_eng_dates = sorted(set(eng_a) | set(eng_b))
    engagement_timeline = [{"date": d, "person_a": eng_a.get(d), "person_b": eng_b.get(d)}
                            for d in all_eng_dates]

    # 3. Platform distribution
    platform_distribution = {
        "person_a": eng.calculate_platform_distribution(df_a),
        "person_b": eng.calculate_platform_distribution(df_b),
    }

    # 4. Content type distribution
    content_type_distribution = {
        "person_a": eng.calculate_content_type_distribution(df_a),
        "person_b": eng.calculate_content_type_distribution(df_b),
    }

    # 5. Engagement comparison (grouped bar: avg likes/comments/shares/engagement)
    engagement_comparison = {
        "person_a": {
            "avg_likes": eng.calculate_average_likes(df_a),
            "avg_comments": eng.calculate_average_comments(df_a),
            "avg_shares": eng.calculate_average_shares(df_a),
            "avg_engagement": eng.calculate_average_engagement(df_a),
        },
        "person_b": {
            "avg_likes": eng.calculate_average_likes(df_b),
            "avg_comments": eng.calculate_average_comments(df_b),
            "avg_shares": eng.calculate_average_shares(df_b),
            "avg_engagement": eng.calculate_average_engagement(df_b),
        },
    }

    # 6. Top performing content (both people combined, top 10 by engagement)
    combined = eng.with_engagement(content) if not content.empty else content
    if not combined.empty:
        combined = combined[combined["person_id"].isin([person_a, person_b])]
        top = combined.sort_values("engagement", ascending=False, na_position="last").head(10)
        top_content = top[["person_id", "person_name", "platform", "content_type",
                            "published_at", "likes", "comments_count", "engagement",
                            "content_id", "content_url"]].to_dict(orient="records")
    else:
        top_content = []

    return ApiResponse.ok({
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
