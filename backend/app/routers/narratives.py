"""GET /api/narratives -- spec sections 20-22. Narrative statistics,
narrative x engagement scatter, and narrative trend over time.

Every value here comes from the `narrative` column, which is only populated
after POST /api/analysis/run has done an NLP pass -- if it hasn't run yet,
this returns empty tables and `analysis_available: false` rather than
fabricating narrative labels.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.analytics import engine as eng
from app.analytics.filters import filter_content
from app.models.common import ApiResponse
from app.storage.data_source import get_content_df

router = APIRouter(prefix="/api/narratives", tags=["narratives"])


def _narrative_table(df_a, df_b) -> list[dict]:
    all_narratives = set()
    if "narrative" in df_a.columns:
        all_narratives |= set(df_a["narrative"].dropna().unique())
    if "narrative" in df_b.columns:
        all_narratives |= set(df_b["narrative"].dropna().unique())

    total_a, total_b = len(df_a), len(df_b)
    rows = []
    for n in sorted(all_narratives):
        sub_a = df_a[df_a["narrative"] == n] if "narrative" in df_a.columns else df_a.iloc[0:0]
        sub_b = df_b[df_b["narrative"] == n] if "narrative" in df_b.columns else df_b.iloc[0:0]
        rows.append({
            "narrative": n,
            "person_a_count": len(sub_a),
            "person_a_pct": round(len(sub_a) / total_a * 100, 1) if total_a else None,
            "person_a_avg_engagement": eng.calculate_average_engagement(sub_a),
            "person_a_median_engagement": eng.calculate_median_engagement(sub_a),
            "person_b_count": len(sub_b),
            "person_b_pct": round(len(sub_b) / total_b * 100, 1) if total_b else None,
            "person_b_avg_engagement": eng.calculate_average_engagement(sub_b),
            "person_b_median_engagement": eng.calculate_median_engagement(sub_b),
        })
    return rows


def _scatter(df) -> list[dict]:
    if df.empty or "narrative" not in df.columns:
        return []
    df = eng.with_engagement(df)
    out = []
    for n, sub in df.dropna(subset=["narrative"]).groupby("narrative"):
        avg = eng.calculate_average_engagement(sub)
        if avg is None:
            continue
        out.append({"narrative": n, "content_volume": len(sub), "avg_engagement": avg, "post_count": len(sub)})
    return out


def _trend(df) -> list[dict]:
    if df.empty or "narrative" not in df.columns:
        return []
    dt = eng.published_datetime_series(df)
    tmp = df.assign(_month=dt.dt.to_period("M").astype(str)).dropna(subset=["narrative"])
    grouped = tmp.groupby(["_month", "narrative"]).size().reset_index(name="count")
    return grouped.to_dict(orient="records")


@router.get("")
def get_narratives(
    person_a: str = Query(...), person_b: str = Query(...),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
) -> ApiResponse:
    content = get_content_df()
    analysis_available = "narrative" in content.columns and content["narrative"].notna().any()

    df_a = filter_content(content, person_ids=[person_a], platform=platform,
                           content_type=content_type, date_from=date_from, date_to=date_to)
    df_b = filter_content(content, person_ids=[person_b], platform=platform,
                           content_type=content_type, date_from=date_from, date_to=date_to)

    return ApiResponse.ok({
        "analysis_available": bool(analysis_available),
        "table": _narrative_table(df_a, df_b),
        "scatter": {"person_a": _scatter(df_a), "person_b": _scatter(df_b)},
        "trend": {"person_a": _trend(df_a), "person_b": _trend(df_b)},
        "label": "Model-classified narrative" if analysis_available else None,
    })
