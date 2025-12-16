"""JSON output formatter."""

import json
from dataclasses import asdict
from typing import List

from ..models import Group, Project, MergeRequest, Pipeline, Job, PipelineSchedule


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
