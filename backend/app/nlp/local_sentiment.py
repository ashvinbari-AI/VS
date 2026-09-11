"""
Optional local, fully-offline sentiment classifier -- a step up in quality
from the keyword lexicon (sentiment.rule_based_sentiment) that needs no
Gemini API key and sends no data off this machine. Configured entirely by
two env vars (see .env.example):

  SENTIMENT_MODEL           HuggingFace model id for non-Devanagari text
                             (English, transliterated, ...).
  MARATHI_SENTIMENT_MODEL   HuggingFace model id for Devanagari-script text.
                             This project's own narrative keyword list
                             (narrative.py) is Marathi-only, not Hindi, so
                             Devanagari here is treated as Marathi.

SENTIMENT ONLY -- narrative / comment-theme / issue-extraction have no
local-transformer tier and stay on the keyword lexicon unless Gemini is
enabled. Both env vars unset (the default) makes this module a no-op:
sentiment.py keeps using the lexicon exactly as before.

Needs `pip install transformers torch` -- see requirements.txt. Same
defensive contract as gemini_client.py: any failure (package missing, model
download/load failure, inference error, or a label the model's own output
can't be confidently mapped to one of SENTIMENT_LABELS) returns None so the
caller falls back to the lexicon. This never crashes the request and never
guesses at a label it can't actually attribute to the model's own output.
"""

from __future__ import annotations

import re
from typing import Any

from app.config import get_settings
from app.logging_setup import get_logger

_pipeline_cache: dict[str, Any] = {}

# Marathi (like Hindi) is written in Devanagari -- this project's own text
# is Maharashtra political content, so Devanagari here means Marathi.
_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.sentiment_model or settings.marathi_sentiment_model)


def _model_for(text: str) -> str | None:
    settings = get_settings()
    if _DEVANAGARI_RE.search(text):
        return settings.marathi_sentiment_model or settings.sentiment_model
    return settings.sentiment_model or settings.marathi_sentiment_model


def _get_pipeline(model_name: str):
    if model_name in _pipeline_cache:
        return _pipeline_cache[model_name]
    try:
        from transformers import pipeline
    except ImportError:
        return None
    try:
        pipe = pipeline("sentiment-analysis", model=model_name, top_k=None)
    except Exception:
        pipe = None
    _pipeline_cache[model_name] = pipe
    return pipe


def _normalize_label(raw_label: str) -> str | None:
    """Map whatever string the model's own config names its class to one of
    SENTIMENT_LABELS -- or None if it can't be attributed with confidence
    (e.g. a generic "LABEL_0" with no id2label mapping baked into the model
    config: guessing an arbitrary index order would be exactly the kind of
    invented value this codebase never allows)."""
    key = raw_label.strip().lower()
    if "pos" in key:
        return "Positive"
    if "neg" in key:
        return "Negative"
    if "neu" in key:
        return "Neutral"
    return None


def classify(text: str) -> dict | None:
    settings = get_settings()
    logger = get_logger("analysis", settings.logs_dir)
    model_name = _model_for(text)
    if not model_name:
        return None
    pipe = _get_pipeline(model_name)
    if pipe is None:
        return None
    try:
        result = pipe(text[:2000], truncation=True)
    except Exception as e:
        logger.warning("Local sentiment model '%s' call failed (%s) -- falling back to lexicon",
                        model_name, type(e).__name__)
        return None
    # A single string input with top_k=None returns a flat list of
    # {"label", "score"} dicts, one per class -- take the highest score.
    scores = result[0] if result and isinstance(result[0], list) else result
    if not scores:
        return None
    best = max(scores, key=lambda s: s["score"])
    label = _normalize_label(best["label"])
    if not label:
        logger.warning("Local sentiment model '%s' returned an unrecognised label '%s' -- "
                        "falling back to lexicon rather than guess its meaning",
                        model_name, best["label"])
        return None
    return {"sentiment": label, "confidence": round(float(best["score"]), 4),
            "model": f"transformer:{model_name}"}
