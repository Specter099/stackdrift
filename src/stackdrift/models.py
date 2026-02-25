"""Core data models for CloudFormation drift detection."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class DetectionStatus(StrEnum):
    """Status of a drift detection operation."""

    IN_PROGRESS = "DETECTION_IN_PROGRESS"
    COMPLETE = "DETECTION_COMPLETE"
    FAILED = "DETECTION_FAILED"


class StackStatus(StrEnum):
    """Overall stack drift status."""

    DRIFTED = "DRIFTED"
    IN_SYNC = "IN_SYNC"
    NOT_CHECKED = "NOT_CHECKED"
    UNKNOWN = "UNKNOWN"


class ResourceStatus(StrEnum):
    """Individual resource drift status."""

    IN_SYNC = "IN_SYNC"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    NOT_CHECKED = "NOT_CHECKED"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


class DiffType(StrEnum):
    """Property difference type."""

    NOT_EQUAL = "NOT_EQUAL"


@dataclass(frozen=True)
class PropertyDiff:
    """A single property difference between expected and actual configuration."""

    property_path: str
    expected_value: str
    actual_value: str
    diff_type: DiffType


@dataclass(frozen=True)
class ResourceDrift:
    """Drift information for a single CloudFormation resource."""

    logical_id: str
    physical_id: str
    resource_type: str
    status: ResourceStatus
    property_diffs: list[PropertyDiff]
    timestamp: datetime


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


@dataclass(frozen=True)
class DetectionRun:
    """Tracks an in-progress drift detection operation for polling."""

    detection_id: str
    stack_id: str
    stack_name: str
    status: DetectionStatus
    started_at: datetime
    stack_status: StackStatus | None = None
    drifted_resource_count: int | None = None
    status_reason: str | None = None
