"""
Central settings for the Competitor Analysis backend.

Everything here is local-only: paths point inside the project tree and the
backend makes no outbound network calls of its own.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = parent of backend/
ROOT_DIR = Path(__file__).resolve().parents[2]


def _blank_means_default(default: Path):
    """A validator factory: an env var present but left blank (as
    .env.example documents, e.g. `DATA_DIR=`) must fall back to `default`,
    not be taken literally as Path("") -> ".". Real bug this fixes: a blank
    DATA_DIR= silently repointed the whole app at backend/'s cwd, making
    every saved person/scrape disappear from a fresh process without any
    error -- pydantic-settings treats a present-but-empty env var as an
    explicit value, not as "unset"."""

    def _validator(cls, v):  # noqa: ANN001 -- pydantic validator signature
        if v in (None, "", Path("")):
            return default
        return v

    return _validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Data locations --
    data_dir: Path = ROOT_DIR / "data"

    # Where the existing scrapers live. python_executable is an explicit
    # override (set PYTHON_EXECUTABLE in .env) -- leave unset to auto-detect
    # whichever interpreter actually has selenium/playwright installed (see
    # scrapers/interpreter.py). A bare "python" is NOT a safe default: on a
    # machine with multiple Python installs, the one a subprocess's PATH
    # resolves to may have neither package even when another one does.
    scraper_dir: Path = ROOT_DIR
    python_executable: str | None = None

    _default_data_dir = field_validator("data_dir", mode="before")(_blank_means_default(ROOT_DIR / "data"))
    _default_scraper_dir = field_validator("scraper_dir", mode="before")(_blank_means_default(ROOT_DIR))

    # -- Behaviour defaults (overridable at runtime via /api/settings) --
    default_period_days: int = 30
    display_timezone: str = "Asia/Kolkata"
    frontend_origin: str = "http://127.0.0.1:5173"
    nlp_batch_size: int = 20

    # -- Deployment --
    # ACCESS_TOKEN set => every page/API call needs it (see app/security.py).
    # Blank/unset => no gate (local dev).
    access_token: str | None = None
    # Built React app (frontend `npm run build`). Served by FastAPI when the
    # folder exists, so the whole platform runs on a single port.
    frontend_dist: Path = ROOT_DIR / "frontend" / "dist"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def analysis_dir(self) -> Path:
        return self.data_dir / "analysis"

    @property
    def mock_dir(self) -> Path:
        return self.data_dir / "mock"

    @property
    def configs_dir(self) -> Path:
        return self.data_dir / "configs"

    @property
    def logs_dir(self) -> Path:
        return ROOT_DIR / "logs"

    @property
    def nlp_cache_path(self) -> Path:
        return self.analysis_dir / "nlp_cache.json"

    @property
    def runtime_settings_path(self) -> Path:
        return self.configs_dir / "settings.json"

    def ensure_dirs(self) -> None:
        for d in (
            self.raw_dir, self.processed_dir, self.analysis_dir,
            self.analysis_dir / "comparison", self.mock_dir, self.configs_dir,
            self.logs_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
