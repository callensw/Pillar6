"""Tests for the Observability pillar."""

from __future__ import annotations

import time

import pytest

from pillar6.core.observability import DefaultObservabilityLayer
from pillar6.types import TraceEvent


@pytest.fixture
def obs() -> DefaultObservabilityLayer:
    return DefaultObservabilityLayer()


# --- Trace lifecycle ---


def test_start_trace(obs: DefaultObservabilityLayer) -> None:
    ctx = obs.start_trace("wf-1")
    assert ctx.workflow_id == "wf-1"
    assert ctx.trace_id != ""
    assert ctx.start_time_ms > 0


def test_add_event(obs: DefaultObservabilityLayer) -> None:
    ctx = obs.start_trace("wf-1")
    obs.add_event(ctx, TraceEvent(event_type="test", message="hello"))
    assert len(obs._traces["wf-1"]) == 1
    assert obs._traces["wf-1"][0].trace_id == ctx.trace_id
    assert obs._traces["wf-1"][0].event_id != ""


def test_end_trace(obs: DefaultObservabilityLayer) -> None:
    ctx = obs.start_trace("wf-1")
    obs.add_event(ctx, TraceEvent(event_type="test", message="hello"))
    obs.end_trace(ctx)
    assert ctx.completed is True
    assert ctx.end_time_ms > 0
    assert ctx.total_duration_ms >= 0


async def test_get_trace(obs: DefaultObservabilityLayer) -> None:
    ctx = obs.start_trace("wf-1")
    obs.add_event(ctx, TraceEvent(event_type="a", message="first"))
    obs.add_event(ctx, TraceEvent(event_type="b", message="second"))

    events = await obs.get_trace("wf-1")
    assert len(events) == 2
    assert events[0].event_type == "a"


async def test_get_trace_empty(obs: DefaultObservabilityLayer) -> None:
    events = await obs.get_trace("nonexistent")
    assert events == []


async def test_events_ordered_by_timestamp(obs: DefaultObservabilityLayer) -> None:
    ctx = obs.start_trace("wf-1")
    obs.add_event(ctx, TraceEvent(event_type="a", timestamp_ms=200))
    obs.add_event(ctx, TraceEvent(event_type="b", timestamp_ms=100))
    obs.add_event(ctx, TraceEvent(event_type="c", timestamp_ms=300))

    events = await obs.get_trace("wf-1")
    assert events[0].event_type == "b"
    assert events[1].event_type == "a"
    assert events[2].event_type == "c"


def test_nested_events(obs: DefaultObservabilityLayer) -> None:
    ctx = obs.start_trace("wf-1")
    parent = TraceEvent(event_type="parent", message="parent")
    obs.add_event(ctx, parent)
    child = TraceEvent(event_type="child", message="child", parent_event_id=parent.event_id)
    obs.add_event(ctx, child)

    events = obs._traces["wf-1"]
    assert events[1].parent_event_id == events[0].event_id


# --- Metrics ---


async def test_emit_metric(obs: DefaultObservabilityLayer) -> None:
    await obs.emit_metric("latency", 42.0, {"env": "test"})
    metrics = obs.get_metrics()
    assert len(metrics) == 1
    assert metrics[0]["name"] == "latency"
    assert metrics[0]["value"] == 42.0


async def test_get_metrics_by_name(obs: DefaultObservabilityLayer) -> None:
    await obs.emit_metric("a", 1.0)
    await obs.emit_metric("b", 2.0)
    await obs.emit_metric("a", 3.0)

    results = obs.get_metrics(name="a")
    assert len(results) == 2
    assert all(m["name"] == "a" for m in results)


async def test_get_metrics_since(obs: DefaultObservabilityLayer) -> None:
    await obs.emit_metric("x", 1.0)
    cutoff = time.time()
    await obs.emit_metric("x", 2.0)

    results = obs.get_metrics(since=cutoff)
    assert len(results) >= 1


# --- Structured logging ---


def test_structured_log(obs: DefaultObservabilityLayer) -> None:
    ctx = obs.start_trace("wf-1")
    obs.log("INFO", "Test message", trace_ctx=ctx, agent_id="agent-1", extra="data")

    logs = obs.get_logs()
    assert len(logs) == 1
    assert logs[0].level == "INFO"
    assert logs[0].message == "Test message"
    assert logs[0].agent_id == "agent-1"
    assert logs[0].workflow_id == "wf-1"
    assert logs[0].data["extra"] == "data"


def test_log_filtering_by_level(obs: DefaultObservabilityLayer) -> None:
    obs.log("INFO", "info msg")
    obs.log("ERROR", "error msg")
    obs.log("INFO", "info msg 2")

    errors = obs.get_logs(level="ERROR")
    assert len(errors) == 1
    assert errors[0].message == "error msg"


def test_log_filtering_by_agent(obs: DefaultObservabilityLayer) -> None:
    obs.log("INFO", "msg a", agent_id="agent-1")
    obs.log("INFO", "msg b", agent_id="agent-2")

    logs = obs.get_logs(agent_id="agent-1")
    assert len(logs) == 1
    assert logs[0].agent_id == "agent-1"


# --- Export trace ---


async def test_export_trace(obs: DefaultObservabilityLayer) -> None:
    ctx = obs.start_trace("wf-1")
    obs.add_event(ctx, TraceEvent(event_type="step", message="step 1"))
    await obs.emit_metric("tokens", 100.0)
    obs.log("INFO", "log entry", trace_ctx=ctx)
    obs.end_trace(ctx)

    exported = await obs.export_trace("wf-1")
    assert exported["workflow_id"] == "wf-1"
    assert exported["completed"] is True
    assert exported["total_duration_ms"] >= 0
    assert len(exported["events"]) == 1
    assert len(exported["metrics"]) >= 1
    assert isinstance(exported["logs"], list)


# --- Multiple concurrent traces ---


async def test_concurrent_traces(obs: DefaultObservabilityLayer) -> None:
    ctx1 = obs.start_trace("wf-1")
    ctx2 = obs.start_trace("wf-2")

    obs.add_event(ctx1, TraceEvent(event_type="a", message="wf1 event"))
    obs.add_event(ctx2, TraceEvent(event_type="b", message="wf2 event"))

    events1 = await obs.get_trace("wf-1")
    events2 = await obs.get_trace("wf-2")

    assert len(events1) == 1
    assert len(events2) == 1
    assert events1[0].event_type == "a"
    assert events2[0].event_type == "b"
