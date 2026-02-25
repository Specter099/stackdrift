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
