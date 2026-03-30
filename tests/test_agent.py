"""Tests for the BaseAgent."""

from __future__ import annotations

import pytest

from pillar6.agents.base import BaseAgent, Pillar6Error
from pillar6.config.models import AgentConfig, Pillar6Config, SecurityConfig


@pytest.fixture
def agent() -> BaseAgent:
    return BaseAgent(config=Pillar6Config())


async def test_agent_init_defaults(agent: BaseAgent) -> None:
    assert agent.agent_id == "default"
    assert agent.llm is None
    assert agent.config is not None


async def test_agent_run_echo_mode(agent: BaseAgent) -> None:
    result = await agent.run("Hello")
    assert "[echo] Hello" in result


async def test_agent_custom_config() -> None:
    config = Pillar6Config(agent=AgentConfig(agent_id="custom", name="Custom Agent"))
    agent = BaseAgent(config=config)
    assert agent.agent_id == "custom"


async def test_agent_input_blocked() -> None:
    config = Pillar6Config(security=SecurityConfig(max_input_length=5, blocked_patterns=[]))
    agent = BaseAgent(config=config)
    result = await agent.run("This is way too long")
    assert "blocked" in result.lower()


async def test_agent_run_traces_lifecycle(agent: BaseAgent) -> None:
    await agent.run("Test task")
    from pillar6.core.observability import DefaultObservabilityLayer

    obs = agent.observability
    assert isinstance(obs, DefaultObservabilityLayer)
    assert len(obs._traces) > 0


async def test_agent_run_tracks_cost(agent: BaseAgent) -> None:
    await agent.run("Cost tracking test")
    summary = await agent.router.get_cost_summary(agent.agent_id)
    assert summary.total_tokens >= 0


async def test_agent_run_audits_action(agent: BaseAgent) -> None:
    await agent.run("Audit test")
    from pillar6.core.security import DefaultGuardrailEngine

    guardrails = agent.guardrails
    assert isinstance(guardrails, DefaultGuardrailEngine)
    log = guardrails.get_audit_log(agent.agent_id)
    assert len(log) >= 1
    assert log[-1].action == "agent_run"


async def test_agent_with_mock_llm() -> None:
    from pillar6.core.eval import MockLLMAdapter

    config = Pillar6Config()
    llm = MockLLMAdapter(responses={"hello": "world"}, default_response="default")
    agent = BaseAgent(config=config, llm=llm)
    result = await agent.run("hello")
    assert result == "world"


async def test_agent_error_handling() -> None:
    """Agent should wrap unexpected errors in Pillar6Error."""
    from unittest.mock import AsyncMock

    from pillar6.core.eval import MockLLMAdapter

    config = Pillar6Config()
    llm = MockLLMAdapter()
    agent = BaseAgent(config=config, llm=llm)

    # Break the router to cause an error
    agent.router.route = AsyncMock(side_effect=RuntimeError("routing failed"))  # type: ignore[method-assign]

    with pytest.raises(Pillar6Error, match="routing failed"):
        await agent.run("test")
