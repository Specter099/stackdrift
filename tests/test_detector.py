"""Tests for the drift detection orchestrator."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from stackdrift.detector import Detector
from stackdrift.models import (
    DetectionRun,
    DetectionStatus,
    DiffType,
    PropertyDiff,
    ResourceDrift,
    ResourceStatus,
    StackStatus,
)


@pytest.fixture
def mock_cfn_client():
    return MagicMock()


def _make_detection_run(stack_name, status=DetectionStatus.IN_PROGRESS, **kwargs):
    return DetectionRun(
        detection_id=f"det-{stack_name}",
        stack_id=f"arn:aws:cloudformation:us-east-1:123:stack/{stack_name}/uuid",
        stack_name=stack_name,
        status=status,
        started_at=datetime(2026, 2, 25, 13, 0, 0, tzinfo=UTC),
        **kwargs,
    )


def test_detect_single_stack_in_sync(mock_cfn_client):
    mock_cfn_client.list_stacks.return_value = [{"stack_name": "my-stack", "stack_id": "arn:..."}]
    mock_cfn_client.detect_drift.return_value = _make_detection_run("my-stack")
    mock_cfn_client.poll_detection.return_value = _make_detection_run(
        "my-stack",
        status=DetectionStatus.COMPLETE,
        stack_status=StackStatus.IN_SYNC,
        drifted_resource_count=0,
    )
    mock_cfn_client.get_resource_drifts.return_value = []

    detector = Detector(mock_cfn_client, max_concurrent=1, poll_interval=0)
    detection = detector.detect()

    assert len(detection.results) == 1
    assert detection.results[0].stack_name == "my-stack"
    assert detection.results[0].stack_status == StackStatus.IN_SYNC
    assert detection.results[0].drifted_resource_count == 0
    assert detection.failed_stacks == []


def test_detect_single_stack_drifted(mock_cfn_client):
    mock_cfn_client.list_stacks.return_value = [
        {"stack_name": "drifted-stack", "stack_id": "arn:..."}
    ]
    mock_cfn_client.detect_drift.return_value = _make_detection_run("drifted-stack")
    mock_cfn_client.poll_detection.return_value = _make_detection_run(
        "drifted-stack",
        status=DetectionStatus.COMPLETE,
        stack_status=StackStatus.DRIFTED,
        drifted_resource_count=1,
    )
    mock_cfn_client.get_resource_drifts.return_value = [
        ResourceDrift(
            logical_id="MyQueue",
            physical_id="queue-url",
            resource_type="AWS::SQS::Queue",
            status=ResourceStatus.MODIFIED,
            property_diffs=[
                PropertyDiff(
                    property_path="/Properties/DelaySeconds",
                    expected_value="0",
                    actual_value="5",
                    diff_type=DiffType.NOT_EQUAL,
                )
            ],
            timestamp=datetime(2026, 2, 25, 13, 30, 0),
        )
    ]

    detector = Detector(mock_cfn_client, max_concurrent=1, poll_interval=0)
    detection = detector.detect()

    assert len(detection.results) == 1
    assert detection.results[0].stack_status == StackStatus.DRIFTED
    assert detection.results[0].drifted_resource_count == 1
    assert len(detection.results[0].resource_drifts) == 1


def test_detect_multiple_stacks_concurrent(mock_cfn_client):
    mock_cfn_client.list_stacks.return_value = [
        {"stack_name": f"stack-{i}", "stack_id": f"arn:{i}"} for i in range(3)
    ]
    mock_cfn_client.detect_drift.side_effect = [_make_detection_run(f"stack-{i}") for i in range(3)]
    mock_cfn_client.poll_detection.side_effect = [
        _make_detection_run(
            f"stack-{i}",
            status=DetectionStatus.COMPLETE,
            stack_status=StackStatus.IN_SYNC,
            drifted_resource_count=0,
        )
        for i in range(3)
    ]
    mock_cfn_client.get_resource_drifts.return_value = []

    detector = Detector(mock_cfn_client, max_concurrent=3, poll_interval=0)
    detection = detector.detect()

    assert len(detection.results) == 3
    assert mock_cfn_client.detect_drift.call_count == 3


def test_detect_polls_until_complete(mock_cfn_client):
    mock_cfn_client.list_stacks.return_value = [{"stack_name": "slow-stack", "stack_id": "arn:..."}]
    mock_cfn_client.detect_drift.return_value = _make_detection_run("slow-stack")
    mock_cfn_client.poll_detection.side_effect = [
        _make_detection_run("slow-stack", status=DetectionStatus.IN_PROGRESS),
        _make_detection_run("slow-stack", status=DetectionStatus.IN_PROGRESS),
        _make_detection_run(
            "slow-stack",
            status=DetectionStatus.COMPLETE,
            stack_status=StackStatus.IN_SYNC,
            drifted_resource_count=0,
        ),
    ]
    mock_cfn_client.get_resource_drifts.return_value = []

    detector = Detector(mock_cfn_client, max_concurrent=1, poll_interval=0)
    detection = detector.detect()

    assert len(detection.results) == 1
    assert mock_cfn_client.poll_detection.call_count == 3


def test_detect_failed_stack_tracked(mock_cfn_client):
    mock_cfn_client.list_stacks.return_value = [{"stack_name": "bad-stack", "stack_id": "arn:..."}]
    mock_cfn_client.detect_drift.return_value = _make_detection_run("bad-stack")
    mock_cfn_client.poll_detection.return_value = _make_detection_run(
        "bad-stack",
        status=DetectionStatus.FAILED,
        status_reason="Stack is in UPDATE_IN_PROGRESS state",
    )

    detector = Detector(mock_cfn_client, max_concurrent=1, poll_interval=0)
    detection = detector.detect()

    assert len(detection.results) == 0
    assert "bad-stack" in detection.failed_stacks


def test_detect_exception_tracked_as_failure(mock_cfn_client):
    mock_cfn_client.list_stacks.return_value = [{"stack_name": "err-stack", "stack_id": "arn:..."}]
    mock_cfn_client.detect_drift.side_effect = Exception("API error")

    detector = Detector(mock_cfn_client, max_concurrent=1, poll_interval=0)
    detection = detector.detect()

    assert len(detection.results) == 0
    assert "err-stack" in detection.failed_stacks


def test_detect_passes_filters(mock_cfn_client):
    mock_cfn_client.list_stacks.return_value = []

    detector = Detector(mock_cfn_client, max_concurrent=1, poll_interval=0)
    detector.detect(
        stack_names=["s1"],
        prefix="prod-",
        tags={"Env": "prod"},
    )

    mock_cfn_client.list_stacks.assert_called_once_with(
        stack_names=["s1"],
        prefix="prod-",
        tags={"Env": "prod"},
    )


def test_detect_empty_returns_empty_result(mock_cfn_client):
    mock_cfn_client.list_stacks.return_value = []

    detector = Detector(mock_cfn_client, max_concurrent=1, poll_interval=0)
    detection = detector.detect()

    assert detection.results == []
    assert detection.failed_stacks == []
