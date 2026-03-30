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
| 5 | **Observability** | Distributed tracing, structured logging, Prometheus metrics, execution replay, and anomaly detection |
| 6 | **Testing & Evaluation** | Mock harnesses, golden dataset eval, LLM-as-judge, regression detection, and chaos testing |

## Quick Start

```bash
pip install pillar6
```

```python
import asyncio
from pillar6 import BaseAgent, Pillar6Config

async def main():
    config = Pillar6Config()
    agent = BaseAgent(config=config)
    result = await agent.run("Summarize the key benefits of agentic AI.")
    print(result)

asyncio.run(main())
```

### With an LLM adapter

```python
from pillar6 import BaseAgent, Pillar6Config
from pillar6.adapters.anthropic import AnthropicAdapter

async def main():
    config = Pillar6Config()
    llm = AnthropicAdapter(api_key="your-api-key")
    agent = BaseAgent(config=config, llm=llm)
    result = await agent.run("What are the six pillars of production AI?")
    print(result)
```

### Scaffold a new project

```bash
pillar6 init my-agent
cd my-agent
python agent.py
```

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
```

## Documentation

Full documentation is coming in Phase 2. For now, every public class and method includes detailed docstrings.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Pillar6 is released under the [MIT License](LICENSE).
