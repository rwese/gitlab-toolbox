"""Projects command implementation."""

import sys

import click
from rich.console import Console

from ..api.projects import ProjectsAPI
from ..formatters.format_decorator import format_decorator

console = Console(file=sys.stderr)


@click.group(name="projects")
def projects_cli():
    """Manage GitLab projects."""
    pass


@projects_cli.command(name="list")
@format_decorator(
    formats=["table", "json", "csv"],
    interactive_default="table",
    script_default="csv",
    entity_type="projects",
)
@click.option("--group", help="Filter projects by group path")
@click.option("--include-subgroups", is_flag=True, help="Include projects from subgroups")
@click.option("--search", help="Search projects by name")
@click.option(
    "--sort",
    type=click.Choice(["path", "stars", "forks", "last_updated"]),
    default="path",
    help="Sort projects by field (default: path)",
)
@click.option("--limit", type=int, help="Maximum number of projects to fetch")
def list_projects(format_handler, group, include_subgroups, search, sort, limit):
    """List GitLab projects."""
    projects = ProjectsAPI.get_projects(
        group_path=group,
        search=search,
        limit=limit,
        include_subgroups=include_subgroups,
        sort_by=sort,
    )

    if not projects:
        console.print("[yellow]No projects found.[/yellow]")
        return

    format_handler(projects)

    if include_subgroups:
        console.print(f"\n[dim]Total projects (including subgroups): {len(projects)}[/dim]")
    else:
        console.print(f"\n[dim]Total projects: {len(projects)}[/dim]")


@projects_cli.command(name="show")
@click.argument("project_path")
@format_decorator(
    formats=["details", "json"],
    interactive_default="details",
    script_default="json",
    entity_type="project",
)
def show_project(project_path, format_handler):
    """Show details of a specific project."""
    project = ProjectsAPI.get_project(project_path)

    if not project:
        console.print(f"[red]Project '{project_path}' not found.[/red]")
        return

    format_handler(project)
