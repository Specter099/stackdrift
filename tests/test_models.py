"""Tests for stackdrift data models."""
from stackdrift.models import DetectionStatus, StackStatus, ResourceStatus, DiffType, PropertyDiff


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


def test_property_diff_creation():
    """Test PropertyDiff dataclass can be created with all fields."""
    diff = PropertyDiff(
        property_path="/Properties/DelaySeconds",
        expected_value="0",
        actual_value="5",
        diff_type=DiffType.NOT_EQUAL
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
        diff_type=DiffType.NOT_EQUAL
    )

    try:
        diff.expected_value = "changed"
        assert False, "Should not be able to modify frozen dataclass"
    except AttributeError:
        pass  # Expected
