"""Tests for the CLI entrypoint."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from stackdrift.cli import main
from stackdrift.models import (
    DetectionResult,
    DiffType,
    PropertyDiff,
    ResourceDrift,
    ResourceStatus,
    StackDriftResult,
    StackStatus,
)


@pytest.fixture
def runner():
    return CliRunner()


def _mock_detection(drifted=False, failed_stacks=None):
    if drifted:
        results = [
            StackDriftResult(
                stack_id="arn:aws:cloudformation:us-east-1:123:stack/my-stack/uuid",
                stack_name="my-stack",
                stack_status=StackStatus.DRIFTED,
                resource_drifts=[
                    ResourceDrift(
                        logical_id="MyQueue",
                        physical_id="queue-url",
                        resource_type="AWS::SQS::Queue",
                        status=ResourceStatus.MODIFIED,
                        property_diffs=[
                            PropertyDiff("/Properties/DelaySeconds", "0", "5", DiffType.NOT_EQUAL)
                        ],
                        timestamp=datetime(2026, 2, 25, 13, 30, 0),
                    )
                ],
                detection_id="det-123",
                timestamp=datetime(2026, 2, 25, 13, 30, 0),
                drifted_resource_count=1,
            )
        ]
    else:
        results = [
            StackDriftResult(
                stack_id="arn:...",
                stack_name="clean-stack",
                stack_status=StackStatus.IN_SYNC,
                resource_drifts=[],
                detection_id="det-456",
                timestamp=datetime(2026, 2, 25, 13, 30, 0),
                drifted_resource_count=0,
            )
        ]
    return DetectionResult(results=results, failed_stacks=failed_stacks or [])


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_no_drift_exit_0(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_detection(drifted=False)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, [])
    assert result.exit_code == 0


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_drift_exit_1(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_detection(drifted=True)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, [])
    assert result.exit_code == 1


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_failed_stacks_exit_2(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_detection(drifted=False, failed_stacks=["bad-stack"])
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, [])
    assert result.exit_code == 2
    assert "bad-stack" in result.output


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_json_format(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_detection(drifted=True)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, ["--format", "json"])
    assert result.exit_code == 1
    assert '"stack_name": "my-stack"' in result.output


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_markdown_format(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_detection(drifted=True)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, ["--format", "markdown"])
    assert result.exit_code == 1
    assert "my-stack" in result.output
    assert "DRIFTED" in result.output


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_drifted_only(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_detection(drifted=False)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, ["--drifted-only"])
    assert result.exit_code == 0


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_passes_stack_filter(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_detection(drifted=False)
    mock_detector_cls.return_value = mock_detector

    runner.invoke(main, ["--stack", "my-stack", "--stack", "other-stack"])

    mock_detector.detect.assert_called_once()
    call_kwargs = mock_detector.detect.call_args[1]
    assert call_kwargs["stack_names"] == ("my-stack", "other-stack")


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_passes_prefix_filter(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_detection(drifted=False)
    mock_detector_cls.return_value = mock_detector

    runner.invoke(main, ["--prefix", "prod-"])

    call_kwargs = mock_detector.detect.call_args[1]
    assert call_kwargs["prefix"] == "prod-"


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_passes_tag_filter(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_detection(drifted=False)
    mock_detector_cls.return_value = mock_detector

    runner.invoke(main, ["--tag", "Environment=prod"])

    call_kwargs = mock_detector.detect.call_args[1]
    assert call_kwargs["tags"] == {"Environment": "prod"}


@patch("stackdrift.cli.post_to_slack")
@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_post_slack(mock_client_cls, mock_detector_cls, mock_slack, runner, monkeypatch):
    monkeypatch.setenv("STACKDRIFT_SLACK_WEBHOOK", "https://hooks.slack.com/services/T00/B00/xxx")
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_detection(drifted=True)
    mock_detector_cls.return_value = mock_detector

    runner.invoke(main, ["--post-slack"])

    mock_slack.assert_called_once()


@patch("stackdrift.cli.post_to_github_pr")
@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_post_github_pr(mock_client_cls, mock_detector_cls, mock_gh, runner, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-not-real")
    monkeypatch.setenv("GITHUB_REPO", "Specter099/stackdrift")
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_detection(drifted=True)
    mock_detector_cls.return_value = mock_detector

    runner.invoke(main, ["--post-github-pr", "42"])

    mock_gh.assert_called_once()
    call_kwargs = mock_gh.call_args[1]
    assert call_kwargs["pr_number"] == 42


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_redact_values(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_detection(drifted=True)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, ["--format", "json", "--redact-values"])
    assert result.exit_code == 1
    assert "[REDACTED]" in result.output
    assert '"0"' not in result.output
    assert '"5"' not in result.output


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_max_concurrent_capped(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_detection(drifted=False)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, ["--max-concurrent", "100"])
    assert result.exit_code != 0
    assert "100 is not in the range 1<=x<=50" in result.output
