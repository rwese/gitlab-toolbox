"""Tests for CI/CD credential inventory."""

from datetime import datetime, timedelta, timezone

from gitlab_toolbox.api.ci_tokens import CITokensAPI
from gitlab_toolbox.api.client import GitLabClient
from gitlab_toolbox.models.ci_scope import SCOPE_GROUP, SCOPE_PROJECT, Scope
from gitlab_toolbox.models.ci_token import (
    KIND_DEPLOY,
    KIND_DEPLOY_KEY,
    KIND_GROUP_ACCESS,
    KIND_PROJECT_ACCESS,
    KIND_TRIGGER,
    CIToken,
)

PROJECT = Scope(kind=SCOPE_PROJECT, path="acme/platform/app", id=100)
GROUP = Scope(kind=SCOPE_GROUP, path="acme/platform", id=62)


def _iso(days_from_now: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days_from_now)).isoformat()


def _date(days_from_now: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days_from_now)).strftime("%Y-%m-%d")


def test_project_scope_fetches_all_kinds(monkeypatch):
    payloads = {
        "projects/100/access_tokens": [
            {
                "id": 1,
                "name": "ci",
                "scopes": ["api"],
                "access_level": 40,
                "created_at": "2025-08-04T06:46:19.882Z",
                "expires_at": "2026-08-04",
                "last_used_at": "2025-09-01T00:00:00.000Z",
                "revoked": False,
                "active": True,
                "user_id": 742,
            }
        ],
        "projects/100/deploy_tokens": [
            {
                "id": 2,
                "name": "dt",
                "username": "dt-user",
                "scopes": ["read_repository"],
                "expires_at": None,
                "revoked": False,
                "expired": False,
            }
        ],
        "projects/100/triggers": [
            {
                "id": 3,
                "description": "nightly",
                "created_at": "2024-01-01T00:00:00.000Z",
                "last_used": "2024-06-01T00:00:00.000Z",
                "owner": {"id": 5, "username": "alice"},
            }
        ],
        "projects/100/deploy_keys": [
            {
                "id": 4,
                "title": "bot key",
                "created_at": "2024-01-01T00:00:00.000Z",
                "expires_at": None,
                "last_used_at": None,
                "can_push": True,
                "fingerprint": "aa:bb",
            }
        ],
    }

    monkeypatch.setattr(
        GitLabClient,
        "paginate_safe",
        staticmethod(
            lambda endpoint, params=None, per_page=100, limit=None: (payloads[endpoint], None)
        ),
    )

    tokens, skipped = CITokensAPI.get_tokens([PROJECT])

    kinds = {t.kind: t for t in tokens}
    assert set(kinds) == {KIND_PROJECT_ACCESS, KIND_DEPLOY, KIND_TRIGGER, KIND_DEPLOY_KEY}
    assert skipped == []

    access = kinds[KIND_PROJECT_ACCESS]
    assert access.access_level_description == "Maintainer"
    assert access.last_used_ips is None  # admin-only field, never populated here

    trigger = kinds[KIND_TRIGGER]
    assert trigger.name == "nightly"
    assert trigger.owner == "alice"
    assert trigger.last_used_at == "2024-06-01T00:00:00.000Z"

    deploy = kinds[KIND_DEPLOY]
    assert deploy.created_at is None  # not exposed by the API
    assert deploy.never_used is False  # usage is not tracked for deploy tokens

    key = kinds[KIND_DEPLOY_KEY]
    assert key.name == "bot key"
    assert key.can_push is True


def test_group_scope_skips_project_only_kinds(monkeypatch):
    seen = []

    def fake_paginate_safe(endpoint, params=None, per_page=100, limit=None):
        seen.append(endpoint)
        return [], None

    monkeypatch.setattr(GitLabClient, "paginate_safe", fake_paginate_safe)

    CITokensAPI.get_tokens([GROUP])

    assert seen == ["groups/62/access_tokens", "groups/62/deploy_tokens"]


def test_kind_filter_limits_requests(monkeypatch):
    seen = []

    def fake_paginate_safe(endpoint, params=None, per_page=100, limit=None):
        seen.append(endpoint)
        return [], None

    monkeypatch.setattr(GitLabClient, "paginate_safe", fake_paginate_safe)

    CITokensAPI.get_tokens([PROJECT], kinds=[KIND_TRIGGER])

    assert seen == ["projects/100/triggers"]


def test_forbidden_resource_is_recorded(monkeypatch):
    def fake_paginate_safe(endpoint, params=None, per_page=100, limit=None):
        if endpoint.endswith("/triggers"):
            return None, "403 Forbidden (insufficient role)"
        return [], None

    monkeypatch.setattr(GitLabClient, "paginate_safe", fake_paginate_safe)

    tokens, skipped = CITokensAPI.get_tokens([PROJECT])

    assert tokens == []
    assert [s.resource for s in skipped] == ["triggers"]


def _token(**overrides) -> CIToken:
    defaults = dict(
        kind=KIND_GROUP_ACCESS,
        id=1,
        name="t",
        scope_kind=SCOPE_GROUP,
        scope_path="acme",
    )
    defaults.update(overrides)
    return CIToken(**defaults)


def test_state_derivation():
    assert _token(expires_at=_date(30)).state == "active"
    assert _token(expires_at=_date(-1)).state == "expired"
    assert _token(revoked=True, expires_at=_date(30)).state == "revoked"
    assert _token(expired=True).state == "expired"
    assert _token(expires_at=None).state == "active"


def test_filter_by_state():
    tokens = [_token(id=1, expires_at=_date(10)), _token(id=2, revoked=True)]

    assert [t.id for t in CITokensAPI.filter_tokens(tokens, state="active")] == [1]
    assert [t.id for t in CITokensAPI.filter_tokens(tokens, state="revoked")] == [2]
    assert len(CITokensAPI.filter_tokens(tokens, state="all")) == 2


def test_filter_by_expiring_in():
    tokens = [
        _token(id=1, expires_at=_date(5)),
        _token(id=2, expires_at=_date(200)),
        _token(id=3, expires_at=None),
    ]

    result = CITokensAPI.filter_tokens(tokens, expiring_in=30)

    assert [t.id for t in result] == [1]


def test_filter_by_unused_for_includes_never_used_old_tokens():
    tokens = [
        _token(id=1, created_at=_iso(-200), last_used_at=None),  # never used, old
        _token(id=2, created_at=_iso(-5), last_used_at=None),  # never used, new
        _token(id=3, created_at=_iso(-200), last_used_at=_iso(-100)),  # stale
        _token(id=4, created_at=_iso(-200), last_used_at=_iso(-2)),  # recently used
        _token(id=5, kind=KIND_DEPLOY, created_at=None, last_used_at=None),  # no tracking
    ]

    result = CITokensAPI.filter_tokens(tokens, unused_for=90)

    assert [t.id for t in result] == [1, 3]


def test_to_dict_exposes_derived_fields():
    payload = _token(expires_at=_date(10), last_used_at=_iso(-3)).to_dict()

    assert payload["state"] == "active"
    assert payload["days_until_expiry"] in (9, 10)
    assert payload["days_since_last_use"] in (2, 3)
