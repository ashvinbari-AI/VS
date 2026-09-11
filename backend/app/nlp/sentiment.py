"""
sentiment.py -- spec section 33.

Three tiers, tried in order, each one labeled distinctly in the API/UI so
none is ever presented as equivalent to another (spec section 23/45):

  1. Gemini (gemini_sentiment)      -- only if enabled and configured.
  2. Local transformer (local_sentiment) -- only if SENTIMENT_MODEL /
     MARATHI_SENTIMENT_MODEL is set (see .env.example); fully offline.
  3. rule_based_sentiment            -- the always-available fallback: a
     lightweight bilingual (English + common Marathi/Hindi, since that's
     what this project's actual scraped captions/comments are in) lexicon
     + emoji scorer. Labeled "Local rule-based" (rule_based_v1).
"""

from __future__ import annotations

from app.config import get_settings
from app.nlp import gemini_client, local_sentiment
from app.nlp.categories import SENTIMENT_LABELS

_POSITIVE_WORDS = {
    "good", "great", "excellent", "congratulations", "congrats", "proud",
    "love", "support", "thank", "thanks", "happy", "blessed", "victory",
    "welcome", "well done", "awesome", "wonderful", "best", "जय", "अभिनंदन",
    "धन्यवाद", "शुभेच्छा", "स्वागत", "उत्तम", "छान", "आवडले", "प्रेम", "सुंदर",
    "मस्त", "जय हिंद", "जय महाराष्ट्र",
}
_NEGATIVE_WORDS = {
    "bad", "shame", "corrupt", "corruption", "fail", "failure", "useless",
    "worst", "angry", "hate", "protest", "scam", "lie", "cheat", "fraud",
    "लाज", "भ्रष्ट", "अपयश", "निषेध", "खोटे", "समस्या", "संताप", "राग", "चोर",
    "नालायक", "बेकार",
}
_POSITIVE_EMOJI = set("🙏🌹❤️👏💗🔥🌷😊👍💐🎉😍🥰💪🇮🇳")
_NEGATIVE_EMOJI = set("😡😠👎💔😢😭")


def rule_based_sentiment(text: str | None) -> dict | None:
    if not text or not text.strip():
        return None
    lowered = text.lower()
    pos = sum(1 for w in _POSITIVE_WORDS if w in lowered)
    neg = sum(1 for w in _NEGATIVE_WORDS if w in lowered)
    pos += sum(1 for ch in text if ch in _POSITIVE_EMOJI)
    neg += sum(1 for ch in text if ch in _NEGATIVE_EMOJI)

    if pos == 0 and neg == 0:
        label = "Neutral"
    elif pos > 0 and neg > 0:
        label = "Mixed/Unclear"
    elif pos > neg:
        label = "Positive"
    else:
        label = "Negative"

    total = max(pos + neg, 1)
    confidence = round(min(0.95, 0.4 + abs(pos - neg) / total * 0.5), 2)
    return {"sentiment": label, "confidence": confidence, "model": "rule_based_v1"}


def gemini_sentiment(text: str) -> dict | None:
    prompt = (
        "Classify the sentiment of this social media text as exactly one of: "
        f"{', '.join(SENTIMENT_LABELS)}. Text may be in English, Hindi, or Marathi. "
        'Respond with ONLY JSON: {"sentiment": "<label>", "confidence": <0-1 float>}.\n\n'
        f"Text: {text[:2000]}"
    )
    result = gemini_client.generate_json(prompt)
    if not result or "sentiment" not in result:
        return None
    label = result["sentiment"]
    if label not in SENTIMENT_LABELS:
        return None
    return {
        "sentiment": label,
        "confidence": float(result.get("confidence", 0.7)),
        "model": f"gemini:{get_settings().gemini_model}",
    }


def classify_sentiment(text: str | None, use_gemini: bool) -> dict | None:
    if not text or not text.strip():
        return None
    if use_gemini and gemini_client.is_configured():
        result = gemini_sentiment(text)
        if result:
            return result
    if local_sentiment.is_configured():
        result = local_sentiment.classify(text)
        if result:
            return result
    return rule_based_sentiment(text)
