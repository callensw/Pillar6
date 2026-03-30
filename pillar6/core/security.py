"""Security & Guardrails pillar — permissions, validation, and audit.

Provides the abstract interface and a default implementation for input/output
validation, permission checks, budget enforcement, and audit logging.
"""

from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any

from pillar6.config.models import SecurityConfig
from pillar6.types import BudgetCheck, ValidationResult

logger = logging.getLogger(__name__)


class GuardrailEngine(ABC):
    """Abstract base class for the security and guardrails engine."""

    @abstractmethod
    async def check_input(self, input_text: str, agent_id: str) -> ValidationResult:
        """Validate input text before it reaches the LLM.

        Args:
            input_text: Raw input text.
            agent_id: Identifier of the requesting agent.

        Returns:
            Validation result indicating pass or fail with reasons.
        """

    @abstractmethod
    async def check_output(
        self, output: Any, schema: dict[str, Any] | None = None
    ) -> ValidationResult:
        """Validate LLM output against an optional schema.

        Args:
            output: The output to validate.
            schema: Optional JSON schema to validate against.

        Returns:
            Validation result.
        """

    @abstractmethod
    async def check_permissions(self, agent_id: str, tool_name: str) -> bool:
        """Check whether an agent is allowed to use a given tool.

        Args:
            agent_id: Agent identifier.
            tool_name: Name of the tool.

        Returns:
            True if allowed, False otherwise.
        """

    @abstractmethod
    async def check_budget(self, agent_id: str, estimated_tokens: int) -> BudgetCheck:
        """Check whether the agent has sufficient token budget.

        Args:
            agent_id: Agent identifier.
            estimated_tokens: Number of tokens the next call is expected to use.

        Returns:
            Budget check result.
        """

    @abstractmethod
    async def log_action(self, agent_id: str, action: str, details: dict[str, Any]) -> None:
        """Record an auditable action.

        Args:
            agent_id: Agent identifier.
            action: Description of the action.
            details: Additional details about the action.
        """


class DefaultGuardrailEngine(GuardrailEngine):
    """Default guardrail engine with basic input validation and budget tracking."""

    def __init__(self, config: SecurityConfig | None = None) -> None:
        self._config = config or SecurityConfig()
        self._usage: dict[str, int] = {}
        self._audit_log: list[dict[str, Any]] = []

    async def check_input(self, input_text: str, agent_id: str) -> ValidationResult:
        """Validate input length and blocked patterns."""
        violations: list[str] = []

        if not self._config.enable_input_validation:
            return ValidationResult(passed=True)

        if len(input_text) > self._config.max_input_length:
            violations.append(
                f"Input length {len(input_text)} exceeds maximum {self._config.max_input_length}"
            )

        for pattern in self._config.blocked_patterns:
            if re.search(pattern, input_text, re.IGNORECASE):
                violations.append(f"Input matches blocked pattern: {pattern}")

        passed = len(violations) == 0
        return ValidationResult(passed=passed, violations=violations)

    async def check_output(
        self, output: Any, schema: dict[str, Any] | None = None
    ) -> ValidationResult:
        """Validate that output is non-empty (schema validation is a Phase 1 feature)."""
        if not self._config.enable_output_validation:
            return ValidationResult(passed=True)

        violations: list[str] = []
        if output is None:
            violations.append("Output is None")

        return ValidationResult(passed=len(violations) == 0, violations=violations)

    async def check_permissions(self, agent_id: str, tool_name: str) -> bool:
        """Check tool permissions against the allow list."""
        if not self._config.enable_permissions:
            return True
        if not self._config.allowed_tools:
            return True
        return tool_name in self._config.allowed_tools

    async def check_budget(self, agent_id: str, estimated_tokens: int) -> BudgetCheck:
        """Check the agent's remaining token budget."""
        used = self._usage.get(agent_id, 0)
        budget = self._config.token_budget_per_agent
        remaining = budget - used
        allowed = estimated_tokens <= remaining

        return BudgetCheck(
            allowed=allowed,
            remaining_tokens=remaining,
            total_budget=budget,
            used_tokens=used,
            message="" if allowed else "Token budget exceeded",
        )

    async def log_action(self, agent_id: str, action: str, details: dict[str, Any]) -> None:
        """Append an action to the in-memory audit log."""
        entry = {
            "agent_id": agent_id,
            "action": action,
            "details": details,
            "timestamp": time.time(),
        }
        self._audit_log.append(entry)
        logger.debug("Audit: agent=%s action=%s", agent_id, action)

    def record_usage(self, agent_id: str, tokens: int) -> None:
        """Record token usage for budget tracking.

        Args:
            agent_id: Agent identifier.
            tokens: Number of tokens consumed.
        """
        self._usage[agent_id] = self._usage.get(agent_id, 0) + tokens
