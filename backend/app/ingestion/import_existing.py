"""'Load Existing Data' -- copy an already-scraped output folder (e.g. this
project's own ./output/instagram) into a person's raw evidence tree without
touching the source. Never moves or deletes the original.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from app.storage.paths import person_import_dir

_KNOWN_FILES = ("posts.jsonl", "comments.jsonl", "users.jsonl", "scrape_runs.jsonl",
                "posts.csv", "comments.csv", "users.csv", "scrape_runs.csv")


def import_existing_output(person_id: str, platform: str, source_dir: str | Path) -> dict:
    src = Path(source_dir)
    if not src.exists() or not src.is_dir():
        return {"ok": False, "error": f"Source directory not found: {src}", "copied": []}

    found = [f for f in _KNOWN_FILES if (src / f).exists()]
    if not found:
        return {"ok": False,
                 "error": f"No recognizable scraper output ({', '.join(_KNOWN_FILES[:4])}) in {src}",
                 "copied": []}

    dest = person_import_dir(person_id, platform)
    copied = []
    for name in found:
        shutil.copy2(src / name, dest / name)
        copied.append(str(dest / name))

    return {"ok": True, "error": None, "dest_dir": str(dest), "copied": copied}
