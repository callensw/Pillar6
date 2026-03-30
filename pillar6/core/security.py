"""Security & Guardrails pillar — permissions, validation, and audit.

Provides the abstract interface and a default implementation for input/output
validation, permission checks, budget enforcement, and audit logging.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from pillar6.config.models import SecurityConfig
from pillar6.types import AuditEntry, BudgetCheck, ValidationResult, _now_iso

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input validators
# ---------------------------------------------------------------------------


class InputValidator(ABC):
    """Abstract base class for input validation chain members."""

    @abstractmethod
    def validate(self, text: str) -> ValidationResult:
        """Validate the input text.

        Args:
            text: Raw input text.

        Returns:
            Validation result.
        """


class MaxLengthValidator(InputValidator):
    """Rejects inputs that exceed a configurable character limit."""

    def __init__(self, max_length: int = 10_000) -> None:
        self._max_length = max_length

    def validate(self, text: str) -> ValidationResult:
        """Check input length against the configured maximum."""
        if len(text) > self._max_length:
            return ValidationResult(
                passed=False,
                violations=[f"Input length {len(text)} exceeds maximum {self._max_length}"],
            )
        return ValidationResult(passed=True)


class PromptInjectionDetector(InputValidator):
    """Heuristic-based prompt injection detection.

    Flags inputs containing common injection patterns. This is intentionally
    simple — users can swap in ML-based detection for production use.
    """

    _PATTERNS: list[str] = [
        r"ignore\s+previous\s+instructions",
        r"system\s+prompt\s*:",
        r"you\s+are\s+now",
        r"forget\s+everything",
        r"\bdisregard\b",
        r"\boverride\b",
        r"new\s+instructions\s*:",
        r"do\s+not\s+follow\s+(?:your|the)\s+(?:instructions|rules)",
        r"pretend\s+you\s+are",
        r"act\s+as\s+(?:if\s+you\s+are|a)\b",
        r"\bjailbreak\b",
    ]

    def validate(self, text: str) -> ValidationResult:
        """Check for common prompt injection patterns."""
        violations: list[str] = []
        for pattern in self._PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(f"Prompt injection pattern detected: {pattern}")
        return ValidationResult(
            passed=len(violations) == 0,
            violations=violations,
        )


class PatternBlocklistValidator(InputValidator):
    """Rejects inputs matching any of the configured regex patterns."""

    def __init__(self, patterns: list[str]) -> None:
        self._patterns = patterns

    def validate(self, text: str) -> ValidationResult:
        """Check input against blocked patterns."""
        violations: list[str] = []
        for pattern in self._patterns:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(f"Input matches blocked pattern: {pattern}")
        return ValidationResult(
            passed=len(violations) == 0,
            violations=violations,
        )


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------


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

    def record_usage(self, agent_id: str, tokens: int) -> None:  # noqa: B027
        """Record token usage for budget tracking.

        Default implementation is a no-op. Override to enable budget tracking.

        Args:
            agent_id: Agent identifier.
            tokens: Number of tokens consumed.
        """


# ---------------------------------------------------------------------------
# Default implementation
# ---------------------------------------------------------------------------


class DefaultGuardrailEngine(GuardrailEngine):
    """Default guardrail engine with validation chain, permissions, budget, and audit."""

    def __init__(self, config: SecurityConfig | None = None) -> None:
        self._config = config or SecurityConfig()
        self._usage: dict[str, int] = {}
        self._audit_log: dict[str, list[AuditEntry]] = {}
        self._permissions: dict[str, set[str]] = {}
        self._validators: list[InputValidator] = []

        # Build the default validator chain from config
        if self._config.enable_input_validation:
            self._validators.append(MaxLengthValidator(self._config.max_input_length))
            self._validators.append(PromptInjectionDetector())
            if self._config.blocked_patterns:
                self._validators.append(PatternBlocklistValidator(self._config.blocked_patterns))

        # Seed permissions from config
        if self._config.allowed_tools:
            self._permissions["*"] = set(self._config.allowed_tools)

    def add_validator(self, validator: InputValidator) -> None:
        """Add a custom validator to the input validation chain.

        Args:
            validator: An InputValidator instance.
        """
        self._validators.append(validator)

    def grant_permission(self, agent_id: str, tool_name: str) -> None:
        """Grant an agent permission to use a tool.

        Args:
            agent_id: Agent identifier.
            tool_name: Name of the tool to allow.
        """
        if agent_id not in self._permissions:
            self._permissions[agent_id] = set()
        self._permissions[agent_id].add(tool_name)

    def revoke_permission(self, agent_id: str, tool_name: str) -> None:
        """Revoke an agent's permission to use a tool.

        Args:
            agent_id: Agent identifier.
            tool_name: Name of the tool to revoke.
        """
        if agent_id in self._permissions:
            self._permissions[agent_id].discard(tool_name)

    async def check_input(self, input_text: str, agent_id: str) -> ValidationResult:
        """Run input through the full validator chain."""
        if not self._config.enable_input_validation:
            return ValidationResult(passed=True)

        all_violations: list[str] = []
        for validator in self._validators:
            result = validator.validate(input_text)
            if not result.passed:
                all_violations.extend(result.violations)

        return ValidationResult(
            passed=len(all_violations) == 0,
            violations=all_violations,
        )

    async def check_output(
        self, output: Any, schema: dict[str, Any] | None = None
    ) -> ValidationResult:
        """Validate output existence and optionally check required keys and types."""
        if not self._config.enable_output_validation:
            return ValidationResult(passed=True)

        violations: list[str] = []
        if output is None:
            violations.append("Output is None")
            return ValidationResult(passed=False, violations=violations)

        if schema is not None and isinstance(output, dict):
            required = schema.get("required", [])
            properties = schema.get("properties", {})
            type_map: dict[str, type | tuple[type, ...]] = {
                "string": str,
                "integer": int,
                "number": (int, float),
                "boolean": bool,
                "array": list,
                "object": dict,
            }
            for key in required:
                if key not in output:
                    violations.append(f"Missing required key: {key}")
            for key, val in output.items():
                if key in properties:
                    expected_type = properties[key].get("type")
                    if (
                        expected_type
                        and expected_type in type_map
                        and not isinstance(val, type_map[expected_type])
                    ):
                        violations.append(
                            f"Key '{key}' expected type '{expected_type}', "
                            f"got '{type(val).__name__}'"
                        )

        return ValidationResult(passed=len(violations) == 0, violations=violations)

    async def check_permissions(self, agent_id: str, tool_name: str) -> bool:
        """Check tool permissions for an agent.

        Permission resolution:
        1. If permissions are disabled, allow all.
        2. Check agent-specific permissions first.
        3. Fall back to wildcard '*' permissions (from config allowed_tools).
        4. If default_deny is True and no permissions found, deny.
        """
        if not self._config.enable_permissions:
            return True

        # Agent-specific permissions
        agent_perms = self._permissions.get(agent_id)
        if agent_perms is not None:
            return tool_name in agent_perms

        # Wildcard permissions (from config)
        wildcard_perms = self._permissions.get("*")
        if wildcard_perms is not None:
            return tool_name in wildcard_perms

        # Default deny
        return not self._config.default_deny

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
        """Append an action to the audit log for the given agent."""
        entry = AuditEntry(
            timestamp=_now_iso(),
            agent_id=agent_id,
            action=action,
            details=details,
        )
        if agent_id not in self._audit_log:
            self._audit_log[agent_id] = []
        self._audit_log[agent_id].append(entry)
        logger.debug("Audit: agent=%s action=%s", agent_id, action)

    def get_audit_log(self, agent_id: str) -> list[AuditEntry]:
        """Return the audit log for a specific agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            List of audit entries, ordered chronologically.
        """
        return list(self._audit_log.get(agent_id, []))

    def record_usage(self, agent_id: str, tokens: int) -> None:
        """Record token usage for budget tracking.

        Args:
            agent_id: Agent identifier.
            tokens: Number of tokens consumed.
        """
        self._usage[agent_id] = self._usage.get(agent_id, 0) + tokens
