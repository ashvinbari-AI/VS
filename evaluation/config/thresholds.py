"""Loads evaluation/config/thresholds.yaml and turns a raw metric value
into PASS / WARNING / FAIL (spec section 28). These are this project's own
acceptance bars, not an industry standard -- see the YAML file's header."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

THRESHOLDS_PATH = Path(__file__).with_name("thresholds.yaml")


@lru_cache
def load_thresholds() -> dict[str, Any]:
    if not THRESHOLDS_PATH.exists():
        return {}
    return yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8")) or {}


def get_threshold(category: str, metric: str) -> dict | None:
    return load_thresholds().get(category, {}).get(metric)


def status_for(category: str, metric: str, value: float | None) -> str:
    """PASS / WARNING / FAIL / NOT_EVALUATED. `value=None` (e.g. no ground
    truth yet to compute the metric at all) is NOT_EVALUATED, never a
    silent PASS or FAIL -- an untested module must never look like a
    passing one."""
    if value is None:
        return "NOT_EVALUATED"
    band = get_threshold(category, metric)
    if not band:
        return "NOT_EVALUATED"
    pass_at = band.get("pass")
    warn_at = band.get("warn")
    if pass_at is not None and value >= pass_at:
        return "PASS"
    if warn_at is not None and value >= warn_at:
        return "WARNING"
    return "FAIL"
