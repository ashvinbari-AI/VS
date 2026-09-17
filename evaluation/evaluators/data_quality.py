"""
DATA QUALITY (spec section 9) -- structural/sanity checks on the
production data itself, independent of any ground truth.

Score methodology (documented per spec's explicit "do not create an
arbitrary score" requirement):

    data_quality_pct = 100 * valid_records / total_records

A record is "invalid" if it fails ANY one of the checks below (duplicate
content_id, missing content_id, negative likes/comments/shares, an
unparseable published_at, or a malformed content_url). This is a record-
level score, not a field-level one -- one bad field fails the whole
record, the same way a single broken column would make you distrust the
whole row. Raw per-check counts are always shown alongside the score so
nothing is hidden behind one number (spec explicitly requires this).
"""

from __future__ import annotations

import re

import pandas as pd

from evaluation.metrics.classification import safe_divide

_URL_RE = re.compile(r"^https?://[^\s]+$")


def _invalid_dates(df: pd.DataFrame) -> pd.Series:
    if "published_at" not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    present = df["published_at"].notna()
    parsed = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
    return present & parsed.isna()


def _invalid_urls(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    present = df[column].notna()
    valid = df[column].astype(str).str.match(_URL_RE)
    return present & ~valid


def _negative(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    numeric = pd.to_numeric(df[column], errors="coerce")
    return numeric < 0


def evaluate_content_quality(df: pd.DataFrame) -> dict:
    total = len(df)
    if total == 0:
        return {"total_records": 0, "valid_records": 0, "invalid_records": 0,
                "data_quality_pct": None, "checks": {}}

    missing_id = df["content_id"].isna() if "content_id" in df.columns else pd.Series([True] * total)
    dup_id = (df["content_id"].duplicated(keep="first")
              if "content_id" in df.columns else pd.Series([False] * total))
    invalid_date = _invalid_dates(df)
    invalid_url = _invalid_urls(df, "content_url")
    negative_likes = _negative(df, "likes")
    negative_comments = _negative(df, "comments_count")
    negative_shares = _negative(df, "shares")

    any_invalid = (missing_id | dup_id | invalid_date | invalid_url
                   | negative_likes | negative_comments | negative_shares)
    invalid_count = int(any_invalid.sum())
    valid_count = total - invalid_count

    checks = {
        "missing_content_id": int(missing_id.sum()),
        "duplicate_content_id": int(dup_id.sum()),
        "invalid_published_at": int(invalid_date.sum()),
        "invalid_content_url": int(invalid_url.sum()),
        "negative_likes": int(negative_likes.sum()),
        "negative_comments": int(negative_comments.sum()),
        "negative_shares": int(negative_shares.sum()),
    }

    return {
        "total_records": total, "valid_records": valid_count, "invalid_records": invalid_count,
        "data_quality_pct": round(safe_divide(valid_count, total) * 100, 2),
        "checks": checks,
        "methodology": ("data_quality_pct = 100 * valid_records / total_records; a record is "
                         "invalid if it fails ANY check listed in `checks` -- see this module's "
                         "docstring."),
    }


def evaluate_comments_quality(df: pd.DataFrame) -> dict:
    total = len(df)
    if total == 0:
        return {"total_records": 0, "valid_records": 0, "invalid_records": 0,
                "data_quality_pct": None, "checks": {}}

    missing_id = df["comment_id"].isna() if "comment_id" in df.columns else pd.Series([True] * total)
    dup_id = (df["comment_id"].duplicated(keep="first")
              if "comment_id" in df.columns else pd.Series([False] * total))
    negative_likes = _negative(df, "like_count")

    any_invalid = missing_id | dup_id | negative_likes
    invalid_count = int(any_invalid.sum())
    valid_count = total - invalid_count

    checks = {
        "missing_comment_id": int(missing_id.sum()),
        "duplicate_comment_id": int(dup_id.sum()),
        "negative_like_count": int(negative_likes.sum()),
    }
    return {
        "total_records": total, "valid_records": valid_count, "invalid_records": invalid_count,
        "data_quality_pct": round(safe_divide(valid_count, total) * 100, 2),
        "checks": checks,
    }
