"""Efficiency & Routing pillar — multi-model routing and cost tracking.

Provides the abstract interface and a default implementation for routing LLM
requests to the most appropriate model based on constraints, with fallback
chains and cost tracking.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from pillar6.config.models import RouterConfig
from pillar6.types import CostSummary, LLMRequest, RouteConstraints, TokenUsage

logger = logging.getLogger(__name__)


class Router(ABC):
    """Abstract base class for LLM request routing."""

    @abstractmethod
    async def route(self, request: LLMRequest, constraints: RouteConstraints | None = None) -> str:
        """Select the best model for the given request.

        Args:
            request: The LLM request to route.
            constraints: Optional constraints to consider.

        Returns:
            Model identifier string.
        """

    @abstractmethod
    async def get_fallback(self, failed_model: str) -> str | None:
        """Get the next fallback model after a failure.

        Args:
            failed_model: The model that failed.

        Returns:
            Next fallback model identifier, or None if none available.
        """

    @abstractmethod
    async def track_cost(self, agent_id: str, model: str, tokens: TokenUsage) -> None:
        """Track token usage and cost for an agent.

        Args:
            agent_id: Agent identifier.
            model: Model identifier that was used.
            tokens: Token usage statistics.
        """

    @abstractmethod
    async def get_cost_summary(self, agent_id: str | None = None) -> CostSummary:
        """Get a summary of costs, optionally filtered by agent.

        Args:
            agent_id: Optional agent to filter by. None returns global summary.

        Returns:
            Cost summary.
        """


class DefaultRouter(Router):
    """Default router that returns the configured model with simple fallback."""

    # Rough cost estimates per 1K tokens (USD) for default tracking.
    _COST_PER_1K: dict[str, float] = {
        "claude-sonnet-4-20250514": 0.003,
        "gpt-4o": 0.005,
    }

    def __init__(self, config: RouterConfig | None = None) -> None:
        self._config = config or RouterConfig()
        self._costs: dict[str, dict[str, float]] = {}  # agent_id -> {model: cost}
        self._token_totals: dict[str, int] = {}  # agent_id -> total_tokens

    async def route(self, request: LLMRequest, constraints: RouteConstraints | None = None) -> str:
        """Return the default model (constraint-aware routing is Phase 1)."""
        if request.model:
            return request.model
        if constraints and constraints.preferred_tier:
            tier_models = {v: k for k, v in self._config.model_tiers.items()}
            if constraints.preferred_tier in tier_models:
                return tier_models[constraints.preferred_tier]
        return self._config.default_model

    async def get_fallback(self, failed_model: str) -> str | None:
        """Return the next fallback model in the chain."""
        fallbacks = self._config.fallback_models
        if failed_model in fallbacks:
            idx = fallbacks.index(failed_model)
            if idx + 1 < len(fallbacks):
                return fallbacks[idx + 1]
            return None
        return fallbacks[0] if fallbacks else None

    async def track_cost(self, agent_id: str, model: str, tokens: TokenUsage) -> None:
        """Record token usage and estimated cost."""
        cost_rate = self._COST_PER_1K.get(model, 0.003)
        cost = (tokens.total_tokens / 1000) * cost_rate

        if agent_id not in self._costs:
            self._costs[agent_id] = {}
        self._costs[agent_id][model] = self._costs[agent_id].get(model, 0.0) + cost
        self._token_totals[agent_id] = self._token_totals.get(agent_id, 0) + tokens.total_tokens

        logger.debug(
            "Tracked cost for agent=%s model=%s tokens=%d cost=$%.4f",
            agent_id,
            model,
            tokens.total_tokens,
            cost,
        )

    async def get_cost_summary(self, agent_id: str | None = None) -> CostSummary:
        """Build a cost summary, optionally filtered to a single agent."""
        if agent_id:
            agent_models = self._costs.get(agent_id, {})
            agent_tokens = self._token_totals.get(agent_id, 0)
            agent_cost = sum(agent_models.values())
            return CostSummary(
                total_tokens=agent_tokens,
                total_cost_usd=agent_cost,
                by_model=dict(agent_models),
                by_agent={agent_id: agent_cost},
            )

        all_by_model: dict[str, float] = {}
        all_by_agent: dict[str, float] = {}
        all_tokens = 0
        for aid, models in self._costs.items():
            agent_total = sum(models.values())
            all_by_agent[aid] = agent_total
            for model, cost in models.items():
                all_by_model[model] = all_by_model.get(model, 0.0) + cost
        for t in self._token_totals.values():
            all_tokens += t

        return CostSummary(
            total_tokens=all_tokens,
            total_cost_usd=sum(all_by_agent.values()),
            by_model=all_by_model,
            by_agent=all_by_agent,
        )
