"""Default taxonomies (spec sections 20/24/26). Custom narrative categories
can be appended at runtime via /api/settings; these are just the seed list."""

from __future__ import annotations

DEFAULT_NARRATIVES: list[str] = [
    "Government & Governance", "Development", "Infrastructure", "Education",
    "Healthcare", "Employment", "Youth", "Farmers", "Women", "Law & Order",
    "Economy", "Public Welfare", "Party Organization", "Political Opposition",
    "Election", "Public Events", "National Issues", "State Issues",
    "Local Issues", "Culture", "Tribute/Condolence", "Personal", "Other",
]

SENTIMENT_LABELS = ["Positive", "Neutral", "Negative", "Mixed/Unclear"]

COMMENT_THEMES = [
    "Support", "Criticism", "Question", "Complaint", "Praise", "Suggestion",
    "Request", "Political attack", "Policy discussion", "Other",
]

PUBLIC_ISSUES = [
    "Roads", "Water", "Traffic", "Electricity", "Employment", "Education",
    "Healthcare", "Housing", "Transport", "Farmers", "Price rise",
    "Local infrastructure", "Government services",
]
