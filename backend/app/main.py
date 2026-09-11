"""
Political Person Social Media Intelligence -- FastAPI backend.

LOCAL-ONLY: the only outbound network call this process ever makes is to
Gemini, and only when GEMINI_API_KEY is set and NLP is enabled in settings.
Run with: uvicorn app.main:app --reload --port 8000  (from backend/)
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.logging_setup import get_logger
from app.models.common import ApiResponse
from app.routers import (
    activity, analysis, comments, comparison, content, data_sources,
    engagement, health, narratives, overview, profiles, scrape,
    sentiment, settings as settings_router, timeline,
)

settings = get_settings()
settings.ensure_dirs()
logger = get_logger("backend", settings.logs_dir)

app = FastAPI(
    title="Political Person Social Media Intelligence",
    description="Instagram + Facebook Political Profile Comparison Platform (local-only)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content=ApiResponse.fail(
        "INTERNAL_ERROR", str(exc)).model_dump())


for router in (
    health.router, profiles.router, scrape.router, analysis.router,
    overview.router, comparison.router, activity.router, engagement.router,
    content.router, narratives.router, sentiment.router, comments.router,
    timeline.router, data_sources.router, settings_router.router,
):
    app.include_router(router)


@app.get("/")
def root() -> ApiResponse:
    return ApiResponse.ok({
        "name": "Political Person Social Media Intelligence",
        "mode": "LOCAL",
        "docs": "/docs",
    })
