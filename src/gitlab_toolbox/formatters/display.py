"""Display formatters for various GitLab entities."""

from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich import box

from ..models import Group, Project, MergeRequest, Pipeline, Job

console = Console()


class DisplayFormatter:
    """Formats and displays GitLab entities."""

    # Groups display methods
    @staticmethod
    def display_groups_as_table(groups: List[Group], show_members: bool = True):
        """Display groups and members as a table."""
        if show_members:
            # Detailed table with member information
            table = Table(
                title="GitLab Groups and Members",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold magenta",
            )

            table.add_column("Group", style="cyan", no_wrap=False)
            table.add_column("Username", style="yellow")
            table.add_column("Name", style="white")
            table.add_column("Role", style="green")
            table.add_column("User Status", style="blue")
            table.add_column("Membership", style="magenta")

            def add_group_to_table(group: Group, indent: int = 0):
                prefix = "  " * indent + ("└─ " if indent > 0 else "")
                group_path = f"{prefix}{group.full_path}"

                if group.members:
                    for i, member in enumerate(group.members):
                        # Show group name only for first member
                        group_col = group_path if i == 0 else ""
                        table.add_row(
                            group_col,
                            member.username,
                            member.name,
                            member.access_level_description,
                            member.state,
                            member.membership_state,
                        )
                else:
                    table.add_row(group_path, "[dim]No members[/dim]", "", "", "", "")

                for subgroup in group.subgroups:
                    add_group_to_table(subgroup, indent + 1)

            for group in groups:
                add_group_to_table(group)
        else:
            # Simple table without members
            table = Table(
                title="GitLab Groups",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold magenta",
            )

            table.add_column("Group Path", style="cyan", no_wrap=False)
            table.add_column("Group ID", style="dim")

            def add_group_to_table(group: Group, indent: int = 0):
                prefix = "  " * indent + ("└─ " if indent > 0 else "")
                group_path = f"{prefix}{group.full_path}"
                table.add_row(group_path, str(group.id))

                for subgroup in group.subgroups:
                    add_group_to_table(subgroup, indent + 1)

            for group in groups:
                add_group_to_table(group)

        console.print(table)

    @staticmethod
    def display_groups_as_tree(groups: List[Group], show_members: bool = True):
        """Display groups and members as a tree."""
        tree = Tree("[bold cyan]GitLab Groups[/bold cyan]", guide_style="dim")

        def add_group_to_tree(parent_tree: Tree, group: Group):
            group_label = f"[cyan]{group.name}[/cyan] [dim]({group.full_path})[/dim]"
            group_branch = parent_tree.add(group_label)

            if show_members and group.members:
                members_branch = group_branch.add("[green]👥 Members[/green]")
                for member in group.members:
                    state_indicator = (
                        "[green]●[/green]" if member.state == "active" else "[red]●[/red]"
                    )
                    members_branch.add(
                        f"{state_indicator} [yellow]{member.username}[/yellow] - {member.name} "
                        f"[dim]({member.access_level_description})[/dim]"
                    )

            for subgroup in group.subgroups:
                add_group_to_tree(group_branch, subgroup)

        for group in groups:
            add_group_to_tree(tree, group)

        console.print(tree)

    @staticmethod
    def display_groups_summary(groups: List[Group]):
        """Display a summary of groups and members."""

        def count_groups_and_members(groups_list: List[Group]) -> tuple:
            total_groups = len(groups_list)
            total_members = sum(len(g.members) for g in groups_list)

            for group in groups_list:
                sub_groups, sub_members = count_groups_and_members(group.subgroups)
                total_groups += sub_groups
                total_members += sub_members

            return total_groups, total_members

        total_groups, total_members = count_groups_and_members(groups)

        summary = Panel(
            f"[bold]Total Groups:[/bold] {total_groups}\n"
            f"[bold]Total Members:[/bold] {total_members}",
            title="Summary",
            border_style="blue",
        )
        console.print(summary)

    # Projects display methods
    @staticmethod
    def display_projects_table(projects: List[Project]):
        """Display projects as a table."""
        table = Table(
            title="GitLab Projects",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )

        table.add_column("Path", style="cyan")
        table.add_column("Visibility", style="yellow")
        table.add_column("Stars", justify="right", style="green")
        table.add_column("Forks", justify="right", style="blue")
        table.add_column("Description", style="dim", no_wrap=False)

        for project in projects:
            table.add_row(
                project.path_with_namespace,
                project.visibility,
                str(project.star_count),
                str(project.forks_count),
                project.description or "",
            )

        console.print(table)

    @staticmethod
    def display_project_details(project: Project):
        """Display detailed information about a project."""
        details = f"""[bold cyan]{project.name}[/bold cyan]
[dim]{project.path_with_namespace}[/dim]

[bold]Description:[/bold] {project.description or 'N/A'}
[bold]Visibility:[/bold] {project.visibility}
[bold]Default Branch:[/bold] {project.default_branch or 'N/A'}
[bold]Stars:[/bold] {project.star_count}
[bold]Forks:[/bold] {project.forks_count}
[bold]URL:[/bold] {project.web_url}"""

        panel = Panel(details, title="Project Details", border_style="blue")
        console.print(panel)

    # Merge Requests display methods
    @staticmethod
    def display_merge_requests_table(mrs: List[MergeRequest]):
        """Display merge requests as a table."""
        table = Table(
            title="Merge Requests",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )

        table.add_column("IID", justify="right", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Author", style="yellow")
        table.add_column("State", style="green")
        table.add_column("Source → Target", style="blue")
        table.add_column("Draft", justify="center", style="red")

        for mr in mrs:
            draft_marker = "✓" if mr.draft or mr.work_in_progress else ""
            state_color = {
                "opened": "[green]opened[/green]",
                "merged": "[blue]merged[/blue]",
                "closed": "[red]closed[/red]",
            }.get(mr.state, mr.state)

            table.add_row(
                f"!{mr.iid}",
                mr.title,
                mr.author,
                state_color,
                f"{mr.source_branch} → {mr.target_branch}",
                draft_marker,
            )

        console.print(table)

    @staticmethod
    def display_merge_request_details(mr: MergeRequest):
        """Display detailed information about a merge request."""
        details = f"""[bold cyan]!{mr.iid} - {mr.title}[/bold cyan]

[bold]State:[/bold] {mr.state}
[bold]Author:[/bold] {mr.author}
[bold]Source Branch:[/bold] {mr.source_branch}
[bold]Target Branch:[/bold] {mr.target_branch}
[bold]Draft:[/bold] {mr.draft or mr.work_in_progress}
[bold]Created:[/bold] {mr.created_at}
[bold]Updated:[/bold] {mr.updated_at}
[bold]Merged:[/bold] {mr.merged_at or 'N/A'}
[bold]URL:[/bold] {mr.web_url}

[bold]Description:[/bold]
{mr.description or 'No description'}"""

        panel = Panel(details, title="Merge Request Details", border_style="blue")
        console.print(panel)

    # Pipelines display methods
    @staticmethod
    def display_pipelines_table(pipelines: List[Pipeline]):
        """Display pipelines as a table."""
        table = Table(
            title="CI/CD Pipelines",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )

        table.add_column("ID", justify="right", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Ref", style="yellow")
        table.add_column("SHA", style="dim")
        table.add_column("Duration", justify="right", style="green")
        table.add_column("Created", style="blue")

        for pipeline in pipelines:
            status_color = {
                "success": "[green]success[/green]",
                "failed": "[red]failed[/red]",
                "running": "[yellow]running[/yellow]",
                "pending": "[dim]pending[/dim]",
                "canceled": "[dim]canceled[/dim]",
                "skipped": "[dim]skipped[/dim]",
            }.get(pipeline.status, pipeline.status)

            duration = f"{pipeline.duration}s" if pipeline.duration else "N/A"

            table.add_row(
                f"#{pipeline.id}",
                status_color,
                pipeline.ref,
                pipeline.sha[:8],
                duration,
                pipeline.created_at,
            )

        console.print(table)

    @staticmethod
    def display_pipeline_jobs(jobs: List[Job]):
        """Display pipeline jobs as a table."""
        table = Table(
            title="Pipeline Jobs",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )

        table.add_column("Name", style="cyan")
        table.add_column("Stage", style="yellow")
        table.add_column("Status", style="white")
        table.add_column("Duration", justify="right", style="green")
        table.add_column("Started", style="blue")

        for job in jobs:
            status_color = {
                "success": "[green]success[/green]",
                "failed": "[red]failed[/red]",
                "running": "[yellow]running[/yellow]",
                "pending": "[dim]pending[/dim]",
                "canceled": "[dim]canceled[/dim]",
                "skipped": "[dim]skipped[/dim]",
            }.get(job.status, job.status)

            duration = f"{job.duration:.1f}s" if job.duration else "N/A"

            table.add_row(
                job.name,
                job.stage,
                status_color,
                duration,
                job.started_at or "N/A",
            )

        console.print(table)
