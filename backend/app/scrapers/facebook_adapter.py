"""Subprocess wrapper around the existing, untouched fb_scraper.py.

fb_scraper.py CLI (confirmed by inspection, not assumed):
    python fb_scraper.py login [--chrome-path]
    python fb_scraper.py scrape --url URL [--profile-key KEY]
        [--days N | --since --until] [--workers N] [--limit N] [--out DIR]
        [--headed] [--no-comments] [--max-comments N] [--no-reactions]
        [--skip-known] [--chrome-path]

Session lives at fb_session/ (a full Playwright/Chrome profile dir) -- created
by `fb_scraper.py login`. Comment depth is limited in headless mode per the
scraper's own warning ("Headless caps at ~20 comments/post"), so this adapter
defaults --headed on for content collection unless the caller says otherwise.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.config import get_settings
from app.logging_setup import get_logger
from app.scrapers.base import ProgressCallback, ScrapeResult, build_window_args, run_subprocess
from app.scrapers.interpreter import find_interpreter_with

_URL_RE = re.compile(r"^https?://(www\.)?facebook\.com/[^/?#]+/?", re.I)
_REQUIRED_MODULES = ("playwright",)
_MISSING_INTERPRETER_MSG = (
    "No Python interpreter with playwright was found on this machine (checked `py -0p` "
    "and common install paths). Install it (`pip install playwright && playwright install`) "
    "for the interpreter you use to run fb_scraper.py, or set PYTHON_EXECUTABLE in .env to "
    "that interpreter's full path."
)


class FacebookAdapter:
    platform = "facebook"

    def __init__(self) -> None:
        s = get_settings()
        self.script = s.scraper_dir / "fb_scraper.py"
        self.session_dir = s.scraper_dir / "fb_session"
        self.logger = get_logger("scraper", s.logs_dir)

    def validate_profile(self, url: str) -> tuple[bool, str | None]:
        if not url:
            return False, "Facebook URL is empty"
        if not _URL_RE.match(url.strip()):
            return False, "Not a recognizable facebook.com page/profile URL"
        return True, None

    def _base_cmd(self, url: str, out_dir: Path, chrome_path: str | None,
                   profile_key: str | None) -> list[str] | None:
        python = find_interpreter_with(_REQUIRED_MODULES)
        if python is None:
            return None
        cmd = [python, str(self.script), "scrape", "--url", url,
               "--out", str(out_dir)]
        if profile_key:
            cmd += ["--profile-key", profile_key]
        if chrome_path:
            cmd += ["--chrome-path", chrome_path]
        return cmd

    def collect_profile(self, url: str, out_dir: Path, chrome_path: str | None = None,
                         on_progress: ProgressCallback | None = None,
                         profile_key: str | None = None) -> ScrapeResult:
        base = self._base_cmd(url, out_dir, chrome_path, profile_key)
        if base is None:
            self.logger.error(_MISSING_INTERPRETER_MSG)
            return ScrapeResult(ok=False, returncode=-1, out_dir=out_dir, error=_MISSING_INTERPRETER_MSG)
        cmd = base + ["--days", "1", "--limit", "1", "--no-comments"]
        return run_subprocess(cmd, out_dir, self.logger, on_progress,
                               session_check=(self.session_dir,
                                              "python fb_scraper.py login"))

    def collect_content(self, url: str, out_dir: Path, *, days: int | None = None,
                         since: str | None = None, until: str | None = None,
                         limit: int | None = None, max_comments: int | None = None,
                         no_comments: bool = False, headed: bool = True,
                         chrome_path: str | None = None,
                         on_progress: ProgressCallback | None = None,
                         profile_key: str | None = None,
                         workers: int | None = None) -> ScrapeResult:
        base = self._base_cmd(url, out_dir, chrome_path, profile_key)
        if base is None:
            self.logger.error(_MISSING_INTERPRETER_MSG)
            return ScrapeResult(ok=False, returncode=-1, out_dir=out_dir, error=_MISSING_INTERPRETER_MSG)
        cmd = base + build_window_args(days, since, until)
        if limit:
            cmd += ["--limit", str(limit)]
        if max_comments:
            cmd += ["--max-comments", str(max_comments)]
        if no_comments:
            cmd += ["--no-comments"]
        if headed:
            cmd += ["--headed"]
        if workers:
            cmd += ["--workers", str(workers)]
        return run_subprocess(cmd, out_dir, self.logger, on_progress,
                               session_check=(self.session_dir,
                                              "python fb_scraper.py login"))

    def collect_comments(self, url: str, out_dir: Path, *, days: int | None = None,
                          since: str | None = None, until: str | None = None,
                          max_comments: int | None = None, headed: bool = True,
                          chrome_path: str | None = None,
                          on_progress: ProgressCallback | None = None,
                          profile_key: str | None = None) -> ScrapeResult:
        return self.collect_content(url, out_dir, days=days, since=since, until=until,
                                     max_comments=max_comments, no_comments=False,
                                     headed=headed, chrome_path=chrome_path,
                                     on_progress=on_progress, profile_key=profile_key)
