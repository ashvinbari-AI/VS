"""
DATA COMPLETENESS (spec section 7) -- deliberately NOT called "accuracy".
This module only answers "did we get the records/fields we expected to
get", never "are the values in them correct" (that's field_accuracy.py).

Two independent numbers, both reported, never blended into one score:

  record_completeness -- only computable when a ground-truth manifest of
    what SHOULD exist is available (evaluation/ground_truth/*.json).
    completeness% = (expected content_ids also found in production) /
                     (expected content_ids) * 100.

  field_completeness -- needs no ground truth at all: for each field this
    project actually expects (dates, captions, likes, comments, followers),
    what % of production rows have a non-null value.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from evaluation.metrics.classification import safe_divide

CONTENT_FIELDS = ["published_at", "caption", "likes", "comments_count"]
PROFILE_FIELDS = ["followers"]


def field_completeness(df: pd.DataFrame, fields: list[str]) -> dict[str, dict]:
    total = len(df)
    out: dict[str, dict] = {}
    for field in fields:
        if field not in df.columns:
            out[field] = {"available": 0, "total": total, "completeness_pct": None,
                           "note": "column not present in production output at all"}
            continue
        available = int(df[field].notna().sum())
        out[field] = {
            "available": available, "total": total,
            "completeness_pct": round(safe_divide(available, total) * 100, 2) if total else None,
        }
    return out


def record_completeness(expected_ids: set[str], production_ids: set[str]) -> dict[str, Any]:
    if not expected_ids:
        return {"expected": 0, "found": 0, "missing": [], "extra": [],
                "completeness_pct": None,
                "note": "no ground-truth manifest -- add records to posts_ground_truth.json to evaluate this"}
    found = expected_ids & production_ids
    missing = sorted(expected_ids - production_ids)
    extra = sorted(production_ids - expected_ids)
    return {
        "expected": len(expected_ids), "found": len(found),
        "missing": missing, "missing_count": len(missing),
        "extra_count": len(extra),
        "completeness_pct": round(len(found) / len(expected_ids) * 100, 2),
    }


def evaluate_content_completeness(content_df: pd.DataFrame, ground_truth_posts: list[dict]) -> dict:
    expected_ids = {r["content_id"] for r in ground_truth_posts if r.get("content_id")}
    production_ids = set(content_df["content_id"]) if "content_id" in content_df.columns else set()

    type_dist = (content_df["content_type"].value_counts().to_dict()
                 if "content_type" in content_df.columns and not content_df.empty else {})

    return {
        "total_posts": int(len(content_df)),
        "content_type_breakdown": type_dist,
        "record_completeness": record_completeness(expected_ids, production_ids),
        "field_completeness": field_completeness(content_df, CONTENT_FIELDS),
    }


def evaluate_comments_completeness(comments_df: pd.DataFrame, ground_truth_comments: list[dict]) -> dict:
    expected_ids = {r["comment_id"] for r in ground_truth_comments if r.get("comment_id")}
    production_ids = set(comments_df["comment_id"]) if "comment_id" in comments_df.columns else set()
    return {
        "total_comments": int(len(comments_df)),
        "record_completeness": record_completeness(expected_ids, production_ids),
        "field_completeness": field_completeness(comments_df, ["comment_text", "commented_at"]),
    }


def evaluate_profiles_completeness(profiles_df: pd.DataFrame) -> dict:
    return {
        "total_profile_snapshots": int(len(profiles_df)),
        "field_completeness": field_completeness(profiles_df, PROFILE_FIELDS),
    }
