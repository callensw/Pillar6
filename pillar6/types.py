"""Shared type definitions and enums for the Pillar6 framework."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
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
    retry_count: int = 0
    cached: bool = False


class ToolHealth(BaseModel):
    """Health status of a registered tool."""

    tool_name: str
    healthy: bool = True
    last_check_ms: float = 0.0
    message: str = ""
    circuit_breaker_state: CircuitBreakerState = CircuitBreakerState.CLOSED
    total_calls: int = 0
    total_failures: int = 0
    avg_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0


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


class CostEntry(BaseModel):
    """A single cost tracking entry."""

    timestamp: float = 0.0
    agent_id: str = ""
    model: str = ""
    tokens: int = 0
    cost_usd: float = 0.0


class CostSummary(BaseModel):
    """Summary of costs incurred by agents."""

    total_tokens: int = 0
    total_cost_usd: float = 0.0
    by_model: dict[str, float] = Field(default_factory=dict)
    by_agent: dict[str, float] = Field(default_factory=dict)
    entries: list[CostEntry] = Field(default_factory=list)


class ModelProfile(BaseModel):
    """Profile for a model used in routing decisions."""

    name: str
    tier: ModelTier = ModelTier.BALANCED
    cost_per_1k_input: float = 0.003
    cost_per_1k_output: float = 0.015
    avg_latency_ms: float = 1000.0
    max_tokens: int = 4096
    provider: str = ""


class TraceContext(BaseModel):
    """Context for distributed tracing."""

    workflow_id: str
    trace_id: str = ""
    parent_id: str | None = None
    start_time_ms: float = 0.0
    end_time_ms: float = 0.0
    total_duration_ms: float = 0.0
    completed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    """A single event in a trace."""

    event_id: str = ""
    event_type: str
    timestamp_ms: float = 0.0
    trace_id: str = ""
    agent_id: str = ""
    parent_event_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    message: str = ""


class LogEntry(BaseModel):
    """A structured log entry."""

    timestamp: str = ""
    level: str = "INFO"
    message: str = ""
    agent_id: str = ""
    workflow_id: str = ""
    trace_id: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class AuditEntry(BaseModel):
    """An entry in the security audit trail."""

    timestamp: str = ""
    agent_id: str = ""
    action: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


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

    @classmethod
    def from_list(cls, cases: list[dict[str, Any]], name: str = "") -> EvalDataset:
        """Create a dataset from a list of dicts.

        Args:
            cases: List of dicts with 'input' and optional 'expected_output', 'rubric', 'metadata'.
            name: Dataset name.

        Returns:
            EvalDataset instance.
        """
        items = [EvalItem(**case) for case in cases]
        return cls(name=name, items=items)

    @classmethod
    def from_json(cls, path: str) -> EvalDataset:
        """Load a dataset from a JSON file.

        Args:
            path: Path to a JSON file containing a list of eval cases or a dataset object.

        Returns:
            EvalDataset instance.
        """
        import json
        from pathlib import Path

        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, list):
            return cls.from_list(data, name=Path(path).stem)
        return cls.model_validate(data)


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
    total_cases: int = 0
    passed: int = 0
    failed: int = 0
    total_duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComparisonReport(BaseModel):
    """Comparison between two evaluation reports."""

    report_a_name: str = ""
    report_b_name: str = ""
    score_diff: float = 0.0
    pass_rate_diff: float = 0.0
    improved: bool = False
    improved_cases: int = 0
    regressed_cases: int = 0
    unchanged_cases: int = 0
    details: dict[str, Any] = Field(default_factory=dict)


def _now_iso() -> str:
    """Return the current time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()
