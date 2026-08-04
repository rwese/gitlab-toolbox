"""Unified credential model for CI/CD-relevant tokens and keys."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Token kinds
KIND_PROJECT_ACCESS = "project_access"
KIND_GROUP_ACCESS = "group_access"
KIND_DEPLOY = "deploy"
KIND_TRIGGER = "trigger"
KIND_DEPLOY_KEY = "deploy_key"

ALL_KINDS = [
    KIND_PROJECT_ACCESS,
    KIND_GROUP_ACCESS,
    KIND_DEPLOY,
    KIND_TRIGGER,
    KIND_DEPLOY_KEY,
]

# CLI ``--kind`` values mapped to the model kinds they select.
KIND_ALIASES = {
    "access": [KIND_PROJECT_ACCESS, KIND_GROUP_ACCESS],
    "deploy": [KIND_DEPLOY],
    "trigger": [KIND_TRIGGER],
    "key": [KIND_DEPLOY_KEY],
}

ACCESS_LEVELS = {
    0: "No Access",
    5: "Minimal Access",
    10: "Guest",
    20: "Reporter",
    30: "Developer",
    40: "Maintainer",
    50: "Owner",
}

STATE_ACTIVE = "active"
STATE_EXPIRED = "expired"
STATE_REVOKED = "revoked"


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse a GitLab timestamp or date string into an aware datetime."""
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _days_from_now(value: Optional[str]) -> Optional[int]:
    """Return whole days between now and ``value`` (negative = in the past).

    Truncated toward zero so that a timestamp three days old reports ``-3``
    rather than ``-4`` because of sub-second drift.
    """
    parsed = _parse_timestamp(value)
    if parsed is None:
        return None
    delta = parsed - datetime.now(timezone.utc)
    return int(delta.total_seconds() / 86400)


@dataclass
class CIToken:
    """A credential attached to a project or group.

    One model covers project/group access tokens, deploy tokens, trigger
    tokens and deploy keys; fields that a given kind does not expose stay
    ``None`` and render as ``n/a``.
    """

    kind: str
    id: Optional[int]
    name: str
    scope_kind: str  # 'project' or 'group'
    scope_path: str

    description: Optional[str] = None
    username: Optional[str] = None
    scopes: List[str] = field(default_factory=list)
    access_level: Optional[int] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None
    last_used_ips: Optional[List[str]] = None
    revoked: Optional[bool] = None
    expired: Optional[bool] = None
    active: Optional[bool] = None
    user_id: Optional[int] = None
    owner: Optional[str] = None
    can_push: Optional[bool] = None
    fingerprint: Optional[str] = None

    @property
    def access_level_description(self) -> Optional[str]:
        """Return the human-readable access level, if the kind has one."""
        if self.access_level is None:
            return None
        return ACCESS_LEVELS.get(self.access_level, f"Unknown ({self.access_level})")

    @property
    def days_until_expiry(self) -> Optional[int]:
        """Days until ``expires_at`` (negative if already past)."""
        return _days_from_now(self.expires_at)

    @property
    def days_since_last_use(self) -> Optional[int]:
        """Days since ``last_used_at``, or None if never used / not exposed."""
        days = _days_from_now(self.last_used_at)
        return None if days is None else -days

    @property
    def days_since_creation(self) -> Optional[int]:
        """Days since ``created_at``, or None if the kind has no timestamp."""
        days = _days_from_now(self.created_at)
        return None if days is None else -days

    @property
    def never_used(self) -> bool:
        """True when the API exposes usage tracking and reports no use."""
        return self.last_used_at is None and self.kind != KIND_DEPLOY

    @property
    def state(self) -> str:
        """Return ``revoked``, ``expired`` or ``active``."""
        if self.revoked:
            return STATE_REVOKED
        if self.expired:
            return STATE_EXPIRED
        days = self.days_until_expiry
        if days is not None and days < 0:
            return STATE_EXPIRED
        if self.active is False:
            return STATE_EXPIRED
        return STATE_ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable dict including derived fields."""
        return {
            "kind": self.kind,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "username": self.username,
            "scope_kind": self.scope_kind,
            "scope_path": self.scope_path,
            "scopes": self.scopes,
            "access_level": self.access_level,
            "access_level_description": self.access_level_description,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_used_at": self.last_used_at,
            "last_used_ips": self.last_used_ips,
            "revoked": self.revoked,
            "state": self.state,
            "user_id": self.user_id,
            "owner": self.owner,
            "can_push": self.can_push,
            "fingerprint": self.fingerprint,
            "days_until_expiry": self.days_until_expiry,
            "days_since_last_use": self.days_since_last_use,
        }
