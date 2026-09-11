"""
The normalized internal schema (spec section 4).

Every field that the source scraper does not actually provide is `None` --
never a manufactured 0 or "". Two scraper-specific caveats baked in by the
adapters (see scrapers/*_adapter.py):

  * Instagram's build_post() hardcodes share_count=0, view_count=0,
    media_urls=[] and comment_timestamp="" -- those are placeholders in the
    scraper itself, not real zeros, so the IG adapter maps them to None here.
  * Facebook's equivalents are real scraped values and pass through as-is.

`raw_source_file` + `raw_record_id` let every downstream number be traced
back to the exact JSONL line it came from (spec section 42).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Platform = Literal["instagram", "facebook"]
ContentType = Literal["post", "reel", "video", "photo", "text", "unknown"]


class NormalizedContent(BaseModel):
    person_id: str
    person_name: str
    platform: Platform
    content_id: str
    content_type: ContentType
    content_url: str | None = None
    published_at: str | None = None       # ISO 8601 UTC, None if unparseable
    published_at_local: str | None = None  # display timezone, derived
    caption: str | None = None
    likes: int | None = None
    comments_count: int | None = None
    shares: int | None = None
    reactions_total: int | None = None
    reactions_breakdown: dict[str, int] | None = None
    view_count: int | None = None
    followers_at_collection: int | None = None
    hashtags: list[str] = []
    mentions: list[str] = []
    media_url: str | None = None
    media_urls: list[str] | None = None
    author: str | None = None
    raw_source_file: str
    raw_record_id: str
    scraped_at: str | None = None
    last_run_id: str | None = None

    # Deterministic, Python-calculated -- filled by the analytics engine, not
    # the adapter. None until calculate_engagement() has run over the row.
    engagement: int | None = None

    # -- AI/model-generated classifications (spec section 8/20/23/42) --
    # Populated only after POST /api/analysis/run has done an NLP pass; None
    # means "not analyzed yet", not "neutral"/"other". Always render these in
    # the UI as "Model-classified", distinct from the deterministic fields
    # above -- never as ground truth.
    narrative: str | None = None
    narrative_confidence: float | None = None
    sentiment: str | None = None
    sentiment_confidence: float | None = None
    nlp_model: str | None = None


class NormalizedComment(BaseModel):
    person_id: str
    person_name: str
    platform: Platform
    content_id: str
    comment_id: str
    parent_comment_id: str | None = None
    thread_root_id: str | None = None
    depth: int = 0
    author_username: str | None = None
    author_profile_url: str | None = None
    comment_text: str | None = None
    commented_at: str | None = None
    like_count: int | None = None
    reply_count: int | None = None
    status: str | None = None   # 'active' | 'disappeared' | None if not tracked
    raw_source_file: str
    raw_record_id: str

    # -- AI/model-generated classifications, populated by the NLP pass --
    sentiment: str | None = None
    theme: str | None = None
    issues: list[str] = []


class ProfileSnapshot(BaseModel):
    """One scrape_runs.jsonl row -- a point-in-time reading of follower count etc."""
    person_id: str
    person_name: str
    platform: Platform
    run_id: str
    profile_url: str | None = None
    followers: int | None = None
    followers_raw: str | None = None
    posts_scanned: int | None = None
    comments_new: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    since: str | None = None
    until: str | None = None
    errors: list[str] = []
    raw_source_file: str
