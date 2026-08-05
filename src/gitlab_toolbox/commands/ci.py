"""CI command implementation.

Provides ``gitlab-toolbox ci validate`` which wraps the GitLab CI Lint API
(https://docs.gitlab.com/api/lint/).

Three input modes are supported:

* ``-f PATH``     — validate a local YAML file (POST endpoint).
* ``-f -``        — validate YAML piped through stdin (POST endpoint).
* ``-f`` omitted  — validate the project's own ``.gitlab-ci.yml``
                    (GET endpoint).

Variables can be supplied via ``--variables-env`` (repeatable) to
simulate a pipeline run with specific CI/CD variables. Because the
GitLab CI Lint API does not accept a top-level ``variables`` request
parameter, the supplied variables are injected into the YAML's
top-level ``variables:`` block before POSTing.
"""

import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import click
from rich.console import Console

from ..api.ci_lint import CILintAPI
from ..api.client import GitLabClient
from ..formatters import DisplayFormatter
from ..formatters import json_output as json

# Console for status/info messages (goes to stderr)
console = Console(file=sys.stderr)


def _parse_variables_env(
    ctx: click.Context, param: click.Parameter, values: Tuple[str, ...]
) -> Dict[str, str]:
    """Parse ``--variables-env KEY:VALUE`` pairs into a dict.

    Each occurrence of the flag may contain a single ``KEY:VALUE``
    pair or multiple pairs separated by commas. Repeatable flags
    accumulate. The first ``:`` separates the key from the value, so
    values may themselves contain colons (e.g. URLs).

    Args:
        ctx: Click context (unused).
        param: Click parameter (unused).
        values: All raw values from the command line, in order.

    Returns:
        Mapping of variable names to their string values. Later
        occurrences override earlier ones for the same key.

    Raises:
        click.BadParameter: If a value is missing a colon separator
            or the key portion is empty.
    """
    result: Dict[str, str] = {}
    for raw in values or ():
        # Support comma-separated lists per flag, like ``glab ci run``.
        for spec in raw.split(","):
            spec = spec.strip()
            if not spec:
                continue
            if ":" not in spec:
                raise click.BadParameter(
                    f"expected KEY:VALUE, got {spec!r} " "(missing ':' between key and value)"
                )
            key, _, value = spec.partition(":")
            key = key.strip()
            if not key:
                raise click.BadParameter(f"empty variable key in {spec!r}")
            result[key] = value
    return result


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
        "POST: ref context for include resolution and pipeline simulation. "
        "GET: ref to read .gitlab-ci.yml from (content_ref); also reused "
        "as the simulation context (dry_run_ref) when --dry-run-ref is "
        "not provided. Defaults to the project's default branch."
    ),
)
@click.option(
    "--dry-run-ref",
    "dry_run_ref",
    default=None,
    help=(
        "Git ref (branch or tag) used as the pipeline-creation simulation "
        "context. Maps to GET: dry_run_ref. For POST, --ref is reused as "
        "the simulation context. Defaults to the value of --ref."
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
@click.option(
    "-V",
    "--variables-env",
    "variables_env",
    multiple=True,
    callback=_parse_variables_env,
    metavar="KEY:VALUE",
    help=(
        "Pass variables to the lint simulation in KEY:VALUE format "
        "(matching ``glab ci run --variables-env``). Repeatable, and "
        "multiple KEY:VALUE pairs may be passed in a single flag "
        "separated by commas. Injected into the YAML's top-level "
        "``variables:`` block; provided values override same-named "
        "entries already defined at the YAML top level. Without "
        "``-f``, the project's ``.gitlab-ci.yml`` is fetched and the "
        "variables are merged into it before linting. Has no effect "
        "on static-only checks — it only matters when ``dry_run`` is "
        "true, which is always the case here."
    ),
)
def validate_ci(
    file_path: Optional[str],
    ref: Optional[str],
    dry_run_ref: Optional[str],
    include_jobs: bool,
    output_format: str,
    fail_on_warning: bool,
    variables_env: Dict[str, str],
):
    """Validate a GitLab CI/CD configuration using the project CI Lint API.

    A pipeline-creation simulation (``dry_run=true``) is always requested
    so that ``--ref`` is honored on POST and local includes are resolved
    against the supplied ref (instead of the project's default branch).
    Validation is therefore always a real pipeline-creation simulation,
    not a static-only check.

    Mandatory fields by endpoint:

      POST /projects/:id/ci/lint  -> content (provided via --file / stdin)

      GET  /projects/:id/ci/lint  -> project context only

    \b
    Examples:
      # Lint a local .gitlab-ci.yml (includes resolved against default branch)
      gitlab-toolbox ci validate --project group/project -f .gitlab-ci.yml

      # Lint YAML piped through stdin
      cat .gitlab-ci.yml | gitlab-toolbox ci validate --project group/project -f -

      # Lint the project's own .gitlab-ci.yml on its default branch
      gitlab-toolbox ci validate --project group/project

      # Validate a feature branch's .gitlab-ci.yml + its local includes
      # against the same branch
      gitlab-toolbox ci validate --project group/project -f .gitlab-ci.yml \\
          --ref feature/login --include-jobs

      # Override the simulation ref independently of the YAML ref
      gitlab-toolbox ci validate --project group/project --ref feature/login \\
          --dry-run-ref main

      # Simulate the pipeline with extra variables (overrides existing
      # top-level YAML variables of the same name)
      gitlab-toolbox ci validate --project group/project -f .gitlab-ci.yml \\
          --variables-env ENGINE_CI_PIPELINES_REF:main \\
          --variables-env RUN_TESTING:0

      # Same, but lint the project's stored .gitlab-ci.yml (the file
      # is fetched and merged with the variables locally)
      gitlab-toolbox ci validate --project group/project \\
          --variables-env DEPLOY_ENV:staging
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
        # GET endpoint (no variables) or POST-after-fetch (with variables).
        # The wrapper handles the variable-injection fallback transparently.
        source_desc = f"{project} .gitlab-ci.yml"
        endpoint_label = "GET /api/v4/projects/{}/ci/lint".format(project.replace("/", "%2F"))

    # ------------------------------------------------------------------
    # Call the API. The wrapper resolves the project path to a numeric
    # ID internally because the CI Lint endpoints require the numeric
    # ID in their :id path segment.
    #
    # ``dry_run`` is always True: the pipeline-creation simulation is
    # required for --ref to be honored on POST and for local includes to
    # be resolved against the supplied ref instead of the default branch.
    #
    # ``variables`` are injected into the YAML's top-level
    # ``variables:`` block (see ``api/ci_lint.py``) since the CI Lint
    # API does not accept variables as a request parameter.
    # ------------------------------------------------------------------
    try:
        if content is not None:
            result = CILintAPI.lint_content(
                project,
                content,
                ref=ref,
                dry_run=True,
                include_jobs=include_jobs,
                variables=variables_env or None,
            )
        else:
            result = CILintAPI.lint_project(
                project,
                content_ref=ref,
                dry_run=True,
                dry_run_ref=dry_run_ref or ref,
                include_jobs=include_jobs,
                variables=variables_env or None,
            )
    except Exception as e:
        console.print(f"[red]CI lint request failed:[/red] {e}")
        sys.exit(1)

    if result is None:
        # The wrapper already printed "Project not found" for resolution
        # failures; for any other unexpected payload, exit non-zero.
        sys.exit(1)

    # When variables were injected via the file-fetch fallback, the
    # real API call was POST even though we initially labelled the
    # endpoint as GET. Correct the label so the panel reflects what
    # actually happened.
    if variables_env and content is None:
        endpoint_label = "POST /api/v4/projects/{}/ci/lint".format(project.replace("/", "%2F"))

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
        if variables_env:
            raw["variables"] = variables_env
        print(json.dumps(raw, indent=2))
    else:
        DisplayFormatter.display_ci_lint_result(
            result,
            project=project,
            endpoint=endpoint_label,
            source=source_desc,
            ref=ref or "",
            include_jobs=include_jobs,
            variables=variables_env or None,
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


# Register the CI/CD configuration inventory subcommands (variables, tokens,
# inventory). Imported at the bottom to avoid a circular import: ci_config
# imports nothing from this module, but keeps the registration next to the
# group it extends.
from .ci_config import register as _register_ci_config  # noqa: E402

_register_ci_config(ci_cli)
