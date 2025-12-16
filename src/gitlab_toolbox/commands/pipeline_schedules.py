"""Pipeline schedules command implementation."""

import sys

import click
from rich.console import Console

from ..api.pipeline_schedules import PipelineSchedulesAPI
from ..formatters import DisplayFormatter, JSONFormatter, CSVFormatter
from ..formatters.format_decorator import format_decorator

console = Console(file=sys.stderr)


# Format handlers for pipeline schedules
def _format_pipeline_schedules_json(schedules, **kwargs):
    """Format pipeline schedules as JSON."""
    print(JSONFormatter.format_pipeline_schedules(schedules))


def _format_pipeline_schedules_csv(schedules, **kwargs):
    """Format pipeline schedules as CSV."""
    print(CSVFormatter.format_pipeline_schedules(schedules))


def _format_pipeline_schedules_table(schedules, **kwargs):
    """Format pipeline schedules as table."""
    DisplayFormatter.display_pipeline_schedules_table(schedules)


PIPELINE_SCHEDULES_FORMAT_HANDLERS = {
    "json": _format_pipeline_schedules_json,
    "csv": _format_pipeline_schedules_csv,
    "table": _format_pipeline_schedules_table,
}


@click.group(name="pipeline-schedules")
def pipeline_schedules_cli():
    """Manage GitLab CI/CD pipeline schedules."""
    pass


@pipeline_schedules_cli.command(name="list")
@format_decorator(
    formats=["table", "json", "csv"],
    interactive_default="table",
    script_default="csv",
    format_handlers=PIPELINE_SCHEDULES_FORMAT_HANDLERS,
)
@click.option("--project", required=True, help="Project path")
@click.option(
    "--state",
    type=click.Choice(["active", "inactive"], case_sensitive=False),
    help="Filter by schedule state",
)
@click.option("--limit", type=int, help="Maximum number of schedules to fetch")
@click.option(
    "--include-last-pipeline",
    is_flag=True,
    help="Fetch last pipeline information for each schedule (slower)",
)
def list_pipeline_schedules(format_handler, project, state, limit, include_last_pipeline):
    """List pipeline schedules for a project."""
    schedules = PipelineSchedulesAPI.get_schedules(
        project, scope=state, limit=limit, include_last_pipeline=include_last_pipeline
    )

    if not schedules:
        console.print("[yellow]No pipeline schedules found.[/yellow]")
        return

    # Sort schedules by description (case-insensitive)
    schedules.sort(key=lambda s: s.description.lower() if s.description else "")

    format_handler(schedules)
    console.print(f"\n[dim]Total schedules: {len(schedules)}[/dim]")


@pipeline_schedules_cli.command(name="show")
@click.option("--project", required=True, help="Project path")
@click.argument("schedule_id", type=int)
def show_pipeline_schedule(project, schedule_id):
    """Show details of a specific pipeline schedule."""
    schedule = PipelineSchedulesAPI.get_schedule(project, schedule_id)

    if not schedule:
        console.print(f"[red]Pipeline schedule #{schedule_id} not found in {project}.[/red]")
        return

    DisplayFormatter.display_pipeline_schedule_details(schedule)


@pipeline_schedules_cli.command(name="pipelines")
@click.option("--project", required=True, help="Project path")
@click.argument("schedule_id", type=int)
@click.option("--limit", type=int, help="Maximum number of pipelines to fetch")
def list_schedule_pipelines(project, schedule_id, limit):
    """List pipelines triggered by a specific schedule."""
    pipelines = PipelineSchedulesAPI.get_schedule_pipelines(project, schedule_id, limit)

    if not pipelines:
        console.print(f"[yellow]No pipelines found for schedule #{schedule_id}.[/yellow]")
        return

    # Use the existing pipeline display formatter
    from ..formatters import DisplayFormatter

    DisplayFormatter.display_pipelines_table(pipelines)
    console.print(f"\n[dim]Total pipelines: {len(pipelines)}[/dim]")
