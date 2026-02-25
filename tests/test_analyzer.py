"""Tests for severity classification analyzer."""

from datetime import datetime

from stackdrift.analyzer import Severity, analyze_results
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
        ]
        if status == ResourceStatus.MODIFIED
        else [],
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
