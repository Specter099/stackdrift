"""Tests for stackdrift data models."""
from stackdrift.models import DetectionStatus, StackStatus, ResourceStatus, DiffType


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
    assert DiffType.NOT_EQUAL.value == "NOT_EQUAL"


def test_enums_are_string_enums():
    """Test enums inherit from str for easy serialization."""
    assert isinstance(DetectionStatus.IN_PROGRESS, str)
    assert isinstance(StackStatus.DRIFTED, str)
    assert isinstance(ResourceStatus.MODIFIED, str)
    assert isinstance(DiffType.NOT_EQUAL, str)
