"""OpenAI LLM adapter using httpx.

Provides async access to the OpenAI Chat Completions API without pulling in the
official ``openai`` SDK, keeping Pillar6's dependency footprint small.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import httpx

from pillar6.adapters.base import LLMAdapter
from pillar6.types import LLMRequest, LLMResponse, TokenUsage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o"


class OpenAIAdapter(LLMAdapter):
    """Adapter for the OpenAI Chat Completions API.

    Args:
        api_key: OpenAI API key. Falls back to ``OPENAI_API_KEY`` env var.
        base_url: Override the API base URL (useful for Azure or proxies).
        default_model: Model to use when the request doesn't specify one.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str = _DEFAULT_MODEL,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = (base_url or _OPENAI_API_URL).rstrip("/")
        self._default_model = default_model
        self._client = httpx.AsyncClient(timeout=120.0)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, request: LLMRequest) -> dict[str, Any]:
        messages: list[dict[str, str]] = [
            {"role": m.role.value, "content": m.content} for m in request.messages
        ]
        payload: dict[str, Any] = {
            "model": request.model or self._default_model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.stream:
            payload["stream"] = True
        return payload

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to OpenAI."""
        payload = self._build_payload(request)
        resp = await self._client.post(self._base_url, headers=self._headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return LLMResponse(
            content=content,
            model=data.get("model", request.model),
            usage=usage,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream a completion response from OpenAI."""
        request.stream = True
        payload = self._build_payload(request)

        async with self._client.stream(
            "POST", self._base_url, headers=self._headers(), json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and line.strip() != "data: [DONE]":
                    event = json.loads(line[6:])
                    delta = event.get("choices", [{}])[0].get("delta", {})
                    text = delta.get("content", "")
                    if text:
                        yield text

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
