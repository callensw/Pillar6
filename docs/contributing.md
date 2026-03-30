# Contributing

Thank you for your interest in contributing to Pillar6!

## Development Setup

```bash
git clone https://github.com/callensw/pillar6.git
cd pillar6
pip install -e ".[dev,docs]"
```

## Running Tests

```bash
# Run all tests
python -m pytest -v

# Run a specific test file
python -m pytest tests/test_patterns.py -v

# Run with coverage
python -m pytest --cov=pillar6 --cov-report=term-missing
```

## Code Quality

We enforce strict code quality standards:

```bash
# Linting
python -m ruff check .

# Formatting
python -m ruff format .

# Type checking
python -m mypy pillar6
```

All three must pass before merging.

## Building Documentation

```bash
# Serve locally with hot reload
mkdocs serve

# Build static site
mkdocs build --strict
```

## Project Structure

```
pillar6/
  adapters/       # LLM provider adapters
  agents/
    base.py       # BaseAgent class
    patterns/     # Agent patterns (ReAct, PlanExecute, Supervisor)
  config/         # Pydantic configuration models
  core/           # Six pillar implementations
  types.py        # Shared type definitions
tests/            # Test suite
docs/             # MkDocs documentation
```

## Coding Conventions

- **Type annotations** on all public functions and methods
- **Docstrings** on all public classes and methods (Google style)
- **Pydantic v2** BaseModel for all data models
- **ABC + default implementation** pattern for each pillar
- **async/await** for all I/O-bound operations
- Target Python 3.11+

## Adding a New Pillar Implementation

1. Create your implementation in `pillar6/core/`
2. Implement the abstract base class interface
3. Add configuration to `pillar6/config/models.py`
4. Write tests in `tests/`
5. Add documentation in `docs/pillars/`

## Adding a New Agent Pattern

1. Create `pillar6/agents/patterns/your_pattern.py`
2. Extend `BaseAgent` with your orchestration logic
3. Add a Pydantic config model
4. Export from `pillar6/agents/patterns/__init__.py`
5. Write tests in `tests/test_patterns.py`
6. Add documentation in `docs/patterns/`
