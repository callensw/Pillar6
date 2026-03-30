# Pillar6

**The production framework for agentic AI. Six pillars. Zero guesswork.**

Pillar6 is an opinionated Python framework for building production-grade AI agents.
It provides six architectural pillars that every agent system needs, wired together
with sensible defaults so you can go from idea to production in minutes.

---

## The Six Pillars

| Pillar | What it does |
|--------|-------------|
| **Context Management** | Token budgets, priority buckets, sliding window, compression |
| **Tool Orchestration** | Schema validation, circuit breakers, retries, caching, parallel execution |
| **Security & Guardrails** | Input/output validation, permissions, budget enforcement, audit trail |
| **Efficiency & Routing** | Model registry, constraint-based routing, fallback chains, cost tracking |
| **Observability** | Distributed tracing, structured logging, metrics, trace export |
| **Testing & Evaluation** | Mock adapters, chaos testing, scoring, dataset-driven eval, comparison |

## Quick Install

```bash
pip install pillar6
```

## Minimal Example

```python
import asyncio
from pillar6 import BaseAgent, Pillar6Config
from pillar6.core.eval import MockLLMAdapter

async def main():
    llm = MockLLMAdapter(
        responses={"hello": "Hello! How can I help you today?"},
        default_response="I'm not sure how to help with that.",
    )
    agent = BaseAgent(config=Pillar6Config(), llm=llm)
    result = await agent.run("hello")
    print(result)  # "Hello! How can I help you today?"

asyncio.run(main())
```

## Agent Patterns

Pillar6 ships with three production-ready agent patterns:

- [**ReAct**](patterns/react.md) -- Reasoning + Acting loop for step-by-step problem solving
- [**Plan-Execute**](patterns/plan-execute.md) -- Plan upfront, execute sequentially, replan on failure
- [**Supervisor**](patterns/supervisor.md) -- Delegate to specialist sub-agents and synthesise results

## Next Steps

- [Installation](getting-started/installation.md) -- Set up your environment
- [Quickstart](getting-started/quickstart.md) -- Build your first agent in 5 minutes
- [Concepts](getting-started/concepts.md) -- Understand the six-pillar architecture
