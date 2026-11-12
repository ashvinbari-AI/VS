"""Shared parsing for the multi-person comparison endpoints.

Every comparison route takes the selected people as a repeated
`person_ids` query parameter (`?person_ids=a&person_ids=b&person_ids=c`)
and returns per-person blocks keyed by person_id, in the same order the
caller sent them -- so the frontend can compare 2, 3, 4... people with the
same code path instead of a hardcoded Person A / Person B pair.
"""

from __future__ import annotations

from typing import Iterable

from fastapi import HTTPException

# Upper bound on how many people one comparison can include. Matches
# MAX_PEOPLE in frontend/src/state/FilterContext.tsx -- keep both in sync.
MAX_COMPARE_PEOPLE = 6


def parse_person_ids(person_ids: Iterable[str] | None) -> list[str]:
    """De-duplicates (order-preserving), drops blanks, and enforces 1..MAX."""
    ids: list[str] = []
    for raw in person_ids or []:
        pid = (raw or "").strip()
        if pid and pid not in ids:
            ids.append(pid)
    if not ids:
        raise HTTPException(status_code=400, detail="At least one person_ids value is required.")
    if len(ids) > MAX_COMPARE_PEOPLE:
        raise HTTPException(
            status_code=400,
            detail=f"At most {MAX_COMPARE_PEOPLE} people can be compared at once (got {len(ids)}).",
        )
    return ids
