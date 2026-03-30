"""Observability pillar — tracing, metrics, and structured logging.

Provides the abstract interface and a default in-memory implementation for
distributed tracing, event recording, and metric emission.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod

from pillar6.config.models import ObservabilityConfig
from pillar6.types import TraceContext, TraceEvent

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


class DefaultObservabilityLayer(ObservabilityLayer):
    """In-memory observability layer suitable for development and testing."""

    def __init__(self, config: ObservabilityConfig | None = None) -> None:
        self._config = config or ObservabilityConfig()
        self._traces: dict[str, list[TraceEvent]] = {}
        self._metrics: list[dict[str, object]] = []

    def start_trace(self, workflow_id: str) -> TraceContext:
        """Start a new in-memory trace."""
        trace_id = uuid.uuid4().hex[:16]
        ctx = TraceContext(
            workflow_id=workflow_id,
            trace_id=trace_id,
            start_time_ms=time.time() * 1000,
        )
        self._traces[workflow_id] = []
        logger.debug("Started trace %s for workflow %s", trace_id, workflow_id)
        return ctx

    def add_event(self, trace_ctx: TraceContext, event: TraceEvent) -> None:
        """Record an event in the trace store."""
        event.trace_id = trace_ctx.trace_id
        if not event.timestamp_ms:
            event.timestamp_ms = time.time() * 1000
        events = self._traces.setdefault(trace_ctx.workflow_id, [])
        events.append(event)
        logger.debug("Trace event: %s — %s", event.event_type, event.message)

    def end_trace(self, trace_ctx: TraceContext) -> None:
        """Mark a trace as ended (no-op in in-memory implementation)."""
        logger.debug("Ended trace %s for workflow %s", trace_ctx.trace_id, trace_ctx.workflow_id)

    async def get_trace(self, workflow_id: str) -> list[TraceEvent]:
        """Return all events for the given workflow."""
        return list(self._traces.get(workflow_id, []))

    async def emit_metric(
        self, name: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """Store a metric in memory."""
        entry: dict[str, object] = {
            "name": name,
            "value": value,
            "tags": tags or {},
            "timestamp": time.time(),
        }
        self._metrics.append(entry)
        logger.debug("Metric: %s=%f tags=%s", name, value, tags)
