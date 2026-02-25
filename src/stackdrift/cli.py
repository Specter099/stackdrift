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
def main(
    stack,
    prefix,
    tag,
    drifted_only,
    output_format,
    post_slack,
    post_github_pr,
    max_concurrent,
    region,
):
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
