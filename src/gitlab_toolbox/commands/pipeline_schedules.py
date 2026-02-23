"""Pipeline schedules command implementation."""

import sys

import click
from rich.console import Console

from ..api.client import GitLabClient
from ..api.pipeline_schedules import PipelineSchedulesAPI
from ..formatters import DisplayFormatter
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
def list_pipeline_schedules(format_handler, state, limit, include_last_pipeline):
    project = GitLabClient._repo_path
    if not project:
        raise click.ClickException(
            "--project is required (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)"
        )
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
@click.argument("schedule_id", type=int)
def show_pipeline_schedule(schedule_id):
    project = GitLabClient._repo_path
    if not project:
        raise click.ClickException(
            "--project is required (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)"
        )
    """Show details of a specific pipeline schedule."""
    schedule = PipelineSchedulesAPI.get_schedule(project, schedule_id)

    if not schedule:
        console.print(f"[red]Pipeline schedule #{schedule_id} not found in {project}.[/red]")
        return

    DisplayFormatter.display_pipeline_schedule_details(schedule)


@pipeline_schedules_cli.command(name="pipelines")
@click.argument("schedule_id", type=int)
@click.option("--limit", type=int, help="Maximum number of pipelines to fetch")
def list_schedule_pipelines(schedule_id, limit):
    project = GitLabClient._repo_path
    if not project:
        raise click.ClickException(
            "--project is required (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)"
        )
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
@click.argument("schedule_id", type=int)
@click.option(
    "--format",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    help="Output format",
)
def trigger_pipeline_schedule(schedule_id, format):
    project = GitLabClient._repo_path
    if not project:
        raise click.ClickException(
            "--project is required (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)"
        )
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
        console.print("ID,Status,Ref,SHA,Created At")
        console.print(
            f"{pipeline.id},{pipeline.status},{pipeline.ref},{pipeline.sha},{pipeline.created_at}"
        )
    else:  # table format
        DisplayFormatter.display_pipeline_details(pipeline)


@pipeline_schedules_cli.command(name="create")
@click.option(
    "--project",
    help="Project path (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)",
)
@click.option("--description", help="Schedule description (overrides JSON)")
@click.option("--ref", help="Git ref (branch/tag) (overrides JSON)")
@click.option("--cron", help="Cron expression (overrides JSON)")
@click.option("--cron-timezone", help="Cron timezone (overrides JSON)")
@click.option("--active/--inactive", default=None, help="Schedule active state (overrides JSON)")
def create_pipeline_schedule(project, description, ref, cron, cron_timezone, active):
    """Create a new pipeline schedule from JSON via stdin.

    Example usage:
        cat schedule.json | gitlab-toolbox pipeline-schedules create --project group/project

    CLI flags override JSON values (highest priority):
        cat schedule.json | gitlab-toolbox pipeline-schedules create --project group/project --description "New desc" --cron "0 2 * * *"

    The JSON should contain fields like:
        {
            "description": "Schedule description",
            "ref": "main",
            "cron": "0 2 * * *",
            "cron_timezone": "UTC",
            "active": true,
            "variables": [
                {"key": "VAR_NAME", "value": "value", "variable_type": "env_var", "raw": false}
            ]
        }
    """
    import json

    if project:
        GitLabClient.set_repo_path(project)
    else:
        project = GitLabClient._repo_path

    if not project:
        raise click.ClickException(
            "--project is required (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)"
        )

    try:
        schedule_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON: {e}")
    except Exception as e:
        raise click.ClickException(f"Error reading stdin: {e}")

    if not isinstance(schedule_data, dict):
        raise click.ClickException("JSON must be an object")

    if description is not None:
        schedule_data["description"] = description
    if ref is not None:
        schedule_data["ref"] = ref
    if cron is not None:
        schedule_data["cron"] = cron
    if cron_timezone is not None:
        schedule_data["cron_timezone"] = cron_timezone
    if active is not None:
        schedule_data["active"] = active

    schedule = PipelineSchedulesAPI.create_schedule(project, schedule_data)

    if schedule:
        DisplayFormatter.display_pipeline_schedule_details(schedule)
    else:
        sys.exit(1)


@pipeline_schedules_cli.command(name="update")
@click.argument("schedule_id", type=int)
@click.option(
    "--project",
    help="Project path (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)",
)
@click.option("--description", help="Schedule description (overrides JSON)")
@click.option("--ref", help="Git ref (branch/tag) (overrides JSON)")
@click.option("--cron", help="Cron expression (overrides JSON)")
@click.option("--cron-timezone", help="Cron timezone (overrides JSON)")
@click.option("--active/--inactive", default=None, help="Schedule active state (overrides JSON)")
def update_pipeline_schedule(schedule_id, project, description, ref, cron, cron_timezone, active):
    """Update an existing pipeline schedule from JSON via stdin.

    Example usage:
        cat schedule.json | gitlab-toolbox pipeline-schedules update 123 --project group/project

    CLI flags override JSON values (highest priority):
        cat schedule.json | gitlab-toolbox pipeline-schedules update 123 --project group/project --description "New desc" --cron "0 2 * * *"

    The JSON should contain fields to update:
        {
            "description": "New description",
            "ref": "main",
            "cron": "0 2 * * *",
            "cron_timezone": "UTC",
            "active": true
        }
    """
    import json

    if project:
        GitLabClient.set_repo_path(project)
    else:
        project = GitLabClient._repo_path

    if not project:
        raise click.ClickException(
            "--project is required (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)"
        )

    try:
        schedule_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON: {e}")
    except Exception as e:
        raise click.ClickException(f"Error reading stdin: {e}")

    if not isinstance(schedule_data, dict):
        raise click.ClickException("JSON must be an object")

    if description is not None:
        schedule_data["description"] = description
    if ref is not None:
        schedule_data["ref"] = ref
    if cron is not None:
        schedule_data["cron"] = cron
    if cron_timezone is not None:
        schedule_data["cron_timezone"] = cron_timezone
    if active is not None:
        schedule_data["active"] = active

    schedule = PipelineSchedulesAPI.update_schedule(project, schedule_id, schedule_data)

    if schedule:
        DisplayFormatter.display_pipeline_schedule_details(schedule)
    else:
        sys.exit(1)
