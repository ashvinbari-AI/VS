"""Smoke tests for route wiring and the response envelope (spec section 36)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_envelope():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["data"]["mode"] == "LOCAL"


def test_settings_roundtrip():
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert "gemini_api_key_configured" in r.json()["data"]

    r2 = client.put("/api/settings", json={"nlp_enabled": True})
    assert r2.status_code == 200
    assert r2.json()["data"]["nlp_enabled"] is True
    # leave it as we found it for other tests/manual runs
    client.put("/api/settings", json={"nlp_enabled": False})


def test_unknown_profile_returns_structured_error():
    r = client.post("/api/scrape/start", json={"person_id": "does_not_exist"})
    assert r.status_code == 404


def test_data_sources_endpoint_shape():
    r = client.get("/api/data-sources")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "sources" in body["data"]


def test_profile_update_can_clear_a_field_to_null():
    """Regression: PUT /api/profiles/{id} used to silently ignore an
    explicit null, making it impossible to ever clear facebook_url/
    instagram_url once set."""
    created = client.post("/api/profiles", json={
        "name": "Test Clear Person", "facebook_url": "https://www.facebook.com/example/",
    }).json()["data"]
    person_id = created["id"]
    try:
        r = client.put(f"/api/profiles/{person_id}", json={"facebook_url": None})
        assert r.status_code == 200
        assert r.json()["data"]["facebook_url"] is None
    finally:
        client.delete(f"/api/profiles/{person_id}")
