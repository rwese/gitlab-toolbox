"""Smoke tests for the `ci variables` / `ci tokens` / `ci inventory` commands."""

import io
import json

import pytest
from click.testing import CliRunner

from gitlab_toolbox.formatters import display as display_module

from gitlab_toolbox.api.ci_tokens import CITokensAPI
from gitlab_toolbox.api.ci_variables import CIVariablesAPI
from gitlab_toolbox.api.scope import ScopeResolver
from gitlab_toolbox.cli import cli
from gitlab_toolbox.models.ci_scope import SCOPE_PROJECT, Scope, SkippedScope
from gitlab_toolbox.models.ci_token import KIND_PROJECT_ACCESS, CIToken
from gitlab_toolbox.models.ci_variable import ORIGIN_INHERITED, CIVariable

PROJECT = Scope(kind=SCOPE_PROJECT, path="acme/platform/app", id=100)


@pytest.fixture
def stub_api(monkeypatch):
    """Serve one variable, one token and one skipped scope."""
    variable = CIVariable(
        key="CI_TOKEN",
        scope_kind=SCOPE_PROJECT,
        scope_path="acme/platform/app",
        defined_in="group:acme",
        origin=ORIGIN_INHERITED,
        inheritance_depth=2,
        masked=True,
        value_fingerprint="sha256:deadbeef",
        value_length=20,
    )
    token = CIToken(
        kind=KIND_PROJECT_ACCESS,
        id=1,
        name="ci-bot",
        scope_kind=SCOPE_PROJECT,
        scope_path="acme/platform/app",
        scopes=["api"],
        access_level=40,
        created_at="2025-01-01T00:00:00.000Z",
        expires_at="2099-01-01",
    )
    skipped = [SkippedScope("project", "acme/platform/app", "triggers", "403 Forbidden")]

    monkeypatch.setattr(ScopeResolver, "resolve", staticmethod(lambda **kwargs: ([PROJECT], [])))
    monkeypatch.setattr(
        CIVariablesAPI, "resolve", staticmethod(lambda *args, **kwargs: ([variable], []))
    )
    monkeypatch.setattr(
        CITokensAPI, "get_tokens", staticmethod(lambda *args, **kwargs: ([token], skipped))
    )
    return variable, token


@pytest.fixture
def stdout_console():
    """Capture the Rich stdout console, which CliRunner cannot intercept."""
    buffer = io.StringIO()
    original = display_module.console_stdout.file
    display_module.console_stdout.file = buffer
    try:
        yield buffer
    finally:
        display_module.console_stdout.file = original


@pytest.mark.parametrize("output_format", ["table", "json", "csv", "markdown"])
def test_variables_list_supports_all_formats(stub_api, stdout_console, output_format):
    result = CliRunner().invoke(
        cli, ["ci", "variables", "list", "--project", "acme/platform/app", "-o", output_format]
    )

    assert result.exit_code == 0, result.output
    assert "CI_TOKEN" in result.output + stdout_console.getvalue()


def test_variables_list_json_envelope_marks_instance_scope(stub_api):
    result = CliRunner().invoke(
        cli, ["ci", "variables", "list", "--project", "acme/platform/app", "-o", "json"]
    )

    payload = json.loads(result.output)
    assert payload["instance_scope_included"] is False
    assert payload["reveal"] is False
    assert payload["variables"][0]["origin"] == "inherited"
    assert payload["variables"][0]["value"] is None


def test_variables_list_rejects_direct_only_with_show_shadowed(stub_api):
    result = CliRunner().invoke(
        cli,
        [
            "ci",
            "variables",
            "list",
            "--project",
            "acme/platform/app",
            "--direct-only",
            "--show-shadowed",
        ],
    )

    assert result.exit_code != 0
    assert "--direct-only cannot be combined" in result.output


def test_variables_list_writes_output_file(stub_api, tmp_path):
    target = tmp_path / "vars.json"

    result = CliRunner().invoke(
        cli,
        [
            "ci",
            "variables",
            "list",
            "--project",
            "acme/platform/app",
            "-o",
            "json",
            "-O",
            str(target),
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(target.read_text())["variables"][0]["key"] == "CI_TOKEN"


@pytest.mark.parametrize("output_format", ["table", "json", "csv", "markdown"])
def test_tokens_list_supports_all_formats(stub_api, stdout_console, output_format):
    result = CliRunner().invoke(
        cli, ["ci", "tokens", "list", "--project", "acme/platform/app", "-o", output_format]
    )

    assert result.exit_code == 0, result.output
    assert "ci-bot" in result.output + stdout_console.getvalue()


def test_tokens_list_reports_skipped_scopes_in_json(stub_api):
    result = CliRunner().invoke(
        cli, ["ci", "tokens", "list", "--project", "acme/platform/app", "-o", "json"]
    )

    payload = json.loads(result.output)
    assert payload["skipped"][0]["resource"] == "triggers"
    assert payload["tokens"][0]["access_level_description"] == "Maintainer"


def test_tokens_list_rejects_unknown_kind(stub_api):
    result = CliRunner().invoke(
        cli, ["ci", "tokens", "list", "--project", "acme/platform/app", "--kind", "nope"]
    )

    assert result.exit_code != 0
    assert "unknown kind" in result.output


def test_inventory_emits_single_document(stub_api):
    result = CliRunner().invoke(cli, ["ci", "inventory", "--project", "acme/platform/app"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["instance_scope_included"] is False
    assert payload["scopes"][0]["path"] == "acme/platform/app"
    assert payload["variables"][0]["key"] == "CI_TOKEN"
    assert payload["tokens"][0]["name"] == "ci-bot"
