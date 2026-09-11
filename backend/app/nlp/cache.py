"""data/analysis/nlp_cache.json -- keyed by content_id (spec section 34).

If a content_id is already cached, its result is reused rather than
re-analyzed -- the app never re-spends a Gemini call (or re-runs the
rule-based pass) on the same content unless the caller explicitly clears
the cache or re-requests analysis for that id.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.config import get_settings

# RLock, not Lock: put_many() acquires this and then calls save_cache(),
# which acquires it again in the same thread -- a plain Lock would deadlock.
_lock = threading.RLock()


def _path() -> Path:
    return get_settings().nlp_cache_path


def load_cache() -> dict[str, dict[str, Any]]:
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_cache(cache: dict[str, dict[str, Any]]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        p.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def get_cached(content_id: str) -> dict[str, Any] | None:
    return load_cache().get(content_id)


def put_many(entries: dict[str, dict[str, Any]]) -> None:
    if not entries:
        return
    with _lock:
        cache = load_cache()
        cache.update(entries)
        save_cache(cache)
