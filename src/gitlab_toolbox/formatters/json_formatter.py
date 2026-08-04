"""JSON output formatter."""

import json
from dataclasses import asdict
from typing import List, Optional

from ..models import (
    CIToken,
    CIVariable,
    Group,
    SkippedScope,
    Project,
    MergeRequest,
    Pipeline,
    Job,
    PipelineSchedule,
    UserCounts,
    UserMembership,
    UserProfile,
)


class JSONFormatter:
    """Formats entities as JSON."""

    @staticmethod
    def format_groups(groups: List[Group]) -> str:
        """Format groups as JSON.

        Args:
            groups: List of Group objects

        Returns:
            JSON string
        """

        def group_to_dict(group: Group) -> dict:
            """Convert Group to dictionary recursively."""
            return {
                "id": group.id,
                "name": group.name,
                "full_path": group.full_path,
                "parent_id": group.parent_id,
                "members": [asdict(m) for m in group.members],
                "subgroups": [group_to_dict(sg) for sg in group.subgroups],
            }

        return json.dumps([group_to_dict(g) for g in groups], indent=2)

    @staticmethod
    def format_projects(projects: List[Project]) -> str:
        """Format projects as JSON.

        Args:
            projects: List of Project objects

        Returns:
            JSON string
        """
        return json.dumps([asdict(p) for p in projects], indent=2)

    @staticmethod
    def format_merge_requests(mrs: List[MergeRequest]) -> str:
        """Format merge requests as JSON.

        Args:
            mrs: List of MergeRequest objects

        Returns:
            JSON string
        """
        return json.dumps([asdict(mr) for mr in mrs], indent=2)

    @staticmethod
    def format_pipelines(pipelines: List[Pipeline]) -> str:
        """Format pipelines as JSON.

        Args:
            pipelines: List of Pipeline objects

        Returns:
            JSON string
        """
        return json.dumps([asdict(p) for p in pipelines], indent=2)

    @staticmethod
    def format_jobs(jobs: List[Job]) -> str:
        """Format jobs as JSON.

        Args:
            jobs: List of Job objects

        Returns:
            JSON string
        """
        return json.dumps([asdict(j) for j in jobs], indent=2)

    @staticmethod
    def format_pipeline_schedules(schedules: List[PipelineSchedule]) -> str:
        """Format pipeline schedules as JSON.

        Args:
            schedules: List of PipelineSchedule objects

        Returns:
            JSON string
        """
        return json.dumps([asdict(s) for s in schedules], indent=2)

    @staticmethod
    def format_user(user: UserProfile, show_sensitive: bool = False) -> str:
        """Format a user as JSON."""
        return json.dumps(user.to_dict(show_sensitive=show_sensitive), indent=2)

    @staticmethod
    def format_users(users: List[UserProfile], show_sensitive: bool = False) -> str:
        """Format users as JSON."""
        return json.dumps(
            [user.to_dict(show_sensitive=show_sensitive) for user in users],
            indent=2,
        )

    @staticmethod
    def format_user_memberships(memberships: List[UserMembership]) -> str:
        """Format user memberships as JSON."""
        return json.dumps([asdict(membership) for membership in memberships], indent=2)

    @staticmethod
    def format_user_counts(counts: UserCounts) -> str:
        """Format user counts as JSON."""
        return json.dumps(asdict(counts), indent=2)

    @staticmethod
    def format_ci_variables(
        variables: List[CIVariable],
        skipped: Optional[List[SkippedScope]] = None,
        reveal: bool = False,
    ) -> str:
        """Format CI/CD variables as a JSON envelope.

        ``instance_scope_included`` is always False: instance-level variables
        require an admin token, so ``origin`` is relative to the readable group
        chain.
        """
        return json.dumps(
            {
                "instance_scope_included": False,
                "reveal": reveal,
                "skipped": [asdict(s) for s in skipped or []],
                "variables": [v.to_dict() for v in variables],
            },
            indent=2,
        )

    @staticmethod
    def format_ci_tokens(
        tokens: List[CIToken], skipped: Optional[List[SkippedScope]] = None
    ) -> str:
        """Format CI/CD credentials as a JSON envelope."""
        return json.dumps(
            {
                "skipped": [asdict(s) for s in skipped or []],
                "tokens": [t.to_dict() for t in tokens],
            },
            indent=2,
        )
