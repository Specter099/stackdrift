"""Thin boto3 wrapper for CloudFormation drift detection API calls."""

from datetime import UTC, datetime

import boto3

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
                status = stack.get("StackStatus", "")
                if status in (
                    "CREATE_COMPLETE",
                    "UPDATE_COMPLETE",
                    "UPDATE_ROLLBACK_COMPLETE",
                    "IMPORT_COMPLETE",
                    "IMPORT_ROLLBACK_COMPLETE",
                ):
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
            started_at=datetime.now(UTC),
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
        results = []
        next_token = None

        while True:
            kwargs: dict = {
                "StackName": stack_name,
                "StackResourceDriftStatusFilters": [
                    "MODIFIED",
                    "DELETED",
                    "NOT_CHECKED",
                    "IN_SYNC",
                ],
            }
            if next_token:
                kwargs["NextToken"] = next_token

            resp = self._client.describe_stack_resource_drifts(**kwargs)

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

            next_token = resp.get("NextToken")
            if not next_token:
                break

        return results
