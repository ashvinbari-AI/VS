"""narrative.py -- spec sections 20/33. Classifies a post caption into one of
DEFAULT_NARRATIVES (or a user-added custom category). Rule-based fallback is
bilingual keyword matching; Gemini path (when enabled) is preferred."""

from __future__ import annotations

from app.nlp import gemini_client
from app.nlp.categories import DEFAULT_NARRATIVES

_KEYWORDS: dict[str, list[str]] = {
    "Farmers": ["शेतकरी", "शेती", "कृषी", "farmer", "agricultur"],
    "Infrastructure": ["रस्ता", "रस्ते", "पूल", "महामार्ग", "road", "bridge", "highway", "infrastructure"],
    "Healthcare": ["आरोग्य", "रुग्णालय", "health", "hospital", "medical"],
    "Education": ["शिक्षण", "शाळा", "विद्यालय", "education", "school", "university"],
    "Government & Governance": ["सरकार", "शासन", "मंत्रिमंडळ", "मंत्रालय", "government", "cabinet", "policy"],
    "Election": ["निवडणूक", "मतदान", "election", "vote", "campaign"],
    "Party Organization": ["भाजप", "पक्ष", "संघटना", "party", "bjp", "shiv sena", "shivsena"],
    "Political Opposition": ["विरोधी", "विरोधक", "टीका", "opposition", "criticis"],
    "Tribute/Condolence": ["श्रद्धांजली", "निधन", "स्मृती", "tribute", "condolence", "demise"],
    "Public Events": ["उद्घाटन", "कार्यक्रम", "समारंभ", "शुभारंभ", "inaugurat", "event", "ceremony"],
    "Women": ["महिला", "स्त्री", "women", "woman"],
    "Youth": ["युवा", "तरुण", "youth"],
    "Employment": ["रोजगार", "नोकरी", "employment", "job"],
    "Law & Order": ["कायदा", "पोलीस", "सुव्यवस्था", "police", "law and order"],
    "Economy": ["अर्थव्यवस्था", "आर्थिक", "गुंतवणूक", "economy", "economic", "investment"],
    "Development": ["विकास", "development", "प्रकल्प", "project"],
    "Culture": ["संस्कृती", "सण", "उत्सव", "परंपरा", "मंदिर", "बैलपोळा", "culture", "festival", "tradition", "temple"],
    "Public Welfare": ["कल्याण", "योजना", "welfare", "scheme"],
    "National Issues": ["राष्ट्रीय", "देश", "national", "india"],
    "State Issues": ["राज्य", "महाराष्ट्र", "state", "maharashtra"],
    "Local Issues": ["स्थानिक", "गाव", "शहर", "local", "ward", "constituency"],
    "Personal": ["वाढदिवस", "जन्मदिन", "birthday", "family"],
}


def rule_based_narrative(text: str | None) -> dict | None:
    if not text or not text.strip():
        return None
    lowered = text.lower()
    scores: dict[str, int] = {}
    for category, kws in _KEYWORDS.items():
        hits = sum(1 for kw in kws if kw.lower() in lowered or kw in text)
        if hits:
            scores[category] = hits
    if not scores:
        return {"narrative": "Other", "confidence": 0.3, "model": "rule_based_v1"}
    best = max(scores, key=scores.get)
    confidence = round(min(0.9, 0.5 + 0.1 * scores[best]), 2)
    return {"narrative": best, "confidence": confidence, "model": "rule_based_v1"}


def gemini_narrative(text: str, categories: list[str]) -> dict | None:
    prompt = (
        "Classify this political social-media post caption into exactly one of these "
        f"categories: {', '.join(categories)}. Text may be English, Hindi, or Marathi. "
        'Respond with ONLY JSON: {"narrative": "<category>", "confidence": <0-1 float>}.\n\n'
        f"Caption: {text[:2000]}"
    )
    result = gemini_client.generate_json(prompt)
    if not result or result.get("narrative") not in categories:
        return None
    from app.config import get_settings
    return {
        "narrative": result["narrative"],
        "confidence": float(result.get("confidence", 0.7)),
        "model": f"gemini:{get_settings().gemini_model}",
    }


def classify_narrative(text: str | None, use_gemini: bool,
                        categories: list[str] | None = None) -> dict | None:
    if not text or not text.strip():
        return None
    categories = categories or DEFAULT_NARRATIVES
    if use_gemini and gemini_client.is_configured():
        result = gemini_narrative(text, categories)
        if result:
            return result
    return rule_based_narrative(text)
