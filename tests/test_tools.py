"""Tests for the Tool Orchestration pillar."""

from __future__ import annotations

import pytest

from pillar6.config.models import ToolConfig
from pillar6.core.tools import DefaultToolExecutor, DefaultToolRegistry
from pillar6.types import ExecutionContext, ToolCall

# --- Helpers ---


async def async_add(a: int, b: int) -> int:
    return a + b


def sync_add(a: int, b: int) -> int:
    return a + b


async def failing_tool() -> None:
    raise RuntimeError("boom")


# --- Registry tests ---


def test_register_and_get() -> None:
    registry = DefaultToolRegistry()
    registry.register("add", async_add, {"type": "object"})
    tool = registry.get_tool("add")
    assert tool.name == "add"


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


# --- Executor tests ---


async def test_execute_async_tool() -> None:
    registry = DefaultToolRegistry()
    registry.register("add", async_add, {})
    executor = DefaultToolExecutor(registry, ToolConfig(max_retries=0))
    result = await executor.execute("add", {"a": 1, "b": 2}, ExecutionContext())
    assert result.success is True
    assert result.output == 3


async def test_execute_sync_tool() -> None:
    registry = DefaultToolRegistry()
    registry.register("add", sync_add, {})
    executor = DefaultToolExecutor(registry, ToolConfig(max_retries=0))
    result = await executor.execute("add", {"a": 5, "b": 3}, ExecutionContext())
    assert result.success is True
    assert result.output == 8


async def test_execute_failing_tool_retries() -> None:
    registry = DefaultToolRegistry()
    registry.register("fail", failing_tool, {})
    executor = DefaultToolExecutor(registry, ToolConfig(max_retries=1, retry_base_delay_ms=10))
    result = await executor.execute("fail", {}, ExecutionContext())
    assert result.success is False
    assert "boom" in (result.error or "")


async def test_execute_parallel() -> None:
    registry = DefaultToolRegistry()
    registry.register("add", async_add, {})
    executor = DefaultToolExecutor(registry, ToolConfig(max_retries=0))

    calls = [
        ToolCall(tool_name="add", arguments={"a": 1, "b": 2}),
        ToolCall(tool_name="add", arguments={"a": 3, "b": 4}),
    ]
    results = await executor.execute_parallel(calls, max_concurrency=2)
    assert len(results) == 2
    assert results[0].output == 3
    assert results[1].output == 7
