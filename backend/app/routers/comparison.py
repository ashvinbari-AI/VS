"""GET /api/comparison -- spec sections 13/32/63/64/65/66."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.analytics import engine as eng
from app.analytics.comparison import calculate_comparison_metrics
from app.analytics.filters import filter_content
from app.models.common import ApiResponse
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


def _normalize_pair(a: float | None, b: float | None) -> tuple[float | None, float | None]:
    if a is None or b is None:
        return None, None
    hi = max(a, b, 1e-9)
    return round(a / hi * 100, 1), round(b / hi * 100, 1)


@router.get("")
def get_comparison(
    person_a: str = Query(...), person_b: str = Query(...),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
    period_days: int = 30,
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

    result = calculate_comparison_metrics(
        person_a, person_b, df_a, df_b, comments_a, comments_b,
        followers_a, followers_b, period_days,
    )

    # Narrative diversity (needs narrative column, added by NLP pass if it ran)
    def diversity(df):
        if "narrative" not in df.columns or df.empty:
            return None
        counts = df["narrative"].dropna().value_counts().to_dict()
        return eng.calculate_narrative_diversity(counts) if counts else None

    # Activity consistency
    consistency_a = eng.calculate_activity_consistency(df_a)
    consistency_b = eng.calculate_activity_consistency(df_b)

    radar_raw = {
        "Activity": (result["person_a"]["posting_frequency_per_day"],
                     result["person_b"]["posting_frequency_per_day"]),
        "Engagement": (result["person_a"]["average_engagement"],
                       result["person_b"]["average_engagement"]),
        "Audience": (followers_a, followers_b),
        "Content volume": (result["person_a"]["total_content"], result["person_b"]["total_content"]),
        "Comment response": (result["person_a"]["average_comments"], result["person_b"]["average_comments"]),
    }
    radar = {}
    for dim, (a, b) in radar_raw.items():
        na, nb = _normalize_pair(a, b)
        radar[dim] = {"person_a": na, "person_b": nb, "raw_person_a": a, "raw_person_b": b}

    return ApiResponse.ok({
        **result,
        "narrative_diversity": {"person_a": diversity(df_a), "person_b": diversity(df_b)},
        "activity_consistency": {"person_a": consistency_a, "person_b": consistency_b},
        "normalized_analytics_index": {
            "note": "Each dimension is a min-max normalization (0-100) of a deterministic "
                    "metric, scaled to the higher of the two people = 100. This is a display "
                    "convenience, not a political influence score.",
            "dimensions": radar,
        },
    })
