"""comment_theme.py -- spec section 24. Classifies a comment into one theme."""

from __future__ import annotations

from app.nlp import gemini_client
from app.nlp.categories import COMMENT_THEMES
from app.nlp.sentiment import _NEGATIVE_WORDS, _POSITIVE_WORDS

_QUESTION_MARKERS = ["?", "का ", "कसे", "केव्हा", "कुठे", "कोण", "कधी"]
_REQUEST_MARKERS = ["please", "कृपया", "पाहिजे", "need", "request", "मागणी"]
_POLICY_MARKERS = ["योजना", "धोरण", "policy", "scheme", "budget", "अर्थसंकल्प"]
_ATTACK_MARKERS = ["भ्रष्ट", "चोर", "नालायक", "शरम", "corrupt", "traitor", "गद्दार"]


def rule_based_theme(text: str | None) -> dict | None:
    if not text or not text.strip():
        return None
    lowered = text.lower()

    if any(m.lower() in lowered for m in _ATTACK_MARKERS):
        theme = "Political attack"
    elif any(m.lower() in lowered for m in _QUESTION_MARKERS):
        theme = "Question"
    elif any(m.lower() in lowered for m in _POLICY_MARKERS):
        theme = "Policy discussion"
    elif any(m.lower() in lowered for m in _REQUEST_MARKERS):
        theme = "Request"
    elif any(w in lowered for w in _NEGATIVE_WORDS):
        theme = "Criticism"
    elif any(w in lowered for w in _POSITIVE_WORDS):
        theme = "Praise" if len(text) < 40 else "Support"
    else:
        theme = "Other"

    return {"theme": theme, "confidence": 0.5, "model": "rule_based_v1"}


def gemini_theme(text: str) -> dict | None:
    prompt = (
        f"Classify this social-media comment into exactly one of: {', '.join(COMMENT_THEMES)}. "
        'Respond with ONLY JSON: {"theme": "<label>", "confidence": <0-1 float>}.\n\n'
        f"Comment: {text[:1000]}"
    )
    result = gemini_client.generate_json(prompt)
    if not result or result.get("theme") not in COMMENT_THEMES:
        return None
    from app.config import get_settings
    return {
        "theme": result["theme"],
        "confidence": float(result.get("confidence", 0.7)),
        "model": f"gemini:{get_settings().gemini_model}",
    }


def classify_theme(text: str | None, use_gemini: bool) -> dict | None:
    if not text or not text.strip():
        return None
    if use_gemini and gemini_client.is_configured():
        result = gemini_theme(text)
        if result:
            return result
    return rule_based_theme(text)
