"""The processed Parquet layer (spec section 47).

RAW JSON -> NORMALIZATION -> PARQUET -> ANALYTICS -> API -> REACT

FastAPI never re-parses raw JSONL on a request; every analytics/API call
reads these three Parquet files instead. They're small enough (thousands to
low hundreds-of-thousands of rows) to load whole with pandas -- no chunking
needed at this scale.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from app.models.content import NormalizedComment, NormalizedContent, ProfileSnapshot
from app.storage.paths import comments_parquet_path, content_parquet_path, profiles_parquet_path


def _to_df(rows: list, list_cols: tuple[str, ...] = ()) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    data = [r.model_dump() for r in rows]
    df = pd.DataFrame(data)
    for col in list_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda v: v if isinstance(v, list) else [])
    return df


def write_content(items: list[NormalizedContent], path: Path | None = None) -> Path:
    path = path or content_parquet_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    df = _to_df(items, list_cols=("hashtags", "mentions", "media_urls"))
    if df.empty:
        # Still write an empty-but-schema'd file so downstream reads don't crash.
        df = pd.DataFrame(columns=list(NormalizedContent.model_fields.keys()))
    df.to_parquet(path, index=False)
    return path


def write_comments(items: list[NormalizedComment], path: Path | None = None) -> Path:
    path = path or comments_parquet_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    df = _to_df(items, list_cols=("issues",))
    if df.empty:
        df = pd.DataFrame(columns=list(NormalizedComment.model_fields.keys()))
    df.to_parquet(path, index=False)
    return path


def write_profiles(items: list[ProfileSnapshot], path: Path | None = None) -> Path:
    path = path or profiles_parquet_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    df = _to_df(items, list_cols=("errors",))
    if df.empty:
        df = pd.DataFrame(columns=list(ProfileSnapshot.model_fields.keys()))
    df.to_parquet(path, index=False)
    return path


def _delistify(df: pd.DataFrame, list_cols: tuple[str, ...]) -> pd.DataFrame:
    """pyarrow round-trips list<> columns back as numpy.ndarray, which the
    JSON encoder can't serialize and which behaves subtly differently from a
    real list (e.g. truthiness). Convert back to plain Python lists/None."""
    for col in list_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: list(v) if isinstance(v, np.ndarray) else (v if isinstance(v, list) else v))
    return df


def read_content(path: Path | None = None) -> pd.DataFrame:
    path = path or content_parquet_path()
    if not path.exists():
        return pd.DataFrame(columns=list(NormalizedContent.model_fields.keys()))
    return _delistify(pd.read_parquet(path), ("hashtags", "mentions", "media_urls"))


def read_comments(path: Path | None = None) -> pd.DataFrame:
    path = path or comments_parquet_path()
    if not path.exists():
        return pd.DataFrame(columns=list(NormalizedComment.model_fields.keys()))
    return _delistify(pd.read_parquet(path), ("issues",))


def read_profiles(path: Path | None = None) -> pd.DataFrame:
    path = path or profiles_parquet_path()
    if not path.exists():
        return pd.DataFrame(columns=list(ProfileSnapshot.model_fields.keys()))
    return _delistify(pd.read_parquet(path), ("errors",))
