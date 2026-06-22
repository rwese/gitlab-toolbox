"""CI command implementation.

Provides ``gitlab-toolbox ci validate`` which wraps the GitLab CI Lint API
(https://docs.gitlab.com/api/lint/).

Three input modes are supported:

* ``-f PATH``     — validate a local YAML file (POST endpoint).
* ``-f -``        — validate YAML piped through stdin (POST endpoint).
* ``-f`` omitted  — validate the project's own ``.gitlab-ci.yml``
                    (GET endpoint).
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from ..api.ci_lint import CILintAPI
from ..api.client import GitLabClient
from ..formatters import DisplayFormatter

# Console for status/info messages (goes to stderr)
console = Console(file=sys.stderr)


@click.group(name="ci")
def ci_cli():
    """Manage and validate GitLab CI/CD configurations."""
    pass


@ci_cli.command(name="validate")
@click.option(
    "-f",
    "--file",
    "file_path",
    type=click.Path(allow_dash=True),
    default=None,
    help=(
        "Path to a CI/CD YAML file, or '-' to read YAML from stdin. "
        "When omitted, the project's .gitlab-ci.yml is linted via the "
        "GET endpoint."
    ),
)
@click.option(
    "--ref",
    "ref",
    default=None,
    help=(
        "Git ref (branch, tag, or SHA) for the lint operation. "
        "POST: validation context when --dry-run is enabled. "
        "GET: which ref to read .gitlab-ci.yml from (content_ref). "
        "Defaults to the project's default branch."
    ),
)
@click.option(
    "--dry-run-ref",
    "dry_run_ref",
    default=None,
    help=(
        "Git ref (branch or tag) used as the pipeline-creation simulation "
        "context when --dry-run is enabled. Maps to POST: ref, GET: "
        "dry_run_ref. Defaults to the value of --ref."
    ),
)
@click.option(
    "--dry-run/--no-dry-run",
    "dry_run",
    default=False,
    help=(
        "Run a pipeline-creation simulation in addition to the static "
        "syntax check. (POST/GET: dry_run) [default: --no-dry-run]"
    ),
)
@click.option(
    "--include-jobs/--no-include-jobs",
    "include_jobs",
    default=False,
    help=(
        "Include the resolved list of jobs in the API response. "
        "(POST/GET: include_jobs) [default: --no-include-jobs]"
    ),
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help=(
        "Output format. 'table' prints a human-readable summary; "
        "'json' prints the raw API response. [default: table]"
    ),
)
@click.option(
    "--fail-on-warning",
    "fail_on_warning",
    is_flag=True,
    default=False,
    help=(
        "Exit with a non-zero status when the lint result is valid but "
        "contains warnings. Validation errors always produce a non-zero "
        "exit regardless of this flag."
    ),
)
def validate_ci(
    file_path: Optional[str],
    ref: Optional[str],
    dry_run_ref: Optional[str],
    dry_run: bool,
    include_jobs: bool,
    output_format: str,
    fail_on_warning: bool,
):
    """Validate a GitLab CI/CD configuration using the project CI Lint API.

    Mandatory fields by endpoint:

      POST /projects/:id/ci/lint  -> content (provided via --file / stdin)

      GET  /projects/:id/ci/lint  -> project context only

    \b
    Examples:
      # Lint a local .gitlab-ci.yml
      gitlab-toolbox ci validate --project group/project -f .gitlab-ci.yml

      # Lint YAML piped through stdin
      cat .gitlab-ci.yml | gitlab-toolbox ci validate --project group/project -f -

      # Lint the project's own .gitlab-ci.yml on its default branch
      gitlab-toolbox ci validate --project group/project

      # Simulate a pipeline against a feature branch, with jobs listed
      gitlab-toolbox ci validate --project group/project -f .gitlab-ci.yml \\
          --ref feature/login --dry-run --include-jobs
    """
    project = GitLabClient._repo_path
    if not project:
        raise click.ClickException(
            "--project is required (set via --project, GITLAB_TOOLBOX_PROJECT, "
            "or run from a git repository with GitLab remote)"
        )

    # ------------------------------------------------------------------
    # Input source: file / stdin / project
    # ------------------------------------------------------------------
    content: Optional[str] = None
    source_desc: str
    endpoint_label: str

    if file_path is not None:
        # POST endpoint: validate provided content
        if file_path == "-":
            if sys.stdin.isatty():
                raise click.ClickException(
                    "no input piped to stdin; use --file <path> or pipe content "
                    "(e.g. `cat .gitlab-ci.yml | gitlab-toolbox ci validate -f -`)"
                )
            content = sys.stdin.read()
            if not content:
                raise click.ClickException(
                    "no input piped to stdin; use --file <path> or pipe content "
                    "(e.g. `cat .gitlab-ci.yml | gitlab-toolbox ci validate -f -`)"
                )
            source_desc = "<stdin>"
        else:
            p = Path(file_path)
            if not p.exists() or not p.is_file():
                raise click.ClickException(f"file not found: {file_path}")
            try:
                content = p.read_text()
            except OSError as e:
                raise click.ClickException(f"could not read {file_path}: {e}")
            source_desc = str(p)
        endpoint_label = "POST /api/v4/projects/{}/ci/lint".format(project.replace("/", "%2F"))
    else:
        # GET endpoint: validate the project's .gitlab-ci.yml
        source_desc = f"{project} .gitlab-ci.yml"
        endpoint_label = "GET /api/v4/projects/{}/ci/lint".format(project.replace("/", "%2F"))

    # ------------------------------------------------------------------
    # Call the API
    # ------------------------------------------------------------------
    try:
        if content is not None:
            result = CILintAPI.lint_content(
                project,
                content,
                ref=ref,
                dry_run=dry_run,
                include_jobs=include_jobs,
            )
        else:
            result = CILintAPI.lint_project(
                project,
                content_ref=ref,
                dry_run=dry_run,
                dry_run_ref=dry_run_ref or ref,
                include_jobs=include_jobs,
            )
    except Exception as e:
        console.print(f"[red]CI lint request failed:[/red] {e}")
        sys.exit(1)

    if result is None:
        console.print("[red]CI lint request returned an unexpected payload.[/red]")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Render output
    # ------------------------------------------------------------------
    if output_format == "json":
        raw = {
            "valid": result.valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "merged_yaml": result.merged_yaml,
            "includes": result.includes,
            "jobs": [
                {
                    "name": j.name,
                    "stage": j.stage,
                    "before_script": j.before_script,
                    "script": j.script,
                    "after_script": j.after_script,
                    "tag_list": j.tag_list,
                    "only": j.only,
                    "except": j.except_config,
                    "environment": j.environment,
                    "when": j.when,
                    "allow_failure": j.allow_failure,
                    "needs": j.needs,
                }
                for j in result.jobs
            ],
        }
        print(json.dumps(raw, indent=2))
    else:
        DisplayFormatter.display_ci_lint_result(
            result,
            project=project,
            endpoint=endpoint_label,
            source=source_desc,
            ref=ref or "",
            dry_run=dry_run,
            include_jobs=include_jobs,
        )

    # ------------------------------------------------------------------
    # Exit codes
    # ------------------------------------------------------------------
    # 0  = valid, no warnings (or warnings allowed)
    # 1  = invalid or API error
    # 2  = valid with warnings + --fail-on-warning
    if result.has_errors:
        sys.exit(1)
    if result.has_warnings and fail_on_warning:
        sys.exit(2)
    sys.exit(0)
