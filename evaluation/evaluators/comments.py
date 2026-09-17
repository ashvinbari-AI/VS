"""COMMENT THEME EVALUATION (spec section 21). Human theme_ground_truth
(via comments_ground_truth.json's `expected_theme` /
sentiment_ground_truth.json-shaped entries with record_type="comment")
vs the cached MODEL-CLASSIFIED comment theme."""

from __future__ import annotations

from evaluation.metrics.classification import classification_report


def evaluate_comment_theme(ground_truth: list[dict], nlp_cache: dict) -> dict:
    """`ground_truth` entries: {"comment_id", "human_label"}."""
    y_true, y_pred, errors = [], [], []
    unclassified = 0

    for gt in ground_truth:
        cid, human = gt.get("comment_id") or gt.get("record_id"), gt.get("human_label")
        if not cid or human is None:
            continue
        entry = nlp_cache.get(f"comment:{cid}")
        if not entry or entry.get("theme") is None:
            unclassified += 1
            continue
        predicted = entry["theme"]
        y_true.append(human)
        y_pred.append(predicted)
        if human != predicted:
            errors.append({"comment_id": cid, "human_label": human, "model_label": predicted,
                            "error_type": "wrong_class"})

    if not y_true:
        return {"n": 0, "unclassified": unclassified,
                "note": "no ground-truth comment-theme records have a cached model prediction yet"}

    report = classification_report(y_true, y_pred)
    report["unclassified"] = unclassified
    report["errors"] = errors
    return report
