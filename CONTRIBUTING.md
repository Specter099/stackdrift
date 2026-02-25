# Contributing to stackdrift

Thanks for your interest in contributing to stackdrift! This guide will help you get started.

## Development Setup

```bash
git clone https://github.com/Specter099/stackdrift.git
cd stackdrift
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Workflow

1. Fork the repo and create a feature branch from `main`.
2. Make your changes. Add tests for new functionality.
3. Run the test suite and linter:
   ```bash
   pytest
   ruff check src/ tests/
   ruff format --check .
   ```
4. Commit with a clear message describing what and why.
5. Open a pull request against `main`.

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR.
- Include tests for new behavior.
- Update documentation if you change user-facing behavior.
- All CI checks must pass before merge.

## Reporting Bugs

Use the [bug report template](https://github.com/Specter099/stackdrift/issues/new?template=bug_report.yml) and include:

- Steps to reproduce
- Expected vs actual behavior
- stackdrift version and Python version
- Relevant AWS environment details (region, stack names)

## Requesting Features

Use the [feature request template](https://github.com/Specter099/stackdrift/issues/new?template=feature_request.yml) and describe:

- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

## Code Style

- Follow existing patterns in the codebase.
- We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.
- Write clear, self-documenting code. Add comments only where the logic isn't obvious.

## Security Vulnerabilities

Do **not** open a public issue. See [SECURITY.md](SECURITY.md) for responsible disclosure instructions.
