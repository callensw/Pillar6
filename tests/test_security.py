"""Tests for the Security & Guardrails pillar."""

from __future__ import annotations

import pytest

from pillar6.config.models import SecurityConfig
from pillar6.core.security import DefaultGuardrailEngine


@pytest.fixture
def engine() -> DefaultGuardrailEngine:
    return DefaultGuardrailEngine(
        SecurityConfig(
            max_input_length=100,
            blocked_patterns=[r"DROP\s+TABLE"],
            allowed_tools=["safe_tool"],
            token_budget_per_agent=10_000,
        )
    )


async def test_check_input_valid(engine: DefaultGuardrailEngine) -> None:
    result = await engine.check_input("Hello world", "agent-1")
    assert result.passed is True


async def test_check_input_too_long(engine: DefaultGuardrailEngine) -> None:
    result = await engine.check_input("x" * 200, "agent-1")
    assert result.passed is False
    assert any("length" in v.lower() for v in result.violations)


async def test_check_input_blocked_pattern(engine: DefaultGuardrailEngine) -> None:
    result = await engine.check_input("DROP TABLE users", "agent-1")
    assert result.passed is False


async def test_check_output_valid(engine: DefaultGuardrailEngine) -> None:
    result = await engine.check_output("some output")
    assert result.passed is True


async def test_check_output_none(engine: DefaultGuardrailEngine) -> None:
    result = await engine.check_output(None)
    assert result.passed is False


async def test_check_permissions_allowed(engine: DefaultGuardrailEngine) -> None:
    assert await engine.check_permissions("agent-1", "safe_tool") is True


async def test_check_permissions_denied(engine: DefaultGuardrailEngine) -> None:
    assert await engine.check_permissions("agent-1", "dangerous_tool") is False


async def test_check_budget_within_limit(engine: DefaultGuardrailEngine) -> None:
    result = await engine.check_budget("agent-1", 500)
    assert result.allowed is True
    assert result.remaining_tokens == 10_000


async def test_check_budget_exceeded(engine: DefaultGuardrailEngine) -> None:
    engine.record_usage("agent-1", 9_900)
    result = await engine.check_budget("agent-1", 500)
    assert result.allowed is False


async def test_log_action(engine: DefaultGuardrailEngine) -> None:
    await engine.log_action("agent-1", "test_action", {"key": "value"})
    assert len(engine._audit_log) == 1
    assert engine._audit_log[0]["action"] == "test_action"


async def test_validation_disabled() -> None:
    engine = DefaultGuardrailEngine(
        SecurityConfig(enable_input_validation=False, enable_output_validation=False)
    )
    assert (await engine.check_input("x" * 999_999, "a")).passed is True
    assert (await engine.check_output(None)).passed is True
