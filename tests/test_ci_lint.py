"""Tests for the ``ci validate`` command and the underlying CI Lint API wrapper."""

import json

from click.testing import CliRunner

from gitlab_toolbox.api.ci_lint import CILintAPI, _merge_variables_into_yaml
from gitlab_toolbox.api.client import GitLabClient
from gitlab_toolbox.cli import cli
from gitlab_toolbox.commands.ci import _parse_variables_env
from gitlab_toolbox.models import CILintResult, LintJob

# Numeric project ID used by all fake project-lookup responses below.
FAKE_PROJECT_ID = 42


# ----------------------------------------------------------------------
# Data model
# ----------------------------------------------------------------------
def test_lint_job_defaults():
    """LintJob should tolerate missing optional fields."""
    job = LintJob(name="build")
    assert job.name == "build"
    assert job.stage is None
    assert job.script == []
    assert job.allow_failure is False
    assert job.tag_list == []


def test_ci_lint_result_helpers():
    """CILintResult exposes has_errors / has_warnings consistently."""
    valid_clean = CILintResult(valid=True)
    assert not valid_clean.has_errors
    assert not valid_clean.has_warnings

    valid_with_warning = CILintResult(valid=True, warnings=["be careful"])
    assert not valid_with_warning.has_errors
    assert valid_with_warning.has_warnings

    invalid = CILintResult(valid=False, errors=["bad"])
    assert invalid.has_errors

    # ``valid`` is the source of truth: even without errors, valid=False means
    # the lint failed.
    invalid_no_errors = CILintResult(valid=False)
    assert invalid_no_errors.has_errors


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def make_fake_request(lint_response):
    """Return a ``_run_api_request`` stub that resolves the project then lints.

    The stub dispatches on the endpoint path: any endpoint that ends with
    ``/ci/lint`` returns ``lint_response``; all others (the project lookup)
    return ``{"id": FAKE_PROJECT_ID}``. URL-suffix dispatch is robust to
    multiple ``runner.invoke()`` calls within a single test, unlike a
    call-count approach.

    Args:
        lint_response: Mapping returned for the lint call(s).

    Returns:
        Tuple of (calls_ref, fake_request). ``calls_ref`` is a list to which
        ``(endpoint, params, method)`` tuples are appended as the stub runs.
    """
    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        if endpoint.endswith("/ci/lint"):
            return lint_response
        return {"id": FAKE_PROJECT_ID}

    return calls, fake_request


def make_fake_request_optional(lint_response):
    """Same as :func:`make_fake_request` but stubs ``_run_api_request_optional``.

    Used because :func:`CILintAPI._resolve_project_id` calls the optional
    variant (so 404 returns ``None`` instead of raising).
    """
    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        if endpoint.endswith("/ci/lint"):
            return lint_response
        return {"id": FAKE_PROJECT_ID}

    return calls, fake_request


# ----------------------------------------------------------------------
# API wrapper
# ----------------------------------------------------------------------
def test_resolve_project_id_skips_lookup_for_numeric_id(monkeypatch):
    """A numeric input must skip the project lookup entirely."""
    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"id": 999}

    monkeypatch.setattr(GitLabClient, "_run_api_request_optional", fake_request)

    assert CILintAPI._resolve_project_id("12345") == 12345
    assert calls == []  # No HTTP call was made.


def test_resolve_project_id_looks_up_path(monkeypatch):
    """A non-numeric project path triggers a lookup and returns the ID."""
    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"id": 777}

    monkeypatch.setattr(GitLabClient, "_run_api_request_optional", fake_request)

    assert CILintAPI._resolve_project_id("group/project") == 777
    assert calls == [("projects/group%2Fproject", None, "GET")]


def test_resolve_project_id_returns_none_on_404(monkeypatch):
    """A 404 from the lookup must surface as ``None`` (not raise)."""

    def fake_request(endpoint, params=None, method="GET"):
        return None

    monkeypatch.setattr(GitLabClient, "_run_api_request_optional", fake_request)

    assert CILintAPI._resolve_project_id("missing/proj") is None


def test_lint_content_posts_required_payload(monkeypatch):
    """lint_content POSTs ``content`` (mandatory) plus the optional flags."""
    lint_response = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "merged_yaml": "stages: []\n",
        "includes": [],
    }
    calls, fake_request = make_fake_request(lint_response)
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    result = CILintAPI.lint_content(
        "group/project",
        "stages: []\n",
        ref="main",
        dry_run=True,
        include_jobs=True,
    )

    assert isinstance(result, CILintResult)
    assert result.valid is True
    assert result.errors == []
    assert result.merged_yaml == "stages: []\n"

    # The wrapper first resolves the path to a numeric ID, then POSTs
    # against the lint endpoint.
    assert calls == [
        (
            "projects/group%2Fproject",
            None,
            "GET",
        ),
        (
            f"projects/{FAKE_PROJECT_ID}/ci/lint",
            {
                "content": "stages: []\n",
                "dry_run": True,
                "include_jobs": True,
                "ref": "main",
            },
            "POST",
        ),
    ]


def test_lint_content_omits_ref_when_not_provided(monkeypatch):
    """The ``ref`` key must NOT be sent when the user did not provide one."""
    calls, fake_request = make_fake_request({"valid": True, "errors": [], "warnings": []})
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    CILintAPI.lint_content(
        "group/project",
        "foo:\n  script: echo 1\n",
        dry_run=True,
    )

    # Skip the project-lookup call; assert on the lint call only.
    lint_call = calls[1]
    assert lint_call[1] == {
        "content": "foo:\n  script: echo 1\n",
        "dry_run": True,
        "include_jobs": False,
    }
    assert "ref" not in lint_call[1]
    assert lint_call[2] == "POST"


def test_lint_content_skips_lookup_when_project_id_is_numeric(monkeypatch):
    """A numeric project ID must be passed straight through to the lint URL."""
    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"valid": True, "errors": [], "warnings": []}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    result = CILintAPI.lint_content("4242", "build:\n  script: echo 1\n", dry_run=True)

    assert result is not None
    # Only the lint call should happen; no project lookup.
    assert calls == [
        (
            "projects/4242/ci/lint",
            {
                "content": "build:\n  script: echo 1\n",
                "dry_run": True,
                "include_jobs": False,
            },
            "POST",
        )
    ]


def test_lint_content_returns_none_when_project_not_found(monkeypatch):
    """A missing project must yield ``None`` (and a clear error message)."""
    captured = []

    def fake_request(endpoint, params=None, method="GET"):
        captured.append(endpoint)
        return None

    monkeypatch.setattr(GitLabClient, "_run_api_request_optional", fake_request)

    # Suppress the console print so the test output stays clean.
    import io as _io

    from rich.console import Console

    from gitlab_toolbox.api import ci_lint as ci_lint_module

    ci_lint_module.console = Console(file=_io.StringIO())

    result = CILintAPI.lint_content("missing/proj", "build:\n  script: echo 1\n")

    assert result is None
    assert captured == ["projects/missing%2Fproj"]


def test_lint_project_uses_get_with_query_params(monkeypatch):
    """lint_project calls GET with query parameters and the numeric ID."""
    lint_response = {
        "valid": False,
        "errors": ["jobs config should contain at least one visible job"],
        "warnings": [],
        "merged_yaml": "---\n",
    }
    calls, fake_request = make_fake_request(lint_response)
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    result = CILintAPI.lint_project(
        "group/project",
        content_ref="abc1234",
        dry_run=True,
        dry_run_ref="main",
        include_jobs=True,
    )

    assert isinstance(result, CILintResult)
    assert result.valid is False
    assert "jobs config should contain" in result.errors[0]

    # Project lookup, then lint GET.
    assert calls == [
        ("projects/group%2Fproject", None, "GET"),
        (
            f"projects/{FAKE_PROJECT_ID}/ci/lint",
            {
                "dry_run": "true",
                "include_jobs": "true",
                "content_ref": "abc1234",
                "dry_run_ref": "main",
            },
            "GET",
        ),
    ]


def test_lint_project_minimal_request(monkeypatch):
    """GET with no optional args still works (server-side default branch)."""
    calls, fake_request = make_fake_request({"valid": True, "errors": [], "warnings": []})
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    CILintAPI.lint_project("group/project", dry_run=True)

    assert calls[1] == (
        f"projects/{FAKE_PROJECT_ID}/ci/lint",
        {"dry_run": "true", "include_jobs": "false"},
        "GET",
    )


def test_parse_result_parses_jobs(monkeypatch):
    """_parse_result must extract job entries into LintJob objects."""
    lint_response = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "merged_yaml": "---\n",
        "includes": [{"type": "local", "location": "ci/build.yml"}],
        "jobs": [
            {
                "name": "test",
                "stage": "test",
                "script": ["pytest"],
                "before_script": [],
                "after_script": [],
                "tag_list": ["docker"],
                "only": {"refs": ["main"]},
                "except": None,
                "environment": "test",
                "when": "on_success",
                "allow_failure": False,
                "needs": [],
            }
        ],
    }
    _, fake_request = make_fake_request(lint_response)
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    result = CILintAPI.lint_content("group/project", "test:\n  script: pytest\n", include_jobs=True)

    assert result is not None
    assert len(result.includes) == 1
    assert result.includes[0]["location"] == "ci/build.yml"
    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert isinstance(job, LintJob)
    assert job.name == "test"
    assert job.stage == "test"
    assert job.script == ["pytest"]
    assert job.tag_list == ["docker"]
    assert job.only == {"refs": ["main"]}
    assert job.except_config is None


def test_parse_result_handles_non_dict_payload():
    """Defensive: a non-mapping payload should return None instead of crashing."""
    assert CILintAPI._parse_result([]) is None
    assert CILintAPI._parse_result("oops") is None
    assert CILintAPI._parse_result(None) is None


# ----------------------------------------------------------------------
# CLI: command surface
# ----------------------------------------------------------------------
def _set_repo(monkeypatch, project="group/project"):
    """Helper: pretend a project context has been configured."""
    GitLabClient.set_repo_path(project)


def test_ci_group_is_registered():
    """The ``ci`` group should appear in the top-level help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "ci" in result.output


def test_ci_validate_help_lists_all_options():
    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "--help"])
    assert result.exit_code == 0
    out = result.output
    assert "--file" in out
    assert "--ref" in out
    assert "--dry-run-ref" in out
    # --dry-run/--no-dry-run is intentionally absent: validation must
    # always perform a real pipeline-creation simulation. (Check only
    # the option names -- otherwise --dry-run-ref matches as a
    # substring, and the wrapped help text would also match.)
    options_section = out.split("Options:", 1)[-1]
    option_lines = [
        line.strip().split()[0] for line in options_section.splitlines() if line.startswith("  --")
    ]
    assert option_lines, f"no options found in help: {out!r}"
    assert "--dry-run" not in option_lines
    assert "--no-dry-run" not in option_lines
    assert "--include-jobs" in out
    assert "--no-include-jobs" in out
    assert "--format" in out
    assert "--fail-on-warning" in out
    assert "POST" in out
    assert "GET" in out


def test_ci_validate_requires_project_context():
    """No project context -> a clear error and exit code != 0."""
    GitLabClient.set_repo_path(None)
    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "--project is required" in result.output


def test_ci_validate_lints_local_file(monkeypatch, tmp_path):
    """-f PATH must POST the file content against the numeric project ID."""
    _set_repo(monkeypatch)

    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo hi\n")

    calls, fake_request = make_fake_request(
        {"valid": True, "errors": [], "warnings": [], "merged_yaml": "build: ..."}
    )
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "-f", str(yaml_file)])

    assert result.exit_code == 0, result.output
    # Lookup, then lint.
    assert calls[0] == ("projects/group%2Fproject", None, "GET")
    assert calls[1] == (
        f"projects/{FAKE_PROJECT_ID}/ci/lint",
        {
            "content": "build:\n  script: echo hi\n",
            "dry_run": True,
            "include_jobs": False,
        },
        "POST",
    )


def test_ci_validate_reads_stdin_when_dash(monkeypatch):
    """-f - must read from stdin and POST its contents against the numeric ID."""
    _set_repo(monkeypatch)

    calls, fake_request = make_fake_request({"valid": True, "errors": [], "warnings": []})
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ci", "validate", "-f", "-"],
        input="deploy:\n  script: echo ok\n",
    )

    assert result.exit_code == 0, result.output
    assert calls[1][1]["content"] == "deploy:\n  script: echo ok\n"
    assert calls[1][2] == "POST"
    # Confirm the lint URL uses the numeric ID.
    assert calls[1][0] == f"projects/{FAKE_PROJECT_ID}/ci/lint"


def test_ci_validate_errors_on_missing_file(monkeypatch, tmp_path):
    """A non-existent path must produce a clear error and a non-zero exit."""
    _set_repo(monkeypatch)
    missing = tmp_path / "does-not-exist.yml"

    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "-f", str(missing)])

    assert result.exit_code != 0
    assert "file not found" in result.output


def test_ci_validate_errors_on_tty_stdin(monkeypatch):
    """-f - with no piped data (TTY) must not hang and must error out."""
    _set_repo(monkeypatch)

    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "-f", "-"])

    assert result.exit_code != 0
    assert "no input piped to stdin" in result.output


def test_ci_validate_uses_get_when_no_file(monkeypatch):
    """No -f -> GET endpoint against the numeric ID, content_ref from --ref."""
    _set_repo(monkeypatch)

    calls, fake_request = make_fake_request({"valid": True, "errors": [], "warnings": []})
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "--ref", "feature/x"])

    assert result.exit_code == 0, result.output
    assert calls[0] == ("projects/group%2Fproject", None, "GET")
    assert calls[1] == (
        f"projects/{FAKE_PROJECT_ID}/ci/lint",
        {
            "dry_run": "true",
            "include_jobs": "false",
            "content_ref": "feature/x",
            # --dry-run-ref defaults to --ref
            "dry_run_ref": "feature/x",
        },
        "GET",
    )


def test_ci_validate_dry_run_is_mandatory(monkeypatch, tmp_path):
    """The CLI must always request ``dry_run=true`` so --ref is honored on POST."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    calls, fake_request = make_fake_request({"valid": True, "errors": [], "warnings": []})
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    runner.invoke(
        cli,
        [
            "ci",
            "validate",
            "-f",
            str(yaml_file),
            "--ref",
            "feature/ref-honored",
        ],
    )

    # Validation must always enable the simulation so the GitLab API
    # resolves local includes against --ref. Otherwise we would silently
    # validate against the default branch.
    assert calls[1][1]["dry_run"] is True
    assert calls[1][1]["ref"] == "feature/ref-honored"


def test_ci_validate_rejects_no_dry_run_flag(monkeypatch, tmp_path):
    """The CLI must not expose --no-dry-run: validation is always real."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "-f", str(yaml_file), "--no-dry-run"])

    assert result.exit_code != 0
    assert "no such option" in result.output.lower()


def test_ci_validate_dry_run_ref_explicit(monkeypatch):
    """--dry-run-ref must take precedence over --ref when provided."""
    _set_repo(monkeypatch)

    calls, fake_request = make_fake_request({"valid": True, "errors": [], "warnings": []})
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ci", "validate", "--ref", "feature/read", "--dry-run-ref", "main"],
    )

    assert result.exit_code == 0, result.output
    assert calls[1][1]["content_ref"] == "feature/read"
    assert calls[1][1]["dry_run_ref"] == "main"


def test_ci_validate_json_output(monkeypatch, tmp_path):
    """--format json must emit the raw API shape."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    _, fake_request = make_fake_request(
        {
            "valid": True,
            "errors": [],
            "warnings": ["deprecated keyword"],
            "merged_yaml": "build:\n  script: echo 1\n",
            "includes": [],
            "jobs": [],
        }
    )
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "-f", str(yaml_file), "--format", "json"])

    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert parsed["valid"] is True
    assert parsed["warnings"] == ["deprecated keyword"]
    assert parsed["jobs"] == []


def test_ci_validate_exit_code_on_errors(monkeypatch, tmp_path):
    """Invalid YAML (errors present) -> exit 1."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    _, fake_request = make_fake_request(
        {
            "valid": False,
            "errors": ["jobs config should contain at least one visible job"],
            "warnings": [],
        }
    )
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "-f", str(yaml_file)])

    assert result.exit_code == 1


def test_ci_validate_fail_on_warning(monkeypatch, tmp_path):
    """--fail-on-warning must exit 2 when warnings are present but valid."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    _, fake_request = make_fake_request({"valid": True, "errors": [], "warnings": ["deprecated"]})
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()

    # Without the flag: exit 0 (warnings allowed).
    res_ok = runner.invoke(cli, ["ci", "validate", "-f", str(yaml_file)])
    assert res_ok.exit_code == 0

    # With the flag: exit 2.
    res_strict = runner.invoke(cli, ["ci", "validate", "-f", str(yaml_file), "--fail-on-warning"])
    assert res_strict.exit_code == 2


def test_ci_validate_include_jobs(monkeypatch, tmp_path):
    """--include-jobs must propagate to the POST body."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    calls, fake_request = make_fake_request({"valid": True, "errors": [], "warnings": []})
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    runner.invoke(cli, ["ci", "validate", "-f", str(yaml_file), "--include-jobs"])

    assert calls[1][1]["include_jobs"] is True


def test_ci_validate_unknown_project_exits_with_error(monkeypatch, tmp_path):
    """If the project path can't be resolved, exit non-zero with a clear error."""
    _set_repo(monkeypatch, project="nonexistent/project")
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    # The lookup returns None -> the wrapper short-circuits before lint.
    monkeypatch.setattr(GitLabClient, "_run_api_request_optional", lambda *a, **kw: None)

    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "-f", str(yaml_file)])

    assert result.exit_code != 0


def test_ci_validate_numeric_project_id_skips_lookup(monkeypatch, tmp_path):
    """A numeric --project must be passed straight through to the lint URL."""
    _set_repo(monkeypatch, project="4242")
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"valid": True, "errors": [], "warnings": []}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "-f", str(yaml_file)])

    assert result.exit_code == 0, result.output
    # Only one HTTP call: the lint call. No project lookup.
    assert calls == [
        (
            "projects/4242/ci/lint",
            {
                "content": "build:\n  script: echo 1\n",
                "dry_run": True,
                "include_jobs": False,
            },
            "POST",
        )
    ]


# ----------------------------------------------------------------------
# Variables: CLI parser
# ----------------------------------------------------------------------
def test_parse_variables_env_single_pair():
    """A single KEY:VALUE yields a one-entry dict."""
    parsed = _parse_variables_env(None, None, ("ENGINE:on",))
    assert parsed == {"ENGINE": "on"}


def test_parse_variables_env_multiple_flags():
    """Repeatable flags accumulate; later values override earlier ones."""
    parsed = _parse_variables_env(None, None, ("ENGINE:on", "RUN_TESTING:0", "ENGINE:off"))
    assert parsed == {"ENGINE": "off", "RUN_TESTING": "0"}


def test_parse_variables_env_comma_separated():
    """A single flag may carry multiple comma-separated pairs."""
    parsed = _parse_variables_env(None, None, ("A:1,B:2,C:3",))
    assert parsed == {"A": "1", "B": "2", "C": "3"}


def test_parse_variables_env_value_may_contain_colons():
    """Only the first ':' splits key from value (URLs etc. work)."""
    parsed = _parse_variables_env(None, None, ("URL:http://example.com:8080/path",))
    assert parsed == {"URL": "http://example.com:8080/path"}


def test_parse_variables_env_empty_value_allowed():
    """An empty value (KEY:) is allowed and stored as the empty string."""
    parsed = _parse_variables_env(None, None, ("EMPTY:",))
    assert parsed == {"EMPTY": ""}


def test_parse_variables_env_empty_input():
    """No flags -> empty dict."""
    assert _parse_variables_env(None, None, ()) == {}


def test_parse_variables_env_rejects_missing_colon():
    """A value without ':' is rejected with a clear message."""
    import click

    with __import__("pytest").raises(click.BadParameter) as exc_info:
        _parse_variables_env(None, None, ("nocolon",))
    assert "missing ':'" in str(exc_info.value)


def test_parse_variables_env_rejects_empty_key():
    """An empty key (' :value' or ':value') is rejected."""
    import click

    with __import__("pytest").raises(click.BadParameter) as exc_info:
        _parse_variables_env(None, None, (":value",))
    assert "empty variable key" in str(exc_info.value)


def test_parse_variables_env_strips_whitespace():
    """Surrounding whitespace around the key is trimmed."""
    parsed = _parse_variables_env(None, None, ("  KEY  :value",))
    assert parsed == {"KEY": "value"}


# ----------------------------------------------------------------------
# Variables: YAML merge helper
# ----------------------------------------------------------------------
def test_merge_variables_into_yaml_empty_returns_unchanged():
    """Empty mapping short-circuits: input is returned verbatim."""
    src = "build:\n  script: echo hi\n"
    assert _merge_variables_into_yaml(src, {}) == src
    assert _merge_variables_into_yaml(src, None) == src


def test_merge_variables_into_yaml_adds_block_when_absent():
    """Without an existing ``variables:`` block, a new one is added."""
    import yaml as _yaml

    src = "build:\n  script: echo hi\n"
    out = _merge_variables_into_yaml(src, {"A": "1", "B": "2"})
    parsed = _yaml.safe_load(out)
    assert parsed["variables"] == {"A": "1", "B": "2"}
    assert parsed["build"] == {"script": "echo hi"}


def test_merge_variables_into_yaml_overrides_existing():
    """Provided values override existing same-named entries."""
    import yaml as _yaml

    src = (
        "variables:\n"
        "  DEPLOY_ENV: production\n"
        "  REGION: us-east-1\n"
        "build:\n"
        "  script: echo hi\n"
    )
    out = _merge_variables_into_yaml(src, {"DEPLOY_ENV": "staging", "NEW": "x"})
    parsed = _yaml.safe_load(out)
    assert parsed["variables"]["DEPLOY_ENV"] == "staging"
    assert parsed["variables"]["REGION"] == "us-east-1"
    assert parsed["variables"]["NEW"] == "x"


def test_merge_variables_into_yaml_preserves_long_form_entries():
    """Long-form variables (with ``value:``, ``description:``) are preserved."""
    import yaml as _yaml

    src = (
        "variables:\n"
        "  DEPLOY_NOTE:\n"
        "    description: A note\n"
        "    value: deploy-me\n"
        "build:\n"
        "  script: echo hi\n"
    )
    out = _merge_variables_into_yaml(src, {"NEW": "x"})
    parsed = _yaml.safe_load(out)
    assert parsed["variables"]["DEPLOY_NOTE"] == {
        "description": "A note",
        "value": "deploy-me",
    }
    assert parsed["variables"]["NEW"] == "x"


def test_merge_variables_into_yaml_overrides_long_form_entry():
    """A string override replaces a long-form entry for the same key."""
    import yaml as _yaml

    src = "variables:\n" "  DEPLOY_NOTE:\n" "    description: A note\n" "    value: deploy-me\n"
    out = _merge_variables_into_yaml(src, {"DEPLOY_NOTE": "simple"})
    parsed = _yaml.safe_load(out)
    assert parsed["variables"]["DEPLOY_NOTE"] == "simple"


def test_merge_variables_into_yaml_unparseable_returns_original():
    """If the YAML can't be parsed, the original content is returned untouched."""
    src = "build:\n  script: [unclosed"
    out = _merge_variables_into_yaml(src, {"X": "y"})
    assert out == src


def test_merge_variables_into_yaml_non_mapping_top_level_returns_original():
    """A non-mapping top-level (e.g. bare list) returns the original."""
    src = "- one\n- two\n"
    out = _merge_variables_into_yaml(src, {"X": "y"})
    assert out == src


# ----------------------------------------------------------------------
# Variables: API wrapper integration
# ----------------------------------------------------------------------
def test_lint_content_injects_variables_into_yaml(monkeypatch):
    """Variables passed to ``lint_content`` are merged into the POSTed YAML."""
    lint_response = {"valid": True, "errors": [], "warnings": []}
    calls, fake_request = make_fake_request(lint_response)
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    import yaml as _yaml

    result = CILintAPI.lint_content(
        "group/project",
        "build:\n  script: echo hi\n",
        dry_run=True,
        variables={"DEPLOY_ENV": "staging", "EXTRA": "x"},
    )

    assert isinstance(result, CILintResult)
    body = calls[1][1]
    parsed = _yaml.safe_load(body["content"])
    assert parsed["variables"] == {"DEPLOY_ENV": "staging", "EXTRA": "x"}


def test_lint_content_without_variables_keeps_yaml_intact(monkeypatch):
    """Without ``variables=``, the original content is sent unchanged."""
    lint_response = {"valid": True, "errors": [], "warnings": []}
    calls, fake_request = make_fake_request(lint_response)
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    src = "build:\n  script: echo hi\n"
    CILintAPI.lint_content("group/project", src, dry_run=True)

    assert calls[1][1]["content"] == src


def test_lint_project_with_variables_fetches_then_posts(monkeypatch):
    """Variables on ``lint_project`` force a fetch + POST instead of GET."""
    import yaml as _yaml

    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"valid": True, "errors": [], "warnings": []}

    def fake_request_optional(endpoint, params=None, method="GET"):
        return {"id": FAKE_PROJECT_ID}

    def fake_request_raw(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return "build:\n  script: echo hi\n"

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)
    monkeypatch.setattr(GitLabClient, "_run_api_request_optional", fake_request_optional)
    monkeypatch.setattr(GitLabClient, "_run_api_request_raw", fake_request_raw)

    result = CILintAPI.lint_project(
        "group/project",
        content_ref="feature/x",
        dry_run=True,
        variables={"DEPLOY_ENV": "staging"},
    )

    assert isinstance(result, CILintResult)

    # Project lookup (optional), file fetch (raw), then lint POST.
    raw_calls = [c for c in calls if c[0].endswith("/raw")]
    assert len(raw_calls) == 1
    assert raw_calls[0][0] == f"projects/{FAKE_PROJECT_ID}/repository/files/.gitlab-ci.yml/raw"
    assert raw_calls[0][1] == {"ref": "feature/x"}
    assert raw_calls[0][2] == "GET"

    lint_calls = [c for c in calls if c[0].endswith("/ci/lint")]
    assert len(lint_calls) == 1
    assert lint_calls[0][2] == "POST"
    parsed_body = _yaml.safe_load(lint_calls[0][1]["content"])
    assert parsed_body["variables"] == {"DEPLOY_ENV": "staging"}


def test_lint_project_without_variables_uses_get(monkeypatch):
    """No variables -> the original GET path is preserved (no fetch, no POST)."""
    lint_response = {"valid": True, "errors": [], "warnings": []}
    calls, fake_request = make_fake_request(lint_response)
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    CILintAPI.lint_project(
        "group/project",
        content_ref="feature/x",
        dry_run=True,
    )

    # The lint call must be GET (not POST) when no variables are provided.
    assert calls[1][2] == "GET"
    assert calls[1][0] == f"projects/{FAKE_PROJECT_ID}/ci/lint"


def test_fetch_project_ci_yml_returns_raw_content(monkeypatch):
    """The raw-files helper returns the response body as text."""
    monkeypatch.setattr(
        GitLabClient,
        "_run_api_request_optional",
        lambda endpoint, params=None, method="GET": {"id": FAKE_PROJECT_ID},
    )
    monkeypatch.setattr(
        GitLabClient,
        "_run_api_request_raw",
        lambda endpoint, params=None, method="GET": "build:\n  script: echo\n",
    )

    content = CILintAPI.fetch_project_ci_yml("group/project", ref="feature/y")
    assert content == "build:\n  script: echo\n"


def test_fetch_project_ci_yml_returns_none_on_404(monkeypatch):
    """A 404 from the raw endpoint surfaces as ``None``."""
    monkeypatch.setattr(
        GitLabClient,
        "_run_api_request_optional",
        lambda endpoint, params=None, method="GET": {"id": FAKE_PROJECT_ID},
    )
    monkeypatch.setattr(GitLabClient, "_run_api_request_raw", lambda *a, **kw: None)

    assert CILintAPI.fetch_project_ci_yml("group/project") is None


# ----------------------------------------------------------------------
# Variables: CLI integration
# ----------------------------------------------------------------------
def test_ci_validate_help_lists_variables_env_option():
    """``--variables-env`` must appear in the help output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "--help"])
    assert result.exit_code == 0
    out = result.output
    assert "--variables-env" in out
    assert "-V" in out


def test_ci_validate_variables_env_with_file(monkeypatch, tmp_path):
    """Variables provided alongside ``-f PATH`` are merged into the POST body."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo hi\n")

    import yaml as _yaml

    calls, fake_request = make_fake_request({"valid": True, "errors": [], "warnings": []})
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "ci",
            "validate",
            "-f",
            str(yaml_file),
            "--variables-env",
            "ENGINE_CI_PIPELINES_REF:main",
            "--variables-env",
            "RUN_TESTING:0",
        ],
    )

    assert result.exit_code == 0, result.output
    body = calls[1][1]
    assert "ref" not in body  # --ref not provided in this test
    parsed = _yaml.safe_load(body["content"])
    assert parsed["variables"] == {
        "ENGINE_CI_PIPELINES_REF": "main",
        "RUN_TESTING": "0",
    }


def test_ci_validate_variables_env_with_stdin(monkeypatch):
    """Variables provided alongside ``-f -`` are merged into the stdin content."""
    _set_repo(monkeypatch)

    import yaml as _yaml

    calls, fake_request = make_fake_request({"valid": True, "errors": [], "warnings": []})
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "ci",
            "validate",
            "-f",
            "-",
            "--variables-env",
            "A:1,B:2",
        ],
        input="build:\n  script: echo ok\n",
    )

    assert result.exit_code == 0, result.output
    parsed = _yaml.safe_load(calls[1][1]["content"])
    assert parsed["variables"] == {"A": "1", "B": "2"}


def test_ci_validate_variables_env_overrides_yaml_default(monkeypatch, tmp_path):
    """A CLI-provided variable with the same key as a YAML default overrides it."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text(
        "variables:\n" "  DEPLOY_ENV: production\n" "build:\n" "  script: echo hi\n"
    )

    import yaml as _yaml

    calls, fake_request = make_fake_request({"valid": True, "errors": [], "warnings": []})
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "ci",
            "validate",
            "-f",
            str(yaml_file),
            "--variables-env",
            "DEPLOY_ENV:staging",
        ],
    )

    assert result.exit_code == 0, result.output
    parsed = _yaml.safe_load(calls[1][1]["content"])
    assert parsed["variables"]["DEPLOY_ENV"] == "staging"


def test_ci_validate_variables_env_without_file_fetches_project(monkeypatch):
    """Without ``-f`` and with variables, the project's file is fetched + POSTed."""
    _set_repo(monkeypatch)

    import yaml as _yaml

    def fake_optional(endpoint, params=None, method="GET"):
        return {"id": FAKE_PROJECT_ID}

    monkeypatch.setattr(GitLabClient, "_run_api_request_optional", fake_optional)
    monkeypatch.setattr(
        GitLabClient,
        "_run_api_request_raw",
        lambda endpoint, params=None, method="GET": "build:\n  script: echo hi\n",
    )

    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"valid": True, "errors": [], "warnings": []}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "ci",
            "validate",
            "--variables-env",
            "DEPLOY_ENV:staging",
        ],
    )

    assert result.exit_code == 0, result.output

    # The lint call must be POST (because variables force the fetch + POST path).
    lint_calls = [c for c in calls if c[0].endswith("/ci/lint")]
    assert len(lint_calls) == 1
    assert lint_calls[0][2] == "POST"
    parsed = _yaml.safe_load(lint_calls[0][1]["content"])
    assert parsed["variables"] == {"DEPLOY_ENV": "staging"}


def test_ci_validate_variables_env_with_ref_fetches_at_ref(monkeypatch):
    """Variables + ``--ref`` (no ``-f``) fetch the file at the given ref."""
    _set_repo(monkeypatch)

    raw_params_seen = []

    def fake_raw(endpoint, params=None, method="GET"):
        raw_params_seen.append(params)
        return "build:\n  script: echo hi\n"

    monkeypatch.setattr(
        GitLabClient, "_run_api_request_optional", lambda *a, **kw: {"id": FAKE_PROJECT_ID}
    )
    monkeypatch.setattr(GitLabClient, "_run_api_request_raw", fake_raw)

    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"valid": True, "errors": [], "warnings": []}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "ci",
            "validate",
            "--ref",
            "feature/x",
            "--variables-env",
            "DEPLOY_ENV:staging",
        ],
    )

    assert result.exit_code == 0, result.output
    assert raw_params_seen == [{"ref": "feature/x"}]
    # The lint POST body's ref also carries the simulation ref (here = --ref).
    lint_calls = [c for c in calls if c[0].endswith("/ci/lint")]
    assert lint_calls[0][1]["ref"] == "feature/x"


def test_ci_validate_variables_env_invalid_format(monkeypatch, tmp_path):
    """A value without ``:`` is rejected with a clear error."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "ci",
            "validate",
            "-f",
            str(yaml_file),
            "--variables-env",
            "no-colon-here",
        ],
    )

    assert result.exit_code != 0
    assert "missing" in result.output.lower() and ":" in result.output


def test_ci_validate_variables_env_empty_key(monkeypatch, tmp_path):
    """An empty key is rejected with a clear error."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "ci",
            "validate",
            "-f",
            str(yaml_file),
            "--variables-env",
            ":value",
        ],
    )

    assert result.exit_code != 0
    assert "empty variable key" in result.output


def test_ci_validate_json_output_includes_variables(monkeypatch, tmp_path):
    """``--format json`` must include the variables mapping when provided."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    _, fake_request = make_fake_request({"valid": True, "errors": [], "warnings": []})
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "ci",
            "validate",
            "-f",
            str(yaml_file),
            "--variables-env",
            "DEPLOY_ENV:staging",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert parsed["variables"] == {"DEPLOY_ENV": "staging"}


def test_ci_validate_json_output_omits_variables_when_unset(monkeypatch, tmp_path):
    """Without variables, the JSON output must not include a ``variables`` key."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    _, fake_request = make_fake_request({"valid": True, "errors": [], "warnings": []})
    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ci", "validate", "-f", str(yaml_file), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert "variables" not in parsed
