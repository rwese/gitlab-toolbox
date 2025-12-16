"""Merge Requests command implementation."""

import sys

import click
from rich.console import Console

from ..api.merge_requests import MergeRequestsAPI
from ..api.pipelines import PipelinesAPI
from ..api.projects import ProjectsAPI
from ..formatters.format_decorator import format_decorator

console = Console(file=sys.stderr)


@click.group(name="mergerequests")
def mergerequests_cli():
    """Manage GitLab merge requests."""
    pass


@mergerequests_cli.command(name="list")
@format_decorator(
    formats=["table", "json", "csv"],
    interactive_default="table",
    script_default="csv",
    entity_type="merge_requests",
)
@click.option("--project", help="Filter by project path")
@click.option(
    "--state",
    type=click.Choice(["opened", "merged", "closed", "all"], case_sensitive=False),
    default="opened",
    help="Filter by MR state",
)
@click.option("--search", help="Search merge requests by title or description")
@click.option("--author", help="Filter by author's username")
@click.option("--no-drafts", is_flag=True, help="Exclude draft merge requests")
@click.option(
    "--pipeline-status",
    help="Filter by pipeline status (success, failed, running, pending, canceled, skipped)",
)
@click.option("--limit", type=int, help="Maximum number of merge requests to fetch")
@click.option(
    "--trigger-pipeline",
    is_flag=True,
    help="Trigger a new pipeline for each merge request's source branch",
)
def list_merge_requests(
    format_handler,
    project,
    state,
    search,
    author,
    no_drafts,
    pipeline_status,
    limit,
    trigger_pipeline,
):
    """List merge requests."""
    mrs = MergeRequestsAPI.get_merge_requests(
        project_path=project,
        state=state,
        search=search,
        author_username=author,
        exclude_drafts=no_drafts,
        pipeline_status=pipeline_status,
        limit=limit,
    )

    if not mrs:
        console.print("[yellow]No merge requests found.[/yellow]")
        return

    format_handler(mrs)

    console.print(f"\n[dim]Total MRs: {len(mrs)}[/dim]")

    if trigger_pipeline:
        console.print("\n[bold cyan]Triggering pipelines...[/bold cyan]")
        for mr in mrs:
            # Get project path from project_id
            if not mr.project_id:
                console.print(f"[yellow]Skipping !{mr.iid} - no project_id available[/yellow]")
                continue

            project_obj = ProjectsAPI.get_project_by_id(mr.project_id)
            if not project_obj:
                console.print(f"[yellow]Skipping !{mr.iid} - could not fetch project info[/yellow]")
                continue

            console.print(
                f"[cyan]Triggering pipeline for !{mr.iid} ({project_obj.path_with_namespace}:{mr.source_branch})...[/cyan]"
            )
            pipeline = PipelinesAPI.trigger_mr_pipeline(project_obj.path_with_namespace, mr.iid)

            if pipeline:
                console.print(f"  [green]✓[/green] Pipeline #{pipeline.id} triggered successfully")
            else:
                console.print(f"  [red]✗[/red] Failed to trigger pipeline")


@mergerequests_cli.command(name="show")
@click.argument("project_path")
@click.argument("mr_iid", type=int)
@format_decorator(
    formats=["details", "json"],
    interactive_default="details",
    script_default="json",
    entity_type="merge_request",
)
def show_merge_request(project_path, mr_iid, format_handler):
    """Show details of a specific merge request."""
    mr = MergeRequestsAPI.get_merge_request(project_path, mr_iid)

    if not mr:
        console.print(f"[red]Merge request !{mr_iid} not found in {project_path}.[/red]")
        return

    format_handler(mr)
