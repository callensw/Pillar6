# Concepts

## Why Pillar6?

Every production AI agent needs the same six things: context management,
tool orchestration, security, efficient routing, observability, and testing.
Most frameworks give you zero of them. Pillar6 gives you all six.

**How Pillar6 complements other frameworks:**

| Concern | LangChain | CrewAI | Raw SDK | + Pillar6 |
|---------|-----------|--------|---------|-----------|
| Security | Opt-in | Minimal | None | Built-in guardrails, audit, permissions |
| Observability | Callbacks | Logging | None | First-class tracing, metrics, export |
| Cost control | Manual | Manual | Manual | Automatic tracking, budget limits |
| Testing | Manual | Manual | Manual | Mock adapters, chaos testing, eval datasets |
| Type safety | Partial | Minimal | Varies | Full Pydantic v2 + mypy strict |

Pillar6 is not a replacement for these frameworks — it wraps around them
to add the production infrastructure they're missing.

## The Six Production Pillars

### 1. Context Management

Manages the agent's context window with priority-based message buckets and
automatic eviction when the token budget is exceeded.

**Key concepts:** Token budgets, priority buckets (SYSTEM > RECENT > RETRIEVED > EPHEMERAL),
compression, multi-agent isolation.

[Deep dive ->](../pillars/context-management.md)

### 2. Tool Orchestration

Handles tool registration, argument validation, execution with retries,
circuit breakers for fault tolerance, and result caching.

**Key concepts:** Schema validation, circuit breaker pattern, exponential backoff
with jitter, TTL-based caching, parallel execution.

[Deep dive ->](../pillars/tool-orchestration.md)

### 3. Security & Guardrails

Validates inputs and outputs, manages per-agent permissions, enforces token
budgets, and maintains an audit trail.

**Key concepts:** Validator chain, prompt injection detection, permission grants,
budget enforcement, audit logging.

[Deep dive ->](../pillars/security.md)

### 4. Efficiency & Routing

Routes requests to the optimal model based on cost, latency, and capability
constraints. Tracks costs and provides semantic caching.

**Key concepts:** Model profiles, constraint-based routing, fallback chains,
cost tracking, semantic caching.

[Deep dive ->](../pillars/routing.md)

### 5. Observability

Provides distributed tracing, structured logging, metric emission, and
trace export for debugging and replay.

**Key concepts:** Trace context, events with parent linking, structured logs,
metric filtering, JSON export.

[Deep dive ->](../pillars/observability.md)

### 6. Testing & Evaluation

Mock adapters for deterministic testing, chaos wrappers for resilience testing,
and dataset-driven evaluation with scoring and comparison.

**Key concepts:** MockLLMAdapter, ChaosToolWrapper, exact/contains/similarity
scoring, EvalDataset, comparison reports.

[Deep dive ->](../pillars/evaluation.md)

## Two Ways to Use Pillar6

### 1. Wrap existing agents (recommended starting point)

Add production infrastructure to agents built with any framework:

```python
from pillar6 import pillar6_wrap

agent = pillar6_wrap(my_existing_agent)
```

See [Add Pillar6 to Existing Agents](wrapping.md) for the full guide.

### 2. Build agents from scratch

Use Pillar6's built-in agent patterns for a full framework experience:

```python
from pillar6 import BaseAgent, Pillar6Config
from pillar6.agents.patterns import ReActAgent
```

See [Build from Scratch](quickstart.md) for the quickstart guide.

## Agent Lifecycle

When using Pillar6's built-in agents, every run follows this lifecycle:

```
INIT -> SECURITY CHECK -> CONTEXT LOAD -> ROUTE -> BUDGET CHECK -> EXECUTE -> OBSERVE -> RESPOND
```

1. **INIT** — Create a trace, generate a workflow ID
2. **SECURITY CHECK** — Validate input through the guardrail chain
3. **CONTEXT LOAD** — Allocate token budget, inject system prompt and user message
4. **ROUTE** — Select the best model based on constraints
5. **BUDGET CHECK** — Verify the agent has sufficient token budget
6. **EXECUTE** — Call the LLM, handle any tool calls
7. **OBSERVE** — Emit metrics, record audit entries
8. **RESPOND** — Validate output and return the response

## Which Pattern Should I Use?

| Pattern | Best for | How it works |
|---------|----------|-------------|
| [**ReAct**](../patterns/react.md) | Step-by-step reasoning with tools | Think -> Act -> Observe loop |
| [**Plan-Execute**](../patterns/plan-execute.md) | Multi-step tasks with known structure | Plan upfront, execute steps, replan on failure |
| [**Supervisor**](../patterns/supervisor.md) | Tasks requiring multiple specialties | Delegate to specialists, synthesise results |
