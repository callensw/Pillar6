"""FastAPI server for the Research Assistant.

Exposes REST endpoints and WebSocket for real-time updates.
Start with: ``uvicorn examples.server:app --reload``
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pipeline import run_research
from storage import Storage, create_storage

app = FastAPI(
    title="Pillar6 Research Assistant",
    description="Multi-Agent Research Assistant powered by Pillar6",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global storage instance (created on startup)
_storage: Storage | None = None

# Active WebSocket connections per job
_ws_connections: dict[str, list[WebSocket]] = {}


def _get_storage() -> Storage:
    global _storage  # noqa: PLW0603
    if _storage is None:
        _storage = create_storage()
    return _storage


@app.on_event("startup")
async def _startup() -> None:
    global _storage  # noqa: PLW0603
    _storage = create_storage()


# ---- REST endpoints ----


@app.post("/research")
async def create_research(body: dict[str, Any]) -> dict[str, Any]:
    """Submit a new research question.

    Body: ``{"question": "..."}``
    Returns: ``{"job_id": "...", "status": "pending"}``
    """
    question = body.get("question", "")
    if not question:
        return {"error": "Question is required"}

    storage = _get_storage()
    job = await storage.create_job(question)

    # Run the research in the background
    async def _run() -> None:
        async def on_event(job_id: str, event: dict[str, Any]) -> None:
            # Broadcast to WebSocket clients
            conns = _ws_connections.get(job_id, [])
            msg = json.dumps(event, default=str)
            for ws in conns:
                with contextlib.suppress(Exception):
                    await ws.send_text(msg)

        await run_research(question, storage, on_event=on_event)

    asyncio.create_task(_run())
    return {"job_id": job.id, "status": "pending"}


@app.get("/research/{job_id}")
async def get_research(job_id: str) -> dict[str, Any]:
    """Get the status and results of a research job."""
    storage = _get_storage()
    job = await storage.get_job(job_id)
    if not job:
        return {"error": "Job not found"}
    return job.to_dict()


@app.get("/research/{job_id}/trace")
async def get_trace(job_id: str) -> dict[str, Any]:
    """Get the full observability trace for a research job."""
    storage = _get_storage()
    job = await storage.get_job(job_id)
    if not job:
        return {"error": "Job not found"}
    return {"job_id": job_id, "trace": job.trace}


@app.get("/research/{job_id}/costs")
async def get_costs(job_id: str) -> dict[str, Any]:
    """Get the cost breakdown for a research job."""
    storage = _get_storage()
    job = await storage.get_job(job_id)
    if not job:
        return {"error": "Job not found"}
    return {"job_id": job_id, "costs": job.costs}


@app.get("/jobs")
async def list_jobs() -> dict[str, Any]:
    """List recent research jobs."""
    storage = _get_storage()
    jobs = await storage.list_jobs()
    return {"jobs": [j.to_dict() for j in jobs]}


@app.get("/system")
async def system_overview() -> dict[str, Any]:
    """Get system health and statistics."""
    storage = _get_storage()
    jobs = await storage.list_jobs(limit=100)
    completed = [j for j in jobs if j.status == "complete"]
    total_cost = sum(j.costs.get("total_cost_usd", 0) for j in completed)
    avg_time = 0.0
    if completed:
        durations = [j.completed_at - j.created_at for j in completed if j.completed_at > 0]
        avg_time = sum(durations) / len(durations) if durations else 0.0
    return {
        "total_jobs": len(jobs),
        "completed_jobs": len(completed),
        "failed_jobs": sum(1 for j in jobs if j.status == "failed"),
        "total_cost_usd": total_cost,
        "avg_completion_time_s": round(avg_time, 2),
    }


# ---- WebSocket ----


@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str) -> None:
    """Stream real-time agent events for a research job."""
    await websocket.accept()
    if job_id not in _ws_connections:
        _ws_connections[job_id] = []
    _ws_connections[job_id].append(websocket)

    try:
        # Send existing events for this job
        storage = _get_storage()
        job = await storage.get_job(job_id)
        if job:
            for event in job.events:
                await websocket.send_text(json.dumps(event, default=str))

        # Keep connection alive until client disconnects
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        conns = _ws_connections.get(job_id, [])
        if websocket in conns:
            conns.remove(websocket)
