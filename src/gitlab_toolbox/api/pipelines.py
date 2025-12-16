"""Pipelines API operations."""

import sys
from typing import List, Optional

from rich.console import Console

from ..models import Pipeline, Job
from .client import GitLabClient

console = Console(file=sys.stderr)


class PipelinesAPI:
    """API wrapper for GitLab CI/CD pipelines operations."""

    @classmethod
    def get_pipelines(
        cls,
        project_path: str,
        status: Optional[str] = None,
        source: Optional[str] = None,
        created_after: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Pipeline]:
        """Fetch pipelines for a project.

        Args:
            project_path: The project path
            status: Optional pipeline status filter
            source: Optional pipeline source filter (e.g., 'merge_request_event', 'push')
            created_after: Optional ISO 8601 date string to filter pipelines created after this date
            limit: Maximum number of pipelines to fetch

        Returns:
            List of Pipeline objects
        """
        encoded_path = project_path.replace("/", "%2F")
        params = {}
        if status:
            params["status"] = status
        if source:
            params["source"] = source
        if created_after:
            params["created_after"] = created_after

        with console.status("[bold green]Fetching pipelines..."):
            pipelines_data = GitLabClient.paginate(
                f"projects/{encoded_path}/pipelines", params, limit=limit
            )

        return [cls._parse_pipeline(p) for p in pipelines_data]

    @classmethod
    def get_pipeline(cls, project_path: str, pipeline_id: int) -> Optional[Pipeline]:
        """Fetch a specific pipeline.

        Args:
            project_path: The project path
            pipeline_id: The pipeline ID

        Returns:
            Pipeline object or None if not found
        """
        encoded_path = project_path.replace("/", "%2F")

        with console.status(f"[bold green]Fetching pipeline #{pipeline_id}..."):
            pipeline_data = GitLabClient._run_api_request_optional(
                f"projects/{encoded_path}/pipelines/{pipeline_id}"
            )

        if not pipeline_data or isinstance(pipeline_data, list):
            return None

        return cls._parse_pipeline(pipeline_data)

    @classmethod
    def get_pipeline_jobs(cls, project_path: str, pipeline_id: int) -> List[Job]:
        """Fetch jobs for a specific pipeline.

        Args:
            project_path: The project path
            pipeline_id: The pipeline ID

        Returns:
            List of Job objects
        """
        encoded_path = project_path.replace("/", "%2F")

        with console.status(f"[bold green]Fetching jobs for pipeline #{pipeline_id}..."):
            jobs_data = GitLabClient.paginate(
                f"projects/{encoded_path}/pipelines/{pipeline_id}/jobs"
            )

        return [cls._parse_job(j) for j in jobs_data]

    @classmethod
    def trigger_pipeline(cls, project_path: str, ref: str) -> Optional[Pipeline]:
        """Trigger a new pipeline for a specific branch.

        Args:
            project_path: The project path
            ref: The branch or tag name to trigger the pipeline for

        Returns:
            Pipeline object or None if failed
        """
        encoded_path = project_path.replace("/", "%2F")
        params = {"ref": ref}

        pipeline_data = GitLabClient._run_glab_command(
            f"projects/{encoded_path}/pipeline", params, method="POST"
        )

        if not pipeline_data or isinstance(pipeline_data, list):
            return None

        return cls._parse_pipeline(pipeline_data)

    @classmethod
    def get_mr_pipelines(cls, project_path: str, mr_iid: int) -> List[Pipeline]:
        """Fetch pipelines for a specific merge request.

        Args:
            project_path: The project path
            mr_iid: The merge request IID

        Returns:
            List of Pipeline objects for this MR
        """
        encoded_path = project_path.replace("/", "%2F")

        with console.status(f"[bold green]Fetching pipelines for MR !{mr_iid}..."):
            pipelines_data = GitLabClient.paginate(
                f"projects/{encoded_path}/merge_requests/{mr_iid}/pipelines"
            )

        return [cls._parse_pipeline(p) for p in pipelines_data]

    @classmethod
    def trigger_mr_pipeline(cls, project_path: str, mr_iid: int) -> Optional[Pipeline]:
        """Trigger a new pipeline for a merge request.

        Args:
            project_path: The project path
            mr_iid: The merge request IID

        Returns:
            Pipeline object or None if failed
        """
        encoded_path = project_path.replace("/", "%2F")

        pipeline_data = GitLabClient._run_glab_command(
            f"projects/{encoded_path}/merge_requests/{mr_iid}/pipelines", method="POST"
        )

        if not pipeline_data or isinstance(pipeline_data, list):
            return None

        return cls._parse_pipeline(pipeline_data)

    @staticmethod
    def _parse_pipeline(data: dict) -> Pipeline:
        """Parse pipeline data into Pipeline object.

        Args:
            data: Pipeline dictionary from API

        Returns:
            Pipeline object
        """
        return Pipeline(
            id=data.get("id"),
            iid=data.get("iid"),
            project_id=data.get("project_id"),
            status=data.get("status"),
            ref=data.get("ref"),
            sha=data.get("sha"),
            web_url=data.get("web_url"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            duration=data.get("duration"),
        )

    @staticmethod
    def _parse_job(data: dict) -> Job:
        """Parse job data into Job object.

        Args:
            data: Job dictionary from API

        Returns:
            Job object
        """
        return Job(
            id=data.get("id"),
            name=data.get("name"),
            stage=data.get("stage"),
            status=data.get("status"),
            ref=data.get("ref"),
            created_at=data.get("created_at"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            duration=data.get("duration"),
            web_url=data.get("web_url"),
        )
