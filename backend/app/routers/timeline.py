"""GET /api/timeline -- spec section 27. Paginated chronological feed."""

from __future__ import annotations

import math

from fastapi import APIRouter, Query

from app.analytics import engine as eng
from app.analytics.filters import filter_content
from app.models.common import ApiResponse
from app.storage.data_source import get_content_df

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


@router.get("")
def get_timeline(
    person_ids: list[str] | None = Query(None),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
    narrative: str | None = None, sentiment: str | None = None,
    min_engagement: float | None = None,
    page: int = 1, page_size: int = 30,
) -> ApiResponse:
    df = get_content_df()
    df = filter_content(df, person_ids=person_ids, platform=platform, content_type=content_type,
                         date_from=date_from, date_to=date_to, narrative=narrative,
                         sentiment=sentiment, min_engagement=min_engagement)
    if df.empty:
        return ApiResponse.ok({"items": [], "total": 0, "page": page, "page_size": page_size})

    df = eng.with_engagement(df)
    df = df.sort_values("published_at", ascending=False, na_position="last")
    total = len(df)
    start = (page - 1) * page_size
    page_df = df.iloc[start:start + page_size]

    import pandas as pd
    records = page_df.to_dict(orient="records")
    for r in records:
        for k, v in list(r.items()):
            if isinstance(v, float) and pd.isna(v):
                r[k] = None

    return ApiResponse.ok({
        "items": records, "total": total, "page": page, "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size else 1,
    })
