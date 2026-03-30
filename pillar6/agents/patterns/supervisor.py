"""Supervisor (Orchestrator) agent pattern.

A coordinator agent analyses a task, delegates sub-tasks to specialist
sub-agents, and synthesises their results into a final response.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any

from pydantic import BaseModel, Field

from pillar6.agents.base import BaseAgent, Pillar6Error
from pillar6.types import (
    LLMRequest,
    Priority,
    TraceEvent,
)


class SupervisorConfig(BaseModel):
    """Configuration for the Supervisor agent pattern."""

    execution_mode: str = Field(
        default="sequential",
        pattern="^(sequential|parallel)$",
    )
    max_specialists_per_task: int = Field(default=5, ge=1)


class _Specialist:
    """Internal record of a registered specialist agent."""

    __slots__ = ("name", "agent", "description")

    def __init__(self, name: str, agent: BaseAgent, description: str) -> None:
        self.name = name
        self.agent = agent
        self.description = description


_DELEGATION_SYSTEM_PROMPT = """\
You are a Supervisor agent. You coordinate specialist agents to accomplish tasks.

When given a task, analyse it and decide which specialists to delegate to.

Available specialists:
{specialists}

Respond with a JSON array of delegation objects. Each object has:
- "specialist": the specialist name
- "sub_task": the task to give that specialist

Example:
[
  {{"specialist": "researcher", "sub_task": "Find information about X"}},
  {{"specialist": "writer", "sub_task": "Write a summary of the findings"}}
]

Only output the JSON array. If no specialists are needed, output: []
"""

_SYNTHESIS_PROMPT = """\
You received results from the following specialists:

{results}

Synthesise these results into a single, coherent final response for the task:
{task}

Provide only the synthesised response.
"""


def _parse_delegations(text: str) -> list[dict[str, str]]:
    """Parse delegation JSON from the LLM response.

    Args:
        text: Raw LLM output expected to contain a JSON array.

    Returns:
        List of dicts with 'specialist' and 'sub_task' keys.
    """
    # Try to find a JSON array in the response
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
        if not isinstance(data, list):
            return []
        return [d for d in data if isinstance(d, dict) and "specialist" in d and "sub_task" in d]
    except (json.JSONDecodeError, TypeError):
        return []


class SupervisorAgent(BaseAgent):
    """Coordinator agent that delegates to specialist sub-agents.

    Lifecycle:
        1. ANALYSE   -- Understand the task and identify specialists.
        2. DELEGATE  -- Send sub-tasks to appropriate specialist agents.
        3. SYNTHESISE -- Combine specialist results into a final response.

    Args:
        supervisor_config: Supervisor-specific configuration.
        **kwargs: Arguments forwarded to :class:`BaseAgent`.
    """

    def __init__(
        self,
        supervisor_config: SupervisorConfig | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.supervisor_config = supervisor_config or SupervisorConfig()
        self._specialists: dict[str, _Specialist] = {}

    def register_specialist(self, name: str, agent: BaseAgent, description: str) -> None:
        """Register a specialist sub-agent.

        Args:
            name: Unique name for the specialist.
            agent: The specialist BaseAgent instance.
            description: Human-readable description of the specialist's expertise.
        """
        self._specialists[name] = _Specialist(name=name, agent=agent, description=description)

    def list_specialists(self) -> list[str]:
        """Return the names of all registered specialists."""
        return list(self._specialists.keys())

    async def run(self, task: str) -> str:  # noqa: C901
        """Execute the supervisor delegation loop.

        Args:
            task: The user's task.

        Returns:
            The synthesised response from specialist results.

        Raises:
            Pillar6Error: On unrecoverable errors.
        """
        workflow_id = uuid.uuid4().hex[:12]
        trace_ctx = self.observability.start_trace(workflow_id)

        try:
            self.observability.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="supervisor_start",
                    message="Supervisor started",
                ),
            )

            # Security: input check
            validation = await self.guardrails.check_input(task, self.agent_id)
            if not validation.passed:
                return f"Input blocked: {'; '.join(validation.violations)}"

            # Context setup
            await self.context_manager.allocate(
                self.agent_id, self.config.context.default_token_budget
            )

            # Build specialist descriptions for the system prompt
            spec_lines = "\n".join(
                f"- {s.name}: {s.description}" for s in self._specialists.values()
            )
            system_prompt = _DELEGATION_SYSTEM_PROMPT.format(specialists=spec_lines or "(none)")
            await self.context_manager.inject(self.agent_id, system_prompt, Priority.SYSTEM)
            await self.context_manager.inject(self.agent_id, task, Priority.RECENT)

            # --- ANALYSE & DELEGATE ---
            llm_request = LLMRequest(
                messages=await self.context_manager.get_context(self.agent_id),
                temperature=self.config.agent.temperature,
                max_tokens=self.config.agent.max_tokens,
            )
            model = await self.router.route(llm_request)
            llm_request.model = model

            if self.llm is None:
                return f"[echo] {task}"

            response = await self.llm.complete(llm_request)
            await self.router.track_cost(self.agent_id, response.model, response.usage)

            delegations = _parse_delegations(response.content)
            # Limit to max_specialists_per_task
            delegations = delegations[: self.supervisor_config.max_specialists_per_task]

            self.observability.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="delegation_plan",
                    message=f"Delegating to {len(delegations)} specialists",
                    data={"delegations": delegations},
                ),
            )

            if not delegations:
                # No delegation needed — return the LLM's direct response
                await self.guardrails.log_action(
                    self.agent_id,
                    "supervisor_run",
                    {"task": task, "delegations": 0},
                )
                return response.content

            # --- EXECUTE DELEGATIONS ---
            specialist_results: list[dict[str, str]] = []

            async def _run_specialist(
                deleg: dict[str, str],
            ) -> dict[str, str]:
                name = deleg["specialist"]
                sub_task = deleg["sub_task"]
                spec = self._specialists.get(name)
                if spec is None:
                    return {
                        "specialist": name,
                        "result": f"[error] Unknown specialist: {name}",
                    }
                try:
                    result = await spec.agent.run(sub_task)
                    return {"specialist": name, "result": result}
                except Exception as exc:
                    return {
                        "specialist": name,
                        "result": f"[error] {exc}",
                    }

            if self.supervisor_config.execution_mode == "parallel":
                specialist_results = list(
                    await asyncio.gather(*[_run_specialist(d) for d in delegations])
                )
            else:
                for deleg in delegations:
                    res = await _run_specialist(deleg)
                    specialist_results.append(res)

            for sr in specialist_results:
                self.observability.add_event(
                    trace_ctx,
                    TraceEvent(
                        event_type="specialist_result",
                        message=f"Specialist {sr['specialist']} returned",
                        data={
                            "specialist": sr["specialist"],
                            "result_preview": sr["result"][:200],
                        },
                    ),
                )

            # --- SYNTHESISE ---
            results_text = "\n\n".join(
                f"**{sr['specialist']}**: {sr['result']}" for sr in specialist_results
            )
            synthesis_prompt = _SYNTHESIS_PROMPT.format(results=results_text, task=task)
            await self.context_manager.inject(self.agent_id, synthesis_prompt, Priority.RECENT)
            synth_request = LLMRequest(
                messages=await self.context_manager.get_context(self.agent_id),
                temperature=self.config.agent.temperature,
                max_tokens=self.config.agent.max_tokens,
            )
            synth_model = await self.router.route(synth_request)
            synth_request.model = synth_model
            synth_response = await self.llm.complete(synth_request)
            await self.router.track_cost(self.agent_id, synth_response.model, synth_response.usage)

            self.observability.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="synthesis_complete",
                    message="Synthesis complete",
                ),
            )
            await self.guardrails.log_action(
                self.agent_id,
                "supervisor_run",
                {
                    "task": task,
                    "delegations": len(delegations),
                    "specialists": [d["specialist"] for d in delegations],
                },
            )

            return synth_response.content

        except Exception as exc:
            self.observability.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="error",
                    message=f"Supervisor error: {exc}",
                    data={"error_type": type(exc).__name__},
                ),
            )
            if isinstance(exc, Pillar6Error):
                raise
            raise Pillar6Error(str(exc), agent_id=self.agent_id, workflow_id=workflow_id) from exc

        finally:
            self.observability.end_trace(trace_ctx)
