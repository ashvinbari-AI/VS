"""
The ingestion pipeline (spec sections 3/47): read every person's raw JSONL,
normalize, dedupe, write the three Parquet tables. Run after every scrape or
import ("Run Analysis" / POST /api/analysis/run triggers this first).

Rebuilds Parquet from scratch on each call rather than incrementally
upserting -- at the data volumes this tool targets (tens of thousands of
rows) a full rebuild from JSONL takes well under a second and is far less
error-prone than incremental merge logic.
"""

from __future__ import annotations

from app.config import get_settings
from app.ingestion.dedupe import dedupe_comments, dedupe_content
from app.ingestion.normalize import normalize_person_platform
from app.logging_setup import get_logger
from app.models.content import NormalizedComment, NormalizedContent, ProfileSnapshot
from app.storage import json_store
from app.storage.parquet_store import write_comments, write_content, write_profiles

PLATFORMS = ("instagram", "facebook")


def run_ingestion() -> dict:
    settings = get_settings()
    logger = get_logger("analysis", settings.logs_dir)
    people = json_store.list_people()

    all_content: list[NormalizedContent] = []
    all_comments: list[NormalizedComment] = []
    all_profiles: list[ProfileSnapshot] = []
    per_person_counts: dict[str, dict] = {}

    for person in people:
        pid, pname = person["id"], person["name"]
        per_person_counts[pid] = {}
        for platform in PLATFORMS:
            raw_dir = settings.raw_dir / pid / platform
            contents, comments, runs = normalize_person_platform(
                raw_dir, person_id=pid, person_name=pname, platform=platform)
            all_content.extend(contents)
            all_comments.extend(comments)
            all_profiles.extend(runs)
            per_person_counts[pid][platform] = {
                "content": len(contents), "comments": len(comments), "runs": len(runs),
            }

    deduped_content = dedupe_content(all_content)
    deduped_comments = dedupe_comments(all_comments)

    write_content(deduped_content)
    write_comments(deduped_comments)
    write_profiles(all_profiles)

    result = {
        "people": len(people),
        "content_rows": len(deduped_content),
        "comments_rows": len(deduped_comments),
        "profile_snapshots": len(all_profiles),
        "content_duplicates_removed": len(all_content) - len(deduped_content),
        "comments_duplicates_removed": len(all_comments) - len(deduped_comments),
        "per_person": per_person_counts,
    }
    logger.info("ingestion complete: %s", result)
    return result
