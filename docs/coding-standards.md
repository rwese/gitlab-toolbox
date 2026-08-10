# Coding Standards

## Code Formatting and Linting

Black and Ruff use a 100-character line length. Run the configured tools through
uv:

```bash
uv run black src/
uv run ruff check src/
```

Keep syntax compatible with the Python version declared in `pyproject.toml`.
When changing the supported Python baseline, update `requires-python`, the
classifiers, and the Black and Ruff target versions together.

## Type Hints

Add type hints to new and changed public functions, methods, and data-model
boundaries. Prefer built-in collection annotations when they are compatible with
the supported Python baseline; otherwise use `typing` equivalents.

```python
from typing import List


def get_groups(limit: int = 100) -> List[Group]:
    ...
```

## Dataclasses

Use dataclasses for models:

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class Project:
    id: int
    name: str
    web_url: Optional[str] = None
    path_with_namespace: str = ""
```

## HTTP API Error Handling

Use `GitLabClient` for GitLab API traffic; do not shell out to `glab api`.
`GitLabClient._run_api_request()` handles HTTP requests, JSON decoding, and
GitLab error reporting. Catch `requests.RequestException` or
`requests.HTTPError` only where the command can provide useful recovery.

For expected missing resources, use `_run_api_request_optional()`. For scope
sweeps where 401, 403, or 404 should not stop other work, use
`_run_api_request_safe()` or `paginate_safe()` and surface the returned reason
as skipped output.

```python
import requests

from gitlab_toolbox.api.client import GitLabClient


try:
    project = GitLabClient._run_api_request(f"projects/{project_id}")
except requests.HTTPError:
    # Add command-specific context or let Click report the failure.
    raise
```

## URL Handling

Always handle nullable `web_url`:

```python
def add_link(entity) -> str:
    if entity.web_url:
        return f"[link={entity.web_url}]🔗[/link]"
    return ""
```

URL-encode GitLab project and group paths before putting them into REST endpoint
paths.

## Click Commands

Use Click composition patterns and keep commands responsible for input handling
and orchestration, not HTTP implementation:

```python
@click.group()
def projects():
    """Manage GitLab projects."""


@projects.command("list")
@click.option("--group", help="Filter by group")
@click.option("--limit", default=100, help="Max results")
def list_projects(group: str, limit: int) -> None:
    """List projects."""
    projects = ProjectsAPI.get_projects(group_path=group, limit=limit)
    display_table(projects)
```

## Import Organization

Order imports as standard library, third-party, then local:

```python
from dataclasses import dataclass
from typing import List, Optional

import click
from rich.table import Table

from gitlab_toolbox.api.client import GitLabClient
from gitlab_toolbox.models.project import Project
```

## Testing

- Place tests in `tests/`.
- Use pytest and name test modules `test_*.py`.
- Add meaningful coverage for new behavior, especially API parsing, error paths,
  and CLI output.

## Documentation

- Keep README.md updated.
- Document complex logic inline.
- Update AGENTS.md when adding reusable command patterns.
- Keep the documentation under `docs/` aligned with the implemented API
  transport and project layout.
