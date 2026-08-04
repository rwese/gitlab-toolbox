"""CSV output formatter."""

import csv
import io
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

    @staticmethod
    def format_users(users: List[UserProfile]) -> str:
        """Format users as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Username", "Name", "State", "Email", "URL"])
        for user in users:
            data = user.to_dict()
            writer.writerow(
                [
                    user.id,
                    user.username,
                    user.name,
                    user.state or "",
                    data.get("email") or data.get("public_email") or "",
                    user.web_url or "",
                ]
            )
        return output.getvalue()

    @staticmethod
    def format_user_memberships(memberships: List[UserMembership]) -> str:
        """Format user memberships as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Type", "ID", "Name", "Access Level", "Role", "Expires", "URL"])
        for membership in memberships:
            writer.writerow(
                [
                    membership.source_type,
                    membership.source_id,
                    membership.source_full_name,
                    membership.access_level or "",
                    membership.access_level_description or "",
                    membership.expires_at or "",
                    membership.web_url or "",
                ]
            )
        return output.getvalue()

    @staticmethod
    def format_user_counts(counts: UserCounts) -> str:
        """Format user counts as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Name", "Count"])
        for key, value in counts.raw.items():
            writer.writerow([key, value])
        return output.getvalue()

    @staticmethod
    def format_ci_variables(
        variables: List[CIVariable],
        skipped: Optional[List[SkippedScope]] = None,
        reveal: bool = False,
    ) -> str:
        """Format CI/CD variables as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Scope Kind",
                "Scope Path",
                "Key",
                "Environment Scope",
                "Origin",
                "Defined In",
                "Overrides",
                "Inheritance Depth",
                "Type",
                "Protected",
                "Masked",
                "Hidden",
                "Raw",
                "Description",
                "Value" if reveal else "Value Fingerprint",
                "Value Length",
            ]
        )
        for variable in variables:
            writer.writerow(
                [
                    variable.scope_kind,
                    variable.scope_path,
                    variable.key,
                    variable.environment_scope,
                    variable.origin,
                    variable.defined_in,
                    variable.overrides or "",
                    variable.inheritance_depth,
                    variable.variable_type,
                    variable.protected,
                    variable.masked,
                    variable.hidden,
                    variable.raw,
                    variable.description or "",
                    (variable.value or "") if reveal else (variable.value_fingerprint or ""),
                    variable.value_length if variable.value_length is not None else "",
                ]
            )
        return output.getvalue()

    @staticmethod
    def format_ci_tokens(
        tokens: List[CIToken], skipped: Optional[List[SkippedScope]] = None
    ) -> str:
        """Format CI/CD credentials as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Scope Kind",
                "Scope Path",
                "Kind",
                "ID",
                "Name",
                "State",
                "Scopes",
                "Access Level",
                "Role",
                "Created At",
                "Expires At",
                "Days Until Expiry",
                "Last Used At",
                "Last Used IPs",
                "Can Push",
            ]
        )
        for token in tokens:
            writer.writerow(
                [
                    token.scope_kind,
                    token.scope_path,
                    token.kind,
                    token.id if token.id is not None else "",
                    token.name,
                    token.state,
                    " ".join(token.scopes),
                    token.access_level if token.access_level is not None else "",
                    token.access_level_description or "",
                    token.created_at or "",
                    token.expires_at or "",
                    token.days_until_expiry if token.days_until_expiry is not None else "",
                    token.last_used_at or "",
                    " ".join(token.last_used_ips) if token.last_used_ips else "",
                    token.can_push if token.can_push is not None else "",
                ]
            )
        return output.getvalue()
