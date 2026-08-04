"""Scope resolution for CI/CD configuration commands.

Turns ``--project`` / ``--group`` selections (optionally recursing into
subgroups and their projects) into a flat list of :class:`Scope` objects, and
provides the ancestor-group chain used for variable inheritance.

The chain is derived from the scope's path (``a/b/c`` → ``a``, ``a/b``) rather
than by walking ``parent_id``, which keeps it to zero extra API calls and works
with a plain non-admin token.
"""

import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, List, Optional, Tuple, TypeVar

from rich.console import Console

from ..models.ci_scope import SCOPE_GROUP, SCOPE_PROJECT, Scope, SkippedScope
from .client import GitLabClient

console = Console(file=sys.stderr)

T = TypeVar("T")
R = TypeVar("R")


def map_concurrent(func: Callable[[T], R], items: Iterable[T], concurrency: int = 8) -> List[R]:
    """Apply ``func`` to ``items`` in parallel, preserving input order.

    Args:
        func: Callable applied to each item.
        items: Items to process.
        concurrency: Maximum number of worker threads.

    Returns:
        List of results in the same order as ``items``.
    """
    items = list(items)
    if not items:
        return []
    if concurrency <= 1 or len(items) == 1:
        return [func(item) for item in items]

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        return list(executor.map(func, items))


def ancestor_group_paths(path: str, scope_kind: str) -> List[str]:
    """Return ancestor group paths, outermost first.

    Args:
        path: Full path of the scope (e.g. ``acme/platform/app``).
        scope_kind: ``project`` or ``group``.

    Returns:
        Ancestor group paths. For project ``a/b/c`` this is ``['a', 'a/b']``;
        for group ``a/b`` it is ``['a']``.
    """
    segments = [segment for segment in path.split("/") if segment]
    # A project's namespace is everything but the last segment; for a group the
    # group itself is the last segment too, so the rule is identical.
    if scope_kind not in (SCOPE_PROJECT, SCOPE_GROUP):
        raise ValueError(f"Unknown scope kind: {scope_kind}")
    ancestors = segments[:-1]
    return ["/".join(ancestors[: i + 1]) for i in range(len(ancestors))]


class ScopeResolver:
    """Resolves CLI scope selections into concrete project/group scopes."""

    @classmethod
    def resolve(
        cls,
        projects: Optional[Iterable[str]] = None,
        groups: Optional[Iterable[str]] = None,
        include_subgroups: bool = False,
        include_projects: bool = False,
        archived: bool = False,
        limit: Optional[int] = None,
    ) -> Tuple[List[Scope], List[SkippedScope]]:
        """Resolve project and group references into scopes.

        Args:
            projects: Project paths or IDs.
            groups: Group paths or IDs.
            include_subgroups: Also include descendant groups of each group.
            include_projects: Also include projects of each selected group.
            archived: Include archived projects (default: skip them).
            limit: Cap on the number of projects fetched per group.

        Returns:
            Tuple of (scopes, skipped scopes).
        """
        scopes: List[Scope] = []
        skipped: List[SkippedScope] = []
        seen = set()

        def add(scope: Scope) -> None:
            if scope.ref not in seen:
                seen.add(scope.ref)
                scopes.append(scope)

        group_scopes: List[Scope] = []
        for ref in groups or []:
            group_scope, reason = cls._resolve_group(ref)
            if group_scope is None:
                skipped.append(SkippedScope(SCOPE_GROUP, ref, "scope", reason or "not found"))
                continue
            group_scopes.append(group_scope)

            if include_subgroups:
                for descendant in cls._descendant_groups(group_scope):
                    group_scopes.append(descendant)

        for group_scope in group_scopes:
            add(group_scope)

        if include_projects:
            for group_scope in group_scopes:
                project_scopes, reason = cls._group_projects(
                    group_scope, include_subgroups=include_subgroups, archived=archived, limit=limit
                )
                if reason:
                    skipped.append(SkippedScope(SCOPE_GROUP, group_scope.path, "projects", reason))
                    continue
                for project_scope in project_scopes:
                    add(project_scope)

        for ref in projects or []:
            project_scope, reason = cls._resolve_project(ref)
            if project_scope is None:
                skipped.append(SkippedScope(SCOPE_PROJECT, ref, "scope", reason or "not found"))
                continue
            add(project_scope)

        return scopes, skipped

    @classmethod
    def _resolve_group(cls, ref: str) -> Tuple[Optional[Scope], Optional[str]]:
        """Resolve a single group reference (numeric ID or full path)."""
        identifier = ref if str(ref).isdigit() else str(ref).replace("/", "%2F")
        data, reason = GitLabClient._run_api_request_safe(f"groups/{identifier}")
        if not isinstance(data, dict):
            return None, reason
        return (
            Scope(
                kind=SCOPE_GROUP,
                path=data.get("full_path", str(ref)),
                id=data.get("id"),
                web_url=data.get("web_url"),
            ),
            None,
        )

    @classmethod
    def _resolve_project(cls, ref: str) -> Tuple[Optional[Scope], Optional[str]]:
        """Resolve a single project reference (numeric ID or full path)."""
        identifier = ref if str(ref).isdigit() else str(ref).replace("/", "%2F")
        data, reason = GitLabClient._run_api_request_safe(f"projects/{identifier}")
        if not isinstance(data, dict):
            return None, reason
        return (
            Scope(
                kind=SCOPE_PROJECT,
                path=data.get("path_with_namespace", str(ref)),
                id=data.get("id"),
                web_url=data.get("web_url"),
            ),
            None,
        )

    @classmethod
    def _descendant_groups(cls, group_scope: Scope) -> List[Scope]:
        """Return all descendant groups of ``group_scope``."""
        data, reason = GitLabClient.paginate_safe(f"groups/{group_scope.api_id}/descendant_groups")
        if reason or not data:
            return []
        return [
            Scope(
                kind=SCOPE_GROUP,
                path=item.get("full_path", ""),
                id=item.get("id"),
                web_url=item.get("web_url"),
            )
            for item in data
            if item.get("full_path")
        ]

    @classmethod
    def _group_projects(
        cls,
        group_scope: Scope,
        include_subgroups: bool = False,
        archived: bool = False,
        limit: Optional[int] = None,
    ) -> Tuple[List[Scope], Optional[str]]:
        """Return the projects owned by a group.

        Projects shared *into* the group are excluded (``with_shared=false``)
        because their CI/CD configuration belongs to their own namespace.
        Subgroup projects are not requested here either: descendant groups
        become scopes of their own when ``--include-subgroups`` is used, so
        their projects are picked up when those scopes are processed.
        """
        params = {"with_shared": "false", "include_subgroups": "false"}
        if not archived:
            params["archived"] = "false"

        data, reason = GitLabClient.paginate_safe(
            f"groups/{group_scope.api_id}/projects", params, limit=limit
        )
        if reason:
            return [], reason
        return [
            Scope(
                kind=SCOPE_PROJECT,
                path=item.get("path_with_namespace", ""),
                id=item.get("id"),
                web_url=item.get("web_url"),
            )
            for item in (data or [])
            if item.get("path_with_namespace")
        ], None
