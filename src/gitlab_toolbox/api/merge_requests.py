"""Merge Requests API operations."""

from typing import List, Optional

from rich.console import Console

from ..models import MergeRequest
from .client import GitLabClient

console = Console()


class MergeRequestsAPI:
    """API wrapper for GitLab merge requests operations."""

    @classmethod
    def get_merge_requests(
        cls,
        project_path: Optional[str] = None,
        state: str = "opened",
        search: Optional[str] = None,
        author_username: Optional[str] = None,
        exclude_drafts: bool = False,
        limit: Optional[int] = None,
    ) -> List[MergeRequest]:
        """Fetch merge requests.

        Args:
            project_path: Optional project path to filter MRs
            state: MR state (opened, merged, closed, all)
            search: Search query for MR titles and descriptions
            author_username: Filter by author's username
            exclude_drafts: Exclude draft/WIP merge requests
            limit: Maximum number of MRs to fetch

        Returns:
            List of MergeRequest objects
        """
        params = {"state": state}
        if search:
            params["search"] = search
        if author_username:
            params["author_username"] = author_username
        if exclude_drafts:
            params["wip"] = "no"

        with console.status("[bold green]Fetching merge requests..."):
            if project_path:
                encoded_path = project_path.replace("/", "%2F")
                mrs_data = GitLabClient.paginate(
                    f"projects/{encoded_path}/merge_requests", params, limit=limit
                )
            else:
                mrs_data = GitLabClient.paginate("merge_requests", params, limit=limit)

        return [cls._parse_merge_request(mr) for mr in mrs_data]

    @classmethod
    def get_merge_request(cls, project_path: str, mr_iid: int) -> Optional[MergeRequest]:
        """Fetch a specific merge request.

        Args:
            project_path: The project path
            mr_iid: The merge request IID

        Returns:
            MergeRequest object or None if not found
        """
        encoded_path = project_path.replace("/", "%2F")

        with console.status(f"[bold green]Fetching MR !{mr_iid}..."):
            mr_data = GitLabClient._run_glab_command(
                f"projects/{encoded_path}/merge_requests/{mr_iid}"
            )

        if not mr_data or isinstance(mr_data, list):
            return None

        return cls._parse_merge_request(mr_data)

    @staticmethod
    def _parse_merge_request(data: dict) -> MergeRequest:
        """Parse merge request data into MergeRequest object.

        Args:
            data: MR dictionary from API

        Returns:
            MergeRequest object
        """
        author = data.get("author", {})
        return MergeRequest(
            id=data.get("id"),
            iid=data.get("iid"),
            title=data.get("title"),
            description=data.get("description"),
            state=data.get("state"),
            author=author.get("username", "unknown"),
            source_branch=data.get("source_branch"),
            target_branch=data.get("target_branch"),
            web_url=data.get("web_url"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            merged_at=data.get("merged_at"),
            draft=data.get("draft", False),
            work_in_progress=data.get("work_in_progress", False),
            project_id=data.get("project_id"),
        )
