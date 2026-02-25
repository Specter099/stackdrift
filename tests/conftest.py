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
