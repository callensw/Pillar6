"""Context Management pillar — intelligent context window management.

Provides the abstract interface and a default in-memory implementation for
managing per-agent conversation context, including allocation, injection,
priority-based eviction, compression, snapshotting, and restoration.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from pillar6.config.models import ContextConfig
from pillar6.types import ContextSnapshot, Message, Priority, Role

logger = logging.getLogger(__name__)

# Priority eviction order: lowest value = highest priority (never evict).
_PRIORITY_RANK: dict[Priority, int] = {
    Priority.SYSTEM: 0,
    Priority.RECENT: 1,
    Priority.RETRIEVED: 2,
    Priority.EPHEMERAL: 3,
}


@runtime_checkable
class TokenCounter(Protocol):
    """Protocol for pluggable token counting strategies.

    Users can implement this to use tiktoken or any other counter.
    """

    def count(self, text: str) -> int:
        """Return the estimated token count for *text*."""
        ...


class WordBasedTokenCounter:
    """Simple word-based token counter using a 1.3x multiplier."""

    def count(self, text: str) -> int:
        """Estimate tokens as ``ceil(word_count * 1.3)``."""
        words = len(text.split())
        return max(1, int(words * 1.3 + 0.5))


class ContextManager(ABC):
    """Abstract base class for context window management.

    Every agent gets its own context window managed through this interface.
    Implementations handle budget tracking, message prioritisation, and
    optional persistence.
    """

    @abstractmethod
    async def allocate(self, agent_id: str, token_budget: int) -> None:
        """Allocate a token budget for the given agent.

        Args:
            agent_id: Unique agent identifier.
            token_budget: Maximum token budget for the context window.
        """

    @abstractmethod
    async def inject(self, agent_id: str, content: str, priority: Priority) -> None:
        """Inject a message into the agent's context.

        Args:
            agent_id: Unique agent identifier.
            content: Text content to inject.
            priority: Priority level for the injected content.
        """

    @abstractmethod
    async def compress(self, agent_id: str) -> None:
        """Compress the agent's context to fit within its token budget.

        Args:
            agent_id: Unique agent identifier.
        """

    @abstractmethod
    async def snapshot(self, agent_id: str) -> ContextSnapshot:
        """Take a serializable snapshot of the agent's current context.

        Args:
            agent_id: Unique agent identifier.

        Returns:
            A ContextSnapshot capturing the full state.
        """

    @abstractmethod
    async def restore(self, agent_id: str, snapshot: ContextSnapshot) -> None:
        """Restore an agent's context from a snapshot.

        Args:
            agent_id: Unique agent identifier.
            snapshot: Previously captured snapshot.
        """

    @abstractmethod
    async def get_context(self, agent_id: str) -> list[Message]:
        """Return the current ordered list of messages for an agent.

        Args:
            agent_id: Unique agent identifier.

        Returns:
            List of messages in context order.
        """


class _AgentContext:
    """Internal container for a single agent's context state."""

    __slots__ = ("buckets", "token_budget", "used_tokens")

    def __init__(self, token_budget: int) -> None:
        self.buckets: dict[Priority, list[Message]] = {p: [] for p in Priority}
        self.token_budget: int = token_budget
        self.used_tokens: int = 0

    @property
    def all_messages(self) -> list[Message]:
        """Return all messages across all priority buckets."""
        msgs: list[Message] = []
        for p in (Priority.SYSTEM, Priority.RECENT, Priority.RETRIEVED, Priority.EPHEMERAL):
            msgs.extend(self.buckets[p])
        return msgs


# Summarizer callable type hint — users can supply an LLM-based summarizer.
# Signature: (messages: list[Message]) -> str
# None means use a simple placeholder instead.
SummarizerFn = None  # placeholder for the type


class DefaultContextManager(ContextManager):
    """In-memory context manager with priority buckets and sliding-window compression.

    Features:
    - Per-priority budget allocation (SYSTEM 20%, RECENT 40%, RETRIEVED 25%, EPHEMERAL 15%)
    - Automatic eviction of lowest-priority content when budget is exceeded
    - Compression replaces old RECENT messages with a summary placeholder
    - Pluggable TokenCounter (default: word-based approximation)
    - Multi-agent isolation via per-agent context state
    """

    def __init__(
        self,
        config: ContextConfig | None = None,
        token_counter: TokenCounter | None = None,
        summarizer: object | None = None,
    ) -> None:
        self._config = config or ContextConfig()
        self._counter: TokenCounter = token_counter or WordBasedTokenCounter()
        self._summarizer = summarizer  # Callable[[list[Message]], str] | None
        self._contexts: dict[str, _AgentContext] = {}

    def _get_or_create(self, agent_id: str) -> _AgentContext:
        if agent_id not in self._contexts:
            self._contexts[agent_id] = _AgentContext(self._config.default_token_budget)
        return self._contexts[agent_id]

    def _budget_for_priority(self, ctx: _AgentContext, priority: Priority) -> int:
        """Return the token budget allocated to a specific priority level."""
        fractions = {
            Priority.SYSTEM: self._config.system_budget_fraction,
            Priority.RECENT: self._config.recent_budget_fraction,
            Priority.RETRIEVED: self._config.retrieved_budget_fraction,
            Priority.EPHEMERAL: self._config.ephemeral_budget_fraction,
        }
        return int(ctx.token_budget * fractions[priority])

    def _tokens_in_bucket(self, bucket: list[Message]) -> int:
        """Sum the token counts for all messages in a bucket."""
        return sum(m.token_count for m in bucket)

    def _evict_lowest_priority(self, ctx: _AgentContext, tokens_needed: int) -> None:
        """Evict messages from the lowest-priority buckets until tokens are freed.

        Never evicts SYSTEM messages.
        """
        eviction_order = [Priority.EPHEMERAL, Priority.RETRIEVED, Priority.RECENT]
        freed = 0
        for priority in eviction_order:
            bucket = ctx.buckets[priority]
            while bucket and freed < tokens_needed:
                removed = bucket.pop(0)  # oldest first
                freed += removed.token_count
                ctx.used_tokens -= removed.token_count
                logger.debug(
                    "Evicted %s-priority message (%d tokens)",
                    priority.value,
                    removed.token_count,
                )

    async def allocate(self, agent_id: str, token_budget: int) -> None:
        """Allocate a token budget for the given agent."""
        ctx = self._get_or_create(agent_id)
        ctx.token_budget = token_budget
        logger.debug("Allocated %d tokens for agent %s", token_budget, agent_id)

    async def inject(self, agent_id: str, content: str, priority: Priority) -> None:
        """Inject a message into the agent's context with automatic eviction."""
        ctx = self._get_or_create(agent_id)
        estimated_tokens = self._counter.count(content)
        msg = Message(
            role=Role.USER,
            content=content,
            priority=priority,
            token_count=estimated_tokens,
        )

        # If adding this message would exceed the budget, evict lower-priority content
        if ctx.used_tokens + estimated_tokens > ctx.token_budget:
            overflow = (ctx.used_tokens + estimated_tokens) - ctx.token_budget
            self._evict_lowest_priority(ctx, overflow)

        ctx.buckets[priority].append(msg)
        ctx.used_tokens += estimated_tokens

        logger.debug(
            "Injected %s-priority message for agent %s (%d tokens, total %d/%d)",
            priority.value,
            agent_id,
            estimated_tokens,
            ctx.used_tokens,
            ctx.token_budget,
        )

    async def compress(self, agent_id: str) -> None:
        """Compress context by summarizing old RECENT messages.

        Keeps the most recent N messages (configurable) and replaces older
        ones with a summary placeholder. If a summarizer callable is
        provided, it is used; otherwise a simple placeholder is inserted.
        """
        ctx = self._get_or_create(agent_id)
        keep_n = self._config.compression_keep_recent
        recent = ctx.buckets[Priority.RECENT]

        if len(recent) <= keep_n:
            return  # nothing to compress

        to_compress = recent[:-keep_n]
        kept = recent[-keep_n:]

        compressed_count = len(to_compress)
        old_tokens = self._tokens_in_bucket(to_compress)

        if self._summarizer is not None and callable(self._summarizer):
            summary_text: str = self._summarizer(to_compress)
        else:
            summary_text = f"[Compressed: {compressed_count} earlier messages]"

        summary_tokens = self._counter.count(summary_text)
        summary_msg = Message(
            role=Role.USER,
            content=summary_text,
            priority=Priority.RECENT,
            token_count=summary_tokens,
        )

        ctx.buckets[Priority.RECENT] = [summary_msg, *kept]
        ctx.used_tokens -= old_tokens
        ctx.used_tokens += summary_tokens

        logger.debug(
            "Compressed %d messages for agent %s (saved %d tokens)",
            compressed_count,
            agent_id,
            old_tokens - summary_tokens,
        )

    async def snapshot(self, agent_id: str) -> ContextSnapshot:
        """Take a snapshot of the agent's current context."""
        ctx = self._get_or_create(agent_id)
        return ContextSnapshot(
            agent_id=agent_id,
            messages=ctx.all_messages,
            token_budget=ctx.token_budget,
            used_tokens=ctx.used_tokens,
        )

    async def restore(self, agent_id: str, snapshot: ContextSnapshot) -> None:
        """Restore an agent's context from a snapshot."""
        ctx = self._get_or_create(agent_id)
        # Clear existing state
        for bucket in ctx.buckets.values():
            bucket.clear()
        ctx.used_tokens = 0
        ctx.token_budget = snapshot.token_budget

        # Re-populate buckets from snapshot messages
        for msg in snapshot.messages:
            ctx.buckets[msg.priority].append(msg)
            ctx.used_tokens += msg.token_count

        logger.debug("Restored context for agent %s from snapshot", agent_id)

    async def get_context(self, agent_id: str) -> list[Message]:
        """Return the ordered context for an agent: SYSTEM → RECENT → RETRIEVED → EPHEMERAL.

        Respects the total token budget by trimming from the lowest priority
        end if the total exceeds the budget.
        """
        ctx = self._get_or_create(agent_id)
        ordered: list[Message] = []
        remaining = ctx.token_budget

        for priority in (Priority.SYSTEM, Priority.RECENT, Priority.RETRIEVED, Priority.EPHEMERAL):
            for msg in ctx.buckets[priority]:
                if remaining >= msg.token_count:
                    ordered.append(msg)
                    remaining -= msg.token_count

        return ordered
