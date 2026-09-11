"""
ScraperAdapter -- the seam between this platform and the existing, untouched
ig_scraper.py / fb_scraper.py.

Neither scraper is modified. Both already expose a `scrape` CLI subcommand
that does profile-meta + posts + comments in one pass (there is no separate
"just the profile" or "just the comments" mode in the underlying tool), so
collect_profile() / collect_content() / collect_comments() below are three
semantically-named entry points over the same subprocess call, distinguished
by which CLI flags they pass (e.g. collect_profile uses --no-comments and a
tiny --limit to fetch profile meta fast; collect_content/collect_comments run
the full window). This keeps the public interface the spec asks for without
inventing scraper behaviour that doesn't exist.

A caller drives collect_content() (the normal "Start Scraping" action); the
other two methods exist for callers that specifically want a cheap profile
check or a comments-only pass (--no-comments was already run once).
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from app.config import get_settings

ProgressCallback = Callable[[str, int | None], None]  # (status_line, percent_0_100)

_PROGRESS_RE = re.compile(r"\[(\d+)\s*/\s*(\d+)\]")


@dataclass
class ScrapeResult:
    ok: bool
    returncode: int
    out_dir: Path
    stdout_tail: list[str] = field(default_factory=list)
    error: str | None = None


class ScraperAdapter(Protocol):
    platform: str

    def validate_profile(self, url: str) -> tuple[bool, str | None]:
        """(is_valid, reason_if_not)."""
        ...

    def collect_profile(self, url: str, out_dir: Path, chrome_path: str | None,
                         on_progress: ProgressCallback | None) -> ScrapeResult:
        ...

    def collect_content(self, url: str, out_dir: Path, *, days: int | None,
                         since: str | None, until: str | None, limit: int | None,
                         max_comments: int | None, no_comments: bool,
                         headed: bool, chrome_path: str | None,
                         on_progress: ProgressCallback | None) -> ScrapeResult:
        ...

    def collect_comments(self, url: str, out_dir: Path, *, days: int | None,
                          since: str | None, until: str | None,
                          max_comments: int | None, headed: bool,
                          chrome_path: str | None,
                          on_progress: ProgressCallback | None) -> ScrapeResult:
        ...


def run_subprocess(cmd: list[str], out_dir: Path, logger,
                    on_progress: ProgressCallback | None = None,
                    session_check: tuple[Path, str] | None = None) -> ScrapeResult:
    """Shell out to a scraper CLI, streaming stdout into on_progress/log.

    session_check: (path, hint) -- if the path doesn't exist, fail fast with
    a clear message instead of launching a browser that will just log out.

    Real bug this fixes: ig_scraper.py/fb_scraper.py look up their saved
    login session with a path relative to the process's own cwd
    (`ig_session/cookies.pkl`, not relative to the script's own file
    location) -- Popen() used to inherit whatever directory the FastAPI
    backend itself happened to be launched from (e.g. backend/), so a
    session that plainly exists at the project root was reported missing.
    The subprocess's cwd is now pinned to scraper_dir explicitly.
    """
    out_dir = Path(out_dir)
    if session_check is not None:
        path, hint = session_check
        if not path.exists():
            msg = f"No saved session at {path}. Run: {hint}"
            logger.warning(msg)
            return ScrapeResult(ok=False, returncode=-1, out_dir=out_dir, error=msg)

    logger.info("launching: %s", " ".join(cmd))
    tail: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            cwd=str(get_settings().scraper_dir),
        )
    except FileNotFoundError as e:
        msg = f"Could not launch scraper process: {e}"
        logger.error(msg)
        return ScrapeResult(ok=False, returncode=-1, out_dir=out_dir, error=msg)

    assert proc.stdout is not None
    for raw_line in proc.stdout:
        line = raw_line.rstrip("\n")
        if not line.strip():
            continue
        logger.info(line)
        tail.append(line)
        if len(tail) > 200:
            tail.pop(0)
        if on_progress:
            pct = None
            m = _PROGRESS_RE.search(line)
            if m:
                done, total = int(m.group(1)), int(m.group(2))
                if total > 0:
                    pct = max(0, min(100, round(done / total * 100)))
            on_progress(line.strip(), pct)

    proc.wait()
    ok = proc.returncode == 0
    if not ok:
        logger.error("scraper exited with code %s", proc.returncode)
    return ScrapeResult(ok=ok, returncode=proc.returncode, out_dir=out_dir,
                         stdout_tail=tail[-20:],
                         error=None if ok else f"scraper exited with code {proc.returncode}")


def build_window_args(days: int | None, since: str | None, until: str | None) -> list[str]:
    if days:
        return ["--days", str(days)]
    if since:
        args = ["--since", since]
        if until:
            args += ["--until", until]
        return args
    # Neither given -- both CLIs require one; default to a safe 30-day window
    # rather than erroring, since the UI always offers a period selector.
    return ["--days", "30"]
