# stackdrift

A pip-installable CloudFormation drift detector. Detects when deployed AWS resources have drifted from their CloudFormation template definitions.

[![CI](https://github.com/Specter099/stackdrift/actions/workflows/ci.yml/badge.svg)](https://github.com/Specter099/stackdrift/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- Detects drift across all stacks in your AWS account (or a filtered subset)
- Property-level diffs with human-readable annotations
- Concurrent drift detection (configurable, default: 5 simultaneous)
- Rich terminal output (tree view), JSON, and Markdown formats
- Slack webhook integration
- GitHub PR comment integration
- CI-friendly: exits with code 1 when drift is detected

## Installation

```bash
pip install stackdrift
```

## Usage

```bash
# Check all stacks
stackdrift

# Check specific stacks
stackdrift --stack my-stack
stackdrift --stack my-stack-1 --stack my-stack-2

# Filter by prefix or tag
stackdrift --prefix prod-
stackdrift --tag Environment=prod

# Show only drifted stacks
stackdrift --drifted-only

# Output formats
stackdrift --format table    # default (Rich tree)
stackdrift --format json
stackdrift --format markdown

# Post to Slack (requires STACKDRIFT_SLACK_WEBHOOK env var)
stackdrift --post-slack

# Post as GitHub PR comment (requires GITHUB_TOKEN, GITHUB_REPO env vars)
stackdrift --post-github-pr 42

# Control concurrency
stackdrift --max-concurrent 5
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

## Development Setup

```bash
git clone https://github.com/Specter099/stackdrift.git
cd stackdrift
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

## Linting

```bash
ruff check src/ tests/
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## License

[MIT](LICENSE)
