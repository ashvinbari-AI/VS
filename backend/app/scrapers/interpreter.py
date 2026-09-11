"""
Finds a Python interpreter that actually has the modules a scraper needs.

Real bug this fixes: the platform used to shell out to a bare `python`
command and trust whatever the backend subprocess's PATH resolved that to.
On a machine with several Python installs (a plain 3.14, a 3.12, a conda
base env, ...) that resolution can silently land on an interpreter with
neither `selenium` nor `playwright` installed, even though a *different*
`python` on the same machine has both -- ig_scraper.py/fb_scraper.py then
exit immediately with "not installed", which the job system reported as a
plain "completed" job with no visible error. See PersonCard/DataSources.tsx
and jobs/manager.py for the other half of that fix (surfacing per-platform
errors instead of a bare "completed").

Resolution order:
  1. `PYTHON_EXECUTABLE` env var / Settings override, if it works.
  2. Every interpreter the Windows `py` launcher knows about (`py -0p`).
  3. A short list of common install locations, as a last resort.
The first candidate that can actually `import` every required module wins,
and the result is cached per module-set so this only runs once per module
combination, not on every scrape click.
"""

from __future__ import annotations

import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

_FALLBACK_CANDIDATES = [
    r"C:\Python314\python.exe",
    r"C:\Python312\python.exe",
    str(Path.home() / "AppData/Local/Programs/Python/Python312/python.exe"),
    str(Path.home() / "AppData/Local/Programs/Python/Python313/python.exe"),
    str(Path.home() / "miniconda3/python.exe"),
    sys.executable,
    "python",
]


def _py_launcher_candidates() -> list[str]:
    try:
        out = subprocess.run(["py", "-0p"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    # Lines look like: " -V:3.14 *        C:\Python314\python.exe"
    return re.findall(r"(\S:\\[^\r\n]*?python\.exe)", out.stdout, flags=re.IGNORECASE)


def _has_modules(python_exe: str, modules: tuple[str, ...]) -> bool:
    probe = "; ".join(f"import {m}" for m in modules)
    try:
        result = subprocess.run([python_exe, "-c", probe], capture_output=True, timeout=10)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@lru_cache
def find_interpreter_with(modules: tuple[str, ...]) -> str | None:
    override = get_settings().python_executable
    candidates = ([override] if override else []) + _py_launcher_candidates() + _FALLBACK_CANDIDATES
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.lower()
        if not candidate or key in seen:
            continue
        seen.add(key)
        if _has_modules(candidate, modules):
            return candidate
    return None
