"""Groups command implementation."""

import sys

import click
from rich.console import Console
from rich.panel import Panel

from ..api.groups import GroupsAPI
from ..formatters import DisplayFormatter
from ..formatters.format_decorator import format_decorator

console = Console(file=sys.stderr)


@click.group(name="groups")
def groups_cli():
    """Manage GitLab groups and members."""
    pass


@groups_cli.command(name="list")
@format_decorator(
    formats=["table", "tree", "json", "markdown", "csv"],
    interactive_default="tree",
    script_default="csv",
    entity_type="groups",
)
@click.option("--include-members", is_flag=True, help="Fetch group members (slower)")
@click.option(
    "--active-members-only",
    is_flag=True,
    help="Only show active members (requires --include-members)",
)
@click.option("--summary", is_flag=True, help="Show summary statistics")
@click.option("--search", help="Search groups by name")
@click.option("--limit", type=int, help="Maximum number of groups to fetch")
def list_groups(format_handler, include_members, active_members_only, summary, search, limit):
    """List all GitLab groups."""
    console.print(
        Panel(
            "[bold cyan]GitLab Groups Explorer[/bold cyan]",
            subtitle="Fetching data from GitLab...",
        )
    )

    # Fetch all groups
    groups_data = GroupsAPI.get_all_groups(search=search, limit=limit)

    if not groups_data:
        console.print("[yellow]No groups found or error occurred.[/yellow]")
        return

    # Build group tree
    groups = GroupsAPI.build_group_tree(
        groups_data, fetch_members=include_members, active_members_only=active_members_only
    )

    # Display results using format handler
    format_handler(groups, show_members=include_members)

    # Show summary if requested
    if summary:
        console.print()
        DisplayFormatter.display_groups_summary(groups)


@groups_cli.command(name="show")
@click.argument("group_path")
@format_decorator(
    formats=["table", "tree", "json", "markdown", "csv"],
    interactive_default="tree",
    script_default="csv",
    entity_type="groups",
)
@click.option("--include-members", is_flag=True, help="Fetch group members (slower)")
@click.option(
    "--active-members-only",
    is_flag=True,
    help="Only show active members (requires --include-members)",
)
def show_group(group_path, format_handler, include_members, active_members_only):
    """Show details of a specific group and its subgroups."""
    console.print(f"[bold]Searching for group:[/bold] {group_path}")

    # Fetch all groups and find the matching one
    groups_data = GroupsAPI.get_all_groups()
    matching_group = None

    for group_data in groups_data:
        if group_data.get("full_path") == group_path:
            matching_group = group_data
            break

    if not matching_group:
        console.print(f"[red]Group '{group_path}' not found.[/red]")
        return

    # Fetch subgroups
    subgroups_data = GroupsAPI.get_subgroups(matching_group["id"])
    all_groups_data = [matching_group] + subgroups_data

    # Build tree
    groups = GroupsAPI.build_group_tree(
        all_groups_data, fetch_members=include_members, active_members_only=active_members_only
    )

    # Display using format handler
    format_handler(groups, show_members=include_members)
