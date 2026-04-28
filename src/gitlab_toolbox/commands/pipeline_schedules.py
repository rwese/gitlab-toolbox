"""Pipeline schedules command implementation."""

import json
import sys
from pathlib import Path

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
@click.option(
    "--name",
    "name_filter",
    help="Filter schedules by description (case-insensitive substring match)",
)
@click.option(
    "--sort",
    type=click.Choice(["description", "id", "next_run"]),
    default="description",
    help="Sort schedules by field (default: description)",
)
@click.option("--limit", type=int, help="Maximum number of schedules to fetch")
@click.option(
    "--include-last-pipeline",
    is_flag=True,
    help="Fetch last pipeline information for each schedule (slower)",
)
def list_pipeline_schedules(format_handler, state, name_filter, sort, limit, include_last_pipeline):
    project = GitLabClient._repo_path
    if not project:
        raise click.ClickException(
            "--project is required (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)"
        )
    """List pipeline schedules for a project."""
    schedules = PipelineSchedulesAPI.get_schedules(
        project, scope=state, limit=limit, include_last_pipeline=include_last_pipeline
    )

    # Filter by name/description if specified
    if name_filter:
        name_lower = name_filter.lower()
        schedules = [s for s in schedules if s.description and name_lower in s.description.lower()]

    if not schedules:
        console.print("[yellow]No pipeline schedules found.[/yellow]")
        return

    # Sort schedules by specified field
    if sort == "id":
        schedules.sort(key=lambda s: s.id)
    elif sort == "next_run":
        schedules.sort(key=lambda s: s.next_run_at or "")
    else:  # description (default)
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

    from ..formatters import DisplayFormatter
    from ..api.pipelines import PipelinesAPI

    pipeline = PipelinesAPI._parse_pipeline(pipeline_data)

    if format == "json":
        console.print(json.dumps(pipeline_data, indent=2))
    elif format == "csv":
        console.print("ID,Status,Ref,SHA,Created At")
        console.print(
            f"{pipeline.id},{pipeline.status},{pipeline.ref},{pipeline.sha},{pipeline.created_at}"
        )
    else:
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
    """
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
    """
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


@pipeline_schedules_cli.command(name="export")
@click.option(
    "--project",
    help="Project path (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)",
)
@click.option(
    "--name",
    "name_filter",
    help="Filter schedules by description (case-insensitive substring match)",
)
@click.option(
    "--state",
    type=click.Choice(["active", "inactive"], case_sensitive=False),
    help="Filter by schedule state",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    help="Output file path (default: stdout)",
)
@click.option(
    "--include-variables/--no-include-variables",
    default=True,
    help="Include schedule variables in export (default: true)",
)
def export_pipeline_schedules(project, name_filter, state, output, include_variables):
    """Export pipeline schedules to JSON.

    Example usage:
        gitlab-toolbox pipeline-schedules export --project group/project
        gitlab-toolbox pipeline-schedules export --project group/project --name "daily"
        gitlab-toolbox pipeline-schedules export --project group/project -o schedules.json
        gitlab-toolbox pipeline-schedules export --project group/project --state active
    """
    if project:
        GitLabClient.set_repo_path(project)
    else:
        project = GitLabClient._repo_path

    if not project:
        raise click.ClickException(
            "--project is required (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)"
        )

    with console.status("[bold green]Fetching pipeline schedules..."):
        schedules = PipelineSchedulesAPI.get_schedules(
            project, scope=state, limit=None, include_variables=include_variables
        )

    if name_filter:
        name_lower = name_filter.lower()
        schedules = [s for s in schedules if s.description and name_lower in s.description.lower()]

    if not schedules:
        console.print("[yellow]No pipeline schedules found matching the criteria.[/yellow]")
        return

    export_data = _schedules_to_export_format(schedules, include_variables=include_variables)
    json_output = json.dumps(export_data, indent=2)

    if output:
        output_path = Path(output)
        output_path.write_text(json_output)
        console.print(f"[green]✓ Exported {len(schedules)} schedule(s) to {output}[/green]")
    else:
        print(json_output)
        console.print(f"[dim]Exported {len(schedules)} schedule(s)[/dim]", file=sys.stderr)


@pipeline_schedules_cli.command(name="import")
@click.option(
    "--project",
    help="Project path (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)",
)
@click.option(
    "-i",
    "--input",
    type=click.Path(exists=True),
    help="Input file path (default: stdin)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be created without actually creating schedules",
)
@click.option(
    "--skip-existing/--no-skip-existing",
    default=True,
    help="Skip schedules that already exist by description (default: true)",
)
def import_pipeline_schedules(project, input, dry_run, skip_existing):
    """Import pipeline schedules from JSON.

    Example usage:
        gitlab-toolbox pipeline-schedules import --project group/project < schedules.json
        gitlab-toolbox pipeline-schedules import --project group/project -i schedules.json
        gitlab-toolbox pipeline-schedules import --project group/project -i schedules.json --dry-run
    """
    if project:
        GitLabClient.set_repo_path(project)
    else:
        project = GitLabClient._repo_path

    if not project:
        raise click.ClickException(
            "--project is required (set via --project, GITLAB_TOOLBOX_PROJECT, or run from a git repository with GitLab remote)"
        )

    try:
        if input:
            schedules_data = json.loads(Path(input).read_text())
        else:
            schedules_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON: {e}")
    except Exception as e:
        raise click.ClickException(f"Error reading input: {e}")

    if not isinstance(schedules_data, list):
        raise click.ClickException("JSON must be an array of schedule objects")

    if not schedules_data:
        console.print("[yellow]No schedules found in input.[/yellow]")
        return

    existing_descriptions = set()
    if skip_existing:
        existing = PipelineSchedulesAPI.get_schedules(project, scope=None, limit=None)
        existing_descriptions = {s.description for s in existing if s.description}

    valid_schedules = []
    for schedule_data in schedules_data:
        if not isinstance(schedule_data, dict):
            console.print("[yellow]⚠ Skipping invalid schedule (not an object)[/yellow]")
            continue

        description = schedule_data.get("description", "")

        if skip_existing and description in existing_descriptions:
            console.print(f"[dim]⏭ Skipping '{description}' (already exists)[/dim]")
            continue

        if not schedule_data.get("ref"):
            console.print(f"[yellow]⚠ Skipping '{description}' (missing 'ref' field)[/yellow]")
            continue

        if not schedule_data.get("cron"):
            console.print(f"[yellow]⚠ Skipping '{description}' (missing 'cron' field)[/yellow]")
            continue

        valid_schedules.append(schedule_data)

    if not valid_schedules:
        console.print("[yellow]No valid schedules to import.[/yellow]")
        return

    created_count = 0
    skipped_count = 0

    for schedule_data in valid_schedules:
        if dry_run:
            console.print(
                f"[cyan]→ Would create: {schedule_data.get('description')} "
                f"(ref={schedule_data.get('ref')}, cron={schedule_data.get('cron')})[/cyan]"
            )
            created_count += 1
        else:
            schedule = PipelineSchedulesAPI.create_schedule(project, schedule_data)
            if schedule:
                console.print(f"[green]✓ Created: {schedule.description}[/green]")
                created_count += 1
            else:
                console.print(f"[red]✗ Failed to create: {schedule_data.get('description')}[/red]")
                skipped_count += 1

    if dry_run:
        console.print(
            f"\n[cyan]Dry run complete: {created_count} schedule(s) would be created[/cyan]"
        )
    else:
        console.print(
            f"\n[green]✓ Import complete: {created_count} created, {skipped_count} skipped[/green]"
        )


def _schedules_to_export_format(schedules, include_variables=True):
    """Convert PipelineSchedule objects to exportable format."""
    export_data = []

    for schedule in schedules:
        schedule_dict = {
            "description": schedule.description,
            "ref": schedule.ref,
            "cron": schedule.cron,
            "cron_timezone": schedule.cron_timezone,
            "active": schedule.active,
        }

        if include_variables and schedule.variables:
            schedule_dict["variables"] = [
                {
                    "key": var.key,
                    "value": var.value,
                    "variable_type": var.variable_type,
                    "raw": var.raw,
                }
                for var in schedule.variables
            ]

        export_data.append(schedule_dict)

    return export_data
