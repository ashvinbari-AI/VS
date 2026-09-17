"""
REGRESSION TESTING (spec sections 26/27/55). Compares a flat set of
tracked scalar metrics from the current evaluation run against a stored
baseline, and flags REGRESSION when a metric drops by more than the
configured `regression.max_allowed_drop_pct_points` threshold (percentage
points, not percent-of-percent) -- everything else is STABLE or IMPROVED.

Baselines are plain JSON files under evaluation/regression/baseline/,
never written automatically -- promoting a run to be the new baseline is
an explicit action (`save_as_baseline`), not a side effect of running the
evaluator, so a baseline can't silently drift.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evaluation.config.thresholds import load_thresholds
from evaluation.utils.backend_bridge import EVAL_ROOT
from evaluation.utils.io import read_json

BASELINE_DIR = EVAL_ROOT / "regression" / "baseline"
CURRENT_DIR = EVAL_ROOT / "regression" / "current"

# Metrics this project tracks run-over-run, and where to find each one in
# a full report (see evaluation/run.py's report shape). Dotted path into
# the report dict; missing -> None, never fabricated.
TRACKED_METRICS = {
    "data.completeness_pct": ("scraper", "completeness", "content", "record_completeness", "completeness_pct"),
    "data.quality_pct": ("scraper", "data_quality", "content", "data_quality_pct"),
    "data.duplicate_f1": ("scraper", "duplicates", "f1"),
    "analytics.engagement_all_passed": ("metrics", "engagement", "all_passed"),
    "analytics.activity_all_passed": ("metrics", "activity", "all_passed"),
    "analytics.comparison_all_passed": ("comparison", "comparison", "all_passed"),
    "nlp.sentiment_macro_f1": ("nlp", "sentiment", "macro_f1"),
    "nlp.narrative_macro_f1": ("nlp", "narrative", "macro_f1"),
    "nlp.comment_theme_macro_f1": ("nlp", "comment_theme", "macro_f1"),
    "nlp.issue_macro_f1": ("nlp", "issues", "macro_f1"),
}


def _dig(d: dict, path: tuple[str, ...]) -> Any:
    cur = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur if isinstance(cur, (int, float, bool)) else None


def flatten_metrics(report: dict) -> dict[str, float | bool | None]:
    return {name: _dig(report, path) for name, path in TRACKED_METRICS.items()}


def load_baseline(run_id: str = "latest") -> dict | None:
    path = BASELINE_DIR / f"{run_id}.json"
    return read_json(path)


def save_as_baseline(metrics: dict, run_id: str = "latest") -> Path:
    import json
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    path = BASELINE_DIR / f"{run_id}.json"
    path.write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    return path


def compare_to_baseline(current_metrics: dict, baseline_metrics: dict | None) -> dict:
    max_drop = (load_thresholds().get("regression", {}) or {}).get("max_allowed_drop_pct_points", 3.0)
    if baseline_metrics is None:
        return {"has_baseline": False, "note": "no baseline saved yet -- run with --save-baseline first",
                "metrics": {}}

    results = {}
    for name, cur_val in current_metrics.items():
        base_val = baseline_metrics.get(name)
        if base_val is None or cur_val is None or isinstance(cur_val, bool) or isinstance(base_val, bool):
            status = "NOT_COMPARABLE" if (base_val is None or cur_val is None) else (
                "STABLE" if cur_val == base_val else ("IMPROVED" if cur_val and not base_val else "REGRESSION"))
            results[name] = {"baseline": base_val, "current": cur_val, "diff": None, "status": status}
            continue
        # Values here are stored as fractions (0-1) or percentages (0-100)
        # depending on the metric; the threshold is expressed in the same
        # percentage-point units the metric itself uses, on the scale
        # >=1 heuristic below, so a 0.87->0.81 F1 drop reads as -6 points.
        scale = 100 if abs(cur_val) <= 1 and abs(base_val) <= 1 else 1
        diff = round((cur_val - base_val) * scale, 4)
        if diff < -max_drop:
            status = "REGRESSION"
        elif diff > max_drop:
            status = "IMPROVED"
        else:
            status = "STABLE"
        results[name] = {"baseline": base_val, "current": cur_val, "diff": diff, "status": status}

    return {"has_baseline": True, "max_allowed_drop_pct_points": max_drop, "metrics": results}
