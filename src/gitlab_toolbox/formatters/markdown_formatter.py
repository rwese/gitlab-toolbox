"""Markdown table output formatter."""

from typing import List

from ..models import Group, Project, MergeRequest, Pipeline, Job


class MarkdownFormatter:
    """Formats entities as Markdown tables."""

    @staticmethod
    def format_groups(groups: List[Group], show_members: bool = True) -> str:
        """Format groups as Markdown table.

        Args:
            groups: List of Group objects
            show_members: Whether to include member information

        Returns:
            Markdown table string
        """
        if show_members:
            lines = [
                "| Group | Username | Name | Role | User Status | Membership |",
                "|-------|----------|------|------|-------------|------------|",
            ]

            def add_group(group: Group, indent: int = 0):
                prefix = "  " * indent + ("└─ " if indent > 0 else "")
                group_path = f"{prefix}{group.full_path}"

                if group.members:
                    for i, member in enumerate(group.members):
                        # Show group name only for first member
                        group_col = group_path if i == 0 else ""
                        lines.append(
                            f"| {group_col} | {member.username} | {member.name} | "
                            f"{member.access_level_description} | {member.state} | "
                            f"{member.membership_state} |"
                        )
                else:
                    lines.append(f"| {group_path} | *No members* | | | | |")

                for subgroup in group.subgroups:
                    add_group(subgroup, indent + 1)

            for group in groups:
                add_group(group)
        else:
            lines = [
                "| Group Path | Group ID |",
                "|------------|----------|",
            ]

            def add_group(group: Group, indent: int = 0):
                prefix = "  " * indent + ("└─ " if indent > 0 else "")
                group_path = f"{prefix}{group.full_path}"
                lines.append(f"| {group_path} | {group.id} |")

                for subgroup in group.subgroups:
                    add_group(subgroup, indent + 1)

            for group in groups:
                add_group(group)

        return "\n".join(lines)

    @staticmethod
    def format_projects(projects: List[Project]) -> str:
        """Format projects as Markdown table.

        Args:
            projects: List of Project objects

        Returns:
            Markdown table string
        """
        lines = [
            "| Path | Visibility | Stars | Forks | Description |",
            "|------|------------|-------|-------|-------------|",
        ]

        for project in projects:
            desc = (project.description or "").replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {project.path_with_namespace} | {project.visibility} | "
                f"{project.star_count} | {project.forks_count} | {desc} |"
            )

        return "\n".join(lines)

    @staticmethod
    def format_merge_requests(mrs: List[MergeRequest]) -> str:
        """Format merge requests as Markdown table.

        Args:
            mrs: List of MergeRequest objects

        Returns:
            Markdown table string
        """
        lines = [
            "| IID | Title | Author | State | Source → Target | Draft |",
            "|-----|-------|--------|-------|-----------------|-------|",
        ]

        for mr in mrs:
            title = mr.title.replace("|", "\\|")
            draft_marker = "✓" if mr.draft or mr.work_in_progress else ""
            lines.append(
                f"| !{mr.iid} | {title} | {mr.author} | {mr.state} | "
                f"{mr.source_branch} → {mr.target_branch} | {draft_marker} |"
            )

        return "\n".join(lines)

    @staticmethod
    def format_pipelines(pipelines: List[Pipeline]) -> str:
        """Format pipelines as Markdown table.

        Args:
            pipelines: List of Pipeline objects

        Returns:
            Markdown table string
        """
        lines = [
            "| ID | Status | Ref | SHA | Duration | Created |",
            "|----|--------|-----|-----|----------|---------|",
        ]

        for pipeline in pipelines:
            duration = f"{pipeline.duration}s" if pipeline.duration else "N/A"
            lines.append(
                f"| #{pipeline.id} | {pipeline.status} | {pipeline.ref} | "
                f"{pipeline.sha[:8]} | {duration} | {pipeline.created_at} |"
            )

        return "\n".join(lines)

    @staticmethod
    def format_jobs(jobs: List[Job]) -> str:
        """Format jobs as Markdown table.

        Args:
            jobs: List of Job objects

        Returns:
            Markdown table string
        """
        lines = [
            "| Name | Stage | Status | Duration | Started |",
            "|------|-------|--------|----------|---------|",
        ]

        for job in jobs:
            duration = f"{job.duration:.1f}s" if job.duration else "N/A"
            started = job.started_at or "N/A"
            lines.append(f"| {job.name} | {job.stage} | {job.status} | {duration} | {started} |")

        return "\n".join(lines)
