"""Smoke tests for the /api/evaluation/* surface -- a thin bridge into the
independent evaluation/ package (project root). Full evaluator behavior
is tested in evaluation/tests/; this only checks the API wiring itself."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_overview_returns_a_full_scorecard():
    r = client.get("/api/evaluation/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "scorecard" in body["data"]
    assert "sample_sizes" in body["data"]


def test_thresholds_endpoint():
    r = client.get("/api/evaluation/thresholds")
    assert r.status_code == 200
    assert "data" in r.json()["data"]  # thresholds.yaml's top-level "data" category


def test_run_rejects_unknown_module():
    r = client.post("/api/evaluation/run", json={"module": "not_a_real_module"})
    assert r.status_code == 400


def test_run_single_module_without_persisting():
    r = client.post("/api/evaluation/run", json={"module": "comparison", "persist": False})
    assert r.status_code == 200
    assert r.json()["data"]["modules_run"] == ["comparison"]


def test_missing_saved_report_is_404():
    r = client.get("/api/evaluation/reports/this_run_id_does_not_exist")
    assert r.status_code == 404


def test_list_reports_returns_a_list():
    r = client.get("/api/evaluation/reports")
    assert r.status_code == 200
    assert isinstance(r.json()["data"]["run_ids"], list)
