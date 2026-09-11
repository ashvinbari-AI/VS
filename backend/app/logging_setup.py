"""Three rotating-free plain log files: logs/backend.log, scraper.log, analysis.log.

Kept deliberately simple (local tool, not a service) -- a single FileHandler
per logger, appended to across runs. Never logs secrets: callers must not
pass GEMINI_API_KEY or full .env contents into a log message.
"""

from __future__ import annotations

import logging
from pathlib import Path

_FORMAT = "%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s"
_configured: set[str] = set()


def get_logger(name: str, logs_dir: Path) -> logging.Logger:
    """name in {'backend', 'scraper', 'analysis'} selects the log file."""
    logger = logging.getLogger(f"polint.{name}")
    if name in _configured:
        return logger
    logs_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(logs_dir / f"{name}.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(stream)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _configured.add(name)
    return logger
