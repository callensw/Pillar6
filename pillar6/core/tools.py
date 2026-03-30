"""Tool Orchestration pillar — tool registration, validation, and execution.

Provides abstract interfaces and default implementations for registering tools,
executing them with retries and concurrency limits, and monitoring health.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pillar6.config.models import ToolConfig
from pillar6.types import (
    ExecutionContext,
    RegisteredTool,
    ToolCall,
    ToolHealth,
    ToolResult,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class ToolRegistry(ABC):
    """Abstract base class for tool registration and discovery."""

    @abstractmethod
    def register(
        self,
        tool_name: str,
        handler: Callable[..., Any],
        schema: dict[str, Any],
        config: ToolConfig | None = None,
    ) -> None:
        """Register a tool with its handler and JSON schema.

        Args:
            tool_name: Unique name for the tool.
            handler: Async callable that implements the tool.
            schema: JSON-schema describing the tool's parameters.
            config: Optional per-tool configuration overrides.
        """

    @abstractmethod
    def get_tool(self, tool_name: str) -> RegisteredTool:
        """Retrieve a registered tool by name.

        Args:
            tool_name: Name of the tool.

        Returns:
            The registered tool descriptor.

        Raises:
            KeyError: If the tool is not registered.
        """

    @abstractmethod
    def list_tools(self) -> list[str]:
        """Return the names of all registered tools."""

    @abstractmethod
    async def health_check(self) -> dict[str, ToolHealth]:
        """Run health checks on all registered tools.

        Returns:
            Mapping of tool name to its health status.
        """


class ToolExecutor(ABC):
    """Abstract base class for executing tool calls."""

    @abstractmethod
    async def execute(
        self, tool_name: str, args: dict[str, Any], context: ExecutionContext
    ) -> ToolResult:
        """Execute a single tool call.

        Args:
            tool_name: Name of the tool to execute.
            args: Arguments to pass to the tool handler.
            context: Runtime execution context.

        Returns:
            The result of the tool execution.
        """

    @abstractmethod
    async def execute_parallel(
        self, calls: list[ToolCall], max_concurrency: int = 5
    ) -> list[ToolResult]:
        """Execute multiple tool calls in parallel.

        Args:
            calls: List of tool calls to execute.
            max_concurrency: Maximum number of concurrent executions.

        Returns:
            List of results in the same order as the input calls.
        """


class DefaultToolRegistry(ToolRegistry):
    """In-memory tool registry."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(
        self,
        tool_name: str,
        handler: Callable[..., Any],
        schema: dict[str, Any],
        config: ToolConfig | None = None,
    ) -> None:
        """Register a tool with its handler and schema."""
        self._tools[tool_name] = RegisteredTool(name=tool_name, tool_schema=schema, handler=handler)
        self._handlers[tool_name] = handler
        logger.debug("Registered tool: %s", tool_name)

    def get_tool(self, tool_name: str) -> RegisteredTool:
        """Retrieve a registered tool by name."""
        if tool_name not in self._tools:
            raise KeyError(f"Tool not found: {tool_name}")
        return self._tools[tool_name]

    def list_tools(self) -> list[str]:
        """Return the names of all registered tools."""
        return list(self._tools.keys())

    def get_handler(self, tool_name: str) -> Callable[..., Any]:
        """Return the handler callable for a tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            The handler callable.

        Raises:
            KeyError: If the tool is not registered.
        """
        if tool_name not in self._handlers:
            raise KeyError(f"Tool not found: {tool_name}")
        return self._handlers[tool_name]

    async def health_check(self) -> dict[str, ToolHealth]:
        """Return health status for all tools (always healthy in default impl)."""
        return {name: ToolHealth(tool_name=name, healthy=True) for name in self._tools}


class DefaultToolExecutor(ToolExecutor):
    """Default tool executor with retry logic and concurrency control."""

    def __init__(self, registry: ToolRegistry, config: ToolConfig | None = None) -> None:
        self._registry = registry
        self._config = config or ToolConfig()

    async def execute(
        self, tool_name: str, args: dict[str, Any], context: ExecutionContext
    ) -> ToolResult:
        """Execute a single tool call with retries."""
        if not isinstance(self._registry, DefaultToolRegistry):
            raise TypeError("DefaultToolExecutor requires a DefaultToolRegistry")

        handler = self._registry.get_handler(tool_name)
        last_error: str = ""

        for attempt in range(self._config.max_retries + 1):
            start = time.monotonic()
            try:
                if asyncio.iscoroutinefunction(handler):
                    output = await handler(**args)
                else:
                    output = handler(**args)
                duration = (time.monotonic() - start) * 1000
                return ToolResult(
                    tool_name=tool_name,
                    output=output,
                    duration_ms=duration,
                    success=True,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.warning("Tool %s attempt %d failed: %s", tool_name, attempt + 1, last_error)
                if attempt < self._config.max_retries:
                    delay = self._config.retry_base_delay_ms / 1000
                    await asyncio.sleep(delay * (2**attempt))

        return ToolResult(
            tool_name=tool_name,
            error=last_error,
            success=False,
        )

    async def execute_parallel(
        self, calls: list[ToolCall], max_concurrency: int = 5
    ) -> list[ToolResult]:
        """Execute multiple tool calls concurrently with a semaphore."""
        sem = asyncio.Semaphore(max_concurrency)
        context = ExecutionContext()

        async def _run(call: ToolCall) -> ToolResult:
            async with sem:
                return await self.execute(call.tool_name, call.arguments, context)

        return list(await asyncio.gather(*[_run(c) for c in calls]))
