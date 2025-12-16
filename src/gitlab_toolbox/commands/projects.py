"""Projects command implementation."""

import sys

import click
from rich.console import Console

from ..api.projects import ProjectsAPI
from ..formatters import DisplayFormatter, JSONFormatter, CSVFormatter
from ..formatters.format_decorator import format_decorator

console = Console(file=sys.stderr)


# Format handlers for projects list
def _format_projects_json(projects, **kwargs):
    """Format projects as JSON."""
    print(JSONFormatter.format_projects(projects))


def _format_projects_csv(projects, **kwargs):
    """Format projects as CSV."""
    print(CSVFormatter.format_projects(projects))


def _format_projects_table(projects, **kwargs):
    """Format projects as table."""
    DisplayFormatter.display_projects_table(projects)


PROJECTS_LIST_FORMAT_HANDLERS = {
    "json": _format_projects_json,
    "csv": _format_projects_csv,
    "table": _format_projects_table,
}


# Format handlers for project show
def _format_project_details(project, **kwargs):
    """Format project as details."""
    DisplayFormatter.display_project_details(project)


def _format_project_json(project, **kwargs):
    """Format project as JSON."""
    print(JSONFormatter.format_projects([project]))


PROJECT_SHOW_FORMAT_HANDLERS = {
    "details": _format_project_details,
    "json": _format_project_json,
}


@click.group(name="projects")
def projects_cli():
    """Manage GitLab projects."""
    pass


@projects_cli.command(name="list")
@format_decorator(
    formats=["table", "json", "csv"],
    interactive_default="table",
    script_default="csv",
    format_handlers=PROJECTS_LIST_FORMAT_HANDLERS,
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
    format_handlers=PROJECT_SHOW_FORMAT_HANDLERS,
)
def show_project(project_path, format_handler):
    """Show details of a specific project."""
    project = ProjectsAPI.get_project(project_path)

    if not project:
        console.print(f"[red]Project '{project_path}' not found.[/red]")
        return

    format_handler(project)
