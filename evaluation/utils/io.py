"""Small, boring I/O helpers shared by every evaluator: load a ground-truth
JSON file (schema'd-but-empty is a valid, expected state until someone
annotates it), and write a report out as JSON/CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from evaluation.utils.backend_bridge import EVAL_ROOT

GROUND_TRUTH_DIR = EVAL_ROOT / "ground_truth"
REPORTS_DIR = EVAL_ROOT / "reports"


def load_ground_truth(filename: str) -> list[dict]:
    """Loads evaluation/ground_truth/<filename>. Returns [] (not an error)
    when the file is missing or empty -- that's the honest "no manually
    verified data yet" state, not a bug, and every evaluator must degrade
    to "cannot evaluate this module yet" rather than crash on it."""
    path = GROUND_TRUTH_DIR / filename
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def write_json_report(name: str, payload: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def write_csv_report(name: str, rows: list[dict]) -> Path | None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if not rows:
        return None
    path = REPORTS_DIR / f"{name}.csv"
    fields: list[str] = []
    for row in rows:
        for k in row:
            if k not in fields:
                fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                              for k, v in row.items()})
    return path


def read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def list_report_run_ids() -> list[str]:
    """Every saved run's id (its JSON report's filename stem), newest
    first. Used to populate a run-history picker without reading every
    report's full contents just to list them."""
    if not REPORTS_DIR.exists():
        return []
    ids = [p.stem for p in REPORTS_DIR.glob("*.json")]
    return sorted(ids, reverse=True)


def read_report(run_id: str) -> dict | None:
    return read_json(REPORTS_DIR / f"{run_id}.json")
