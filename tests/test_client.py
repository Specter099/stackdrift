"""Tests for CloudFormationClient."""

from datetime import datetime
from unittest.mock import MagicMock

import boto3
from moto import mock_aws

from stackdrift.aws.client import CloudFormationClient
from stackdrift.models import (
    DetectionRun,
    DetectionStatus,
    ResourceStatus,
    StackStatus,
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
    mock_boto.detect_stack_drift.return_value = {"StackDriftDetectionId": "detection-123"}
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
