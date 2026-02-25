# Data Models Design - stackdrift

**Date:** 2026-02-25
**Status:** Approved
**Phase:** Phase 2 - Core Data Models

## Overview

This document describes the core data models for stackdrift, a CloudFormation drift detector. These models represent AWS CloudFormation drift detection states and results using Python dataclasses.

## Design Approach

**Selected Approach:** Frozen Dataclasses with Strict Types

- Use Python's `@dataclass(frozen=True)` for immutability
- Explicit `Optional[]` types for fields that may be None
- Standard library only (no extra dependencies)
- Thread-safe for concurrent drift detection operations

**Rationale:**
- Immutability prevents bugs in concurrent code (ThreadPoolExecutor)
- Standard library keeps the project lightweight
- Explicit Optional types make the API crystal clear
- No runtime overhead from validation libraries

## Data Model Hierarchy

```
DetectionRun (polling state)
    ↓ (converts to)
StackDriftResult
    ├── ResourceDrift (list)
    │   └── PropertyDiff (list)
    └── Metadata (stack_id, timestamps, counts)
```

## Enums

### DetectionStatus

Tracks drift detection operation progress.

```python
class DetectionStatus(str, Enum):
    IN_PROGRESS = "DETECTION_IN_PROGRESS"
    COMPLETE = "DETECTION_COMPLETE"
    FAILED = "DETECTION_FAILED"
```

**Source:** AWS CloudFormation `DescribeStackDriftDetectionStatus.DetectionStatus`

### StackStatus

Overall stack drift state.

```python
class StackStatus(str, Enum):
    DRIFTED = "DRIFTED"
    IN_SYNC = "IN_SYNC"
    NOT_CHECKED = "NOT_CHECKED"
    UNKNOWN = "UNKNOWN"
```

**Source:** AWS CloudFormation `DescribeStackDriftDetectionStatus.StackDriftStatus`

### ResourceStatus

Individual resource drift state.

```python
class ResourceStatus(str, Enum):
    IN_SYNC = "IN_SYNC"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    NOT_CHECKED = "NOT_CHECKED"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"
```

**Source:** AWS CloudFormation `StackResourceDrift.StackResourceDriftStatus`

**Note:** `UNSUPPORTED` indicates CloudFormation doesn't support drift detection for this resource type.

### DiffType

Property difference classification.

```python
class DiffType(str, Enum):
    NOT_EQUAL = "NOT_EQUAL"
```

**Source:** AWS CloudFormation `PropertyDifference.DifferenceType`

**Future expansion:** AWS may add `ADD` and `REMOVE` types for added/removed properties.

## Dataclasses

### PropertyDiff

The smallest unit - represents a single property that drifted.

```python
@dataclass(frozen=True)
class PropertyDiff:
    """A single property difference between expected and actual configuration."""
    property_path: str          # e.g., "/Properties/DelaySeconds"
    expected_value: str         # From CloudFormation template
    actual_value: str           # From actual AWS resource
    diff_type: DiffType         # Currently always NOT_EQUAL
```

**Design decisions:**
- Simple, flat structure with four fields from AWS API
- `property_path` uses JSON pointer notation (AWS format)
- Both values are strings (AWS returns JSON-encoded strings)
- No optional fields - AWS always provides all four values

**Example:**
```python
PropertyDiff(
    property_path="/Properties/DelaySeconds",
    expected_value="0",
    actual_value="5",
    diff_type=DiffType.NOT_EQUAL
)
```

### ResourceDrift

Represents a single CloudFormation resource and all its drift information.

```python
@dataclass(frozen=True)
class ResourceDrift:
    """Drift information for a single CloudFormation resource."""
    logical_id: str                      # CloudFormation logical ID
    physical_id: str                     # AWS physical resource ID
    resource_type: str                   # e.g., "AWS::SQS::Queue"
    status: ResourceStatus               # IN_SYNC, MODIFIED, DELETED, etc.
    property_diffs: list[PropertyDiff]   # Empty list if IN_SYNC
    timestamp: datetime                  # When drift detection ran
```

**Design decisions:**
- Groups all information about one resource's drift
- `property_diffs` is an empty list for `status=IN_SYNC` resources
- `physical_id` and `resource_type` identify the AWS resource
- All fields required - AWS always provides these

**Example:**
```python
ResourceDrift(
    logical_id="MyQueue",
    physical_id="https://sqs.us-east-1.amazonaws.com/123456789012/my-queue",
    resource_type="AWS::SQS::Queue",
    status=ResourceStatus.MODIFIED,
    property_diffs=[
        PropertyDiff(...)
    ],
    timestamp=datetime(2026, 2, 25, 13, 30, 0)
)
```

### StackDriftResult

Represents the final drift detection results for one CloudFormation stack.

```python
@dataclass(frozen=True)
class StackDriftResult:
    """Complete drift detection results for a single stack."""
    stack_id: str                        # Full ARN of the stack
    stack_name: str                      # Human-readable name
    stack_status: StackStatus            # DRIFTED, IN_SYNC, etc.
    resource_drifts: list[ResourceDrift] # All resources checked
    detection_id: str                    # AWS detection ID
    timestamp: datetime                  # When detection completed
    drifted_resource_count: int          # How many resources drifted
```

**Design decisions:**
- Final output after polling completes
- `resource_drifts` may be empty if stack is IN_SYNC
- `stack_name` extracted from ARN for display convenience
- `drifted_resource_count` matches AWS field for quick summaries
- All fields required - represents completed detection

**Example:**
```python
StackDriftResult(
    stack_id="arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/uuid",
    stack_name="my-stack",
    stack_status=StackStatus.DRIFTED,
    resource_drifts=[...],
    detection_id="b78ac9b0-dec1-11e7-a451-503a3example",
    timestamp=datetime(2026, 2, 25, 13, 30, 0),
    drifted_resource_count=3
)
```

### DetectionRun

Represents an in-progress drift detection operation (used during polling).

```python
@dataclass(frozen=True)
class DetectionRun:
    """Tracks an in-progress drift detection operation for polling."""
    detection_id: str                    # AWS detection ID
    stack_id: str                        # Full ARN of the stack
    stack_name: str                      # Human-readable name
    status: DetectionStatus              # IN_PROGRESS, COMPLETE, FAILED
    started_at: datetime                 # When detection was initiated
    stack_status: Optional[StackStatus] = None          # None until COMPLETE
    drifted_resource_count: Optional[int] = None        # None until COMPLETE
    status_reason: Optional[str] = None                 # Explanation if FAILED
```

**Design decisions:**
- Used internally during polling loop
- Three optional fields are `None` during `IN_PROGRESS`
- Converts to `StackDriftResult` when complete
- `status_reason` captures AWS error messages on failure
- Immutable - create new instances as status changes

**Lifecycle example:**
```python
# Initially:
DetectionRun(
    detection_id="abc123",
    stack_id="arn:aws:...",
    stack_name="my-stack",
    status=DetectionStatus.IN_PROGRESS,
    started_at=datetime.now(),
)

# After completion (new instance):
DetectionRun(
    detection_id="abc123",
    stack_id="arn:aws:...",
    stack_name="my-stack",
    status=DetectionStatus.COMPLETE,
    started_at=datetime(...),
    stack_status=StackStatus.DRIFTED,
    drifted_resource_count=3,
)
```

## Key Design Decisions

### 1. Property Storage: Differences Only

**Decision:** Store only `PropertyDifferences`, not full `ExpectedProperties`/`ActualProperties` JSON.

**Rationale:**
- Users care about what changed, not full configuration
- Memory efficient for large stacks
- Most properties unchanged - storing them adds noise
- Focused output in CLI results

### 2. Immutability: Frozen Dataclasses

**Decision:** Use `@dataclass(frozen=True)` for all models.

**Rationale:**
- Concurrent drift detection requires thread-safe models
- Prevents accidental mutation bugs
- Clear separation between construction and use
- Easier to test and reason about

### 3. Enum Naming: Simplified but Clear

**Decision:** Use `DetectionStatus`, `StackStatus`, `ResourceStatus`, `DiffType`.

**Rationale:**
- Shorter than AWS names (e.g., `StackResourceDriftStatus`)
- Clear meaning in context
- Reduces verbosity throughout codebase

### 4. Detection Tracking: Separate DetectionRun Model

**Decision:** Use `DetectionRun` for polling, convert to `StackDriftResult` when complete.

**Rationale:**
- Clean separation between "in progress" and "complete" states
- Optional fields make sense during polling
- Polling logic decoupled from result representation

## AWS API Mapping

| AWS API | stackdrift Model |
|---------|------------------|
| `DetectStackDrift` response | Creates `DetectionRun` |
| `DescribeStackDriftDetectionStatus` | Updates `DetectionRun` |
| `DescribeStackResourceDrifts` | Creates `StackDriftResult` with `ResourceDrift` list |
| `PropertyDifference` | Maps to `PropertyDiff` |

## Implementation Notes

### File Location
`src/stackdrift/models.py`

### Imports Required
```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
```

### Testing Considerations
- Create fixture JSON files from actual AWS responses
- Test enum string serialization for JSON output
- Test frozen=True enforcement (should raise on mutation)
- Test Optional field handling in DetectionRun

## Future Considerations

- If AWS adds `ADD`/`REMOVE` to `DifferenceType`, add to `DiffType` enum
- If we add caching, timestamp fields enable TTL calculations
- If we add historical tracking, these models are the unit of storage

## References

- [AWS CloudFormation API: DescribeStackResourceDrifts](https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_DescribeStackResourceDrifts.html)
- [AWS CloudFormation API: DescribeStackDriftDetectionStatus](https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_DescribeStackDriftDetectionStatus.html)
- [AWS CloudFormation API: DetectStackDrift](https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_DetectStackDrift.html)
