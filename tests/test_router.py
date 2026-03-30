"""Tests for the Efficiency & Routing pillar."""

from __future__ import annotations

import pytest

from pillar6.config.models import RouterConfig
from pillar6.core.router import DefaultRouter
from pillar6.types import (
    LLMRequest,
    LLMResponse,
    ModelProfile,
    ModelTier,
    RouteConstraints,
    TokenUsage,
)


@pytest.fixture
def router() -> DefaultRouter:
    return DefaultRouter(
        RouterConfig(
            default_model="claude-sonnet-4-20250514",
            fallback_models=["gpt-4o", "gpt-3.5-turbo"],
            model_tiers={"gpt-4o": ModelTier.POWERFUL, "gpt-3.5-turbo": ModelTier.FAST},
        )
    )


# --- Routing ---


async def test_route_default_model(router: DefaultRouter) -> None:
    model = await router.route(LLMRequest())
    assert model == "claude-sonnet-4-20250514"


async def test_route_respects_request_model(router: DefaultRouter) -> None:
    model = await router.route(LLMRequest(model="custom-model"))
    assert model == "custom-model"


async def test_route_by_tier(router: DefaultRouter) -> None:
    model = await router.route(
        LLMRequest(),
        RouteConstraints(preferred_tier=ModelTier.FAST),
    )
    # Should pick a FAST tier model
    profile = router._profiles.get(model)
    assert profile is not None
    assert profile.tier == ModelTier.FAST


async def test_route_respects_latency_constraint() -> None:
    router = DefaultRouter()
    model = await router.route(
        LLMRequest(),
        RouteConstraints(max_latency_ms=500),
    )
    profile = router._profiles.get(model)
    # Should pick a model with low latency
    assert profile is not None
    assert profile.avg_latency_ms <= 500


async def test_route_respects_cost_constraint() -> None:
    router = DefaultRouter()
    model = await router.route(
        LLMRequest(),
        RouteConstraints(max_cost_per_token=0.001),
    )
    # Should find a cheap model
    assert model != ""


# --- Fallbacks ---


async def test_get_fallback(router: DefaultRouter) -> None:
    fb = await router.get_fallback("claude-sonnet-4-20250514")
    assert fb == "gpt-4o"  # first in the fallback chain


async def test_get_fallback_unknown_model(router: DefaultRouter) -> None:
    fb = await router.get_fallback("unknown-model")
    assert fb is None


async def test_get_fallback_last_in_chain(router: DefaultRouter) -> None:
    fb = await router.get_fallback("gpt-3.5-turbo")
    assert fb is None  # not in any chain


async def test_next_fallback_skips_tried() -> None:
    router = DefaultRouter()
    fb = await router.get_next_fallback(
        "claude-sonnet-4-20250514",
        already_tried=["gpt-4o"],
    )
    assert fb == "claude-haiku-4-5-20251001"


# --- Cost tracking ---


async def test_track_cost_and_summary(router: DefaultRouter) -> None:
    usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    await router.track_cost("agent-1", "gpt-4o", usage)

    summary = await router.get_cost_summary("agent-1")
    assert summary.total_tokens == 150
    assert summary.total_cost_usd > 0
    assert len(summary.entries) == 1


async def test_global_cost_summary(router: DefaultRouter) -> None:
    usage_a = TokenUsage(prompt_tokens=50, completion_tokens=50, total_tokens=100)
    usage_b = TokenUsage(prompt_tokens=100, completion_tokens=100, total_tokens=200)
    await router.track_cost("a1", "gpt-4o", usage_a)
    await router.track_cost("a2", "gpt-4o", usage_b)

    summary = await router.get_cost_summary()
    assert summary.total_tokens == 300
    assert len(summary.by_agent) == 2


async def test_cost_summary_per_model() -> None:
    router = DefaultRouter()
    usage = TokenUsage(prompt_tokens=100, completion_tokens=100, total_tokens=200)
    await router.track_cost("a1", "gpt-4o", usage)
    await router.track_cost("a1", "claude-sonnet-4-20250514", usage)

    summary = await router.get_cost_summary("a1")
    assert len(summary.by_model) == 2


# --- Semantic caching ---


async def test_cache_hit() -> None:
    router = DefaultRouter(RouterConfig(enable_caching=True, cache_ttl_seconds=60))
    resp = LLMResponse(content="cached answer", model="test")
    router.store_cache("model", "sys", "user msg", resp)

    cached = router.check_cache("model", "sys", "user msg")
    assert cached is not None
    assert cached.content == "cached answer"


async def test_cache_miss() -> None:
    router = DefaultRouter(RouterConfig(enable_caching=True))
    cached = router.check_cache("model", "sys", "no such message")
    assert cached is None


async def test_cache_expires() -> None:
    router = DefaultRouter(RouterConfig(enable_caching=True, cache_ttl_seconds=0))
    resp = LLMResponse(content="cached answer", model="test")
    router.store_cache("model", "sys", "user msg", resp)

    # TTL=0 means immediately expired
    cached = router.check_cache("model", "sys", "user msg")
    assert cached is None


async def test_cache_disabled() -> None:
    router = DefaultRouter(RouterConfig(enable_caching=False))
    resp = LLMResponse(content="cached answer", model="test")
    router.store_cache("model", "sys", "user msg", resp)
    cached = router.check_cache("model", "sys", "user msg")
    assert cached is None


# --- Custom model profile ---


async def test_custom_model_profile() -> None:
    router = DefaultRouter()
    router.register_model(
        ModelProfile(
            name="custom-model",
            tier=ModelTier.POWERFUL,
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.03,
            avg_latency_ms=500,
        )
    )
    model = await router.route(
        LLMRequest(),
        RouteConstraints(preferred_tier=ModelTier.POWERFUL),
    )
    # custom-model or gpt-4o both qualify; just verify we get a POWERFUL model
    profile = router._profiles.get(model)
    assert profile is not None
    assert profile.tier == ModelTier.POWERFUL
