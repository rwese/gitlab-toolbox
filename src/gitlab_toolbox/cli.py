"""Main CLI entry point for GitLab Toolbox."""

import click

from .api.client import GitLabClient
from .commands import (
    groups_cli,
    projects_cli,
    mergerequests_cli,
    pipelines_cli,
    pipeline_schedules_cli,
)


@click.group()
@click.version_option(version="1.0.0")
@click.option(
    "--gitlab-url",
    envvar="GITLAB_URL",
    help="GitLab instance URL (defaults to https://gitlab.com). Can also be set via GITLAB_URL env var.",
)
@click.option(
    "--token",
    envvar="GITLAB_TOKEN",
    help="GitLab personal access token. Can also be set via GITLAB_TOKEN, CI_JOB_TOKEN, or GL_TOKEN env vars.",
)
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
def cli(gitlab_url, token, repo_path, debug):
    """GitLab Toolbox - A comprehensive CLI for GitLab operations.

    This tool provides commands for managing GitLab groups, projects,
    merge requests, CI/CD pipelines, and pipeline schedules using direct HTTP API calls.
    """
    # Configure GitLab client
    if gitlab_url:
        GitLabClient.set_base_url(gitlab_url)
    if token:
        GitLabClient.set_token(token)
    # Configure from environment if not explicitly set
    GitLabClient.configure_from_env()

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

cli.add_command(pipeline_schedules_cli)
cli.add_command(pipeline_schedules_cli, name="ps")  # Alias for pipeline-schedules


if __name__ == "__main__":
    cli()
