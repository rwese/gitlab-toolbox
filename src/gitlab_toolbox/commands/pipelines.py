"""Pipelines command implementation."""

import sys

import click
from rich.console import Console

from ..api.client import GitLabClient
from ..api.pipelines import PipelinesAPI
from ..formatters.format_decorator import format_decorator

console = Console(file=sys.stderr)


@click.group(name="pipelines")
def pipelines_cli():
    """Manage GitLab CI/CD pipelines."""
    pass


@pipelines_cli.command(name="list")
@format_decorator(
    formats=["table", "json", "csv"],
    interactive_default="table",
    script_default="csv",
    entity_type="pipelines",
)
@click.option(
    "--status",
    type=click.Choice(
        ["running", "pending", "success", "failed", "canceled", "skipped"],
        case_sensitive=False,
    ),
    help="Filter by pipeline status",
)
@click.option("--limit", type=int, help="Maximum number of pipelines to fetch")
def list_pipelines(format_handler, status, limit):
    project = GitLabClient._repo_path
    if not project:
        raise click.ClickException(
            "--project is required (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)"
        )
    """List pipelines for a project."""
    pipelines = PipelinesAPI.get_pipelines(project, status=status, limit=limit)

    if not pipelines:
        console.print("[yellow]No pipelines found.[/yellow]")
        return

    format_handler(pipelines)

    console.print(f"\n[dim]Total pipelines: {len(pipelines)}[/dim]")


@pipelines_cli.command(name="show")
@click.argument("pipeline_id", type=int)
def show_pipeline(pipeline_id):
    project = GitLabClient._repo_path
    if not project:
        raise click.ClickException(
            "--project is required (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)"
        )
    """Show details of a specific pipeline."""
    pipeline = PipelinesAPI.get_pipeline(project, pipeline_id)

    if not pipeline:
        console.print(f"[red]Pipeline #{pipeline_id} not found in {project}.[/red]")
        return

    console.print(f"[bold cyan]Pipeline #{pipeline.id}[/bold cyan]")
    console.print(f"[bold]Status:[/bold] {pipeline.status}")
    console.print(f"[bold]Ref:[/bold] {pipeline.ref}")
    console.print(f"[bold]SHA:[/bold] {pipeline.sha}")
    console.print(f"[bold]Duration:[/bold] {pipeline.duration}s" if pipeline.duration else "N/A")
    console.print(f"[bold]URL:[/bold] {pipeline.web_url}")


@pipelines_cli.command(name="jobs")
@format_decorator(
    formats=["table", "json", "csv"],
    interactive_default="table",
    script_default="csv",
    entity_type="jobs",
)
@click.argument("pipeline_id", type=int)
def list_pipeline_jobs(format_handler, pipeline_id):
    project = GitLabClient._repo_path
    if not project:
        raise click.ClickException(
            "--project is required (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)"
        )
    """List jobs for a specific pipeline."""
    jobs = PipelinesAPI.get_pipeline_jobs(project, pipeline_id)

    if not jobs:
        console.print("[yellow]No jobs found.[/yellow]")
        return

    format_handler(jobs)

    console.print(f"\n[dim]Total jobs: {len(jobs)}[/dim]")
