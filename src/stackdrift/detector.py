"""Orchestrates concurrent CloudFormation drift detection."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from stackdrift.aws.client import CloudFormationClient
from stackdrift.models import (
    DetectionResult,
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
    ) -> DetectionResult:
        """Run drift detection on matching stacks and return results."""
        stacks = self._client.list_stacks(
            stack_names=stack_names,
            prefix=prefix,
            tags=tags,
        )

        if not stacks:
            return DetectionResult(results=[], failed_stacks=[])

        results: list[StackDriftResult] = []
        failed_stacks: list[str] = []

        with ThreadPoolExecutor(max_workers=self._max_concurrent) as executor:
            futures = {executor.submit(self._detect_stack, s["stack_name"]): s for s in stacks}
            for future in as_completed(futures):
                stack_info = futures[future]
                try:
                    result = future.result()
                    if result is not None:
                        results.append(result)
                    else:
                        failed_stacks.append(stack_info["stack_name"])
                except Exception:
                    logger.exception("Failed to detect drift for %s", stack_info["stack_name"])
                    failed_stacks.append(stack_info["stack_name"])

        return DetectionResult(results=results, failed_stacks=failed_stacks)

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
            timestamp=datetime.now(UTC),
            drifted_resource_count=run.drifted_resource_count or 0,
        )
