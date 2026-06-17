"""Whoami command implementation."""

import sys

import click
from rich.console import Console

from ..api.users import UsersAPI
from ..formatters.csv_formatter import CSVFormatter
from ..formatters.display import DisplayFormatter
from ..formatters.format_decorator import format_decorator
from ..formatters.json_formatter import JSONFormatter

console = Console(file=sys.stderr)


@click.group(name="whoami", invoke_without_command=True)
@format_decorator(
    formats=["details", "json", "csv"],
    interactive_default="details",
    script_default="json",
    format_handlers={
        "details": DisplayFormatter.display_user_details,
        "json": lambda user, **kwargs: print(JSONFormatter.format_user(user, **kwargs)),
        "csv": lambda user, **kwargs: print(CSVFormatter.format_users([user])),
    },
)
@click.pass_context
def whoami_cli(
    ctx,
    format_handler,
):
    """Show authenticated GitLab user information."""
    if ctx.invoked_subcommand is not None:
        return
    show_current_user(format_handler=format_handler)


def show_current_user(format_handler):
    """Show the authenticated user."""
    profile = UsersAPI.get_current_user()
    format_handler(profile)


@whoami_cli.command(name="memberships")
@click.option(
    "--type",
    "resource_type",
    type=click.Choice(["group", "project", "all"]),
    default="all",
    help="Membership resource type.",
)
@click.option("--min-access-level", type=int, help="Minimum GitLab access level.")
@click.option("--limit", type=int, help="Maximum number of memberships to fetch.")
@format_decorator(
    formats=["table", "json", "csv"],
    interactive_default="table",
    script_default="json",
    entity_type="user_memberships",
)
def memberships(format_handler, resource_type, min_access_level, limit):
    """List memberships visible for the authenticated user."""
    memberships_data = UsersAPI.get_current_memberships(
        resource_type=resource_type,
        min_access_level=min_access_level,
        limit=limit,
    )

    format_handler(memberships_data)


@whoami_cli.command(name="stats")
@format_decorator(
    formats=["details", "json", "csv"],
    interactive_default="details",
    script_default="json",
    entity_type="user_counts",
)
def stats(format_handler):
    """Show authenticated user's current work and association counts."""
    format_handler(UsersAPI.get_counts())
