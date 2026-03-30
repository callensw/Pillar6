"""Storage layer — Supabase with in-memory fallback.

If ``SUPABASE_URL`` and ``SUPABASE_KEY`` are set, uses Supabase.
Otherwise, falls back to a thread-safe in-memory store with a warning.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ResearchJob:
    """A single research job."""

    id: str = ""
    question: str = ""
    status: str = "pending"  # pending | running | complete | failed
    result: str = ""
    trace: dict[str, Any] = field(default_factory=dict)
    costs: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = 0.0
    completed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "id": self.id,
            "question": self.question,
            "status": self.status,
            "result": self.result,
            "trace": self.trace,
            "costs": self.costs,
            "events": self.events,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class Storage(ABC):
    """Abstract storage interface."""

    @abstractmethod
    async def create_job(self, question: str) -> ResearchJob:
        """Create a new research job."""

    @abstractmethod
    async def get_job(self, job_id: str) -> ResearchJob | None:
        """Get a job by ID."""

    @abstractmethod
    async def update_job(self, job: ResearchJob) -> None:
        """Update an existing job."""

    @abstractmethod
    async def list_jobs(self, limit: int = 20) -> list[ResearchJob]:
        """List recent jobs."""

    @abstractmethod
    async def add_event(self, job_id: str, event: dict[str, Any]) -> None:
        """Append a real-time event to a job."""


class InMemoryStorage(Storage):
    """Thread-safe in-memory storage."""

    def __init__(self) -> None:
        self._jobs: dict[str, ResearchJob] = {}

    async def create_job(self, question: str) -> ResearchJob:
        job = ResearchJob(
            id=uuid.uuid4().hex[:12],
            question=question,
            status="pending",
            created_at=time.time(),
        )
        self._jobs[job.id] = job
        return job

    async def get_job(self, job_id: str) -> ResearchJob | None:
        return self._jobs.get(job_id)

    async def update_job(self, job: ResearchJob) -> None:
        self._jobs[job.id] = job

    async def list_jobs(self, limit: int = 20) -> list[ResearchJob]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    async def add_event(self, job_id: str, event: dict[str, Any]) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.events.append(event)


class SupabaseStorage(Storage):
    """Supabase-backed storage.

    Requires ``SUPABASE_URL`` and ``SUPABASE_KEY`` environment variables.
    Uses httpx for REST API calls (no Supabase SDK dependency).
    """

    def __init__(self, url: str, key: str) -> None:
        self._url = url.rstrip("/")
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def _request(self, method: str, table: str, **kwargs: Any) -> Any:
        import httpx

        url = f"{self._url}/rest/v1/{table}"
        async with httpx.AsyncClient() as client:
            resp = await client.request(method, url, headers=self._headers, **kwargs)
            resp.raise_for_status()
            if resp.content:
                return resp.json()
            return None

    async def create_job(self, question: str) -> ResearchJob:
        job_id = uuid.uuid4().hex[:12]
        data = {
            "id": job_id,
            "question": question,
            "status": "pending",
            "result": "",
            "trace": {},
            "costs": {},
            "created_at": time.time(),
            "completed_at": 0.0,
        }
        result = await self._request("POST", "research_jobs", json=data)
        row = result[0] if isinstance(result, list) else data
        return ResearchJob(**{k: row.get(k, v) for k, v in data.items()})

    async def get_job(self, job_id: str) -> ResearchJob | None:
        result = await self._request("GET", f"research_jobs?id=eq.{job_id}&select=*")
        if result and isinstance(result, list) and len(result) > 0:
            row = result[0]
            return ResearchJob(
                id=row["id"],
                question=row.get("question", ""),
                status=row.get("status", "pending"),
                result=row.get("result", ""),
                trace=row.get("trace", {}),
                costs=row.get("costs", {}),
                events=row.get("events", []),
                created_at=row.get("created_at", 0.0),
                completed_at=row.get("completed_at", 0.0),
            )
        return None

    async def update_job(self, job: ResearchJob) -> None:
        await self._request(
            "PATCH",
            f"research_jobs?id=eq.{job.id}",
            json=job.to_dict(),
        )

    async def list_jobs(self, limit: int = 20) -> list[ResearchJob]:
        result = await self._request(
            "GET",
            f"research_jobs?select=*&order=created_at.desc&limit={limit}",
        )
        if not result or not isinstance(result, list):
            return []
        return [
            ResearchJob(
                id=r["id"],
                question=r.get("question", ""),
                status=r.get("status", "pending"),
                result=r.get("result", ""),
                created_at=r.get("created_at", 0.0),
                completed_at=r.get("completed_at", 0.0),
            )
            for r in result
        ]

    async def add_event(self, job_id: str, event: dict[str, Any]) -> None:
        # For Supabase, we store events in a separate table
        await self._request(
            "POST",
            "research_events",
            json={"job_id": job_id, **event},
        )


def create_storage() -> Storage:
    """Create the appropriate storage backend.

    Returns SupabaseStorage if environment variables are set,
    otherwise InMemoryStorage with a warning.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if url and key:
        logger.info("Using Supabase storage at %s", url)
        return SupabaseStorage(url, key)
    logger.warning(
        "SUPABASE_URL/SUPABASE_KEY not set — using in-memory storage. Data will be lost on restart."
    )
    return InMemoryStorage()
