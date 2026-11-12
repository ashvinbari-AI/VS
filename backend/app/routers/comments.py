"""GET /api/comments -- spec sections 24-25. Comment stats, theme/issue
breakdown, and an issue drilldown. Never infers commenter location (section
25) -- only reports explicit issue topics and links back to post/person."""

from __future__ import annotations

import math

from fastapi import APIRouter, Query

from app.analytics import engine as eng
from app.analytics.filters import filter_comments_by_post
from app.models.common import ApiResponse
from app.routers.people_params import parse_person_ids
from app.storage.data_source import get_comments_df, get_content_df

router = APIRouter(prefix="/api/comments", tags=["comments"])

_LIST_COLUMNS = [
    "comment_id", "content_id", "person_id", "person_name", "platform",
    "author_username", "comment_text", "commented_at", "like_count",
    "sentiment", "theme",
]


def _issue_breakdown(comments_df, content_df) -> list[dict]:
    if comments_df.empty or "issues" not in comments_df.columns:
        return []
    exploded = comments_df.explode("issues").dropna(subset=["issues"])
    if exploded.empty:
        return []
    total = len(comments_df)
    rows = []
    for issue, sub in exploded.groupby("issues"):
        sentiment_counts = sub["sentiment"].dropna().value_counts().to_dict() if "sentiment" in sub else {}
        associated_people = sub["person_id"].dropna().unique().tolist() if "person_id" in sub else []
        associated_posts = sub["content_id"].dropna().unique().tolist()[:20]
        rows.append({
            "issue": issue, "mentions": len(sub),
            "percentage": round(len(sub) / total * 100, 2) if total else None,
            "sentiment_breakdown": sentiment_counts,
            "associated_people": associated_people,
            "associated_posts": associated_posts,
        })
    return sorted(rows, key=lambda r: r["mentions"], reverse=True)


@router.get("")
def get_comments(
    person_ids: list[str] = Query(...),
    platform: str | None = None,
) -> ApiResponse:
    ids = parse_person_ids(person_ids)
    comments = get_comments_df()
    content = get_content_df()
    if platform and platform.lower() != "all" and not comments.empty:
        comments = comments[comments["platform"] == platform.lower()]

    analysis_available = "theme" in comments.columns and comments["theme"].notna().any()

    def block(c_df, content_df):
        stats = eng.calculate_comment_statistics(c_df, content_df)
        return {
            **stats,
            "sentiment_breakdown": c_df["sentiment"].dropna().value_counts().to_dict()
                if "sentiment" in c_df.columns else {},
            "theme_breakdown": c_df["theme"].dropna().value_counts().to_dict()
                if "theme" in c_df.columns else {},
            "issues": _issue_breakdown(c_df, content_df),
        }

    people = {}
    for pid in ids:
        c_df = comments[comments["person_id"] == pid] if not comments.empty else comments
        content_df = content[content["person_id"] == pid] if not content.empty else content
        people[pid] = block(c_df, content_df)

    return ApiResponse.ok({
        "person_ids": ids,
        "analysis_available": bool(analysis_available),
        "label": "Model-classified theme/sentiment" if analysis_available else None,
        "people": people,
    })


@router.get("/list")
def list_comments(
    person_id: str = Query(...),
    platform: str | None = None,
    content_type: str | None = None,
    sentiment: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
    search: str | None = None,
    page: int = 1, page_size: int = 25,
) -> ApiResponse:
    """Paginated raw comments for one person -- the drilldown behind a
    sentiment donut slice (spec section 23/45: clicking a slice must let a
    reviewer see the actual text behind a model-assigned label, not just
    trust the count). content_type/date_from/date_to go through
    filter_comments_by_post -- see app/analytics/filters.py: a comment has
    no reliable timestamp of its own, so these apply to its parent post."""
    df = get_comments_df()
    if not df.empty:
        df = df[df["person_id"] == person_id]
    df = filter_comments_by_post(
        df, get_content_df(), platform=platform, content_type=content_type,
        date_from=date_from, date_to=date_to,
    )
    if not df.empty and sentiment:
        df = df[df["sentiment"] == sentiment]
    if not df.empty and search:
        needle = search.lower()
        df = df[df["comment_text"].fillna("").str.lower().str.contains(needle, regex=False)]

    if df.empty:
        return ApiResponse.ok({"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1})

    df = df.sort_values("commented_at", ascending=False, na_position="last")
    total = len(df)
    start = max(0, (page - 1) * page_size)
    page_df = df.iloc[start:start + page_size]

    cols = [c for c in _LIST_COLUMNS if c in page_df.columns]
    records = page_df[cols].to_dict(orient="records")
    for r in records:
        for k, v in list(r.items()):
            if isinstance(v, float) and math.isnan(v):
                r[k] = None

    return ApiResponse.ok({
        "items": records, "total": total, "page": page, "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size else 1,
    })


@router.get("/issues/{issue}")
def get_issue_drilldown(issue: str, person_ids: list[str] = Query(...)) -> ApiResponse:
    ids = parse_person_ids(person_ids)
    comments = get_comments_df()
    if comments.empty or "issues" not in comments.columns:
        return ApiResponse.ok({"issue": issue, "items": []})
    matching = comments[comments["issues"].apply(lambda v: isinstance(v, list) and issue in v)]
    matching = matching[matching["person_id"].isin(ids)]
    items = matching[["content_id", "commented_at", "person_id", "person_name", "platform",
                       "comment_text", "sentiment"]].to_dict(orient="records") if not matching.empty else []
    return ApiResponse.ok({"issue": issue, "items": items, "total": len(items)})
