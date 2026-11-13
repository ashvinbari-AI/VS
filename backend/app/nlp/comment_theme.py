"""comment_theme.py -- spec section 24. Classifies a comment into one theme
using local bilingual (English + Marathi) keyword lists."""

from __future__ import annotations

_QUESTION_MARKERS = ["?", "का ", "कसे", "केव्हा", "कुठे", "कोण", "कधी"]
_REQUEST_MARKERS = ["please", "कृपया", "पाहिजे", "need", "request", "मागणी"]
_POLICY_MARKERS = ["योजना", "धोरण", "policy", "scheme", "budget", "अर्थसंकल्प"]
_ATTACK_MARKERS = ["भ्रष्ट", "चोर", "नालायक", "शरम", "corrupt", "traitor", "गद्दार"]

# Praise/Support vs. Criticism cues.
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


def classify_theme(text: str | None) -> dict | None:
    return rule_based_theme(text)
