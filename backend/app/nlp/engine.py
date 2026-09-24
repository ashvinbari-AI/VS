"""
Orchestrates NLP analysis over content + comments with the on-disk cache
(spec sections 33/34). This is the only module that decides "do we call
Gemini or run rule-based" -- callers (routers) just ask for analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.nlp import cache as nlp_cache
from app.nlp import comment_theme, gemini_client, issue_extraction, narrative, sentiment
from app.storage import json_store


def nlp_status() -> dict[str, Any]:
    settings = json_store.load_runtime_settings()
    gemini_ready = gemini_client.is_configured()
    enabled = bool(settings.get("nlp_enabled")) and gemini_ready
    return {
        "nlp_enabled_setting": bool(settings.get("nlp_enabled")),
        "gemini_configured": gemini_ready,
        # Gemini only ever powers Comment Sentiment (see analyze_content_df /
        # analyze_comments_df) -- the label says so rather than implying
        # narrative/post-sentiment/theme/issues are Gemini-backed too.
        "effective_mode": "GEMINI NLP ENABLED (Comment Sentiment)" if enabled else "LOCAL ANALYSIS MODE",
        "use_gemini": enabled,
    }


def analyze_content_df(df: pd.DataFrame, force: bool = False) -> pd.DataFrame:
    """Adds narrative/sentiment columns to a content DataFrame, using the
    cache keyed by content_id and only calling the classifiers for rows not
    already cached (unless force=True)."""
    if df.empty:
        df = df.copy()
        df["narrative"] = pd.Series(dtype="object")
        df["narrative_confidence"] = pd.Series(dtype="float64")
        df["sentiment"] = pd.Series(dtype="object")
        df["sentiment_confidence"] = pd.Series(dtype="float64")
        df["nlp_model"] = pd.Series(dtype="object")
        return df

    # Gemini is scoped to Comment Sentiment only (see analyze_comments_df) --
    # post narrative and post ("Comment Sentiment" vs "Post Sentiment" in the
    # UI/report, spec section 45) sentiment always stay on the local
    # transformer/rule-based tiers, regardless of the Gemini toggle, so a
    # user enabling Gemini for comments doesn't unexpectedly burn quota on
    # every post too.
    cache = nlp_cache.load_cache()
    new_entries: dict[str, dict] = {}

    narratives, narrative_conf, sentiments, sentiment_conf, models = [], [], [], [], []
    for _, row in df.iterrows():
        cid = row["content_id"]
        cached = cache.get(cid) if not force else None
        if cached:
            narratives.append(cached.get("narrative"))
            narrative_conf.append(cached.get("narrative_confidence"))
            sentiments.append(cached.get("sentiment"))
            sentiment_conf.append(cached.get("sentiment_confidence"))
            models.append(cached.get("model"))
            continue

        caption = row.get("caption")
        n_result = narrative.classify_narrative(caption, use_gemini=False)
        s_result = sentiment.classify_sentiment(caption, use_gemini=False)

        entry = {
            "content_id": cid,
            "narrative": n_result["narrative"] if n_result else None,
            "narrative_confidence": n_result["confidence"] if n_result else None,
            "sentiment": s_result["sentiment"] if s_result else None,
            "sentiment_confidence": s_result["confidence"] if s_result else None,
            "model": (n_result or s_result or {}).get("model"),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        new_entries[cid] = entry
        narratives.append(entry["narrative"])
        narrative_conf.append(entry["narrative_confidence"])
        sentiments.append(entry["sentiment"])
        sentiment_conf.append(entry["sentiment_confidence"])
        models.append(entry["model"])

    if new_entries:
        nlp_cache.put_many(new_entries)

    out = df.copy()
    out["narrative"] = narratives
    out["narrative_confidence"] = narrative_conf
    out["sentiment"] = sentiments
    out["sentiment_confidence"] = sentiment_conf
    out["nlp_model"] = models
    return out


def analyze_comments_df(df: pd.DataFrame, force: bool = False) -> pd.DataFrame:
    if df.empty:
        df = df.copy()
        df["sentiment"] = pd.Series(dtype="object")
        df["theme"] = pd.Series(dtype="object")
        df["issues"] = pd.Series(dtype="object")
        return df

    status = nlp_status()
    use_gemini = status["use_gemini"]
    cache = nlp_cache.load_cache()
    new_entries: dict[str, dict] = {}

    sentiments, themes, issues_list = [], [], []
    for _, row in df.iterrows():
        cid = "comment:" + row["comment_id"]
        cached = cache.get(cid) if not force else None
        if cached:
            sentiments.append(cached.get("sentiment"))
            themes.append(cached.get("theme"))
            issues_list.append(cached.get("issues") or [])
            continue

        text = row.get("comment_text")
        # Comment Sentiment is the one and only analysis Gemini is allowed
        # to run (see note in analyze_content_df) -- theme/issue extraction
        # for comments stay rule-based even with Gemini enabled.
        s_result = sentiment.classify_sentiment(text, use_gemini)
        t_result = comment_theme.classify_theme(text, use_gemini=False)
        i_result = issue_extraction.classify_issues(text, use_gemini=False)

        entry = {
            "content_id": cid,
            "sentiment": s_result["sentiment"] if s_result else None,
            "theme": t_result["theme"] if t_result else None,
            "issues": i_result["issues"] if i_result else [],
            "model": (s_result or t_result or i_result or {}).get("model"),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        new_entries[cid] = entry
        sentiments.append(entry["sentiment"])
        themes.append(entry["theme"])
        issues_list.append(entry["issues"])

    if new_entries:
        nlp_cache.put_many(new_entries)

    out = df.copy()
    out["sentiment"] = sentiments
    out["theme"] = themes
    out["issues"] = issues_list
    return out
