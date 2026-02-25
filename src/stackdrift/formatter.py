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
    drifted_count = sum(1 for a in analyzed if a.result.stack_status == StackStatus.DRIFTED)

    stacks = []
    for a in analyzed:
        resources = []
        for rd in a.result.resource_drifts:
            if rd.status == ResourceStatus.IN_SYNC:
                continue
            resources.append(
                {
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
                }
            )

        stacks.append(
            {
                "stack_name": a.result.stack_name,
                "stack_id": a.result.stack_id,
                "status": a.result.stack_status.value,
                "severity": a.stack_severity.name if a.stack_severity else None,
                "drifted_resource_count": a.result.drifted_resource_count,
                "resources": resources,
            }
        )

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
