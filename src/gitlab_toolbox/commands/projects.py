"""Projects command implementation."""

import sys

import click
from rich.console import Console

from ..api.projects import ProjectsAPI
from ..formatters import DisplayFormatter

console = Console(file=sys.stderr)


@click.group(name="projects")
def projects_cli():
    """Manage GitLab projects."""
    pass


@projects_cli.command(name="list")
@click.option("--group", help="Filter projects by group path")
@click.option("--search", help="Search projects by name")
@click.option("--limit", type=int, help="Maximum number of projects to fetch")
def list_projects(group, search, limit):
    """List GitLab projects."""
    projects = ProjectsAPI.get_projects(group_path=group, search=search, limit=limit)

    if not projects:
        console.print("[yellow]No projects found.[/yellow]")
        return

    DisplayFormatter.display_projects_table(projects)
    console.print(f"\n[dim]Total projects: {len(projects)}[/dim]")


@projects_cli.command(name="show")
@click.argument("project_path")
def show_project(project_path):
    """Show details of a specific project."""
    project = ProjectsAPI.get_project(project_path)

    if not project:
        console.print(f"[red]Project '{project_path}' not found.[/red]")
        return

    DisplayFormatter.display_project_details(project)
