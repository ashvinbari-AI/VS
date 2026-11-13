from __future__ import annotations

from fastapi import APIRouter

from app.models.common import ApiResponse
from app.nlp.engine import NLP_MODE
from app.storage.data_source import is_demo_mode

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> ApiResponse:
    return ApiResponse.ok({
        "status": "ok",
        "mode": "LOCAL",
        "demo_mode": is_demo_mode(),
        "nlp_mode": NLP_MODE,
    })
