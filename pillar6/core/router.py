"""Efficiency & Routing pillar — multi-model routing and cost tracking.

Provides the abstract interface and a default implementation for routing LLM
requests to the most appropriate model based on constraints, with fallback
chains, cost tracking, and semantic caching.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod

from pillar6.config.models import RouterConfig
from pillar6.types import (
    CostEntry,
    CostSummary,
    LLMRequest,
    LLMResponse,
    ModelProfile,
    ModelTier,
    RouteConstraints,
    TokenUsage,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pre-configured model profiles
# ---------------------------------------------------------------------------

_DEFAULT_PROFILES: list[ModelProfile] = [
    ModelProfile(
        name="claude-sonnet-4-20250514",
        tier=ModelTier.BALANCED,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        avg_latency_ms=800,
        max_tokens=8192,
        provider="anthropic",
    ),
    ModelProfile(
        name="claude-haiku-4-5-20251001",
        tier=ModelTier.FAST,
        cost_per_1k_input=0.001,
        cost_per_1k_output=0.005,
        avg_latency_ms=400,
        max_tokens=8192,
        provider="anthropic",
    ),
    ModelProfile(
        name="gpt-4o",
        tier=ModelTier.POWERFUL,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.015,
        avg_latency_ms=1000,
        max_tokens=4096,
        provider="openai",
    ),
    ModelProfile(
        name="gpt-4o-mini",
        tier=ModelTier.FAST,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
        avg_latency_ms=300,
        max_tokens=4096,
        provider="openai",
    ),
]

# Default fallback chains
_DEFAULT_FALLBACKS: dict[str, list[str]] = {
    "claude-sonnet-4-20250514": ["gpt-4o", "claude-haiku-4-5-20251001"],
    "gpt-4o": ["claude-sonnet-4-20250514", "gpt-4o-mini"],
}


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
    """Default router with model selection, fallbacks, cost tracking, and caching."""

    def __init__(self, config: RouterConfig | None = None) -> None:
        self._config = config or RouterConfig()
        self._profiles: dict[str, ModelProfile] = {}
        self._fallbacks: dict[str, list[str]] = dict(_DEFAULT_FALLBACKS)
        self._cost_entries: list[CostEntry] = []
        self._cache: dict[str, tuple[float, LLMResponse]] = {}

        # Register default profiles
        for profile in _DEFAULT_PROFILES:
            self._profiles[profile.name] = profile

        # Register config-specified tiers into profiles
        for model_name, tier in self._config.model_tiers.items():
            if model_name not in self._profiles:
                self._profiles[model_name] = ModelProfile(name=model_name, tier=tier)
            else:
                self._profiles[model_name].tier = tier

        # Register config fallback models
        if self._config.fallback_models:
            self._fallbacks[self._config.default_model] = list(self._config.fallback_models)

    def register_model(self, profile: ModelProfile) -> None:
        """Register or update a model profile.

        Args:
            profile: The model profile to register.
        """
        self._profiles[profile.name] = profile
        logger.debug("Registered model profile: %s", profile.name)

    def set_fallbacks(self, model: str, fallbacks: list[str]) -> None:
        """Set the fallback chain for a model.

        Args:
            model: Primary model name.
            fallbacks: Ordered list of fallback model names.
        """
        self._fallbacks[model] = fallbacks

    async def route(self, request: LLMRequest, constraints: RouteConstraints | None = None) -> str:
        """Select a model based on constraints, falling back to the configured default."""
        # If the request already specifies a model, use it
        if request.model:
            return request.model

        if constraints is None:
            return self._config.default_model

        # Filter candidates by constraints
        candidates: list[ModelProfile] = []
        for profile in self._profiles.values():
            if (
                constraints.preferred_tier is not None
                and profile.tier != constraints.preferred_tier
            ):
                continue
            if (
                constraints.max_latency_ms is not None
                and profile.avg_latency_ms > constraints.max_latency_ms
            ):
                continue
            if constraints.max_cost_per_token is not None:
                avg_cost = (profile.cost_per_1k_input + profile.cost_per_1k_output) / 2 / 1000
                if avg_cost > constraints.max_cost_per_token:
                    continue
            candidates.append(profile)

        if not candidates:
            return self._config.default_model

        # Rank by cost-efficiency (lower average cost per 1k wins for same tier)
        candidates.sort(key=lambda p: p.cost_per_1k_input + p.cost_per_1k_output)
        return candidates[0].name

    async def get_fallback(self, failed_model: str) -> str | None:
        """Return the next fallback model in the chain."""
        chain = self._fallbacks.get(failed_model)
        if not chain:
            return None
        return chain[0]

    async def get_next_fallback(self, failed_model: str, already_tried: list[str]) -> str | None:
        """Return the next untried fallback for a model.

        Args:
            failed_model: The model that failed.
            already_tried: Models already attempted.

        Returns:
            Next fallback, or None if all exhausted.
        """
        chain = self._fallbacks.get(failed_model, [])
        for model in chain:
            if model not in already_tried:
                return model
        return None

    async def track_cost(self, agent_id: str, model: str, tokens: TokenUsage) -> None:
        """Record token usage and estimated cost."""
        profile = self._profiles.get(model)
        if profile:
            input_cost = (tokens.prompt_tokens / 1000) * profile.cost_per_1k_input
            output_cost = (tokens.completion_tokens / 1000) * profile.cost_per_1k_output
            cost = input_cost + output_cost
        else:
            cost = (tokens.total_tokens / 1000) * 0.003  # fallback rate

        entry = CostEntry(
            timestamp=time.time(),
            agent_id=agent_id,
            model=model,
            tokens=tokens.total_tokens,
            cost_usd=cost,
        )
        self._cost_entries.append(entry)

        logger.debug(
            "Tracked cost for agent=%s model=%s tokens=%d cost=$%.6f",
            agent_id,
            model,
            tokens.total_tokens,
            cost,
        )

    async def get_cost_summary(self, agent_id: str | None = None) -> CostSummary:
        """Build a cost summary from recorded entries."""
        entries = self._cost_entries
        if agent_id:
            entries = [e for e in entries if e.agent_id == agent_id]

        total_tokens = sum(e.tokens for e in entries)
        total_cost = sum(e.cost_usd for e in entries)

        by_model: dict[str, float] = {}
        by_agent: dict[str, float] = {}
        for e in entries:
            by_model[e.model] = by_model.get(e.model, 0.0) + e.cost_usd
            by_agent[e.agent_id] = by_agent.get(e.agent_id, 0.0) + e.cost_usd

        return CostSummary(
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
            by_model=by_model,
            by_agent=by_agent,
            entries=list(entries),
        )

    # --- Semantic caching ---

    def _cache_key(self, model: str, system_prompt: str, last_user_msg: str) -> str:
        """Generate a cache key from model, system prompt, and last user message."""
        raw = json.dumps(
            {"model": model, "system": system_prompt, "user": last_user_msg}, sort_keys=True
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def check_cache(self, model: str, system_prompt: str, last_user_msg: str) -> LLMResponse | None:
        """Check the semantic cache for a matching response.

        Args:
            model: Model identifier.
            system_prompt: System prompt text.
            last_user_msg: Last user message text.

        Returns:
            Cached LLMResponse if found and not expired, else None.
        """
        if not self._config.enable_caching:
            return None
        key = self._cache_key(model, system_prompt, last_user_msg)
        cached = self._cache.get(key)
        if cached is None:
            return None
        ts, response = cached
        if (time.time() - ts) > self._config.cache_ttl_seconds:
            del self._cache[key]
            return None
        return response

    def store_cache(
        self, model: str, system_prompt: str, last_user_msg: str, response: LLMResponse
    ) -> None:
        """Store a response in the semantic cache.

        Args:
            model: Model identifier.
            system_prompt: System prompt text.
            last_user_msg: Last user message text.
            response: The LLM response to cache.
        """
        if not self._config.enable_caching:
            return
        key = self._cache_key(model, system_prompt, last_user_msg)
        self._cache[key] = (time.time(), response)
