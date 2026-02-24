"""CSV output formatter."""

import csv
import io
from typing import List

from ..models import Group, Project, MergeRequest, Pipeline, Job, PipelineSchedule


class CSVFormatter:
    """Formats entities as CSV."""

    @staticmethod
    def format_groups(groups: List[Group], show_members: bool = True) -> str:
        """Format groups as CSV.

        Args:
            groups: List of Group objects
            show_members: Whether to include member information

        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        if show_members:
            writer.writerow(
                ["Group", "Username", "Name", "Role", "User Status", "Membership Status"]
            )

            def add_group(group: Group):
                group_path = group.full_path

                if group.members:
                    for member in group.members:
                        writer.writerow(
                            [
                                group_path,
                                member.username,
                                member.name,
                                member.access_level_description,
                                member.state,
                                member.membership_state,
                            ]
                        )

                for subgroup in group.subgroups:
                    add_group(subgroup)

            for group in groups:
                add_group(group)
        else:
            writer.writerow(["Group Path", "Group ID"])

            def add_group(group: Group):
                group_path = group.full_path
                writer.writerow([group_path, group.id])

                for subgroup in group.subgroups:
                    add_group(subgroup)

            for group in groups:
                add_group(group)

        return output.getvalue()

    @staticmethod
    def format_projects(projects: List[Project]) -> str:
        """Format projects as CSV.

        Args:
            projects: List of Project objects

        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["Path", "Visibility", "Stars", "Forks", "Description", "URL"])

        for project in projects:
            writer.writerow(
                [
                    project.path_with_namespace,
                    project.visibility,
                    project.star_count,
                    project.forks_count,
                    project.description or "",
                    project.web_url or "",
                ]
            )

        return output.getvalue()

    @staticmethod
    def format_merge_requests(mrs: List[MergeRequest]) -> str:
        """Format merge requests as CSV.

        Args:
            mrs: List of MergeRequest objects

        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            ["IID", "Title", "Author", "State", "Source Branch", "Target Branch", "Draft", "URL"]
        )

        for mr in mrs:
            writer.writerow(
                [
                    mr.iid,
                    mr.title,
                    mr.author,
                    mr.state,
                    mr.source_branch,
                    mr.target_branch,
                    "Yes" if mr.draft or mr.work_in_progress else "No",
                    mr.web_url or "",
                ]
            )

        return output.getvalue()

    @staticmethod
    def format_pipelines(pipelines: List[Pipeline]) -> str:
        """Format pipelines as CSV.

        Args:
            pipelines: List of Pipeline objects

        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["ID", "Status", "Ref", "SHA", "Duration", "Created", "URL"])

        for pipeline in pipelines:
            writer.writerow(
                [
                    pipeline.id,
                    pipeline.status,
                    pipeline.ref,
                    pipeline.sha[:8],
                    pipeline.duration if pipeline.duration else "",
                    pipeline.created_at,
                    pipeline.web_url or "",
                ]
            )

        return output.getvalue()

    @staticmethod
    def format_jobs(jobs: List[Job]) -> str:
        """Format jobs as CSV.

        Args:
            jobs: List of Job objects

        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["Name", "Stage", "Status", "Duration", "Started", "URL"])

        for job in jobs:
            writer.writerow(
                [
                    job.name,
                    job.stage,
                    job.status,
                    job.duration if job.duration else "",
                    job.started_at or "",
                    job.web_url or "",
                ]
            )

        return output.getvalue()

    @staticmethod
    def format_pipeline_schedules(schedules: List[PipelineSchedule]) -> str:
        """Format pipeline schedules as CSV.

        Args:
            schedules: List of PipelineSchedule objects

        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            ["ID", "Description", "Ref", "Cron", "Timezone", "Next Run", "Active", "Owner"]
        )

        for schedule in schedules:
            writer.writerow(
                [
                    schedule.id,
                    schedule.description,
                    schedule.ref,
                    schedule.cron,
                    schedule.cron_timezone,
                    schedule.next_run_at,
                    "Yes" if schedule.active else "No",
                    schedule.owner.username if schedule.owner else "",
                ]
            )

        return output.getvalue()
