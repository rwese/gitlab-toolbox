"""Tests for CI/CD variable inventory and inheritance resolution."""

from gitlab_toolbox.api.ci_variables import CIVariablesAPI
from gitlab_toolbox.api.client import GitLabClient
from gitlab_toolbox.models.ci_scope import SCOPE_GROUP, SCOPE_PROJECT, Scope
from gitlab_toolbox.models.ci_variable import (
    ORIGIN_DIRECT,
    ORIGIN_INHERITED,
    ORIGIN_OVERRIDE,
    ORIGIN_SHADOWED,
    fingerprint,
)


def _raw(key, value="secret", **overrides):
    data = {
        "key": key,
        "value": value,
        "variable_type": "env_var",
        "environment_scope": "*",
        "protected": False,
        "masked": False,
        "hidden": False,
        "raw": False,
        "description": None,
    }
    data.update(overrides)
    return data


PROJECT = Scope(kind=SCOPE_PROJECT, path="ps/devops/app", id=100)


def _patch_variables(monkeypatch, payloads):
    """Serve variable payloads keyed by scope ref."""

    def fake_get(scope):
        return payloads.get(scope.ref, []), None

    monkeypatch.setattr(CIVariablesAPI, "get_scope_variables", staticmethod(fake_get))


def test_direct_only_skips_parent_chain(monkeypatch):
    _patch_variables(
        monkeypatch,
        {
            "project:ps/devops/app": [_raw("LOCAL")],
            "group:ps": [_raw("GLOBAL")],
        },
    )

    variables, skipped = CIVariablesAPI.resolve([PROJECT], direct_only=True)

    assert [v.key for v in variables] == ["LOCAL"]
    assert variables[0].origin == ORIGIN_DIRECT
    assert variables[0].inheritance_depth == 0
    assert skipped == []


def test_inherited_variable_is_tagged_with_defining_group(monkeypatch):
    _patch_variables(
        monkeypatch,
        {
            "project:ps/devops/app": [],
            "group:ps/devops": [],
            "group:ps": [_raw("GLOBAL")],
        },
    )

    variables, _ = CIVariablesAPI.resolve([PROJECT])

    assert variables[0].origin == ORIGIN_INHERITED
    assert variables[0].defined_in == "group:ps"
    assert variables[0].inheritance_depth == 2
    assert variables[0].display_key.startswith("↑")


def test_project_value_overrides_group_value(monkeypatch):
    _patch_variables(
        monkeypatch,
        {
            "project:ps/devops/app": [_raw("TOKEN", "project-value")],
            "group:ps/devops": [_raw("TOKEN", "group-value")],
            "group:ps": [_raw("TOKEN", "root-value")],
        },
    )

    variables, _ = CIVariablesAPI.resolve([PROJECT])

    assert len(variables) == 1
    winner = variables[0]
    assert winner.origin == ORIGIN_OVERRIDE
    assert winner.defined_in == "project:ps/devops/app"
    # The nearest masked scope is reported, not the outermost one.
    assert winner.overrides == "group:ps/devops"


def test_show_shadowed_emits_masked_entries(monkeypatch):
    _patch_variables(
        monkeypatch,
        {
            "project:ps/devops/app": [_raw("TOKEN", "project-value")],
            "group:ps/devops": [_raw("TOKEN", "group-value")],
            "group:ps": [],
        },
    )

    variables, _ = CIVariablesAPI.resolve([PROJECT], show_shadowed=True)

    origins = {v.origin: v for v in variables}
    assert set(origins) == {ORIGIN_OVERRIDE, ORIGIN_SHADOWED}
    assert origins[ORIGIN_SHADOWED].defined_in == "group:ps/devops"
    assert origins[ORIGIN_SHADOWED].overridden_by == "project:ps/devops/app"


def test_same_key_different_environment_scopes_do_not_merge(monkeypatch):
    _patch_variables(
        monkeypatch,
        {
            "project:ps/devops/app": [_raw("TOKEN", "prod", environment_scope="production")],
            "group:ps/devops": [],
            "group:ps": [_raw("TOKEN", "any")],
        },
    )

    variables, _ = CIVariablesAPI.resolve([PROJECT])

    by_env = {v.environment_scope: v for v in variables}
    assert by_env["production"].origin == ORIGIN_DIRECT
    assert by_env["*"].origin == ORIGIN_INHERITED


def test_values_are_redacted_by_default(monkeypatch):
    _patch_variables(monkeypatch, {"project:ps/devops/app": [_raw("TOKEN", "s3cret")]})

    variables, _ = CIVariablesAPI.resolve([PROJECT], direct_only=True)
    variable = variables[0]

    assert variable.value is None
    assert variable.value_redacted is True
    assert variable.value_fingerprint == fingerprint("s3cret")
    assert variable.value_length == 6
    assert variable.to_dict()["value"] is None


def test_reveal_includes_raw_value(monkeypatch):
    _patch_variables(monkeypatch, {"project:ps/devops/app": [_raw("TOKEN", "s3cret")]})

    variables, _ = CIVariablesAPI.resolve([PROJECT], direct_only=True, reveal=True)
    payload = variables[0].to_dict()

    assert payload["value"] == "s3cret"
    assert payload["value_redacted"] is False
    assert "value_fingerprint" not in payload


def test_identical_override_is_detectable_via_fingerprint(monkeypatch):
    _patch_variables(
        monkeypatch,
        {
            "project:ps/devops/app": [_raw("TOKEN", "same")],
            "group:ps/devops": [_raw("TOKEN", "same")],
            "group:ps": [],
        },
    )

    variables, _ = CIVariablesAPI.resolve([PROJECT], show_shadowed=True)

    fingerprints = {v.value_fingerprint for v in variables}
    assert len(fingerprints) == 1


def test_environment_filter_matches_wildcards(monkeypatch):
    _patch_variables(
        monkeypatch,
        {
            "project:ps/devops/app": [
                _raw("ANY"),
                _raw("PROD", environment_scope="production"),
                _raw("REVIEW", environment_scope="review/*"),
            ]
        },
    )

    variables, _ = CIVariablesAPI.resolve([PROJECT], direct_only=True, environment="review/mr-1")

    assert sorted(v.key for v in variables) == ["ANY", "REVIEW"]


def test_type_filter(monkeypatch):
    _patch_variables(
        monkeypatch,
        {
            "project:ps/devops/app": [
                _raw("ENV"),
                _raw("FILE", variable_type="file"),
            ]
        },
    )

    variables, _ = CIVariablesAPI.resolve([PROJECT], direct_only=True, variable_type="file")

    assert [v.key for v in variables] == ["FILE"]


def test_forbidden_scope_is_reported_not_raised(monkeypatch):
    def fake_paginate_safe(endpoint, params=None, per_page=100, limit=None):
        if endpoint.startswith("groups/"):
            return None, "403 Forbidden (insufficient role)"
        return [_raw("LOCAL")], None

    monkeypatch.setattr(GitLabClient, "paginate_safe", fake_paginate_safe)

    variables, skipped = CIVariablesAPI.resolve([PROJECT])

    assert [v.key for v in variables] == ["LOCAL"]
    refs = {s.ref for s in skipped}
    assert refs == {"group:ps", "group:ps/devops"}
    assert all(s.resource == "variables" for s in skipped)


def test_group_scope_uses_group_endpoint(monkeypatch):
    seen = []

    def fake_paginate_safe(endpoint, params=None, per_page=100, limit=None):
        seen.append(endpoint)
        return [], None

    monkeypatch.setattr(GitLabClient, "paginate_safe", fake_paginate_safe)

    CIVariablesAPI.resolve([Scope(kind=SCOPE_GROUP, path="ps/devops", id=62)], direct_only=True)

    assert seen == ["groups/62/variables"]
