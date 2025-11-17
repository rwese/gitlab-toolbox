"""Pipeline and job data models."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Pipeline:
    """Represents a GitLab CI/CD pipeline."""

    id: int
    iid: int
    project_id: int
    status: str
    ref: str
    sha: str
    web_url: str
    created_at: str
    updated_at: str
    duration: Optional[int]


@dataclass
class Job:
    """Represents a GitLab CI/CD job."""

    id: int
    name: str
    stage: str
    status: str
    ref: str
    created_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    duration: Optional[float]
    web_url: str
