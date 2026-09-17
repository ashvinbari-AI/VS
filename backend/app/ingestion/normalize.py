"""
Adapts real ig_scraper.py / fb_scraper.py output (Phase1Store's posts.jsonl /
comments.jsonl / scrape_runs.jsonl) into the normalized schema (spec section
4). This is the ONLY place that reads raw scraper field names -- everything
downstream (analytics, NLP, API, React) only ever sees NormalizedContent /
NormalizedComment / ProfileSnapshot.

Golden rule enforced throughout: never invent a value. A field the scraper
did not really collect for that platform becomes None, which the API/UI
render as "N/A" -- never a 0, never "".
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Iterator

from app.models.content import NormalizedComment, NormalizedContent, ProfileSnapshot

_HASHTAG_RE = re.compile(r"#([^\s#@,.!?;:()\[\]{}\"']+)", re.UNICODE)
_MENTION_RE = re.compile(r"@([^\s#@,.!?;:()\[\]{}\"']+)", re.UNICODE)

_CONTENT_TYPES = {"post", "reel", "video", "photo"}


def extract_hashtags(caption: str | None) -> list[str]:
    if not caption:
        return []
    return _HASHTAG_RE.findall(caption)


def extract_mentions(caption: str | None) -> list[str]:
    if not caption:
        return []
    return _MENTION_RE.findall(caption)


def iter_jsonl_records(base_dir: Path, filename: str) -> Iterator[tuple[dict[str, Any], str]]:
    """Yield (record, source_file_str) for every line of every `filename`
    found anywhere under base_dir (handles both the single canonical
    out-dir case and multiple imported_*/ snapshots)."""
    if not base_dir.exists():
        return
    for path in sorted(base_dir.rglob(filename)):
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        doc = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    yield doc, str(path)
        except OSError:
            continue


def _parse_iso(ts: str | None) -> str | None:
    """Best-effort -> ISO 8601 UTC string, or None if unparseable/absent."""
    if not ts:
        return None
    from datetime import datetime, timezone
    s = ts.strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
    except ValueError:
        return None


def to_local(iso_utc: str | None, tz_name: str) -> str | None:
    if not iso_utc:
        return None
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        dt = datetime.fromisoformat(iso_utc)
        return dt.astimezone(ZoneInfo(tz_name)).isoformat(timespec="seconds")
    except (ValueError, KeyError):
        return None


def normalize_post(raw: dict[str, Any], *, person_id: str, person_name: str,
                    platform: str, raw_source_file: str,
                    followers_by_run: dict[str, int]) -> NormalizedContent | None:
    post_id = raw.get("post_id")
    if not post_id:
        return None
    caption = raw.get("caption") or None
    post_type = raw.get("post_type")
    content_type = post_type if post_type in _CONTENT_TYPES else "unknown"

    reactions = raw.get("reactions") or {}
    reactions_total = reactions.get("total")
    likes = reactions.get("like")
    if likes is None:
        likes = reactions_total
    breakdown = None
    extra_keys = {k: v for k, v in reactions.items() if k not in ("like", "total")}
    if extra_keys:
        breakdown = {k: v for k, v in reactions.items() if k != "total"}

    if platform == "instagram":
        # ig_scraper.build_post() still hardcodes these two -- not real
        # measurements.
        shares: int | None = None
        media_urls: list[str] | None = None
        # view_count IS real now for reels (collect_reel_view_counts, off
        # the Reels tab) -- but raw records written before that existed
        # still carry the old hardcoded 0 placeholder. A real reel is never
        # actually seen by zero people, so treating a literal 0 the same as
        # "absent" discards that stale placeholder without needing to
        # touch already-collected raw files.
        view_count: int | None = raw.get("view_count") or None
    else:
        shares = raw.get("share_count")
        view_count = raw.get("view_count")
        media_urls = raw.get("media_urls") or None

    published_at = _parse_iso(raw.get("post_timestamp") or raw.get("post_timestamp_raw"))
    from app.config import get_settings
    published_at_local = to_local(published_at, get_settings().display_timezone)

    run_id = raw.get("last_run_id")
    followers_at_collection = followers_by_run.get(run_id) if run_id else None

    comments_count = raw.get("comment_count")

    return NormalizedContent(
        person_id=person_id,
        person_name=person_name,
        platform=platform,  # type: ignore[arg-type]
        content_id=str(post_id),
        content_type=content_type,  # type: ignore[arg-type]
        content_url=raw.get("post_url") or raw.get("scrape_url"),
        published_at=published_at,
        published_at_local=published_at_local,
        caption=caption,
        likes=likes,
        comments_count=comments_count,
        shares=shares,
        reactions_total=reactions_total,
        reactions_breakdown=breakdown,
        view_count=view_count,
        followers_at_collection=followers_at_collection,
        hashtags=extract_hashtags(caption),
        mentions=extract_mentions(caption),
        media_url=(media_urls[0] if media_urls else None),
        media_urls=media_urls,
        author=raw.get("author") or raw.get("profile"),
        raw_source_file=raw_source_file,
        raw_record_id=str(post_id),
        scraped_at=raw.get("first_seen_at"),
        last_run_id=run_id,
    )


def normalize_comment(raw: dict[str, Any], *, person_id: str, person_name: str,
                       platform: str, raw_source_file: str) -> NormalizedComment | None:
    comment_id = raw.get("comment_id")
    post_id = raw.get("post_id")
    if not comment_id or not post_id:
        return None
    commented_at = _parse_iso(raw.get("comment_timestamp")) if raw.get("comment_timestamp") else None
    return NormalizedComment(
        person_id=person_id,
        person_name=person_name,
        platform=platform,  # type: ignore[arg-type]
        content_id=str(post_id),
        comment_id=str(comment_id),
        parent_comment_id=raw.get("parent_comment_id"),
        thread_root_id=raw.get("thread_root_id"),
        depth=raw.get("depth") or 0,
        author_username=raw.get("user_name") or None,
        author_profile_url=raw.get("user_profile_url") or None,
        comment_text=raw.get("comment_text") or None,
        commented_at=commented_at,
        like_count=raw.get("like_count"),
        reply_count=raw.get("reply_count"),
        status=raw.get("status"),
        raw_source_file=raw_source_file,
        raw_record_id=str(comment_id),
    )


def normalize_run(raw: dict[str, Any], *, person_id: str, person_name: str,
                   platform: str, raw_source_file: str) -> ProfileSnapshot | None:
    run_id = raw.get("run_id")
    if not run_id:
        return None
    followers = raw.get("followers")
    followers_raw = raw.get("followers_raw")
    # A 0-with-no-raw-string reading means the scraper never actually saw a
    # follower count on that run (e.g. the FB run in this project's own
    # output/ that scanned 0 posts) -- report it as unavailable, not "0".
    if not followers_raw and not followers:
        followers = None
    window = raw.get("date_window") or {}
    return ProfileSnapshot(
        person_id=person_id,
        person_name=person_name,
        platform=platform,  # type: ignore[arg-type]
        run_id=str(run_id),
        profile_url=raw.get("profile_url"),
        followers=followers,
        followers_raw=followers_raw or None,
        posts_scanned=raw.get("posts_scanned"),
        comments_new=raw.get("comments_new"),
        started_at=raw.get("started_at"),
        finished_at=raw.get("finished_at"),
        since=window.get("since"),
        until=window.get("until"),
        errors=raw.get("errors") or [],
        raw_source_file=raw_source_file,
    )


def normalize_person_platform(raw_dir: Path, *, person_id: str, person_name: str,
                               platform: str) -> tuple[list[NormalizedContent],
                                                        list[NormalizedComment],
                                                        list[ProfileSnapshot]]:
    """Read every posts/comments/scrape_runs.jsonl under raw_dir (recursively,
    to cover multiple imports) and normalize them for one person+platform."""
    runs: list[ProfileSnapshot] = []
    for raw, src in iter_jsonl_records(raw_dir, "scrape_runs.jsonl"):
        snap = normalize_run(raw, person_id=person_id, person_name=person_name,
                              platform=platform, raw_source_file=src)
        if snap:
            runs.append(snap)
    followers_by_run = {r.run_id: r.followers for r in runs if r.followers is not None}

    contents: list[NormalizedContent] = []
    for raw, src in iter_jsonl_records(raw_dir, "posts.jsonl"):
        item = normalize_post(raw, person_id=person_id, person_name=person_name,
                               platform=platform, raw_source_file=src,
                               followers_by_run=followers_by_run)
        if item:
            contents.append(item)

    comments: list[NormalizedComment] = []
    for raw, src in iter_jsonl_records(raw_dir, "comments.jsonl"):
        item = normalize_comment(raw, person_id=person_id, person_name=person_name,
                                  platform=platform, raw_source_file=src)
        if item:
            comments.append(item)

    return contents, comments, runs
