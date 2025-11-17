"""Main CLI entry point for GitLab Toolbox."""

import click

from .api.client import GitLabClient
from .commands import groups_cli, projects_cli, mergerequests_cli, pipelines_cli


@click.group()
@click.version_option(version="1.0.0")
@click.option(
    "--repo-path",
    envvar="GITLAB_REPO_PATH",
    help="Path to a Git repository that uses the target GitLab instance. Can also be set via GITLAB_REPO_PATH env var.",
)
@click.option(
    "--debug",
    is_flag=True,
    envvar="GITLAB_DEBUG",
    help="Enable debug mode with verbose output. Can also be set via GITLAB_DEBUG env var.",
)
def cli(repo_path, debug):
    """GitLab Toolbox - A comprehensive CLI for GitLab operations.

    This tool provides commands for managing GitLab groups, projects,
    merge requests, and CI/CD pipelines using the glab CLI.
    """
    if repo_path:
        GitLabClient.set_repo_path(repo_path)
    if debug:
        GitLabClient.set_debug(True)


# Register command groups with aliases
cli.add_command(groups_cli)
cli.add_command(groups_cli, name="g")  # Alias for groups

cli.add_command(projects_cli)
cli.add_command(projects_cli, name="proj")  # Alias for projects

cli.add_command(mergerequests_cli)
cli.add_command(mergerequests_cli, name="mr")  # Alias for mergerequests

cli.add_command(pipelines_cli)
cli.add_command(pipelines_cli, name="p")  # Alias for pipelines


if __name__ == "__main__":
    cli()
