"""User data models."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


def mask_email(email: Optional[str]) -> Optional[str]:
    """Mask an email address while preserving enough context for recognition."""
    if not email or "@" not in email:
        return email

    local, domain = email.split("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


@dataclass
class UserProfile:
    """Represents a GitLab user profile."""

    id: int
    username: str
    name: str
    state: Optional[str] = None
    web_url: Optional[str] = None
    avatar_url: Optional[str] = None
    public_email: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    organization: Optional[str] = None
    job_title: Optional[str] = None
    created_at: Optional[str] = None
    last_activity_on: Optional[str] = None
    is_admin: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, show_sensitive: bool = False) -> Dict[str, Any]:
        """Return a dictionary with sensitive values redacted by default."""
        data = dict(self.raw) if self.raw else {}
        data.update(
            {
                "id": self.id,
                "username": self.username,
                "name": self.name,
                "state": self.state,
                "web_url": self.web_url,
                "avatar_url": self.avatar_url,
                "public_email": self.public_email,
                "email": self.email,
                "bio": self.bio,
                "location": self.location,
                "organization": self.organization,
                "job_title": self.job_title,
                "created_at": self.created_at,
                "last_activity_on": self.last_activity_on,
                "is_admin": self.is_admin,
            }
        )
        if not show_sensitive:
            data["email"] = mask_email(data.get("email"))
            data["public_email"] = mask_email(data.get("public_email"))
        return {key: value for key, value in data.items() if value is not None}


@dataclass
class UserMembership:
    """Represents a GitLab group or project membership."""

    source_type: str
    source_id: int
    source_full_name: str
    access_level: Optional[int] = None
    access_level_description: Optional[str] = None
    expires_at: Optional[str] = None
    web_url: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserCounts:
    """Represents current work and association counts for a GitLab user."""

    assigned_issues: Optional[int] = None
    assigned_merge_requests: Optional[int] = None
    review_requested_merge_requests: Optional[int] = None
    todos: Optional[int] = None
    projects: Optional[int] = None
    groups: Optional[int] = None
    issues: Optional[int] = None
    merge_requests: Optional[int] = None
    snippets: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)
