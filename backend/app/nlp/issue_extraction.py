"""issue_extraction.py -- spec section 24/26.

Detects mentions of PUBLIC_ISSUES in comment/post text. Never infers a
commenter's location from username/language/opinion (spec section 25) --
this module only reports issue *topics*, and only from explicit text.
"""

from __future__ import annotations


_KEYWORDS: dict[str, list[str]] = {
    "Roads": ["रस्ता", "रस्ते", "road", "pothole", "खड्डे"],
    "Water": ["पाणी", "जलवाहिनी", "water", "drought", "दुष्काळ"],
    "Traffic": ["वाहतूक कोंडी", "ट्रॅफिक", "traffic jam", "traffic"],
    "Electricity": ["वीज", "लाईट", "electricity", "power cut", "भारनियमन"],
    "Employment": ["रोजगार", "बेरोजगार", "नोकरी", "employment", "unemploy", "job"],
    "Education": ["शिक्षण", "शाळा", "education", "school"],
    "Healthcare": ["आरोग्य", "रुग्णालय", "healthcare", "hospital", "medicine"],
    "Housing": ["घरकुल", "घर", "housing", "awas"],
    "Transport": ["बस", "वाहतूक", "transport", "railway", "रेल्वे"],
    "Farmers": ["शेतकरी", "शेती", "farmer", "crop", "पीक"],
    "Price rise": ["महागाई", "भाववाढ", "inflation", "price rise"],
    "Local infrastructure": ["गटार", "पूल", "नाला", "infrastructure", "drainage"],
    "Government services": ["सरकारी सेवा", "government service", "सेतू", "e-governance"],
}


def rule_based_issues(text: str | None) -> dict | None:
    if not text or not text.strip():
        return None
    lowered = text.lower()
    found = [issue for issue, kws in _KEYWORDS.items()
             if any(kw.lower() in lowered or kw in text for kw in kws)]
    return {"issues": found, "model": "rule_based_v1"}


def classify_issues(text: str | None) -> dict | None:
    return rule_based_issues(text)
