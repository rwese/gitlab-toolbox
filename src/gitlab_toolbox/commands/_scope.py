"""Shared Click options for selecting projects and groups."""

import sys
from typing import Callable, List, Optional, Tuple

import click
from rich.console import Console

from ..api.client import GitLabClient
from ..api.scope import ScopeResolver
from ..models.ci_scope import Scope, SkippedScope

console = Console(file=sys.stderr)


def scope_options(func: Callable) -> Callable:
    """Add the shared ``--project`` / ``--group`` scope selection options."""
    options = [
        click.option(
            "--project",
            "projects",
            multiple=True,
            help="Project path or ID (repeatable). Defaults to the global --project or git remote.",
        ),
        click.option(
            "--group",
            "groups",
            multiple=True,
            help="Group path or ID (repeatable).",
        ),
        click.option(
            "--include-subgroups",
            is_flag=True,
            help="Recurse into descendant groups of each --group.",
        ),
        click.option(
            "--include-projects",
            is_flag=True,
            help="Include the projects of each selected group.",
        ),
        click.option(
            "--archived/--no-archived",
            default=False,
            help="Include archived projects (default: skip them).",
        ),
        click.option("--limit", type=int, help="Maximum number of projects fetched per group."),
        click.option(
            "--concurrency",
            type=int,
            default=8,
            show_default=True,
            help="Number of parallel API requests.",
        ),
    ]
    for option in reversed(options):
        func = option(func)
    return func


def resolve_scopes(
    projects: Tuple[str, ...],
    groups: Tuple[str, ...],
    include_subgroups: bool,
    include_projects: bool,
    archived: bool,
    limit: Optional[int],
) -> Tuple[List[Scope], List[SkippedScope]]:
    """Resolve the scope options into concrete scopes.

    Falls back to the globally configured project (``--project`` on the root
    command, ``GITLAB_TOOLBOX_PROJECT`` or the git remote) when neither
    ``--project`` nor ``--group`` is given.

    Returns:
        Tuple of (scopes, skipped scopes).
    """
    project_refs = list(projects)
    group_refs = list(groups)

    if not project_refs and not group_refs:
        default_project = GitLabClient._repo_path
        if not default_project:
            raise click.UsageError(
                "No scope given. Use --project/--group, the global --project option, "
                "or run inside a GitLab repository."
            )
        project_refs = [default_project]

    scopes, skipped = ScopeResolver.resolve(
        projects=project_refs,
        groups=group_refs,
        include_subgroups=include_subgroups,
        include_projects=include_projects,
        archived=archived,
        limit=limit,
    )

    if not scopes:
        console.print("[yellow]No readable scopes resolved.[/yellow]")

    return scopes, skipped
