# stackdrift – Claude Code Context

## Project
CloudFormation drift detector CLI (`stackdrift`). Python package in `src/stackdrift/`.

## Python
- `requires-python = ">=3.11"` — never test below 3.11
- CI matrix: `["3.11", "3.12", "3.13"]` — add 3.14 when it reaches stable (Oct 2026)
- Install deps: `pip install -e ".[dev]"` (not requirements files)
- Lint: `ruff format --check . && ruff check .`
- Tests: `pytest --tb=short`

## GitHub / CI
- Repo: `Specter099/stackdrift`
- Required status checks: `lint`, `test (3.11)`, `test (3.12)`, `test (3.13)`
- `enforce_admins: false` — admins can bypass branch protection for emergency merges
- `gh pr merge --squash --admin --body ""` — merge with admin bypass

## GitHub API Gotchas
- Branch protection only supports `PUT` (full replacement) — always GET first and merge, never blindly PUT
- `gh api --field` silently stringifies nested objects; use `gh api --input -` with a JSON heredoc instead
- `/repo-bootstrap` overwrites branch protection — re-apply status checks afterwards
