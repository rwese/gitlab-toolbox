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

Note on variables: the CI Lint API does **not** accept a top-level
``variables`` request parameter. To simulate variables during lint, this
module injects them into the YAML's top-level ``variables:`` block
before POSTing. See :func:`_merge_variables_into_yaml`.
"""

import sys
from typing import Any, Dict, Optional

import yaml
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
        variables: Optional[Dict[str, str]] = None,
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
            variables: Optional mapping of CI/CD variables to inject
                into the YAML's top-level ``variables:`` block before
                POSTing. The CI Lint API itself does not accept a
                variables parameter, so this is the only way to
                simulate variables. Values provided here override any
                same-named entries already defined at the YAML top
                level (matching how project-level CI/CD variables
                override YAML-defined variables in real pipelines).

        Returns:
            A :class:`CILintResult` populated from the API response, or
            ``None`` if the project could not be resolved or the API
            call failed.
        """
        project_id = cls._resolve_project_id(project_path)
        if project_id is None:
            console.print(f"[red]Project not found:[/red] {project_path}")
            return None

        # The CI Lint API does not accept a variables parameter. Inject
        # the requested variables into the YAML's top-level variables:
        # block so the simulation sees them.
        body_content = content
        if variables:
            body_content = _merge_variables_into_yaml(content, variables)

        body: Dict[str, Any] = {"content": body_content}
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
        variables: Optional[Dict[str, str]] = None,
    ) -> Optional[CILintResult]:
        """Validate the project's ``.gitlab-ci.yml``.

        Without ``variables``, the project's stored ``.gitlab-ci.yml``
        is validated via the GET endpoint (which uses
        ``content_ref``/``dry_run_ref``). With ``variables``, the file
        is first fetched via the repository files API and merged with
        the variables locally, then validated via the POST endpoint
        (because the CI Lint API itself does not accept a
        ``variables`` parameter on either endpoint).

        Args:
            project_path: The project path (e.g., ``group/project``)
                or numeric ID. Will be resolved to the numeric ID
                before calling the API.
            content_ref: SHA, branch, or tag to read the configuration
                from. Maps to ``content_ref`` on GET; passed as ``ref``
                on the POST fallback when ``variables`` are provided.
                Defaults to the head of the project's default branch.
            dry_run: When ``True``, runs a pipeline-creation simulation
                instead of just a static check. Maps to ``dry_run``.
            dry_run_ref: Branch/tag context used when ``dry_run`` is
                true. Maps to ``dry_run_ref`` on GET; passed as ``ref``
                on the POST fallback. Defaults to the project's default
                branch when omitted.
            include_jobs: When ``True``, the response includes the list
                of jobs that would exist. Maps to ``include_jobs``.
            variables: Optional mapping of CI/CD variables to inject
                into the YAML's top-level ``variables:`` block before
                POSTing. See :meth:`lint_content` for semantics.

        Returns:
            A :class:`CILintResult` populated from the API response, or
            ``None`` if the project could not be resolved, the file
            could not be fetched, or the API call failed.
        """
        project_id = cls._resolve_project_id(project_path)
        if project_id is None:
            console.print(f"[red]Project not found:[/red] {project_path}")
            return None

        if variables:
            # The GET endpoint can't honor an injected-variables
            # request. Fetch the file, merge, and fall through to POST.
            raw = cls.fetch_project_ci_yml(project_path, ref=content_ref)
            if raw is None:
                return None
            return cls.lint_content(
                project_path,
                raw,
                ref=dry_run_ref or content_ref,
                dry_run=dry_run,
                include_jobs=include_jobs,
                variables=variables,
            )

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

    @classmethod
    def fetch_project_ci_yml(
        cls,
        project_path: str,
        *,
        ref: Optional[str] = None,
    ) -> Optional[str]:
        """Fetch the project's ``.gitlab-ci.yml`` via the repository files API.

        Args:
            project_path: The project path (e.g., ``group/project``)
                or numeric ID. Will be resolved to the numeric ID
                before calling the API.
            ref: Optional branch/tag/SHA to read the file from. Maps
                to the ``ref`` query parameter on the raw-files API.
                Defaults to the project's default branch when omitted.

        Returns:
            The file contents as text, or ``None`` if the project
            could not be resolved, the file does not exist (HTTP 404),
            or the API call failed.
        """
        project_id = cls._resolve_project_id(project_path)
        if project_id is None:
            console.print(f"[red]Project not found:[/red] {project_path}")
            return None

        params: Dict[str, Any] = {}
        if ref:
            params["ref"] = ref

        with console.status(f"[bold green]Fetching .gitlab-ci.yml from {project_path}..."):
            return GitLabClient._run_api_request_raw(
                f"projects/{project_id}/repository/files/.gitlab-ci.yml/raw",
                params=params,
                method="GET",
            )

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


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------
def _merge_variables_into_yaml(content: str, variables: Dict[str, str]) -> str:
    """Merge variables into the YAML's top-level ``variables:`` block.

    The CI Lint API does not accept a top-level ``variables`` request
    parameter, so the only way to simulate variables during lint is to
    splice them into the YAML before POSTing. This helper performs a
    round-trip through PyYAML, merging ``variables`` into any existing
    top-level ``variables:`` block. Provided values override existing
    values for the same key (matching how project-level CI/CD
    variables override YAML-defined variables in real pipelines).

    Long-form variable entries already in the YAML (e.g.
    ``variables: { VAR: { value: ..., description: ... } }``) are
    preserved as-is unless the same key is overridden by ``variables``;
    in that case the user-provided string value replaces the long-form
    entry entirely.

    If the input cannot be parsed as a YAML mapping at the top level,
    the original content is returned untouched and a warning is
    printed to stderr. We prefer not to fail here so that GitLab's own
    (slightly more lenient) YAML parser can still report the
    underlying problem with a useful error message.

    Args:
        content: Original YAML content (must be a mapping at the top
            level — true for any valid ``.gitlab-ci.yml``).
        variables: Mapping of variable names to string values to
            inject. Empty / ``None`` short-circuits and returns
            ``content`` unchanged.

    Returns:
        A new YAML string with the merged ``variables:`` block, or the
        original ``content`` if ``variables`` is empty or the YAML
        could not be parsed.
    """
    if not variables:
        return content

    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as e:
        console.print(
            f"[yellow]warning:[/yellow] could not parse YAML locally to inject "
            f"variables; sending content unmodified. GitLab will report the "
            f"parse error directly. ({e})"
        )
        return content

    if not isinstance(parsed, dict):
        # Top-level isn't a mapping. .gitlab-ci.yml must be a mapping,
        # but defer to GitLab's parser if it's something exotic.
        console.print(
            "[yellow]warning:[/yellow] YAML top-level is not a mapping; sending "
            "content unmodified so GitLab can report the issue."
        )
        return content

    existing = parsed.get("variables")
    merged: Dict[str, Any] = {}
    if isinstance(existing, dict):
        for key, val in existing.items():
            # Pass through long-form (dict-valued) entries untouched;
            # short-form (string-valued) entries become normal merges.
            merged[key] = val
    elif existing is not None:
        # Unrecognised shape (e.g. a list or scalar at this key).
        # Preserve it under a sentinel so the merge isn't lossy, but
        # in practice this branch is unreachable for .gitlab-ci.yml.
        merged["__existing_variables__"] = existing

    for key, val in variables.items():
        merged[key] = val

    parsed["variables"] = merged
    return yaml.safe_dump(parsed, default_flow_style=False, sort_keys=False)
