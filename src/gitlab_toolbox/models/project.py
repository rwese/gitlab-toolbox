"""Project data model."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Project:
    """Represents a GitLab project."""

    id: int
    name: str
    path: str
    path_with_namespace: str
    description: Optional[str]
    visibility: str
    default_branch: Optional[str]
    web_url: str
    namespace_path: str
    star_count: int
    forks_count: int
