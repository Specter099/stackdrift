# stackdrift Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a pip-installable CloudFormation drift detector with concurrent detection, severity classification, multiple output formats, and Slack/GitHub integrations.

**Architecture:** Layered pipeline — CLI (click) → Detector (ThreadPoolExecutor) → CloudFormationClient (boto3) → Analyzer (severity) → Formatter (table/json/markdown) → Integrations (slack/github). All data flows through frozen dataclasses defined in models.py.

**Tech Stack:** Python 3.11+, boto3, click, rich, requests. Testing: pytest, moto, pytest-mock.

**Branch:** `feature/build-stackdrift`

**Existing code:** Enums (DetectionStatus, StackStatus, ResourceStatus, DiffType), PropertyDiff, ResourceDrift dataclasses, and their tests are already implemented.

---

### Task 1: Complete Data Models — StackDriftResult and DetectionRun

**Files:**
- Modify: `src/stackdrift/models.py:47-56` (append after ResourceDrift)
- Modify: `tests/test_models.py` (append new tests)

**Step 1: Write failing tests for StackDriftResult and DetectionRun**

Append to `tests/test_models.py`:

```python
from stackdrift.models import (
    DetectionStatus,
    StackStatus,
    ResourceStatus,
    DiffType,
    PropertyDiff,
    ResourceDrift,
    StackDriftResult,
    DetectionRun,
)


def test_stack_drift_result_creation():
    timestamp = datetime(2026, 2, 25, 13, 30, 0)
    result = StackDriftResult(
        stack_id="arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/uuid",
        stack_name="my-stack",
        stack_status=StackStatus.DRIFTED,
        resource_drifts=[
            ResourceDrift(
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
        ],
        detection_id="b78ac9b0-dec1-11e7-a451-503a3example",
        timestamp=timestamp,
        drifted_resource_count=1,
    )
    assert result.stack_name == "my-stack"
    assert result.stack_status == StackStatus.DRIFTED
    assert result.drifted_resource_count == 1
    assert len(result.resource_drifts) == 1


def test_stack_drift_result_is_frozen():
    result = StackDriftResult(
        stack_id="arn:aws:cloudformation:us-east-1:123456789012:stack/s/uuid",
        stack_name="s",
        stack_status=StackStatus.IN_SYNC,
        resource_drifts=[],
        detection_id="abc",
        timestamp=datetime.now(),
        drifted_resource_count=0,
    )
    try:
        result.stack_status = StackStatus.DRIFTED
        assert False, "Should not be able to modify frozen dataclass"
    except AttributeError:
        pass


def test_detection_run_creation_in_progress():
    run = DetectionRun(
        detection_id="abc123",
        stack_id="arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/uuid",
        stack_name="my-stack",
        status=DetectionStatus.IN_PROGRESS,
        started_at=datetime(2026, 2, 25, 13, 0, 0),
    )
    assert run.status == DetectionStatus.IN_PROGRESS
    assert run.stack_status is None
    assert run.drifted_resource_count is None
    assert run.status_reason is None


def test_detection_run_creation_complete():
    run = DetectionRun(
        detection_id="abc123",
        stack_id="arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/uuid",
        stack_name="my-stack",
        status=DetectionStatus.COMPLETE,
        started_at=datetime(2026, 2, 25, 13, 0, 0),
        stack_status=StackStatus.DRIFTED,
        drifted_resource_count=3,
    )
    assert run.status == DetectionStatus.COMPLETE
    assert run.stack_status == StackStatus.DRIFTED
    assert run.drifted_resource_count == 3


def test_detection_run_creation_failed():
    run = DetectionRun(
        detection_id="abc123",
        stack_id="arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/uuid",
        stack_name="my-stack",
        status=DetectionStatus.FAILED,
        started_at=datetime(2026, 2, 25, 13, 0, 0),
        status_reason="Stack is in UPDATE_IN_PROGRESS state",
    )
    assert run.status == DetectionStatus.FAILED
    assert run.status_reason == "Stack is in UPDATE_IN_PROGRESS state"


def test_detection_run_is_frozen():
    run = DetectionRun(
        detection_id="abc",
        stack_id="arn",
        stack_name="s",
        status=DetectionStatus.IN_PROGRESS,
        started_at=datetime.now(),
    )
    try:
        run.status = DetectionStatus.COMPLETE
        assert False, "Should not be able to modify frozen dataclass"
    except AttributeError:
        pass
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'StackDriftResult'`

**Step 3: Implement StackDriftResult and DetectionRun**

Append to `src/stackdrift/models.py` after the ResourceDrift class:

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

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/stackdrift/models.py tests/test_models.py
git commit -m "feat: add StackDriftResult and DetectionRun dataclasses"
```

---

### Task 2: AWS Client — CloudFormationClient

**Files:**
- Create: `src/stackdrift/aws/client.py`
- Create: `tests/test_client.py`
- Create: `tests/conftest.py`

**Step 1: Write failing tests for CloudFormationClient**

Create `tests/conftest.py`:

```python
"""Shared test fixtures."""
import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def aws_credentials(monkeypatch):
    """Set dummy AWS credentials for moto."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def cfn_client(aws_credentials):
    """Create a moto-mocked CloudFormation boto3 client."""
    with mock_aws():
        yield boto3.client("cloudformation", region_name="us-east-1")


SIMPLE_TEMPLATE = """{
    "AWSTemplateFormatVersion": "2010-09-09",
    "Resources": {
        "MyQueue": {
            "Type": "AWS::SQS::Queue",
            "Properties": {
                "QueueName": "my-test-queue"
            }
        }
    }
}"""

TAGGED_TEMPLATE = """{
    "AWSTemplateFormatVersion": "2010-09-09",
    "Resources": {
        "MyBucket": {
            "Type": "AWS::S3::Bucket"
        }
    }
}"""
```

Create `tests/test_client.py`:

```python
"""Tests for CloudFormationClient."""
import boto3
import pytest
from moto import mock_aws
from unittest.mock import patch, MagicMock
from datetime import datetime

from stackdrift.aws.client import CloudFormationClient
from stackdrift.models import (
    DetectionRun,
    DetectionStatus,
    StackStatus,
    ResourceStatus,
    ResourceDrift,
    DiffType,
    PropertyDiff,
)
from tests.conftest import SIMPLE_TEMPLATE, TAGGED_TEMPLATE


@mock_aws
def test_list_stacks_returns_all(aws_credentials):
    """list_stacks returns all active stacks when no filters provided."""
    boto_cfn = boto3.client("cloudformation", region_name="us-east-1")
    boto_cfn.create_stack(StackName="stack-a", TemplateBody=SIMPLE_TEMPLATE)
    boto_cfn.create_stack(StackName="stack-b", TemplateBody=SIMPLE_TEMPLATE)

    client = CloudFormationClient(region="us-east-1")
    stacks = client.list_stacks()

    names = [s["stack_name"] for s in stacks]
    assert "stack-a" in names
    assert "stack-b" in names


@mock_aws
def test_list_stacks_prefix_filter(aws_credentials):
    """list_stacks filters by prefix."""
    boto_cfn = boto3.client("cloudformation", region_name="us-east-1")
    boto_cfn.create_stack(StackName="prod-api", TemplateBody=SIMPLE_TEMPLATE)
    boto_cfn.create_stack(StackName="dev-api", TemplateBody=SIMPLE_TEMPLATE)

    client = CloudFormationClient(region="us-east-1")
    stacks = client.list_stacks(prefix="prod-")

    names = [s["stack_name"] for s in stacks]
    assert names == ["prod-api"]


@mock_aws
def test_list_stacks_tag_filter(aws_credentials):
    """list_stacks filters by tag."""
    boto_cfn = boto3.client("cloudformation", region_name="us-east-1")
    boto_cfn.create_stack(
        StackName="tagged-stack",
        TemplateBody=TAGGED_TEMPLATE,
        Tags=[{"Key": "Environment", "Value": "prod"}],
    )
    boto_cfn.create_stack(StackName="untagged-stack", TemplateBody=SIMPLE_TEMPLATE)

    client = CloudFormationClient(region="us-east-1")
    stacks = client.list_stacks(tags={"Environment": "prod"})

    names = [s["stack_name"] for s in stacks]
    assert "tagged-stack" in names
    assert "untagged-stack" not in names


@mock_aws
def test_list_stacks_specific_names(aws_credentials):
    """list_stacks filters by explicit stack names."""
    boto_cfn = boto3.client("cloudformation", region_name="us-east-1")
    boto_cfn.create_stack(StackName="stack-a", TemplateBody=SIMPLE_TEMPLATE)
    boto_cfn.create_stack(StackName="stack-b", TemplateBody=SIMPLE_TEMPLATE)
    boto_cfn.create_stack(StackName="stack-c", TemplateBody=SIMPLE_TEMPLATE)

    client = CloudFormationClient(region="us-east-1")
    stacks = client.list_stacks(stack_names=["stack-a", "stack-c"])

    names = [s["stack_name"] for s in stacks]
    assert sorted(names) == ["stack-a", "stack-c"]


def test_detect_drift_returns_detection_run(aws_credentials):
    """detect_drift calls DetectStackDrift and returns a DetectionRun."""
    mock_boto = MagicMock()
    mock_boto.detect_stack_drift.return_value = {
        "StackDriftDetectionId": "detection-123"
    }
    mock_boto.describe_stacks.return_value = {
        "Stacks": [{"StackId": "arn:aws:cloudformation:us-east-1:123:stack/my-stack/uuid"}]
    }

    client = CloudFormationClient(region="us-east-1")
    client._client = mock_boto

    run = client.detect_drift("my-stack")

    assert isinstance(run, DetectionRun)
    assert run.detection_id == "detection-123"
    assert run.stack_name == "my-stack"
    assert run.status == DetectionStatus.IN_PROGRESS


def test_poll_detection_in_progress(aws_credentials):
    """poll_detection returns IN_PROGRESS status."""
    mock_boto = MagicMock()
    mock_boto.describe_stack_drift_detection_status.return_value = {
        "StackDriftDetectionId": "det-123",
        "StackId": "arn:aws:cloudformation:us-east-1:123:stack/s/uuid",
        "DetectionStatus": "DETECTION_IN_PROGRESS",
        "Timestamp": datetime(2026, 2, 25, 13, 0, 0),
    }

    client = CloudFormationClient(region="us-east-1")
    client._client = mock_boto

    run = client.poll_detection("det-123", "s")

    assert run.status == DetectionStatus.IN_PROGRESS
    assert run.stack_status is None


def test_poll_detection_complete(aws_credentials):
    """poll_detection returns COMPLETE with drift status."""
    mock_boto = MagicMock()
    mock_boto.describe_stack_drift_detection_status.return_value = {
        "StackDriftDetectionId": "det-123",
        "StackId": "arn:aws:cloudformation:us-east-1:123:stack/s/uuid",
        "DetectionStatus": "DETECTION_COMPLETE",
        "StackDriftStatus": "DRIFTED",
        "DriftedStackResourceCount": 2,
        "Timestamp": datetime(2026, 2, 25, 13, 0, 0),
    }

    client = CloudFormationClient(region="us-east-1")
    client._client = mock_boto

    run = client.poll_detection("det-123", "s")

    assert run.status == DetectionStatus.COMPLETE
    assert run.stack_status == StackStatus.DRIFTED
    assert run.drifted_resource_count == 2


def test_get_resource_drifts(aws_credentials):
    """get_resource_drifts returns list of ResourceDrift from AWS response."""
    mock_boto = MagicMock()
    mock_boto.describe_stack_resource_drifts.return_value = {
        "StackResourceDrifts": [
            {
                "LogicalResourceId": "MyQueue",
                "PhysicalResourceId": "https://sqs.us-east-1.amazonaws.com/123/q",
                "ResourceType": "AWS::SQS::Queue",
                "StackResourceDriftStatus": "MODIFIED",
                "Timestamp": datetime(2026, 2, 25, 13, 30, 0),
                "PropertyDifferences": [
                    {
                        "PropertyPath": "/Properties/DelaySeconds",
                        "ExpectedValue": "0",
                        "ActualValue": "5",
                        "DifferenceType": "NOT_EQUAL",
                    }
                ],
            },
            {
                "LogicalResourceId": "MyBucket",
                "PhysicalResourceId": "my-bucket",
                "ResourceType": "AWS::S3::Bucket",
                "StackResourceDriftStatus": "IN_SYNC",
                "Timestamp": datetime(2026, 2, 25, 13, 30, 0),
                "PropertyDifferences": [],
            },
        ]
    }

    client = CloudFormationClient(region="us-east-1")
    client._client = mock_boto

    drifts = client.get_resource_drifts("my-stack")

    assert len(drifts) == 2
    assert drifts[0].logical_id == "MyQueue"
    assert drifts[0].status == ResourceStatus.MODIFIED
    assert len(drifts[0].property_diffs) == 1
    assert drifts[0].property_diffs[0].expected_value == "0"
    assert drifts[1].logical_id == "MyBucket"
    assert drifts[1].status == ResourceStatus.IN_SYNC
    assert drifts[1].property_diffs == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stackdrift.aws.client'`

**Step 3: Implement CloudFormationClient**

Create `src/stackdrift/aws/client.py`:

```python
"""Thin boto3 wrapper for CloudFormation drift detection API calls."""
import boto3
from datetime import datetime, timezone

from stackdrift.models import (
    DetectionRun,
    DetectionStatus,
    DiffType,
    PropertyDiff,
    ResourceDrift,
    ResourceStatus,
    StackStatus,
)


class CloudFormationClient:
    """Wraps boto3 CloudFormation calls and returns stackdrift dataclasses."""

    def __init__(self, region: str | None = None):
        self._client = boto3.client("cloudformation", **({"region_name": region} if region else {}))

    def list_stacks(
        self,
        stack_names: list[str] | None = None,
        prefix: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """List active CloudFormation stacks, optionally filtered.

        Returns list of dicts with 'stack_name' and 'stack_id' keys.
        """
        paginator = self._client.get_paginator("describe_stacks")
        stacks = []
        for page in paginator.paginate():
            for stack in page["Stacks"]:
                if stack.get("StackStatus", "").endswith("_COMPLETE") or stack.get(
                    "StackStatus", ""
                ) in ("CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"):
                    stacks.append(stack)

        results = []
        for stack in stacks:
            name = stack["StackName"]

            if stack_names and name not in stack_names:
                continue

            if prefix and not name.startswith(prefix):
                continue

            if tags:
                stack_tags = {t["Key"]: t["Value"] for t in stack.get("Tags", [])}
                if not all(stack_tags.get(k) == v for k, v in tags.items()):
                    continue

            results.append({"stack_name": name, "stack_id": stack["StackId"]})

        return results

    def detect_drift(self, stack_name: str) -> DetectionRun:
        """Trigger drift detection for a stack. Returns a DetectionRun for polling."""
        response = self._client.detect_stack_drift(StackName=stack_name)
        detection_id = response["StackDriftDetectionId"]

        desc = self._client.describe_stacks(StackName=stack_name)
        stack_id = desc["Stacks"][0]["StackId"]

        return DetectionRun(
            detection_id=detection_id,
            stack_id=stack_id,
            stack_name=stack_name,
            status=DetectionStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc),
        )

    def poll_detection(self, detection_id: str, stack_name: str) -> DetectionRun:
        """Check status of a drift detection operation."""
        resp = self._client.describe_stack_drift_detection_status(
            StackDriftDetectionId=detection_id
        )

        status = DetectionStatus(resp["DetectionStatus"])
        stack_status = None
        drifted_count = None
        status_reason = None

        if status == DetectionStatus.COMPLETE:
            stack_status = StackStatus(resp["StackDriftStatus"])
            drifted_count = resp.get("DriftedStackResourceCount", 0)
        elif status == DetectionStatus.FAILED:
            status_reason = resp.get("DetectionStatusReason")

        return DetectionRun(
            detection_id=detection_id,
            stack_id=resp["StackId"],
            stack_name=stack_name,
            status=status,
            started_at=resp["Timestamp"],
            stack_status=stack_status,
            drifted_resource_count=drifted_count,
            status_reason=status_reason,
        )

    def get_resource_drifts(self, stack_name: str) -> list[ResourceDrift]:
        """Fetch resource-level drift details for a stack."""
        resp = self._client.describe_stack_resource_drifts(
            StackName=stack_name,
            StackResourceDriftStatusFilters=["MODIFIED", "DELETED", "NOT_CHECKED", "IN_SYNC"],
        )

        results = []
        for resource in resp["StackResourceDrifts"]:
            property_diffs = [
                PropertyDiff(
                    property_path=pd["PropertyPath"],
                    expected_value=pd["ExpectedValue"],
                    actual_value=pd["ActualValue"],
                    diff_type=DiffType(pd["DifferenceType"]),
                )
                for pd in resource.get("PropertyDifferences", [])
            ]

            results.append(
                ResourceDrift(
                    logical_id=resource["LogicalResourceId"],
                    physical_id=resource["PhysicalResourceId"],
                    resource_type=resource["ResourceType"],
                    status=ResourceStatus(resource["StackResourceDriftStatus"]),
                    property_diffs=property_diffs,
                    timestamp=resource["Timestamp"],
                )
            )

        return results
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_client.py -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `pytest -v`
Expected: ALL PASS

**Step 6: Lint**

Run: `ruff check src/ tests/ && ruff format --check src/ tests/`
Expected: No errors

**Step 7: Commit**

```bash
git add src/stackdrift/aws/client.py tests/conftest.py tests/test_client.py
git commit -m "feat: add CloudFormationClient boto3 wrapper"
```

---

### Task 3: Detector — Concurrent Drift Detection

**Files:**
- Create: `src/stackdrift/detector.py`
- Create: `tests/test_detector.py`

**Step 1: Write failing tests for Detector**

Create `tests/test_detector.py`:

```python
"""Tests for the drift detection orchestrator."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, call

import pytest

from stackdrift.detector import Detector
from stackdrift.models import (
    DetectionRun,
    DetectionStatus,
    DiffType,
    PropertyDiff,
    ResourceDrift,
    ResourceStatus,
    StackDriftResult,
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
        started_at=datetime(2026, 2, 25, 13, 0, 0, tzinfo=timezone.utc),
        **kwargs,
    )


def test_detect_single_stack_in_sync(mock_cfn_client):
    """Detect a single stack with no drift."""
    mock_cfn_client.list_stacks.return_value = [
        {"stack_name": "my-stack", "stack_id": "arn:..."}
    ]
    mock_cfn_client.detect_drift.return_value = _make_detection_run("my-stack")
    mock_cfn_client.poll_detection.return_value = _make_detection_run(
        "my-stack",
        status=DetectionStatus.COMPLETE,
        stack_status=StackStatus.IN_SYNC,
        drifted_resource_count=0,
    )
    mock_cfn_client.get_resource_drifts.return_value = []

    detector = Detector(mock_cfn_client, max_concurrent=1, poll_interval=0)
    results = detector.detect()

    assert len(results) == 1
    assert results[0].stack_name == "my-stack"
    assert results[0].stack_status == StackStatus.IN_SYNC
    assert results[0].drifted_resource_count == 0


def test_detect_single_stack_drifted(mock_cfn_client):
    """Detect a single stack with drift."""
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
    results = detector.detect()

    assert len(results) == 1
    assert results[0].stack_status == StackStatus.DRIFTED
    assert results[0].drifted_resource_count == 1
    assert len(results[0].resource_drifts) == 1


def test_detect_multiple_stacks_concurrent(mock_cfn_client):
    """Detect multiple stacks concurrently."""
    mock_cfn_client.list_stacks.return_value = [
        {"stack_name": f"stack-{i}", "stack_id": f"arn:{i}"} for i in range(3)
    ]
    mock_cfn_client.detect_drift.side_effect = [
        _make_detection_run(f"stack-{i}") for i in range(3)
    ]
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
    results = detector.detect()

    assert len(results) == 3
    assert mock_cfn_client.detect_drift.call_count == 3


def test_detect_polls_until_complete(mock_cfn_client):
    """Detector polls until detection completes."""
    mock_cfn_client.list_stacks.return_value = [
        {"stack_name": "slow-stack", "stack_id": "arn:..."}
    ]
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
    results = detector.detect()

    assert len(results) == 1
    assert mock_cfn_client.poll_detection.call_count == 3


def test_detect_failed_stack_excluded(mock_cfn_client):
    """Failed detections are excluded from results."""
    mock_cfn_client.list_stacks.return_value = [
        {"stack_name": "bad-stack", "stack_id": "arn:..."}
    ]
    mock_cfn_client.detect_drift.return_value = _make_detection_run("bad-stack")
    mock_cfn_client.poll_detection.return_value = _make_detection_run(
        "bad-stack",
        status=DetectionStatus.FAILED,
        status_reason="Stack is in UPDATE_IN_PROGRESS state",
    )

    detector = Detector(mock_cfn_client, max_concurrent=1, poll_interval=0)
    results = detector.detect()

    assert len(results) == 0


def test_detect_passes_filters(mock_cfn_client):
    """Detector passes filters through to list_stacks."""
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_detector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stackdrift.detector'`

**Step 3: Implement Detector**

Create `src/stackdrift/detector.py`:

```python
"""Orchestrates concurrent CloudFormation drift detection."""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from stackdrift.aws.client import CloudFormationClient
from stackdrift.models import (
    DetectionRun,
    DetectionStatus,
    StackDriftResult,
)

logger = logging.getLogger(__name__)


class Detector:
    """Detects CloudFormation drift across multiple stacks concurrently."""

    def __init__(
        self,
        client: CloudFormationClient,
        max_concurrent: int = 5,
        poll_interval: float = 5.0,
        max_poll_attempts: int = 60,
    ):
        self._client = client
        self._max_concurrent = max_concurrent
        self._poll_interval = poll_interval
        self._max_poll_attempts = max_poll_attempts

    def detect(
        self,
        stack_names: list[str] | None = None,
        prefix: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> list[StackDriftResult]:
        """Run drift detection on matching stacks and return results."""
        stacks = self._client.list_stacks(
            stack_names=stack_names,
            prefix=prefix,
            tags=tags,
        )

        if not stacks:
            return []

        results: list[StackDriftResult] = []

        with ThreadPoolExecutor(max_workers=self._max_concurrent) as executor:
            futures = {
                executor.submit(self._detect_stack, s["stack_name"]): s
                for s in stacks
            }
            for future in as_completed(futures):
                stack_info = futures[future]
                try:
                    result = future.result()
                    if result is not None:
                        results.append(result)
                except Exception:
                    logger.exception("Failed to detect drift for %s", stack_info["stack_name"])

        return results

    def _detect_stack(self, stack_name: str) -> StackDriftResult | None:
        """Detect drift for a single stack. Returns None if detection fails."""
        run = self._client.detect_drift(stack_name)

        for _ in range(self._max_poll_attempts):
            run = self._client.poll_detection(run.detection_id, stack_name)

            if run.status == DetectionStatus.COMPLETE:
                break
            elif run.status == DetectionStatus.FAILED:
                logger.warning(
                    "Drift detection failed for %s: %s",
                    stack_name,
                    run.status_reason,
                )
                return None

            if self._poll_interval > 0:
                time.sleep(self._poll_interval)
        else:
            logger.warning("Drift detection timed out for %s", stack_name)
            return None

        resource_drifts = self._client.get_resource_drifts(stack_name)

        return StackDriftResult(
            stack_id=run.stack_id,
            stack_name=stack_name,
            stack_status=run.stack_status,
            resource_drifts=resource_drifts,
            detection_id=run.detection_id,
            timestamp=datetime.now(timezone.utc),
            drifted_resource_count=run.drifted_resource_count or 0,
        )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_detector.py -v`
Expected: ALL PASS

**Step 5: Run full test suite and lint**

Run: `pytest -v && ruff check src/ tests/ && ruff format --check src/ tests/`
Expected: ALL PASS, no lint errors

**Step 6: Commit**

```bash
git add src/stackdrift/detector.py tests/test_detector.py
git commit -m "feat: add Detector with concurrent drift detection"
```

---

### Task 4: Analyzer — Severity Classification

**Files:**
- Create: `src/stackdrift/analyzer.py`
- Create: `tests/test_analyzer.py`

**Step 1: Write failing tests for Analyzer**

Create `tests/test_analyzer.py`:

```python
"""Tests for severity classification analyzer."""
from datetime import datetime

from stackdrift.analyzer import Severity, AnalyzedDrift, analyze_results
from stackdrift.models import (
    DiffType,
    PropertyDiff,
    ResourceDrift,
    ResourceStatus,
    StackDriftResult,
    StackStatus,
)


def _make_resource_drift(resource_type, status=ResourceStatus.MODIFIED):
    return ResourceDrift(
        logical_id="Res1",
        physical_id="phys-1",
        resource_type=resource_type,
        status=status,
        property_diffs=[
            PropertyDiff(
                property_path="/Properties/Foo",
                expected_value="a",
                actual_value="b",
                diff_type=DiffType.NOT_EQUAL,
            )
        ] if status == ResourceStatus.MODIFIED else [],
        timestamp=datetime(2026, 2, 25, 13, 30, 0),
    )


def _make_stack_result(resource_drifts):
    drifted = [r for r in resource_drifts if r.status != ResourceStatus.IN_SYNC]
    return StackDriftResult(
        stack_id="arn:aws:cloudformation:us-east-1:123:stack/test/uuid",
        stack_name="test-stack",
        stack_status=StackStatus.DRIFTED if drifted else StackStatus.IN_SYNC,
        resource_drifts=resource_drifts,
        detection_id="det-123",
        timestamp=datetime(2026, 2, 25, 13, 30, 0),
        drifted_resource_count=len(drifted),
    )


def test_security_group_is_critical():
    rd = _make_resource_drift("AWS::EC2::SecurityGroup")
    result = _make_stack_result([rd])
    analyzed = analyze_results([result])
    assert analyzed[0].resource_severities["Res1"] == Severity.CRITICAL


def test_iam_role_is_critical():
    rd = _make_resource_drift("AWS::IAM::Role")
    result = _make_stack_result([rd])
    analyzed = analyze_results([result])
    assert analyzed[0].resource_severities["Res1"] == Severity.CRITICAL


def test_lambda_function_is_high():
    rd = _make_resource_drift("AWS::Lambda::Function")
    result = _make_stack_result([rd])
    analyzed = analyze_results([result])
    assert analyzed[0].resource_severities["Res1"] == Severity.HIGH


def test_sqs_queue_is_medium():
    rd = _make_resource_drift("AWS::SQS::Queue")
    result = _make_stack_result([rd])
    analyzed = analyze_results([result])
    assert analyzed[0].resource_severities["Res1"] == Severity.MEDIUM


def test_unknown_resource_is_low():
    rd = _make_resource_drift("AWS::Some::UnknownResource")
    result = _make_stack_result([rd])
    analyzed = analyze_results([result])
    assert analyzed[0].resource_severities["Res1"] == Severity.LOW


def test_in_sync_resource_has_no_severity():
    rd = _make_resource_drift("AWS::EC2::SecurityGroup", status=ResourceStatus.IN_SYNC)
    result = _make_stack_result([rd])
    analyzed = analyze_results([result])
    assert "Res1" not in analyzed[0].resource_severities


def test_stack_severity_is_max_of_resources():
    rd_critical = ResourceDrift(
        logical_id="SG",
        physical_id="sg-1",
        resource_type="AWS::EC2::SecurityGroup",
        status=ResourceStatus.MODIFIED,
        property_diffs=[PropertyDiff("/P/A", "a", "b", DiffType.NOT_EQUAL)],
        timestamp=datetime(2026, 2, 25, 13, 30, 0),
    )
    rd_low = ResourceDrift(
        logical_id="Alarm",
        physical_id="alarm-1",
        resource_type="AWS::CloudWatch::Alarm",
        status=ResourceStatus.MODIFIED,
        property_diffs=[PropertyDiff("/P/B", "x", "y", DiffType.NOT_EQUAL)],
        timestamp=datetime(2026, 2, 25, 13, 30, 0),
    )
    result = _make_stack_result([rd_critical, rd_low])
    analyzed = analyze_results([result])
    assert analyzed[0].stack_severity == Severity.CRITICAL


def test_empty_results():
    analyzed = analyze_results([])
    assert analyzed == []


def test_in_sync_stack_severity_is_none():
    result = StackDriftResult(
        stack_id="arn:...",
        stack_name="clean-stack",
        stack_status=StackStatus.IN_SYNC,
        resource_drifts=[],
        detection_id="det-1",
        timestamp=datetime(2026, 2, 25, 13, 30, 0),
        drifted_resource_count=0,
    )
    analyzed = analyze_results([result])
    assert analyzed[0].stack_severity is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_analyzer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stackdrift.analyzer'`

**Step 3: Implement Analyzer**

Create `src/stackdrift/analyzer.py`:

```python
"""Severity classification for CloudFormation drift results."""
from dataclasses import dataclass
from enum import IntEnum

from stackdrift.models import ResourceStatus, StackDriftResult


class Severity(IntEnum):
    """Drift severity level. Higher value = more severe."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


SEVERITY_MAP: dict[str, Severity] = {
    # Critical — security boundaries
    "AWS::EC2::SecurityGroup": Severity.CRITICAL,
    "AWS::IAM::Role": Severity.CRITICAL,
    "AWS::IAM::Policy": Severity.CRITICAL,
    "AWS::IAM::ManagedPolicy": Severity.CRITICAL,
    "AWS::IAM::User": Severity.CRITICAL,
    "AWS::IAM::Group": Severity.CRITICAL,
    "AWS::KMS::Key": Severity.CRITICAL,
    "AWS::EC2::NetworkAcl": Severity.CRITICAL,
    "AWS::EC2::NetworkAclEntry": Severity.CRITICAL,
    "AWS::WAFv2::WebACL": Severity.CRITICAL,
    # High — compute and data processing
    "AWS::Lambda::Function": Severity.HIGH,
    "AWS::RDS::DBInstance": Severity.HIGH,
    "AWS::RDS::DBCluster": Severity.HIGH,
    "AWS::ECS::TaskDefinition": Severity.HIGH,
    "AWS::ECS::Service": Severity.HIGH,
    "AWS::EC2::Instance": Severity.HIGH,
    "AWS::ElasticLoadBalancingV2::Listener": Severity.HIGH,
    "AWS::ElasticLoadBalancingV2::TargetGroup": Severity.HIGH,
    # Medium — storage and messaging
    "AWS::SQS::Queue": Severity.MEDIUM,
    "AWS::SNS::Topic": Severity.MEDIUM,
    "AWS::S3::Bucket": Severity.MEDIUM,
    "AWS::DynamoDB::Table": Severity.MEDIUM,
    "AWS::ElastiCache::ReplicationGroup": Severity.MEDIUM,
    # Low is the default for anything not listed
}


@dataclass(frozen=True)
class AnalyzedDrift:
    """A StackDriftResult annotated with severity classifications."""
    result: StackDriftResult
    resource_severities: dict[str, Severity]
    stack_severity: Severity | None


def analyze_results(results: list[StackDriftResult]) -> list[AnalyzedDrift]:
    """Classify each drifted resource by severity."""
    analyzed = []
    for result in results:
        resource_severities: dict[str, Severity] = {}
        for rd in result.resource_drifts:
            if rd.status == ResourceStatus.IN_SYNC:
                continue
            severity = SEVERITY_MAP.get(rd.resource_type, Severity.LOW)
            resource_severities[rd.logical_id] = severity

        stack_severity = max(resource_severities.values()) if resource_severities else None

        analyzed.append(
            AnalyzedDrift(
                result=result,
                resource_severities=resource_severities,
                stack_severity=stack_severity,
            )
        )
    return analyzed
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_analyzer.py -v`
Expected: ALL PASS

**Step 5: Run full test suite and lint**

Run: `pytest -v && ruff check src/ tests/ && ruff format --check src/ tests/`
Expected: ALL PASS, no lint errors

**Step 6: Commit**

```bash
git add src/stackdrift/analyzer.py tests/test_analyzer.py
git commit -m "feat: add severity classification analyzer"
```

---

### Task 5: Formatter — Table, JSON, and Markdown Output

**Files:**
- Create: `src/stackdrift/formatter.py`
- Create: `tests/test_formatter.py`

**Step 1: Write failing tests for formatters**

Create `tests/test_formatter.py`:

```python
"""Tests for output formatters."""
import json
from datetime import datetime

from stackdrift.analyzer import AnalyzedDrift, Severity
from stackdrift.formatter import format_json, format_markdown, format_table
from stackdrift.models import (
    DiffType,
    PropertyDiff,
    ResourceDrift,
    ResourceStatus,
    StackDriftResult,
    StackStatus,
)


def _make_analyzed_drift(drifted=True):
    if drifted:
        resource_drifts = [
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
        ]
        return AnalyzedDrift(
            result=StackDriftResult(
                stack_id="arn:aws:cloudformation:us-east-1:123:stack/my-stack/uuid",
                stack_name="my-stack",
                stack_status=StackStatus.DRIFTED,
                resource_drifts=resource_drifts,
                detection_id="det-123",
                timestamp=datetime(2026, 2, 25, 13, 30, 0),
                drifted_resource_count=1,
            ),
            resource_severities={"MyQueue": Severity.MEDIUM},
            stack_severity=Severity.MEDIUM,
        )
    else:
        return AnalyzedDrift(
            result=StackDriftResult(
                stack_id="arn:aws:cloudformation:us-east-1:123:stack/clean/uuid",
                stack_name="clean-stack",
                stack_status=StackStatus.IN_SYNC,
                resource_drifts=[],
                detection_id="det-456",
                timestamp=datetime(2026, 2, 25, 13, 30, 0),
                drifted_resource_count=0,
            ),
            resource_severities={},
            stack_severity=None,
        )


def test_format_json_structure():
    analyzed = [_make_analyzed_drift(drifted=True)]
    output = format_json(analyzed)
    data = json.loads(output)

    assert len(data["stacks"]) == 1
    stack = data["stacks"][0]
    assert stack["stack_name"] == "my-stack"
    assert stack["status"] == "DRIFTED"
    assert stack["severity"] == "MEDIUM"
    assert len(stack["resources"]) == 1
    res = stack["resources"][0]
    assert res["logical_id"] == "MyQueue"
    assert res["severity"] == "MEDIUM"
    assert len(res["property_diffs"]) == 1


def test_format_json_summary():
    analyzed = [_make_analyzed_drift(drifted=True), _make_analyzed_drift(drifted=False)]
    output = format_json(analyzed)
    data = json.loads(output)

    assert data["summary"]["total_stacks"] == 2
    assert data["summary"]["drifted_stacks"] == 1


def test_format_json_empty():
    output = format_json([])
    data = json.loads(output)
    assert data["stacks"] == []
    assert data["summary"]["total_stacks"] == 0


def test_format_markdown_contains_stack():
    analyzed = [_make_analyzed_drift(drifted=True)]
    output = format_markdown(analyzed)

    assert "my-stack" in output
    assert "DRIFTED" in output
    assert "MyQueue" in output
    assert "MEDIUM" in output
    assert "DelaySeconds" in output


def test_format_markdown_empty():
    output = format_markdown([])
    assert "No drift detected" in output


def test_format_table_returns_string():
    analyzed = [_make_analyzed_drift(drifted=True)]
    output = format_table(analyzed)
    assert isinstance(output, str)
    assert "my-stack" in output


def test_format_table_empty():
    output = format_table([])
    assert "No drift detected" in output
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_formatter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stackdrift.formatter'`

**Step 3: Implement formatters**

Create `src/stackdrift/formatter.py`:

```python
"""Output formatters for drift detection results."""
import json

from rich.console import Console
from rich.text import Text
from rich.tree import Tree

from stackdrift.analyzer import AnalyzedDrift, Severity
from stackdrift.models import ResourceStatus, StackStatus

SEVERITY_COLORS = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "dim",
}


def format_json(analyzed: list[AnalyzedDrift]) -> str:
    """Format results as JSON."""
    drifted_count = sum(
        1 for a in analyzed if a.result.stack_status == StackStatus.DRIFTED
    )

    stacks = []
    for a in analyzed:
        resources = []
        for rd in a.result.resource_drifts:
            if rd.status == ResourceStatus.IN_SYNC:
                continue
            resources.append({
                "logical_id": rd.logical_id,
                "physical_id": rd.physical_id,
                "resource_type": rd.resource_type,
                "status": rd.status.value,
                "severity": a.resource_severities.get(rd.logical_id, Severity.LOW).name,
                "property_diffs": [
                    {
                        "property_path": pd.property_path,
                        "expected_value": pd.expected_value,
                        "actual_value": pd.actual_value,
                    }
                    for pd in rd.property_diffs
                ],
            })

        stacks.append({
            "stack_name": a.result.stack_name,
            "stack_id": a.result.stack_id,
            "status": a.result.stack_status.value,
            "severity": a.stack_severity.name if a.stack_severity else None,
            "drifted_resource_count": a.result.drifted_resource_count,
            "resources": resources,
        })

    return json.dumps(
        {
            "summary": {
                "total_stacks": len(analyzed),
                "drifted_stacks": drifted_count,
            },
            "stacks": stacks,
        },
        indent=2,
    )


def format_markdown(analyzed: list[AnalyzedDrift]) -> str:
    """Format results as Markdown."""
    if not analyzed:
        return "No drift detected."

    drifted = [a for a in analyzed if a.result.stack_status == StackStatus.DRIFTED]

    if not drifted:
        return "No drift detected."

    lines = [
        f"## Drift Report — {len(drifted)}/{len(analyzed)} stacks drifted",
        "",
    ]

    for a in drifted:
        severity_label = f" [{a.stack_severity.name}]" if a.stack_severity else ""
        lines.append(f"### {a.result.stack_name} — DRIFTED{severity_label}")
        lines.append("")
        lines.append("| Resource | Type | Status | Severity | Property | Expected | Actual |")
        lines.append("|----------|------|--------|----------|----------|----------|--------|")

        for rd in a.result.resource_drifts:
            if rd.status == ResourceStatus.IN_SYNC:
                continue
            sev = a.resource_severities.get(rd.logical_id, Severity.LOW).name
            if rd.property_diffs:
                for pd in rd.property_diffs:
                    lines.append(
                        f"| {rd.logical_id} | {rd.resource_type} | {rd.status.value} "
                        f"| {sev} | `{pd.property_path}` "
                        f"| `{pd.expected_value}` | `{pd.actual_value}` |"
                    )
            else:
                lines.append(
                    f"| {rd.logical_id} | {rd.resource_type} | {rd.status.value} "
                    f"| {sev} | — | — | — |"
                )

        lines.append("")

    return "\n".join(lines)


def format_table(analyzed: list[AnalyzedDrift]) -> str:
    """Format results as a Rich tree view, returned as a string."""
    if not analyzed:
        return "No drift detected."

    console = Console(record=True, width=120)
    tree = Tree("[bold]Drift Report[/bold]")

    for a in analyzed:
        status_style = "green" if a.result.stack_status == StackStatus.IN_SYNC else "red"
        severity_label = f" [{a.stack_severity.name}]" if a.stack_severity else ""
        stack_branch = tree.add(
            Text.from_markup(
                f"[{status_style}]{a.result.stack_name}[/{status_style}]"
                f" — {a.result.stack_status.value}{severity_label}"
            )
        )

        for rd in a.result.resource_drifts:
            if rd.status == ResourceStatus.IN_SYNC:
                continue
            sev = a.resource_severities.get(rd.logical_id, Severity.LOW)
            color = SEVERITY_COLORS.get(sev, "dim")
            resource_branch = stack_branch.add(
                Text.from_markup(
                    f"[{color}]{rd.logical_id}[/{color}]"
                    f" ({rd.resource_type}) — {rd.status.value} [{sev.name}]"
                )
            )
            for pd in rd.property_diffs:
                resource_branch.add(
                    Text.from_markup(
                        f"{pd.property_path}: "
                        f"[green]{pd.expected_value}[/green] → "
                        f"[red]{pd.actual_value}[/red]"
                    )
                )

    console.print(tree)
    return console.export_text()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_formatter.py -v`
Expected: ALL PASS

**Step 5: Run full test suite and lint**

Run: `pytest -v && ruff check src/ tests/ && ruff format --check src/ tests/`
Expected: ALL PASS, no lint errors

**Step 6: Commit**

```bash
git add src/stackdrift/formatter.py tests/test_formatter.py
git commit -m "feat: add table, JSON, and markdown formatters"
```

---

### Task 6: Integrations — Slack and GitHub

**Files:**
- Create: `src/stackdrift/integrations/slack.py`
- Create: `src/stackdrift/integrations/github.py`
- Create: `tests/test_integrations.py`

**Step 1: Write failing tests**

Create `tests/test_integrations.py`:

```python
"""Tests for Slack and GitHub integrations."""
from unittest.mock import patch, MagicMock

import pytest

from stackdrift.integrations.slack import post_to_slack
from stackdrift.integrations.github import post_to_github_pr


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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_integrations.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement Slack integration**

Create `src/stackdrift/integrations/slack.py`:

```python
"""Post drift reports to Slack via incoming webhook."""
import requests


def post_to_slack(report: str, webhook_url: str) -> None:
    """Post a drift report to a Slack incoming webhook."""
    response = requests.post(
        webhook_url,
        json={"text": report},
        timeout=30,
    )
    response.raise_for_status()
```

**Step 4: Implement GitHub integration**

Create `src/stackdrift/integrations/github.py`:

```python
"""Post drift reports as GitHub PR comments."""
import requests


def post_to_github_pr(
    body: str,
    repo: str,
    pr_number: int,
    token: str,
) -> None:
    """Post a drift report as a comment on a GitHub pull request."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    response = requests.post(
        url,
        json={"body": body},
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
        timeout=30,
    )
    response.raise_for_status()
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_integrations.py -v`
Expected: ALL PASS

**Step 6: Run full test suite and lint**

Run: `pytest -v && ruff check src/ tests/ && ruff format --check src/ tests/`
Expected: ALL PASS, no lint errors

**Step 7: Commit**

```bash
git add src/stackdrift/integrations/slack.py src/stackdrift/integrations/github.py tests/test_integrations.py
git commit -m "feat: add Slack and GitHub PR integrations"
```

---

### Task 7: CLI Entrypoint

**Files:**
- Create: `src/stackdrift/cli.py`
- Create: `tests/test_cli.py`

**Step 1: Write failing tests for CLI**

Create `tests/test_cli.py`:

```python
"""Tests for the CLI entrypoint."""
from unittest.mock import patch, MagicMock
from datetime import datetime

from click.testing import CliRunner

from stackdrift.cli import main
from stackdrift.models import (
    StackDriftResult,
    StackStatus,
    ResourceDrift,
    ResourceStatus,
    PropertyDiff,
    DiffType,
)


@pytest.fixture
def runner():
    return CliRunner()


def _mock_results(drifted=False):
    if drifted:
        return [
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
    return [
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


import pytest


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_no_drift_exit_0(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_results(drifted=False)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, [])
    assert result.exit_code == 0


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_drift_exit_1(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_results(drifted=True)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, [])
    assert result.exit_code == 1


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_json_format(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_results(drifted=True)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, ["--format", "json"])
    assert result.exit_code == 1
    assert '"stack_name": "my-stack"' in result.output


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_markdown_format(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_results(drifted=True)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, ["--format", "markdown"])
    assert result.exit_code == 1
    assert "my-stack" in result.output
    assert "DRIFTED" in result.output


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_drifted_only(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_results(drifted=False)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, ["--drifted-only"])
    assert result.exit_code == 0


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_passes_stack_filter(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = []
    mock_detector_cls.return_value = mock_detector

    runner.invoke(main, ["--stack", "my-stack", "--stack", "other-stack"])

    mock_detector.detect.assert_called_once()
    call_kwargs = mock_detector.detect.call_args[1]
    assert call_kwargs["stack_names"] == ("my-stack", "other-stack")


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_passes_prefix_filter(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = []
    mock_detector_cls.return_value = mock_detector

    runner.invoke(main, ["--prefix", "prod-"])

    call_kwargs = mock_detector.detect.call_args[1]
    assert call_kwargs["prefix"] == "prod-"


@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_passes_tag_filter(mock_client_cls, mock_detector_cls, runner):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = []
    mock_detector_cls.return_value = mock_detector

    runner.invoke(main, ["--tag", "Environment=prod"])

    call_kwargs = mock_detector.detect.call_args[1]
    assert call_kwargs["tags"] == {"Environment": "prod"}


@patch("stackdrift.cli.post_to_slack")
@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_post_slack(mock_client_cls, mock_detector_cls, mock_slack, runner, monkeypatch):
    monkeypatch.setenv("STACKDRIFT_SLACK_WEBHOOK", "https://hooks.slack.example.com/test")
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_results(drifted=True)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, ["--post-slack"])

    mock_slack.assert_called_once()


@patch("stackdrift.cli.post_to_github_pr")
@patch("stackdrift.cli.Detector")
@patch("stackdrift.cli.CloudFormationClient")
def test_cli_post_github_pr(mock_client_cls, mock_detector_cls, mock_gh, runner, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GITHUB_REPO", "Specter099/stackdrift")
    mock_detector = MagicMock()
    mock_detector.detect.return_value = _mock_results(drifted=True)
    mock_detector_cls.return_value = mock_detector

    result = runner.invoke(main, ["--post-github-pr", "42"])

    mock_gh.assert_called_once()
    call_kwargs = mock_gh.call_args[1]
    assert call_kwargs["pr_number"] == 42
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stackdrift.cli'`

**Step 3: Implement CLI**

Create `src/stackdrift/cli.py`:

```python
"""CLI entrypoint for stackdrift."""
import os
import sys

import click

from stackdrift.analyzer import analyze_results
from stackdrift.aws.client import CloudFormationClient
from stackdrift.detector import Detector
from stackdrift.formatter import format_json, format_markdown, format_table
from stackdrift.integrations.github import post_to_github_pr
from stackdrift.integrations.slack import post_to_slack
from stackdrift.models import StackStatus


@click.command()
@click.option("--stack", multiple=True, help="Specific stack name(s) to check.")
@click.option("--prefix", default=None, help="Filter stacks by name prefix.")
@click.option("--tag", default=None, help="Filter stacks by tag (KEY=VALUE).")
@click.option("--drifted-only", is_flag=True, help="Show only drifted stacks.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "markdown"]),
    default="table",
    help="Output format.",
)
@click.option("--post-slack", is_flag=True, help="Post report to Slack webhook.")
@click.option("--post-github-pr", type=int, default=None, help="Post report as GitHub PR comment.")
@click.option("--max-concurrent", type=int, default=5, help="Max concurrent drift detections.")
@click.option("--region", default=None, help="AWS region.")
def main(stack, prefix, tag, drifted_only, output_format, post_slack, post_github_pr, max_concurrent, region):
    """Detect CloudFormation stack drift."""
    tags = None
    if tag:
        key, _, value = tag.partition("=")
        tags = {key: value}

    client = CloudFormationClient(region=region)
    detector = Detector(client, max_concurrent=max_concurrent)

    results = detector.detect(
        stack_names=stack or None,
        prefix=prefix,
        tags=tags,
    )

    if drifted_only:
        results = [r for r in results if r.stack_status == StackStatus.DRIFTED]

    analyzed = analyze_results(results)

    formatters = {
        "table": format_table,
        "json": format_json,
        "markdown": format_markdown,
    }
    output = formatters[output_format](analyzed)
    click.echo(output)

    if post_slack:
        webhook_url = os.environ.get("STACKDRIFT_SLACK_WEBHOOK")
        if not webhook_url:
            click.echo("Error: STACKDRIFT_SLACK_WEBHOOK env var not set.", err=True)
            sys.exit(2)
        md_output = format_markdown(analyzed)
        post_to_slack(report=md_output, webhook_url=webhook_url)

    if post_github_pr is not None:
        token = os.environ.get("GITHUB_TOKEN")
        repo = os.environ.get("GITHUB_REPO")
        if not token or not repo:
            click.echo("Error: GITHUB_TOKEN and GITHUB_REPO env vars required.", err=True)
            sys.exit(2)
        md_output = format_markdown(analyzed)
        post_to_github_pr(body=md_output, repo=repo, pr_number=post_github_pr, token=token)

    has_drift = any(r.result.stack_status == StackStatus.DRIFTED for r in analyzed)
    sys.exit(1 if has_drift else 0)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: ALL PASS

**Step 5: Run full test suite and lint**

Run: `pytest -v && ruff check src/ tests/ && ruff format --check src/ tests/`
Expected: ALL PASS, no lint errors

**Step 6: Commit**

```bash
git add src/stackdrift/cli.py tests/test_cli.py
git commit -m "feat: add CLI entrypoint with all flags"
```

---

### Task 8: Final Verification

**Files:**
- No new files

**Step 1: Install in editable mode**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Step 2: Run full test suite with coverage**

Run: `pytest --cov=stackdrift --cov-report=term-missing -v`
Expected: ALL PASS, coverage >= 80%

**Step 3: Run linter**

Run: `ruff check src/ tests/ && ruff format --check src/ tests/`
Expected: No errors

**Step 4: Verify CLI help**

Run: `stackdrift --help`
Expected: Shows all options from README

**Step 5: Commit any fixes from verification**

If any fixes needed, commit them.

**Step 6: Update todo.md**

Mark all phases complete in `tasks/todo.md`.

**Step 7: Commit and push**

```bash
git push -u origin feature/build-stackdrift
```
