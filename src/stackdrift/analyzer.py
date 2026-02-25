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
