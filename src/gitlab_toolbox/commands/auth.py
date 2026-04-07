"""Authentication commands for GitLab Toolbox."""

import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..api.auth import AuthAPI
from ..api.client import GitLabClient

console = Console(file=sys.stderr)


@click.group(name="auth")
def auth_cli():
    """Manage GitLab authentication."""
    pass


@auth_cli.command(name="status")
@click.option(
    "--url",
    help="GitLab instance URL to check (defaults to configured URL)",
)
@click.option(
    "--token",
    help="Token to check (defaults to configured token)",
)
def check_status(url: str, token: str):
    """Check authentication status with GitLab instance."""
    # Determine URL
    gitlab_url = url or GitLabClient._base_url or "https://gitlab.com"
    if not gitlab_url:
        gitlab_url = "https://gitlab.com"

    # Normalize URL
    gitlab_url = gitlab_url.rstrip("/")
    if not gitlab_url.startswith("http"):
        gitlab_url = f"https://{gitlab_url}"

    console.print(f"[bold cyan]Checking authentication for:[/bold cyan] {gitlab_url}")

    # Check authentication
    auth_info = AuthAPI.check_auth_with_url(gitlab_url, token)

    # Display results
    _display_auth_status(auth_info)


def _display_auth_status(auth_info: dict):
    """Display authentication status in a nice format."""
    is_authenticated = auth_info.get("is_authenticated", False)

    if is_authenticated:
        # Success panel
        panel = Panel(
            f"[green]✓ Authenticated[/green]\n\n"
            f"[bold]Username:[/bold] {auth_info.get('username', 'N/A')}\n"
            f"[bold]User ID:[/bold] {auth_info.get('user_id', 'N/A')}\n"
            f"[bold]Email:[/bold] {auth_info.get('user_email', 'N/A')}\n"
            f"[bold]Token Source:[/bold] {auth_info.get('token_source', 'unknown')}",
            title=f"Authentication Status: {auth_info.get('hostname')}",
            border_style="green",
        )
        console.print(panel)
    else:
        # Error/warning panel
        error = auth_info.get("error", "No valid authentication found")
        panel = Panel(
            f"[red]✗ Not Authenticated[/red]\n\n"
            f"[bold]Reason:[/bold] {error}\n\n"
            f"[dim]To authenticate, run:[/dim]\n"
            f"[dim]  gitlab-toolbox auth login --url {auth_info.get('base_url')}[/dim]",
            title=f"Authentication Status: {auth_info.get('hostname')}",
            border_style="red",
        )
        console.print(panel)

    # Show API details
    table = Table(title="Connection Details", show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Instance URL", auth_info.get("base_url", "N/A"))
    table.add_row("API Protocol", auth_info.get("api_protocol", "https"))
    table.add_row("GitLab.com Instance", "Yes" if auth_info.get("is_gitlab_com") else "No")

    console.print()
    console.print(table)


@auth_cli.command(name="login")
@click.option(
    "--url",
    help="GitLab instance URL (defaults to https://gitlab.com or GITLAB_URL env var)",
)
@click.option(
    "--token",
    help="Personal access token (will prompt if not provided)",
)
@click.option(
    "--token-name",
    default="gitlab-toolbox",
    help="Name for the token in configuration",
)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="Use interactive login (uses glab CLI)",
)
@click.option(
    "--glab",
    is_flag=True,
    help="Use glab CLI for authentication",
)
def login(url: str, token: str, token_name: str, interactive: bool, glab: bool):
    """Authenticate with a GitLab instance."""
    # Determine URL
    gitlab_url = url or GitLabClient._base_url or "https://gitlab.com"
    if not gitlab_url:
        gitlab_url = "https://gitlab.com"

    # Normalize URL
    gitlab_url = gitlab_url.rstrip("/")
    if not gitlab_url.startswith("http"):
        gitlab_url = f"https://{gitlab_url}"

    console.print(f"[bold cyan]Authenticating with:[/bold cyan] {gitlab_url}")

    # Use interactive mode if requested
    if interactive or glab:
        success = AuthAPI.login_interactive()
        if not success:
            raise click.Exit(1)
        return

    # Get token if not provided
    if not token:
        token = click.prompt(
            "Enter your GitLab personal access token",
            type=str,
            hide_input=True,
        )

    if not token:
        console.print("[red]Token is required.[/red]")
        raise click.Exit(1)

    # Perform login
    success = AuthAPI.login_with_token(gitlab_url, token, token_name)

    if not success:
        raise click.Exit(1)

    # Verify and show status
    console.print()
    console.print("[bold]Verifying authentication...[/bold]")
    auth_info = AuthAPI.check_auth_with_url(gitlab_url, token)
    _display_auth_status(auth_info)


@auth_cli.command(name="logout")
@click.option(
    "--url",
    help="GitLab instance URL (defaults to configured URL)",
)
@click.option(
    "--all",
    "all_instances",
    is_flag=True,
    help="Logout from all GitLab instances",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Don't ask for confirmation",
)
def logout(url: str, all_instances: bool, force: bool):
    """Remove authentication for a GitLab instance."""
    from pathlib import Path

    if all_instances:
        if not force:
            if not click.confirm(
                "This will remove authentication for all configured GitLab instances. Continue?"
            ):
                console.print("Aborted.")
                return

        config_path = Path.home() / ".config" / "glab-cli" / "config.yml"
        if config_path.exists():
            config_path.unlink()
            console.print("[green]Removed all GitLab authentication.[/green]")
        else:
            console.print("[yellow]No authentication configuration found.[/yellow]")
        return

    # Determine URL
    gitlab_url = url or GitLabClient._base_url
    if not gitlab_url:
        console.print("[red]No GitLab URL specified and none configured.[/red]")
        console.print(
            "[dim]Use --url to specify an instance, or use --all to logout from all instances.[/dim]"
        )
        raise click.Exit(1)

    # Normalize URL
    gitlab_url = gitlab_url.rstrip("/")
    hostname = gitlab_url.replace("https://", "").replace("http://", "")

    if not force:
        if not click.confirm(f"Remove authentication for {hostname}?"):
            console.print("Aborted.")
            return

    success = AuthAPI.logout(hostname)

    if not success:
        raise click.Exit(1)


@auth_cli.command(name="token")
@click.option(
    "--set",
    "set_token",
    help="Set token via command line (use with caution - this may be visible in shell history)",
)
@click.option(
    "--clear",
    is_flag=True,
    help="Clear the token from environment",
)
def manage_token(set_token: str, clear: bool):
    """Manage the GitLab token directly.

    This command helps manage the token used for authentication.
    Tokens can come from environment variables or glab config.
    """
    import os

    if clear:
        # Clear token from environment
        env_vars = [
            "GITLAB_TOKEN",
            "GL_TOKEN",
            "CI_JOB_TOKEN",
            "CI_API_TOKEN",
            "GITLAB_ACCESS_TOKEN",
        ]
        cleared = []
        for var in env_vars:
            if os.environ.get(var):
                del os.environ[var]
                cleared.append(var)

        if cleared:
            console.print(f"[green]Cleared environment variables: {', '.join(cleared)}[/green]")
        else:
            console.print("[yellow]No token environment variables found.[/yellow]")
        return

    if set_token:
        # Set token in environment
        os.environ["GITLAB_TOKEN"] = set_token
        console.print("[green]Token set in GITLAB_TOKEN environment variable.[/green]")
        console.print("[dim]Note: This only affects the current shell session.[/dim]")
        return

    # Show current token status
    env_vars = ["GITLAB_TOKEN", "GL_TOKEN", "CI_JOB_TOKEN", "CI_API_TOKEN", "GITLAB_ACCESS_TOKEN"]

    table = Table(title="Token Environment Variables", show_header=True)
    table.add_column("Variable", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Value", style="dim")

    for var in env_vars:
        value = os.environ.get(var)
        if value:
            # Show masked value (first 4 and last 4 chars)
            masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
            table.add_row(var, "[green]Set[/green]", masked)
        else:
            table.add_row(var, "[dim]Not set[/dim]", "")

    console.print(table)
    console.print()
    console.print("[dim]To set a token: gitlab-toolbox auth token --set YOUR_TOKEN[/dim]")
    console.print("[dim]To clear tokens: gitlab-toolbox auth token --clear[/dim]")


@auth_cli.command(name="setup")
@click.option(
    "--url",
    default="https://gitlab.com",
    help="GitLab instance URL",
)
@click.option(
    "--token",
    help="Personal access token (will prompt securely if not provided)",
)
@click.option(
    "--scope",
    type=click.Choice(["api", "read_api", "read_repository", "write_repository", "all"]),
    default="api",
    help="Token scope to request",
)
def setup(url: str, token: str, scope: str):
    """Interactive setup wizard for GitLab authentication.

    This command guides users through setting up authentication step by step.
    """
    console.print(
        Panel(
            "[bold cyan]GitLab Toolbox Authentication Setup[/bold cyan]\n\n"
            "This wizard will help you configure authentication with your GitLab instance.",
            border_style="cyan",
        )
    )

    # Step 1: Get URL
    if not url or url == "https://gitlab.com":
        console.print("\n[bold]Step 1:[/bold] GitLab Instance URL")
        url = click.prompt(
            "Enter your GitLab instance URL",
            default=url,
            type=str,
        )

    # Normalize URL
    url = url.rstrip("/")
    if not url.startswith("http"):
        url = f"https://{url}"

    console.print(f"[green]  → Using: {url}[/green]")

    # Step 2: Get token
    console.print("\n[bold]Step 2:[/bold] Personal Access Token")

    if not token:
        console.print("""
[dim]Create a personal access token at:[/dim]
  {url}/-/profile/personal_access_tokens

[dim]Required scopes:[/dim]
  • api - Full API access
  • read_api - Read API access
  • read_repository - Read repository access
  • write_repository - Write repository access
""".format(url=url))

        token = click.prompt(
            "Enter your personal access token",
            type=str,
            hide_input=True,
        )

    console.print("[green]  → Token received[/green]")

    # Step 3: Validate and store
    console.print("\n[bold]Step 3:[/bold] Validating and Storing Credentials")

    success = AuthAPI.login_with_token(url, token, "gitlab-toolbox")

    if success:
        console.print("\n[bold green]✓ Authentication configured successfully![/bold green]")

        # Verify
        auth_info = AuthAPI.check_auth_with_url(url, token)
        _display_auth_status(auth_info)

        console.print("""
[dim]You can now use gitlab-toolbox commands.[/dim]
[dim]Run 'gitlab-toolbox auth status' to verify your authentication.[/dim]
""")
    else:
        console.print("\n[bold red]✗ Authentication failed.[/bold red]")
        console.print("[dim]Please check your token and try again.[/dim]")
        raise click.Exit(1)
