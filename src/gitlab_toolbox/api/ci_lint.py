"""CI lint API operations.

Implements the GitLab CI Lint API as documented at
https://docs.gitlab.com/api/lint/.

Two endpoints are exposed:

* ``POST /projects/:id/ci/lint`` — validate YAML provided as the
  ``content`` request body field.
* ``GET /projects/:id/ci/lint`` — validate the project's own
  ``.gitlab-ci.yml`` (optionally at a specific ref).

Both endpoints share the same response shape; see
:func:`CILintAPI._parse_result` for the parsing logic.

Note: the ``:id`` path segment of both endpoints must be the project's
**numeric** ID. Path-based lookups (``group/project``) are not accepted
by the lint endpoints, so callers can pass either a numeric ID or a
project path and :func:`CILintAPI._resolve_project_id` will handle the
translation transparently.
"""

import sys
from typing import Any, Dict, Optional

from rich.console import Console

from ..models import CILintResult, LintJob
from .client import GitLabClient

console = Console(file=sys.stderr)


class CILintAPI:
    """API wrapper for the GitLab CI Lint API."""

    @staticmethod
    def _resolve_project_id(project: str) -> Optional[int]:
        """Resolve a project path or numeric ID to a numeric ID.

        The CI Lint endpoints only accept the numeric project ID in
        their ``:id`` path segment, so any caller-provided project path
        (e.g. ``group/project``) must first be translated to its
        numeric ID via ``GET /projects/:id_or_path``.

        Args:
            project: Either a numeric project ID (as a string) or a
                project path (e.g. ``group/project``).

        Returns:
            The numeric project ID, or ``None`` if the project could
            not be resolved.
        """
        # If the caller already provided a numeric ID, skip the lookup.
        if project.isdigit():
            return int(project)

        encoded_path = project.replace("/", "%2F")
        with console.status(f"[bold green]Resolving project {project}..."):
            data = GitLabClient._run_api_request_optional(f"projects/{encoded_path}")

        if not data or not isinstance(data, dict):
            return None
        return data.get("id")

    @classmethod
    def lint_content(
        cls,
        project_path: str,
        content: str,
        *,
        ref: Optional[str] = None,
        dry_run: bool = False,
        include_jobs: bool = False,
    ) -> Optional[CILintResult]:
        """Validate a CI configuration provided as content via the POST endpoint.

        Args:
            project_path: The project path (e.g., ``group/project``)
                or numeric ID. Will be resolved to the numeric ID
                before calling the API.
            content: The CI/CD configuration YAML content. Maps to the
                ``content`` API field.
            ref: Optional branch/tag context. Maps to the ``ref`` API
                field. According to the GitLab documentation this is only
                consulted when ``dry_run`` is true; it is still sent if
                provided.
            dry_run: When ``True``, runs a pipeline-creation simulation
                instead of just a static check. Maps to ``dry_run``.
            include_jobs: When ``True``, the response includes the list
                of jobs that would exist. Maps to ``include_jobs``.

        Returns:
            A :class:`CILintResult` populated from the API response, or
            ``None`` if the project could not be resolved or the API
            call failed.
        """
        project_id = cls._resolve_project_id(project_path)
        if project_id is None:
            console.print(f"[red]Project not found:[/red] {project_path}")
            return None

        body: Dict[str, Any] = {"content": content}
        body["dry_run"] = bool(dry_run)
        body["include_jobs"] = bool(include_jobs)
        if ref:
            body["ref"] = ref

        with console.status("[bold green]Linting CI configuration..."):
            data = GitLabClient._run_api_request(
                f"projects/{project_id}/ci/lint",
                body,
                method="POST",
            )

        return cls._parse_result(data)

    @classmethod
    def lint_project(
        cls,
        project_path: str,
        *,
        content_ref: Optional[str] = None,
        dry_run: bool = False,
        dry_run_ref: Optional[str] = None,
        include_jobs: bool = False,
    ) -> Optional[CILintResult]:
        """Validate the project's ``.gitlab-ci.yml`` via the GET endpoint.

        Args:
            project_path: The project path (e.g., ``group/project``)
                or numeric ID. Will be resolved to the numeric ID
                before calling the API.
            content_ref: SHA, branch, or tag to read the configuration
                from. Maps to ``content_ref``. Defaults to the head of
                the project's default branch.
            dry_run: When ``True``, runs a pipeline-creation simulation
                instead of just a static check. Maps to ``dry_run``.
            dry_run_ref: Branch/tag context used when ``dry_run`` is
                true. Maps to ``dry_run_ref``. Defaults to the project's
                default branch when omitted.
            include_jobs: When ``True``, the response includes the list
                of jobs that would exist. Maps to ``include_jobs``.

        Returns:
            A :class:`CILintResult` populated from the API response, or
            ``None`` if the project could not be resolved or the API
            call failed.
        """
        project_id = cls._resolve_project_id(project_path)
        if project_id is None:
            console.print(f"[red]Project not found:[/red] {project_path}")
            return None

        params: Dict[str, Any] = {}
        params["dry_run"] = "true" if dry_run else "false"
        params["include_jobs"] = "true" if include_jobs else "false"
        if content_ref:
            params["content_ref"] = content_ref
        if dry_run_ref:
            params["dry_run_ref"] = dry_run_ref

        with console.status("[bold green]Linting project CI configuration..."):
            data = GitLabClient._run_api_request(
                f"projects/{project_id}/ci/lint",
                params,
                method="GET",
            )

        return cls._parse_result(data)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    @classmethod
    def _parse_result(cls, data: Any) -> Optional[CILintResult]:
        """Parse the raw API response into a :class:`CILintResult`.

        Args:
            data: Parsed JSON dictionary returned by the API.

        Returns:
            A :class:`CILintResult`, or ``None`` if ``data`` is not a
            mapping (defensive against unexpected payloads).
        """
        if not isinstance(data, dict):
            return None

        return CILintResult(
            valid=bool(data.get("valid", False)),
            errors=list(data.get("errors") or []),
            warnings=list(data.get("warnings") or []),
            merged_yaml=data.get("merged_yaml"),
            includes=list(data.get("includes") or []),
            jobs=[cls._parse_job(j) for j in (data.get("jobs") or [])],
        )

    @staticmethod
    def _parse_job(data: Dict[str, Any]) -> LintJob:
        """Parse a single job entry from the lint response."""
        return LintJob(
            name=data.get("name", ""),
            stage=data.get("stage"),
            before_script=list(data.get("before_script") or []),
            script=list(data.get("script") or []),
            after_script=list(data.get("after_script") or []),
            tag_list=list(data.get("tag_list") or []),
            only=data.get("only"),
            except_config=data.get("except"),
            environment=data.get("environment"),
            when=data.get("when"),
            allow_failure=bool(data.get("allow_failure", False)),
            needs=data.get("needs"),
        )
