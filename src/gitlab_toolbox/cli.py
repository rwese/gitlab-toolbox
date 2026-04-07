"""Main CLI entry point for GitLab Toolbox."""

import click

from .api.client import GitLabClient
from .commands import (
    auth_cli,
    groups_cli,
    projects_cli,
    mergerequests_cli,
    pipelines_cli,
    pipeline_schedules_cli,
)


@click.group(context_settings={"ignore_unknown_options": True}, invoke_without_command=True)
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
@click.option(
    "--project",
    envvar="GITLAB_TOOLBOX_PROJECT",
    help="Default project path. Can also be set via GITLAB_TOOLBOX_PROJECT env var.",
)
@click.pass_context
def cli(ctx, gitlab_url, token, repo_path, debug, project):
    """GitLab Toolbox - A comprehensive CLI for GitLab operations.

    This tool provides commands for managing GitLab groups, projects,
    merge requests, CI/CD pipelines, and pipeline schedules using direct HTTP API calls.
    """
    # Show help if no command provided
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)

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

    # Handle project: CLI arg > env var > git remote fallback
    if not project:
        base_url = GitLabClient._base_url if GitLabClient._base_url else "https://gitlab.com"
        project = GitLabClient.get_project_from_git(base_url)

    if project:
        GitLabClient.set_repo_path(project)


# Register command groups
cli.add_command(auth_cli)
cli.add_command(groups_cli)
cli.add_command(projects_cli)
cli.add_command(mergerequests_cli)
cli.add_command(pipelines_cli)
cli.add_command(pipeline_schedules_cli)


if __name__ == "__main__":
    cli()
