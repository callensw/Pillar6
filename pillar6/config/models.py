"""Pydantic v2 configuration models for every Pillar6 pillar."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from pillar6.types import ModelTier, RetryStrategy


class ContextConfig(BaseModel):
    """Configuration for the Context Management pillar."""

    default_token_budget: int = Field(default=4096, ge=1)
    compression_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Compress when usage exceeds this fraction of the budget.",
    )
    max_messages: int = Field(default=100, ge=1)
    enable_persistence: bool = False
    # Priority budget allocation (fraction of total)
    system_budget_fraction: float = Field(default=0.20, ge=0.0, le=1.0)
    recent_budget_fraction: float = Field(default=0.40, ge=0.0, le=1.0)
    retrieved_budget_fraction: float = Field(default=0.25, ge=0.0, le=1.0)
    ephemeral_budget_fraction: float = Field(default=0.15, ge=0.0, le=1.0)
    # Compression settings
    compression_keep_recent: int = Field(
        default=5,
        ge=1,
        description="Number of most-recent messages to keep during compression.",
    )

    @model_validator(mode="after")
    def _check_budget_fractions(self) -> ContextConfig:
        total = (
            self.system_budget_fraction
            + self.recent_budget_fraction
            + self.retrieved_budget_fraction
            + self.ephemeral_budget_fraction
        )
        if not (0.99 <= total <= 1.01):
            msg = f"Budget fractions must sum to 1.0, got {total:.2f}"
            raise ValueError(msg)
        return self


class ToolConfig(BaseModel):
    """Configuration for the Tool Orchestration pillar."""

    max_retries: int = Field(default=3, ge=0)
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retry_base_delay_ms: float = Field(default=500.0, ge=0.0)
    timeout_ms: float = Field(default=30_000.0, ge=0.0)
    max_concurrency: int = Field(default=5, ge=1)
    circuit_breaker_threshold: int = Field(default=5, ge=1)
    circuit_breaker_reset_ms: float = Field(default=60_000.0, ge=0.0)
    cache_ttl_seconds: float = Field(default=0.0, ge=0.0)


class SecurityConfig(BaseModel):
    """Configuration for the Security & Guardrails pillar."""

    enable_input_validation: bool = True
    enable_output_validation: bool = True
    enable_permissions: bool = True
    max_input_length: int = Field(default=100_000, ge=1)
    token_budget_per_agent: int = Field(default=1_000_000, ge=0)
    allowed_tools: list[str] = Field(default_factory=list)
    blocked_patterns: list[str] = Field(default_factory=list)
    default_deny: bool = True


class RouterConfig(BaseModel):
    """Configuration for the Efficiency & Routing pillar."""

    default_model: str = "claude-sonnet-4-20250514"
    fallback_models: list[str] = Field(default_factory=list)
    model_tiers: dict[str, ModelTier] = Field(default_factory=dict)
    enable_caching: bool = False
    cache_ttl_seconds: int = Field(default=300, ge=0)
    max_cost_usd: float = Field(default=10.0, ge=0.0)


class ObservabilityConfig(BaseModel):
    """Configuration for the Observability pillar."""

    enable_tracing: bool = True
    enable_metrics: bool = True
    log_level: str = "INFO"
    trace_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    export_endpoint: str | None = None


class EvalConfig(BaseModel):
    """Configuration for the Testing & Evaluation pillar."""

    enable_auto_eval: bool = False
    default_judge_model: str = "claude-sonnet-4-20250514"
    pass_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_parallel_evals: int = Field(default=3, ge=1)


class AgentConfig(BaseModel):
    """Per-agent configuration."""

    agent_id: str = "default"
    name: str = "Agent"
    model: str = "claude-sonnet-4-20250514"
    system_prompt: str = "You are a helpful assistant."
    max_turns: int = Field(default=10, ge=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1)


class Pillar6Config(BaseModel):
    """Top-level configuration composing all six pillars."""

    context: ContextConfig = Field(default_factory=ContextConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    router: RouterConfig = Field(default_factory=RouterConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    eval: EvalConfig = Field(default_factory=EvalConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
