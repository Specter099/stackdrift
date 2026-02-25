"""Tests for Slack and GitHub integrations."""

from unittest.mock import MagicMock, patch

import pytest

from stackdrift.integrations.github import post_to_github_pr
from stackdrift.integrations.slack import post_to_slack


def test_post_to_slack_sends_payload():
    with patch("stackdrift.integrations.slack.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        post_to_slack("## Drift Report\nSome drift", "https://hooks.slack.example.com/test")

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0] == "https://hooks.slack.example.com/test"
        payload = call_kwargs[1]["json"]
        assert "Drift Report" in payload["text"]


def test_post_to_slack_raises_on_failure():
    with patch("stackdrift.integrations.slack.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=500, text="Server Error")
        mock_post.return_value.raise_for_status.side_effect = Exception("500 Server Error")

        with pytest.raises(Exception, match="500"):
            post_to_slack("report", "https://hooks.slack.example.com/test")


def test_post_to_github_pr_creates_comment():
    with patch("stackdrift.integrations.github.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=201)

        post_to_github_pr(
            body="## Drift Report",
            repo="Specter099/stackdrift",
            pr_number=42,
            token="ghp_test123",
        )

        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        assert "Specter099/stackdrift" in url
        assert "/42/" in url
        payload = mock_post.call_args[1]["json"]
        assert payload["body"] == "## Drift Report"


def test_post_to_github_pr_raises_on_failure():
    with patch("stackdrift.integrations.github.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=403, text="Forbidden")
        mock_post.return_value.raise_for_status.side_effect = Exception("403 Forbidden")

        with pytest.raises(Exception, match="403"):
            post_to_github_pr("report", "owner/repo", 1, "bad-token")
