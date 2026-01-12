# Coding Standards

## Code Formatting

**Tool**: Black with line-length 100

```bash
uv run black src/
```

## Linting

**Tool**: Ruff with line-length 100, target Python 3.8

```bash
uv run ruff check src/
```

## Type Hints

All functions should include type hints:

```python
def get_groups(limit: int = 100) -> List[Group]:
    ...

def format_table(entities: List[Entity], columns: List[str]) -> Table:
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

## Error Handling

Wrap API calls with proper error handling:

```python
try:
    result = subprocess.run(
        ["glab", "api", "projects"],
        capture_output=True,
        text=True,
        check=True
    )
    return json.loads(result.stdout)
except subprocess.CalledProcessError as e:
    raise GitLabAPIError(f"glab command failed: {e}")
except json.JSONDecodeError as e:
    raise GitLabAPIError(f"Failed to parse JSON response: {e}")
```

## URL Handling

Always handle nullable web_url:

```python
def add_link(entity) -> str:
    if entity.web_url:
        return f"[link={entity.web_url}]🔗[/link]"
    return ""
```

## Click Commands

Use Click's composition patterns:

```python
@click.group()
def projects():
    """Manage GitLab projects"""
    pass

@projects.command("list")
@click.option("--group", help="Filter by group")
@click.option("--limit", default=100, help="Max results")
def list_projects(group: str, limit: int):
    """List projects"""
    api = ProjectsAPI()
    projects = api.list(group=group, limit=limit)
    display_table(projects)
```

## Import Organization

Standard library imports first, then third-party, then local:

```python
import json
from dataclasses import dataclass
from typing import List, Optional

import click
from rich.table import Table

from gitlab_toolbox.api.client import GitLabClient
from gitlab_toolbox.models.project import Project
```

## Testing

- Place tests in `test/` directory
- Use pytest framework
- Test file naming: `test_*.py`
- Aim for meaningful test coverage on new features

## Documentation

- Keep README.md updated
- Document complex logic inline
- Update AGENTS.md when adding new command patterns
