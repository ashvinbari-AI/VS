"""GET /api/comments -- spec sections 24-25. Comment stats, theme/issue
breakdown, and an issue drilldown. Never infers commenter location (section
25) -- only reports explicit issue topics and links back to post/person."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.analytics import engine as eng
from app.models.common import ApiResponse
from app.storage.data_source import get_comments_df, get_content_df

router = APIRouter(prefix="/api/comments", tags=["comments"])


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
    person_a: str = Query(...), person_b: str = Query(...),
    platform: str | None = None,
) -> ApiResponse:
    comments = get_comments_df()
    content = get_content_df()
    if platform and platform.lower() != "all" and not comments.empty:
        comments = comments[comments["platform"] == platform.lower()]

    comments_a = comments[comments["person_id"] == person_a] if not comments.empty else comments
    comments_b = comments[comments["person_id"] == person_b] if not comments.empty else comments
    content_a = content[content["person_id"] == person_a] if not content.empty else content
    content_b = content[content["person_id"] == person_b] if not content.empty else content

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

    return ApiResponse.ok({
        "analysis_available": bool(analysis_available),
        "label": "Model-classified theme/sentiment" if analysis_available else None,
        "person_a": block(comments_a, content_a),
        "person_b": block(comments_b, content_b),
    })


@router.get("/issues/{issue}")
def get_issue_drilldown(issue: str, person_a: str = Query(...), person_b: str = Query(...)) -> ApiResponse:
    comments = get_comments_df()
    if comments.empty or "issues" not in comments.columns:
        return ApiResponse.ok({"issue": issue, "items": []})
    matching = comments[comments["issues"].apply(lambda v: isinstance(v, list) and issue in v)]
    matching = matching[matching["person_id"].isin([person_a, person_b])]
    items = matching[["content_id", "commented_at", "person_id", "person_name", "platform",
                       "comment_text", "sentiment"]].to_dict(orient="records") if not matching.empty else []
    return ApiResponse.ok({"issue": issue, "items": items, "total": len(items)})
