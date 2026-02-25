# Testing stackdrift

Step-by-step guide to test stackdrift against a real AWS account.

## Prerequisites

- Python 3.11+
- AWS CLI configured with credentials (`aws sts get-caller-identity` should work)
- At least one CloudFormation stack deployed in your account

## 1. Install

```bash
cd stackdrift
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 2. Verify Installation

```bash
stackdrift --help
```

You should see all options: `--stack`, `--prefix`, `--tag`, `--format`, etc.

## 3. Run the Test Suite

```bash
pytest -v
```

All 61 tests should pass. For coverage:

```bash
pytest --cov=stackdrift --cov-report=term-missing
```

## 4. Check All Stacks

```bash
stackdrift
```

This scans every active CloudFormation stack in your default region. Drift detection can take 30-60 seconds per stack depending on resource count.

To target a specific region:

```bash
stackdrift --region us-east-1
```

## 5. Check a Specific Stack

```bash
stackdrift --stack your-stack-name
```

Replace `your-stack-name` with an actual stack in your account. List your stacks with:

```bash
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query 'StackSummaries[].StackName' --output text
```

## 6. Try Different Output Formats

```bash
# Rich tree view (default)
stackdrift --stack your-stack-name --format table

# JSON (good for piping to jq)
stackdrift --stack your-stack-name --format json

# Markdown (good for reports)
stackdrift --stack your-stack-name --format markdown
```

## 7. Filter by Prefix or Tag

```bash
# All stacks starting with "prod-"
stackdrift --prefix prod-

# All stacks tagged with Environment=production
stackdrift --tag Environment=production
```

## 8. Show Only Drifted Stacks

```bash
stackdrift --drifted-only
```

## 9. Check Exit Codes

stackdrift exits with different codes depending on results:

```bash
stackdrift --stack your-stack-name
echo $?
# 0 = no drift detected
# 1 = drift detected
# 2 = error (missing env vars, AWS errors, etc.)
```

This makes it CI-friendly — use it in a pipeline and fail the build on drift.

## 10. Create Drift to Test Detection

If you want to verify detection works, manually change a resource that belongs to a CloudFormation stack:

1. Pick a stack with an SQS queue, S3 bucket, or similar simple resource
2. Change a property directly in the AWS console (e.g., change an SQS queue's visibility timeout)
3. Run `stackdrift --stack your-stack-name --format json`
4. You should see the property diff with expected vs actual values and a severity rating

**Important:** Revert your manual change afterward to avoid leaving drift in your account.

## 11. Test Slack Integration (Optional)

```bash
export STACKDRIFT_SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
stackdrift --post-slack
```

## 12. Test GitHub PR Integration (Optional)

```bash
export GITHUB_TOKEN="ghp_your_token"
export GITHUB_REPO="owner/repo"
stackdrift --post-github-pr 1
```

This posts a markdown drift report as a comment on PR #1.

## Troubleshooting

**"No stacks found"** — Check your AWS region. Use `--region` to specify it explicitly.

**"Access Denied"** — Your IAM user/role needs the permissions listed in the README. At minimum: `cloudformation:ListStacks`, `cloudformation:DetectStackDrift`, `cloudformation:DescribeStackDriftDetectionStatus`, `cloudformation:DescribeStackResourceDrifts`, `cloudformation:DescribeStacks`.

**Slow detection** — Drift detection is an async AWS operation. Each stack takes 10-60 seconds. Use `--max-concurrent` to increase parallelism (default is 5).
