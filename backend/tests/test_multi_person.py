"""Multi-person comparison (2..N people, `?person_ids=a&person_ids=b&...`).

Unit tests for the parsing + N-way winner/normalization logic, and API
tests for every comparison endpoint against a small hand-checkable fake
dataset of three people (so expected values can be computed by hand):

    pa: 2 posts  (likes 100, 300)   followers 1000
    pb: 1 reel   (likes 500)        followers 2000
    pc: 3 posts  (likes 10, 20, 30) followers None  (no profile snapshot)
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routers.activity as activity_module
import app.routers.comments as comments_module
import app.routers.comparison as comparison_module
import app.routers.engagement as engagement_module
import app.routers.narratives as narratives_module
import app.routers.overview as overview_module
import app.routers.sentiment as sentiment_module
from app.analytics.comparison import (
    _winner_n, calculate_comparison_metrics, calculate_multi_comparison,
)
from app.main import app
from app.routers.comparison import _normalize
from app.routers.people_params import MAX_COMPARE_PEOPLE, parse_person_ids

client = TestClient(app)

IDS = ["pa", "pb", "pc"]
QS = "person_ids=pa&person_ids=pb&person_ids=pc"


# --------------------------------------------------------------------------
# Fake data
# --------------------------------------------------------------------------

def _post(cid, pid, ctype, day, likes, comments, narrative):
    return {
        "content_id": cid, "person_id": pid, "person_name": pid.upper(), "platform": "instagram",
        "content_type": ctype, "published_at": f"2026-01-{day:02d}T10:00:00+00:00",
        "likes": likes, "comments_count": comments, "reactions_total": likes, "shares": None,
        "view_count": None, "content_url": f"https://x/{cid}", "author": pid,
        "caption": f"caption {cid}", "narrative": narrative,
    }


def fake_content():
    return pd.DataFrame([
        _post("a1", "pa", "post", 1, 100, 10, "Development"),
        _post("a2", "pa", "post", 3, 300, 30, "Welfare"),
        _post("b1", "pb", "reel", 2, 500, 50, "Development"),
        _post("c1", "pc", "post", 1, 10, 1, "Welfare"),
        _post("c2", "pc", "post", 2, 20, 2, "Welfare"),
        _post("c3", "pc", "post", 3, 30, 3, "Welfare"),
    ])


def fake_comments():
    rows = [
        ("k1", "a1", "pa", "Positive", "Praise", ["Roads"]),
        ("k2", "a1", "pa", "Negative", "Criticism", ["Water"]),
        ("k3", "b1", "pb", "Positive", "Praise", ["Roads"]),
        ("k4", "c1", "pc", "Neutral", "Question", []),
    ]
    return pd.DataFrame([
        {"comment_id": k, "content_id": c, "person_id": p, "person_name": p.upper(),
         "platform": "instagram", "sentiment": s, "theme": t, "issues": i,
         "commented_at": None, "comment_text": f"text {k}", "like_count": 0}
        for k, c, p, s, t, i in rows
    ])


def fake_profiles():
    return pd.DataFrame([
        {"person_id": "pa", "platform": "instagram", "run_id": "r1", "followers": 1000,
         "followers_raw": "1K", "finished_at": "2026-01-03T00:00:00+00:00"},
        {"person_id": "pb", "platform": "instagram", "run_id": "r2", "followers": 2000,
         "followers_raw": "2K", "finished_at": "2026-01-03T00:00:00+00:00"},
    ])


@pytest.fixture(autouse=True)
def patch_data(monkeypatch):
    """Every comparison router reads data through its own imported getters;
    point them all at the fake dataset (never the real data/ folder)."""
    for module in (overview_module, comparison_module, activity_module, engagement_module,
                   narratives_module, sentiment_module, comments_module):
        for name, fn in (("get_content_df", fake_content), ("get_comments_df", fake_comments),
                         ("get_profiles_df", fake_profiles)):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, fn)


def ok(path: str) -> dict:
    r = client.get(path)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True, body
    return body["data"]


# --------------------------------------------------------------------------
# parse_person_ids
# --------------------------------------------------------------------------

def test_parse_keeps_order_and_dedupes():
    assert parse_person_ids(["pc", "pa", "pc", " pa ", "pb"]) == ["pc", "pa", "pb"]


def test_parse_drops_blanks():
    assert parse_person_ids(["", "  ", "pa", "pb"]) == ["pa", "pb"]


@pytest.mark.parametrize("value", [None, [], ["", " "]])
def test_parse_rejects_empty(value):
    with pytest.raises(HTTPException) as exc:
        parse_person_ids(value)
    assert exc.value.status_code == 400


def test_parse_enforces_max():
    ids = [f"p{i}" for i in range(MAX_COMPARE_PEOPLE)]
    assert parse_person_ids(ids) == ids
    with pytest.raises(HTTPException) as exc:
        parse_person_ids(ids + ["one_too_many"])
    assert exc.value.status_code == 400


# --------------------------------------------------------------------------
# N-way winner / normalization
# --------------------------------------------------------------------------

def test_winner_higher_better():
    assert _winner_n({"a": 1, "b": 5, "c": 3}, "higher_better") == "b"


def test_winner_lower_better():
    assert _winner_n({"a": 1, "b": 5, "c": 3}, "lower_better") == "a"


def test_winner_tie_at_top_is_none():
    assert _winner_n({"a": 5, "b": 5, "c": 3}, "higher_better") is None


def test_winner_tie_below_top_still_has_winner():
    assert _winner_n({"a": 9, "b": 5, "c": 5}, "higher_better") == "a"


def test_winner_missing_value_is_none():
    """Never fabricate: a missing value can neither win nor lose."""
    assert _winner_n({"a": 1, "b": None, "c": 3}, "higher_better") is None


def test_winner_neutral_is_none():
    assert _winner_n({"a": 1, "b": 5}, "neutral") is None


def test_normalize_scales_highest_to_100():
    assert _normalize({"a": 50, "b": 100, "c": 25}) == {"a": 50.0, "b": 100.0, "c": 25.0}


def test_normalize_leaves_incomplete_dimension_empty():
    assert _normalize({"a": 50, "b": None}) == {"a": None, "b": None}


def test_normalize_all_zero_does_not_divide_by_zero():
    assert _normalize({"a": 0, "b": 0}) == {"a": 0.0, "b": 0.0}


def test_multi_comparison_matches_two_person_version():
    """With exactly two people the N-way function must agree with the
    original Person A/B function on every value and every winner."""
    content = fake_content()
    df_a = content[content["person_id"] == "pa"]
    df_b = content[content["person_id"] == "pb"]
    empty = pd.DataFrame()
    legacy = calculate_comparison_metrics("pa", "pb", df_a, df_b, empty, empty, 1000, 2000, 30)
    multi = calculate_multi_comparison(
        ["pa", "pb"], {"pa": df_a, "pb": df_b}, {"pa": empty, "pb": empty},
        {"pa": 1000, "pb": 2000}, 30,
    )
    for key, old in legacy["comparisons"].items():
        new = multi["comparisons"][key]
        assert new["values"] == {"pa": old["person_a"], "pb": old["person_b"]}, key
        assert new["winner"] == old["winner"], key


def test_leader_margin_is_gap_to_runner_up():
    content = fake_content()
    dfs = {pid: content[content["person_id"] == pid] for pid in IDS}
    empty = {pid: pd.DataFrame() for pid in IDS}
    result = calculate_multi_comparison(IDS, dfs, empty, {"pa": 1000, "pb": 2000, "pc": None}, 30)
    likes = result["comparisons"]["total_likes"]
    assert likes["values"] == {"pa": 400, "pb": 500, "pc": 60}
    assert likes["winner"] == "pb"
    assert likes["leader_margin"] == 100  # 500 - 400


# --------------------------------------------------------------------------
# API: request validation
# --------------------------------------------------------------------------

ENDPOINTS = ["overview", "comparison", "activity", "engagement", "narratives", "sentiment", "comments"]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_missing_person_ids_is_422(endpoint):
    assert client.get(f"/api/{endpoint}").status_code == 422


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_too_many_people_is_400(endpoint):
    qs = "&".join(f"person_ids=p{i}" for i in range(MAX_COMPARE_PEOPLE + 1))
    assert client.get(f"/api/{endpoint}?{qs}").status_code == 400


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_old_person_a_b_params_are_rejected(endpoint):
    """The pre-multi-person API shape must fail loudly, not silently
    return someone else's data."""
    assert client.get(f"/api/{endpoint}?person_a=pa&person_b=pb").status_code == 422


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_every_endpoint_echoes_people_in_request_order(endpoint):
    data = ok(f"/api/{endpoint}?person_ids=pc&person_ids=pa&person_ids=pb&person_ids=pa")
    assert data["person_ids"] == ["pc", "pa", "pb"]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_unknown_person_gets_empty_block_not_an_error(endpoint):
    ok(f"/api/{endpoint}?person_ids=pa&person_ids=nobody")


# --------------------------------------------------------------------------
# API: values, three people
# --------------------------------------------------------------------------

def test_overview_kpis_per_person():
    data = ok(f"/api/overview?{QS}")
    k = data["kpis"]
    assert set(k) == set(IDS)
    assert (k["pa"]["total_content"], k["pb"]["total_content"], k["pc"]["total_content"]) == (2, 1, 3)
    assert (k["pa"]["total_likes"], k["pb"]["total_likes"], k["pc"]["total_likes"]) == (400, 500, 60)
    assert k["pa"]["followers"] == 1000 and k["pc"]["followers"] is None
    assert k["pb"]["reels"] == 1 and k["pb"]["posts"] == 0


def test_overview_timeline_rows_have_every_person():
    rows = ok(f"/api/overview?{QS}")["charts"]["content_activity_timeline"]
    by_date = {r["date"]: r for r in rows}
    assert by_date["2026-01-01"] == {"date": "2026-01-01", "pa": 1, "pb": 0, "pc": 1}
    assert by_date["2026-01-02"] == {"date": "2026-01-02", "pa": 0, "pb": 1, "pc": 1}
    assert by_date["2026-01-03"] == {"date": "2026-01-03", "pa": 1, "pb": 0, "pc": 1}


def test_overview_top_content_only_selected_people():
    data = ok("/api/overview?person_ids=pa&person_ids=pc")
    assert {r["person_id"] for r in data["charts"]["top_content"]} == {"pa", "pc"}


def test_comparison_winners_and_radar():
    data = ok(f"/api/comparison?{QS}")
    cmp = data["comparisons"]
    assert cmp["total_content"]["winner"] == "pc"
    assert cmp["total_likes"]["winner"] == "pb"
    # pc has no followers snapshot -> no defensible winner for followers.
    assert cmp["followers"]["winner"] is None
    assert cmp["peak_posting_hour"]["winner"] is None  # neutral metric
    radar = data["normalized_analytics_index"]["dimensions"]
    assert radar["Content volume"]["values"] == {"pa": 66.7, "pb": 33.3, "pc": 100.0}
    assert radar["Audience"]["values"] == {"pa": None, "pb": None, "pc": None}
    assert set(data["narrative_diversity"]) == set(IDS)
    assert set(data["activity_consistency"]) == set(IDS)


def test_activity_per_person():
    people = ok(f"/api/activity?{QS}&period_days=10")["people"]
    assert set(people) == set(IDS)
    assert people["pc"]["active_days"] == 3
    assert people["pb"]["reels_per_day"] == pytest.approx(0.1)


def test_engagement_pools_top_content_across_everyone():
    data = ok(f"/api/engagement?{QS}")
    assert set(data["people"]) == set(IDS)
    assert data["people"]["pa"]["followers"] == 1000
    assert [r["content_id"] for r in data["top_posts"]] == ["a2", "a1", "c3"]
    assert [r["content_id"] for r in data["top_reels"]] == ["b1"]


def test_engagement_when_nobody_has_content():
    data = ok("/api/engagement?person_ids=nobody&person_ids=nobody2")
    assert data["top_posts"] == [] and data["top_reels"] == []


def test_narratives_table_per_person():
    data = ok(f"/api/narratives?{QS}")
    rows = {r["narrative"]: r["people"] for r in data["table"]}
    assert rows["Welfare"]["pa"]["count"] == 1 and rows["Welfare"]["pa"]["pct"] == 50.0
    assert rows["Welfare"]["pc"]["count"] == 3 and rows["Welfare"]["pc"]["pct"] == 100.0
    assert rows["Development"]["pb"]["pct"] == 100.0
    assert rows["Development"]["pc"]["count"] == 0
    assert set(data["scatter"]) == set(IDS)


def test_sentiment_per_person():
    dist = ok(f"/api/sentiment?{QS}")["comment_sentiment"]
    assert dist == {
        "pa": {"Positive": 1, "Negative": 1},
        "pb": {"Positive": 1},
        "pc": {"Neutral": 1},
    }


def test_comments_per_person_and_issue_drilldown():
    people = ok(f"/api/comments?{QS}")["people"]
    assert people["pa"]["total_comments"] == 2
    assert people["pa"]["theme_breakdown"] == {"Praise": 1, "Criticism": 1}
    assert [i["issue"] for i in people["pc"]["issues"]] == []

    roads = ok(f"/api/comments/issues/Roads?{QS}")
    assert {i["person_id"] for i in roads["items"]} == {"pa", "pb"}
    only_c = ok("/api/comments/issues/Roads?person_ids=pc")
    assert only_c["items"] == []
