#!/usr/bin/env python3
"""
Generate a small, clearly-synthetic demo dataset so the dashboard can be
exercised before any real scraping happens (spec sections 54/55).

Run directly:  python -m app.demo.demo_data
(or via the "Load Demo Data" action in Settings)

Writes ONLY to data/mock/ -- never touches data/processed/ (real data), and
every synthetic record's raw_source_file is literally "DEMO_DATA" so it can
never be mistaken for, or accidentally merged with, real scraped evidence.
The frontend must show a "DEMO MODE" badge whenever this data is what's
being displayed (driven by GET /api/data-sources reporting demo=true).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import get_settings
from app.models.content import NormalizedComment, NormalizedContent, ProfileSnapshot
from app.storage import json_store
from app.storage.parquet_store import write_comments, write_content, write_profiles

DEMO_NARRATIVES = [
    "Development", "Infrastructure", "Farmers", "Healthcare", "Education",
    "Public Events", "Culture", "Party Organization",
]
DEMO_ISSUES_TEXT = {
    "Roads": "the road near our village is still broken, please fix it",
    "Water": "we need better water supply this summer",
    "Electricity": "power cuts have increased in our area",
}
CONTENT_TYPES = ["post", "reel", "video", "photo"]
COMMENT_SAMPLES = [
    "Great work, fully support this initiative!",
    "When will this actually be completed?",
    "This is just for show, nothing changes on the ground.",
    "Thank you for visiting our district.",
    "Please look into the road near our village, it is still broken.",
    "Jai Hind! Proud to see this development.",
    "Why hasn't the promised hospital been built yet?",
    "Good policy discussion, hope it's implemented well.",
]


def _rand_engagement(rng: random.Random, base: int) -> dict:
    likes = int(rng.gauss(base, base * 0.35))
    likes = max(10, likes)
    comments = max(0, int(likes * rng.uniform(0.02, 0.08)))
    shares = max(0, int(likes * rng.uniform(0.0, 0.03)))
    return {"likes": likes, "comments": comments, "shares": shares}


def _gen_person(person_id: str, person_name: str, rng: random.Random,
                 base_engagement: int, days: int = 60) -> tuple[list, list, list]:
    now = datetime.now(timezone.utc)
    contents: list[NormalizedContent] = []
    comments: list[NormalizedComment] = []

    n_posts = rng.randint(int(days * 0.6), int(days * 1.1))
    for i in range(n_posts):
        published = now - timedelta(days=rng.uniform(0, days), hours=rng.uniform(0, 24))
        platform = rng.choice(["instagram", "facebook"])
        content_type = rng.choices(CONTENT_TYPES, weights=[35, 30, 15, 20])[0]
        eng = _rand_engagement(rng, base_engagement)
        content_id = f"demo_{person_id}_{platform}_{i}"
        narrative_hint = rng.choice(DEMO_NARRATIVES)

        contents.append(NormalizedContent(
            person_id=person_id, person_name=person_name, platform=platform,
            content_id=content_id, content_type=content_type,
            content_url=f"https://example.invalid/demo/{content_id}",
            published_at=published.isoformat(timespec="seconds"),
            published_at_local=published.isoformat(timespec="seconds"),
            caption=f"[DEMO] {narrative_hint} update #{i} for {person_name}.",
            likes=eng["likes"], comments_count=eng["comments"],
            shares=eng["shares"] if platform == "facebook" else None,
            reactions_total=eng["likes"],
            reactions_breakdown=None,
            view_count=rng.randint(1000, 50000) if content_type in ("video", "reel") and platform == "facebook" else None,
            followers_at_collection=base_engagement * 200,
            hashtags=["DemoData", narrative_hint.replace(" ", "")],
            mentions=[],
            media_url=None, media_urls=None, author=person_name,
            raw_source_file="DEMO_DATA", raw_record_id=content_id,
            scraped_at=now.isoformat(timespec="seconds"),
            last_run_id="demo_run",
        ))

        n_comments = min(eng["comments"], rng.randint(0, 8))
        for c in range(n_comments):
            text = rng.choice(COMMENT_SAMPLES)
            comments.append(NormalizedComment(
                person_id=person_id, person_name=person_name, platform=platform,
                content_id=content_id, comment_id=f"{content_id}_c{c}",
                parent_comment_id=None, thread_root_id=f"{content_id}_c{c}", depth=0,
                author_username=f"demo_user_{rng.randint(1, 500)}",
                author_profile_url=None, comment_text=f"[DEMO] {text}",
                commented_at=(published + timedelta(minutes=rng.randint(1, 500))).isoformat(timespec="seconds"),
                like_count=rng.randint(0, 20), reply_count=0, status="active",
                raw_source_file="DEMO_DATA", raw_record_id=f"{content_id}_c{c}",
            ))

    runs = [ProfileSnapshot(
        person_id=person_id, person_name=person_name, platform=platform,
        run_id="demo_run", profile_url=f"https://example.invalid/{person_id}",
        followers=base_engagement * 200, followers_raw=f"{base_engagement * 200 / 1_000_000:.1f}M",
        posts_scanned=n_posts, comments_new=len(comments),
        started_at=now.isoformat(timespec="seconds"), finished_at=now.isoformat(timespec="seconds"),
        since=(now - timedelta(days=days)).isoformat(timespec="seconds"),
        until=now.isoformat(timespec="seconds"), errors=[], raw_source_file="DEMO_DATA",
    ) for platform in ("instagram", "facebook")]

    return contents, comments, runs


def generate_demo_dataset(seed: int = 42) -> dict:
    rng = random.Random(seed)
    settings = get_settings()
    settings.ensure_dirs()

    a_content, a_comments, a_runs = _gen_person("demo_person_a", "Demo Leader A", rng, base_engagement=4000)
    b_content, b_comments, b_runs = _gen_person("demo_person_b", "Demo Leader B", rng, base_engagement=2600)

    all_content = a_content + b_content
    all_comments = a_comments + b_comments
    all_runs = a_runs + b_runs

    mock_dir = settings.mock_dir
    write_content(all_content, mock_dir / "content.parquet")
    write_comments(all_comments, mock_dir / "comments.parquet")
    write_profiles(all_runs, mock_dir / "profiles.parquet")

    # Register the two demo people so Person Setup shows them (separately
    # from any real saved configs -- these ids are demo_person_a/b only).
    now = json_store.now_iso()
    for pid, pname in (("demo_person_a", "Demo Leader A"), ("demo_person_b", "Demo Leader B")):
        json_store.save_person({
            "id": pid, "name": pname,
            "instagram_url": f"https://example.invalid/{pid}",
            "facebook_url": f"https://example.invalid/{pid}",
            "instagram_profile_key": None, "facebook_profile_key": None,
            "created_at": now, "updated_at": now, "notes": "DEMO DATA -- synthetic, not scraped.",
        })

    return {
        "content_rows": len(all_content),
        "comment_rows": len(all_comments),
        "profile_snapshots": len(all_runs),
        "mock_dir": str(mock_dir),
    }


if __name__ == "__main__":
    result = generate_demo_dataset()
    print(f"Demo dataset written to {result['mock_dir']}")
    print(f"  content rows : {result['content_rows']}")
    print(f"  comment rows : {result['comment_rows']}")
    print(f"  profile runs : {result['profile_snapshots']}")
