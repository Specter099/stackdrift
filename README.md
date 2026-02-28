# stackdrift

A pip-installable CloudFormation drift detector. Detects when deployed AWS resources have drifted from their CloudFormation template definitions, with property-level diffs and optional Slack/GitHub integrations.

[![CI](https://github.com/Specter099/stackdrift/actions/workflows/ci.yml/badge.svg)](https://github.com/Specter099/stackdrift/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/stackdrift)](https://pypi.org/project/stackdrift/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- Detects drift across all stacks in an AWS account, or a filtered subset by name, prefix, or tag
- Property-level diffs — shows exactly which resource properties changed and what the expected vs. actual values are
- Concurrent drift detection (configurable, default: 5 simultaneous)
- Rich color terminal output (tree view), JSON, and Markdown formats
- Slack webhook and GitHub PR comment integrations
- `--redact-values` flag to suppress sensitive values from output and reports
- CI-friendly exit codes: `0` no drift, `1` drift detected, `2` detection failure

## Installation

```bash
pip install stackdrift
```

## Usage

```bash
# Check all stacks in the account
stackdrift

# Check specific stacks by name
stackdrift --stack my-stack
stackdrift --stack my-stack-1 --stack my-stack-2

# Filter stacks by name prefix or tag
stackdrift --prefix prod-
stackdrift --tag Environment=prod

# Show only stacks with drift (suppress IN_SYNC stacks)
stackdrift --drifted-only

# AWS region (defaults to AWS_DEFAULT_REGION / ~/.aws/config)
stackdrift --region us-east-1

# Output formats
stackdrift --format table     # default — colored Rich tree
stackdrift --format json
stackdrift --format markdown

# Suppress sensitive expected/actual values in all output
stackdrift --redact-values

# Suppress warning messages (show only errors)
stackdrift --quiet

# Control how many stacks are checked concurrently (1–50)
stackdrift --max-concurrent 10

# Post report to Slack (requires STACKDRIFT_SLACK_WEBHOOK env var)
stackdrift --post-slack

# Post report as a GitHub PR comment (requires GITHUB_TOKEN and GITHUB_REPO env vars)
stackdrift --post-github-pr 42
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All stacks in sync — no drift detected |
| `1` | Drift detected in one or more stacks |
| `2` | Detection failed for one or more stacks (API error, insufficient permissions, etc.), or a required env var was missing (`STACKDRIFT_SLACK_WEBHOOK`, `GITHUB_TOKEN`, `GITHUB_REPO`) |

Useful for CI pipelines:

```bash
stackdrift --drifted-only || echo "Drift detected!"
```

## Environment Variables

| Variable | Required for | Description |
|---|---|---|
| `STACKDRIFT_SLACK_WEBHOOK` | `--post-slack` | Incoming webhook URL for the target Slack channel |
| `GITHUB_TOKEN` | `--post-github-pr` | Personal access token or Actions token with `pull_requests: write` |
| `GITHUB_REPO` | `--post-github-pr` | Repository in `owner/repo` format (e.g. `myorg/myrepo`) |

## Reading the Output

Property diffs are shown as `expected → actual`. A value of `null` means the property is **absent** on that side:

| Pattern | Meaning |
|---|---|
| `null → "value"` | Property exists on the live resource but **not in the template** — added out-of-band |
| `"value" → null` | Property is in the template but **missing from the live resource** — removed out-of-band |

**Examples:**

```
/Parameters/3: null → {"ParameterKey":"ExistingOIDCProviderArn","ParameterValue":""}
```
An extra parameter was added directly to the StackSet, not through CloudFormation.

```
/TargetIds/0: ou-350a-kg3vy772 → null
```
That OU target was detached from the SCP directly in AWS — CloudFormation still expects it.

```
/KmsMasterKeyId: alias/aws/sns → null
```
The SNS topic's KMS encryption key was removed outside of CloudFormation.

## Required IAM Permissions

```json
{
  "Effect": "Allow",
  "Action": [
    "cloudformation:ListStacks",
    "cloudformation:DetectStackDrift",
    "cloudformation:DescribeStackDriftDetectionStatus",
    "cloudformation:DescribeStackResourceDrifts",
    "cloudformation:DescribeStacks"
  ],
  "Resource": "*"
}
```

## Development

```bash
git clone https://github.com/Specter099/stackdrift.git
cd stackdrift
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Lint and format check
ruff check src/ tests/
ruff format --check .
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## License

[MIT](LICENSE)
