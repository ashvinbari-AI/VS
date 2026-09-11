from __future__ import annotations

from fastapi import APIRouter

from app.models.common import ApiResponse
from app.nlp.engine import nlp_status
from app.storage.data_source import is_demo_mode

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> ApiResponse:
    status = nlp_status()
    return ApiResponse.ok({
        "status": "ok",
        "mode": "LOCAL",
        "demo_mode": is_demo_mode(),
        "nlp_mode": status["effective_mode"],
    })
