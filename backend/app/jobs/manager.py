"""
Local background job system (spec section 48) -- scraping and analysis run
on a daemon thread so they never block the FastAPI event loop. State lives
in-memory (this is a single-user local tool restarted rarely); the React
side polls GET /api/scrape/status/{job_id} until status is a terminal one.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

JobStatus = str  # "queued" | "running" | "completed" | "failed"


@dataclass
class Job:
    id: str
    kind: str
    status: JobStatus = "queued"
    progress: dict[str, Any] = field(default_factory=dict)
    status_message: str = ""
    result: Any = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.id, "kind": self.kind, "status": self.status,
            "progress": self.progress, "status_message": self.status_message,
            "result": self.result, "error": self.error,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def create_job(kind: str) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], kind=kind)
    with _lock:
        _jobs[job.id] = job
    return job


def get_job(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def list_jobs() -> list[dict[str, Any]]:
    with _lock:
        return [j.to_dict() for j in sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)]


def _update(job: Job, **kwargs: Any) -> None:
    with _lock:
        for k, v in kwargs.items():
            setattr(job, k, v)
        job.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_job(job: Job, target: Callable[[Job], Any]) -> None:
    """Runs `target(job)` on a background thread. `target` is responsible for
    calling job helper functions (set_progress/set_status_message) as it
    goes and for returning the final result dict (or raising)."""

    def _runner() -> None:
        _update(job, status="running")
        try:
            result = target(job)
            _update(job, status="completed", result=result, status_message="Completed")
        except Exception as e:  # noqa: BLE001 -- surfaced to the UI, not crashed
            _update(job, status="failed", error=str(e), status_message=f"Failed: {e}")

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()


def set_progress(job: Job, key: str, percent: int | None) -> None:
    with _lock:
        job.progress[key] = percent
        job.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")


def set_status_message(job: Job, message: str) -> None:
    _update(job, status_message=message)
