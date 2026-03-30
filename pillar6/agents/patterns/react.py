"""ReAct (Reasoning + Acting) agent pattern.

The agent follows a think-act-observe loop until it produces a final answer
or exhausts the maximum number of steps.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from pydantic import BaseModel, Field

from pillar6.agents.base import BaseAgent, Pillar6Error
from pillar6.types import (
    ExecutionContext,
    LLMRequest,
    Priority,
    TraceEvent,
)


class ReActConfig(BaseModel):
    """Configuration for the ReAct agent pattern."""

    max_steps: int = Field(default=10, ge=1)
    thought_prefix: str = "Thought:"
    action_prefix: str = "Action:"
    action_input_prefix: str = "Action Input:"
    observation_prefix: str = "Observation:"
    final_answer_prefix: str = "Final Answer:"


_REACT_SYSTEM_PROMPT = """\
You are a ReAct agent. Solve the user's task by reasoning step-by-step and using tools.

On each step, respond in EXACTLY one of these two formats:

Format A (use a tool):
Thought: <your reasoning about what to do next>
Action: <tool_name>
Action Input: <JSON object with arguments>

Format B (provide the final answer):
Thought: <your final reasoning>
Final Answer: <your answer>

Rules:
- Always start with a Thought.
- Only call one tool per step.
- After each tool result you will see an Observation with the result.
- When you have enough information, respond with Final Answer.
"""


class _ParsedResponse:
    """Internal representation of a parsed ReAct LLM response."""

    __slots__ = ("thought", "action", "action_input", "final_answer")

    def __init__(
        self,
        thought: str = "",
        action: str = "",
        action_input: dict[str, Any] | None = None,
        final_answer: str = "",
    ) -> None:
        self.thought = thought
        self.action = action
        self.action_input: dict[str, Any] = action_input or {}
        self.final_answer = final_answer

    @property
    def has_action(self) -> bool:
        """Return True if an action was parsed."""
        return bool(self.action)

    @property
    def has_final_answer(self) -> bool:
        """Return True if a final answer was parsed."""
        return bool(self.final_answer)


def parse_response(text: str) -> _ParsedResponse:
    """Parse a ReAct-formatted LLM response into structured parts.

    Uses regex to extract Thought, Action, Action Input, and Final Answer
    from the response text.

    Args:
        text: Raw LLM response text.

    Returns:
        A _ParsedResponse with extracted fields.
    """
    thought = ""
    action = ""
    action_input: dict[str, Any] = {}
    final_answer = ""

    # Extract thought
    thought_match = re.search(
        r"Thought:\s*(.+?)(?=\n(?:Action:|Final Answer:)|$)",
        text,
        re.DOTALL,
    )
    if thought_match:
        thought = thought_match.group(1).strip()

    # Extract final answer
    final_match = re.search(r"Final Answer:\s*(.+)", text, re.DOTALL)
    if final_match:
        final_answer = final_match.group(1).strip()
        return _ParsedResponse(thought=thought, final_answer=final_answer)

    # Extract action
    action_match = re.search(r"Action:\s*(\S+)", text)
    if action_match:
        action = action_match.group(1).strip()

    # Extract action input
    input_match = re.search(
        r"Action Input:\s*(.+?)(?=\n(?:Thought:|Action:|Final Answer:)|$)",
        text,
        re.DOTALL,
    )
    if input_match:
        raw = input_match.group(1).strip()
        try:
            parsed_json = json.loads(raw)
            if isinstance(parsed_json, dict):
                action_input = parsed_json
        except (json.JSONDecodeError, TypeError):
            action_input = {"input": raw}

    return _ParsedResponse(
        thought=thought,
        action=action,
        action_input=action_input,
    )


class ReActAgent(BaseAgent):
    """Agent that follows the ReAct (Reasoning + Acting) loop.

    Loop:
        1. THINK  -- LLM reasons about the current state
        2. ACT    -- Execute a tool call based on the reasoning
        3. OBSERVE -- Add the tool result to context
        4. Repeat until Final Answer or max_steps reached.

    Args:
        react_config: ReAct-specific configuration.
        **kwargs: Arguments forwarded to :class:`BaseAgent`.
    """

    def __init__(
        self,
        react_config: ReActConfig | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.react_config = react_config or ReActConfig()

    async def run(self, task: str) -> str:  # noqa: C901
        """Execute the ReAct loop for the given task.

        Args:
            task: The user's task / question.

        Returns:
            The final answer string, or the last thought if max_steps is
            reached without a Final Answer.

        Raises:
            Pillar6Error: On unrecoverable errors.
        """
        workflow_id = uuid.uuid4().hex[:12]
        trace_ctx = self.observability.start_trace(workflow_id)

        try:
            self.observability.add_event(
                trace_ctx,
                TraceEvent(event_type="react_start", message="ReAct loop started"),
            )

            # Security: input check
            validation = await self.guardrails.check_input(task, self.agent_id)
            if not validation.passed:
                self.observability.add_event(
                    trace_ctx,
                    TraceEvent(
                        event_type="guardrail_block",
                        message=f"Input blocked: {validation.violations}",
                    ),
                )
                return f"Input blocked: {'; '.join(validation.violations)}"

            # Context setup
            await self.context_manager.allocate(
                self.agent_id, self.config.context.default_token_budget
            )
            await self.context_manager.inject(self.agent_id, _REACT_SYSTEM_PROMPT, Priority.SYSTEM)
            await self.context_manager.inject(self.agent_id, task, Priority.RECENT)

            last_thought = ""
            for step in range(self.react_config.max_steps):
                # Build LLM request from current context
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

                parsed = parse_response(response.content)
                last_thought = parsed.thought or response.content

                # Trace the thought
                self.observability.add_event(
                    trace_ctx,
                    TraceEvent(
                        event_type="react_thought",
                        message=parsed.thought,
                        data={"step": step + 1},
                    ),
                )

                # --- Final Answer ---
                if parsed.has_final_answer:
                    self.observability.add_event(
                        trace_ctx,
                        TraceEvent(
                            event_type="react_final_answer",
                            message=parsed.final_answer,
                            data={"step": step + 1},
                        ),
                    )
                    await self.guardrails.log_action(
                        self.agent_id,
                        "react_run",
                        {"task": task, "steps": step + 1},
                    )
                    return parsed.final_answer

                # --- Action ---
                if parsed.has_action:
                    self.observability.add_event(
                        trace_ctx,
                        TraceEvent(
                            event_type="react_action",
                            message=f"Action: {parsed.action}",
                            data={
                                "step": step + 1,
                                "tool": parsed.action,
                                "args": parsed.action_input,
                            },
                        ),
                    )

                    # Permission check
                    allowed = await self.guardrails.check_permissions(self.agent_id, parsed.action)
                    if not allowed:
                        observation = f"Permission denied for tool '{parsed.action}'."
                        self.observability.add_event(
                            trace_ctx,
                            TraceEvent(
                                event_type="permission_denied",
                                message=observation,
                                data={"step": step + 1},
                            ),
                        )
                    else:
                        # Execute tool
                        try:
                            result = await self.tool_executor.execute(
                                parsed.action,
                                parsed.action_input,
                                ExecutionContext(
                                    agent_id=self.agent_id,
                                    workflow_id=workflow_id,
                                    trace_id=trace_ctx.trace_id,
                                ),
                            )
                            if result.success:
                                observation = str(result.output)
                            else:
                                observation = f"Error: {result.error}"
                        except Exception as tool_exc:
                            observation = f"Tool error: {tool_exc}"

                    # Inject observation into context
                    obs_text = f"Observation: {observation}"
                    await self.context_manager.inject(self.agent_id, obs_text, Priority.RECENT)
                    self.observability.add_event(
                        trace_ctx,
                        TraceEvent(
                            event_type="react_observation",
                            message=observation,
                            data={"step": step + 1},
                        ),
                    )

                    # Inject the assistant response into context for continuity
                    await self.context_manager.inject(
                        self.agent_id, response.content, Priority.RECENT
                    )
                else:
                    # No action and no final answer — inject response and continue
                    await self.context_manager.inject(
                        self.agent_id, response.content, Priority.RECENT
                    )

            # Max steps reached
            self.observability.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="react_max_steps",
                    message="Max steps reached without Final Answer",
                    data={"max_steps": self.react_config.max_steps},
                ),
            )
            await self.guardrails.log_action(
                self.agent_id,
                "react_run",
                {
                    "task": task,
                    "steps": self.react_config.max_steps,
                    "completed": False,
                },
            )
            return f"[max steps reached] {last_thought}"

        except Exception as exc:
            self.observability.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="error",
                    message=f"ReAct error: {exc}",
                    data={"error_type": type(exc).__name__},
                ),
            )
            if isinstance(exc, Pillar6Error):
                raise
            raise Pillar6Error(str(exc), agent_id=self.agent_id, workflow_id=workflow_id) from exc

        finally:
            self.observability.end_trace(trace_ctx)
