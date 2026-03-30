"""Tests for the research pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_APP_DIR = str(Path(__file__).resolve().parent.parent)
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from pipeline import run_research
from storage import InMemoryStorage


class TestPipeline:
    """Integration tests for the research pipeline."""

    @pytest.mark.asyncio
    async def test_run_research_completes(self) -> None:
        storage = InMemoryStorage()
        job = await run_research("test question", storage)
        assert job.status == "complete"
        assert job.result != ""
        assert job.completed_at > 0

    @pytest.mark.asyncio
    async def test_run_research_records_events(self) -> None:
        storage = InMemoryStorage()
        events_received: list[dict] = []  # type: ignore[type-arg]

        async def on_event(job_id: str, event: dict) -> None:  # type: ignore[type-arg]
            events_received.append(event)

        await run_research("quantum computing", storage, on_event=on_event)
        assert len(events_received) >= 2  # at least start + complete

    @pytest.mark.asyncio
    async def test_job_stored_in_storage(self) -> None:
        storage = InMemoryStorage()
        job = await run_research("climate change", storage)
        retrieved = await storage.get_job(job.id)
        assert retrieved is not None
        assert retrieved.status == "complete"
        assert retrieved.question == "climate change"


class TestStorage:
    """Tests for the in-memory storage."""

    @pytest.mark.asyncio
    async def test_create_and_get(self) -> None:
        storage = InMemoryStorage()
        job = await storage.create_job("test")
        assert job.id != ""
        assert job.status == "pending"
        retrieved = await storage.get_job(job.id)
        assert retrieved is not None
        assert retrieved.question == "test"

    @pytest.mark.asyncio
    async def test_update_job(self) -> None:
        storage = InMemoryStorage()
        job = await storage.create_job("test")
        job.status = "complete"
        job.result = "done"
        await storage.update_job(job)
        retrieved = await storage.get_job(job.id)
        assert retrieved is not None
        assert retrieved.status == "complete"

    @pytest.mark.asyncio
    async def test_list_jobs(self) -> None:
        storage = InMemoryStorage()
        await storage.create_job("q1")
        await storage.create_job("q2")
        jobs = await storage.list_jobs()
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_add_event(self) -> None:
        storage = InMemoryStorage()
        job = await storage.create_job("test")
        await storage.add_event(job.id, {"type": "test"})
        retrieved = await storage.get_job(job.id)
        assert retrieved is not None
        assert len(retrieved.events) == 1
