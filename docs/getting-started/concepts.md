# Concepts

## Why Six Pillars?

Every production AI agent needs the same core capabilities: manage context windows,
orchestrate tools, enforce security, route efficiently, observe behaviour, and
test reliably. Pillar6 codifies these into six explicit architectural pillars
so you don't have to reinvent them.

**How Pillar6 differs from LangChain / CrewAI:**

| Concern | LangChain | CrewAI | Pillar6 |
|---------|-----------|--------|---------|
| Architecture | Chain-of-components | Role-based crews | Six explicit pillars |
| Security | Opt-in | Minimal | Built-in guardrails, audit, permissions |
| Observability | Callbacks | Logging | First-class tracing, metrics, export |
| Testing | Manual | Manual | Mock adapters, chaos testing, eval datasets |
| Type safety | Partial | Minimal | Full Pydantic v2 + mypy strict |

## Agent Lifecycle

Every agent run follows this lifecycle:

```
INIT -> SECURITY CHECK -> CONTEXT LOAD -> ROUTE -> BUDGET CHECK -> EXECUTE -> OBSERVE -> RESPOND
```

1. **INIT** -- Create a trace, generate a workflow ID
2. **SECURITY CHECK** -- Validate input through the guardrail chain
3. **CONTEXT LOAD** -- Allocate token budget, inject system prompt and user message
4. **ROUTE** -- Select the best model based on constraints
5. **BUDGET CHECK** -- Verify the agent has sufficient token budget
6. **EXECUTE** -- Call the LLM, handle any tool calls
7. **OBSERVE** -- Emit metrics, record audit entries
8. **RESPOND** -- Validate output and return the response

## The Six Pillars

### Pillar 1: Context Management

Manages the agent's context window with priority-based message buckets and
automatic eviction when the token budget is exceeded.

**Key concepts:** Token budgets, priority buckets (SYSTEM > RECENT > RETRIEVED > EPHEMERAL),
compression, multi-agent isolation.

[Deep dive ->](../pillars/context-management.md)

### Pillar 2: Tool Orchestration

Handles tool registration, argument validation, execution with retries,
circuit breakers for fault tolerance, and result caching.

**Key concepts:** Schema validation, circuit breaker pattern, exponential backoff
with jitter, TTL-based caching, parallel execution.

[Deep dive ->](../pillars/tool-orchestration.md)

### Pillar 3: Security & Guardrails

Validates inputs and outputs, manages per-agent permissions, enforces token
budgets, and maintains an audit trail.

**Key concepts:** Validator chain, prompt injection detection, permission grants,
budget enforcement, audit logging.

[Deep dive ->](../pillars/security.md)

### Pillar 4: Efficiency & Routing

Routes requests to the optimal model based on cost, latency, and capability
constraints. Tracks costs and provides semantic caching.

**Key concepts:** Model profiles, constraint-based routing, fallback chains,
cost tracking, semantic caching.

[Deep dive ->](../pillars/routing.md)

### Pillar 5: Observability

Provides distributed tracing, structured logging, metric emission, and
trace export for debugging and replay.

**Key concepts:** Trace context, events with parent linking, structured logs,
metric filtering, JSON export.

[Deep dive ->](../pillars/observability.md)

### Pillar 6: Testing & Evaluation

Mock adapters for deterministic testing, chaos wrappers for resilience testing,
and dataset-driven evaluation with scoring and comparison.

**Key concepts:** MockLLMAdapter, ChaosToolWrapper, exact/contains/similarity
scoring, EvalDataset, comparison reports.

[Deep dive ->](../pillars/evaluation.md)

## Which Pattern Should I Use?

Pillar6 provides three agent patterns for common orchestration strategies:

| Pattern | Best for | How it works |
|---------|----------|-------------|
| [**ReAct**](../patterns/react.md) | Step-by-step reasoning with tools | Think -> Act -> Observe loop |
| [**Plan-Execute**](../patterns/plan-execute.md) | Multi-step tasks with known structure | Plan upfront, execute steps, replan on failure |
| [**Supervisor**](../patterns/supervisor.md) | Tasks requiring multiple specialties | Delegate to specialists, synthesise results |
