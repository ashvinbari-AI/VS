"""Where everything lives on disk (spec section 7)."""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings


def person_raw_dir(person_id: str, platform: str) -> Path:
    s = get_settings()
    d = s.raw_dir / person_id / platform
    d.mkdir(parents=True, exist_ok=True)
    return d


def person_import_dir(person_id: str, platform: str) -> Path:
    """A fresh, timestamped subfolder for an imported (copied) raw dataset --
    keeps every import as distinct audit evidence instead of overwriting."""
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("imported_%Y%m%dT%H%M%SZ")
    d = person_raw_dir(person_id, platform) / stamp
    d.mkdir(parents=True, exist_ok=True)
    return d


def person_analysis_dir(person_id: str) -> Path:
    s = get_settings()
    d = s.analysis_dir / person_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def content_parquet_path() -> Path:
    return get_settings().processed_dir / "content.parquet"


def comments_parquet_path() -> Path:
    return get_settings().processed_dir / "comments.parquet"


def profiles_parquet_path() -> Path:
    return get_settings().processed_dir / "profiles.parquet"
