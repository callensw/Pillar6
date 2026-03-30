"""Context Management pillar — intelligent context window management.

Provides the abstract interface and a default in-memory implementation for
managing per-agent conversation context, including allocation, injection,
compression, snapshotting, and restoration.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from pillar6.config.models import ContextConfig
from pillar6.types import ContextSnapshot, Message, Priority, Role

logger = logging.getLogger(__name__)


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

    __slots__ = ("messages", "token_budget", "used_tokens")

    def __init__(self, token_budget: int) -> None:
        self.messages: list[Message] = []
        self.token_budget: int = token_budget
        self.used_tokens: int = 0


class DefaultContextManager(ContextManager):
    """In-memory context manager with a simple sliding-window compression.

    Suitable for development and single-process deployments.
    """

    def __init__(self, config: ContextConfig | None = None) -> None:
        self._config = config or ContextConfig()
        self._contexts: dict[str, _AgentContext] = {}

    def _get_or_create(self, agent_id: str) -> _AgentContext:
        if agent_id not in self._contexts:
            self._contexts[agent_id] = _AgentContext(self._config.default_token_budget)
        return self._contexts[agent_id]

    async def allocate(self, agent_id: str, token_budget: int) -> None:
        """Allocate a token budget for the given agent."""
        ctx = self._get_or_create(agent_id)
        ctx.token_budget = token_budget
        logger.debug("Allocated %d tokens for agent %s", token_budget, agent_id)

    async def inject(self, agent_id: str, content: str, priority: Priority) -> None:
        """Inject a message into the agent's context."""
        ctx = self._get_or_create(agent_id)
        estimated_tokens = max(1, len(content) // 4)
        msg = Message(
            role=Role.USER,
            content=content,
            priority=priority,
            token_count=estimated_tokens,
        )
        ctx.messages.append(msg)
        ctx.used_tokens += estimated_tokens

        if len(ctx.messages) > self._config.max_messages:
            await self.compress(agent_id)

        logger.debug("Injected %s-priority message for agent %s", priority.value, agent_id)

    async def compress(self, agent_id: str) -> None:
        """Compress context by dropping lowest-priority ephemeral messages."""
        ctx = self._get_or_create(agent_id)
        priority_order = [Priority.SYSTEM, Priority.RECENT, Priority.RETRIEVED, Priority.EPHEMERAL]

        while (
            ctx.used_tokens > int(ctx.token_budget * self._config.compression_threshold)
            and ctx.messages
        ):
            # Remove the lowest-priority message (last in priority order)
            worst_idx: int | None = None
            worst_priority = -1
            for i, msg in enumerate(ctx.messages):
                p_rank = priority_order.index(msg.priority) if msg.priority in priority_order else 0
                if p_rank >= worst_priority:
                    worst_priority = p_rank
                    worst_idx = i
            if worst_idx is not None:
                removed = ctx.messages.pop(worst_idx)
                ctx.used_tokens -= removed.token_count
            else:
                break

        logger.debug("Compressed context for agent %s to %d tokens", agent_id, ctx.used_tokens)

    async def snapshot(self, agent_id: str) -> ContextSnapshot:
        """Take a snapshot of the agent's current context."""
        ctx = self._get_or_create(agent_id)
        return ContextSnapshot(
            agent_id=agent_id,
            messages=list(ctx.messages),
            token_budget=ctx.token_budget,
            used_tokens=ctx.used_tokens,
        )

    async def restore(self, agent_id: str, snapshot: ContextSnapshot) -> None:
        """Restore an agent's context from a snapshot."""
        ctx = self._get_or_create(agent_id)
        ctx.messages = list(snapshot.messages)
        ctx.token_budget = snapshot.token_budget
        ctx.used_tokens = snapshot.used_tokens
        logger.debug("Restored context for agent %s from snapshot", agent_id)

    async def get_context(self, agent_id: str) -> list[Message]:
        """Return the current ordered messages for an agent."""
        ctx = self._get_or_create(agent_id)
        return list(ctx.messages)
