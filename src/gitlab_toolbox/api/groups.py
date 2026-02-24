"""Groups API operations."""

import sys
from typing import List, Optional
from urllib.parse import quote

from rich.console import Console

from ..models import Group, GroupMember
from .client import GitLabClient

console = Console(file=sys.stderr)


class GroupsAPI:
    """API wrapper for GitLab groups operations."""

    ACCESS_LEVELS = {
        0: "No Access",
        5: "Minimal Access",
        10: "Guest",
        20: "Reporter",
        30: "Developer",
        40: "Maintainer",
        50: "Owner",
    }

    @classmethod
    def get_all_groups(
        cls,
        include_subgroups: bool = True,
        search: str = None,
        limit: int = None,
    ) -> List[dict]:
        """Fetch all groups from GitLab.

        Args:
            include_subgroups: Include all available groups including subgroups
            search: Search query for group names
            limit: Maximum number of groups to fetch

        Returns:
            List of group dictionaries
        """
        params = {}
        if include_subgroups:
            params["all_available"] = "true"
        if search:
            params["search"] = search

        with console.status("[bold green]Fetching groups..."):
            return GitLabClient.paginate("groups", params, limit=limit)

    @classmethod
    def get_group(cls, group_ref: str) -> Optional[dict]:
        """Fetch a single group by ID, full path, or name.

        Args:
            group_ref: Group identifier (numeric ID, full path, path, or name)

        Returns:
            Group dictionary if uniquely resolved, otherwise None
        """
        ref = (group_ref or "").strip()
        if not ref:
            return None

        # Numeric ID lookup
        if ref.isdigit():
            group = GitLabClient._run_api_request_optional(f"groups/{ref}")
            return group if isinstance(group, dict) else None

        # Full path lookup (URL-encoded)
        encoded_ref = quote(ref, safe="")
        group = GitLabClient._run_api_request_optional(f"groups/{encoded_ref}")
        if isinstance(group, dict):
            return group

        # Fallback: search and resolve exact matches
        candidates = GitLabClient.paginate(
            "groups", params={"all_available": "true", "search": ref}, limit=100
        )
        if not candidates:
            return None

        ref_lower = ref.lower()

        path_matches = [
            g
            for g in candidates
            if g.get("full_path", "").lower() == ref_lower or g.get("path", "").lower() == ref_lower
        ]
        if len(path_matches) == 1:
            return path_matches[0]
        if len(path_matches) > 1:
            return None

        name_matches = [g for g in candidates if g.get("name", "").lower() == ref_lower]
        if len(name_matches) == 1:
            return name_matches[0]
        if len(name_matches) > 1:
            return None

        return None

    @classmethod
    def get_descendant_groups(
        cls,
        group_id: int,
        search: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[dict]:
        """Fetch all descendant groups for a parent group.

        Args:
            group_id: Parent group ID
            search: Optional subgroup search
            limit: Maximum number of descendant groups to fetch

        Returns:
            List of descendant group dictionaries
        """
        params = {}
        if search:
            params["search"] = search
        return GitLabClient.paginate(f"groups/{group_id}/descendant_groups", params, limit=limit)

    @classmethod
    def get_group_members(cls, group_id: int, active_only: bool = False) -> List[GroupMember]:
        """Fetch members of a specific group.

        Args:
            group_id: The group ID
            active_only: If True, only return active members

        Returns:
            List of GroupMember objects
        """
        members_data = GitLabClient.paginate(f"groups/{group_id}/members")

        members = []
        for member in members_data:
            access_level = member.get("access_level", 0)
            state = member.get("state", "active")  # User account state
            membership_state = member.get("membership_state", "active")  # Membership state

            # Skip inactive members if active_only is set
            if active_only and state != "active":
                continue

            members.append(
                GroupMember(
                    id=member.get("id"),
                    username=member.get("username"),
                    name=member.get("name"),
                    access_level=access_level,
                    access_level_description=cls.ACCESS_LEVELS.get(access_level, "Unknown"),
                    state=state,
                    membership_state=membership_state,
                )
            )

        return members

    @classmethod
    def get_subgroups(cls, group_id: int) -> List[dict]:
        """Fetch subgroups of a specific group.

        Args:
            group_id: The group ID

        Returns:
            List of subgroup dictionaries
        """
        return GitLabClient.paginate(f"groups/{group_id}/subgroups")

    @classmethod
    def build_group_tree(
        cls, groups_data: List[dict], fetch_members: bool = True, active_members_only: bool = False
    ) -> List[Group]:
        """Build a tree structure from flat groups list.

        Args:
            groups_data: List of group dictionaries
            fetch_members: Whether to fetch members for each group
            active_members_only: If True, only fetch active members

        Returns:
            List of root Group objects with nested subgroups
        """
        groups_dict = {}
        root_groups = []

        # First pass: create all group objects
        for group_data in groups_data:
            group = Group(
                id=group_data.get("id"),
                name=group_data.get("name"),
                full_path=group_data.get("full_path"),
                parent_id=group_data.get("parent_id"),
                members=[],
                subgroups=[],
            )
            groups_dict[group.id] = group

        # Second pass: build hierarchy
        for group in groups_dict.values():
            if group.parent_id and group.parent_id in groups_dict:
                groups_dict[group.parent_id].subgroups.append(group)
            else:
                root_groups.append(group)

        # Fetch members if requested
        if fetch_members:
            with console.status("[bold green]Fetching group members..."):
                for group in groups_dict.values():
                    group.members = cls.get_group_members(group.id, active_only=active_members_only)

        return root_groups
