"""Pipeline schedules command implementation."""

import sys

import click
from rich.console import Console

from ..api.pipeline_schedules import PipelineSchedulesAPI
from ..formatters.format_decorator import format_decorator

console = Console(file=sys.stderr)


@click.group(name="pipeline-schedules")
def pipeline_schedules_cli():
    """Manage GitLab CI/CD pipeline schedules."""
    pass


@pipeline_schedules_cli.command(name="list")
@format_decorator(
    formats=["table", "json", "csv"],
    interactive_default="table",
    script_default="csv",
    entity_type="pipeline_schedules",
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


@pipeline_schedules_cli.command(name="trigger")
@click.option("--project", required=True, help="Project path")
@click.argument("schedule_id", type=int)
@click.option(
    "--format",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    help="Output format",
)
def trigger_pipeline_schedule(project, schedule_id, format):
    """Trigger a pipeline schedule to run immediately."""
    pipeline_data = PipelineSchedulesAPI.trigger_schedule(project, schedule_id)

    if not pipeline_data:
        sys.exit(1)

    # Display the created pipeline information
    from ..formatters import DisplayFormatter
    from ..api.pipelines import PipelinesAPI

    # Parse the pipeline data
    pipeline = PipelinesAPI._parse_pipeline(pipeline_data)

    if format == "json":
        import json

        console.print(json.dumps(pipeline_data, indent=2))
    elif format == "csv":
        # For CSV, show basic pipeline info
        console.print(f"ID,Status,Ref,SHA,Created At")
        console.print(
            f"{pipeline.id},{pipeline.status},{pipeline.ref},{pipeline.sha},{pipeline.created_at}"
        )
    else:  # table format
        DisplayFormatter.display_pipeline_details(pipeline)
