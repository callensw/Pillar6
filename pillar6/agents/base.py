"""BaseAgent — the central agent class wiring all six pillars together.

The agent lifecycle follows:
    INIT -> CONTEXT LOAD -> PLAN -> EXECUTE -> OBSERVE -> EVALUATE -> RESPOND
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from pillar6.config.models import Pillar6Config
from pillar6.core.context import ContextManager, DefaultContextManager
from pillar6.core.eval import DefaultEvalSuite, EvalSuite
from pillar6.core.observability import DefaultObservabilityLayer, ObservabilityLayer
from pillar6.core.router import DefaultRouter, Router
from pillar6.core.security import DefaultGuardrailEngine, GuardrailEngine
from pillar6.core.tools import DefaultToolExecutor, DefaultToolRegistry, ToolExecutor, ToolRegistry
from pillar6.types import (
    LLMRequest,
    LLMResponse,
    Priority,
    TraceEvent,
)

if TYPE_CHECKING:
    from pillar6.adapters.base import LLMAdapter

logger = logging.getLogger(__name__)


class Pillar6Error(Exception):
    """Base exception for Pillar6 agent errors."""

    def __init__(self, message: str, agent_id: str = "", workflow_id: str = "") -> None:
        self.agent_id = agent_id
        self.workflow_id = workflow_id
        super().__init__(message)


class BaseAgent:
    """Core agent that orchestrates all six Pillar6 pillars.

    Can be used directly or subclassed for custom behaviour. When instantiated
    with only a config, it creates default implementations for every pillar.

    Args:
        config: Complete Pillar6 configuration.
        llm: Optional LLM adapter. If not provided, the agent can only be used
            with explicitly injected responses (useful for testing).
        context_manager: Optional custom context manager.
        tool_registry: Optional custom tool registry.
        tool_executor: Optional custom tool executor.
        guardrails: Optional custom guardrail engine.
        router: Optional custom router.
        observability: Optional custom observability layer.
        eval_suite: Optional custom evaluation suite.
    """

    def __init__(
        self,
        config: Pillar6Config | None = None,
        *,
        llm: LLMAdapter | None = None,
        context_manager: ContextManager | None = None,
        tool_registry: ToolRegistry | None = None,
        tool_executor: ToolExecutor | None = None,
        guardrails: GuardrailEngine | None = None,
        router: Router | None = None,
        observability: ObservabilityLayer | None = None,
        eval_suite: EvalSuite | None = None,
    ) -> None:
        self.config = config or Pillar6Config()
        self.llm = llm

        # Pillar 1: Context Management
        self.context_manager: ContextManager = context_manager or DefaultContextManager(
            self.config.context
        )

        # Pillar 2: Tool Orchestration
        self.tool_registry: ToolRegistry = tool_registry or DefaultToolRegistry()
        self.tool_executor: ToolExecutor = tool_executor or DefaultToolExecutor(
            self.tool_registry, self.config.tools
        )

        # Pillar 3: Security & Guardrails
        self.guardrails: GuardrailEngine = guardrails or DefaultGuardrailEngine(
            self.config.security
        )

        # Pillar 4: Efficiency & Routing
        self.router: Router = router or DefaultRouter(self.config.router)

        # Pillar 5: Observability
        self.observability: ObservabilityLayer = observability or DefaultObservabilityLayer(
            self.config.observability
        )

        # Pillar 6: Testing & Evaluation
        self.eval_suite: EvalSuite = eval_suite or DefaultEvalSuite(self.config.eval)

        self._agent_id: str = self.config.agent.agent_id

    @property
    def agent_id(self) -> str:
        """Return the unique agent identifier."""
        return self._agent_id

    async def run(self, task: str) -> str:
        """Execute the full agent lifecycle for a given task.

        Lifecycle: INIT -> CONTEXT LOAD -> SECURITY -> ROUTE -> EXECUTE -> OBSERVE -> RESPOND

        Args:
            task: The user task / instruction to process.

        Returns:
            The agent's final text response.

        Raises:
            Pillar6Error: If an unrecoverable error occurs during the lifecycle.
        """
        workflow_id = uuid.uuid4().hex[:12]
        trace_ctx = self.observability.start_trace(workflow_id)

        try:
            # --- INIT ---
            self.observability.add_event(
                trace_ctx, TraceEvent(event_type="init", message="Agent run started")
            )

            # --- SECURITY: input check ---
            validation = await self.guardrails.check_input(task, self._agent_id)
            if not validation.passed:
                self.observability.add_event(
                    trace_ctx,
                    TraceEvent(
                        event_type="guardrail_block",
                        message=f"Input blocked: {validation.violations}",
                    ),
                )
                return f"Input blocked: {'; '.join(validation.violations)}"

            # --- CONTEXT LOAD ---
            await self.context_manager.allocate(
                self._agent_id, self.config.context.default_token_budget
            )

            # Inject system prompt
            await self.context_manager.inject(
                self._agent_id, self.config.agent.system_prompt, Priority.SYSTEM
            )

            # Inject user task
            await self.context_manager.inject(self._agent_id, task, Priority.RECENT)
            self.observability.add_event(
                trace_ctx, TraceEvent(event_type="context_loaded", message="Context prepared")
            )

            # --- ROUTE ---
            llm_request = LLMRequest(
                messages=await self.context_manager.get_context(self._agent_id),
                temperature=self.config.agent.temperature,
                max_tokens=self.config.agent.max_tokens,
            )
            model = await self.router.route(llm_request)
            llm_request.model = model
            self.observability.add_event(
                trace_ctx,
                TraceEvent(event_type="routed", message=f"Routed to {model}"),
            )

            # --- BUDGET CHECK ---
            budget = await self.guardrails.check_budget(self._agent_id, llm_request.max_tokens)
            if not budget.allowed:
                self.observability.add_event(
                    trace_ctx,
                    TraceEvent(event_type="budget_exceeded", message=budget.message),
                )
                return f"Budget exceeded: {budget.message}"

            # --- EXECUTE (LLM call) ---
            if self.llm is None:
                self.observability.add_event(
                    trace_ctx,
                    TraceEvent(
                        event_type="no_llm",
                        message="No LLM adapter configured — returning echo",
                    ),
                )
                response = LLMResponse(content=f"[echo] {task}", model="none")
            else:
                response = await self.llm.complete(llm_request)

            self.observability.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="llm_response",
                    message=f"Received response from {response.model}",
                    data={"tokens": response.usage.total_tokens},
                ),
            )

            # --- HANDLE TOOL CALLS ---
            if response.tool_calls:
                for tc in response.tool_calls:
                    # Check permissions
                    allowed = await self.guardrails.check_permissions(self._agent_id, tc.tool_name)
                    if not allowed:
                        self.observability.add_event(
                            trace_ctx,
                            TraceEvent(
                                event_type="permission_denied",
                                message=f"Permission denied for tool {tc.tool_name}",
                            ),
                        )
                        continue

                    from pillar6.types import ExecutionContext

                    tool_result = await self.tool_executor.execute(
                        tc.tool_name,
                        tc.arguments,
                        ExecutionContext(
                            agent_id=self._agent_id,
                            workflow_id=workflow_id,
                            trace_id=trace_ctx.trace_id,
                        ),
                    )
                    self.observability.add_event(
                        trace_ctx,
                        TraceEvent(
                            event_type="tool_call",
                            message=(
                                f"Tool {tc.tool_name}: "
                                f"{'success' if tool_result.success else 'failed'}"
                            ),
                            data={
                                "tool_name": tc.tool_name,
                                "success": tool_result.success,
                                "duration_ms": tool_result.duration_ms,
                            },
                        ),
                    )

            # --- COST TRACKING ---
            await self.router.track_cost(self._agent_id, response.model, response.usage)

            # --- SECURITY: output check ---
            output_check = await self.guardrails.check_output(response.content)
            if not output_check.passed:
                self.observability.add_event(
                    trace_ctx,
                    TraceEvent(
                        event_type="output_blocked",
                        message=f"Output blocked: {output_check.violations}",
                    ),
                )
                return f"Output blocked: {'; '.join(output_check.violations)}"

            # --- AUDIT ---
            await self.guardrails.log_action(
                self._agent_id,
                "agent_run",
                {"task": task, "model": response.model, "tokens": response.usage.total_tokens},
            )

            # --- OBSERVE ---
            await self.observability.emit_metric(
                "agent.run.tokens",
                float(response.usage.total_tokens),
                {"agent_id": self._agent_id, "model": response.model},
            )

            return response.content

        except Exception as exc:
            # Log the error and re-raise as Pillar6Error
            self.observability.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="error",
                    message=f"Agent error: {exc}",
                    data={"error_type": type(exc).__name__},
                ),
            )
            if isinstance(exc, Pillar6Error):
                raise
            raise Pillar6Error(str(exc), agent_id=self._agent_id, workflow_id=workflow_id) from exc

        finally:
            self.observability.end_trace(trace_ctx)
