"""Tests for the ``ci validate`` command and the underlying CI Lint API wrapper."""

import json

from click.testing import CliRunner

from gitlab_toolbox.api.ci_lint import CILintAPI
from gitlab_toolbox.api.client import GitLabClient
from gitlab_toolbox.cli import cli
from gitlab_toolbox.models import CILintResult, LintJob


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
# API wrapper
# ----------------------------------------------------------------------
def test_lint_content_posts_required_payload(monkeypatch):
    """lint_content POSTs ``content`` (mandatory) plus the optional flags."""
    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {
            "valid": True,
            "errors": [],
            "warnings": [],
            "merged_yaml": "stages: []\n",
            "includes": [],
        }

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

    assert calls == [
        (
            "projects/group%2Fproject/ci/lint",
            {
                "content": "stages: []\n",
                "dry_run": True,
                "include_jobs": True,
                "ref": "main",
            },
            "POST",
        )
    ]


def test_lint_content_omits_ref_when_not_provided(monkeypatch):
    """The ``ref`` key must NOT be sent when the user did not provide one."""
    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"valid": True, "errors": [], "warnings": []}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    CILintAPI.lint_content("group/project", "foo:\n  script: echo 1\n")

    assert calls[0][1] == {
        "content": "foo:\n  script: echo 1\n",
        "dry_run": False,
        "include_jobs": False,
    }
    assert "ref" not in calls[0][1]


def test_lint_project_uses_get_with_query_params(monkeypatch):
    """lint_project calls GET with query parameters."""
    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {
            "valid": False,
            "errors": ["jobs config should contain at least one visible job"],
            "warnings": [],
            "merged_yaml": "---\n",
        }

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

    assert calls == [
        (
            "projects/group%2Fproject/ci/lint",
            {
                "dry_run": "true",
                "include_jobs": "true",
                "content_ref": "abc1234",
                "dry_run_ref": "main",
            },
            "GET",
        )
    ]


def test_lint_project_minimal_request(monkeypatch):
    """GET with no optional args still works (server-side default branch)."""
    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"valid": True, "errors": [], "warnings": []}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    CILintAPI.lint_project("group/project")

    assert calls == [
        (
            "projects/group%2Fproject/ci/lint",
            {"dry_run": "false", "include_jobs": "false"},
            "GET",
        )
    ]


def test_parse_result_parses_jobs(monkeypatch):
    """_parse_result must extract job entries into LintJob objects."""

    def fake_request(endpoint, params=None, method="GET"):
        return {
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
    assert "--dry-run" in out
    assert "--no-dry-run" in out
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
    """-f PATH must POST the file content with the project endpoint."""
    _set_repo(monkeypatch)

    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo hi\n")

    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"valid": True, "errors": [], "warnings": [], "merged_yaml": "build: ..."}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "-f", str(yaml_file)])

    assert result.exit_code == 0, result.output
    assert calls == [
        (
            "projects/group%2Fproject/ci/lint",
            {
                "content": "build:\n  script: echo hi\n",
                "dry_run": False,
                "include_jobs": False,
            },
            "POST",
        )
    ]


def test_ci_validate_reads_stdin_when_dash(monkeypatch):
    """-f - must read from stdin and POST its contents."""
    _set_repo(monkeypatch)

    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"valid": True, "errors": [], "warnings": []}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ci", "validate", "-f", "-"],
        input="deploy:\n  script: echo ok\n",
    )

    assert result.exit_code == 0, result.output
    assert calls[0][1]["content"] == "deploy:\n  script: echo ok\n"
    assert calls[0][2] == "POST"


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
    # CliRunner mixes stdin/stdout; emulate a TTY-like stdin by leaving it empty
    # and explicitly NOT providing ``input``.
    result = runner.invoke(cli, ["ci", "validate", "-f", "-"])

    assert result.exit_code != 0
    assert "no input piped to stdin" in result.output


def test_ci_validate_uses_get_when_no_file(monkeypatch):
    """No -f -> GET endpoint, content_ref comes from --ref."""
    _set_repo(monkeypatch)

    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"valid": True, "errors": [], "warnings": []}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "--ref", "feature/x", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert calls == [
        (
            "projects/group%2Fproject/ci/lint",
            {
                "dry_run": "true",
                "include_jobs": "false",
                "content_ref": "feature/x",
                # --dry-run-ref defaults to --ref
                "dry_run_ref": "feature/x",
            },
            "GET",
        )
    ]


def test_ci_validate_dry_run_ref_explicit(monkeypatch):
    """--dry-run-ref must take precedence over --ref when provided."""
    _set_repo(monkeypatch)

    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"valid": True, "errors": [], "warnings": []}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["ci", "validate", "--ref", "feature/read", "--dry-run-ref", "main", "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    assert calls[0][1]["content_ref"] == "feature/read"
    assert calls[0][1]["dry_run_ref"] == "main"


def test_ci_validate_json_output(monkeypatch, tmp_path):
    """--format json must emit the raw API shape."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    def fake_request(endpoint, params=None, method="GET"):
        return {
            "valid": True,
            "errors": [],
            "warnings": ["deprecated keyword"],
            "merged_yaml": "build:\n  script: echo 1\n",
            "includes": [],
            "jobs": [],
        }

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

    def fake_request(endpoint, params=None, method="GET"):
        return {
            "valid": False,
            "errors": ["jobs config should contain at least one visible job"],
            "warnings": [],
        }

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    result = runner.invoke(cli, ["ci", "validate", "-f", str(yaml_file)])

    assert result.exit_code == 1


def test_ci_validate_fail_on_warning(monkeypatch, tmp_path):
    """--fail-on-warning must exit 2 when warnings are present but valid."""
    _set_repo(monkeypatch)
    yaml_file = tmp_path / ".gitlab-ci.yml"
    yaml_file.write_text("build:\n  script: echo 1\n")

    def fake_request(endpoint, params=None, method="GET"):
        return {"valid": True, "errors": [], "warnings": ["deprecated"]}

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

    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"valid": True, "errors": [], "warnings": []}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    runner = CliRunner()
    runner.invoke(cli, ["ci", "validate", "-f", str(yaml_file), "--include-jobs"])

    assert calls[0][1]["include_jobs"] is True
