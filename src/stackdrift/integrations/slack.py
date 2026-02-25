"""Post drift reports to Slack via incoming webhook."""

from urllib.parse import urlparse

import requests

ALLOWED_SLACK_HOSTS = {"hooks.slack.com", "hooks.slack-gov.com"}


def post_to_slack(report: str, webhook_url: str, timeout: int = 30) -> None:
    """Post a drift report to a Slack incoming webhook."""
    parsed = urlparse(webhook_url)
    if parsed.scheme != "https":
        raise ValueError("Slack webhook URL must use HTTPS")
    if parsed.hostname not in ALLOWED_SLACK_HOSTS:
        raise ValueError(
            f"Invalid Slack webhook host {parsed.hostname!r}: "
            f"must be one of {sorted(ALLOWED_SLACK_HOSTS)}"
        )
    response = requests.post(
        webhook_url,
        json={"text": report},
        timeout=timeout,
    )
    response.raise_for_status()
