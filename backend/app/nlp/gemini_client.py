"""
Thin, defensive wrapper around google-generativeai.

Used ONLY for narrative classification / sentiment / comment themes / issue
extraction (spec section 33) -- never for core metrics. Every call is
wrapped so that a missing package, missing key, rate limit, or network
failure degrades to "Gemini unavailable" rather than crashing the request;
callers must fall back to the rule-based engine on None.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import get_settings
from app.logging_setup import get_logger

_model_cache: dict[str, Any] = {}


def is_configured() -> bool:
    return bool(get_settings().gemini_api_key)


def _get_model():
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    key = settings.gemini_model
    if key in _model_cache:
        return _model_cache[key]
    try:
        import google.generativeai as genai
    except ImportError:
        return None
    try:
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        _model_cache[key] = model
        return model
    except Exception:
        return None


def _extract_json(text: str) -> Any | None:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def generate_json(prompt: str) -> Any | None:
    """Send one prompt, expect JSON back. Returns None on any failure --
    logged, never raised, so the caller can silently fall back."""
    settings = get_settings()
    logger = get_logger("analysis", settings.logs_dir)
    model = _get_model()
    if model is None:
        return None
    try:
        response = model.generate_content(prompt)
        text = getattr(response, "text", None)
        if not text:
            return None
        return _extract_json(text)
    except Exception as e:  # rate limit, network, safety block, etc.
        logger.warning("Gemini call failed (%s) -- falling back to local analysis", type(e).__name__)
        return None
