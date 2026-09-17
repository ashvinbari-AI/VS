"""GET /api/proof -- the KPI evidence-trail endpoint. Values must match
the exact same app.analytics.engine functions the KPI cards themselves
call; that equivalence is what makes this "proof" rather than a second,
possibly-drifted calculation."""

from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

import app.routers.proof as proof_module
from app.main import app

client = TestClient(app)


def _fake_content_df():
    return pd.DataFrame([
        {"content_id": "p1", "person_id": "px", "person_name": "Person X", "platform": "instagram",
         "content_type": "post", "published_at": "2026-01-01T00:00:00+00:00", "likes": 100,
         "comments_count": 10, "reactions_total": 100, "shares": None, "content_url": "https://x/1",
         "author": "px"},
        {"content_id": "p2", "person_id": "px", "person_name": "Person X", "platform": "instagram",
         "content_type": "reel", "published_at": "2026-01-02T00:00:00+00:00", "likes": 200,
         "comments_count": 20, "reactions_total": 200, "shares": None, "content_url": "https://x/2",
         "author": "px"},
    ])


def _fake_profiles_df():
    return pd.DataFrame([
        {"person_id": "px", "platform": "instagram", "run_id": "run_1", "followers": 1000,
         "followers_raw": "1.0K", "finished_at": "2026-01-02T00:00:00+00:00"},
    ])


def test_average_likes_matches_hand_computed_value(monkeypatch):
    monkeypatch.setattr(proof_module, "get_content_df", _fake_content_df)
    monkeypatch.setattr(proof_module, "get_profiles_df", _fake_profiles_df)
    r = client.get("/api/proof", params={"person_id": "px", "metric": "average_likes"})
    body = r.json()["data"]
    assert body["value"] == 150.0  # (100+200)/2
    assert body["sum"] == 300.0
    assert body["count"] == 2
    assert len(body["records"]) == 2


def test_engagement_rate_includes_followers_and_average_engagement(monkeypatch):
    monkeypatch.setattr(proof_module, "get_content_df", _fake_content_df)
    monkeypatch.setattr(proof_module, "get_profiles_df", _fake_profiles_df)
    r = client.get("/api/proof", params={"person_id": "px", "metric": "engagement_rate"})
    body = r.json()["data"]
    assert body["followers"] == 1000
    assert body["average_engagement"] == 165.0  # ((100+10)+(200+20))/2
    assert body["value"] == 16.5  # 165/1000*100


def test_unknown_metric_is_a_400_not_a_silent_empty_result(monkeypatch):
    monkeypatch.setattr(proof_module, "get_content_df", _fake_content_df)
    monkeypatch.setattr(proof_module, "get_profiles_df", _fake_profiles_df)
    r = client.get("/api/proof", params={"person_id": "px", "metric": "not_a_real_metric"})
    assert r.status_code == 400


def test_followers_returns_the_snapshot_record(monkeypatch):
    monkeypatch.setattr(proof_module, "get_content_df", _fake_content_df)
    monkeypatch.setattr(proof_module, "get_profiles_df", _fake_profiles_df)
    r = client.get("/api/proof", params={"person_id": "px", "metric": "followers"})
    body = r.json()["data"]
    assert body["value"] == 1000
    assert body["records"][0]["followers"] == 1000


def _fake_activity_content_df():
    # p1 on day 1, p2 two days later, p3 one day after that -- longest gap
    # is p1->p2 (2 days = 48h), the other gap (p2->p3) is 1 day (24h), so
    # the median of [24, 48] is 36 hours.
    return pd.DataFrame([
        {"content_id": "p1", "person_id": "px", "person_name": "Person X", "platform": "instagram",
         "content_type": "post", "published_at": "2026-01-01T00:00:00+00:00", "likes": 10,
         "comments_count": 1, "reactions_total": 10, "shares": None, "content_url": "https://x/1",
         "author": "px"},
        {"content_id": "p2", "person_id": "px", "person_name": "Person X", "platform": "instagram",
         "content_type": "post", "published_at": "2026-01-03T00:00:00+00:00", "likes": 20,
         "comments_count": 2, "reactions_total": 20, "shares": None, "content_url": "https://x/2",
         "author": "px"},
        {"content_id": "p3", "person_id": "px", "person_name": "Person X", "platform": "instagram",
         "content_type": "reel", "published_at": "2026-01-04T00:00:00+00:00", "likes": 30,
         "comments_count": 3, "reactions_total": 30, "shares": None, "content_url": "https://x/3",
         "author": "px"},
    ])


def test_posts_per_day_and_week(monkeypatch):
    monkeypatch.setattr(proof_module, "get_content_df", _fake_activity_content_df)
    monkeypatch.setattr(proof_module, "get_profiles_df", lambda: pd.DataFrame())
    r = client.get("/api/proof", params={"person_id": "px", "metric": "posts_per_day", "period_days": 10})
    body = r.json()["data"]
    assert body["value"] == 0.3  # 3 posts / 10 days
    assert body["count"] == 3
    assert body["period_days"] == 10


def test_reels_per_week_only_counts_reels(monkeypatch):
    monkeypatch.setattr(proof_module, "get_content_df", _fake_activity_content_df)
    monkeypatch.setattr(proof_module, "get_profiles_df", lambda: pd.DataFrame())
    r = client.get("/api/proof", params={"person_id": "px", "metric": "reels_per_week", "period_days": 10})
    body = r.json()["data"]
    assert body["count"] == 1  # only p3 is a reel


def test_active_days(monkeypatch):
    monkeypatch.setattr(proof_module, "get_content_df", _fake_activity_content_df)
    monkeypatch.setattr(proof_module, "get_profiles_df", lambda: pd.DataFrame())
    r = client.get("/api/proof", params={"person_id": "px", "metric": "active_days"})
    assert r.json()["data"]["value"] == 3


def test_longest_inactive_period_returns_the_bounding_pair(monkeypatch):
    monkeypatch.setattr(proof_module, "get_content_df", _fake_activity_content_df)
    monkeypatch.setattr(proof_module, "get_profiles_df", lambda: pd.DataFrame())
    r = client.get("/api/proof", params={"person_id": "px", "metric": "longest_inactive_period_days"})
    body = r.json()["data"]
    assert body["value"] == 2.0
    assert body["records"][0]["from_content_id"] == "p1"
    assert body["records"][0]["to_content_id"] == "p2"
    assert body["records"][0]["gap_days"] == 2.0


def test_median_interval_hours(monkeypatch):
    monkeypatch.setattr(proof_module, "get_content_df", _fake_activity_content_df)
    monkeypatch.setattr(proof_module, "get_profiles_df", lambda: pd.DataFrame())
    r = client.get("/api/proof", params={"person_id": "px", "metric": "median_interval_hours"})
    assert r.json()["data"]["value"] == 36.0


def test_most_active_day_and_hour_return_full_distribution(monkeypatch):
    monkeypatch.setattr(proof_module, "get_content_df", _fake_activity_content_df)
    monkeypatch.setattr(proof_module, "get_profiles_df", lambda: pd.DataFrame())
    r = client.get("/api/proof", params={"person_id": "px", "metric": "most_active_day"})
    body = r.json()["data"]
    assert len(body["records"]) == 7  # all 7 days always present, even at 0

    r2 = client.get("/api/proof", params={"person_id": "px", "metric": "most_active_hour"})
    body2 = r2.json()["data"]
    assert len(body2["records"]) == 24  # all 24 hours always present
