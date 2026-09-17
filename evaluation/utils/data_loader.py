"""Loads the production system's actual data -- never a copy, never a
re-derived version -- for the evaluators to compare against ground truth.

Content/comments/profiles come from backend's own data_source module (the
same switch the API and React app read through), so evaluation always sees
exactly what the app would show, including the demo/real-data guard.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from evaluation.utils.backend_bridge import BACKEND_DIR, load_production_modules


def load_production_dataframes() -> dict[str, pd.DataFrame]:
    """content/comments/profiles, exactly as the running app would read
    them (demo mode or real data, whichever data_source.is_demo_mode()
    currently reports)."""
    mods = load_production_modules()
    ds = mods["data_source"]
    return {
        "content": ds.get_content_df(),
        "comments": ds.get_comments_df(),
        "profiles": ds.get_profiles_df(),
    }


def load_nlp_cache() -> dict[str, dict]:
    """The production NLP cache (data/analysis/nlp_cache.json), keyed by
    content_id for posts and "comment:<comment_id>" for comments -- see
    app/nlp/engine.py. Evaluating NLP against this cache (rather than
    re-running the classifier) is deliberate: spec section 57 requires NLP
    evaluation to work even when Gemini is unreachable, using whatever was
    already cached from a real analysis run."""
    from app.nlp import cache as nlp_cache
    return nlp_cache.load_cache()


def index_by(records: list[dict], key: str) -> dict[Any, dict]:
    """Ground-truth records keyed by their id field, skipping any record
    that's missing the key entirely (malformed ground truth is reported,
    never silently included as a false match)."""
    return {r[key]: r for r in records if key in r and r[key] is not None}


def rows_to_dicts(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    return df.where(pd.notnull(df), None).to_dict(orient="records")
