import sys

import requests
from rich.console import Console

from gitlab_toolbox.api.client import GitLabClient
from gitlab_toolbox.api import groups as groups_api
from gitlab_toolbox.api.groups import GroupsAPI


def _http_error(status_code: int, reason: str) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    response.reason = reason
    response.url = "https://gitlab.example/api/v4/groups/178/members"
    return requests.HTTPError(f"{status_code} Client Error: {reason}", response=response)


def test_build_group_tree_skips_members_when_group_members_are_forbidden(monkeypatch, capfd):
    def fake_paginate(endpoint, params=None, per_page=100, limit=None):
        if endpoint == "groups/178/members":
            raise _http_error(403, "Forbidden")
        return []

    monkeypatch.setattr(GitLabClient, "paginate", fake_paginate)
    monkeypatch.setattr(groups_api, "console", Console(file=sys.stderr))

    groups = GroupsAPI.build_group_tree(
        [{"id": 178, "name": "Private", "full_path": "private", "parent_id": None}],
        fetch_members=True,
    )

    assert groups[0].members == []
    assert "Skipping members for group 178: 403 Forbidden" in capfd.readouterr().err


def test_build_group_tree_reraises_non_forbidden_member_errors(monkeypatch):
    def fake_paginate(endpoint, params=None, per_page=100, limit=None):
        raise _http_error(500, "Internal Server Error")

    monkeypatch.setattr(GitLabClient, "paginate", fake_paginate)

    try:
        GroupsAPI.build_group_tree(
            [{"id": 178, "name": "Private", "full_path": "private", "parent_id": None}],
            fetch_members=True,
        )
    except requests.HTTPError as error:
        assert error.response.status_code == 500
    else:
        raise AssertionError("Expected HTTPError")
