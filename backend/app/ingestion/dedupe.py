"""Deterministic duplicate detection (spec section 51).

Primary key: (platform, content_id) / (platform, comment_id) -- these are
already globally unique because the scrapers prefix ids per-platform
(e.g. "ig_..."). Fallback, used only if content_id is ever missing after
normalization (shouldn't happen -- normalize_post/comment already drop
records with no id), is a hash of person+platform+published_at+caption.

When the same id appears more than once (e.g. the same raw file imported
twice, or two overlapping scrape windows), the record with the latest
`scraped_at` / `last_run_id` wins -- both scrapers already do this kind of
upsert internally, this just re-applies the same rule when merging multiple
raw snapshots at ingestion time.
"""

from __future__ import annotations

import hashlib
from typing import TypeVar

from app.models.content import NormalizedComment, NormalizedContent

T = TypeVar("T", NormalizedContent, NormalizedComment)


def fallback_hash(person_id: str, platform: str, published_at: str | None,
                   text: str | None) -> str:
    raw = f"{person_id}|{platform}|{published_at or ''}|{text or ''}"
    return "fallback_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def dedupe_content(items: list[NormalizedContent]) -> list[NormalizedContent]:
    best: dict[tuple[str, str], NormalizedContent] = {}
    for item in items:
        key = (item.platform, item.content_id) if item.content_id else (
            item.platform, fallback_hash(item.person_id, item.platform,
                                          item.published_at, item.caption))
        current = best.get(key)
        if current is None or _newer(item.scraped_at, current.scraped_at):
            best[key] = item
    return list(best.values())


def dedupe_comments(items: list[NormalizedComment]) -> list[NormalizedComment]:
    best: dict[tuple[str, str], NormalizedComment] = {}
    for item in items:
        key = (item.platform, item.comment_id) if item.comment_id else (
            item.platform, fallback_hash(item.person_id, item.platform,
                                          item.commented_at, item.comment_text))
        current = best.get(key)
        if current is None or (item.status == "active" and current.status != "active"):
            best[key] = item
    return list(best.values())


def _newer(a: str | None, b: str | None) -> bool:
    if a is None:
        return False
    if b is None:
        return True
    return a > b
