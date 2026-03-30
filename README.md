# Pillar6

**The production framework for agentic AI. Six pillars. Zero guesswork.**

[![PyPI version](https://img.shields.io/pypi/v/pillar6)](https://pypi.org/project/pillar6/)
[![Python](https://img.shields.io/pypi/pyversions/pillar6)](https://pypi.org/project/pillar6/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/callensw/pillar6/actions/workflows/ci.yml/badge.svg)](https://github.com/callensw/pillar6/actions/workflows/ci.yml)

---

## The Six Pillars

| # | Pillar | Description |
|---|--------|-------------|
| 1 | **Context Management** | Intelligent context window management with sliding window, summarization, priority tagging, and persistence |
| 2 | **Tool Orchestration** | Tool registration, validation, retries, rate limiting, parallel execution, and circuit breakers |
| 3 | **Security & Guardrails** | Permissions, input sanitization, output validation, prompt injection detection, cost guardrails, and audit trail |
| 4 | **Efficiency & Routing** | Multi-model routing, fallback chains, semantic caching, cost tracking, and latency-aware routing |
| 5 | **Observability** | Distributed tracing, structured logging, metric emission, execution replay, and trace export |
| 6 | **Testing & Evaluation** | Mock harnesses, golden dataset eval, scoring heuristics, regression detection, and chaos testing |

## Agent Patterns

Pillar6 ships with three production-ready agent patterns:

| Pattern | Description |
|---------|-------------|
| **ReAct** | Reasoning + Acting loop — think, use tools, observe, repeat |
| **Plan-Execute** | Plan upfront, execute steps, replan on failure |
| **Supervisor** | Delegate to specialist sub-agents, synthesise results |

## Quick Start

```bash
pip install pillar6
```

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

### Using Agent Patterns

```python
from pillar6.agents.patterns import ReActAgent, ReActConfig

agent = ReActAgent(
    react_config=ReActConfig(max_steps=5),
    config=Pillar6Config(),
    llm=llm,
)
result = await agent.run("Search for and summarise recent AI news")
```

## Reference App: Multi-Agent Research Assistant

A complete demo of all six pillars in action. A team of AI agents autonomously
researches a question and produces a structured report, with a live React
dashboard for real-time observability.

```
User Question → Conductor (Supervisor) → Researchers (ReAct) → Analyst (PlanExecute) → Report
```

<!-- Screenshot placeholder: ![Dashboard](docs/assets/dashboard-screenshot.png) -->

**Run it:**

```bash
cd examples/research-assistant
PYTHONPATH=../../:. python main.py "What are the latest developments in quantum computing?"
```

**Start the dashboard:**

```bash
PYTHONPATH=../../:. python main.py --serve        # API at :8000
cd dashboard && npm install && npm run dev  # Dashboard at :5173
```

See [examples/research-assistant/README.md](examples/research-assistant/README.md) for full setup instructions.

## Installation

**From PyPI:**

```bash
pip install pillar6
```

**From source:**

```bash
git clone https://github.com/callensw/pillar6.git
cd pillar6
pip install -e ".[dev]"
```

## Documentation

Full documentation is available via MkDocs:

```bash
pip install -e ".[docs]"
mkdocs serve    # http://localhost:8000
```

See the [docs/](docs/) directory for all documentation pages.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint and format
ruff check .
ruff format .

# Type check
mypy pillar6

# Build docs
mkdocs build --strict
```

## Contributing

We welcome contributions! Please see [docs/contributing.md](docs/contributing.md) for guidelines.

## License

Pillar6 is released under the [MIT License](LICENSE).
