"""GET /api/content (Content Explorer / Top Content), GET /api/content/{id}
(detail drawer + evidence), GET /api/content/{id}/raw (raw audit record).
Spec sections 17-19/28/42."""

from __future__ import annotations

import json
import math

from fastapi import APIRouter, HTTPException, Query

from app.analytics import engine as eng
from app.analytics.filters import filter_content
from app.models.common import ApiResponse
from app.storage.data_source import get_comments_df, get_content_df

router = APIRouter(prefix="/api/content", tags=["content"])

_SORTABLE = {"published_at", "likes", "comments_count", "engagement", "shares"}


def _clean_records(df) -> list[dict]:
    if df.empty:
        return []
    records = df.to_dict(orient="records")
    for r in records:
        for k, v in list(r.items()):
            if isinstance(v, float) and math.isnan(v):
                r[k] = None
    return records


@router.get("")
def list_content(
    person_ids: list[str] | None = Query(None),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
    narrative: str | None = None, sentiment: str | None = None,
    min_likes: int | None = None, min_comments: int | None = None,
    min_engagement: float | None = None, search: str | None = None,
    sort_by: str = "published_at", sort_dir: str = "desc",
    page: int = 1, page_size: int = 25,
) -> ApiResponse:
    df = get_content_df()
    df = filter_content(df, person_ids=person_ids, platform=platform, content_type=content_type,
                         date_from=date_from, date_to=date_to, narrative=narrative,
                         sentiment=sentiment, min_likes=min_likes, min_comments=min_comments,
                         min_engagement=min_engagement, search=search)
    if df.empty:
        return ApiResponse.ok({"items": [], "total": 0, "page": page, "page_size": page_size})

    df = eng.with_engagement(df)
    sort_col = sort_by if sort_by in _SORTABLE and sort_by in df.columns else "published_at"
    df = df.sort_values(sort_col, ascending=(sort_dir == "asc"), na_position="last")

    total = len(df)
    start = max(0, (page - 1) * page_size)
    page_df = df.iloc[start:start + page_size]

    return ApiResponse.ok({
        "items": _clean_records(page_df),
        "total": total, "page": page, "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size else 1,
    })


@router.get("/{content_id}")
def get_content_detail(content_id: str) -> ApiResponse:
    df = get_content_df()
    row = df[df["content_id"] == content_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="Content not found")
    record = _clean_records(row)[0]
    record["engagement"] = eng.compute_engagement_series(row).iloc[0]
    if isinstance(record["engagement"], float) and math.isnan(record["engagement"]):
        record["engagement"] = None
    record["engagement_rate_pct"] = None
    if record.get("followers_at_collection"):
        eng_val = record["engagement"]
        if eng_val is not None:
            record["engagement_rate_pct"] = round(eng_val / record["followers_at_collection"] * 100, 4)

    comments_df = get_comments_df()
    matching_comments = comments_df[comments_df["content_id"] == content_id] if not comments_df.empty else comments_df
    comments = _clean_records(matching_comments.sort_values("commented_at", na_position="last")
                               if not matching_comments.empty else matching_comments)

    return ApiResponse.ok({"content": record, "comments": comments})


@router.get("/{content_id}/raw")
def get_content_raw(content_id: str) -> ApiResponse:
    """The literal scraped JSONL line(s) this record and its comments came
    from -- the audit/evidence trail (spec sections 7/19/42)."""
    df = get_content_df()
    row = df[df["content_id"] == content_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="Content not found")
    source_file = row.iloc[0]["raw_source_file"]

    raw_post = None
    try:
        with open(source_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                doc = json.loads(line)
                if str(doc.get("post_id")) == content_id:
                    raw_post = doc
                    break
    except OSError:
        pass

    return ApiResponse.ok({"raw_source_file": source_file, "raw_record": raw_post})
