"""GET /api/sentiment -- spec section 23. Always labeled model-classified,
never presented as ground truth (see the `label` field in the response)."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Query

from app.analytics import engine as eng
from app.analytics.filters import filter_content
from app.models.common import ApiResponse
from app.storage.data_source import get_comments_df, get_content_df

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])


def _distribution(df, col: str) -> dict:
    if df.empty or col not in df.columns:
        return {}
    return df[col].dropna().value_counts().to_dict()


def _timeline(df, col: str) -> list[dict]:
    if df.empty or col not in df.columns:
        return []
    date_col = "published_at" if "published_at" in df.columns else "commented_at"
    dt = eng.published_datetime_series(df) if date_col == "published_at" else \
        pd.to_datetime(df[date_col], errors="coerce", utc=True)
    tmp = df.assign(_date=dt.dt.date.astype(str)).dropna(subset=[col])
    grouped = tmp.groupby(["_date", col]).size().reset_index(name="count")
    return grouped.to_dict(orient="records")


@router.get("")
def get_sentiment(
    person_a: str = Query(...), person_b: str = Query(...),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
) -> ApiResponse:
    content = get_content_df()
    comments = get_comments_df()
    analysis_available = "sentiment" in content.columns and content["sentiment"].notna().any()

    df_a = filter_content(content, person_ids=[person_a], platform=platform,
                           content_type=content_type, date_from=date_from, date_to=date_to)
    df_b = filter_content(content, person_ids=[person_b], platform=platform,
                           content_type=content_type, date_from=date_from, date_to=date_to)
    comments_a = comments[comments["person_id"] == person_a] if not comments.empty else comments
    comments_b = comments[comments["person_id"] == person_b] if not comments.empty else comments

    # narrative x sentiment cross-tab
    def cross(df):
        if df.empty or "narrative" not in df.columns or "sentiment" not in df.columns:
            return []
        grouped = df.dropna(subset=["narrative", "sentiment"]).groupby(
            ["narrative", "sentiment"]).size().reset_index(name="count")
        return grouped.to_dict(orient="records")

    return ApiResponse.ok({
        "analysis_available": bool(analysis_available),
        "label": "Model-classified sentiment" if analysis_available else None,
        "post_sentiment": {"person_a": _distribution(df_a, "sentiment"), "person_b": _distribution(df_b, "sentiment")},
        "comment_sentiment": {"person_a": _distribution(comments_a, "sentiment"),
                              "person_b": _distribution(comments_b, "sentiment")},
        "post_sentiment_timeline": {"person_a": _timeline(df_a, "sentiment"), "person_b": _timeline(df_b, "sentiment")},
        "narrative_x_sentiment": {"person_a": cross(df_a), "person_b": cross(df_b)},
    })
