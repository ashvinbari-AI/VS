"""Person configuration CRUD (spec section 5) -- multiple saved people,
not just a fixed Person A / Person B pair."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, HTTPException

from app.models.common import ApiResponse
from app.models.profile import PersonConfigCreate, PersonConfigUpdate
from app.storage import json_store

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or uuid.uuid4().hex[:8]


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
        "instagram_url": payload.instagram_url, "facebook_url": payload.facebook_url,
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
        existing[field] = value
    existing["updated_at"] = json_store.now_iso()
    json_store.save_person(existing)
    return ApiResponse.ok(existing)


@router.delete("/{person_id}")
def delete_profile(person_id: str) -> ApiResponse:
    ok = json_store.delete_person(person_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Person not found")
    return ApiResponse.ok({"deleted": person_id})
