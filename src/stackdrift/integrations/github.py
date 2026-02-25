"""Post drift reports as GitHub PR comments."""

import re

import requests

REPO_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$")


def post_to_github_pr(
    body: str,
    repo: str,
    pr_number: int,
    token: str,
    timeout: int = 30,
) -> None:
    """Post a drift report as a comment on a GitHub pull request."""
    if not REPO_PATTERN.match(repo):
        raise ValueError(f"Invalid GitHub repo format: {repo!r} (expected 'owner/repo')")
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    response = requests.post(
        url,
        json={"body": body},
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
        timeout=timeout,
    )
    response.raise_for_status()
