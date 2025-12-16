"""Pipeline schedule data models."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PipelineScheduleVariable:
    """Represents a pipeline schedule variable."""

    key: str
    variable_type: str
    value: str
    raw: bool


@dataclass
class PipelineScheduleOwner:
    """Represents a pipeline schedule owner."""

    name: str
    username: str
    id: int
    state: str
    avatar_url: str
    web_url: str


@dataclass
class PipelineScheduleLastPipeline:
    """Represents the last pipeline triggered by a schedule."""

    id: int
    sha: str
    ref: str
    status: str


@dataclass
class PipelineSchedule:
    """Represents a GitLab CI/CD pipeline schedule."""

    id: int
    description: str
    ref: str
    cron: str
    cron_timezone: str
    next_run_at: str
    active: bool
    created_at: str
    updated_at: str
    owner: PipelineScheduleOwner
    last_pipeline: Optional[PipelineScheduleLastPipeline]
    variables: List[PipelineScheduleVariable]
