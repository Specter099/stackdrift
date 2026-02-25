# Contributing to StackDrift

Thank you for your interest in contributing to StackDrift! This guide will help you get started.

## Development Setup

```bash
git clone https://github.com/Specter099/stackdrift.git
cd stackdrift
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Workflow

1. Fork the repository and create a feature branch from `main`.
2. Make your changes in small, focused commits.
3. Add or update tests for any new functionality.
4. Ensure all checks pass before submitting:
   ```bash
   ruff format .
   ruff check .
   pytest
   ```
5. Open a pull request targeting `main`.

## Pull Request Guidelines

- Keep PRs focused on a single change.
- Write a clear title and description explaining **what** and **why**.
- Link any related issues.
- All CI checks must pass before review.

## Coding Standards

- Follow [PEP 8](https://peps.python.org/pep-0008/) conventions.
- Use [ruff](https://docs.astral.sh/ruff/) for linting and formatting.
- Write docstrings for public functions and classes.
- Add type hints to function signatures.

## Reporting Bugs

- Use the **Bug Report** issue template.
- Include steps to reproduce, expected behavior, and actual behavior.
- Include your Python version and OS.

## Requesting Features

- Use the **Feature Request** issue template.
- Describe the problem you're trying to solve, not just the solution.

## Code of Conduct

By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).
