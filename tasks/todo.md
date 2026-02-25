# stackdrift Implementation Checklist

## Phase 1 — Project Scaffolding
- [x] Create feature branch: `feature/initial-implementation`
- [x] `pyproject.toml`
- [x] `README.md` (CLI usage + IAM requirements)
- [x] Directory structure (`src/stackdrift/`, `tests/`, `tasks/`)
- [x] `src/stackdrift/__init__.py` (version string)
- [x] `tasks/todo.md` (this file)
- [x] `tasks/lessons.md`

## Phase 2 — Core Data Models
- [ ] `src/stackdrift/models.py` — DriftStatus, DiffType, DetectionStatus enums; PropertyDiff, ResourceDrift, StackDriftResult, DetectionRun dataclasses

## Phase 3 — AWS Client
- [ ] `src/stackdrift/aws/__init__.py`
- [ ] `src/stackdrift/aws/client.py` — CloudFormationClient
- [ ] `tests/conftest.py` + fixture JSON files
- [ ] `tests/test_client.py`

## Phase 4 — Detector (Polling + Concurrency)
- [ ] `src/stackdrift/detector.py` — detect_all_stacks() with ThreadPoolExecutor
- [ ] `tests/test_detector.py`

## Phase 5 — Analyzer
- [ ] `src/stackdrift/analyzer.py` — annotate_results()
- [ ] `tests/test_analyzer.py`

## Phase 6 — Formatter
- [ ] `src/stackdrift/formatter.py` — table/json/markdown renderers
- [ ] `tests/test_formatter.py`

## Phase 7 — Integrations
- [ ] `src/stackdrift/integrations/slack.py`
- [ ] `src/stackdrift/integrations/github.py`
- [ ] `tests/test_integrations.py`

## Phase 8 — CLI Entrypoint
- [ ] `src/stackdrift/cli.py`

## Phase 9 — Final Verification
- [ ] All tests pass (`pytest`)
- [ ] Linter passes (`ruff check src/ tests/`)
- [ ] `stackdrift --help` works after `pip install -e ".[dev]"`
