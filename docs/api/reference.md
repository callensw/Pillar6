# API Reference

Auto-generated reference for all public Pillar6 classes and functions.

## Core Types

::: pillar6.types
    options:
      members:
        - Priority
        - Role
        - ModelTier
        - Message
        - ToolCall
        - ToolResult
        - ToolHealth
        - TokenUsage
        - LLMRequest
        - LLMResponse
        - ValidationResult
        - BudgetCheck
        - RouteConstraints
        - CostEntry
        - CostSummary
        - ModelProfile
        - TraceContext
        - TraceEvent
        - LogEntry
        - AuditEntry
        - EvalResult
        - EvalDataset
        - EvalItem
        - EvalReport
        - ComparisonReport
        - ExecutionContext
        - ContextSnapshot

## Configuration

::: pillar6.config.models
    options:
      members:
        - Pillar6Config
        - ContextConfig
        - ToolConfig
        - SecurityConfig
        - RouterConfig
        - ObservabilityConfig
        - EvalConfig
        - AgentConfig

## Agents

::: pillar6.agents.base
    options:
      members:
        - BaseAgent
        - Pillar6Error

## Agent Patterns

::: pillar6.agents.patterns.react
    options:
      members:
        - ReActAgent
        - ReActConfig

::: pillar6.agents.patterns.plan_execute
    options:
      members:
        - PlanExecuteAgent
        - PlanExecuteConfig
        - PlanStep

::: pillar6.agents.patterns.supervisor
    options:
      members:
        - SupervisorAgent
        - SupervisorConfig

## Context Management

::: pillar6.core.context
    options:
      members:
        - ContextManager
        - DefaultContextManager

## Tool Orchestration

::: pillar6.core.tools
    options:
      members:
        - ToolRegistry
        - ToolExecutor
        - DefaultToolRegistry
        - DefaultToolExecutor
        - ToolCircuitOpenError
        - ToolValidationError

## Security & Guardrails

::: pillar6.core.security
    options:
      members:
        - GuardrailEngine
        - DefaultGuardrailEngine
        - InputValidator
        - MaxLengthValidator
        - PromptInjectionDetector
        - PatternBlocklistValidator

## Routing

::: pillar6.core.router
    options:
      members:
        - Router
        - DefaultRouter

## Observability

::: pillar6.core.observability
    options:
      members:
        - ObservabilityLayer
        - DefaultObservabilityLayer

## Evaluation

::: pillar6.core.eval
    options:
      members:
        - EvalSuite
        - DefaultEvalSuite
        - MockLLMAdapter
        - ChaosToolWrapper

## LLM Adapters

::: pillar6.adapters.base
    options:
      members:
        - LLMAdapter
