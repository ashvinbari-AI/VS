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


def filter_comments_by_post(
    comments: pd.DataFrame,
    content: pd.DataFrame,
    *,
    platform: str | None = None,
    content_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    """Comments have no reliable `commented_at` of their own -- every comment
    in this project's actual scraped data has it null (Instagram/Facebook
    don't expose a comment timestamp the scrapers can capture) -- so
    content_type/date filters can't be applied to a comment directly.
    Instead they're applied to the post the comment is *on* (left-joined via
    content_id): "comments on posts published in the selected window", the
    only date signal actually available. A comment whose post isn't in
    `content` (or there are no posts at all) gets NaN/NaT for the joined
    fields, which correctly excludes it from a content_type/date filter
    rather than guessing it belongs in every window.

    platform filters directly on the comment's own `platform` column (that
    one *is* reliable -- comments carry it themselves, no join needed)."""
    if comments.empty:
        return comments
    out = comments
    if platform and platform.lower() != "all" and "platform" in out.columns:
        out = out[out["platform"] == platform.lower()]

    needs_post_join = (content_type and content_type.lower() != "all") or date_from or date_to
    if needs_post_join and not content.empty and "content_id" in content.columns:
        lookup = content[["content_id", "published_at", "content_type"]].drop_duplicates("content_id")
        out = out.merge(lookup, on="content_id", how="left")
    elif needs_post_join:
        # No posts to join against at all -- every comment fails a
        # content_type/date filter (no parent post to check it against),
        # same as a real join finding no match.
        return out.iloc[0:0]

    if content_type and content_type.lower() != "all" and "content_type" in out.columns:
        out = out[out["content_type"] == content_type.lower()]
    if (date_from or date_to) and "published_at" in out.columns:
        published = pd.to_datetime(out["published_at"], errors="coerce", utc=True)
        if date_from:
            out = out[published >= pd.Timestamp(date_from, tz="UTC")]
            published = published[out.index]
        if date_to:
            out = out[published <= pd.Timestamp(date_to, tz="UTC")]
    return out
