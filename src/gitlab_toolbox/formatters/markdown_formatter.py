"""Markdown table output formatter."""

from typing import List, Optional

from ..models import CIToken, CIVariable, Group, Job, MergeRequest, Pipeline, Project, SkippedScope


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

            def add_group(group: Group):
                group_path = group.full_path

                if group.members:
                    for member in group.members:
                        lines.append(
                            f"| {group_path} | {member.username} | {member.name} | "
                            f"{member.access_level_description} | {member.state} | "
                            f"{member.membership_state} |"
                        )
                else:
                    lines.append(f"| {group_path} | *No members* | | | | |")

                for subgroup in group.subgroups:
                    add_group(subgroup)

            for group in groups:
                add_group(group)
        else:
            lines = [
                "| Group Path | Group ID |",
                "|------------|----------|",
            ]

            def add_group(group: Group):
                group_path = group.full_path
                lines.append(f"| {group_path} | {group.id} |")

                for subgroup in group.subgroups:
                    add_group(subgroup)

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

    @staticmethod
    def format_ci_variables(
        variables: List[CIVariable],
        skipped: Optional[List[SkippedScope]] = None,
        reveal: bool = False,
    ) -> str:
        """Format CI/CD variables as a Markdown table."""
        value_header = "Value" if reveal else "Value (redacted)"
        lines = [
            f"| Scope | Key | Origin | Defined in | Env | Type | Flags | {value_header} |",
            "|-------|-----|--------|------------|-----|------|-------|-------|",
        ]

        for variable in variables:
            flags = []
            if variable.protected:
                flags.append("protected")
            if variable.masked:
                flags.append("masked")
            if variable.hidden:
                flags.append("hidden")
            if variable.raw:
                flags.append("raw")

            origin = variable.origin
            if variable.origin == "override" and variable.overrides:
                origin = f"override of `{variable.overrides}`"

            value = variable.value if reveal else variable.display_value

            lines.append(
                f"| {variable.scope_path} | `{variable.key}` | {origin} | "
                f"`{variable.defined_in}` | {variable.environment_scope} | "
                f"{variable.variable_type} | {', '.join(flags) or '-'} | {value or '-'} |"
            )

        return "\n".join(lines)

    @staticmethod
    def format_ci_tokens(
        tokens: List[CIToken], skipped: Optional[List[SkippedScope]] = None
    ) -> str:
        """Format CI/CD credentials as a Markdown table."""
        lines = [
            "| Scope | Kind | Name | State | Scopes / Role | Created | Expires | Last used | Last IPs |",
            "|-------|------|------|-------|---------------|---------|---------|-----------|----------|",
        ]

        for token in tokens:
            permissions = list(token.scopes)
            if token.access_level_description:
                permissions.append(f"role={token.access_level_description}")
            if token.can_push is not None:
                permissions.append("push" if token.can_push else "read-only")

            lines.append(
                f"| {token.scope_path} | {token.kind} | {token.name} | {token.state} | "
                f"{', '.join(permissions) or '-'} | {(token.created_at or '-')[:10]} | "
                f"{token.expires_at or 'never'} | {token.last_used_at or 'never'} | "
                f"{', '.join(token.last_used_ips) if token.last_used_ips else '-'} |"
            )

        return "\n".join(lines)
