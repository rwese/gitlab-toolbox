"""Projects API operations."""

import sys
from typing import List, Optional

from rich.console import Console

from ..models import Project
from .client import GitLabClient

console = Console(file=sys.stderr)


class ProjectsAPI:
    """API wrapper for GitLab projects operations."""

    @classmethod
    def get_projects(
        cls,
        group_path: Optional[str] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        include_subgroups: bool = False,
        sort_by: str = "path",
    ) -> List[Project]:
        """Fetch projects from GitLab.

        Args:
            group_path: Optional group path to filter projects
            search: Optional search query
            limit: Maximum number of projects to fetch
            include_subgroups: Include projects from subgroups
            sort_by: Sort field (path, stars, forks, last_updated)

        Returns:
            List of Project objects
        """
        params = {}
        if search:
            params["search"] = search

        with console.status("[bold green]Fetching projects..."):
            if group_path:
                # Get group ID first
                groups = GitLabClient._run_api_request("groups", {"search": group_path})
                matching_group = next((g for g in groups if g.get("full_path") == group_path), None)
                if not matching_group:
                    console.print(f"[yellow]Group '{group_path}' not found[/yellow]")
                    return []

                group_id = matching_group["id"]

                if include_subgroups:
                    params["include_subgroups"] = "true"

                projects_data = GitLabClient.paginate(
                    f"groups/{group_id}/projects", params, limit=limit
                )
            else:
                projects_data = GitLabClient.paginate("projects", params, limit=limit)

        projects = [cls._parse_project(p) for p in projects_data]

        # Sort projects
        if sort_by == "path":
            projects.sort(key=lambda p: p.path_with_namespace.lower())
        elif sort_by == "stars":
            projects.sort(key=lambda p: p.star_count, reverse=True)
        elif sort_by == "forks":
            projects.sort(key=lambda p: p.forks_count, reverse=True)
        elif sort_by == "last_updated":
            # Projects with web_url have last_activity_at, use it for sorting
            projects.sort(key=lambda p: getattr(p, "last_activity_at", "") or "", reverse=True)

        return projects

    @classmethod
    def get_project(cls, project_path: str) -> Optional[Project]:
        """Fetch a specific project by path.

        Args:
            project_path: The project path (e.g., 'group/project')

        Returns:
            Project object or None if not found
        """
        # URL encode the project path
        encoded_path = project_path.replace("/", "%2F")

        with console.status(f"[bold green]Fetching project {project_path}..."):
            project_data = GitLabClient._run_api_request_optional(f"projects/{encoded_path}")

        if not project_data or isinstance(project_data, list):
            return None

        return cls._parse_project(project_data)

    @classmethod
    def get_project_by_id(cls, project_id: int) -> Optional[Project]:
        """Fetch a specific project by ID.

        Args:
            project_id: The project ID

        Returns:
            Project object or None if not found
        """
        project_data = GitLabClient._run_api_request_optional(f"projects/{project_id}")

        if not project_data or isinstance(project_data, list):
            return None

        return cls._parse_project(project_data)

    @staticmethod
    def _parse_project(data: dict) -> Project:
        """Parse project data into Project object.

        Args:
            data: Project dictionary from API

        Returns:
            Project object
        """
        return Project(
            id=data.get("id"),
            name=data.get("name"),
            path=data.get("path"),
            path_with_namespace=data.get("path_with_namespace"),
            description=data.get("description"),
            visibility=data.get("visibility"),
            default_branch=data.get("default_branch"),
            web_url=data.get("web_url"),
            namespace_path=data.get("namespace", {}).get("full_path", ""),
            star_count=data.get("star_count", 0),
            forks_count=data.get("forks_count", 0),
            last_activity_at=data.get("last_activity_at"),
        )
