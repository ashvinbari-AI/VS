"""A saved person configuration -- what the UI's Person Setup screen persists.

Stored locally as one JSON file per person under data/configs/people/<id>.json.
Nothing here is scraped data; it's just "who to scrape and from where".
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PersonConfig(BaseModel):
    id: str
    name: str
    instagram_url: str | None = None
    facebook_url: str | None = None
    instagram_profile_key: str | None = None  # slug used as the raw-data folder name
    facebook_profile_key: str | None = None
    created_at: str
    updated_at: str
    notes: str | None = None


class PersonConfigCreate(BaseModel):
    name: str
    instagram_url: str | None = None
    facebook_url: str | None = None
    notes: str | None = None


class PersonConfigUpdate(BaseModel):
    name: str | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    notes: str | None = None
