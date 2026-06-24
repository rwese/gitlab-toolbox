"""CLI command modules."""

from .auth import auth_cli
from .ci import ci_cli
from .groups import groups_cli
from .projects import projects_cli
from .merge_requests import mergerequests_cli
from .pipelines import pipelines_cli
from .pipeline_schedules import pipeline_schedules_cli
from .users import whoami_cli

__all__ = [
    "auth_cli",
    "ci_cli",
    "groups_cli",
    "projects_cli",
    "mergerequests_cli",
    "pipelines_cli",
    "pipeline_schedules_cli",
    "whoami_cli",
]
