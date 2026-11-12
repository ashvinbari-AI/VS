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
from app.routers.people_params import parse_person_ids
from app.storage.data_source import get_content_df

router = APIRouter(prefix="/api/narratives", tags=["narratives"])


def _narrative_table(dfs: dict) -> list[dict]:
    """One row per narrative; `people` holds each selected person's count,
    share of their own content, and avg/median engagement on it."""
    all_narratives: set = set()
    for df in dfs.values():
        if "narrative" in df.columns:
            all_narratives |= set(df["narrative"].dropna().unique())

    rows = []
    for n in sorted(all_narratives):
        people = {}
        for pid, df in dfs.items():
            sub = df[df["narrative"] == n] if "narrative" in df.columns else df.iloc[0:0]
            total = len(df)
            people[pid] = {
                "count": len(sub),
                "pct": round(len(sub) / total * 100, 1) if total else None,
                "avg_engagement": eng.calculate_average_engagement(sub),
                "median_engagement": eng.calculate_median_engagement(sub),
            }
        rows.append({"narrative": n, "people": people})
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
    person_ids: list[str] = Query(...),
    platform: str | None = None, content_type: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
) -> ApiResponse:
    ids = parse_person_ids(person_ids)
    content = get_content_df()
    analysis_available = "narrative" in content.columns and content["narrative"].notna().any()

    dfs = {
        pid: filter_content(content, person_ids=[pid], platform=platform,
                            content_type=content_type, date_from=date_from, date_to=date_to)
        for pid in ids
    }

    return ApiResponse.ok({
        "person_ids": ids,
        "analysis_available": bool(analysis_available),
        "table": _narrative_table(dfs),
        "scatter": {pid: _scatter(dfs[pid]) for pid in ids},
        "trend": {pid: _trend(dfs[pid]) for pid in ids},
        "label": "Model-classified narrative" if analysis_available else None,
    })
