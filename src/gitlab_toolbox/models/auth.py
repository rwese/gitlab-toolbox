"""Authentication data model."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AuthStatus:
    """Represents the current authentication status with a GitLab instance."""

    hostname: str
    base_url: str
    api_protocol: str
    is_authenticated: bool
    username: Optional[str] = None
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    token_source: Optional[str] = None  # env, glab_config, keyring
    token_name: Optional[str] = None
    git_protocol: Optional[str] = None  # ssh or https for git operations
    error: Optional[str] = None
    is_gitlab_com: bool = False

    @property
    def status_icon(self) -> str:
        """Return an icon representing the authentication status."""
        if self.is_authenticated:
            return "✓"
        return "✗"

    @property
    def status_text(self) -> str:
        """Return a human-readable status description."""
        if self.is_authenticated:
            return f"Authenticated as {self.username}"
        if self.error:
            return f"Authentication failed: {self.error}"
        return "Not authenticated"
