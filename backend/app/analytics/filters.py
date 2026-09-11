"""Shared filter application for the content/comments DataFrames -- every
page-level endpoint runs its query through here so "respect global filters"
(spec section 69) is enforced in one place instead of per-route."""

from __future__ import annotations

from typing import Iterable

import pandas as pd


def filter_content(
    df: pd.DataFrame,
    *,
    person_ids: Iterable[str] | None = None,
    platform: str | None = None,
    content_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    narrative: str | None = None,
    sentiment: str | None = None,
    min_likes: int | None = None,
    min_comments: int | None = None,
    min_engagement: float | None = None,
    search: str | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df
    out = df
    if person_ids:
        out = out[out["person_id"].isin(list(person_ids))]
    if platform and platform.lower() != "all":
        out = out[out["platform"] == platform.lower()]
    if content_type and content_type.lower() != "all":
        out = out[out["content_type"] == content_type.lower()]
    if date_from:
        out = out[pd.to_datetime(out["published_at"], errors="coerce", utc=True)
                  >= pd.Timestamp(date_from, tz="UTC")]
    if date_to:
        out = out[pd.to_datetime(out["published_at"], errors="coerce", utc=True)
                  <= pd.Timestamp(date_to, tz="UTC")]
    if narrative and "narrative" in out.columns:
        out = out[out["narrative"] == narrative]
    if sentiment and "sentiment" in out.columns:
        out = out[out["sentiment"] == sentiment]
    if min_likes is not None:
        out = out[out["likes"].fillna(0) >= min_likes]
    if min_comments is not None:
        out = out[out["comments_count"].fillna(0) >= min_comments]
    if min_engagement is not None and "engagement" in out.columns:
        out = out[out["engagement"].fillna(0) >= min_engagement]
    if search:
        needle = search.lower()
        hay = out["caption"].fillna("").str.lower()
        out = out[hay.str.contains(needle, regex=False)]
    return out
