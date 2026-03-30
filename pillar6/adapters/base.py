"""Base LLM adapter abstract class.

All LLM adapters must implement this interface to be usable with Pillar6 agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pillar6.types import LLMRequest, LLMResponse


class LLMAdapter(ABC):
    """Abstract base class for LLM provider adapters."""

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to the LLM.

        Args:
            request: The LLM request containing messages, model, and parameters.

        Returns:
            The LLM response with content and usage statistics.
        """

    @abstractmethod
    def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream a completion response token by token.

        Args:
            request: The LLM request.

        Yields:
            Successive text chunks from the LLM.
        """

    async def close(self) -> None:  # noqa: B027
        """Clean up any resources held by the adapter.

        Subclasses should override this if they hold open connections.
        """
