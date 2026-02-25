# Security Audit Report — stackdrift

**Date:** 2026-02-25
**Scope:** Full codebase review of stackdrift v0.1.0
**Auditor:** Automated security review (Claude)

---

## Executive Summary

stackdrift is a CloudFormation drift detection CLI tool with Slack and GitHub integrations. The codebase is compact (~750 lines of application code) with a clean architecture that limits the attack surface. However, several security issues were identified, primarily in input validation, output data exposure, CI/CD supply chain hardening, and integration robustness.

**Finding Summary:**

| Severity | Count |
|----------|-------|
| High     | 2     |
| Medium   | 5     |
| Low      | 6     |

---

## HIGH Severity Findings

### H-1: SSRF risk via unvalidated Slack webhook URL

**File:** `src/stackdrift/integrations/slack.py:8`
**CWE:** CWE-918 (Server-Side Request Forgery)

The `webhook_url` parameter is passed directly to `requests.post()` without any URL validation. While sourced from the `STACKDRIFT_SLACK_WEBHOOK` environment variable, in CI/CD environments env vars can be set from less-trusted sources (e.g., repository variables, workflow inputs, or compromised config).

An attacker who controls this value could:
- Redirect drift reports (containing infrastructure details) to an arbitrary endpoint
- Target internal services (e.g., cloud metadata endpoints like `http://169.254.169.254/`)
- Probe internal network topology via response timing

**Current code:**
```python
def post_to_slack(report: str, webhook_url: str) -> None:
    response = requests.post(webhook_url, json={"text": report}, timeout=30)
```

**Recommendation:** Validate the webhook URL against an allowlist of known Slack domains:
```python
from urllib.parse import urlparse

ALLOWED_SLACK_HOSTS = {"hooks.slack.com", "hooks.slack-gov.com"}

def post_to_slack(report: str, webhook_url: str) -> None:
    parsed = urlparse(webhook_url)
    if parsed.hostname not in ALLOWED_SLACK_HOSTS:
        raise ValueError(
            f"Invalid Slack webhook URL: host must be one of {ALLOWED_SLACK_HOSTS}"
        )
    if parsed.scheme != "https":
        raise ValueError("Slack webhook URL must use HTTPS")
    # ...
```

---

### H-2: Path traversal risk in GitHub API URL construction

**File:** `src/stackdrift/integrations/github.py:13`
**CWE:** CWE-22 (Path Traversal)

The `repo` parameter from the `GITHUB_REPO` environment variable is interpolated directly into the API URL with no validation:

```python
url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
```

A malicious `GITHUB_REPO` value (e.g., `../../../api/v3/admin`) could manipulate the URL path. While `pr_number` is safely typed as `int` by Click, the `repo` value has no format validation.

**Recommendation:** Validate the repo format before constructing the URL:
```python
import re

REPO_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$")

def post_to_github_pr(body: str, repo: str, pr_number: int, token: str) -> None:
    if not REPO_PATTERN.match(repo):
        raise ValueError(f"Invalid GitHub repo format: {repo!r} (expected 'owner/repo')")
    # ...
```

---

## MEDIUM Severity Findings

### M-1: Sensitive infrastructure data exposed in integration outputs

**File:** `src/stackdrift/formatter.py`
**CWE:** CWE-200 (Exposure of Sensitive Information)

The JSON and Markdown formatters include `physical_id`, `expected_value`, and `actual_value` for every drifted property. These values can contain highly sensitive data:
- Security group ingress/egress rules (IP ranges, port numbers)
- IAM policy documents (permissions, resource ARNs)
- KMS key configurations
- Database connection strings or parameters

When this output is posted to Slack channels or GitHub PR comments, it may be visible to audiences who shouldn't see infrastructure details.

**Recommendation:**
1. Add a `--redact-values` flag that replaces actual values with `[REDACTED]` in output
2. Consider redacting by default when `--post-slack` or `--post-github-pr` is used
3. At minimum, redact values for CRITICAL-severity resources (IAM, KMS, security groups)

---

### M-2: Incomplete API pagination in get_resource_drifts

**File:** `src/stackdrift/aws/client.py:111-141`
**CWE:** CWE-1286 (Improper Validation of Syntactic Correctness of Input)

`get_resource_drifts()` makes a single API call without handling pagination. The AWS `DescribeStackResourceDrifts` API returns at most 100 resources per response and uses a `NextToken` for pagination. For stacks with more than 100 resources, drifts will be **silently truncated**.

This is a security concern because a drift detection tool that misses drifted resources gives false confidence. Critical security-boundary drifts (IAM roles, security groups) could go unreported.

**Current code:**
```python
resp = self._client.describe_stack_resource_drifts(
    StackName=stack_name,
    StackResourceDriftStatusFilters=["MODIFIED", "DELETED", "NOT_CHECKED", "IN_SYNC"],
)
# Only processes resp["StackResourceDrifts"] — no NextToken handling
```

**Recommendation:** Add pagination loop:
```python
def get_resource_drifts(self, stack_name: str) -> list[ResourceDrift]:
    results = []
    next_token = None
    while True:
        kwargs = {
            "StackName": stack_name,
            "StackResourceDriftStatusFilters": ["MODIFIED", "DELETED", "NOT_CHECKED", "IN_SYNC"],
        }
        if next_token:
            kwargs["NextToken"] = next_token
        resp = self._client.describe_stack_resource_drifts(**kwargs)
        # ... process resp["StackResourceDrifts"] ...
        next_token = resp.get("NextToken")
        if not next_token:
            break
    return results
```

---

### M-3: No upper bound on --max-concurrent allows resource exhaustion

**File:** `src/stackdrift/cli.py:31`
**CWE:** CWE-770 (Allocation of Resources Without Limits)

The `--max-concurrent` CLI option accepts any positive integer with no upper bound. A value like `--max-concurrent 10000` would:
- Create 10,000 threads, exhausting system memory
- Trigger aggressive AWS API throttling (CloudFormation rate limits)
- Potentially cause cascading failures in shared AWS accounts

**Recommendation:** Add a reasonable upper bound:
```python
@click.option("--max-concurrent", type=click.IntRange(1, 50), default=5,
              help="Max concurrent drift detections (1-50).")
```

---

### M-4: Silent failure swallowing masks detection gaps

**File:** `src/stackdrift/detector.py:58-59`
**CWE:** CWE-392 (Missing Report of Error Condition)

When a drift detection fails for a stack, the exception is logged but the stack is silently omitted from results. The CLI exit code (0 = no drift) does not distinguish between "all stacks checked and clean" and "some stacks failed to check." A security tool must clearly surface incomplete results.

```python
except Exception:
    logger.exception("Failed to detect drift for %s", stack_info["stack_name"])
    # Stack silently dropped from results
```

**Recommendation:**
1. Track failed stacks and include them in the output summary (e.g., "3/5 stacks checked, 2 failed")
2. Consider exit code 2 (error) when any stacks fail, or add a `--strict` flag for this behavior
3. At minimum, print a warning to stderr summarizing failures

---

### M-5: CI/CD supply chain — GitHub Actions not pinned by SHA

**Files:** `.github/workflows/ci.yml`, `.github/workflows/release.yml`
**CWE:** CWE-829 (Inclusion of Functionality from Untrusted Control Sphere)

All GitHub Actions are referenced by mutable tag (e.g., `@v4`, `@v5`, `@v2`) rather than immutable commit SHA. This is vulnerable to supply chain attacks if an action maintainer's account is compromised — the tag can be silently re-pointed to malicious code.

The third-party action `softprops/action-gh-release@v2` is highest risk since it has `contents: write` permissions.

**Recommendation:** Pin all actions to full commit SHAs:
```yaml
# Instead of:
- uses: actions/checkout@v4
# Use:
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
```

---

## LOW Severity Findings

### L-1: DiffType enum is incomplete — possible crash on valid AWS responses

**File:** `src/stackdrift/models.py:36-38`

The `DiffType` enum only defines `NOT_EQUAL`. The AWS API can also return `ADD` and `REMOVE` difference types. Encountering these will raise an unhandled `ValueError`, crashing the tool.

**Recommendation:** Add missing enum values:
```python
class DiffType(StrEnum):
    ADD = "ADD"
    REMOVE = "REMOVE"
    NOT_EQUAL = "NOT_EQUAL"
```

---

### L-2: No input sanitization for markdown injection

**File:** `src/stackdrift/formatter.py:86-108`

Stack names, resource IDs, and property values are interpolated directly into Markdown table rows without escaping. While CloudFormation stack names are constrained by AWS naming rules, property values could contain characters that break markdown rendering or, in web contexts that render markdown unsafely, inject content.

**Recommendation:** Escape pipe characters (`|`) and backtick sequences in table cell values before rendering.

---

### L-3: Dependencies have no upper version bounds

**File:** `pyproject.toml:27-32`

All dependencies use `>=` without upper bounds:
```toml
dependencies = [
    "boto3>=1.34",
    "click>=8.1",
    "rich>=13.7",
    "requests>=2.31",
]
```

A future major version release with breaking changes or a compromised release could be silently installed.

**Recommendation:** Add compatible-release bounds:
```toml
dependencies = [
    "boto3>=1.34,<2",
    "click>=8.1,<9",
    "rich>=13.7,<15",
    "requests>=2.31,<3",
]
```

---

### L-4: Logging may expose infrastructure details

**File:** `src/stackdrift/detector.py:59, 73-76`

Stack names and AWS error reasons are logged via `logger.exception()` and `logger.warning()`. In centralized logging environments, this could expose naming conventions and AWS-specific error details to audiences with log access but not infrastructure access.

**Recommendation:** Ensure logging configuration guidance notes that stack names may appear in logs. Consider adding a `--quiet` flag that suppresses warning-level messages.

---

### L-5: No request timeout documentation or override

**Files:** `src/stackdrift/integrations/slack.py:11`, `src/stackdrift/integrations/github.py:22`

Both integrations hardcode a 30-second timeout. While this is reasonable, there's no way to override it. In slow network environments, this could cause silent failures. Conversely, 30 seconds is a long time to wait for a webhook post in CI/CD pipelines.

**Recommendation:** Consider making the timeout configurable or documenting the 30-second default.

---

### L-6: Test fixtures contain example token patterns

**File:** `tests/test_integrations.py:42`

The test file contains `"ghp_test123"` as a token value. While this is clearly a test fixture and not a real token, some secret scanning tools may flag `ghp_*` patterns. Using a clearly non-token string avoids false positives.

**Recommendation:** Use a value like `"test-token-not-real"` instead of `"ghp_test123"`.

---

## Positive Security Observations

The following security practices are already well-implemented:

1. **Frozen dataclasses** — All models use `@dataclass(frozen=True)`, ensuring thread safety in the concurrent `ThreadPoolExecutor` execution
2. **Minimal permissions in CI** — `ci.yml` correctly uses `permissions: contents: read`
3. **Comprehensive .gitignore** — Properly excludes `.env`, credentials, SSH keys, PEM files, and other sensitive patterns
4. **No shell command execution** — The tool avoids `subprocess`, `os.system()`, or any shell-out patterns, eliminating command injection risks
5. **Type-safe CLI options** — Click's `type=int` for `--post-github-pr` and `type=click.Choice()` for `--format` prevent type confusion
6. **No persistent storage** — Results are processed in-memory and output immediately, with no local caches or databases that could leak data
7. **HTTPS by default** — GitHub API calls use HTTPS. Slack webhooks are HTTPS by Slack's design
8. **Timeout on HTTP requests** — Both integrations set explicit 30-second timeouts, preventing indefinite hangs
9. **Dependabot configured** — Automated dependency updates help catch known vulnerabilities
10. **SECURITY.md exists** — Responsible disclosure policy with clear SLAs

---

## Remediation Priority

| Priority | Finding | Effort |
|----------|---------|--------|
| 1        | H-1: Validate Slack webhook URL | Low |
| 2        | H-2: Validate GitHub repo format | Low |
| 3        | M-2: Add pagination to get_resource_drifts | Low |
| 4        | M-3: Cap --max-concurrent | Trivial |
| 5        | M-4: Surface failed stack detections | Medium |
| 6        | M-5: Pin GitHub Actions to SHA | Low |
| 7        | M-1: Add value redaction option | Medium |
| 8        | L-1: Complete DiffType enum | Trivial |
| 9        | L-2: Escape markdown cell values | Low |
| 10       | L-3: Add dependency upper bounds | Trivial |
| 11       | L-4: Document logging behavior | Trivial |
| 12       | L-5: Document/configure timeouts | Trivial |
| 13       | L-6: Use non-ghp test tokens | Trivial |
