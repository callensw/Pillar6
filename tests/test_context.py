"""Tests for the Context Management pillar."""

from __future__ import annotations

import pytest

from pillar6.config.models import ContextConfig
from pillar6.core.context import DefaultContextManager
from pillar6.types import Priority


@pytest.fixture
def ctx_manager() -> DefaultContextManager:
    return DefaultContextManager(ContextConfig(default_token_budget=1000, max_messages=5))


async def test_allocate_sets_budget(ctx_manager: DefaultContextManager) -> None:
    await ctx_manager.allocate("agent-1", 2048)
    snap = await ctx_manager.snapshot("agent-1")
    assert snap.token_budget == 2048


async def test_inject_adds_message(ctx_manager: DefaultContextManager) -> None:
    await ctx_manager.inject("agent-1", "hello", Priority.RECENT)
    messages = await ctx_manager.get_context("agent-1")
    assert len(messages) == 1
    assert messages[0].content == "hello"
    assert messages[0].priority == Priority.RECENT


async def test_get_context_empty_agent(ctx_manager: DefaultContextManager) -> None:
    messages = await ctx_manager.get_context("nonexistent")
    assert messages == []


async def test_snapshot_and_restore(ctx_manager: DefaultContextManager) -> None:
    await ctx_manager.inject("agent-1", "msg1", Priority.SYSTEM)
    await ctx_manager.inject("agent-1", "msg2", Priority.RECENT)
    snap = await ctx_manager.snapshot("agent-1")

    # Clear and restore
    await ctx_manager.allocate("agent-1", 500)
    await ctx_manager.restore("agent-1", snap)

    messages = await ctx_manager.get_context("agent-1")
    assert len(messages) == 2
    assert messages[0].content == "msg1"


async def test_compress_drops_low_priority() -> None:
    # Use a tiny budget so compression actually kicks in
    mgr = DefaultContextManager(ContextConfig(default_token_budget=10, max_messages=100))
    await mgr.allocate("agent-1", 10)

    # Inject enough content to exceed the budget (each ~25 chars => ~6 tokens)
    await mgr.inject("agent-1", "x" * 25, Priority.SYSTEM)
    await mgr.inject("agent-1", "y" * 25, Priority.EPHEMERAL)
    await mgr.inject("agent-1", "z" * 25, Priority.EPHEMERAL)

    # Manually trigger compression
    await mgr.compress("agent-1")

    messages = await mgr.get_context("agent-1")
    # Ephemeral messages should be dropped before system messages
    priorities = [m.priority for m in messages]
    assert Priority.SYSTEM in priorities
    assert len(messages) < 3


async def test_inject_multiple_priorities(ctx_manager: DefaultContextManager) -> None:
    await ctx_manager.inject("agent-1", "system", Priority.SYSTEM)
    await ctx_manager.inject("agent-1", "recent", Priority.RECENT)
    await ctx_manager.inject("agent-1", "ephemeral", Priority.EPHEMERAL)
    messages = await ctx_manager.get_context("agent-1")
    assert len(messages) == 3
    priorities = {m.priority for m in messages}
    assert priorities == {Priority.SYSTEM, Priority.RECENT, Priority.EPHEMERAL}
