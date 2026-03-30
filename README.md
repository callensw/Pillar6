# Pillar6

**Production infrastructure for agentic AI. Any framework. Full visibility.**

Add observability, security, cost tracking, and evaluation to your AI agents
in one line of code. Works with LangChain, CrewAI, AutoGen, raw SDKs, or
any custom agent.

[![PyPI version](https://img.shields.io/pypi/v/pillar6)](https://pypi.org/project/pillar6/)
[![Python](https://img.shields.io/pypi/pyversions/pillar6)](https://pypi.org/project/pillar6/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/callensw/pillar6/actions/workflows/ci.yml/badge.svg)](https://github.com/callensw/pillar6/actions/workflows/ci.yml)

---

## The Problem

Building AI agents is easy. Running them in production is hard. You need
observability to debug failures, security to prevent prompt injection, cost
tracking to avoid budget blowouts, and evaluation to catch regressions.
Pillar6 gives you all of this without rewriting your agents.

## Quick Start

### Wrap any function

```python
from pillar6 import pillar6_wrap

async def my_agent(query: str) -> str:
    # your existing agent code
    ...

agent = pillar6_wrap(my_agent)
result = await agent("What is quantum computing?")

# That's it. You now have tracing, cost tracking, and security.
print(await agent.traces.get_trace(agent.last_workflow_id))
```

### Monitor a raw SDK client

```python
from anthropic import AsyncAnthropic
from pillar6.wrappers.sdk import wrap_client

client = wrap_client(AsyncAnthropic())
# Use exactly like normal — now with production monitoring
response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Hello"}],
)
```

### Wrap a LangChain chain

```python
from pillar6.wrappers.langchain import wrap_langchain

production_chain = wrap_langchain(my_chain)
result = await production_chain.ainvoke({"query": "..."})
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

## Advanced: Build Agents From Scratch

Pillar6 also includes full agent patterns for those who want a complete
framework experience:

```python
from pillar6 import BaseAgent, Pillar6Config
from pillar6.agents.patterns import ReActAgent, PlanExecuteAgent, SupervisorAgent
```

Three production-ready patterns:

| Pattern | Description |
|---------|-------------|
| **ReAct** | Reasoning + Acting loop — think, use tools, observe, repeat |
| **Plan-Execute** | Plan upfront, execute steps, replan on failure |
| **Supervisor** | Delegate to specialist sub-agents, synthesise results |

See the [documentation](https://callensw.github.io/Pillar6) for full guides.

## Reference App: Multi-Agent Research Assistant

A complete demo with a team of AI agents that autonomously research a question
and produce a structured report, with a live React dashboard.

```bash
cd examples/research-assistant
PYTHONPATH=../../:. python main.py "What are the latest developments in quantum computing?"
```

See [examples/research-assistant/](examples/research-assistant/) for full setup.

## Installation

```bash
pip install pillar6
```

With optional integrations:

```bash
pip install pillar6[langchain]   # LangChain support
pip install pillar6[crewai]      # CrewAI support
pip install pillar6[all]         # Everything
```

From source:

```bash
git clone https://github.com/callensw/Pillar6.git
cd Pillar6
pip install -e ".[dev]"
```

## Development

```bash
pytest                 # Run tests
ruff check .           # Lint
ruff format .          # Format
mypy pillar6           # Type check
mkdocs serve           # Docs at http://localhost:8000
```

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Pillar6 is released under the [MIT License](LICENSE).
