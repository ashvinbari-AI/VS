"""Person configuration CRUD (spec section 5) -- multiple saved people,
not just a fixed Person A / Person B pair."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

import pandas as pd

from fastapi import APIRouter, HTTPException

from app.models.common import ApiResponse
from app.models.profile import PersonConfigCreate, PersonConfigUpdate
from app.config import get_settings
from app.storage import json_store
from app.storage.paths import comments_parquet_path, content_parquet_path, profiles_parquet_path

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or uuid.uuid4().hex[:8]


def _clean_instagram_url(url: str | None) -> str | None:
    """Strip ?hl=en / tracking params -- the scraper appends paths like
    "/reels/" to this URL. (Facebook is left alone: profile.php?id=... needs
    its query string.)"""
    if not url:
        return url
    return url.strip().split("#")[0].split("?")[0].rstrip("/") + "/"


@router.get("")
def list_profiles() -> ApiResponse:
    return ApiResponse.ok(json_store.list_people())


@router.post("")
def create_profile(payload: PersonConfigCreate) -> ApiResponse:
    now = json_store.now_iso()
    base_id = _slugify(payload.name)
    person_id = base_id
    suffix = 1
    while json_store.get_person(person_id) is not None:
        suffix += 1
        person_id = f"{base_id}_{suffix}"
    doc = {
        "id": person_id, "name": payload.name,
        "instagram_url": _clean_instagram_url(payload.instagram_url), "facebook_url": payload.facebook_url,
        "instagram_profile_key": None, "facebook_profile_key": None,
        "created_at": now, "updated_at": now, "notes": payload.notes,
    }
    json_store.save_person(doc)
    return ApiResponse.ok(doc)


@router.put("/{person_id}")
def update_profile(person_id: str, payload: PersonConfigUpdate) -> ApiResponse:
    existing = json_store.get_person(person_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    # exclude_unset already distinguishes "field omitted" from "field sent
    # as null" -- do NOT also skip None values here, or a client can never
    # clear a field (e.g. removing a facebook_url) via this endpoint.
    for field, value in payload.model_dump(exclude_unset=True).items():
        existing[field] = _clean_instagram_url(value) if field == "instagram_url" else value
    existing["updated_at"] = json_store.now_iso()
    json_store.save_person(existing)
    return ApiResponse.ok(existing)


def _remove_dir(root: Path, person_id: str) -> bool:
    """rmtree root/person_id, refusing anything that resolves outside root."""
    target = (root / person_id).resolve()
    if target.parent != root.resolve() or not target.is_dir():
        return False
    shutil.rmtree(target)
    return True


def _drop_rows(path: Path, person_id: str) -> int:
    """Rewrite one processed Parquet file without this person's rows."""
    if not path.exists():
        return 0
    df = pd.read_parquet(path)
    if "person_id" not in df.columns:
        return 0
    keep = df["person_id"] != person_id
    removed = int((~keep).sum())
    if removed:
        df[keep].to_parquet(path, index=False)
    return removed


@router.delete("/{person_id}")
def delete_profile(person_id: str) -> ApiResponse:
    """Delete the person AND all their data: raw scrapes, per-person analysis
    output and their rows in the processed Parquet files. Demo (mock) data
    is never touched. Not reversible."""
    if not json_store.get_person(person_id):
        raise HTTPException(status_code=404, detail="Person not found")
    s = get_settings()
    removed = {
        "raw_files": _remove_dir(s.raw_dir, person_id),
        "analysis_files": _remove_dir(s.analysis_dir, person_id),
        "content_rows": _drop_rows(content_parquet_path(), person_id),
        "comment_rows": _drop_rows(comments_parquet_path(), person_id),
        "profile_rows": _drop_rows(profiles_parquet_path(), person_id),
    }
    json_store.delete_person(person_id)
    return ApiResponse.ok({"deleted": person_id, "removed": removed})
