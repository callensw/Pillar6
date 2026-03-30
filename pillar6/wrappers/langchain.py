"""Wrap a LangChain chain or agent with Pillar6 production infrastructure.

Usage::

    from pillar6.wrappers.langchain import wrap_langchain
    from langchain.chains import LLMChain

    chain = LLMChain(llm=my_llm, prompt=my_prompt)
    production_chain = wrap_langchain(chain)
    result = await production_chain.ainvoke({"query": "..."})

LangChain is NOT a dependency of Pillar6.  This module uses duck typing
to detect LangChain objects and will raise a clear error if LangChain is
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


def _check_langchain_available() -> None:
    """Raise a helpful error if LangChain is not installed."""
    try:
        import langchain  # noqa: F401
    except ImportError:
        msg = "LangChain is not installed. Install it with: pip install langchain"
        raise ImportError(msg) from None


class LangChainWrapper:
    """A LangChain chain/agent wrapped with Pillar6 production infrastructure.

    Attributes:
        traces: The observability layer.
        costs: The router for cost tracking.
        security: The guardrail engine.
        chain: The original LangChain object.
        last_workflow_id: The workflow ID from the most recent invocation.
    """

    def __init__(
        self,
        chain: Any,
        config: Pillar6Config | None = None,
    ) -> None:
        self._config = config or Pillar6Config()
        self.chain = chain
        self.traces = DefaultObservabilityLayer(config=self._config.observability)
        self.costs = DefaultRouter(config=self._config.router)
        self.security = DefaultGuardrailEngine(config=self._config.security)
        self.last_workflow_id: str = ""

    async def ainvoke(self, input_data: dict[str, Any], **kwargs: Any) -> Any:
        """Invoke the chain asynchronously with Pillar6 instrumentation."""
        workflow_id = uuid.uuid4().hex[:12]
        self.last_workflow_id = workflow_id
        agent_id = self._config.agent.agent_id
        trace_ctx = self.traces.start_trace(workflow_id)

        self.traces.add_event(
            trace_ctx,
            TraceEvent(
                event_type="langchain.start",
                agent_id=agent_id,
                message="LangChain invocation started",
                data={"input_keys": list(input_data.keys())},
            ),
        )

        try:
            # Security check on input values
            for value in input_data.values():
                if isinstance(value, str):
                    validation = await self.security.check_input(value, agent_id)
                    if not validation.passed:
                        violations = "; ".join(validation.violations)
                        msg = f"Input validation failed: {violations}"
                        raise ValueError(msg)

            start_time = time.monotonic()

            if hasattr(self.chain, "ainvoke"):
                result = await self.chain.ainvoke(input_data, **kwargs)
            elif hasattr(self.chain, "invoke"):
                result = self.chain.invoke(input_data, **kwargs)
            else:
                msg = "LangChain object has neither 'ainvoke' nor 'invoke' method"
                raise TypeError(msg)

            duration_ms = (time.monotonic() - start_time) * 1000

            await self.traces.emit_metric(
                "langchain.duration_ms",
                duration_ms,
                tags={"agent_id": agent_id, "workflow_id": workflow_id},
            )

            self.traces.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="langchain.complete",
                    agent_id=agent_id,
                    message=f"LangChain invocation completed in {duration_ms:.1f}ms",
                    data={"duration_ms": duration_ms},
                ),
            )

            return result

        except Exception as exc:
            self.traces.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="langchain.error",
                    agent_id=agent_id,
                    message=f"Error: {exc}",
                ),
            )
            raise
        finally:
            self.traces.end_trace(trace_ctx)

    def invoke(self, input_data: dict[str, Any], **kwargs: Any) -> Any:
        """Synchronous invoke — delegates to ainvoke via asyncio."""
        import asyncio

        return asyncio.run(self.ainvoke(input_data, **kwargs))


def wrap_langchain(
    chain: Any,
    config: Pillar6Config | None = None,
) -> LangChainWrapper:
    """Wrap a LangChain chain or agent with Pillar6 production infrastructure.

    Args:
        chain: A LangChain chain, agent, or any object with ``invoke()``
            or ``ainvoke()`` methods.
        config: Optional Pillar6 configuration.

    Returns:
        A :class:`LangChainWrapper` with tracing, security, and cost tracking.

    Raises:
        ImportError: If LangChain is not installed.
        TypeError: If the object doesn't look like a LangChain chain.
    """
    _check_langchain_available()

    if not (hasattr(chain, "invoke") or hasattr(chain, "ainvoke")):
        msg = (
            f"Expected a LangChain chain or agent with 'invoke' or 'ainvoke' "
            f"method, got {type(chain).__name__}"
        )
        raise TypeError(msg)

    return LangChainWrapper(chain, config=config)
