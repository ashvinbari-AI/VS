from __future__ import annotations

from app.ingestion.dedupe import dedupe_comments, dedupe_content
from app.models.content import NormalizedComment, NormalizedContent


def _content(content_id: str, platform: str = "instagram", scraped_at: str = "2026-01-01T00:00:00+00:00"):
    return NormalizedContent(
        person_id="p1", person_name="P", platform=platform, content_id=content_id,
        content_type="post", raw_source_file="a.jsonl", raw_record_id=content_id,
        scraped_at=scraped_at,
    )


def test_same_platform_and_content_id_deduped_keeping_latest():
    older = _content("x1", scraped_at="2026-01-01T00:00:00+00:00")
    newer = _content("x1", scraped_at="2026-02-01T00:00:00+00:00")
    result = dedupe_content([older, newer])
    assert len(result) == 1
    assert result[0].scraped_at == "2026-02-01T00:00:00+00:00"


def test_different_platforms_same_id_not_deduped():
    ig = _content("shared_id", platform="instagram")
    fb = _content("shared_id", platform="facebook")
    result = dedupe_content([ig, fb])
    assert len(result) == 2


def test_comments_prefer_active_status_over_disappeared():
    c1 = NormalizedComment(person_id="p1", person_name="P", platform="instagram",
                            content_id="post1", comment_id="c1", status="disappeared",
                            raw_source_file="a.jsonl", raw_record_id="c1")
    c2 = NormalizedComment(person_id="p1", person_name="P", platform="instagram",
                            content_id="post1", comment_id="c1", status="active",
                            raw_source_file="b.jsonl", raw_record_id="c1")
    result = dedupe_comments([c1, c2])
    assert len(result) == 1
    assert result[0].status == "active"
