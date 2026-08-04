"""Tests for CI/CD scope resolution."""

from gitlab_toolbox.api.client import GitLabClient
from gitlab_toolbox.api.scope import ScopeResolver, ancestor_group_paths, map_concurrent
from gitlab_toolbox.models.ci_scope import SCOPE_GROUP, SCOPE_PROJECT


def test_ancestor_group_paths_for_project():
    assert ancestor_group_paths("ps/devops/app", SCOPE_PROJECT) == ["ps", "ps/devops"]


def test_ancestor_group_paths_for_group():
    assert ancestor_group_paths("ps/devops", SCOPE_GROUP) == ["ps"]


def test_ancestor_group_paths_for_top_level_group():
    assert ancestor_group_paths("ps", SCOPE_GROUP) == []


def test_map_concurrent_preserves_order():
    assert map_concurrent(lambda n: n * 2, [1, 2, 3, 4], concurrency=4) == [2, 4, 6, 8]


def test_resolve_group_with_subgroups_and_projects(monkeypatch):
    def fake_request_safe(endpoint, params=None, method="GET"):
        if endpoint == "groups/ps%2Fdevops":
            return {"id": 62, "full_path": "ps/devops", "web_url": "u"}, None
        raise AssertionError(f"unexpected endpoint {endpoint}")

    def fake_paginate_safe(endpoint, params=None, per_page=100, limit=None):
        if endpoint == "groups/62/descendant_groups":
            return [{"id": 63, "full_path": "ps/devops/sub"}], None
        if endpoint == "groups/62/projects":
            return [{"id": 100, "path_with_namespace": "ps/devops/app"}], None
        if endpoint == "groups/63/projects":
            return [{"id": 101, "path_with_namespace": "ps/devops/sub/lib"}], None
        raise AssertionError(f"unexpected endpoint {endpoint}")

    monkeypatch.setattr(GitLabClient, "_run_api_request_safe", fake_request_safe)
    monkeypatch.setattr(GitLabClient, "paginate_safe", fake_paginate_safe)

    scopes, skipped = ScopeResolver.resolve(
        groups=["ps/devops"], include_subgroups=True, include_projects=True
    )

    assert [s.ref for s in scopes] == [
        "group:ps/devops",
        "group:ps/devops/sub",
        "project:ps/devops/app",
        "project:ps/devops/sub/lib",
    ]
    assert skipped == []


def test_resolve_excludes_shared_projects(monkeypatch):
    seen_params = {}

    def fake_request_safe(endpoint, params=None, method="GET"):
        return {"id": 62, "full_path": "ps/devops"}, None

    def fake_paginate_safe(endpoint, params=None, per_page=100, limit=None):
        seen_params.update(params or {})
        return [], None

    monkeypatch.setattr(GitLabClient, "_run_api_request_safe", fake_request_safe)
    monkeypatch.setattr(GitLabClient, "paginate_safe", fake_paginate_safe)

    ScopeResolver.resolve(groups=["ps/devops"], include_projects=True)

    assert seen_params["with_shared"] == "false"
    assert seen_params["archived"] == "false"


def test_resolve_records_forbidden_scope(monkeypatch):
    def fake_request_safe(endpoint, params=None, method="GET"):
        return None, "403 Forbidden (insufficient role)"

    monkeypatch.setattr(GitLabClient, "_run_api_request_safe", fake_request_safe)

    scopes, skipped = ScopeResolver.resolve(projects=["ps/private"])

    assert scopes == []
    assert skipped[0].ref == "project:ps/private"
    assert "403" in skipped[0].reason
