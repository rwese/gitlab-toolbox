"""Group and member data models."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class GroupMember:
    """Represents a group member."""

    id: int
    username: str
    name: str
    access_level: int
    access_level_description: str
    state: str  # User account state: active, blocked, etc.
    membership_state: str  # Membership state: active, awaiting, etc.


@dataclass
class Group:
    """Represents a GitLab group."""

    id: int
    name: str
    full_path: str
    parent_id: Optional[int]
    members: List[GroupMember]
    subgroups: List["Group"]
