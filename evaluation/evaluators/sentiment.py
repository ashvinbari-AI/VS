"""
SENTIMENT EVALUATION (spec sections 16/17). Compares HUMAN ground truth
(sentiment_ground_truth.json / the `expected_sentiment` field on posts or
comments) against the production system's own MODEL-CLASSIFIED sentiment
(never called "truth" -- see backend/app/models/content.py's own
docstring on this exact point). Reads whatever is already cached in
data/analysis/nlp_cache.json (spec section 57: NLP evaluation must work
even when Gemini is unreachable, using cached predictions).
"""

from __future__ import annotations

from evaluation.metrics.classification import classification_report


def _production_sentiment(record_id: str, record_type: str, nlp_cache: dict) -> tuple[str | None, str | None]:
    """Returns (sentiment, model) -- both None if nothing was ever cached
    for this record (i.e. Run Analysis hasn't been done on it yet)."""
    key = f"comment:{record_id}" if record_type == "comment" else record_id
    entry = nlp_cache.get(key)
    if not entry:
        return None, None
    return entry.get("sentiment"), entry.get("model")


def evaluate_sentiment(ground_truth: list[dict], nlp_cache: dict) -> dict:
    """`ground_truth` entries: {"record_id", "record_type" ("post"|"comment"),
    "human_label"} -- see ground_truth/README.md's sentiment_ground_truth.json
    schema."""
    y_true, y_pred, errors = [], [], []
    models_used: set[str] = set()
    unclassified = 0

    for gt in ground_truth:
        rid, rtype, human = gt.get("record_id"), gt.get("record_type", "post"), gt.get("human_label")
        if not rid or human is None:
            continue
        predicted, model = _production_sentiment(rid, rtype, nlp_cache)
        if predicted is None:
            unclassified += 1
            continue
        y_true.append(human)
        y_pred.append(predicted)
        if model:
            models_used.add(model)
        if human != predicted:
            errors.append({"record_id": rid, "human_label": human, "model_label": predicted,
                            "model": model, "error_type": "wrong_class"})

    if not y_true:
        return {"n": 0, "unclassified": unclassified,
                "note": "no ground-truth sentiment records have a cached model prediction yet -- "
                        "annotate sentiment_ground_truth.json and run Run Analysis in the app first"}

    report = classification_report(y_true, y_pred)
    report["unclassified"] = unclassified
    report["models_used"] = sorted(models_used)
    report["errors"] = errors
    report["label_note"] = "human_label = manual ground truth; model label = MODEL-CLASSIFIED SENTIMENT, never treated as truth"
    return report
