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
