"""Wrap a CrewAI Crew with Pillar6 production infrastructure.

Usage::

    from pillar6.wrappers.crewai import wrap_crew
    from crewai import Crew

    crew = Crew(agents=[...], tasks=[...])
    production_crew = wrap_crew(crew)
    result = production_crew.kickoff()

CrewAI is NOT a dependency of Pillar6.  This module uses duck typing
to detect CrewAI objects and will raise a clear error if CrewAI is
not installed.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from pillar6.config.models import Pillar6Config
from pillar6.core.observability import DefaultObservabilityLayer
from pillar6.core.router import DefaultRouter
from pillar6.core.security import DefaultGuardrailEngine
from pillar6.types import TraceEvent


def _check_crewai_available() -> None:
    """Raise a helpful error if CrewAI is not installed."""
    try:
        import crewai  # noqa: F401
    except ImportError:
        msg = "CrewAI is not installed. Install it with: pip install crewai"
        raise ImportError(msg) from None


class CrewWrapper:
    """A CrewAI Crew wrapped with Pillar6 production infrastructure.

    Attributes:
        traces: The observability layer.
        costs: The router for cost tracking.
        security: The guardrail engine.
        crew: The original CrewAI Crew object.
        last_workflow_id: The workflow ID from the most recent invocation.
    """

    def __init__(
        self,
        crew: Any,
        config: Pillar6Config | None = None,
    ) -> None:
        self._config = config or Pillar6Config()
        self.crew = crew
        self.traces = DefaultObservabilityLayer(config=self._config.observability)
        self.costs = DefaultRouter(config=self._config.router)
        self.security = DefaultGuardrailEngine(config=self._config.security)
        self.last_workflow_id: str = ""

    def kickoff(self, **kwargs: Any) -> Any:
        """Run the crew with Pillar6 instrumentation."""
        workflow_id = uuid.uuid4().hex[:12]
        self.last_workflow_id = workflow_id
        agent_id = self._config.agent.agent_id
        trace_ctx = self.traces.start_trace(workflow_id)

        # Trace each agent in the crew if available
        agents = getattr(self.crew, "agents", [])
        for i, agent in enumerate(agents):
            agent_name = getattr(agent, "role", None) or getattr(agent, "name", f"agent-{i}")
            self.traces.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="crewai.agent_registered",
                    agent_id=agent_id,
                    message=f"Crew agent: {agent_name}",
                    data={"agent_index": i, "agent_name": str(agent_name)},
                ),
            )

        self.traces.add_event(
            trace_ctx,
            TraceEvent(
                event_type="crewai.start",
                agent_id=agent_id,
                message=f"CrewAI kickoff started with {len(agents)} agents",
            ),
        )

        try:
            start_time = time.monotonic()
            result = self.crew.kickoff(**kwargs)
            duration_ms = (time.monotonic() - start_time) * 1000

            self.traces.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="crewai.complete",
                    agent_id=agent_id,
                    message=f"CrewAI kickoff completed in {duration_ms:.1f}ms",
                    data={"duration_ms": duration_ms},
                ),
            )

            return result

        except Exception as exc:
            self.traces.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="crewai.error",
                    agent_id=agent_id,
                    message=f"Error: {exc}",
                ),
            )
            raise
        finally:
            self.traces.end_trace(trace_ctx)


def wrap_crew(
    crew: Any,
    config: Pillar6Config | None = None,
) -> CrewWrapper:
    """Wrap a CrewAI Crew with Pillar6 production infrastructure.

    Args:
        crew: A CrewAI Crew or any object with a ``kickoff()`` method.
        config: Optional Pillar6 configuration.

    Returns:
        A :class:`CrewWrapper` with tracing, security, and cost tracking.

    Raises:
        ImportError: If CrewAI is not installed.
        TypeError: If the object doesn't look like a CrewAI Crew.
    """
    _check_crewai_available()

    if not hasattr(crew, "kickoff"):
        msg = f"Expected a CrewAI Crew with 'kickoff' method, got {type(crew).__name__}"
        raise TypeError(msg)

    return CrewWrapper(crew, config=config)
