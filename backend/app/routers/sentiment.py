"""GET /api/sentiment -- spec section 23. Always labeled model-classified,
never presented as ground truth (see the `label` field in the response).

Comment Sentiment is the only sentiment this app classifies (post-level
sentiment was removed -- see app/nlp/engine.py) -- this endpoint only ever
returns comment-derived numbers, never content/post ones. platform/
content_type/date filtering is applied via filter_comments_by_post (see
app/analytics/filters.py for why: comments have no reliable timestamp of
their own, so date/content_type filters go through the parent post)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.analytics.filters import filter_comments_by_post
from app.models.common import ApiResponse
from app.routers.people_params import parse_person_ids
from app.storage.data_source import get_comments_df, get_content_df

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])


def _distribution(df, col: str) -> dict:
    if df.empty or col not in df.columns:
        return {}
    return df[col].dropna().value_counts().to_dict()


@router.get("")
def get_sentiment(
    person_ids: list[str] = Query(...),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
) -> ApiResponse:
    ids = parse_person_ids(person_ids)
    comments = get_comments_df()
    content = get_content_df()
    analysis_available = "sentiment" in comments.columns and comments["sentiment"].notna().any()

    filtered = filter_comments_by_post(
        comments, content, platform=platform, content_type=content_type,
        date_from=date_from, date_to=date_to,
    )

    def for_person(pid):
        return filtered[filtered["person_id"] == pid] if not filtered.empty else filtered

    return ApiResponse.ok({
        "person_ids": ids,
        "analysis_available": bool(analysis_available),
        "label": "Model-classified sentiment" if analysis_available else None,
        "comment_sentiment": {pid: _distribution(for_person(pid), "sentiment") for pid in ids},
    })
