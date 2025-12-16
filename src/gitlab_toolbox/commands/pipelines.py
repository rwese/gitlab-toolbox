"""Pipelines command implementation."""

import sys

import click
from rich.console import Console

from ..api.pipelines import PipelinesAPI
from ..formatters import DisplayFormatter

console = Console(file=sys.stderr)


@click.group(name="pipelines")
def pipelines_cli():
    """Manage GitLab CI/CD pipelines."""
    pass


@pipelines_cli.command(name="list")
@click.argument("project_path")
@click.option(
    "--status",
    type=click.Choice(
        ["running", "pending", "success", "failed", "canceled", "skipped"],
        case_sensitive=False,
    ),
    help="Filter by pipeline status",
)
@click.option("--limit", type=int, help="Maximum number of pipelines to fetch")
def list_pipelines(project_path, status, limit):
    """List pipelines for a project."""
    pipelines = PipelinesAPI.get_pipelines(project_path, status=status, limit=limit)

    if not pipelines:
        console.print("[yellow]No pipelines found.[/yellow]")
        return

    DisplayFormatter.display_pipelines_table(pipelines)
    console.print(f"\n[dim]Total pipelines: {len(pipelines)}[/dim]")


@pipelines_cli.command(name="show")
@click.argument("project_path")
@click.argument("pipeline_id", type=int)
def show_pipeline(project_path, pipeline_id):
    """Show details of a specific pipeline."""
    pipeline = PipelinesAPI.get_pipeline(project_path, pipeline_id)

    if not pipeline:
        console.print(f"[red]Pipeline #{pipeline_id} not found in {project_path}.[/red]")
        return

    console.print(f"[bold cyan]Pipeline #{pipeline.id}[/bold cyan]")
    console.print(f"[bold]Status:[/bold] {pipeline.status}")
    console.print(f"[bold]Ref:[/bold] {pipeline.ref}")
    console.print(f"[bold]SHA:[/bold] {pipeline.sha}")
    console.print(f"[bold]Duration:[/bold] {pipeline.duration}s" if pipeline.duration else "N/A")
    console.print(f"[bold]URL:[/bold] {pipeline.web_url}")


@pipelines_cli.command(name="jobs")
@click.argument("project_path")
@click.argument("pipeline_id", type=int)
def list_pipeline_jobs(project_path, pipeline_id):
    """List jobs for a specific pipeline."""
    jobs = PipelinesAPI.get_pipeline_jobs(project_path, pipeline_id)

    if not jobs:
        console.print("[yellow]No jobs found.[/yellow]")
        return

    DisplayFormatter.display_pipeline_jobs(jobs)
    console.print(f"\n[dim]Total jobs: {len(jobs)}[/dim]")
