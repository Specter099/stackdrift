"""Post drift reports to Slack via incoming webhook."""

import requests


def post_to_slack(report: str, webhook_url: str) -> None:
    """Post a drift report to a Slack incoming webhook."""
    response = requests.post(
        webhook_url,
        json={"text": report},
        timeout=30,
    )
    response.raise_for_status()
