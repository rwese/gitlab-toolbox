"""Users API operations."""

import sys
from typing import List, Optional

import requests
from rich.console import Console

from ..models.user import UserCounts, UserMembership, UserProfile
from .client import GitLabClient

console = Console(file=sys.stderr)


class UsersAPI:
    """API wrapper for GitLab users operations."""

    @classmethod
    def get_current_user(cls) -> UserProfile:
        """Fetch the authenticated user via GET /user."""
        data = GitLabClient._run_api_request("user")
        return cls._parse_user(data)

    @classmethod
    def get_user_by_id(cls, user_id: int) -> Optional[UserProfile]:
        """Fetch a visible user profile by ID."""
        data = GitLabClient._run_api_request_optional(f"users/{user_id}")
        if not data or isinstance(data, list):
            return None
        return cls._parse_user(data)

    @classmethod
    def get_user_by_username(cls, username: str) -> Optional[UserProfile]:
        """Resolve a visible user by exact username."""
        users = GitLabClient._run_api_request("users", {"username": username})
        match = next((user for user in users if user.get("username") == username), None)
        return cls._parse_user(match) if match else None

    @classmethod
    def resolve_user(cls, user: Optional[str]) -> Optional[UserProfile]:
        """Resolve no user/current, numeric ID, or exact username to a user profile."""
        if not user:
            return cls.get_current_user()
        if user.isdigit():
            return cls.get_user_by_id(int(user))
        return cls.get_user_by_username(user)

    @classmethod
    def get_current_memberships(
        cls,
        resource_type: str = "all",
        min_access_level: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[UserMembership]:
        """Fetch current user's available group and project memberships."""
        memberships: List[UserMembership] = []

        if resource_type in ("group", "all"):
            params = {"all_available": "false"}
            if min_access_level is not None:
                params["min_access_level"] = str(min_access_level)
            groups = GitLabClient.paginate("groups", params, limit=limit)
            memberships.extend(cls._parse_group_membership(group) for group in groups)

        if resource_type in ("project", "all"):
            params = {"membership": "true"}
            if min_access_level is not None:
                params["min_access_level"] = str(min_access_level)
            projects = GitLabClient.paginate("projects", params, limit=limit)
            memberships.extend(cls._parse_project_membership(project) for project in projects)

        return memberships

    @classmethod
    def get_user_memberships(
        cls,
        user_id: int,
        resource_type: str = "all",
        min_access_level: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[UserMembership]:
        """Fetch direct memberships for a user via the admin-only endpoint."""
        params = {}
        if resource_type != "all":
            params["type"] = resource_type
        if min_access_level is not None:
            params["min_access_level"] = str(min_access_level)

        try:
            data = GitLabClient.paginate(f"users/{user_id}/memberships", params, limit=limit)
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code == 403:
                raise PermissionError("403 Forbidden") from error
            raise

        return [cls._parse_direct_membership(item) for item in data]

    @classmethod
    def get_counts(cls, user_id: Optional[int] = None) -> UserCounts:
        """Fetch current work counts and association counts."""
        current_counts = {}
        if user_id is None:
            current_counts = GitLabClient._run_api_request("user_counts")
            current_user = cls.get_current_user()
            user_id = current_user.id

        association_counts = GitLabClient._run_api_request(f"users/{user_id}/associations_count")
        return cls._parse_counts({**current_counts, **association_counts})

    @staticmethod
    def _parse_user(data: dict) -> UserProfile:
        return UserProfile(
            id=data.get("id"),
            username=data.get("username"),
            name=data.get("name"),
            state=data.get("state"),
            web_url=data.get("web_url"),
            avatar_url=data.get("avatar_url"),
            public_email=data.get("public_email"),
            email=data.get("email"),
            bio=data.get("bio"),
            location=data.get("location"),
            organization=data.get("organization"),
            job_title=data.get("job_title"),
            created_at=data.get("created_at"),
            last_activity_on=data.get("last_activity_on"),
            is_admin=data.get("is_admin"),
            raw=data,
        )

    @staticmethod
    def _parse_group_membership(data: dict) -> UserMembership:
        access_level = data.get("access_level")
        return UserMembership(
            source_type="group",
            source_id=data.get("id"),
            source_full_name=data.get("full_path") or data.get("name"),
            access_level=access_level,
            access_level_description=UsersAPI._access_level_description(access_level),
            web_url=data.get("web_url"),
            raw=data,
        )

    @staticmethod
    def _parse_project_membership(data: dict) -> UserMembership:
        permissions = data.get("permissions") or {}
        project_access = permissions.get("project_access") or {}
        group_access = permissions.get("group_access") or {}
        access_level = project_access.get("access_level") or group_access.get("access_level")
        return UserMembership(
            source_type="project",
            source_id=data.get("id"),
            source_full_name=data.get("path_with_namespace") or data.get("name"),
            access_level=access_level,
            access_level_description=UsersAPI._access_level_description(access_level),
            web_url=data.get("web_url"),
            raw=data,
        )

    @staticmethod
    def _parse_direct_membership(data: dict) -> UserMembership:
        source_type = data.get("source_type") or data.get("type")
        source = data.get("source") or {}
        access_level = data.get("access_level")
        return UserMembership(
            source_type=source_type,
            source_id=data.get("source_id") or source.get("id"),
            source_full_name=(
                data.get("source_full_name")
                or source.get("full_path")
                or source.get("path_with_namespace")
                or source.get("name")
            ),
            access_level=access_level,
            access_level_description=UsersAPI._access_level_description(access_level),
            expires_at=data.get("expires_at"),
            web_url=source.get("web_url"),
            raw=data,
        )

    @staticmethod
    def _parse_counts(data: dict) -> UserCounts:
        return UserCounts(
            assigned_issues=data.get("assigned_issues"),
            assigned_merge_requests=data.get("assigned_merge_requests"),
            review_requested_merge_requests=data.get("review_requested_merge_requests"),
            todos=data.get("todos"),
            projects=data.get("projects"),
            groups=data.get("groups"),
            issues=data.get("issues"),
            merge_requests=data.get("merge_requests"),
            snippets=data.get("snippets"),
            raw=data,
        )

    @staticmethod
    def _access_level_description(access_level: Optional[int]) -> Optional[str]:
        return {
            5: "Minimal Access",
            10: "Guest",
            15: "Planner",
            20: "Reporter",
            30: "Developer",
            40: "Maintainer",
            50: "Owner",
        }.get(access_level)
