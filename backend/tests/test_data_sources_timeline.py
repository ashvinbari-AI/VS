"""GET /api/data-sources -- the date-range/timeline fields (earliest_post,
latest_post, days_of_content, scrape_window_since/until) added alongside
the existing content_count/last_scraped fields."""

from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

import app.routers.data_sources as data_sources_module
from app.main import app

client = TestClient(app)


def _fake_content_df():
    return pd.DataFrame([
        {"person_id": "px", "platform": "instagram", "published_at": "2026-08-01T00:00:00+00:00"},
        {"person_id": "px", "platform": "instagram", "published_at": "2026-08-10T00:00:00+00:00"},
    ])


def _fake_profiles_df():
    return pd.DataFrame([
        {"person_id": "px", "platform": "instagram", "finished_at": "2026-08-10T01:00:00+00:00",
         "since": "2026-07-01T00:00:00+00:00", "until": "2026-08-10T00:00:00+00:00", "errors": []},
    ])


def test_days_of_content_is_the_real_post_span_not_the_requested_window(monkeypatch):
    monkeypatch.setattr(data_sources_module, "get_content_df", _fake_content_df)
    monkeypatch.setattr(data_sources_module, "get_comments_df", lambda: pd.DataFrame())
    monkeypatch.setattr(data_sources_module, "get_profiles_df", _fake_profiles_df)
    monkeypatch.setattr(data_sources_module.json_store, "list_people",
                         lambda: [{"id": "px", "name": "Person X", "instagram_url": "https://x", "facebook_url": None}])

    r = client.get("/api/data-sources")
    row = next(s for s in r.json()["data"]["sources"] if s["platform"] == "instagram")
    assert row["days_of_content"] == 9  # 10th - 1st
    assert row["scrape_window_since"] == "2026-07-01T00:00:00+00:00"
    assert row["scrape_window_until"] == "2026-08-10T00:00:00+00:00"


def test_scrape_history_returns_runs_newest_first(monkeypatch):
    runs_df = pd.DataFrame([
        {"person_id": "px", "platform": "instagram", "run_id": "run_1", "since": "2026-07-01T00:00:00+00:00",
         "until": "2026-07-08T00:00:00+00:00", "started_at": "2026-07-08T00:00:00+00:00",
         "finished_at": "2026-07-08T00:10:00+00:00", "followers": 1000, "followers_raw": "1.0K",
         "posts_scanned": 5, "comments_new": 20, "errors": []},
        {"person_id": "px", "platform": "instagram", "run_id": "run_2", "since": "2026-08-01T00:00:00+00:00",
         "until": "2026-08-08T00:00:00+00:00", "started_at": "2026-08-08T00:00:00+00:00",
         "finished_at": "2026-08-08T00:10:00+00:00", "followers": 1100, "followers_raw": "1.1K",
         "posts_scanned": 6, "comments_new": 25, "errors": []},
    ])
    monkeypatch.setattr(data_sources_module, "get_profiles_df", lambda: runs_df)
    monkeypatch.setattr(data_sources_module.json_store, "get_person", lambda pid: {"id": pid, "name": "Person X"})

    r = client.get("/api/data-sources/px/history")
    assert r.status_code == 200
    runs = r.json()["data"]["runs"]
    assert [run["run_id"] for run in runs] == ["run_2", "run_1"]


def test_scrape_history_unknown_person_is_404(monkeypatch):
    monkeypatch.setattr(data_sources_module.json_store, "get_person", lambda pid: None)
    r = client.get("/api/data-sources/does_not_exist/history")
    assert r.status_code == 404


def test_no_content_reports_none_not_zero(monkeypatch):
    monkeypatch.setattr(data_sources_module, "get_content_df", lambda: pd.DataFrame())
    monkeypatch.setattr(data_sources_module, "get_comments_df", lambda: pd.DataFrame())
    monkeypatch.setattr(data_sources_module, "get_profiles_df", lambda: pd.DataFrame())
    monkeypatch.setattr(data_sources_module.json_store, "list_people",
                         lambda: [{"id": "py", "name": "Person Y", "instagram_url": "https://y", "facebook_url": None}])

    r = client.get("/api/data-sources")
    row = next(s for s in r.json()["data"]["sources"] if s["platform"] == "instagram")
    assert row["days_of_content"] is None
    assert row["earliest_post"] is None
