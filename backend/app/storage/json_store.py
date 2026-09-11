"""Small local JSON stores: person configs, runtime settings, job records.

Not a database -- plain files, one per entity, because the volumes here
(a handful of person configs, a handful of jobs) don't need Parquet.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings


def _people_dir() -> Path:
    d = get_settings().configs_dir / "people"
    d.mkdir(parents=True, exist_ok=True)
    return d


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def list_people() -> list[dict[str, Any]]:
    out = []
    for f in sorted(_people_dir().glob("*.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def get_person(person_id: str) -> dict[str, Any] | None:
    f = _people_dir() / f"{person_id}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_person(doc: dict[str, Any]) -> dict[str, Any]:
    f = _people_dir() / f"{doc['id']}.json"
    f.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc


def delete_person(person_id: str) -> bool:
    f = _people_dir() / f"{person_id}.json"
    if not f.exists():
        return False
    f.unlink()
    return True


def _settings_path() -> Path:
    return get_settings().runtime_settings_path


DEFAULT_RUNTIME_SETTINGS = {
    "gemini_model": "gemini-2.0-flash",
    "nlp_enabled": False,
    "analysis_batch_size": 20,
    "data_directory": str(get_settings().data_dir),
    "date_format": "DD MMM YYYY",
    "theme": "light",
    "auto_refresh": False,
    "default_comparison_period_days": 30,
}


def load_runtime_settings() -> dict[str, Any]:
    f = _settings_path()
    if not f.exists():
        return dict(DEFAULT_RUNTIME_SETTINGS)
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(DEFAULT_RUNTIME_SETTINGS)
    merged = dict(DEFAULT_RUNTIME_SETTINGS)
    merged.update(data)
    return merged


def save_runtime_settings(patch: dict[str, Any]) -> dict[str, Any]:
    current = load_runtime_settings()
    current.update({k: v for k, v in patch.items() if v is not None})
    f = _settings_path()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current
