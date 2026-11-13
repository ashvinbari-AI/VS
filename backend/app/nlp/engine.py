"""
Orchestrates comment analysis (theme + issue extraction) with the on-disk
cache (spec sections 33/34). Everything here is local, keyword-based and
deterministic -- no model, no network call.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from app.nlp import cache as nlp_cache
from app.nlp import comment_theme, issue_extraction

NLP_MODE = "LOCAL ANALYSIS MODE"


def analyze_comments_df(df: pd.DataFrame, force: bool = False) -> pd.DataFrame:
    if df.empty:
        df = df.copy()
        df["theme"] = pd.Series(dtype="object")
        df["issues"] = pd.Series(dtype="object")
        return df

    cache = nlp_cache.load_cache()
    new_entries: dict[str, dict] = {}

    themes, issues_list = [], []
    texts = df["comment_text"] if "comment_text" in df else [None] * len(df)
    for comment_id, text in zip(df["comment_id"], texts):
        cid = "comment:" + comment_id
        cached = cache.get(cid) if not force else None
        if cached:
            themes.append(cached.get("theme"))
            issues_list.append(cached.get("issues") or [])
            continue

        t_result = comment_theme.classify_theme(text)
        i_result = issue_extraction.classify_issues(text)

        entry = {
            "content_id": cid,
            "theme": t_result["theme"] if t_result else None,
            "issues": i_result["issues"] if i_result else [],
            "model": (t_result or i_result or {}).get("model"),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        new_entries[cid] = entry
        themes.append(entry["theme"])
        issues_list.append(entry["issues"])

    if new_entries:
        nlp_cache.put_many(new_entries)

    out = df.copy()
    out["theme"] = themes
    out["issues"] = issues_list
    return out
