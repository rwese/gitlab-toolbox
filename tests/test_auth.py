from pathlib import Path

import requests

from gitlab_toolbox.api.auth import AuthAPI
from gitlab_toolbox.api.client import GitLabClient


def test_auth_status_does_not_read_glab_when_configured_token_is_valid(monkeypatch):
    monkeypatch.setattr(GitLabClient, "_base_url", "https://gitlab.example.com")
    monkeypatch.setattr(GitLabClient, "_token", "valid-token")
    monkeypatch.setattr(
        AuthAPI, "_check_token", classmethod(lambda cls, url, token: {"username": "alice"})
    )
    monkeypatch.setattr(
        GitLabClient,
        "_read_glab_config",
        lambda url: (_ for _ in ()).throw(AssertionError("glab should not be read")),
    )

    result = AuthAPI.check_auth_with_url("https://gitlab.example.com")

    assert result["is_authenticated"] is True
    assert result["token_source"] == "configured token"


def test_auth_status_falls_back_to_glab_after_invalid_configured_token(monkeypatch):
    monkeypatch.setattr(GitLabClient, "_token", "invalid-token")
    monkeypatch.setattr(
        AuthAPI,
        "_check_token",
        classmethod(
            lambda cls, url, token: {"username": "alice"} if token == "glab-token" else None
        ),
    )
    monkeypatch.setattr(GitLabClient, "_read_glab_config", lambda url: (url, "glab-token"))

    result = AuthAPI.check_auth_with_url("https://gitlab.example.com")

    assert result["is_authenticated"] is True
    assert result["token_source"] == "glab authentication"


def test_api_request_retries_unauthorized_response_with_glab_token(monkeypatch):
    calls = []

    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self.payload = payload
            self.content = b"{}"

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(response=self)

        def json(self):
            return self.payload

    def fake_get(url, headers, params, timeout):
        calls.append(headers.get("Authorization"))
        if len(calls) == 1:
            return Response(401, {"message": "401 Unauthorized"})
        return Response(200, {"username": "alice"})

    monkeypatch.setattr(GitLabClient, "_base_url", "https://gitlab.example.com")
    monkeypatch.setattr(GitLabClient, "_token", "invalid-token")
    monkeypatch.setattr(
        GitLabClient,
        "_read_glab_config",
        lambda url: ("https://gitlab.example.com", "glab-token"),
    )
    monkeypatch.setattr(requests, "get", fake_get)

    result = GitLabClient._run_api_request("user")

    assert result == {"username": "alice"}
    assert calls == ["Bearer invalid-token", "Bearer glab-token"]
    assert GitLabClient._token == "invalid-token"


def test_glab_config_never_returns_a_different_hosts_token(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "glab-cli"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yml").write_text("hosts:\n  other.example.com:\n    token: other-token\n")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    assert GitLabClient._read_glab_config("https://gitlab.example.com") == (None, None)
