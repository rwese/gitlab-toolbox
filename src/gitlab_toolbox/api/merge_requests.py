"""Merge Requests API operations."""

import sys
from typing import List, Optional

from rich.console import Console

from ..models import MergeRequest
from .client import GitLabClient
from .pipelines import PipelinesAPI

console = Console(file=sys.stderr)


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
        pipeline_status: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[MergeRequest]:
        """Fetch merge requests.

        Args:
            project_path: Optional project path to filter MRs
            state: MR state (opened, merged, closed, all)
            search: Search query for MR titles and descriptions
            author_username: Filter by author's username
            exclude_drafts: Exclude draft/WIP merge requests
            pipeline_status: Filter by pipeline status (success, failed, running, pending, etc.)
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

        # If pipeline status filtering is requested, don't apply limit during fetch
        # We'll fetch more items and filter them, then apply limit afterwards
        fetch_limit = None if pipeline_status else limit

        with console.status("[bold green]Fetching merge requests..."):
            if project_path:
                encoded_path = project_path.replace("/", "%2F")
                mrs_data = GitLabClient.paginate_optional(
                    f"projects/{encoded_path}/merge_requests", params, limit=fetch_limit
                )
                if mrs_data is None:
                    console.print(f"[yellow]Project '{project_path}' not found.[/yellow]")
                    return []
            else:
                mrs_data = GitLabClient.paginate_optional(
                    "merge_requests", params, limit=fetch_limit
                )
                if mrs_data is None:
                    console.print(
                        "[yellow]Unable to fetch merge requests: endpoint not found[/yellow]"
                    )
                    return []

        mrs = [cls._parse_merge_request(mr) for mr in mrs_data]

        # Filter by pipeline status if requested
        if pipeline_status:
            mrs = cls._filter_mrs_by_pipeline_status_ultra_efficient(
                mrs, project_path, pipeline_status
            )
            # Apply limit after filtering
            if limit:
                mrs = mrs[:limit]

        return mrs

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
            mr_data = GitLabClient._run_api_request_optional(
                f"projects/{encoded_path}/merge_requests/{mr_iid}"
            )

        if not mr_data or isinstance(mr_data, list):
            return None

        return cls._parse_merge_request(mr_data)

    @classmethod
    def _filter_mrs_by_pipeline_status_ultra_efficient(
        cls, mrs: List[MergeRequest], project_path: Optional[str], pipeline_status: str
    ) -> List[MergeRequest]:
        """Ultra-efficient filtering of MRs by pipeline status.

        Fetches all pipelines for the project once, then filters MR-related pipelines.
        Much more efficient than fetching pipelines per MR.

        Args:
            mrs: List of merge requests to filter
            project_path: Project path (for pipeline fetching)
            pipeline_status: Desired pipeline status

        Returns:
            Filtered list of merge requests
        """
        if not project_path or not mrs:
            return []

        # Get project info to get the full path
        # For now, assume project_path is already the full path
        # TODO: If we have a mix of projects, we'd need to group by project

        try:
            # Calculate date 30 days ago for efficiency
            from datetime import datetime, timedelta

            thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()

            # Fetch merge request pipelines for the project from the last 30 days
            pipelines = PipelinesAPI.get_pipelines(
                project_path=project_path,
                source="merge_request_event",  # Only fetch merge request pipelines
                created_after=thirty_days_ago,  # Only pipelines from the last 30 days
                limit=1000,  # Fetch enough recent MR pipelines to cover most MRs
            )
            console.print(
                f"[dim]Fetched {len(pipelines)} merge request pipelines from the last 30 days for project {project_path}[/dim]"
            )

            # Build map of MR IID -> latest pipeline status
            # MR pipelines have refs like: refs/merge-requests/123/head
            # Since pipelines are ordered newest first, the first one we encounter per MR is the latest
            mr_latest_pipeline_status = {}

            for pipeline in pipelines:
                # Check if this is an MR pipeline
                if pipeline.ref.startswith("refs/merge-requests/") and pipeline.ref.endswith(
                    "/head"
                ):
                    # Extract MR IID from ref: refs/merge-requests/123/head -> 123
                    try:
                        mr_iid = int(pipeline.ref.split("/")[2])
                        # Keep the first (newest) pipeline status per MR
                        if mr_iid not in mr_latest_pipeline_status:
                            mr_latest_pipeline_status[mr_iid] = pipeline.status
                            if GitLabClient._debug:
                                console.print(
                                    f"[dim]MR !{mr_iid}: latest pipeline status = {pipeline.status}[/dim]"
                                )
                    except (ValueError, IndexError):
                        continue

            # Filter MRs based on their latest pipeline status
            filtered_mrs = []
            for mr in mrs:
                if mr.iid in mr_latest_pipeline_status:
                    latest_status = mr_latest_pipeline_status[mr.iid]
                    if latest_status == pipeline_status:
                        if GitLabClient._debug:
                            console.print(
                                f"[green]MR !{mr.iid}: pipeline status is {pipeline_status} ✓[/green]"
                            )
                        filtered_mrs.append(mr)
                    else:
                        if GitLabClient._debug:
                            console.print(
                                f"[dim]MR !{mr.iid}: pipeline status is {latest_status} (filtered out)[/dim]"
                            )
                else:
                    if GitLabClient._debug:
                        console.print(f"[dim]MR !{mr.iid} has no pipelines[/dim]")

            return filtered_mrs

        except Exception as e:
            console.print(f"[red]Error filtering MRs by pipeline status: {e}[/red]")
            return []

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
