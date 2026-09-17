"""GET /api/data-sources -- spec section 29."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.models.common import ApiResponse
from app.storage import json_store
from app.storage.data_source import get_comments_df, get_content_df, get_profiles_df, is_demo_mode

router = APIRouter(prefix="/api/data-sources", tags=["data-sources"])


@router.get("")
def get_data_sources() -> ApiResponse:
    content = get_content_df()
    comments = get_comments_df()
    profiles = get_profiles_df()
    people = json_store.list_people()

    rows = []
    for person in people:
        pid = person["id"]
        for platform in ("instagram", "facebook"):
            url = person.get(f"{platform}_url")
            p_content = content[(content["person_id"] == pid) & (content["platform"] == platform)] \
                if not content.empty else content
            p_comments = comments[(comments["person_id"] == pid) & (comments["platform"] == platform)] \
                if not comments.empty else comments
            p_runs = profiles[(profiles["person_id"] == pid) & (profiles["platform"] == platform)] \
                if not profiles.empty else profiles

            last_scraped = None
            errors: list[str] = []
            scrape_window_since = None
            scrape_window_until = None
            if not p_runs.empty:
                sorted_runs = p_runs.sort_values("finished_at")
                last_scraped = sorted_runs.iloc[-1].get("finished_at")
                scrape_window_since = sorted_runs.iloc[-1].get("since")
                scrape_window_until = sorted_runs.iloc[-1].get("until")
                for e in p_runs["errors"]:
                    if isinstance(e, list):
                        errors.extend(e)

            # The actual span of collected content -- distinct from the
            # --since/--until window that was *requested* of the scraper
            # (scrape_window_* above): a person who simply didn't post as
            # often as the window allows will show a narrower span here,
            # which is a fact about them, not a scraper failure.
            earliest_post = None
            latest_post = None
            days_of_content = None
            if not p_content.empty:
                published = pd.to_datetime(p_content["published_at"], errors="coerce", utc=True).dropna()
                if not published.empty:
                    earliest_post = published.min().isoformat()
                    latest_post = published.max().isoformat()
                    days_of_content = int((published.max() - published.min()).days)

            if not url:
                status = "not_configured"
            elif len(p_content) == 0 and p_runs.empty:
                status = "not_loaded"
            elif len(p_content) == 0:
                status = "partial"
            else:
                status = "loaded"

            rows.append({
                "person_id": pid, "person_name": person["name"], "platform": platform,
                "profile_url": url, "last_scraped": last_scraped,
                "content_count": int(len(p_content)), "comments_count": int(len(p_comments)),
                "status": status, "errors": errors,
                "earliest_post": earliest_post, "latest_post": latest_post,
                "days_of_content": days_of_content,
                "scrape_window_since": scrape_window_since, "scrape_window_until": scrape_window_until,
            })

    return ApiResponse.ok({"demo_mode": is_demo_mode(), "sources": rows})


@router.get("/{person_id}/history")
def get_scrape_history(person_id: str) -> ApiResponse:
    """Every scrape run ever recorded for this person, both platforms,
    newest first -- the full scrape_runs.jsonl history (spec section 42's
    evidence-trail principle applied to runs, not just individual posts),
    not just the single "last scraped" timestamp the summary table shows."""
    person = json_store.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    profiles = get_profiles_df()
    p_runs = profiles[profiles["person_id"] == person_id] if not profiles.empty else profiles
    if p_runs.empty:
        return ApiResponse.ok({"person_id": person_id, "person_name": person["name"], "runs": []})

    cols = [c for c in ["run_id", "platform", "since", "until", "started_at", "finished_at",
                        "followers", "followers_raw", "posts_scanned", "comments_new", "errors"]
            if c in p_runs.columns]
    runs = p_runs[cols].sort_values("finished_at", ascending=False)
    runs = runs.where(pd.notnull(runs), None).to_dict(orient="records")
    return ApiResponse.ok({"person_id": person_id, "person_name": person["name"], "runs": runs})
