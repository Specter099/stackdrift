"""Tests for stackdrift data models."""

from datetime import datetime

from stackdrift.models import (
    DetectionResult,
    DetectionRun,
    DetectionStatus,
    DiffType,
    PropertyDiff,
    ResourceDrift,
    ResourceStatus,
    StackDriftResult,
    StackStatus,
)


def test_detection_status_values():
    """Test DetectionStatus enum has correct AWS API values."""
    assert DetectionStatus.IN_PROGRESS.value == "DETECTION_IN_PROGRESS"
    assert DetectionStatus.COMPLETE.value == "DETECTION_COMPLETE"
    assert DetectionStatus.FAILED.value == "DETECTION_FAILED"


def test_stack_status_values():
    """Test StackStatus enum has correct AWS API values."""
    assert StackStatus.DRIFTED.value == "DRIFTED"
    assert StackStatus.IN_SYNC.value == "IN_SYNC"
    assert StackStatus.NOT_CHECKED.value == "NOT_CHECKED"
    assert StackStatus.UNKNOWN.value == "UNKNOWN"


def test_resource_status_values():
    """Test ResourceStatus enum has correct AWS API values."""
    assert ResourceStatus.IN_SYNC.value == "IN_SYNC"
    assert ResourceStatus.MODIFIED.value == "MODIFIED"
    assert ResourceStatus.DELETED.value == "DELETED"
    assert ResourceStatus.NOT_CHECKED.value == "NOT_CHECKED"
    assert ResourceStatus.UNKNOWN.value == "UNKNOWN"
    assert ResourceStatus.UNSUPPORTED.value == "UNSUPPORTED"


def test_diff_type_values():
    """Test DiffType enum has correct AWS API values."""
    assert DiffType.ADD.value == "ADD"
    assert DiffType.REMOVE.value == "REMOVE"
    assert DiffType.NOT_EQUAL.value == "NOT_EQUAL"


def test_enums_are_string_enums():
    """Test enums inherit from str for easy serialization."""
    assert isinstance(DetectionStatus.IN_PROGRESS, str)
    assert isinstance(StackStatus.DRIFTED, str)
    assert isinstance(ResourceStatus.MODIFIED, str)
    assert isinstance(DiffType.NOT_EQUAL, str)


def test_property_diff_creation():
    """Test PropertyDiff dataclass can be created with all fields."""
    diff = PropertyDiff(
        property_path="/Properties/DelaySeconds",
        expected_value="0",
        actual_value="5",
        diff_type=DiffType.NOT_EQUAL,
    )

    assert diff.property_path == "/Properties/DelaySeconds"
    assert diff.expected_value == "0"
    assert diff.actual_value == "5"
    assert diff.diff_type == DiffType.NOT_EQUAL


def test_property_diff_is_frozen():
    """Test PropertyDiff is immutable."""
    diff = PropertyDiff(
        property_path="/Properties/Test",
        expected_value="a",
        actual_value="b",
        diff_type=DiffType.NOT_EQUAL,
    )

    try:
        diff.expected_value = "changed"
        assert False, "Should not be able to modify frozen dataclass"
    except AttributeError:
        pass  # Expected


def test_resource_drift_creation():
    """Test ResourceDrift dataclass can be created with all fields."""
    timestamp = datetime(2026, 2, 25, 13, 30, 0)

    drift = ResourceDrift(
        logical_id="MyQueue",
        physical_id="https://sqs.us-east-1.amazonaws.com/123456789012/my-queue",
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
        timestamp=timestamp,
    )

    assert drift.logical_id == "MyQueue"
    assert drift.physical_id == "https://sqs.us-east-1.amazonaws.com/123456789012/my-queue"
    assert drift.resource_type == "AWS::SQS::Queue"
    assert drift.status == ResourceStatus.MODIFIED
    assert len(drift.property_diffs) == 1
    assert drift.timestamp == timestamp


def test_resource_drift_in_sync_has_empty_diffs():
    """Test ResourceDrift with IN_SYNC status can have empty property_diffs."""
    drift = ResourceDrift(
        logical_id="MyBucket",
        physical_id="my-bucket-name",
        resource_type="AWS::S3::Bucket",
        status=ResourceStatus.IN_SYNC,
        property_diffs=[],
        timestamp=datetime.now(),
    )

    assert drift.status == ResourceStatus.IN_SYNC
    assert drift.property_diffs == []


def test_resource_drift_is_frozen():
    """Test ResourceDrift is immutable."""
    drift = ResourceDrift(
        logical_id="Test",
        physical_id="test-id",
        resource_type="AWS::Test::Resource",
        status=ResourceStatus.IN_SYNC,
        property_diffs=[],
        timestamp=datetime.now(),
    )

    try:
        drift.status = ResourceStatus.MODIFIED
        assert False, "Should not be able to modify frozen dataclass"
    except AttributeError:
        pass  # Expected


def test_stack_drift_result_creation():
    """Test StackDriftResult dataclass can be created with all fields."""
    timestamp = datetime(2026, 2, 25, 14, 0, 0)

    result = StackDriftResult(
        stack_id="arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/uuid",
        stack_name="my-stack",
        stack_status=StackStatus.DRIFTED,
        resource_drifts=[
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
                timestamp=timestamp,
            )
        ],
        detection_id="b78ac9b0-dec1-11e7-a451-503a3example",
        timestamp=timestamp,
        drifted_resource_count=1,
    )

    assert result.stack_id == "arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/uuid"
    assert result.stack_name == "my-stack"
    assert result.stack_status == StackStatus.DRIFTED
    assert len(result.resource_drifts) == 1
    assert result.detection_id == "b78ac9b0-dec1-11e7-a451-503a3example"
    assert result.timestamp == timestamp
    assert result.drifted_resource_count == 1


def test_stack_drift_result_in_sync():
    """Test StackDriftResult for stack with no drift."""
    result = StackDriftResult(
        stack_id="arn:aws:cloudformation:us-east-1:123456789012:stack/clean-stack/uuid",
        stack_name="clean-stack",
        stack_status=StackStatus.IN_SYNC,
        resource_drifts=[],
        detection_id="detection-id",
        timestamp=datetime.now(),
        drifted_resource_count=0,
    )

    assert result.stack_status == StackStatus.IN_SYNC
    assert result.resource_drifts == []
    assert result.drifted_resource_count == 0


def test_stack_drift_result_is_frozen():
    """Test StackDriftResult is immutable."""
    result = StackDriftResult(
        stack_id="arn",
        stack_name="test",
        stack_status=StackStatus.IN_SYNC,
        resource_drifts=[],
        detection_id="id",
        timestamp=datetime.now(),
        drifted_resource_count=0,
    )

    try:
        result.stack_status = StackStatus.DRIFTED
        assert False, "Should not be able to modify frozen dataclass"
    except AttributeError:
        pass  # Expected


def test_detection_run_in_progress():
    """Test DetectionRun dataclass for in-progress detection."""
    started_at = datetime(2026, 2, 25, 14, 0, 0)

    run = DetectionRun(
        detection_id="abc123",
        stack_id="arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/uuid",
        stack_name="my-stack",
        status=DetectionStatus.IN_PROGRESS,
        started_at=started_at,
    )

    assert run.detection_id == "abc123"
    assert run.stack_id == "arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/uuid"
    assert run.stack_name == "my-stack"
    assert run.status == DetectionStatus.IN_PROGRESS
    assert run.started_at == started_at
    assert run.stack_status is None
    assert run.drifted_resource_count is None
    assert run.status_reason is None


def test_detection_run_complete():
    """Test DetectionRun dataclass for completed detection."""
    started_at = datetime(2026, 2, 25, 14, 0, 0)

    run = DetectionRun(
        detection_id="abc123",
        stack_id="arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/uuid",
        stack_name="my-stack",
        status=DetectionStatus.COMPLETE,
        started_at=started_at,
        stack_status=StackStatus.DRIFTED,
        drifted_resource_count=3,
    )

    assert run.status == DetectionStatus.COMPLETE
    assert run.stack_status == StackStatus.DRIFTED
    assert run.drifted_resource_count == 3
    assert run.status_reason is None


def test_detection_run_failed():
    """Test DetectionRun dataclass for failed detection."""
    started_at = datetime(2026, 2, 25, 14, 0, 0)

    run = DetectionRun(
        detection_id="abc123",
        stack_id="arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/uuid",
        stack_name="my-stack",
        status=DetectionStatus.FAILED,
        started_at=started_at,
        status_reason="Stack does not exist",
    )

    assert run.status == DetectionStatus.FAILED
    assert run.status_reason == "Stack does not exist"
    assert run.stack_status is None
    assert run.drifted_resource_count is None


def test_detection_run_is_frozen():
    """Test DetectionRun is immutable."""
    run = DetectionRun(
        detection_id="test",
        stack_id="arn",
        stack_name="test",
        status=DetectionStatus.IN_PROGRESS,
        started_at=datetime.now(),
    )

    try:
        run.status = DetectionStatus.COMPLETE
        assert False, "Should not be able to modify frozen dataclass"
    except AttributeError:
        pass  # Expected


def test_detection_result_creation():
    """Test DetectionResult tracks results and failed stacks."""
    result = DetectionResult(
        results=[
            StackDriftResult(
                stack_id="arn",
                stack_name="good-stack",
                stack_status=StackStatus.IN_SYNC,
                resource_drifts=[],
                detection_id="det-1",
                timestamp=datetime.now(),
                drifted_resource_count=0,
            )
        ],
        failed_stacks=["bad-stack"],
    )

    assert len(result.results) == 1
    assert result.results[0].stack_name == "good-stack"
    assert result.failed_stacks == ["bad-stack"]
