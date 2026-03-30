"""Tests for the Efficiency & Routing pillar."""

from __future__ import annotations

import pytest

from pillar6.config.models import RouterConfig
from pillar6.core.router import DefaultRouter
from pillar6.types import LLMRequest, ModelTier, RouteConstraints, TokenUsage


@pytest.fixture
def router() -> DefaultRouter:
    return DefaultRouter(
        RouterConfig(
            default_model="claude-sonnet-4-20250514",
            fallback_models=["gpt-4o", "gpt-3.5-turbo"],
            model_tiers={"gpt-4o": ModelTier.POWERFUL, "gpt-3.5-turbo": ModelTier.FAST},
        )
    )


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
    assert model == "gpt-3.5-turbo"


async def test_get_fallback(router: DefaultRouter) -> None:
    fb = await router.get_fallback("gpt-4o")
    assert fb == "gpt-3.5-turbo"


async def test_get_fallback_last_in_chain(router: DefaultRouter) -> None:
    fb = await router.get_fallback("gpt-3.5-turbo")
    assert fb is None


async def test_get_fallback_unknown_model(router: DefaultRouter) -> None:
    fb = await router.get_fallback("unknown-model")
    assert fb == "gpt-4o"  # first fallback


async def test_track_cost_and_summary(router: DefaultRouter) -> None:
    usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    await router.track_cost("agent-1", "gpt-4o", usage)

    summary = await router.get_cost_summary("agent-1")
    assert summary.total_tokens == 150
    assert summary.total_cost_usd > 0


async def test_global_cost_summary(router: DefaultRouter) -> None:
    await router.track_cost("a1", "gpt-4o", TokenUsage(total_tokens=100))
    await router.track_cost("a2", "gpt-4o", TokenUsage(total_tokens=200))

    summary = await router.get_cost_summary()
    assert summary.total_tokens == 300
    assert len(summary.by_agent) == 2
