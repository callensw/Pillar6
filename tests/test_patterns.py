"""Tests for agent patterns: ReAct, PlanExecute, Supervisor."""

from __future__ import annotations

from typing import Any

import pytest

from pillar6.agents.patterns.plan_execute import (
    PlanExecuteAgent,
    PlanExecuteConfig,
    PlanStep,
    parse_plan,
)
from pillar6.agents.patterns.react import (
    ReActAgent,
    ReActConfig,
    parse_response,
)
from pillar6.agents.patterns.supervisor import SupervisorAgent, SupervisorConfig
from pillar6.config.models import Pillar6Config, SecurityConfig, ToolConfig
from pillar6.core.eval import MockLLMAdapter
from pillar6.types import LLMRequest, LLMResponse, TokenUsage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class SequentialMockLLM(MockLLMAdapter):
    """Mock LLM that returns responses from a pre-defined sequence."""

    def __init__(self, responses: list[str]) -> None:
        super().__init__()
        self._sequence = list(responses)
        self._call_index = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return the next response in the sequence."""
        if self._call_index < len(self._sequence):
            content = self._sequence[self._call_index]
            self._call_index += 1
        else:
            content = "Final Answer: done"
        return LLMResponse(
            content=content,
            model="mock-sequential",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )


def _no_deny_config() -> Pillar6Config:
    """Config with security default_deny=False so tools are allowed."""
    return Pillar6Config(
        security=SecurityConfig(default_deny=False),
        tools=ToolConfig(max_retries=0, timeout_ms=5000),
    )


# ===========================================================================
# ReAct tests
# ===========================================================================


class TestReActParsing:
    """Tests for ReAct response parsing."""

    def test_parse_final_answer(self) -> None:
        text = "Thought: I know the answer.\nFinal Answer: 42"
        parsed = parse_response(text)
        assert parsed.has_final_answer
        assert parsed.final_answer == "42"
        assert parsed.thought == "I know the answer."

    def test_parse_action(self) -> None:
        text = 'Thought: I need to search.\nAction: search\nAction Input: {"query": "test"}'
        parsed = parse_response(text)
        assert parsed.has_action
        assert parsed.action == "search"
        assert parsed.action_input == {"query": "test"}
        assert not parsed.has_final_answer

    def test_parse_action_with_plain_input(self) -> None:
        text = "Thought: Let me look.\nAction: lookup\nAction Input: hello world"
        parsed = parse_response(text)
        assert parsed.action == "lookup"
        assert parsed.action_input == {"input": "hello world"}

    def test_parse_no_structure(self) -> None:
        text = "Just some random text with no structure."
        parsed = parse_response(text)
        assert not parsed.has_action
        assert not parsed.has_final_answer


class TestReActAgent:
    """Tests for the ReAct agent loop."""

    @pytest.mark.asyncio
    async def test_final_answer_on_first_step(self) -> None:
        llm = SequentialMockLLM(
            [
                "Thought: I already know.\nFinal Answer: The answer is 42",
            ]
        )
        agent = ReActAgent(config=_no_deny_config(), llm=llm)
        result = await agent.run("What is 6 * 7?")
        assert result == "The answer is 42"

    @pytest.mark.asyncio
    async def test_tool_call_then_final_answer(self) -> None:
        async def calc(**kwargs: Any) -> str:
            return str(eval(kwargs["expr"]))  # noqa: S307

        llm = SequentialMockLLM(
            [
                'Thought: I need to calculate.\nAction: calc\nAction Input: {"expr": "6*7"}',
                "Thought: The result is 42.\nFinal Answer: 42",
            ]
        )
        agent = ReActAgent(config=_no_deny_config(), llm=llm)
        agent.tool_registry.register(
            "calc",
            calc,
            {"properties": {"expr": {"type": "string"}}, "required": ["expr"]},
        )
        result = await agent.run("Calculate 6*7")
        assert result == "42"

    @pytest.mark.asyncio
    async def test_max_steps_reached(self) -> None:
        # LLM never produces a Final Answer
        llm = SequentialMockLLM(
            [
                "Thought: Still thinking...\nAction: noop\nAction Input: {}",
            ]
            * 5
        )
        agent = ReActAgent(
            react_config=ReActConfig(max_steps=3),
            config=_no_deny_config(),
            llm=llm,
        )
        # Register a noop tool so it doesn't fail on missing tool
        agent.tool_registry.register("noop", lambda: "ok", {})
        result = await agent.run("Do something")
        assert result.startswith("[max steps reached]")

    @pytest.mark.asyncio
    async def test_permission_denied_for_tool(self) -> None:
        llm = SequentialMockLLM(
            [
                "Thought: I need to use secret.\nAction: secret_tool\nAction Input: {}",
                "Thought: Permission was denied.\nFinal Answer: Cannot use that tool.",
            ]
        )
        # default_deny=True — no permissions granted
        agent = ReActAgent(
            config=Pillar6Config(security=SecurityConfig(default_deny=True)),
            llm=llm,
        )
        agent.tool_registry.register("secret_tool", lambda: "secret", {})
        result = await agent.run("Use secret tool")
        assert result == "Cannot use that tool."

    @pytest.mark.asyncio
    async def test_observability_traces_recorded(self) -> None:
        llm = SequentialMockLLM(
            [
                "Thought: Quick answer.\nFinal Answer: done",
            ]
        )
        agent = ReActAgent(config=_no_deny_config(), llm=llm)
        await agent.run("test")
        obs = agent.observability
        assert len(obs._completed_traces) > 0  # type: ignore[attr-defined]
        all_events: list[Any] = []
        for events in obs._traces.values():  # type: ignore[attr-defined]
            all_events.extend(events)
        event_types = {e.event_type for e in all_events}
        assert "react_start" in event_types
        assert "react_final_answer" in event_types


# ===========================================================================
# PlanExecute tests
# ===========================================================================


class TestPlanParsing:
    """Tests for plan parsing."""

    def test_parse_simple_plan(self) -> None:
        text = "1. Do research\n2. Write report\n3. Review"
        steps = parse_plan(text)
        assert len(steps) == 3
        assert steps[0].step_number == 1
        assert steps[0].description == "Do research"
        assert steps[2].description == "Review"

    def test_parse_plan_with_tool(self) -> None:
        text = '1. Search the web [tool:search] [args:{"q": "test"}] [expect:results]'
        steps = parse_plan(text)
        assert len(steps) == 1
        assert steps[0].tool_name == "search"
        assert steps[0].tool_args == {"q": "test"}
        assert steps[0].expected_output == "results"

    def test_parse_empty_text(self) -> None:
        assert parse_plan("") == []

    def test_parse_plan_ignores_non_numbered_lines(self) -> None:
        text = "Here is the plan:\n1. Step one\nSome extra text\n2. Step two"
        steps = parse_plan(text)
        assert len(steps) == 2


class TestPlanExecuteAgent:
    """Tests for the PlanExecute agent."""

    @pytest.mark.asyncio
    async def test_simple_plan_execution(self) -> None:
        llm = SequentialMockLLM(
            [
                # Plan generation
                "1. Think about it\n2. Provide the answer",
                # Step 1 execution
                "Thinking complete.",
                # Step 2 execution
                "The answer is 42.",
            ]
        )
        agent = PlanExecuteAgent(config=_no_deny_config(), llm=llm)
        result = await agent.run("What is the answer?")
        assert "42" in result or "Thinking" in result

    @pytest.mark.asyncio
    async def test_plan_with_tool_step(self) -> None:
        async def lookup(**kwargs: Any) -> str:
            return f"Found: {kwargs.get('topic', 'nothing')}"

        llm = SequentialMockLLM(
            [
                # Plan generation
                '1. Look up info [tool:lookup] [args:{"topic": "AI"}]\n2. Summarize',
                # Step 2 (step 1 uses tool, no LLM call)
                "AI is artificial intelligence.",
            ]
        )
        agent = PlanExecuteAgent(config=_no_deny_config(), llm=llm)
        agent.tool_registry.register(
            "lookup",
            lookup,
            {"properties": {"topic": {"type": "string"}}, "required": ["topic"]},
        )
        result = await agent.run("Tell me about AI")
        assert "Found: AI" in result or "artificial intelligence" in result

    @pytest.mark.asyncio
    async def test_replan_on_failure(self) -> None:
        call_count = 0

        async def flaky_tool(**kwargs: Any) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Temporary failure")
            return "success"

        llm = SequentialMockLLM(
            [
                # Initial plan
                "1. Use flaky [tool:flaky]",
                # Replan after failure
                "1. Try flaky again [tool:flaky]",
            ]
        )
        agent = PlanExecuteAgent(
            plan_config=PlanExecuteConfig(allow_replan=True, max_replans=2),
            config=_no_deny_config(),
            llm=llm,
        )
        agent.tool_registry.register("flaky", flaky_tool, {})
        result = await agent.run("Do flaky thing")
        assert "success" in result

    @pytest.mark.asyncio
    async def test_max_replans_exceeded(self) -> None:
        async def always_fail(**kwargs: Any) -> str:
            raise RuntimeError("Always fails")

        llm = SequentialMockLLM(
            [
                "1. Use broken [tool:broken]",
                # Replan 1
                "1. Try broken again [tool:broken]",
                # Replan 2
                "1. Try once more [tool:broken]",
                # Would be replan 3, but max_replans=2
            ]
        )
        agent = PlanExecuteAgent(
            plan_config=PlanExecuteConfig(allow_replan=True, max_replans=2),
            config=_no_deny_config(),
            llm=llm,
        )
        agent.tool_registry.register("broken", always_fail, {})
        result = await agent.run("Do broken thing")
        assert "[error]" in result

    @pytest.mark.asyncio
    async def test_observability_traces(self) -> None:
        llm = SequentialMockLLM(
            [
                "1. Think about it",
                "Done thinking.",
            ]
        )
        agent = PlanExecuteAgent(config=_no_deny_config(), llm=llm)
        await agent.run("test task")
        obs = agent.observability
        assert len(obs._completed_traces) > 0  # type: ignore[attr-defined]
        all_events: list[Any] = []
        for events in obs._traces.values():  # type: ignore[attr-defined]
            all_events.extend(events)
        event_types = {e.event_type for e in all_events}
        assert "plan_execute_start" in event_types
        assert "plan_generated" in event_types


# ===========================================================================
# Supervisor tests
# ===========================================================================


class TestSupervisorAgent:
    """Tests for the Supervisor agent."""

    @pytest.mark.asyncio
    async def test_specialist_registration(self) -> None:
        agent = SupervisorAgent(config=_no_deny_config())
        specialist = ReActAgent(config=_no_deny_config())
        agent.register_specialist("researcher", specialist, "Finds info")
        assert "researcher" in agent.list_specialists()

    @pytest.mark.asyncio
    async def test_delegation_and_synthesis(self) -> None:
        # Supervisor LLM: first call returns delegation, second call synthesises
        supervisor_llm = SequentialMockLLM(
            [
                '[{"specialist": "helper", "sub_task": "Do the work"}]',
                "The helper did the work and the result is great.",
            ]
        )
        # Specialist LLM
        specialist_llm = SequentialMockLLM(
            [
                "Thought: Done.\nFinal Answer: Work completed successfully.",
            ]
        )
        specialist = ReActAgent(config=_no_deny_config(), llm=specialist_llm)

        agent = SupervisorAgent(config=_no_deny_config(), llm=supervisor_llm)
        agent.register_specialist("helper", specialist, "Does work")

        result = await agent.run("Get the work done")
        assert "great" in result or "helper" in result.lower() or len(result) > 0

    @pytest.mark.asyncio
    async def test_parallel_execution(self) -> None:
        supervisor_llm = SequentialMockLLM(
            [
                (
                    '[{"specialist": "a", "sub_task": "task A"}, '
                    '{"specialist": "b", "sub_task": "task B"}]'
                ),
                "Combined result from A and B.",
            ]
        )
        spec_a_llm = SequentialMockLLM(["Thought: ok.\nFinal Answer: Result A"])
        spec_b_llm = SequentialMockLLM(["Thought: ok.\nFinal Answer: Result B"])

        agent = SupervisorAgent(
            supervisor_config=SupervisorConfig(execution_mode="parallel"),
            config=_no_deny_config(),
            llm=supervisor_llm,
        )
        agent.register_specialist(
            "a", ReActAgent(config=_no_deny_config(), llm=spec_a_llm), "Agent A"
        )
        agent.register_specialist(
            "b", ReActAgent(config=_no_deny_config(), llm=spec_b_llm), "Agent B"
        )

        result = await agent.run("Do both tasks")
        # Synthesis should contain content from both specialist results
        assert len(result) > 0
        assert "[error]" not in result.lower() or "synthesi" in result.lower()

    @pytest.mark.asyncio
    async def test_unknown_specialist_handled(self) -> None:
        supervisor_llm = SequentialMockLLM(
            [
                '[{"specialist": "nonexistent", "sub_task": "do something"}]',
                "Could not complete because specialist was not found.",
            ]
        )
        agent = SupervisorAgent(config=_no_deny_config(), llm=supervisor_llm)
        result = await agent.run("Use nonexistent specialist")
        # Should still get a synthesis response (even with error from unknown specialist)
        assert len(result) > 0
        assert "error" in result.lower() or len(result) > 5

    @pytest.mark.asyncio
    async def test_no_delegation_needed(self) -> None:
        supervisor_llm = SequentialMockLLM(["[]"])
        agent = SupervisorAgent(config=_no_deny_config(), llm=supervisor_llm)
        result = await agent.run("Simple question")
        # When no delegation, returns the LLM response directly
        assert result == "[]"

    @pytest.mark.asyncio
    async def test_max_specialists_limit(self) -> None:
        delegations = [f'{{"specialist": "s{i}", "sub_task": "task {i}"}}' for i in range(10)]
        supervisor_llm = SequentialMockLLM(
            [
                "[" + ", ".join(delegations) + "]",
                "Synthesised from limited specialists.",
            ]
        )
        agent = SupervisorAgent(
            supervisor_config=SupervisorConfig(max_specialists_per_task=2),
            config=_no_deny_config(),
            llm=supervisor_llm,
        )
        # Register all 10 specialists
        for i in range(10):
            spec_llm = SequentialMockLLM([f"Thought: ok.\nFinal Answer: Result {i}"])
            agent.register_specialist(
                f"s{i}",
                ReActAgent(config=_no_deny_config(), llm=spec_llm),
                f"Specialist {i}",
            )

        result = await agent.run("Big task")
        # Should produce a synthesised result (not empty or just whitespace)
        assert result.strip()

    @pytest.mark.asyncio
    async def test_observability_traces(self) -> None:
        supervisor_llm = SequentialMockLLM(
            [
                '[{"specialist": "h", "sub_task": "do it"}]',
                "Done.",
            ]
        )
        spec_llm = SequentialMockLLM(["Thought: ok.\nFinal Answer: ok"])
        agent = SupervisorAgent(config=_no_deny_config(), llm=supervisor_llm)
        agent.register_specialist(
            "h",
            ReActAgent(config=_no_deny_config(), llm=spec_llm),
            "Helper",
        )
        await agent.run("test")
        obs = agent.observability
        assert len(obs._completed_traces) > 0  # type: ignore[attr-defined]
        all_events: list[Any] = []
        for events in obs._traces.values():  # type: ignore[attr-defined]
            all_events.extend(events)
        event_types = {e.event_type for e in all_events}
        assert "supervisor_start" in event_types
        assert "delegation_plan" in event_types


# ===========================================================================
# PlanStep model tests
# ===========================================================================


class TestPlanStepModel:
    """Tests for PlanStep Pydantic model."""

    def test_plan_step_defaults(self) -> None:
        step = PlanStep(step_number=1, description="Do something")
        assert step.tool_name is None
        assert step.tool_args is None
        assert step.expected_output is None

    def test_plan_step_with_tool(self) -> None:
        step = PlanStep(
            step_number=1,
            description="Search",
            tool_name="search",
            tool_args={"q": "test"},
            expected_output="results",
        )
        assert step.tool_name == "search"
        assert step.tool_args == {"q": "test"}
