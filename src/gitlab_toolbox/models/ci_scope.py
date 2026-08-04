"""Scope models for CI/CD configuration inventory commands."""

from dataclasses import dataclass
from typing import Optional

SCOPE_PROJECT = "project"
SCOPE_GROUP = "group"


@dataclass
class Scope:
    """A project or group that CI/CD configuration is read from."""

    kind: str  # 'project' or 'group'
    path: str
    id: Optional[int] = None
    web_url: Optional[str] = None

    @property
    def ref(self) -> str:
        """Return a stable ``kind:path`` reference (e.g. ``group:acme/platform``)."""
        return f"{self.kind}:{self.path}"

    @property
    def api_id(self) -> str:
        """Return the identifier to use in API paths (numeric ID or encoded path)."""
        if self.id is not None:
            return str(self.id)
        return self.path.replace("/", "%2F")


@dataclass
class SkippedScope:
    """A scope that could not be read, with the reason why."""

    kind: str
    path: str
    resource: str  # 'variables', 'access_tokens', ...
    reason: str

    @property
    def ref(self) -> str:
        """Return a stable ``kind:path`` reference."""
        return f"{self.kind}:{self.path}"
