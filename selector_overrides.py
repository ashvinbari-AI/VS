#!/usr/bin/env python3
"""
Per-profile DOM selector overrides for fb_scraper.py.

The docstring in fb_scraper.py refers to a companion `fb_doctor.py` that is
meant to populate a per-leader registry here after diagnosing a blocked or
renamed layout against a specific --profile-key. That tool isn't present in
this checkout, so OVERRIDES starts empty and apply_to() is a no-op: SELECTORS
stays exactly what fb_scraper.py defines, whatever --profile-key is passed.

To add an override once you've found a working selector for some page:
    OVERRIDES["some_profile_key"] = {"comment_article": 'div[role="article"][data-x]'}
Any attribute name here must match one defined on fb_scraper.SELECTORS.
"""

from __future__ import annotations

OVERRIDES: dict[str, dict[str, object]] = {}


def apply_to(selectors, profile_key: str | None) -> None:
    """Mutate `selectors` (fb_scraper.SELECTORS) in place for this profile key."""
    if not profile_key:
        return
    over = OVERRIDES.get(profile_key)
    if not over:
        return
    for k, v in over.items():
        setattr(selectors, k, v)
