"""Pipelines command implementation."""

import sys

import click
from rich.console import Console

from ..api.pipelines import PipelinesAPI
from ..formatters import DisplayFormatter, JSONFormatter, CSVFormatter
from ..formatters.format_decorator import format_decorator

console = Console(file=sys.stderr)


# Format handlers for pipelines
def _format_pipelines_json(pipelines, **kwargs):
    """Format pipelines as JSON."""
    print(JSONFormatter.format_pipelines(pipelines))


def _format_pipelines_csv(pipelines, **kwargs):
    """Format pipelines as CSV."""
    print(CSVFormatter.format_pipelines(pipelines))


def _format_pipelines_table(pipelines, **kwargs):
    """Format pipelines as table."""
    DisplayFormatter.display_pipelines_table(pipelines)


PIPELINES_FORMAT_HANDLERS = {
    "json": _format_pipelines_json,
    "csv": _format_pipelines_csv,
    "table": _format_pipelines_table,
}


# Format handlers for pipeline jobs
def _format_jobs_json(jobs, **kwargs):
    """Format jobs as JSON."""
    print(JSONFormatter.format_jobs(jobs))


def _format_jobs_csv(jobs, **kwargs):
    """Format jobs as CSV."""
    print(CSVFormatter.format_jobs(jobs))


def _format_jobs_table(jobs, **kwargs):
    """Format jobs as table."""
    DisplayFormatter.display_pipeline_jobs(jobs)


PIPELINE_JOBS_FORMAT_HANDLERS = {
    "json": _format_jobs_json,
    "csv": _format_jobs_csv,
    "table": _format_jobs_table,
}


@click.group(name="pipelines")
def pipelines_cli():
    """Manage GitLab CI/CD pipelines."""
    pass


@pipelines_cli.command(name="list")
@format_decorator(
    formats=["table", "json", "csv"],
    interactive_default="table",
    script_default="csv",
    format_handlers=PIPELINES_FORMAT_HANDLERS,
)
@click.option("--project", required=True, help="Project path")
@click.option(
    "--status",
    type=click.Choice(
        ["running", "pending", "success", "failed", "canceled", "skipped"],
        case_sensitive=False,
    ),
    help="Filter by pipeline status",
)
@click.option("--limit", type=int, help="Maximum number of pipelines to fetch")
def list_pipelines(format_handler, project, status, limit):
    """List pipelines for a project."""
    pipelines = PipelinesAPI.get_pipelines(project, status=status, limit=limit)

    if not pipelines:
        console.print("[yellow]No pipelines found.[/yellow]")
        return

    format_handler(pipelines)

    console.print(f"\n[dim]Total pipelines: {len(pipelines)}[/dim]")


@pipelines_cli.command(name="show")
@click.option("--project", required=True, help="Project path")
@click.argument("pipeline_id", type=int)
def show_pipeline(project, pipeline_id):
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
    format_handlers=PIPELINE_JOBS_FORMAT_HANDLERS,
)
@click.option("--project", required=True, help="Project path")
@click.argument("pipeline_id", type=int)
def list_pipeline_jobs(format_handler, project, pipeline_id):
    """List jobs for a specific pipeline."""
    jobs = PipelinesAPI.get_pipeline_jobs(project, pipeline_id)

    if not jobs:
        console.print("[yellow]No jobs found.[/yellow]")
        return

    format_handler(jobs)

    console.print(f"\n[dim]Total jobs: {len(jobs)}[/dim]")
