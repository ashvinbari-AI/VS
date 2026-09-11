"""Subprocess wrapper around the existing, untouched ig_scraper.py.

ig_scraper.py CLI (confirmed by inspection, not assumed):
    python ig_scraper.py login  [--chrome-path]
    python ig_scraper.py check  [--chrome-path] [--headed]
    python ig_scraper.py scrape --url URL [--days N | --since --until]
        [--limit N] [--out DIR] [--headed] [--no-comments]
        [--max-comments N] [--chrome-path]

Session lives at ig_session/cookies.pkl (relative to the scraper's cwd) --
created by `ig_scraper.py login`, which this adapter does not attempt to
automate (it requires a human to solve login/2FA in a real browser window).
"""

from __future__ import annotations

import re
from pathlib import Path

from app.config import get_settings
from app.logging_setup import get_logger
from app.scrapers.base import ProgressCallback, ScrapeResult, build_window_args, run_subprocess
from app.scrapers.interpreter import find_interpreter_with

_URL_RE = re.compile(r"^https?://(www\.)?instagram\.com/[A-Za-z0-9_.]+/?", re.I)
_REQUIRED_MODULES = ("selenium", "webdriver_manager")
_MISSING_INTERPRETER_MSG = (
    "No Python interpreter with selenium + webdriver-manager was found on this machine "
    "(checked `py -0p` and common install paths). Install them "
    "(`pip install selenium webdriver-manager`) for the interpreter you use to run "
    "ig_scraper.py, or set PYTHON_EXECUTABLE in .env to that interpreter's full path."
)


class InstagramAdapter:
    platform = "instagram"

    def __init__(self) -> None:
        s = get_settings()
        self.script = s.scraper_dir / "ig_scraper.py"
        self.session_path = s.scraper_dir / "ig_session" / "cookies.pkl"
        self.logger = get_logger("scraper", s.logs_dir)

    def validate_profile(self, url: str) -> tuple[bool, str | None]:
        if not url:
            return False, "Instagram URL is empty"
        if not _URL_RE.match(url.strip()):
            return False, "Not a recognizable instagram.com profile URL"
        return True, None

    def _base_cmd(self, url: str, out_dir: Path, chrome_path: str | None) -> list[str] | None:
        python = find_interpreter_with(_REQUIRED_MODULES)
        if python is None:
            return None
        cmd = [python, str(self.script), "scrape", "--url", url,
               "--out", str(out_dir)]
        if chrome_path:
            cmd += ["--chrome-path", chrome_path]
        return cmd

    def collect_profile(self, url: str, out_dir: Path, chrome_path: str | None = None,
                         on_progress: ProgressCallback | None = None) -> ScrapeResult:
        base = self._base_cmd(url, out_dir, chrome_path)
        if base is None:
            self.logger.error(_MISSING_INTERPRETER_MSG)
            return ScrapeResult(ok=False, returncode=-1, out_dir=out_dir, error=_MISSING_INTERPRETER_MSG)
        # Cheapest possible real call: 1 post, no comment threads, just to
        # populate scrape_runs.jsonl (followers) and confirm the profile loads.
        cmd = base + ["--days", "1", "--limit", "1", "--no-comments"]
        return run_subprocess(cmd, out_dir, self.logger, on_progress,
                               session_check=(self.session_path,
                                              "python ig_scraper.py login"))

    def collect_content(self, url: str, out_dir: Path, *, days: int | None = None,
                         since: str | None = None, until: str | None = None,
                         limit: int | None = None, max_comments: int | None = None,
                         no_comments: bool = False, headed: bool = False,
                         chrome_path: str | None = None,
                         on_progress: ProgressCallback | None = None) -> ScrapeResult:
        base = self._base_cmd(url, out_dir, chrome_path)
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
        return run_subprocess(cmd, out_dir, self.logger, on_progress,
                               session_check=(self.session_path,
                                              "python ig_scraper.py login"))

    def collect_comments(self, url: str, out_dir: Path, *, days: int | None = None,
                          since: str | None = None, until: str | None = None,
                          max_comments: int | None = None, headed: bool = False,
                          chrome_path: str | None = None,
                          on_progress: ProgressCallback | None = None) -> ScrapeResult:
        # Same underlying call as collect_content with comments forced on --
        # ig_scraper has no comments-only mode.
        return self.collect_content(url, out_dir, days=days, since=since, until=until,
                                     max_comments=max_comments, no_comments=False,
                                     headed=headed, chrome_path=chrome_path,
                                     on_progress=on_progress)
