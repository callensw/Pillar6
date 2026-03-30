# Installation

## Requirements

- Python 3.11 or later
- pip or uv

## Install from PyPI

```bash
pip install pillar6
```

## Install from Source

```bash
git clone https://github.com/callensw/pillar6.git
cd pillar6
pip install -e ".[dev]"
```

## Development Setup

Install with dev and docs dependencies:

```bash
pip install -e ".[dev,docs]"
```

This gives you:

- `pytest` and `pytest-asyncio` for testing
- `ruff` for linting and formatting
- `mypy` for type checking
- `mkdocs-material` for building documentation

## Verify Installation

```python
import pillar6
print(pillar6.__version__)  # "0.1.0"
```

## Dependencies

Pillar6 has minimal core dependencies:

| Package | Purpose |
|---------|---------|
| `pydantic>=2.0` | Data models and validation |
| `httpx>=0.25` | HTTP client for LLM adapters |
| `typer>=0.9` | CLI interface |
