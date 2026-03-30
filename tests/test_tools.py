"""Tests for the Tool Orchestration pillar."""

from __future__ import annotations

import asyncio

import pytest

from pillar6.config.models import ToolConfig
from pillar6.core.tools import DefaultToolExecutor, DefaultToolRegistry
from pillar6.types import CircuitBreakerState, ExecutionContext, ToolCall

# --- Helpers ---


async def async_add(a: int, b: int) -> int:
    return a + b


def sync_add(a: int, b: int) -> int:
    return a + b


async def failing_tool() -> None:
    raise RuntimeError("boom")


async def slow_tool() -> str:
    await asyncio.sleep(5)
    return "done"


SCHEMA_ADD: dict[str, object] = {
    "type": "object",
    "properties": {
        "a": {"type": "integer"},
        "b": {"type": "integer"},
    },
    "required": ["a", "b"],
}


# --- Registry tests ---


def test_register_and_get() -> None:
    registry = DefaultToolRegistry()
    registry.register("add", async_add, SCHEMA_ADD)
    tool = registry.get_tool("add")
    assert tool.name == "add"


def test_register_non_callable_raises() -> None:
    registry = DefaultToolRegistry()
    with pytest.raises(TypeError, match="not callable"):
        registry.register("bad", "not_a_function", {})  # type: ignore[arg-type]


def test_get_unknown_tool_raises() -> None:
    registry = DefaultToolRegistry()
    with pytest.raises(KeyError):
        registry.get_tool("nope")


def test_list_tools() -> None:
    registry = DefaultToolRegistry()
    registry.register("a", async_add, {})
    registry.register("b", sync_add, {})
    assert sorted(registry.list_tools()) == ["a", "b"]


async def test_health_check() -> None:
    registry = DefaultToolRegistry()
    registry.register("add", async_add, {})
    health = await registry.health_check()
    assert "add" in health
    assert health["add"].healthy is True
    assert health["add"].circuit_breaker_state == CircuitBreakerState.CLOSED


# --- Executor tests ---


async def test_execute_async_tool() -> None:
    registry = DefaultToolRegistry()
    registry.register("add", async_add, SCHEMA_ADD)
    executor = DefaultToolExecutor(registry, ToolConfig(max_retries=0))
    result = await executor.execute("add", {"a": 1, "b": 2}, ExecutionContext())
    assert result.success is True
    assert result.output == 3
    assert result.duration_ms > 0


async def test_execute_sync_tool() -> None:
    registry = DefaultToolRegistry()
    registry.register("add", sync_add, SCHEMA_ADD)
    executor = DefaultToolExecutor(registry, ToolConfig(max_retries=0))
    result = await executor.execute("add", {"a": 5, "b": 3}, ExecutionContext())
    assert result.success is True
    assert result.output == 8


async def test_execute_failing_tool_retries() -> None:
    registry = DefaultToolRegistry()
    registry.register("fail", failing_tool, {}, ToolConfig(max_retries=2, retry_base_delay_ms=10))
    executor = DefaultToolExecutor(registry)
    result = await executor.execute("fail", {}, ExecutionContext())
    assert result.success is False
    assert "boom" in (result.error or "")
    assert result.retry_count == 2


async def test_execute_parallel() -> None:
    registry = DefaultToolRegistry()
    registry.register("add", async_add, SCHEMA_ADD)
    executor = DefaultToolExecutor(registry, ToolConfig(max_retries=0))

    calls = [
        ToolCall(tool_name="add", arguments={"a": 1, "b": 2}),
        ToolCall(tool_name="add", arguments={"a": 3, "b": 4}),
    ]
    results = await executor.execute_parallel(calls, max_concurrency=2)
    assert len(results) == 2
    assert results[0].output == 3
    assert results[1].output == 7


# --- Validation ---


async def test_invalid_args_rejected() -> None:
    registry = DefaultToolRegistry()
    registry.register("add", async_add, SCHEMA_ADD)
    executor = DefaultToolExecutor(registry, ToolConfig(max_retries=0))
    # Missing required arg 'b'
    result = await executor.execute("add", {"a": 1}, ExecutionContext())
    assert result.success is False
    assert "Missing required" in (result.error or "")


async def test_wrong_type_rejected() -> None:
    registry = DefaultToolRegistry()
    registry.register("add", async_add, SCHEMA_ADD)
    executor = DefaultToolExecutor(registry, ToolConfig(max_retries=0))
    result = await executor.execute("add", {"a": "not_int", "b": 2}, ExecutionContext())
    assert result.success is False
    assert "expected type" in (result.error or "")


# --- Circuit breaker ---


async def test_circuit_breaker_trips_after_threshold() -> None:
    registry = DefaultToolRegistry()
    cfg = ToolConfig(max_retries=0, circuit_breaker_threshold=3, circuit_breaker_reset_ms=60_000)
    registry.register("fail", failing_tool, {}, cfg)
    executor = DefaultToolExecutor(registry)

    # Trip the circuit breaker
    for _ in range(3):
        await executor.execute("fail", {}, ExecutionContext())

    cb = registry.get_circuit_breaker("fail")
    assert cb.state == CircuitBreakerState.OPEN

    # Next call should be immediately rejected
    result = await executor.execute("fail", {}, ExecutionContext())
    assert result.success is False
    assert "Circuit breaker OPEN" in (result.error or "")


async def test_circuit_breaker_recovers_through_half_open() -> None:
    registry = DefaultToolRegistry()
    cfg = ToolConfig(max_retries=0, circuit_breaker_threshold=2, circuit_breaker_reset_ms=10)
    registry.register("fail", failing_tool, {}, cfg)
    registry.register("ok", async_add, SCHEMA_ADD, cfg)
    executor = DefaultToolExecutor(registry)

    # Trip the breaker on 'ok' tool with a different handler first
    cb = registry.get_circuit_breaker("ok")
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN

    # Wait for reset
    await asyncio.sleep(0.02)
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # Successful call should close it
    result = await executor.execute("ok", {"a": 1, "b": 2}, ExecutionContext())
    assert result.success is True
    assert cb.state == CircuitBreakerState.CLOSED


# --- Parallel with mixed results ---


async def test_parallel_mixed_success_failure() -> None:
    registry = DefaultToolRegistry()
    registry.register("add", async_add, SCHEMA_ADD, ToolConfig(max_retries=0))
    registry.register("fail", failing_tool, {}, ToolConfig(max_retries=0))
    executor = DefaultToolExecutor(registry)

    calls = [
        ToolCall(tool_name="add", arguments={"a": 1, "b": 2}),
        ToolCall(tool_name="fail", arguments={}),
        ToolCall(tool_name="add", arguments={"a": 5, "b": 5}),
    ]
    results = await executor.execute_parallel(calls, max_concurrency=3)
    assert results[0].success is True
    assert results[1].success is False
    assert results[2].success is True
    assert results[2].output == 10


# --- Caching ---


async def test_cache_hit_skips_execution() -> None:
    call_count = 0

    async def counting_tool(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x * 2

    registry = DefaultToolRegistry()
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}
    registry.register("double", counting_tool, schema, ToolConfig(cache_ttl_seconds=60))
    executor = DefaultToolExecutor(registry)

    r1 = await executor.execute("double", {"x": 5}, ExecutionContext())
    r2 = await executor.execute("double", {"x": 5}, ExecutionContext())

    assert r1.output == 10
    assert r2.output == 10
    assert r2.cached is True
    assert call_count == 1


async def test_cache_expires_after_ttl() -> None:
    call_count = 0

    async def counting_tool(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x * 2

    registry = DefaultToolRegistry()
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}
    registry.register("double", counting_tool, schema, ToolConfig(cache_ttl_seconds=0.01))
    executor = DefaultToolExecutor(registry)

    await executor.execute("double", {"x": 5}, ExecutionContext())
    await asyncio.sleep(0.02)
    r2 = await executor.execute("double", {"x": 5}, ExecutionContext())

    assert r2.cached is False
    assert call_count == 2


# --- Health check with stats ---


async def test_health_check_reports_stats() -> None:
    registry = DefaultToolRegistry()
    registry.register("add", async_add, SCHEMA_ADD, ToolConfig(max_retries=0))
    executor = DefaultToolExecutor(registry)

    await executor.execute("add", {"a": 1, "b": 2}, ExecutionContext())
    await executor.execute("add", {"a": 3, "b": 4}, ExecutionContext())

    health = await registry.health_check()
    assert health["add"].total_calls == 2
    assert health["add"].total_failures == 0
    assert health["add"].avg_latency_ms > 0


async def test_execute_sync_tool_via_executor() -> None:
    """Sync tools should run in an executor without blocking the event loop."""

    def sync_multiply(a: int, b: int) -> int:
        return a * b

    registry = DefaultToolRegistry()
    schema = {
        "properties": {
            "a": {"type": "integer"},
            "b": {"type": "integer"},
        },
        "required": ["a", "b"],
    }
    registry.register("multiply", sync_multiply, schema)
    executor = DefaultToolExecutor(registry)
    result = await executor.execute("multiply", {"a": 3, "b": 7}, ExecutionContext())
    assert result.success is True
    assert result.output == 21


async def test_execute_with_empty_args() -> None:
    """Tool with no required args should succeed with empty dict."""

    async def no_args_tool() -> str:
        return "done"

    registry = DefaultToolRegistry()
    registry.register("noop", no_args_tool, {})
    executor = DefaultToolExecutor(registry)
    result = await executor.execute("noop", {}, ExecutionContext())
    assert result.success is True
    assert result.output == "done"


async def test_execute_unknown_tool() -> None:
    """Executing an unregistered tool should raise KeyError."""
    registry = DefaultToolRegistry()
    executor = DefaultToolExecutor(registry)
    with pytest.raises(KeyError, match="Tool not found"):
        await executor.execute("nonexistent", {}, ExecutionContext())
