"""Adapter-layer tests using literal shapes copied from the real
ig_scraper.py / fb_scraper.py output (schema_store.Phase1Store), not
invented fixtures."""

from __future__ import annotations

from app.ingestion.normalize import (
    extract_hashtags, extract_mentions, normalize_comment, normalize_post,
)

IG_POST = {
    "post_id": "ig_DdF4BgoG-jt", "profile": "devendra_fadnavis", "page_id": "devendra_fadnavis",
    "platform": "instagram", "post_url": "https://www.instagram.com/devendra_fadnavis/p/DdF4BgoG-jt/",
    "post_type": "reel", "caption": "Test caption #Farmers @someone",
    "post_timestamp": "2026-09-10T03:31:33.000Z", "author": "devendra_fadnavis",
    "reactions": {"like": 7700, "total": 7700}, "comment_count": 211,
    "share_count": 0, "view_count": 0, "media_urls": [],
    "scrape_url": "https://www.instagram.com/devendra_fadnavis/p/DdF4BgoG-jt/",
    "comments_captured": 103, "first_seen_at": "2026-09-10T06:23:46+00:00",
    "last_seen_at": "2026-09-10T06:23:46+00:00", "last_run_id": "run_20260910T115246",
}

FB_POST = {
    "post_id": "fb_123", "profile": "some.page", "page_id": "some.page",
    "platform": "facebook", "post_url": "https://www.facebook.com/some.page/posts/123",
    "post_type": "video", "caption": "FB caption", "post_timestamp": "2026-09-01T10:00:00+05:30",
    "author": "Some Page", "reactions": {"like": 500, "love": 50, "total": 600},
    "comment_count": 40, "share_count": 12, "view_count": 5000,
    "media_urls": ["https://example.com/v.mp4"],
    "scrape_url": "https://www.facebook.com/some.page/posts/123",
    "last_run_id": "run_fb_1",
}

IG_COMMENT = {
    "comment_id": "ig_x_c1", "post_id": "ig_DdF4BgoG-jt", "parent_comment_id": None,
    "thread_root_id": "ig_x_c1", "depth": 0, "user_id": "ig_someone", "user_name": "someone",
    "user_profile_url": "https://www.instagram.com/someone/", "comment_text": "Nice!",
    "comment_timestamp": "", "like_count": 0, "reply_count": 0, "status": "active",
}


def test_instagram_hardcoded_placeholders_become_none_not_fake_zero():
    """ig_scraper.build_post() hardcodes share_count/view_count/media_urls --
    these are NOT real measurements and must never surface as a real 0/[]."""
    item = normalize_post(IG_POST, person_id="p1", person_name="Person One",
                           platform="instagram", raw_source_file="posts.jsonl",
                           followers_by_run={})
    assert item is not None
    assert item.shares is None
    assert item.view_count is None
    assert item.media_urls is None


def test_facebook_real_values_pass_through():
    item = normalize_post(FB_POST, person_id="p2", person_name="Person Two",
                           platform="facebook", raw_source_file="posts.jsonl",
                           followers_by_run={})
    assert item.shares == 12
    assert item.view_count == 5000
    assert item.media_urls == ["https://example.com/v.mp4"]
    # reactions_total (600) includes likes+love -- must not be double-counted
    # with `likes` when engagement is computed downstream.
    assert item.reactions_total == 600
    assert item.reactions_breakdown == {"like": 500, "love": 50}


def test_hashtag_and_mention_extraction_is_deterministic_parsing_not_ai():
    assert extract_hashtags("hello #Farmers and #Water2026") == ["Farmers", "Water2026"]
    assert extract_mentions("cc @someone and @another_one") == ["someone", "another_one"]
    assert extract_hashtags(None) == []
    assert extract_mentions("") == []


def test_followers_at_collection_joined_from_run():
    item = normalize_post(IG_POST, person_id="p1", person_name="Person One",
                           platform="instagram", raw_source_file="posts.jsonl",
                           followers_by_run={"run_20260910T115246": 2900000})
    assert item.followers_at_collection == 2900000


def test_post_missing_id_is_dropped_not_crashed():
    broken = dict(IG_POST)
    del broken["post_id"]
    assert normalize_post(broken, person_id="p1", person_name="P", platform="instagram",
                           raw_source_file="x", followers_by_run={}) is None


def test_comment_normalization_empty_timestamp_becomes_none():
    """ig_scraper never exposes a per-comment timestamp -- must be None, not ''."""
    item = normalize_comment(IG_COMMENT, person_id="p1", person_name="Person One",
                              platform="instagram", raw_source_file="comments.jsonl")
    assert item is not None
    assert item.commented_at is None
