"""
FIELD ACCURACY (spec section 8) -- are the individual field *values*
correct, not just present. Requires posts_ground_truth.json /
comments_ground_truth.json entries (manually verified against the real
post/comment on the platform) -- with none, every field reports
NOT_EVALUATED rather than a fabricated 100%.
"""

from __future__ import annotations

from typing import Any

from evaluation.metrics.classification import classification_report, safe_divide
from evaluation.utils.data_loader import index_by

POST_FIELDS = ["caption", "published_at", "content_type", "likes", "comments", "shares"]
COMMENT_FIELDS = ["comment_text"]

# Ground truth uses "comments"/"content_type" naming (spec's own example);
# production NormalizedContent uses "comments_count". Mapped here once so
# every evaluator/report can show the ground-truth field name.
_GT_TO_PRODUCTION_FIELD = {"comments": "comments_count"}


def _values_match(field: str, expected: Any, actual: Any) -> bool:
    if expected is None and actual is None:
        return True
    if expected is None or actual is None:
        return False
    if field in ("likes", "comments", "shares"):
        try:
            return int(expected) == int(actual)
        except (TypeError, ValueError):
            return False
    if field == "published_at":
        # Compare only up to the minute -- timezone-normalization/seconds
        # rounding differences are not what this evaluator is checking for.
        return str(expected)[:16] == str(actual)[:16]
    return str(expected).strip() == str(actual).strip()


def evaluate_post_fields(ground_truth_posts: list[dict], production_records: list[dict],
                          fields: list[str] = POST_FIELDS) -> dict:
    by_id = index_by(production_records, "content_id")
    per_field = {f: {"correct": 0, "incorrect": 0, "missing": 0, "tested": 0, "mismatches": []}
                 for f in fields}
    records_tested = 0
    records_found = 0

    for gt in ground_truth_posts:
        cid = gt.get("content_id")
        if not cid:
            continue
        records_tested += 1
        prod = by_id.get(cid)
        if prod is None:
            for f in fields:
                if f in gt:
                    per_field[f]["missing"] += 1
                    per_field[f]["tested"] += 1
            continue
        records_found += 1
        for f in fields:
            if f not in gt:
                continue
            per_field[f]["tested"] += 1
            prod_field = _GT_TO_PRODUCTION_FIELD.get(f, f)
            actual = prod.get(prod_field)
            if _values_match(f, gt[f], actual):
                per_field[f]["correct"] += 1
            else:
                per_field[f]["incorrect"] += 1
                per_field[f]["mismatches"].append({
                    "content_id": cid, "expected": gt[f], "actual": actual,
                })

    for f, stats in per_field.items():
        stats["accuracy_pct"] = (round(safe_divide(stats["correct"], stats["tested"]) * 100, 2)
                                  if stats["tested"] else None)

    total_correct = sum(s["correct"] for s in per_field.values())
    total_tested = sum(s["tested"] for s in per_field.values())

    return {
        "records_tested": records_tested, "records_found_in_production": records_found,
        "per_field": per_field,
        "overall_field_accuracy_pct": (round(safe_divide(total_correct, total_tested) * 100, 2)
                                        if total_tested else None),
    }


def evaluate_comment_fields(ground_truth_comments: list[dict], production_records: list[dict],
                             fields: list[str] = COMMENT_FIELDS) -> dict:
    by_id = index_by(production_records, "comment_id")
    per_field = {f: {"correct": 0, "incorrect": 0, "missing": 0, "tested": 0, "mismatches": []}
                 for f in fields}
    for gt in ground_truth_comments:
        cid = gt.get("comment_id")
        if not cid:
            continue
        prod = by_id.get(cid)
        for f in fields:
            if f not in gt:
                continue
            per_field[f]["tested"] += 1
            if prod is None:
                per_field[f]["missing"] += 1
                continue
            actual = prod.get(f)
            if _values_match(f, gt[f], actual):
                per_field[f]["correct"] += 1
            else:
                per_field[f]["incorrect"] += 1
                per_field[f]["mismatches"].append({"comment_id": cid, "expected": gt[f], "actual": actual})

    for f, stats in per_field.items():
        stats["accuracy_pct"] = (round(safe_divide(stats["correct"], stats["tested"]) * 100, 2)
                                  if stats["tested"] else None)
    return {"per_field": per_field}


def evaluate_content_type_classification(ground_truth_posts: list[dict], production_records: list[dict]) -> dict:
    """Content-type accuracy/precision/recall/F1 + confusion matrix (spec
    section 15) -- Post/Reel/Video/Photo/Text, human-labeled vs what the
    scraper+normalize.py actually recorded."""
    by_id = index_by(production_records, "content_id")
    y_true, y_pred = [], []
    for gt in ground_truth_posts:
        cid = gt.get("content_id")
        if not cid or "content_type" not in gt:
            continue
        prod = by_id.get(cid)
        if prod is None:
            continue
        y_true.append(gt["content_type"])
        y_pred.append(prod.get("content_type"))

    if not y_true:
        return {"n": 0, "note": "no ground-truth posts with content_type overlap production data yet"}
    return classification_report(y_true, y_pred)
