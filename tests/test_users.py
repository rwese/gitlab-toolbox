import json

from click.testing import CliRunner

from gitlab_toolbox.api.client import GitLabClient
from gitlab_toolbox.cli import cli


def test_get_current_user_fetches_user_endpoint(monkeypatch):
    from gitlab_toolbox.api.users import UsersAPI

    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        return {"id": 7, "username": "alice", "name": "Alice"}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    user = UsersAPI.get_current_user()

    assert user.id == 7
    assert user.username == "alice"
    assert calls == [("user", None, "GET")]


def test_current_memberships_fetches_groups_and_projects(monkeypatch):
    from gitlab_toolbox.api.users import UsersAPI

    calls = []

    def fake_paginate(endpoint, params=None, per_page=100, limit=None):
        calls.append((endpoint, params, limit))
        if endpoint == "groups":
            return [{"id": 1, "full_path": "team", "name": "Team", "access_level": 40}]
        return [
            {
                "id": 2,
                "path_with_namespace": "team/app",
                "name": "App",
                "permissions": {"project_access": {"access_level": 30}},
            }
        ]

    monkeypatch.setattr(GitLabClient, "paginate", fake_paginate)

    memberships = UsersAPI.get_current_memberships(
        resource_type="all", min_access_level=30, limit=5
    )

    assert [(m.source_type, m.source_full_name, m.access_level) for m in memberships] == [
        ("group", "team", 40),
        ("project", "team/app", 30),
    ]
    assert calls == [
        ("groups", {"all_available": "false", "min_access_level": "30"}, 5),
        ("projects", {"membership": "true", "min_access_level": "30"}, 5),
    ]


def test_counts_use_current_and_association_endpoints(monkeypatch):
    from gitlab_toolbox.api.users import UsersAPI

    calls = []

    def fake_request(endpoint, params=None, method="GET"):
        calls.append((endpoint, params, method))
        if endpoint == "user_counts":
            return {"assigned_issues": 3}
        if endpoint == "user":
            return {"id": 7, "username": "alice", "name": "Alice"}
        return {"projects": 4}

    monkeypatch.setattr(GitLabClient, "_run_api_request", fake_request)

    counts = UsersAPI.get_counts()

    assert counts.assigned_issues == 3
    assert counts.projects == 4
    assert calls == [
        ("user_counts", None, "GET"),
        ("user", None, "GET"),
        ("users/7/associations_count", None, "GET"),
    ]


def test_whoami_outputs_current_user_json(monkeypatch):
    from gitlab_toolbox.api.users import UsersAPI

    monkeypatch.setattr(
        UsersAPI,
        "get_current_user",
        lambda: UsersAPI._parse_user({"id": 9, "username": "carol", "name": "Carol"}),
    )

    result = CliRunner().invoke(cli, ["whoami", "--output", "json"])

    assert result.exit_code == 0
    assert json.loads(result.output)["username"] == "carol"


def test_whoami_rejects_user_argument():
    result = CliRunner().invoke(cli, ["whoami", "carol"])

    assert result.exit_code != 0
    assert "No such command 'carol'." in result.output


def test_whoami_show_subcommand_is_removed():
    result = CliRunner().invoke(cli, ["whoami", "show"])

    assert result.exit_code != 0
    assert "No such command 'show'." in result.output


def test_whoami_counts_subcommand_is_removed():
    result = CliRunner().invoke(cli, ["whoami", "counts"])

    assert result.exit_code != 0
    assert "No such command 'counts'." in result.output


def test_whoami_sensitive_flags_are_removed():
    result = CliRunner().invoke(cli, ["whoami", "--include-emails"])

    assert result.exit_code != 0
    assert "No such option: --include-emails" in result.output
