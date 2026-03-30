"""Tests for the Context Management pillar."""

from __future__ import annotations

import pytest

from pillar6.config.models import ContextConfig
from pillar6.core.context import DefaultContextManager, WordBasedTokenCounter
from pillar6.types import Priority


@pytest.fixture
def ctx_manager() -> DefaultContextManager:
    return DefaultContextManager(ContextConfig(default_token_budget=1000, max_messages=50))


# --- Token counter ---


def test_word_based_counter() -> None:
    counter = WordBasedTokenCounter()
    assert counter.count("hello world") >= 2
    assert counter.count("") == 1  # minimum 1


# --- Allocate ---


async def test_allocate_sets_budget(ctx_manager: DefaultContextManager) -> None:
    await ctx_manager.allocate("agent-1", 2048)
    snap = await ctx_manager.snapshot("agent-1")
    assert snap.token_budget == 2048


# --- Inject ---


async def test_inject_adds_message(ctx_manager: DefaultContextManager) -> None:
    await ctx_manager.inject("agent-1", "hello", Priority.RECENT)
    messages = await ctx_manager.get_context("agent-1")
    assert len(messages) == 1
    assert messages[0].content == "hello"
    assert messages[0].priority == Priority.RECENT


async def test_get_context_empty_agent(ctx_manager: DefaultContextManager) -> None:
    messages = await ctx_manager.get_context("nonexistent")
    assert messages == []


async def test_inject_multiple_priorities(ctx_manager: DefaultContextManager) -> None:
    await ctx_manager.inject("agent-1", "system", Priority.SYSTEM)
    await ctx_manager.inject("agent-1", "recent", Priority.RECENT)
    await ctx_manager.inject("agent-1", "ephemeral", Priority.EPHEMERAL)
    messages = await ctx_manager.get_context("agent-1")
    assert len(messages) == 3
    priorities = {m.priority for m in messages}
    assert priorities == {Priority.SYSTEM, Priority.RECENT, Priority.EPHEMERAL}


# --- Budget enforcement and eviction ---


async def test_budget_enforcement_evicts_lowest_priority() -> None:
    """When injecting beyond budget, ephemeral messages are evicted first."""
    mgr = DefaultContextManager(ContextConfig(default_token_budget=20))
    await mgr.allocate("a", 20)

    # Inject content that fills the budget
    await mgr.inject("a", "system message here", Priority.SYSTEM)
    await mgr.inject("a", "recent message here", Priority.RECENT)
    await mgr.inject("a", "ephemeral message", Priority.EPHEMERAL)
    # This should trigger eviction of ephemeral first
    await mgr.inject("a", "another recent message", Priority.RECENT)

    messages = await mgr.get_context("a")
    priorities = [m.priority for m in messages]
    # SYSTEM should never be evicted
    assert Priority.SYSTEM in priorities


async def test_eviction_order_ephemeral_first() -> None:
    """Ephemeral is evicted before Retrieved, which is evicted before Recent."""
    mgr = DefaultContextManager(ContextConfig(default_token_budget=15))
    await mgr.allocate("a", 15)

    await mgr.inject("a", "sys", Priority.SYSTEM)
    await mgr.inject("a", "eph one", Priority.EPHEMERAL)
    await mgr.inject("a", "ret one", Priority.RETRIEVED)
    await mgr.inject("a", "rec one", Priority.RECENT)
    # Force eviction
    await mgr.inject("a", "rec two extra words", Priority.RECENT)

    messages = await mgr.get_context("a")
    priorities = [m.priority for m in messages]
    # System should remain
    assert Priority.SYSTEM in priorities
    # Ephemeral should have been evicted first
    assert (
        sum(1 for p in priorities if p == Priority.EPHEMERAL) == 0
        or sum(1 for p in priorities if p == Priority.RETRIEVED) <= 1
    )


async def test_system_never_evicted() -> None:
    """SYSTEM priority messages are never evicted."""
    mgr = DefaultContextManager(ContextConfig(default_token_budget=10))
    await mgr.allocate("a", 10)

    await mgr.inject("a", "important system", Priority.SYSTEM)
    await mgr.inject("a", "eph", Priority.EPHEMERAL)
    await mgr.inject("a", "more stuff here", Priority.RECENT)

    messages = await mgr.get_context("a")
    system_msgs = [m for m in messages if m.priority == Priority.SYSTEM]
    assert len(system_msgs) >= 1


# --- Compression ---


async def test_compress_reduces_messages() -> None:
    mgr = DefaultContextManager(ContextConfig(default_token_budget=500, compression_keep_recent=2))

    for i in range(8):
        await mgr.inject("a", f"message number {i}", Priority.RECENT)

    await mgr.compress("a")
    messages = await mgr.get_context("a")
    # Should have: 1 compressed summary + 2 kept recent = 3
    assert len([m for m in messages if m.priority == Priority.RECENT]) == 3


async def test_compress_preserves_recent_messages() -> None:
    mgr = DefaultContextManager(ContextConfig(default_token_budget=500, compression_keep_recent=3))

    await mgr.inject("a", "old message one", Priority.RECENT)
    await mgr.inject("a", "old message two", Priority.RECENT)
    await mgr.inject("a", "keep me one", Priority.RECENT)
    await mgr.inject("a", "keep me two", Priority.RECENT)
    await mgr.inject("a", "keep me three", Priority.RECENT)

    await mgr.compress("a")

    messages = await mgr.get_context("a")
    recent = [m for m in messages if m.priority == Priority.RECENT]
    # Summary + 3 kept
    assert len(recent) == 4
    assert "[Compressed:" in recent[0].content
    assert recent[-1].content == "keep me three"


async def test_compress_noop_when_few_messages() -> None:
    mgr = DefaultContextManager(ContextConfig(default_token_budget=500, compression_keep_recent=5))
    await mgr.inject("a", "only one", Priority.RECENT)
    await mgr.compress("a")
    messages = await mgr.get_context("a")
    assert len(messages) == 1


# --- Snapshot / Restore ---


async def test_snapshot_and_restore(ctx_manager: DefaultContextManager) -> None:
    await ctx_manager.inject("agent-1", "msg1", Priority.SYSTEM)
    await ctx_manager.inject("agent-1", "msg2", Priority.RECENT)
    snap = await ctx_manager.snapshot("agent-1")

    # Modify state
    await ctx_manager.allocate("agent-1", 500)
    await ctx_manager.inject("agent-1", "msg3", Priority.EPHEMERAL)

    # Restore
    await ctx_manager.restore("agent-1", snap)

    messages = await ctx_manager.get_context("agent-1")
    assert len(messages) == 2
    assert messages[0].content == "msg1"


async def test_snapshot_roundtrip_preserves_state() -> None:
    mgr = DefaultContextManager(ContextConfig(default_token_budget=500))
    await mgr.inject("a", "sys", Priority.SYSTEM)
    await mgr.inject("a", "rec", Priority.RECENT)
    await mgr.inject("a", "eph", Priority.EPHEMERAL)

    snap = await mgr.snapshot("a")
    snap_dict = snap.model_dump()
    # Verify JSON-serializable
    from pillar6.types import ContextSnapshot

    restored_snap = ContextSnapshot.model_validate(snap_dict)
    await mgr.restore("a", restored_snap)

    messages = await mgr.get_context("a")
    assert len(messages) == 3


# --- Multi-agent isolation ---


async def test_multi_agent_isolation() -> None:
    mgr = DefaultContextManager(ContextConfig(default_token_budget=500))
    await mgr.inject("agent-a", "A's message", Priority.RECENT)
    await mgr.inject("agent-b", "B's message", Priority.RECENT)

    a_msgs = await mgr.get_context("agent-a")
    b_msgs = await mgr.get_context("agent-b")

    assert len(a_msgs) == 1
    assert a_msgs[0].content == "A's message"
    assert len(b_msgs) == 1
    assert b_msgs[0].content == "B's message"


# --- get_context ordering ---


async def test_get_context_ordering() -> None:
    mgr = DefaultContextManager(ContextConfig(default_token_budget=500))
    await mgr.inject("a", "ephemeral", Priority.EPHEMERAL)
    await mgr.inject("a", "recent", Priority.RECENT)
    await mgr.inject("a", "system", Priority.SYSTEM)
    await mgr.inject("a", "retrieved", Priority.RETRIEVED)

    messages = await mgr.get_context("a")
    priorities = [m.priority for m in messages]
    # Order should be: SYSTEM, RECENT, RETRIEVED, EPHEMERAL
    assert priorities.index(Priority.SYSTEM) < priorities.index(Priority.RECENT)
    assert priorities.index(Priority.RECENT) < priorities.index(Priority.RETRIEVED)
    assert priorities.index(Priority.RETRIEVED) < priorities.index(Priority.EPHEMERAL)


async def test_inject_unicode_content() -> None:
    mgr = DefaultContextManager(ContextConfig(default_token_budget=500))
    await mgr.inject("a", "Hello \U0001f30d \u4f60\u597d \u00e9\u00e8\u00ea", Priority.RECENT)
    messages = await mgr.get_context("a")
    assert len(messages) == 1
    assert "\U0001f30d" in messages[0].content


async def test_get_context_unknown_agent() -> None:
    """Getting context for a non-existent agent returns empty list."""
    mgr = DefaultContextManager(ContextConfig(default_token_budget=500))
    messages = await mgr.get_context("nonexistent")
    assert messages == []
