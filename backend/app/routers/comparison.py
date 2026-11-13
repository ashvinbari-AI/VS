"""GET /api/comparison -- spec sections 13/32/63/64/65/66."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.analytics import engine as eng
from app.analytics.comparison import calculate_multi_comparison
from app.analytics.filters import filter_content
from app.models.common import ApiResponse
from app.routers.people_params import parse_person_ids
from app.storage.data_source import get_comments_df, get_content_df, get_profiles_df, latest_followers

router = APIRouter(prefix="/api/comparison", tags=["comparison"])

# Normalized Analytics Index dimensions (spec section 64). Each is a 0-100
# min-max normalization of a deterministic metric already computed above --
# NOT a political score, just a display convenience for the radar chart.
_RADAR_METRIC_MAP = {
    "Activity": "posting_frequency_per_day",
    "Engagement": "average_engagement",
    "Audience": "followers",
    "Content volume": "total_content",
    "Comment response": "average_comments",
}


def _normalize(values: dict[str, float | None]) -> dict[str, float | None]:
    """Scale every person's value so the highest = 100. If anyone's value is
    missing the whole dimension is left unnormalized (None) rather than
    scaled against an incomplete set."""
    if any(v is None for v in values.values()):
        return {pid: None for pid in values}
    hi = max([*values.values(), 1e-9])
    return {pid: round(v / hi * 100, 1) for pid, v in values.items()}


@router.get("")
def get_comparison(
    person_ids: list[str] = Query(...),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
    period_days: int = 30,
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

    result = calculate_multi_comparison(ids, dfs, person_comments, followers, period_days)
    people = result["people"]

    radar = {}
    for dim, metric_key in _RADAR_METRIC_MAP.items():
        raw = {pid: (followers[pid] if metric_key == "followers" else people[pid][metric_key]) for pid in ids}
        radar[dim] = {"values": _normalize(raw), "raw": raw}

    return ApiResponse.ok({
        "person_ids": ids,
        **result,
        "activity_consistency": {pid: eng.calculate_activity_consistency(dfs[pid]) for pid in ids},
        "normalized_analytics_index": {
            "note": "Each dimension is a min-max normalization (0-100) of a deterministic "
                    "metric, scaled to the highest of the selected people = 100. This is a "
                    "display convenience, not a political influence score.",
            "dimensions": radar,
        },
    })
