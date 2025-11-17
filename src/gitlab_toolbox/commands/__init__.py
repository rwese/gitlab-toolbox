"""CLI command modules."""

from .groups import groups_cli
from .projects import projects_cli
from .merge_requests import mergerequests_cli
from .pipelines import pipelines_cli

__all__ = ["groups_cli", "projects_cli", "mergerequests_cli", "pipelines_cli"]
