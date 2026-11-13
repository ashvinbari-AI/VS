"""
Competitor Analysis -- FastAPI backend.

LOCAL-ONLY: this process makes no outbound network calls of its own (the
scrapers it launches are separate processes).
Run with: uvicorn app.main:app --reload --port 3001  (from backend/)
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.logging_setup import get_logger
from app.models.common import ApiResponse
from app.routers import (
    activity, analysis, comments, comparison, content, data_sources,
    engagement, evaluation, health, overview, profiles, proof, scrape,
    settings as settings_router, timeline,
)

settings = get_settings()
settings.ensure_dirs()
logger = get_logger("backend", settings.logs_dir)

app = FastAPI(
    title="Competitor Analysis",
    description="Instagram + Facebook Competitor Comparison Platform (local-only)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.access_token:
    from app.security import AccessTokenMiddleware
    app.add_middleware(AccessTokenMiddleware, token=settings.access_token)
    logger.info("Access-token gate enabled")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content=ApiResponse.fail(
        "INTERNAL_ERROR", str(exc)).model_dump())


for router in (
    health.router, profiles.router, scrape.router, analysis.router,
    overview.router, comparison.router, activity.router, engagement.router,
    content.router, comments.router,
    timeline.router, data_sources.router, settings_router.router, evaluation.router, proof.router,
):
    app.include_router(router)


@app.get("/api")
def api_root() -> ApiResponse:
    return ApiResponse.ok({
        "name": "Competitor Analysis",
        "mode": "LOCAL",
        "docs": "/docs",
    })


# -- Built frontend (single-port deployment) --
# Real files under dist/ are served as-is; any other non-API path returns
# index.html so React Router can handle client-side routes on refresh.
_dist = settings.frontend_dist
if (_dist / "index.html").is_file():
    if (_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            return JSONResponse(status_code=404, content=ApiResponse.fail(
                "NOT_FOUND", f"No API route /{full_path}").model_dump())
        candidate = (_dist / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_dist.resolve()):
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html", headers={"Cache-Control": "no-cache"})
else:
    @app.get("/")
    def root() -> ApiResponse:
        return api_root()
