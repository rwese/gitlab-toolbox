"""Pipeline schedule data models."""

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class PipelineScheduleVariable:
    """Represents a pipeline schedule variable."""

    key: str
    variable_type: str
    value: str
    raw: bool


@dataclass
class PipelineScheduleInput:
    """Represents a pipeline schedule input.

    Pipeline inputs are a newer GitLab feature (17.11/18.1) that lets a
    schedule pass typed values to the pipeline specification's
    ``spec.inputs`` section. Unlike ``PipelineScheduleVariable``, the value
    is not constrained to a string and can be a number, boolean, array, or
    string depending on the spec.

    The optional ``_destroy`` flag mirrors the GitLab REST API convention for
    removing an input from an existing schedule via ``PUT`` (sending
    ``{"name": "<input>", "_destroy": true}``).
    """

    name: str
    value: Any = None
    _destroy: bool = False


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
    inputs: List[PipelineScheduleInput] = None  # type: ignore[assignment]
