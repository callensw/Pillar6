# Pillar6

**Production infrastructure for agentic AI. Any framework. Full visibility.**

Add observability, security, cost tracking, and evaluation to any AI agent
in one line of code. Works with LangChain, CrewAI, AutoGen, raw SDKs, or
any custom agent.

---

## Quick Start

```python
from pillar6 import pillar6_wrap

async def my_agent(query: str) -> str:
    # your existing agent code
    ...

agent = pillar6_wrap(my_agent)
result = await agent("What is quantum computing?")

# You now have tracing, cost tracking, and security.
print(await agent.traces.get_trace(agent.last_workflow_id))
```

## What You Get

| Problem | How Pillar6 solves it |
|---------|----------------------|
| **See what your agents are doing** | Distributed tracing, structured logs, execution replay |
| **Control costs** | Real-time cost tracking per agent, model routing, budget guardrails |
| **Stay secure** | Prompt injection detection, permission scoping, input/output validation |
| **Test with confidence** | Deterministic mocks, golden datasets, LLM-as-judge, chaos testing |
| **Manage context** | Token budgets, priority-based eviction, session persistence |
| **Orchestrate tools** | Retries, circuit breakers, rate limiting, parallel execution |

## Works With

- **LangChain / LangGraph** — `wrap_langchain(chain)`
- **CrewAI** — `wrap_crew(crew)`
- **Anthropic SDK** — `wrap_client(AsyncAnthropic())`
- **OpenAI SDK** — `wrap_client(OpenAI())`
- **Any Python function** — `pillar6_wrap(my_func)`

## Build Agents From Scratch

Pillar6 also includes full agent patterns for those who want a complete
framework experience:

- [**ReAct**](patterns/react.md) — Reasoning + Acting loop for step-by-step problem solving
- [**Plan-Execute**](patterns/plan-execute.md) — Plan upfront, execute sequentially, replan on failure
- [**Supervisor**](patterns/supervisor.md) — Delegate to specialist sub-agents and synthesise results

## Next Steps

- [Add Pillar6 to Existing Agents](getting-started/wrapping.md) — The fastest path to production
- [Installation](getting-started/installation.md) — Set up your environment
- [Build from Scratch](getting-started/quickstart.md) — Create agents using Pillar6 patterns
- [Concepts](getting-started/concepts.md) — Understand the production pillars
