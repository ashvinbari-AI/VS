"""
Reconciles the two ground-truth annotation styles the spec allows for
NLP tasks: a full post/comment record carrying `expected_*` fields
(comments_ground_truth.json), and a dedicated single-task file
(issues_ground_truth.json) shaped {"record_id", "record_type",
"human_issues"}.

Every NLP evaluator consumes only the merged, canonical shape this module
produces -- this is the one place that reconciles the two sources. Where
the same record appears in both, the dedicated single-task file wins (it
represents a more deliberate, focused annotation pass).
"""

from __future__ import annotations

from evaluation.utils.io import load_ground_truth


def _dedupe_by_id(records: list[dict], id_key: str = "record_id") -> list[dict]:
    seen: dict = {}
    for r in records:
        rid = r.get(id_key)
        if rid:
            seen[rid] = r  # dict insertion order: later entries overwrite earlier ones
    return list(seen.values())


def comment_theme_ground_truth() -> list[dict]:
    out = []
    for c in load_ground_truth("comments_ground_truth.json"):
        if c.get("expected_theme") and c.get("comment_id"):
            out.append({"record_id": c["comment_id"], "human_label": c["expected_theme"]})
    return out


def issues_ground_truth() -> list[dict]:
    derived = []
    for c in load_ground_truth("comments_ground_truth.json"):
        if c.get("expected_issues") is not None and c.get("comment_id"):
            derived.append({"record_id": c["comment_id"], "human_issues": c["expected_issues"]})
    dedicated = load_ground_truth("issues_ground_truth.json")
    return _dedupe_by_id(derived + dedicated)
