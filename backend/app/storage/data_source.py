"""
Single switch between DEMO MODE (data/mock/*.parquet, synthetic) and real
local data (data/processed/*.parquet, from your actual scrapes). Every
router reads through here so demo and real data can never mix (spec
sections 45/54).
"""

from __future__ import annotations

import pandas as pd

from app.config import get_settings
from app.storage import json_store
from app.storage.parquet_store import read_comments, read_content, read_profiles


def is_demo_mode() -> bool:
    return bool(json_store.load_runtime_settings().get("demo_mode", False))


def set_demo_mode(enabled: bool) -> None:
    json_store.save_runtime_settings({"demo_mode": enabled})


def get_content_df() -> pd.DataFrame:
    settings = get_settings()
    path = (settings.mock_dir / "content.parquet") if is_demo_mode() else None
    return read_content(path)


def get_comments_df() -> pd.DataFrame:
    settings = get_settings()
    path = (settings.mock_dir / "comments.parquet") if is_demo_mode() else None
    return read_comments(path)


def get_profiles_df() -> pd.DataFrame:
    settings = get_settings()
    path = (settings.mock_dir / "profiles.parquet") if is_demo_mode() else None
    return read_profiles(path)


def latest_followers(profiles_df: pd.DataFrame, person_id: str, platform: str | None = None) -> int | None:
    if profiles_df.empty:
        return None
    df = profiles_df[profiles_df["person_id"] == person_id]
    if platform:
        df = df[df["platform"] == platform]
    df = df.dropna(subset=["followers"])
    if df.empty:
        return None
    df = df.sort_values("finished_at")
    return int(df.iloc[-1]["followers"])
