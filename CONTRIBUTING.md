# Contributing to Pillar6

Thank you for your interest in contributing to Pillar6! This guide will help you get started.

## Development Setup

1. Fork and clone the repository:

```bash
git clone https://github.com/callensw/pillar6.git
cd pillar6
```

2. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

3. Verify everything works:

```bash
pytest
ruff check .
mypy pillar6
```

## Code Standards

- **Formatting**: We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting. Run `ruff format .` before committing.
- **Type hints**: All public functions must have complete type annotations. Run `mypy pillar6` to verify.
- **Docstrings**: Every public class and function needs a docstring explaining its purpose.
- **Testing**: All new features need tests. We use `pytest` with `pytest-asyncio` for async tests.
- **No print statements**: Use the `logging` module instead.

## Pull Request Process

1. Create a feature branch from `main`.
2. Write your code and tests.
3. Ensure all checks pass: `pytest`, `ruff check .`, `ruff format --check .`, `mypy pillar6`.
4. Submit a PR with a clear description of what changed and why.

## Architecture

Pillar6 is organized around six pillars. Each pillar lives in `pillar6/core/` and follows the same pattern:

- An **Abstract Base Class** (ABC) defining the interface.
- A **default implementation** that works out of the box.
- A **config model** in `pillar6/config/models.py`.

When adding new functionality, follow this pattern to maintain consistency.

## Reporting Issues

Please open an issue on GitHub with:

- A clear description of the problem or feature request.
- Steps to reproduce (for bugs).
- Your Python version and OS.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
