"""POST /api/scrape/start, GET /api/scrape/status/{job_id}, and the
'Load Existing Data' import endpoint (spec sections 5/6/48)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.ingestion.import_existing import import_existing_output
from app.jobs.manager import Job, create_job, get_job, run_job, set_progress, set_status_message
from app.models.common import ApiResponse
from app.scrapers.facebook_adapter import FacebookAdapter
from app.scrapers.instagram_adapter import InstagramAdapter
from app.storage import json_store
from app.storage.paths import person_raw_dir

router = APIRouter(prefix="/api/scrape", tags=["scrape"])


class ScrapeStartRequest(BaseModel):
    person_id: str
    platforms: list[str] = ["instagram", "facebook"]
    days: int | None = 30
    since: str | None = None
    until: str | None = None
    headed: bool = True
    no_comments: bool = False
    max_comments: int | None = None
    limit: int | None = None


class ImportExistingRequest(BaseModel):
    person_id: str
    platform: str
    source_dir: str


@router.post("/start")
def start_scrape(payload: ScrapeStartRequest) -> ApiResponse:
    person = json_store.get_person(payload.person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found -- save the person config first")

    job = create_job("scrape")

    def _work(job: Job) -> dict:
        results = {}
        adapters = {"instagram": InstagramAdapter(), "facebook": FacebookAdapter()}
        for platform in payload.platforms:
            url = person.get(f"{platform}_url")
            if not url:
                results[platform] = {"ok": False, "error": f"No {platform} URL configured for this person"}
                continue
            adapter = adapters[platform]
            valid, reason = adapter.validate_profile(url)
            if not valid:
                results[platform] = {"ok": False, "error": reason}
                continue

            out_dir = person_raw_dir(payload.person_id, platform)
            set_status_message(job, f"Scraping {platform}...")

            def on_progress(line: str, pct: int | None, _platform=platform) -> None:
                set_progress(job, _platform, pct)
                set_status_message(job, f"[{_platform}] {line}"[:200])

            kwargs = dict(days=payload.days, since=payload.since, until=payload.until,
                          limit=payload.limit, max_comments=payload.max_comments,
                          no_comments=payload.no_comments, headed=payload.headed,
                          on_progress=on_progress)
            result = adapter.collect_content(url, out_dir, **kwargs)
            results[platform] = {"ok": result.ok, "error": result.error,
                                  "tail": result.stdout_tail}
            set_progress(job, platform, 100 if result.ok else None)
        return results

    run_job(job, _work)
    return ApiResponse.ok({"job_id": job.id})


@router.get("/status/{job_id}")
def scrape_status(job_id: str) -> ApiResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return ApiResponse.ok(job.to_dict())


@router.post("/import")
def import_existing(payload: ImportExistingRequest) -> ApiResponse:
    """'Load Existing Data' -- copies an already-scraped output folder
    (e.g. this project's own ./output/instagram) into the person's raw
    evidence tree, without touching or deleting the source."""
    person = json_store.get_person(payload.person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found -- save the person config first")
    result = import_existing_output(payload.person_id, payload.platform, payload.source_dir)
    if not result["ok"]:
        return ApiResponse.fail("IMPORT_FAILED", result["error"])
    return ApiResponse.ok(result)
