"""Tests for LLM adapters.

These tests verify adapter construction and payload building without making
real HTTP calls.
"""

from __future__ import annotations

from pillar6.adapters.anthropic import AnthropicAdapter
from pillar6.adapters.openai import OpenAIAdapter
from pillar6.types import LLMRequest, Message, Role


def test_anthropic_adapter_init() -> None:
    adapter = AnthropicAdapter(api_key="test-key")
    assert adapter._api_key == "test-key"


def test_anthropic_build_payload() -> None:
    adapter = AnthropicAdapter(api_key="test-key")
    request = LLMRequest(
        messages=[
            Message(role=Role.SYSTEM, content="You are helpful."),
            Message(role=Role.USER, content="Hi"),
        ],
        max_tokens=100,
        temperature=0.5,
    )
    payload = adapter._build_payload(request)
    assert payload["max_tokens"] == 100
    assert payload["temperature"] == 0.5
    assert payload["system"] == "You are helpful."
    # System messages should be extracted, not in messages list
    assert all(m["role"] != "system" for m in payload["messages"])


def test_openai_adapter_init() -> None:
    adapter = OpenAIAdapter(api_key="test-key")
    assert adapter._api_key == "test-key"


def test_openai_build_payload() -> None:
    adapter = OpenAIAdapter(api_key="test-key")
    request = LLMRequest(
        messages=[
            Message(role=Role.SYSTEM, content="You are helpful."),
            Message(role=Role.USER, content="Hi"),
        ],
        max_tokens=200,
        temperature=0.3,
    )
    payload = adapter._build_payload(request)
    assert payload["max_tokens"] == 200
    assert payload["temperature"] == 0.3
    assert len(payload["messages"]) == 2
    assert payload["messages"][0]["role"] == "system"


def test_anthropic_default_model() -> None:
    adapter = AnthropicAdapter(api_key="k", default_model="my-model")
    request = LLMRequest(messages=[Message(role=Role.USER, content="Hi")])
    payload = adapter._build_payload(request)
    assert payload["model"] == "my-model"


def test_openai_default_model() -> None:
    adapter = OpenAIAdapter(api_key="k", default_model="my-model")
    request = LLMRequest(messages=[Message(role=Role.USER, content="Hi")])
    payload = adapter._build_payload(request)
    assert payload["model"] == "my-model"
