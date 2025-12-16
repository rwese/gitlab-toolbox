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
@click.option("--search", help="Search projects by name")
@click.option("--limit", type=int, help="Maximum number of projects to fetch")
def list_projects(format_handler, group, search, limit):
    """List GitLab projects."""
    projects = ProjectsAPI.get_projects(group_path=group, search=search, limit=limit)

    if not projects:
        console.print("[yellow]No projects found.[/yellow]")
        return

    format_handler(projects)

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
