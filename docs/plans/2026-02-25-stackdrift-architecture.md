# stackdrift Architecture Design

**Date:** 2026-02-25
**Status:** Approved

## Overview

stackdrift is a pip-installable CloudFormation drift detector. It detects when deployed AWS resources have drifted from their template definitions, classifies drift by severity, and outputs results in multiple formats with optional Slack/GitHub integrations.

## Architecture

Layered pipeline with clean separation of concerns:

```
CLI (click)
    │
    ├── Detector (orchestration + concurrency)
    │       │
    │       └── CloudFormationClient (boto3 wrapper)
    │
    ├── Analyzer (severity classification)
    │
    ├── Formatter (table/json/markdown)
    │
    └── Integrations (slack, github)
```

**Data flow:**
1. CLI parses args, creates CloudFormationClient and Detector
2. Detector lists stacks (with filtering), triggers drift detection concurrently via ThreadPoolExecutor, polls for completion, fetches resource-level results
3. Results come back as `list[StackDriftResult]` (frozen dataclasses)
4. Analyzer classifies each ResourceDrift with a severity level based on resource type
5. Formatter renders to chosen format
6. Integrations post to Slack/GitHub if requested
7. CLI exits with code 1 if any drift detected

## Components

### AWS Client (`src/stackdrift/aws/client.py`)

Thin boto3 wrapper. No business logic — translates between boto3 responses and dataclasses.

Methods:
- `list_stacks(prefix, tags)` — calls ListStacks/DescribeStacks, applies filters, returns stack names + ARNs
- `detect_drift(stack_name)` — calls DetectStackDrift, returns DetectionRun
- `poll_detection(detection_id)` — calls DescribeStackDriftDetectionStatus, returns updated DetectionRun
- `get_resource_drifts(stack_name)` — calls DescribeStackResourceDrifts, returns `list[ResourceDrift]`

Testable with moto.

### Detector (`src/stackdrift/detector.py`)

Orchestrates the full detection cycle:
- Takes a CloudFormationClient + config (max_concurrent, filters)
- Uses `ThreadPoolExecutor(max_workers=max_concurrent)` to run stacks in parallel
- Per-stack flow: detect_drift → poll with exponential backoff → get_resource_drifts → assemble StackDriftResult
- Returns `list[StackDriftResult]`

### Analyzer (`src/stackdrift/analyzer.py`)

Severity classification based on a static resource type mapping:
- **Critical:** Security groups, IAM roles/policies, KMS keys, NACLs
- **High:** Lambda functions, RDS instances, ECS task definitions
- **Medium:** SQS queues, SNS topics, S3 buckets, DynamoDB tables
- **Low:** Tags, CloudWatch alarms, outputs

Takes `list[StackDriftResult]`, returns annotated results with severity per resource. The mapping is a dict — easy to extend.

### Formatter (`src/stackdrift/formatter.py`)

Three renderers, all take the same annotated result list:
- **table** — Rich tree view grouped by stack → resource → property diffs, color-coded by severity
- **json** — Structured JSON dump
- **markdown** — Table format suitable for GitHub PR comments

### Integrations

- **Slack** (`src/stackdrift/integrations/slack.py`) — POST markdown summary to webhook URL from `STACKDRIFT_SLACK_WEBHOOK`
- **GitHub** (`src/stackdrift/integrations/github.py`) — POST markdown as PR comment using `GITHUB_TOKEN` and `GITHUB_REPO`

### CLI (`src/stackdrift/cli.py`)

Click-based entrypoint:

```
stackdrift [--stack NAME]... [--prefix PREFIX] [--tag KEY=VALUE]
           [--drifted-only] [--format table|json|markdown]
           [--post-slack] [--post-github-pr NUMBER]
           [--max-concurrent N]
```

Exit codes: 0 = no drift, 1 = drift detected, 2 = error.

## Key Decisions

- **Frozen dataclasses** for all models — thread-safe for concurrent detection
- **Severity via static mapping** — simple dict lookup by resource type, no runtime overhead
- **boto3 wrapper** — isolates AWS calls for testability with moto
- **ThreadPoolExecutor** — matches existing design, configurable concurrency
- **Click** — already a dependency in pyproject.toml, proven CLI framework

## File Layout

```
src/stackdrift/
    __init__.py
    models.py          (enums + dataclasses — exists)
    cli.py             (click entrypoint)
    detector.py        (orchestration + concurrency)
    analyzer.py        (severity classification)
    formatter.py       (table/json/markdown)
    aws/
        __init__.py
        client.py      (boto3 wrapper)
    integrations/
        __init__.py
        slack.py
        github.py
tests/
    conftest.py        (fixtures + moto setup)
    test_models.py
    test_client.py
    test_detector.py
    test_analyzer.py
    test_formatter.py
    test_integrations.py
    test_cli.py
```
