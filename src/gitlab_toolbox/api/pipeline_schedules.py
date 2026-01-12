"""Pipeline schedules API operations."""

import sys
from typing import List, Optional

from rich.console import Console

from ..models import (
    Pipeline,
    PipelineSchedule,
    PipelineScheduleVariable,
    PipelineScheduleOwner,
    PipelineScheduleLastPipeline,
)
from .client import GitLabClient

console = Console(file=sys.stderr)


class PipelineSchedulesAPI:
    """API wrapper for GitLab CI/CD pipeline schedules operations."""

    @classmethod
    def get_schedules(
        cls,
        project_path: str,
        scope: Optional[str] = None,
        limit: Optional[int] = None,
        include_last_pipeline: bool = False,
    ) -> List[PipelineSchedule]:
        """Fetch pipeline schedules for a project.

        Args:
            project_path: The project path
            scope: Optional scope filter ('active' or 'inactive')
            limit: Maximum number of schedules to fetch

        Returns:
            List of PipelineSchedule objects
        """
        encoded_path = project_path.replace("/", "%2F")
        params = {}
        if scope:
            params["scope"] = scope

        if include_last_pipeline:
            # Use REST API with pipeline fetching for reliable last pipeline data
            return cls._get_schedules_with_rest_fallback(project_path, scope, limit)
        else:
            # Use REST API for fast listing without pipeline details
            with console.status("[bold green]Fetching pipeline schedules..."):
                schedules_data = GitLabClient.paginate(
                    f"projects/{encoded_path}/pipeline_schedules", params, limit=limit
                )

            # Debug: show what we received
            if GitLabClient._debug:
                console.print(f"[dim]Received {len(schedules_data)} schedules[/dim]")
                for i, s in enumerate(schedules_data[:3]):  # Show first 3 for brevity
                    console.print(
                        f"[dim]Schedule {i + 1}: has last_pipeline = {'last_pipeline' in s}, keys = {list(s.keys())}[/dim]"
                    )

            return [cls._parse_schedule(s) for s in schedules_data]

    @classmethod
    def _get_schedules_with_graphql(
        cls, project_path: str, scope: Optional[str] = None, limit: Optional[int] = None
    ) -> List[PipelineSchedule]:
        """Fetch pipeline schedules with last pipeline status using GraphQL."""
        query = """
        query GetPipelineSchedules($projectPath: ID!, $first: Int) {
          project(fullPath: $projectPath) {
            pipelineSchedules(first: $first) {
              nodes {
                id
                description
                ref
                cron
                cronTimezone
                nextRunAt
                active
                createdAt
                updatedAt
                owner {
                  id
                  name
                  username
                  state
                  avatarUrl
                  webUrl
                }
                pipelines(first: 1, sort: CREATED_DESC) {
                  nodes {
                    id
                    sha
                    ref
                    status
                    createdAt
                  }
                }
                variables {
                  nodes {
                    key
                    value
                    variableType
                    raw
                  }
                }
              }
            }
          }
        }
        """

        try:
            with console.status("[bold green]Fetching pipeline schedules with GraphQL..."):
                response = GitLabClient._run_graphql_query(
                    query, {"projectPath": project_path, "first": limit or 100}
                )

            schedules_data = (
                response.get("data", {})
                .get("project", {})
                .get("pipelineSchedules", {})
                .get("nodes", [])
            )

            if GitLabClient._debug:
                console.print(
                    f"[dim]GraphQL response received: {len(schedules_data)} schedules[/dim]"
                )

            # Filter by scope if specified
            if scope:
                schedules_data = [
                    s
                    for s in schedules_data
                    if (s.get("active") if scope == "active" else not s.get("active"))
                ]

            return [cls._parse_schedule_from_graphql(s) for s in schedules_data]

        except Exception as e:
            if GitLabClient._debug:
                console.print(f"[red]GraphQL failed, falling back to REST: {e}[/red]")
            # Fall back to REST with N+1 approach
            return cls._get_schedules_with_rest_fallback(project_path, scope, limit)

    @classmethod
    def _get_schedules_with_rest_fallback(
        cls, project_path: str, scope: Optional[str] = None, limit: Optional[int] = None
    ) -> List[PipelineSchedule]:
        """Fallback method using REST API with N+1 calls for pipeline status."""

        encoded_path = project_path.replace("/", "%2F")
        params = {}
        if scope:
            params["scope"] = scope

        with console.status("[bold green]Fetching pipeline schedules (REST fallback)..."):
            schedules_data = GitLabClient.paginate(
                f"projects/{encoded_path}/pipeline_schedules", params, limit=limit
            )

        schedules = []
        for schedule_data in schedules_data:
            schedule = cls._parse_schedule(schedule_data)

            # Always try to fetch the most recent pipeline for this schedule
            try:
                # Get recent pipelines for this schedule to find the most recent
                # Fetch enough to ensure we get the most recent, with Python sorting as backup
                pipelines = cls.get_schedule_pipelines(project_path, schedule.id, limit=10)
                if pipelines:
                    last_pipeline = PipelineScheduleLastPipeline(
                        id=pipelines[0].id,
                        sha=pipelines[0].sha,
                        ref=pipelines[0].ref,
                        status=pipelines[0].status,
                    )
                    schedule.last_pipeline = last_pipeline
                    if GitLabClient._debug:
                        console.print(
                            f"[dim]Found {len(pipelines)} pipelines for schedule {schedule.id}, using most recent: {last_pipeline.id}[/dim]"
                        )
                        if len(pipelines) > 1:
                            console.print(
                                f"[dim]Other pipeline IDs: {[p.id for p in pipelines[1:]]}[/dim]"
                            )
                elif GitLabClient._debug:
                    console.print(f"[dim]No pipelines found for schedule {schedule.id}[/dim]")
            except Exception as e:
                if GitLabClient._debug:
                    console.print(
                        f"[dim]Error fetching pipelines for schedule {schedule.id}: {e}[/dim]"
                    )

            schedules.append(schedule)

        return schedules

    @staticmethod
    def _parse_schedule_from_graphql(data: dict) -> PipelineSchedule:
        """Parse schedule data from GraphQL response."""
        from ..client import GitLabClient

        if GitLabClient._debug:
            console.print(f"[dim]Parsing GraphQL schedule data: {data}[/dim]")
            console.print(
                f"[dim]Schedule ID: {data.get('id')}, Description: {data.get('description')}[/dim]"
            )
            pipelines_data = data.get("pipelines", {}).get("nodes", [])
            console.print(f"[dim]Pipelines data: {len(pipelines_data)} pipelines found[/dim]")
            if pipelines_data:
                console.print(f"[dim]First pipeline: {pipelines_data[0]}[/dim]")

        # Parse owner
        owner_data = data.get("owner", {})
        owner = PipelineScheduleOwner(
            name=owner_data.get("name"),
            username=owner_data.get("username"),
            id=int(owner_data.get("id", 0)),
            state=owner_data.get("state"),
            avatar_url=owner_data.get("avatarUrl"),
            web_url=owner_data.get("webUrl"),
        )

        # Parse most recent pipeline from pipelines connection
        pipelines_data = data.get("pipelines", {}).get("nodes", [])
        last_pipeline = None
        if pipelines_data:
            pipeline_data = pipelines_data[0]  # Already sorted by CREATED_DESC
            last_pipeline = PipelineScheduleLastPipeline(
                id=int(pipeline_data.get("id", 0)),
                sha=pipeline_data.get("sha"),
                ref=pipeline_data.get("ref"),
                status=pipeline_data.get("status"),
            )
            if GitLabClient._debug:
                console.print(
                    f"[dim]Parsed most recent pipeline: ID={last_pipeline.id}, status={last_pipeline.status}[/dim]"
                )
        elif GitLabClient._debug:
            console.print(f"[dim]No pipelines found for schedule {data.get('id')}[/dim]")

        # Parse variables
        variables_data = data.get("variables", {}).get("nodes", [])
        variables = [
            PipelineScheduleVariable(
                key=var.get("key"),
                variable_type=var.get("variableType"),
                value=var.get("value"),
                raw=var.get("raw", False),
            )
            for var in variables_data
        ]

        return PipelineSchedule(
            id=int(data.get("id", 0)),
            description=data.get("description"),
            ref=data.get("ref"),
            cron=data.get("cron"),
            cron_timezone=data.get("cronTimezone"),
            next_run_at=data.get("nextRunAt"),
            active=data.get("active"),
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt"),
            owner=owner,
            last_pipeline=last_pipeline,
            variables=variables,
        )

        # Parse last pipeline from GraphQL
        last_pipeline_data = data.get("lastPipeline")
        last_pipeline = None
        if last_pipeline_data:
            last_pipeline = PipelineScheduleLastPipeline(
                id=int(last_pipeline_data.get("id", 0)),
                sha=last_pipeline_data.get("sha"),
                ref=last_pipeline_data.get("ref"),
                status=last_pipeline_data.get("status"),
            )

        # Parse variables
        variables_data = data.get("variables", {}).get("nodes", [])
        variables = [
            PipelineScheduleVariable(
                key=var.get("key"),
                variable_type=var.get("variableType"),
                value=var.get("value"),
                raw=var.get("raw", False),
            )
            for var in variables_data
        ]

        return PipelineSchedule(
            id=int(data.get("id", 0)),
            description=data.get("description"),
            ref=data.get("ref"),
            cron=data.get("cron"),
            cron_timezone=data.get("cronTimezone"),
            next_run_at=data.get("nextRunAt"),
            active=data.get("active"),
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt"),
            owner=owner,
            last_pipeline=last_pipeline,
            variables=variables,
        )

    @classmethod
    def get_schedule(cls, project_path: str, schedule_id: int) -> Optional[PipelineSchedule]:
        """Fetch a specific pipeline schedule.

        Args:
            project_path: The project path
            schedule_id: The schedule ID

        Returns:
            PipelineSchedule object or None if not found
        """
        encoded_path = project_path.replace("/", "%2F")

        with console.status(f"[bold green]Fetching pipeline schedule #{schedule_id}..."):
            schedule_data = GitLabClient._run_api_request_optional(
                f"projects/{encoded_path}/pipeline_schedules/{schedule_id}"
            )

        if not schedule_data or isinstance(schedule_data, list):
            return None

        return cls._parse_schedule(schedule_data)

    @classmethod
    def get_schedule_pipelines(
        cls, project_path: str, schedule_id: int, limit: Optional[int] = None
    ) -> List[Pipeline]:
        """Fetch pipelines triggered by a specific schedule.

        Args:
            project_path: The project path
            schedule_id: The schedule ID
            limit: Maximum number of pipelines to fetch

        Returns:
            List of Pipeline objects for this schedule, sorted by creation date descending
        """
        from .pipelines import PipelinesAPI  # Import here to avoid circular import

        encoded_path = project_path.replace("/", "%2F")

        # Add sorting parameter to get most recent first
        # Use sort=desc to ensure most recent pipelines come first
        params = {"sort": "desc"}

        with console.status(f"[bold green]Fetching pipelines for schedule #{schedule_id}..."):
            pipelines_data = GitLabClient.paginate(
                f"projects/{encoded_path}/pipeline_schedules/{schedule_id}/pipelines",
                params,
                limit=limit,
            )

        pipelines = [PipelinesAPI._parse_pipeline(p) for p in pipelines_data]

        # Ensure pipelines are sorted by ID descending (most recent first)
        # since GitLab API sorting might not work as expected
        pipelines.sort(key=lambda p: p.id, reverse=True)

        if GitLabClient._debug and pipelines:
            console.print(
                f"[dim]After sorting, first pipeline: {pipelines[0].id}, last: {pipelines[-1].id}[/dim]"
            )

        return pipelines

    @classmethod
    def trigger_schedule(cls, project_path: str, schedule_id: int) -> Optional[dict]:
        """Trigger a pipeline schedule to run immediately.

        Args:
            project_path: The project path
            schedule_id: The schedule ID

        Returns:
            Pipeline data if successful, None if failed
        """
        encoded_path = project_path.replace("/", "%2F")

        with console.status(f"[bold green]Triggering pipeline schedule #{schedule_id}..."):
            try:
                pipeline_data = GitLabClient._run_api_request(
                    f"projects/{encoded_path}/pipeline_schedules/{schedule_id}/play", method="POST"
                )

                if pipeline_data and isinstance(pipeline_data, dict):
                    console.print(
                        f"[green]✓ Successfully triggered pipeline schedule #{schedule_id}[/green]"
                    )
                    if GitLabClient._debug:
                        console.print(f"[dim]Pipeline created: {pipeline_data}[/dim]")
                    return pipeline_data
                else:
                    console.print(
                        f"[red]✗ Failed to trigger pipeline schedule #{schedule_id}[/red]"
                    )
                    return None

            except Exception as e:
                console.print(
                    f"[red]✗ Error triggering pipeline schedule #{schedule_id}: {e}[/red]"
                )
                return None

    @staticmethod
    def _parse_schedule(data: dict) -> PipelineSchedule:
        """Parse schedule data into PipelineSchedule object.

        Args:
            data: Schedule dictionary from API

        Returns:
            PipelineSchedule object
        """
        # Debug: print the raw data if debug is enabled
        from .client import GitLabClient

        if GitLabClient._debug:
            console.print(f"[dim]Parsing schedule data: {data}[/dim]")

        # Parse owner
        owner_data = data.get("owner", {})
        owner = PipelineScheduleOwner(
            name=owner_data.get("name"),
            username=owner_data.get("username"),
            id=owner_data.get("id"),
            state=owner_data.get("state"),
            avatar_url=owner_data.get("avatar_url"),
            web_url=owner_data.get("web_url"),
        )

        # Parse last pipeline
        last_pipeline_data = data.get("last_pipeline")
        last_pipeline = None
        if GitLabClient._debug:
            console.print(f"[dim]last_pipeline_data: {last_pipeline_data}[/dim]")
        if last_pipeline_data:
            last_pipeline = PipelineScheduleLastPipeline(
                id=last_pipeline_data.get("id"),
                sha=last_pipeline_data.get("sha"),
                ref=last_pipeline_data.get("ref"),
                status=last_pipeline_data.get("status"),
            )

        # Parse variables
        variables_data = data.get("variables", [])
        variables = [
            PipelineScheduleVariable(
                key=var.get("key"),
                variable_type=var.get("variable_type"),
                value=var.get("value"),
                raw=var.get("raw", False),
            )
            for var in variables_data
        ]

        return PipelineSchedule(
            id=data.get("id"),
            description=data.get("description"),
            ref=data.get("ref"),
            cron=data.get("cron"),
            cron_timezone=data.get("cron_timezone"),
            next_run_at=data.get("next_run_at"),
            active=data.get("active"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            owner=owner,
            last_pipeline=last_pipeline,
            variables=variables,
        )
