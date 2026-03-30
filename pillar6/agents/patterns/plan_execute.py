"""Plan-Execute agent pattern.

The agent creates a plan upfront, then executes each step sequentially.
If a step fails and replanning is enabled, it generates a revised plan.
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


class PlanStep(BaseModel):
    """A single step in an execution plan."""

    step_number: int
    description: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    expected_output: str | None = None


class PlanExecuteConfig(BaseModel):
    """Configuration for the Plan-Execute agent pattern."""

    max_replans: int = Field(default=2, ge=0)
    allow_replan: bool = True


_PLAN_SYSTEM_PROMPT = """\
You are a planning agent. Given a task, produce a step-by-step plan.

Respond with a numbered list of steps. Each step should be on its own line with this format:
<step_number>. <description> [tool:<tool_name>] [args:<JSON args>] [expect:<expected output>]

The [tool:...], [args:...], and [expect:...] parts are optional.

Example:
1. Look up the weather [tool:weather] [args:{"city": "London"}] [expect:temperature and conditions]
2. Summarize the findings [expect:a short paragraph]
3. Format the final response

Only output the plan, nothing else.
"""

_REPLAN_PROMPT_TEMPLATE = """\
The original plan partially failed. Here is what happened:

Completed steps:
{completed}

Failed step:
{failed}

Error: {error}

Remaining steps from original plan:
{remaining}

Please produce a REVISED plan (numbered starting from {next_step}) to complete \
the task given what has been accomplished and what went wrong. Same format as before.
"""

_STEP_PROMPT_TEMPLATE = """\
Execute the following step and provide the result:

Step {step_number}: {description}

Context from previous steps:
{context}

Provide only the result of this step.
"""


def parse_plan(text: str) -> list[PlanStep]:
    """Parse a numbered plan from LLM output into structured PlanStep objects.

    Args:
        text: Raw LLM response containing a numbered plan.

    Returns:
        List of PlanStep objects.
    """
    steps: list[PlanStep] = []
    # Match lines starting with a number and a period/parenthesis
    pattern = re.compile(r"(\d+)[.)]\s*(.+)")

    for line in text.strip().splitlines():
        line = line.strip()
        match = pattern.match(line)
        if not match:
            continue

        step_num = int(match.group(1))
        rest = match.group(2)

        # Extract optional [tool:...], [args:...], [expect:...]
        tool_name: str | None = None
        tool_args: dict[str, Any] | None = None
        expected_output: str | None = None

        tool_match = re.search(r"\[tool:\s*(\S+?)\]", rest)
        if tool_match:
            tool_name = tool_match.group(1)
            rest = rest[: tool_match.start()] + rest[tool_match.end() :]

        args_match = re.search(r"\[args:\s*(\{.*?\})\]", rest)
        if args_match:
            try:
                tool_args = json.loads(args_match.group(1))
            except json.JSONDecodeError:
                tool_args = None
            rest = rest[: args_match.start()] + rest[args_match.end() :]

        expect_match = re.search(r"\[expect:\s*(.+?)\]", rest)
        if expect_match:
            expected_output = expect_match.group(1).strip()
            rest = rest[: expect_match.start()] + rest[expect_match.end() :]

        description = rest.strip()

        steps.append(
            PlanStep(
                step_number=step_num,
                description=description,
                tool_name=tool_name,
                tool_args=tool_args,
                expected_output=expected_output,
            )
        )

    return steps


class PlanExecuteAgent(BaseAgent):
    """Agent that plans before executing.

    Lifecycle:
        1. PLAN    -- Generate a step-by-step plan for the task.
        2. EXECUTE -- Execute each step sequentially.
        3. REPLAN  -- If a step fails, generate a revised plan incorporating
                      what was learned.

    Args:
        plan_config: Plan-Execute-specific configuration.
        **kwargs: Arguments forwarded to :class:`BaseAgent`.
    """

    def __init__(
        self,
        plan_config: PlanExecuteConfig | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.plan_config = plan_config or PlanExecuteConfig()

    async def _call_llm(self, extra_prompt: str) -> str:
        """Send a prompt to the LLM using the current context.

        Injects *extra_prompt* into context, calls the LLM, and returns
        the response content.
        """
        await self.context_manager.inject(self.agent_id, extra_prompt, Priority.RECENT)
        llm_request = LLMRequest(
            messages=await self.context_manager.get_context(self.agent_id),
            temperature=self.config.agent.temperature,
            max_tokens=self.config.agent.max_tokens,
        )
        model = await self.router.route(llm_request)
        llm_request.model = model

        if self.llm is None:
            return f"[echo] {extra_prompt}"

        response = await self.llm.complete(llm_request)
        await self.router.track_cost(self.agent_id, response.model, response.usage)
        return response.content

    async def run(self, task: str) -> str:  # noqa: C901
        """Execute the plan-execute loop for the given task.

        Args:
            task: The user's task.

        Returns:
            The final synthesised response, or partial results on failure.

        Raises:
            Pillar6Error: On unrecoverable errors.
        """
        workflow_id = uuid.uuid4().hex[:12]
        trace_ctx = self.observability.start_trace(workflow_id)

        try:
            self.observability.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="plan_execute_start",
                    message="Plan-Execute started",
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
            await self.context_manager.inject(self.agent_id, _PLAN_SYSTEM_PROMPT, Priority.SYSTEM)
            await self.context_manager.inject(self.agent_id, task, Priority.RECENT)

            # --- PLAN ---
            plan_text = await self._call_llm("Generate a plan for the following task:\n" + task)
            plan = parse_plan(plan_text)
            self.observability.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="plan_generated",
                    message=f"Generated plan with {len(plan)} steps",
                    data={"steps": len(plan), "plan_text": plan_text},
                ),
            )

            if not plan:
                # LLM didn't produce a parseable plan — return raw text
                return plan_text

            # --- EXECUTE ---
            step_results: list[str] = []
            replans = 0

            i = 0
            while i < len(plan):
                step = plan[i]
                self.observability.add_event(
                    trace_ctx,
                    TraceEvent(
                        event_type="step_start",
                        message=f"Step {step.step_number}: {step.description}",
                        data={"step_number": step.step_number},
                    ),
                )

                try:
                    if step.tool_name:
                        # Execute tool
                        allowed = await self.guardrails.check_permissions(
                            self.agent_id, step.tool_name
                        )
                        if not allowed:
                            raise PermissionError(f"Permission denied for tool '{step.tool_name}'")

                        result = await self.tool_executor.execute(
                            step.tool_name,
                            step.tool_args or {},
                            ExecutionContext(
                                agent_id=self.agent_id,
                                workflow_id=workflow_id,
                                trace_id=trace_ctx.trace_id,
                            ),
                        )
                        if result.success:
                            step_output = str(result.output)
                        else:
                            raise RuntimeError(f"Tool failed: {result.error}")
                    else:
                        # No tool — ask LLM to complete the step
                        context_summary = "\n".join(
                            f"Step {j + 1}: {r}" for j, r in enumerate(step_results)
                        )
                        step_output = await self._call_llm(
                            _STEP_PROMPT_TEMPLATE.format(
                                step_number=step.step_number,
                                description=step.description,
                                context=context_summary or "(none)",
                            )
                        )

                    step_results.append(step_output)
                    self.observability.add_event(
                        trace_ctx,
                        TraceEvent(
                            event_type="step_complete",
                            message=f"Step {step.step_number} completed",
                            data={
                                "step_number": step.step_number,
                                "output_preview": step_output[:200],
                            },
                        ),
                    )
                    i += 1

                except Exception as step_exc:
                    self.observability.add_event(
                        trace_ctx,
                        TraceEvent(
                            event_type="step_failed",
                            message=f"Step {step.step_number} failed: {step_exc}",
                            data={"step_number": step.step_number},
                        ),
                    )

                    if not self.plan_config.allow_replan or replans >= self.plan_config.max_replans:
                        # Cannot replan — return partial results
                        partial = "\n".join(step_results) if step_results else ""
                        error_msg = f"Step {step.step_number} failed: {step_exc}"
                        return f"{partial}\n[error] {error_msg}".strip()

                    # --- REPLAN ---
                    replans += 1
                    completed_summary = "\n".join(
                        f"Step {j + 1}: {r}" for j, r in enumerate(step_results)
                    )
                    remaining_summary = "\n".join(
                        f"Step {s.step_number}: {s.description}" for s in plan[i + 1 :]
                    )
                    replan_prompt = _REPLAN_PROMPT_TEMPLATE.format(
                        completed=completed_summary or "(none)",
                        failed=f"Step {step.step_number}: {step.description}",
                        error=str(step_exc),
                        remaining=remaining_summary or "(none)",
                        next_step=len(step_results) + 1,
                    )
                    new_plan_text = await self._call_llm(replan_prompt)
                    new_plan = parse_plan(new_plan_text)
                    self.observability.add_event(
                        trace_ctx,
                        TraceEvent(
                            event_type="replan",
                            message=f"Replan #{replans}: {len(new_plan)} new steps",
                            data={"replan_number": replans},
                        ),
                    )

                    if new_plan:
                        plan = new_plan
                        i = 0  # restart from first step of new plan
                    else:
                        # Replan produced no parseable steps
                        partial = "\n".join(step_results) if step_results else ""
                        return f"{partial}\n[replan failed]".strip()

            # All steps completed — synthesize
            await self.guardrails.log_action(
                self.agent_id,
                "plan_execute_run",
                {
                    "task": task,
                    "total_steps": len(plan),
                    "replans": replans,
                },
            )

            if len(step_results) == 1:
                return step_results[0]
            return "\n".join(step_results)

        except Exception as exc:
            self.observability.add_event(
                trace_ctx,
                TraceEvent(
                    event_type="error",
                    message=f"PlanExecute error: {exc}",
                    data={"error_type": type(exc).__name__},
                ),
            )
            if isinstance(exc, Pillar6Error):
                raise
            raise Pillar6Error(str(exc), agent_id=self.agent_id, workflow_id=workflow_id) from exc

        finally:
            self.observability.end_trace(trace_ctx)
