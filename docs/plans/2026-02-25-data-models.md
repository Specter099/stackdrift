# Data Models Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement core data models (enums and dataclasses) for CloudFormation drift detection results.

**Architecture:** Frozen dataclasses with explicit Optional types. Four enums (DetectionStatus, StackStatus, ResourceStatus, DiffType) and four dataclasses (PropertyDiff, ResourceDrift, StackDriftResult, DetectionRun). Immutable for thread safety in concurrent operations.

**Tech Stack:** Python 3.11+, dataclasses, enum, pytest

---

## Task 1: Create Enums

**Files:**
- Create: `src/stackdrift/models.py`
- Test: `tests/test_models.py`

**Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py -v
```

Expected: FAIL with "cannot import name 'DetectionStatus'"

**Step 3: Write minimal implementation**

Create `src/stackdrift/models.py`:

```python
"""Core data models for CloudFormation drift detection."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class DetectionStatus(str, Enum):
    """Status of a drift detection operation."""
    IN_PROGRESS = "DETECTION_IN_PROGRESS"
    COMPLETE = "DETECTION_COMPLETE"
    FAILED = "DETECTION_FAILED"


class StackStatus(str, Enum):
    """Overall stack drift status."""
    DRIFTED = "DRIFTED"
    IN_SYNC = "IN_SYNC"
    NOT_CHECKED = "NOT_CHECKED"
    UNKNOWN = "UNKNOWN"


class ResourceStatus(str, Enum):
    """Individual resource drift status."""
    IN_SYNC = "IN_SYNC"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    NOT_CHECKED = "NOT_CHECKED"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


class DiffType(str, Enum):
    """Property difference type."""
    NOT_EQUAL = "NOT_EQUAL"
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_models.py::test_detection_status_values -v
pytest tests/test_models.py::test_stack_status_values -v
pytest tests/test_models.py::test_resource_status_values -v
pytest tests/test_models.py::test_diff_type_values -v
pytest tests/test_models.py::test_enums_are_string_enums -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/stackdrift/models.py tests/test_models.py
git commit -m "feat: add core enums for drift detection

Add DetectionStatus, StackStatus, ResourceStatus, and DiffType enums.
All inherit from str for JSON serialization.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Create PropertyDiff Dataclass

**Files:**
- Modify: `src/stackdrift/models.py`
- Modify: `tests/test_models.py`

**Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
from stackdrift.models import PropertyDiff


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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py::test_property_diff_creation -v
pytest tests/test_models.py::test_property_diff_is_frozen -v
```

Expected: FAIL with "cannot import name 'PropertyDiff'"

**Step 3: Write minimal implementation**

Add to `src/stackdrift/models.py`:

```python
@dataclass(frozen=True)
class PropertyDiff:
    """A single property difference between expected and actual configuration."""
    property_path: str
    expected_value: str
    actual_value: str
    diff_type: DiffType
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_models.py::test_property_diff_creation -v
pytest tests/test_models.py::test_property_diff_is_frozen -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/stackdrift/models.py tests/test_models.py
git commit -m "feat: add PropertyDiff dataclass

Represents a single property difference with path, expected/actual values,
and diff type. Frozen for immutability.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Create ResourceDrift Dataclass

**Files:**
- Modify: `src/stackdrift/models.py`
- Modify: `tests/test_models.py`

**Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
from datetime import datetime
from stackdrift.models import ResourceDrift


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
                diff_type=DiffType.NOT_EQUAL
            )
        ],
        timestamp=timestamp
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
        timestamp=datetime.now()
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
        timestamp=datetime.now()
    )

    try:
        drift.status = ResourceStatus.MODIFIED
        assert False, "Should not be able to modify frozen dataclass"
    except AttributeError:
        pass  # Expected
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py::test_resource_drift_creation -v
pytest tests/test_models.py::test_resource_drift_in_sync_has_empty_diffs -v
pytest tests/test_models.py::test_resource_drift_is_frozen -v
```

Expected: FAIL with "cannot import name 'ResourceDrift'"

**Step 3: Write minimal implementation**

Add to `src/stackdrift/models.py`:

```python
@dataclass(frozen=True)
class ResourceDrift:
    """Drift information for a single CloudFormation resource."""
    logical_id: str
    physical_id: str
    resource_type: str
    status: ResourceStatus
    property_diffs: list[PropertyDiff]
    timestamp: datetime
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_models.py::test_resource_drift_creation -v
pytest tests/test_models.py::test_resource_drift_in_sync_has_empty_diffs -v
pytest tests/test_models.py::test_resource_drift_is_frozen -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/stackdrift/models.py tests/test_models.py
git commit -m "feat: add ResourceDrift dataclass

Represents drift info for a single CloudFormation resource including
logical/physical IDs, resource type, status, property diffs, and timestamp.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Create StackDriftResult Dataclass

**Files:**
- Modify: `src/stackdrift/models.py`
- Modify: `tests/test_models.py`

**Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
from stackdrift.models import StackDriftResult


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
                        diff_type=DiffType.NOT_EQUAL
                    )
                ],
                timestamp=timestamp
            )
        ],
        detection_id="b78ac9b0-dec1-11e7-a451-503a3example",
        timestamp=timestamp,
        drifted_resource_count=1
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
        drifted_resource_count=0
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
        drifted_resource_count=0
    )

    try:
        result.stack_status = StackStatus.DRIFTED
        assert False, "Should not be able to modify frozen dataclass"
    except AttributeError:
        pass  # Expected
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py::test_stack_drift_result_creation -v
pytest tests/test_models.py::test_stack_drift_result_in_sync -v
pytest tests/test_models.py::test_stack_drift_result_is_frozen -v
```

Expected: FAIL with "cannot import name 'StackDriftResult'"

**Step 3: Write minimal implementation**

Add to `src/stackdrift/models.py`:

```python
@dataclass(frozen=True)
class StackDriftResult:
    """Complete drift detection results for a single stack."""
    stack_id: str
    stack_name: str
    stack_status: StackStatus
    resource_drifts: list[ResourceDrift]
    detection_id: str
    timestamp: datetime
    drifted_resource_count: int
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_models.py::test_stack_drift_result_creation -v
pytest tests/test_models.py::test_stack_drift_result_in_sync -v
pytest tests/test_models.py::test_stack_drift_result_is_frozen -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/stackdrift/models.py tests/test_models.py
git commit -m "feat: add StackDriftResult dataclass

Represents complete drift detection results for a single stack including
stack metadata, resource drifts, and drift count.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Create DetectionRun Dataclass

**Files:**
- Modify: `src/stackdrift/models.py`
- Modify: `tests/test_models.py`

**Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
from stackdrift.models import DetectionRun


def test_detection_run_in_progress():
    """Test DetectionRun dataclass for in-progress detection."""
    started_at = datetime(2026, 2, 25, 14, 0, 0)

    run = DetectionRun(
        detection_id="abc123",
        stack_id="arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/uuid",
        stack_name="my-stack",
        status=DetectionStatus.IN_PROGRESS,
        started_at=started_at
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
        drifted_resource_count=3
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
        status_reason="Stack does not exist"
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
        started_at=datetime.now()
    )

    try:
        run.status = DetectionStatus.COMPLETE
        assert False, "Should not be able to modify frozen dataclass"
    except AttributeError:
        pass  # Expected
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py::test_detection_run_in_progress -v
pytest tests/test_models.py::test_detection_run_complete -v
pytest tests/test_models.py::test_detection_run_failed -v
pytest tests/test_models.py::test_detection_run_is_frozen -v
```

Expected: FAIL with "cannot import name 'DetectionRun'"

**Step 3: Write minimal implementation**

Add to `src/stackdrift/models.py`:

```python
@dataclass(frozen=True)
class DetectionRun:
    """Tracks an in-progress drift detection operation for polling."""
    detection_id: str
    stack_id: str
    stack_name: str
    status: DetectionStatus
    started_at: datetime
    stack_status: Optional[StackStatus] = None
    drifted_resource_count: Optional[int] = None
    status_reason: Optional[str] = None
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_models.py::test_detection_run_in_progress -v
pytest tests/test_models.py::test_detection_run_complete -v
pytest tests/test_models.py::test_detection_run_failed -v
pytest tests/test_models.py::test_detection_run_is_frozen -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/stackdrift/models.py tests/test_models.py
git commit -m "feat: add DetectionRun dataclass

Represents an in-progress drift detection operation with optional fields
for polling state. Converts to StackDriftResult when complete.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Run Full Test Suite and Verify

**Step 1: Run all tests**

```bash
pytest tests/test_models.py -v
```

Expected: All tests PASS

**Step 2: Check test coverage**

```bash
pytest tests/test_models.py --cov=src/stackdrift/models --cov-report=term-missing
```

Expected: 100% coverage on models.py

**Step 3: Run linter**

```bash
ruff check src/stackdrift/models.py tests/test_models.py
```

Expected: No issues

**Step 4: Format check**

```bash
ruff format --check src/stackdrift/models.py tests/test_models.py
```

Expected: No issues (or format if needed with `ruff format`)

**Step 5: Final verification commit (if needed)**

If any formatting changes were made:

```bash
git add src/stackdrift/models.py tests/test_models.py
git commit -m "style: format data models and tests

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Completion Criteria

- [ ] All enums defined with correct AWS API values
- [ ] All dataclasses defined with correct fields and types
- [ ] All dataclasses are frozen (immutable)
- [ ] All tests pass
- [ ] 100% test coverage on models.py
- [ ] Linter passes
- [ ] Code properly formatted
- [ ] All work committed with descriptive messages

## Notes for Implementation

1. **Import order**: Python standard library imports first (dataclasses, datetime, enum, typing)
2. **Type hints**: Use modern syntax (`list[X]` not `List[X]` since we require Python 3.11+)
3. **Test isolation**: Each test function should be independent
4. **Frozen enforcement**: Test that dataclasses raise AttributeError on modification attempts
5. **Optional fields**: Only DetectionRun has Optional fields, all others are fully required

## References

- Design document: [docs/plans/2026-02-25-data-models-design.md](2026-02-25-data-models-design.md)
- AWS CloudFormation API: [DescribeStackResourceDrifts](https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_DescribeStackResourceDrifts.html)
