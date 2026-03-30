"""Tests for the Observability pillar."""

from __future__ import annotations

import pytest

from pillar6.core.observability import DefaultObservabilityLayer
from pillar6.types import TraceEvent


@pytest.fixture
def obs() -> DefaultObservabilityLayer:
    return DefaultObservabilityLayer()


def test_start_trace(obs: DefaultObservabilityLayer) -> None:
    ctx = obs.start_trace("wf-1")
    assert ctx.workflow_id == "wf-1"
    assert ctx.trace_id != ""


def test_add_event(obs: DefaultObservabilityLayer) -> None:
    ctx = obs.start_trace("wf-1")
    obs.add_event(ctx, TraceEvent(event_type="test", message="hello"))
    assert len(obs._traces["wf-1"]) == 1
    assert obs._traces["wf-1"][0].trace_id == ctx.trace_id


def test_end_trace_no_error(obs: DefaultObservabilityLayer) -> None:
    ctx = obs.start_trace("wf-1")
    obs.end_trace(ctx)  # should not raise


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


async def test_emit_metric(obs: DefaultObservabilityLayer) -> None:
    await obs.emit_metric("latency", 42.0, {"env": "test"})
    assert len(obs._metrics) == 1
    assert obs._metrics[0]["name"] == "latency"
    assert obs._metrics[0]["value"] == 42.0
