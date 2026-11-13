from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.demo.demo_data import generate_demo_dataset
from app.models.common import ApiResponse
from app.storage import json_store
from app.storage.data_source import set_demo_mode

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    analysis_batch_size: int | None = None
    date_format: str | None = None
    theme: str | None = None
    auto_refresh: bool | None = None
    default_comparison_period_days: int | None = None
    demo_mode: bool | None = None


@router.get("")
def get_settings_route() -> ApiResponse:
    runtime = json_store.load_runtime_settings()
    runtime["data_directory"] = str(get_settings().data_dir)
    return ApiResponse.ok(runtime)


@router.put("")
def update_settings_route(payload: SettingsUpdate) -> ApiResponse:
    patch = payload.model_dump(exclude_unset=True)
    updated = json_store.save_runtime_settings(patch)
    return ApiResponse.ok(updated)


@router.post("/demo-data")
def load_demo_data() -> ApiResponse:
    """spec section 55 -- generates data/mock/*.parquet (clearly synthetic,
    never mixed with real scraped data) and switches demo_mode on."""
    result = generate_demo_dataset()
    set_demo_mode(True)
    return ApiResponse.ok(result)


@router.post("/demo-data/disable")
def disable_demo_data() -> ApiResponse:
    set_demo_mode(False)
    return ApiResponse.ok({"demo_mode": False})
