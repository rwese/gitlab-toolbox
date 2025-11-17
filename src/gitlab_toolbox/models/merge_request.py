"""Merge request data model."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MergeRequest:
    """Represents a GitLab merge request."""

    id: int
    iid: int
    title: str
    description: Optional[str]
    state: str
    author: str
    source_branch: str
    target_branch: str
    web_url: str
    created_at: str
    updated_at: str
    merged_at: Optional[str]
    draft: bool
    work_in_progress: bool
    project_id: Optional[int] = None
