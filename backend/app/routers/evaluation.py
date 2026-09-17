"""
GET/POST surface over the independent evaluation/ package (project root,
sibling to backend/) -- exposes what evaluation/run.py already computes to
the React dashboard. Trimmed from spec section 34's full 14-endpoint list
to what a first dashboard pass actually needs; see evaluation/README.md
for the fuller list of what's not built yet.

Every run here is synchronous: the deterministic + ground-truth evaluators
run in well under a second even against this project's real ~20k-comment
dataset, so there is no background job/polling layer here unlike
/api/scrape or /api/analysis.

This is the ONLY backend file that reaches into evaluation/ -- the
reverse of evaluation/utils/backend_bridge.py, which is the only file in
evaluation/ that reaches into backend/. Neither package imports the other
except through these two single seams.
"""

from __future__ import annotations

import sys
from pathlib import Path

# evaluation/ lives one level ABOVE backend/ -- not on sys.path when this
# process is started as `uvicorn app.main:app` from inside backend/.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.common import ApiResponse

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


class RunRequest(BaseModel):
    module: str = "all"           # "all" | "scraper" | "metrics" | "nlp" | "comparison"
    save_baseline: bool = False   # promote this run's metrics to the new regression baseline
    persist: bool = True          # write the JSON/CSV report files under evaluation/reports/


@router.get("/overview")
def get_overview() -> ApiResponse:
    """A fresh, unpersisted run of every module -- the dashboard's default
    landing view. Use POST /run with persist=true to keep a copy."""
    from evaluation.run import build_report
    return ApiResponse.ok(build_report("all"))


@router.get("/thresholds")
def get_thresholds() -> ApiResponse:
    """This project's own PASS/WARNING/FAIL bands (evaluation/config/
    thresholds.yaml) -- shown in the UI so a status is never a black box."""
    from evaluation.config.thresholds import load_thresholds
    return ApiResponse.ok(load_thresholds())


@router.post("/run")
def run_evaluation(payload: RunRequest) -> ApiResponse:
    valid_modules = {"all", "scraper", "metrics", "nlp", "comparison"}
    if payload.module not in valid_modules:
        raise HTTPException(status_code=400, detail=f"module must be one of {sorted(valid_modules)}")

    from evaluation.evaluators import regression
    from evaluation.run import build_report
    from evaluation.utils.io import write_csv_report, write_json_report

    report = build_report(payload.module)

    if payload.save_baseline:
        regression.save_as_baseline(regression.flatten_metrics(report))

    if payload.persist:
        write_json_report(report["run_id"], report)
        write_csv_report(f"{report['run_id']}_scorecard", report["scorecard"])

    return ApiResponse.ok(report)


@router.get("/reports")
def list_reports() -> ApiResponse:
    """Saved run ids, newest first -- for a run-history picker."""
    from evaluation.utils.io import list_report_run_ids
    return ApiResponse.ok({"run_ids": list_report_run_ids()})


@router.get("/reports/{run_id}")
def get_report(run_id: str) -> ApiResponse:
    from evaluation.utils.io import read_report
    report = read_report(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"No saved report '{run_id}'")
    return ApiResponse.ok(report)
