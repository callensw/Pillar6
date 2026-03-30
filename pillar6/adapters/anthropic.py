"""Anthropic LLM adapter using httpx.

Provides async access to the Anthropic Messages API without pulling in the
official ``anthropic`` SDK, keeping Pillar6's dependency footprint small.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import httpx

from pillar6.adapters.base import LLMAdapter
from pillar6.types import LLMRequest, LLMResponse, TokenUsage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicAdapter(LLMAdapter):
    """Adapter for the Anthropic Messages API.

    Args:
        api_key: Anthropic API key. Falls back to ``ANTHROPIC_API_KEY`` env var.
        base_url: Override the API base URL.
        default_model: Model to use when the request doesn't specify one.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str = _DEFAULT_MODEL,
    ) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._base_url = (base_url or _ANTHROPIC_API_URL).rstrip("/")
        self._default_model = default_model
        self._client = httpx.AsyncClient(timeout=120.0)

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    def _build_payload(self, request: LLMRequest) -> dict[str, Any]:
        messages = [
            {"role": m.role.value, "content": m.content}
            for m in request.messages
            if m.role.value != "system"
        ]
        system_parts = [m.content for m in request.messages if m.role.value == "system"]
        system_text = "\n".join(system_parts) if system_parts else None

        payload: dict[str, Any] = {
            "model": request.model or self._default_model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if system_text:
            payload["system"] = system_text
        if request.stream:
            payload["stream"] = True
        return payload

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to Anthropic."""
        payload = self._build_payload(request)
        resp = await self._client.post(self._base_url, headers=self._headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("input_tokens", 0),
            completion_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
        )

        return LLMResponse(
            content=content,
            model=data.get("model", request.model),
            usage=usage,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream a completion response from Anthropic."""
        request.stream = True
        payload = self._build_payload(request)

        async with self._client.stream(
            "POST", self._base_url, headers=self._headers(), json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    import json

                    event = json.loads(line[6:])
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield delta.get("text", "")

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
