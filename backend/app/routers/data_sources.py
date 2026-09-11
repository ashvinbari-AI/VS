"""GET /api/data-sources -- spec section 29."""

from __future__ import annotations

from fastapi import APIRouter

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
            if not p_runs.empty:
                sorted_runs = p_runs.sort_values("finished_at")
                last_scraped = sorted_runs.iloc[-1].get("finished_at")
                for e in p_runs["errors"]:
                    if isinstance(e, list):
                        errors.extend(e)

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
            })

    return ApiResponse.ok({"demo_mode": is_demo_mode(), "sources": rows})
