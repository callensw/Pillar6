"""Tool Orchestration pillar — tool registration, validation, and execution.

Provides abstract interfaces and default implementations for registering tools,
executing them with retries and concurrency limits, circuit breakers, result
caching, and monitoring health.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pillar6.config.models import ToolConfig
from pillar6.types import (
    CircuitBreakerState,
    ExecutionContext,
    RegisteredTool,
    ToolCall,
    ToolHealth,
    ToolResult,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class ToolCircuitOpenError(Exception):
    """Raised when a tool call is rejected because the circuit breaker is OPEN."""


class ToolValidationError(Exception):
    """Raised when tool arguments fail validation."""


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
            handler: Async or sync callable that implements the tool.
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _CircuitBreaker:
    """Per-tool circuit breaker state machine."""

    __slots__ = ("_failure_count", "_last_failure_time", "_state", "_threshold", "_reset_ms")

    def __init__(self, threshold: int, reset_ms: float) -> None:
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._state: CircuitBreakerState = CircuitBreakerState.CLOSED
        self._threshold = threshold
        self._reset_ms = reset_ms

    @property
    def state(self) -> CircuitBreakerState:
        """Return the current state, transitioning OPEN → HALF_OPEN when the timeout elapses."""
        if self._state == CircuitBreakerState.OPEN:
            elapsed = (time.monotonic() - self._last_failure_time) * 1000
            if elapsed >= self._reset_ms:
                self._state = CircuitBreakerState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        """Record a successful call, resetting the breaker to CLOSED."""
        self._failure_count = 0
        self._state = CircuitBreakerState.CLOSED

    def record_failure(self) -> None:
        """Record a failure, potentially tripping the breaker to OPEN."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._threshold:
            self._state = CircuitBreakerState.OPEN


class _ToolStats:
    """Per-tool execution statistics."""

    __slots__ = ("total_calls", "total_failures", "total_latency_ms", "cache_hits", "cache_misses")

    def __init__(self) -> None:
        self.total_calls: int = 0
        self.total_failures: int = 0
        self.total_latency_ms: float = 0.0
        self.cache_hits: int = 0
        self.cache_misses: int = 0


def _validate_args(args: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Simple schema validation (checks required keys and basic types).

    Returns a list of violation messages (empty if valid).
    """
    violations: list[str] = []

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    for key in required:
        if key not in args:
            violations.append(f"Missing required argument: {key}")

    type_map: dict[str, type | tuple[type, ...]] = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    for key, val in args.items():
        if key in properties:
            expected_type = properties[key].get("type")
            if (
                expected_type
                and expected_type in type_map
                and not isinstance(val, type_map[expected_type])
            ):
                violations.append(
                    f"Argument '{key}' expected type '{expected_type}', got '{type(val).__name__}'"
                )

    return violations


def _cache_key(tool_name: str, args: dict[str, Any]) -> str:
    """Generate a deterministic cache key from tool name and arguments."""
    raw = json.dumps({"tool": tool_name, "args": args}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Default implementations
# ---------------------------------------------------------------------------


class DefaultToolRegistry(ToolRegistry):
    """In-memory tool registry with validation and health tracking."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._configs: dict[str, ToolConfig] = {}
        self._circuit_breakers: dict[str, _CircuitBreaker] = {}
        self._stats: dict[str, _ToolStats] = {}

    def register(
        self,
        tool_name: str,
        handler: Callable[..., Any],
        schema: dict[str, Any],
        config: ToolConfig | None = None,
    ) -> None:
        """Register a tool with its handler and schema after validation."""
        if not callable(handler):
            raise TypeError(f"Handler for tool '{tool_name}' is not callable")

        cfg = config or ToolConfig()
        self._tools[tool_name] = RegisteredTool(name=tool_name, tool_schema=schema, handler=handler)
        self._handlers[tool_name] = handler
        self._configs[tool_name] = cfg
        self._circuit_breakers[tool_name] = _CircuitBreaker(
            cfg.circuit_breaker_threshold, cfg.circuit_breaker_reset_ms
        )
        self._stats[tool_name] = _ToolStats()
        logger.debug("Registered tool: %s", tool_name)

    def get_tool(self, tool_name: str) -> RegisteredTool:
        """Retrieve a registered tool by name."""
        if tool_name not in self._tools:
            raise KeyError(f"Tool not found: {tool_name}")
        return self._tools[tool_name]

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

    def get_config(self, tool_name: str) -> ToolConfig:
        """Return the config for a tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            The ToolConfig for this tool.

        Raises:
            KeyError: If the tool is not registered.
        """
        if tool_name not in self._configs:
            raise KeyError(f"Tool not found: {tool_name}")
        return self._configs[tool_name]

    def get_circuit_breaker(self, tool_name: str) -> _CircuitBreaker:
        """Return the circuit breaker for a tool."""
        return self._circuit_breakers[tool_name]

    def get_stats(self, tool_name: str) -> _ToolStats:
        """Return the execution stats for a tool."""
        return self._stats[tool_name]

    def list_tools(self) -> list[str]:
        """Return the names of all registered tools."""
        return list(self._tools.keys())

    async def health_check(self) -> dict[str, ToolHealth]:
        """Return health status and statistics for all tools."""
        result: dict[str, ToolHealth] = {}
        for name in self._tools:
            cb = self._circuit_breakers[name]
            stats = self._stats[name]
            avg_latency = stats.total_latency_ms / max(stats.total_calls, 1)
            total_cache = stats.cache_hits + stats.cache_misses
            cache_rate = stats.cache_hits / max(total_cache, 1)
            result[name] = ToolHealth(
                tool_name=name,
                healthy=cb.state != CircuitBreakerState.OPEN,
                circuit_breaker_state=cb.state,
                total_calls=stats.total_calls,
                total_failures=stats.total_failures,
                avg_latency_ms=avg_latency,
                cache_hit_rate=cache_rate,
            )
        return result


class DefaultToolExecutor(ToolExecutor):
    """Default tool executor with retry logic, circuit breaker, caching, and concurrency control."""

    def __init__(self, registry: ToolRegistry, config: ToolConfig | None = None) -> None:
        if not isinstance(registry, DefaultToolRegistry):
            raise TypeError("DefaultToolExecutor requires a DefaultToolRegistry")
        self._registry: DefaultToolRegistry = registry
        self._config = config or ToolConfig()
        self._cache: dict[str, tuple[float, Any]] = {}  # key -> (timestamp, result)

    async def execute(
        self, tool_name: str, args: dict[str, Any], context: ExecutionContext
    ) -> ToolResult:
        """Execute a single tool call with validation, caching, retries, and circuit breaker."""
        tool = self._registry.get_tool(tool_name)
        tool_config = self._registry.get_config(tool_name)
        cb = self._registry.get_circuit_breaker(tool_name)
        stats = self._registry.get_stats(tool_name)

        # --- Validate arguments ---
        violations = _validate_args(args, tool.tool_schema)
        if violations:
            stats.total_calls += 1
            stats.total_failures += 1
            return ToolResult(
                tool_name=tool_name,
                error=f"Validation failed: {'; '.join(violations)}",
                success=False,
            )

        # --- Check circuit breaker ---
        if cb.state == CircuitBreakerState.OPEN:
            stats.total_calls += 1
            stats.total_failures += 1
            return ToolResult(
                tool_name=tool_name,
                error=f"Circuit breaker OPEN for tool '{tool_name}'",
                success=False,
            )

        # --- Check cache ---
        if tool_config.cache_ttl_seconds > 0:
            key = _cache_key(tool_name, args)
            cached = self._cache.get(key)
            if cached is not None:
                ts, cached_output = cached
                if (time.monotonic() - ts) < tool_config.cache_ttl_seconds:
                    stats.total_calls += 1
                    stats.cache_hits += 1
                    return ToolResult(
                        tool_name=tool_name,
                        output=cached_output,
                        success=True,
                        cached=True,
                    )
                else:
                    del self._cache[key]
            stats.cache_misses += 1

        # --- Execute with retries ---
        handler = self._registry.get_handler(tool_name)
        last_error: str = ""
        timeout_s = tool_config.timeout_ms / 1000
        retries = tool_config.max_retries

        for attempt in range(retries + 1):
            stats.total_calls += 1
            start = time.monotonic()
            try:
                if asyncio.iscoroutinefunction(handler):
                    output = await asyncio.wait_for(handler(**args), timeout=timeout_s)
                else:
                    output = handler(**args)
                duration = (time.monotonic() - start) * 1000
                stats.total_latency_ms += duration

                cb.record_success()

                # Store in cache
                if tool_config.cache_ttl_seconds > 0:
                    self._cache[_cache_key(tool_name, args)] = (time.monotonic(), output)

                return ToolResult(
                    tool_name=tool_name,
                    output=output,
                    duration_ms=duration,
                    success=True,
                    retry_count=attempt,
                )
            except Exception as exc:
                duration = (time.monotonic() - start) * 1000
                stats.total_latency_ms += duration
                stats.total_failures += 1
                last_error = str(exc)
                cb.record_failure()
                logger.warning("Tool %s attempt %d failed: %s", tool_name, attempt + 1, last_error)
                if attempt < retries:
                    base_delay = tool_config.retry_base_delay_ms / 1000
                    delay = base_delay * (2**attempt)
                    jitter = random.uniform(0, 0.1 * delay)  # noqa: S311
                    await asyncio.sleep(delay + jitter)

        return ToolResult(
            tool_name=tool_name,
            error=last_error,
            success=False,
            retry_count=retries,
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
