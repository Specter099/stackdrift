"""Post drift reports as GitHub PR comments."""

import requests


def post_to_github_pr(
    body: str,
    repo: str,
    pr_number: int,
    token: str,
) -> None:
    """Post a drift report as a comment on a GitHub pull request."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    response = requests.post(
        url,
        json={"body": body},
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
        timeout=30,
    )
    response.raise_for_status()
