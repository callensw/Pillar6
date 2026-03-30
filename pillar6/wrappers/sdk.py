"""Wrap raw Anthropic or OpenAI SDK clients with Pillar6 monitoring.

Usage::

    from anthropic import AsyncAnthropic
    from pillar6.wrappers.sdk import wrap_client

    client = AsyncAnthropic()
    monitored_client = wrap_client(client)

    # Use exactly like normal — but now every call is traced,
    # costs are tracked, and security checks run automatically
    response = await monitored_client.messages.create(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": "Hello"}],
    )

This module does NOT import any SDK directly.  It detects the client type
via duck typing and proxies the relevant ``create`` method.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
import uuid
from typing import Any

from pillar6.config.models import Pillar6Config
from pillar6.core.observability import DefaultObservabilityLayer
from pillar6.core.router import DefaultRouter
from pillar6.core.security import DefaultGuardrailEngine
from pillar6.types import TokenUsage, TraceEvent


class _MonitoredCreate:
    """Proxy for a ``create`` method that adds Pillar6 instrumentation."""

    def __init__(
        self,
        original_create: Any,
        provider: str,
        traces: DefaultObservabilityLayer,
        costs: DefaultRouter,
        security: DefaultGuardrailEngine,
        config: Pillar6Config,
    ) -> None:
        self._original = original_create
        self._provider = provider
        self._traces = traces
        self._costs = costs
        self._security = security
        self._config = config
        self._is_async = inspect.iscoroutinefunction(original_create)

    async def _call_async(self, *args: Any, **kwargs: Any) -> Any:
        workflow_id = uuid.uuid4().hex[:12]
        agent_id = self._config.agent.agent_id
        trace_ctx = self._traces.start_trace(workflow_id)

        model = kwargs.get("model", "unknown")

        # Security check on message content
        messages = kwargs.get("messages", [])
        for msg in messages:
            content = msg.get("content", "") if isinstance(msg, dict) else ""
            if isinstance(content, str) and content:
                validation = await self._security.check_input(content, agent_id)
                if not validation.passed:
                    self._traces.end_trace(trace_ctx)
                    violations = "; ".join(validation.violations)
                    err = f"Input validation failed: {violations}"
                    raise ValueError(err)

        self._traces.add_event(
            trace_ctx,
            TraceEvent(
                event_type=f"{self._provider}.request",
                agent_id=agent_id,
                message=f"{self._provider} API call to {model}",
                data={"model": model, "message_count": len(messages)},
            ),
        )

        try:
            start_time = time.monotonic()
            response = await self._original(*args, **kwargs)
            duration_ms = (time.monotonic() - start_time) * 1000

            # Extract usage from response
            usage = self._extract_usage(response)
            if usage:
                await self._costs.track_cost(agent_id, model, usage)

            await self._traces.emit_metric(
                f"{self._provider}.duration_ms",
                duration_ms,
                tags={"model": model, "agent_id": agent_id},
            )

            self._traces.add_event(
                trace_ctx,
                TraceEvent(
                    event_type=f"{self._provider}.response",
                    agent_id=agent_id,
                    message=f"{self._provider} response in {duration_ms:.1f}ms",
                    data={
                        "duration_ms": duration_ms,
                        "model": model,
                        "total_tokens": usage.total_tokens if usage else 0,
                    },
                ),
            )

            return response

        except Exception as exc:
            self._traces.add_event(
                trace_ctx,
                TraceEvent(
                    event_type=f"{self._provider}.error",
                    agent_id=agent_id,
                    message=f"Error: {exc}",
                ),
            )
            raise
        finally:
            self._traces.end_trace(trace_ctx)

    def _extract_usage(self, response: Any) -> TokenUsage | None:
        """Extract token usage from an SDK response object."""
        usage = getattr(response, "usage", None)
        if usage is None:
            return None

        # Anthropic format: usage.input_tokens, usage.output_tokens
        input_tokens = getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0)

        if input_tokens or output_tokens:
            return TokenUsage(
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            )
        return None

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the create method with instrumentation."""
        if self._is_async:
            return await self._call_async(*args, **kwargs)
        # Sync SDK client — run in executor, still instrument
        loop = asyncio.get_running_loop()
        # For sync clients we need a sync wrapper path
        workflow_id = uuid.uuid4().hex[:12]
        agent_id = self._config.agent.agent_id
        trace_ctx = self._traces.start_trace(workflow_id)
        model = kwargs.get("model", "unknown")

        self._traces.add_event(
            trace_ctx,
            TraceEvent(
                event_type=f"{self._provider}.request",
                agent_id=agent_id,
                message=f"{self._provider} API call to {model}",
            ),
        )

        try:
            start_time = time.monotonic()
            response = await loop.run_in_executor(
                None, functools.partial(self._original, *args, **kwargs)
            )
            duration_ms = (time.monotonic() - start_time) * 1000

            usage = self._extract_usage(response)
            if usage:
                await self._costs.track_cost(agent_id, model, usage)

            self._traces.add_event(
                trace_ctx,
                TraceEvent(
                    event_type=f"{self._provider}.response",
                    agent_id=agent_id,
                    message=f"{self._provider} response in {duration_ms:.1f}ms",
                ),
            )

            return response
        except Exception as exc:
            self._traces.add_event(
                trace_ctx,
                TraceEvent(
                    event_type=f"{self._provider}.error",
                    agent_id=agent_id,
                    message=f"Error: {exc}",
                ),
            )
            raise
        finally:
            self._traces.end_trace(trace_ctx)


class _MonitoredNamespace:
    """Proxy for a namespace (e.g., ``client.messages``) that intercepts ``create``."""

    def __init__(self, original_ns: Any, monitored_create: _MonitoredCreate) -> None:
        self._original_ns = original_ns
        self._monitored_create = monitored_create

    @property
    def create(self) -> _MonitoredCreate:
        return self._monitored_create

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original_ns, name)


class MonitoredClient:
    """An SDK client wrapped with Pillar6 production monitoring.

    Attributes:
        traces: The observability layer.
        costs: The router for cost tracking.
        security: The guardrail engine.
        last_workflow_id: The workflow ID from the most recent call.
    """

    def __init__(
        self,
        client: Any,
        provider: str,
        config: Pillar6Config | None = None,
    ) -> None:
        self._client = client
        self._provider = provider
        self._config = config or Pillar6Config()

        self.traces = DefaultObservabilityLayer(config=self._config.observability)
        self.costs = DefaultRouter(config=self._config.router)
        self.security = DefaultGuardrailEngine(config=self._config.security)

        # Set up monitored namespace
        if provider == "anthropic":
            ns = getattr(client, "messages", None)
            if ns and hasattr(ns, "create"):
                self._messages = _MonitoredNamespace(
                    ns,
                    _MonitoredCreate(
                        ns.create,
                        provider,
                        self.traces,
                        self.costs,
                        self.security,
                        self._config,
                    ),
                )
        elif provider == "openai":
            chat = getattr(client, "chat", None)
            if chat:
                completions = getattr(chat, "completions", None)
                if completions and hasattr(completions, "create"):
                    self._chat = _MonitoredChat(
                        chat,
                        _MonitoredCreate(
                            completions.create,
                            provider,
                            self.traces,
                            self.costs,
                            self.security,
                            self._config,
                        ),
                    )

    @property
    def messages(self) -> _MonitoredNamespace:
        """Anthropic-style ``client.messages`` namespace."""
        if hasattr(self, "_messages"):
            return self._messages
        return self._client.messages

    @property
    def chat(self) -> Any:
        """OpenAI-style ``client.chat`` namespace."""
        if hasattr(self, "_chat"):
            return self._chat
        return self._client.chat

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class _MonitoredChat:
    """Proxy for ``client.chat`` that intercepts ``completions.create``."""

    def __init__(self, original_chat: Any, monitored_create: _MonitoredCreate) -> None:
        self._original_chat = original_chat
        self._completions = _MonitoredNamespace(
            getattr(original_chat, "completions", None),
            monitored_create,
        )

    @property
    def completions(self) -> _MonitoredNamespace:
        return self._completions

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original_chat, name)


def wrap_client(
    client: Any,
    config: Pillar6Config | None = None,
) -> MonitoredClient:
    """Wrap a raw Anthropic or OpenAI SDK client with Pillar6 monitoring.

    Detects whether the client is Anthropic or OpenAI by checking for
    ``client.messages.create`` (Anthropic) vs
    ``client.chat.completions.create`` (OpenAI).

    Args:
        client: An Anthropic or OpenAI client instance.
        config: Optional Pillar6 configuration.

    Returns:
        A :class:`MonitoredClient` that proxies all calls through Pillar6
        instrumentation.

    Raises:
        TypeError: If the client type cannot be detected.
    """
    # Detect Anthropic client
    messages = getattr(client, "messages", None)
    if messages and hasattr(messages, "create"):
        return MonitoredClient(client, "anthropic", config=config)

    # Detect OpenAI client
    chat = getattr(client, "chat", None)
    if chat:
        completions = getattr(chat, "completions", None)
        if completions and hasattr(completions, "create"):
            return MonitoredClient(client, "openai", config=config)

    msg = (
        f"Cannot detect SDK client type for {type(client).__name__}. "
        f"Expected an Anthropic client (with .messages.create) or "
        f"OpenAI client (with .chat.completions.create)."
    )
    raise TypeError(msg)
