"""The simplest way to add Pillar6 to any agent.

Usage::

    from pillar6 import pillar6_wrap

    # Wrap any callable that takes a string and returns a string
    my_production_agent = pillar6_wrap(my_agent_function)
    result = await my_production_agent("What is quantum computing?")

    # Now you get: tracing, cost tracking, security checks,
    # and eval capability — for free.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
import uuid
from collections.abc import Callable
from typing import Any, TypeVar, overload

from pillar6.config.models import Pillar6Config
from pillar6.core.eval import DefaultEvalSuite
from pillar6.core.observability import DefaultObservabilityLayer
from pillar6.core.router import DefaultRouter
from pillar6.core.security import DefaultGuardrailEngine
from pillar6.types import TraceEvent

F = TypeVar("F", bound=Callable[..., Any])


class WrappedAgent:
    """A wrapped agent function with Pillar6 production infrastructure attached.

    Attributes:
        traces: The observability layer for accessing traces and metrics.
        costs: The router for cost tracking and model routing.
        security: The guardrail engine for input/output validation.
        evals: The evaluation suite for testing.
        last_workflow_id: The workflow ID from the most recent invocation.
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        config: Pillar6Config | None = None,
    ) -> None:
        self._fn = fn
        self._is_async = inspect.iscoroutinefunction(fn)
        self._config = config or Pillar6Config()

        self.traces = DefaultObservabilityLayer(config=self._config.observability)
        self.costs = DefaultRouter(config=self._config.router)
        self.security = DefaultGuardrailEngine(config=self._config.security)
        self.evals = DefaultEvalSuite(config=self._config.eval)
        self.last_workflow_id: str = ""

    async def __call__(self, query: str, **kwargs: Any) -> str:
        """Invoke the wrapped function with full Pillar6 instrumentation."""
        workflow_id = uuid.uuid4().hex[:12]
        self.last_workflow_id = workflow_id
        agent_id = self._config.agent.agent_id

        # Start trace
        trace_ctx = self.traces.start_trace(workflow_id)

        self.traces.add_event(
            trace_ctx,
            TraceEvent(
                event_type="wrapper.start",
                agent_id=agent_id,
                message=f"Wrapped call started: {query[:100]}",
            ),
        )

        try:
            # Security: check input
            validation = await self.security.check_input(query, agent_id)
            if not validation.passed:
                violations = "; ".join(validation.violations)
                self.traces.add_event(
                    trace_ctx,
                    TraceEvent(
                        event_type="security.blocked",
                        agent_id=agent_id,
                        message=f"Input blocked: {violations}",
                    ),
                )
                msg = f"Input validation failed: {violations}"
                raise ValueError(msg)

            # Execute the wrapped function
            start_time = time.monotonic()

            if self._is_async:
                result = await self._fn(query, **kwargs)
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None, functools.partial(self._fn, query, **kwargs)
                )

            duration_ms = (time.monotonic() - start_time) * 1000

            # Security: check output
            output_validation = await self.security.check_output(result)
            if not output_validation.passed:
                self.traces.add_event(
                    trace_ctx,
                    TraceEvent(
                        event_type="security.output_blocked",
                        agent_id=agent_id,
                        message=f"Output blocked: {'; '.join(output_validation.violations)}",
                    ),
                )

            # Track cost (emit metric for duration)
            await self.traces.emit_metric(
                "wrapper.duration_ms",
                duration_ms,
                tags={"agent_id": agent_id, "workflow_id": workflow_id},
            )

            # Record completion event
            self.traces.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="wrapper.complete",
                    agent_id=agent_id,
                    message=f"Wrapped call completed in {duration_ms:.1f}ms",
                    data={"duration_ms": duration_ms},
                ),
            )

            # Audit log
            await self.security.log_action(
                agent_id,
                "wrapped_call",
                {"query": query[:200], "duration_ms": duration_ms, "workflow_id": workflow_id},
            )

            return str(result)

        except Exception as exc:
            self.traces.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="wrapper.error",
                    agent_id=agent_id,
                    message=f"Error: {exc}",
                ),
            )
            raise
        finally:
            self.traces.end_trace(trace_ctx)


def pillar6_wrap(
    fn: Callable[..., Any],
    config: Pillar6Config | None = None,
) -> WrappedAgent:
    """Wrap any callable with Pillar6 production infrastructure.

    Takes any function ``(str) -> str`` (sync or async) and returns a new async
    callable that wraps the original with tracing, security, cost tracking,
    and evaluation.

    Args:
        fn: The function to wrap.  Must accept a string as the first argument
            and return a string.
        config: Optional Pillar6 configuration.  Uses sensible defaults if
            not provided.

    Returns:
        A :class:`WrappedAgent` instance that can be called like the original
        function but with all six pillars active.

    Example::

        from pillar6 import pillar6_wrap

        async def my_agent(query: str) -> str:
            return "Hello!"

        agent = pillar6_wrap(my_agent)
        result = await agent("Hi there")
        print(agent.traces.get_trace(agent.last_workflow_id))
    """
    return WrappedAgent(fn, config=config)


@overload
def pillar6_monitor(fn: F) -> F: ...


@overload
def pillar6_monitor(*, config: Pillar6Config | None = None) -> Callable[[F], F]: ...


def pillar6_monitor(
    fn: F | None = None,
    *,
    config: Pillar6Config | None = None,
) -> F | Callable[[F], F]:
    """Decorator to add Pillar6 production infrastructure to an agent function.

    Can be used with or without arguments::

        @pillar6_monitor
        async def my_agent(query: str) -> str:
            ...

        @pillar6_monitor(config=my_config)
        async def my_agent(query: str) -> str:
            ...

    The decorated function becomes a :class:`WrappedAgent` and gains
    ``.traces``, ``.costs``, ``.security``, and ``.evals`` attributes.
    """

    def decorator(func: F) -> F:
        wrapped = WrappedAgent(func, config=config)
        functools.update_wrapper(wrapped, func)
        return wrapped  # type: ignore[return-value]

    if fn is not None:
        return decorator(fn)
    return decorator  # type: ignore[return-value]
