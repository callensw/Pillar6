"""Observability pillar — tracing, metrics, structured logging, and replay.

Provides the abstract interface and a default in-memory implementation for
distributed tracing, event recording, metric emission, structured logging,
and trace export for replay/debugging.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

from pillar6.config.models import ObservabilityConfig
from pillar6.types import LogEntry, TraceContext, TraceEvent, _now_iso

logger = logging.getLogger(__name__)


class ObservabilityLayer(ABC):
    """Abstract base class for the observability layer."""

    @abstractmethod
    def start_trace(self, workflow_id: str) -> TraceContext:
        """Begin a new trace for a workflow.

        Args:
            workflow_id: Unique workflow identifier.

        Returns:
            A new TraceContext.
        """

    @abstractmethod
    def add_event(self, trace_ctx: TraceContext, event: TraceEvent) -> None:
        """Add an event to an active trace.

        Args:
            trace_ctx: Active trace context.
            event: Event to record.
        """

    @abstractmethod
    def end_trace(self, trace_ctx: TraceContext) -> None:
        """End a trace, flushing any pending events.

        Args:
            trace_ctx: Trace context to close.
        """

    @abstractmethod
    async def get_trace(self, workflow_id: str) -> list[TraceEvent]:
        """Retrieve all events for a given workflow trace.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            Ordered list of trace events.
        """

    @abstractmethod
    async def emit_metric(
        self, name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """Emit a named metric value.

        Args:
            name: Metric name.
            value: Metric value.
            tags: Optional key-value tags for the metric.
        """


class _Metric:
    """Internal metric storage."""

    __slots__ = ("name", "value", "timestamp", "tags")

    def __init__(self, name: str, value: float, tags: dict[str, str]) -> None:
        self.name = name
        self.value = value
        self.timestamp = time.time()
        self.tags = tags

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
            "tags": self.tags,
        }


class DefaultObservabilityLayer(ObservabilityLayer):
    """In-memory observability layer with tracing, metrics, structured logging, and replay."""

    def __init__(self, config: ObservabilityConfig | None = None) -> None:
        self._config = config or ObservabilityConfig()
        self._active_traces: dict[str, TraceContext] = {}
        self._traces: dict[str, list[TraceEvent]] = {}
        self._completed_traces: dict[str, TraceContext] = {}
        self._metrics: list[_Metric] = []
        self._logs: list[LogEntry] = []

    def start_trace(self, workflow_id: str) -> TraceContext:
        """Start a new in-memory trace."""
        trace_id = uuid.uuid4().hex[:16]
        ctx = TraceContext(
            workflow_id=workflow_id,
            trace_id=trace_id,
            start_time_ms=time.time() * 1000,
        )
        self._active_traces[workflow_id] = ctx
        self._traces[workflow_id] = []
        logger.debug("Started trace %s for workflow %s", trace_id, workflow_id)
        return ctx

    def add_event(self, trace_ctx: TraceContext, event: TraceEvent) -> None:
        """Record an event in the trace store."""
        if not event.event_id:
            event.event_id = uuid.uuid4().hex[:12]
        event.trace_id = trace_ctx.trace_id
        if not event.timestamp_ms:
            event.timestamp_ms = time.time() * 1000
        events = self._traces.setdefault(trace_ctx.workflow_id, [])
        events.append(event)
        logger.debug("Trace event: %s — %s", event.event_type, event.message)

    def end_trace(self, trace_ctx: TraceContext) -> None:
        """Mark a trace as completed with timing information."""
        trace_ctx.end_time_ms = time.time() * 1000
        trace_ctx.total_duration_ms = trace_ctx.end_time_ms - trace_ctx.start_time_ms
        trace_ctx.completed = True
        self._completed_traces[trace_ctx.workflow_id] = trace_ctx
        self._active_traces.pop(trace_ctx.workflow_id, None)
        logger.debug(
            "Ended trace %s for workflow %s (%.1fms)",
            trace_ctx.trace_id,
            trace_ctx.workflow_id,
            trace_ctx.total_duration_ms,
        )

    async def get_trace(self, workflow_id: str) -> list[TraceEvent]:
        """Return all events for the given workflow, ordered by timestamp."""
        events = list(self._traces.get(workflow_id, []))
        events.sort(key=lambda e: e.timestamp_ms)
        return events

    async def emit_metric(
        self, name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """Store a metric in memory."""
        metric = _Metric(name=name, value=value, tags=tags or {})
        self._metrics.append(metric)
        logger.debug("Metric: %s=%f tags=%s", name, value, tags)

    def get_metrics(
        self, name: str | None = None, since: float | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve stored metrics with optional filtering.

        Args:
            name: Filter by metric name (None returns all).
            since: Filter to metrics after this Unix timestamp.

        Returns:
            List of metric dicts.
        """
        result: list[dict[str, Any]] = []
        for m in self._metrics:
            if name is not None and m.name != name:
                continue
            if since is not None and m.timestamp < since:
                continue
            result.append(m.to_dict())
        return result

    def log(
        self,
        level: str,
        message: str,
        trace_ctx: TraceContext | None = None,
        agent_id: str = "",
        **kwargs: Any,
    ) -> None:
        """Create a structured log entry.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR).
            message: Log message.
            trace_ctx: Optional trace context for correlation.
            agent_id: Optional agent identifier.
            **kwargs: Additional structured data fields.
        """
        entry = LogEntry(
            timestamp=_now_iso(),
            level=level.upper(),
            message=message,
            agent_id=agent_id,
            workflow_id=trace_ctx.workflow_id if trace_ctx else "",
            trace_id=trace_ctx.trace_id if trace_ctx else "",
            data=dict(kwargs),
        )
        self._logs.append(entry)
        logger.log(
            getattr(logging, level.upper(), logging.INFO),
            "[%s] %s",
            agent_id or "system",
            message,
        )

    def get_logs(
        self,
        level: str | None = None,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[LogEntry]:
        """Retrieve structured log entries with optional filtering.

        Args:
            level: Filter by log level.
            agent_id: Filter by agent identifier.
            limit: Maximum number of entries to return.

        Returns:
            List of log entries, most recent first.
        """
        result: list[LogEntry] = []
        for entry in reversed(self._logs):
            if level is not None and entry.level != level.upper():
                continue
            if agent_id is not None and entry.agent_id != agent_id:
                continue
            result.append(entry)
            if len(result) >= limit:
                break
        return result

    async def export_trace(self, workflow_id: str) -> dict[str, Any]:
        """Export a complete trace with events, metrics, and logs for replay.

        Args:
            workflow_id: The workflow to export.

        Returns:
            JSON-serializable dict containing the full trace data.
        """
        trace_ctx = self._completed_traces.get(workflow_id) or self._active_traces.get(workflow_id)
        events = await self.get_trace(workflow_id)

        trace_id = trace_ctx.trace_id if trace_ctx else ""

        # Collect relevant metrics and logs
        relevant_metrics = [m.to_dict() for m in self._metrics]
        relevant_logs = [
            entry.model_dump()
            for entry in self._logs
            if entry.workflow_id == workflow_id or entry.trace_id == trace_id
        ]

        return {
            "workflow_id": workflow_id,
            "trace_id": trace_id,
            "start_time_ms": trace_ctx.start_time_ms if trace_ctx else 0,
            "end_time_ms": trace_ctx.end_time_ms if trace_ctx else 0,
            "total_duration_ms": trace_ctx.total_duration_ms if trace_ctx else 0,
            "completed": trace_ctx.completed if trace_ctx else False,
            "events": [e.model_dump() for e in events],
            "metrics": relevant_metrics,
            "logs": relevant_logs,
        }
