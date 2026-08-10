"""Read-only authentication status command."""

import sys
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..api.auth import AuthAPI
from ..api.client import GitLabClient

console = Console(file=sys.stderr)


@click.group(name="auth")
def auth_cli() -> None:
    """Inspect GitLab authentication."""


@auth_cli.command(name="status")
@click.option("--url", help="GitLab instance URL to check.")
@click.option("--token", help="Token to check before falling back to glab authentication.")
def check_status(url: Optional[str], token: Optional[str]) -> None:
    """Check authentication status with a GitLab instance."""
    gitlab_url = (url or GitLabClient._base_url or "https://gitlab.com").rstrip("/")
    if not gitlab_url.startswith("http"):
        gitlab_url = f"https://{gitlab_url}"

    console.print(f"[bold cyan]Checking authentication for:[/bold cyan] {gitlab_url}")
    _display_auth_status(AuthAPI.check_auth_with_url(gitlab_url, token))


def _display_auth_status(auth_info: dict) -> None:
    """Render an authentication-status response."""
    if auth_info["is_authenticated"]:
        panel = Panel(
            f"[green]✓ Authenticated[/green]\n\n"
            f"[bold]Username:[/bold] {auth_info.get('username', 'N/A')}\n"
            f"[bold]User ID:[/bold] {auth_info.get('user_id', 'N/A')}\n"
            f"[bold]Email:[/bold] {auth_info.get('user_email', 'N/A')}\n"
            f"[bold]Token Source:[/bold] {auth_info.get('token_source', 'unknown')}",
            title=f"Authentication Status: {auth_info['hostname']}",
            border_style="green",
        )
    else:
        panel = Panel(
            f"[red]✗ Not Authenticated[/red]\n\n"
            f"[bold]Reason:[/bold] {auth_info['error']}\n\n"
            "[dim]Set GITLAB_TOKEN or authenticate with glab.[/dim]",
            title=f"Authentication Status: {auth_info['hostname']}",
            border_style="red",
        )
    console.print(panel)

    table = Table(title="Connection Details", show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Instance URL", auth_info["base_url"])
    table.add_row("API Protocol", auth_info["api_protocol"])
    table.add_row("GitLab.com Instance", "Yes" if auth_info["is_gitlab_com"] else "No")
    console.print()
    console.print(table)
