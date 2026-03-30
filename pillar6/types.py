"""Shared type definitions and enums for the Pillar6 framework."""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Priority(enum.StrEnum):
    """Priority level for context entries."""

    SYSTEM = "system"
    RECENT = "recent"
    RETRIEVED = "retrieved"
    EPHEMERAL = "ephemeral"


class RetryStrategy(enum.StrEnum):
    """Retry back-off strategies for tool execution."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CUSTOM = "custom"


class CircuitBreakerState(enum.StrEnum):
    """States for the circuit-breaker pattern."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ModelTier(enum.StrEnum):
    """LLM model tier classification."""

    FAST = "fast"
    BALANCED = "balanced"
    POWERFUL = "powerful"


class Role(enum.StrEnum):
    """Message role within a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------


class Message(BaseModel):
    """A single message in a conversation context."""

    role: Role
    content: str
    priority: Priority = Priority.RECENT
    token_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """Represents a request to invoke a tool."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    call_id: str = ""


class ToolResult(BaseModel):
    """Result returned after a tool execution."""

    call_id: str = ""
    tool_name: str
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    success: bool = True


class ToolHealth(BaseModel):
    """Health status of a registered tool."""

    tool_name: str
    healthy: bool = True
    last_check_ms: float = 0.0
    message: str = ""


class RegisteredTool(BaseModel, arbitrary_types_allowed=True):
    """A tool registered in the ToolRegistry."""

    name: str
    tool_schema: dict[str, Any] = Field(default_factory=dict)
    handler: Any = None  # Callable stored at runtime


class TokenUsage(BaseModel):
    """Token usage statistics for a single LLM call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMRequest(BaseModel):
    """A request to an LLM adapter."""

    messages: list[Message] = Field(default_factory=list)
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 1024
    tools: list[dict[str, Any]] = Field(default_factory=list)
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Response from an LLM adapter."""

    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    model: str = ""
    usage: TokenUsage = Field(default_factory=TokenUsage)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextSnapshot(BaseModel):
    """A serializable snapshot of an agent's context window."""

    agent_id: str
    messages: list[Message] = Field(default_factory=list)
    token_budget: int = 0
    used_tokens: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionContext(BaseModel):
    """Runtime context passed to tool executors."""

    agent_id: str = ""
    workflow_id: str = ""
    trace_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Result of a guardrail validation check."""

    passed: bool = True
    violations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BudgetCheck(BaseModel):
    """Result of a budget check."""

    allowed: bool = True
    remaining_tokens: int = 0
    total_budget: int = 0
    used_tokens: int = 0
    message: str = ""


class RouteConstraints(BaseModel):
    """Constraints for model routing decisions."""

    max_latency_ms: float | None = None
    max_cost_per_token: float | None = None
    preferred_tier: ModelTier | None = None
    required_capabilities: list[str] = Field(default_factory=list)


class CostSummary(BaseModel):
    """Summary of costs incurred by agents."""

    total_tokens: int = 0
    total_cost_usd: float = 0.0
    by_model: dict[str, float] = Field(default_factory=dict)
    by_agent: dict[str, float] = Field(default_factory=dict)


class TraceContext(BaseModel):
    """Context for distributed tracing."""

    workflow_id: str
    trace_id: str = ""
    parent_id: str | None = None
    start_time_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    """A single event in a trace."""

    event_type: str
    timestamp_ms: float = 0.0
    trace_id: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    message: str = ""


class EvalResult(BaseModel):
    """Result of a single evaluation."""

    score: float = 0.0
    passed: bool = True
    reasoning: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalDataset(BaseModel):
    """A dataset used for evaluation."""

    name: str = ""
    items: list[EvalItem] = Field(default_factory=list)


class EvalItem(BaseModel):
    """A single item in an evaluation dataset."""

    input: str
    expected_output: str = ""
    rubric: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalReport(BaseModel):
    """Aggregated evaluation report."""

    dataset_name: str = ""
    results: list[EvalResult] = Field(default_factory=list)
    avg_score: float = 0.0
    pass_rate: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComparisonReport(BaseModel):
    """Comparison between two evaluation reports."""

    report_a_name: str = ""
    report_b_name: str = ""
    score_diff: float = 0.0
    pass_rate_diff: float = 0.0
    improved: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
