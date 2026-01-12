# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Repository**: [https://github.com/rwese/gitlab-toolbox](https://github.com/rwese/gitlab-toolbox)

## Project Overview

GitLab Toolbox is a comprehensive Python CLI tool for GitLab operations, providing commands for managing groups, projects, merge requests, and CI/CD pipelines. The tool uses direct HTTP API calls to GitLab for maximum compatibility and no external dependencies.

## Prerequisites

- **Python 3.8+**: Required for the package
- **Python dependencies**: `click` (CLI framework), `rich` (terminal formatting), and `requests` (HTTP client)
- **uv**: Modern Python package manager (preferred over pip)
- **GitLab Access Token**: Personal access token for authenticated operations (optional for public GitLab.com data)

## Installation & Setup

```bash
# Install in development mode with uv
uv pip install -e .

# Or install with dev dependencies
uv pip install -e ".[dev]"

# Run without installing
uv run gitlab-toolbox --help
```

After installation, the `gitlab-toolbox` command will be available globally.

## Common Commands

### Groups

```bash
# List groups (members NOT fetched by default for speed)
gitlab-toolbox groups list [--format tree|table] [--include-members] [--summary] [--search QUERY] [--limit N]

# Show specific group
gitlab-toolbox groups show GROUP_PATH [--format tree|table] [--include-members]
```

### Projects

```bash
gitlab-toolbox projects list [--group GROUP_PATH] [--search QUERY] [--limit N]
gitlab-toolbox projects show PROJECT_PATH
```

### Merge Requests

```bash
gitlab-toolbox mergerequests list [--project PROJECT_PATH] [--state opened|merged|closed|all] [--search QUERY] [--author USERNAME] [--no-drafts] [--pipeline-status STATUS] [--limit N]
gitlab-toolbox mergerequests show PROJECT_PATH MR_IID
```

### CI/CD Pipelines

```bash
gitlab-toolbox pipelines list PROJECT_PATH [--status running|pending|success|failed|canceled|skipped] [--limit N]
gitlab-toolbox pipelines show PROJECT_PATH PIPELINE_ID
gitlab-toolbox pipelines jobs PROJECT_PATH PIPELINE_ID
```

### Pipeline Schedules

```bash
gitlab-toolbox pipeline-schedules list --project PROJECT_PATH [--state active|inactive] [--limit N]
gitlab-toolbox pipeline-schedules show --project PROJECT_PATH SCHEDULE_ID
gitlab-toolbox pipeline-schedules trigger --project PROJECT_PATH SCHEDULE_ID
```

## Project Structure

```
src/gitlab_toolbox/
├── cli.py                    # Main CLI entry point, registers all command groups
├── api/                      # API layer - wraps glab CLI
│   ├── client.py             # Base GitLabClient with pagination support
│   ├── groups.py             # Groups API operations
│   ├── projects.py           # Projects API operations
│   ├── merge_requests.py     # MRs API operations
│   ├── pipelines.py          # Pipelines/jobs API operations
│   └── pipeline_schedules.py # Pipeline schedules API operations
├── models/                   # Data models (dataclasses)
│   ├── group.py              # Group and GroupMember models
│   ├── project.py            # Project model
│   ├── merge_request.py      # MergeRequest model
│   ├── pipeline.py           # Pipeline and Job models
│   └── pipeline_schedule.py  # PipelineSchedule model
├── commands/                 # Click command implementations
│   ├── groups.py             # Groups CLI commands
│   ├── projects.py           # Projects CLI commands
│   ├── merge_requests.py     # MRs CLI commands
│   ├── pipelines.py          # Pipelines CLI commands
│   └── pipeline_schedules.py # Pipeline schedules CLI commands
└── formatters/               # Display formatters
    ├── display.py            # Rich-based formatters for tables and details
    ├── csv_formatter.py      # CSV output formatter
    ├── json_formatter.py     # JSON output formatter
    ├── markdown_formatter.py # Markdown output formatter
    ├── generic_handlers.py   # Generic format handlers
    └── format_decorator.py   # Format selection decorator
```

## Architecture

The codebase follows a layered architecture with clear separation of concerns:

1. **CLI Layer** (`commands/`): Click-based command definitions that handle user input and orchestrate API calls
2. **API Layer** (`api/`): Wraps `glab api` commands, handles pagination, and returns structured data
3. **Model Layer** (`models/`): Dataclasses that define the domain model for GitLab entities
4. **Presentation Layer** (`formatters/`): Rich-based formatters for displaying data as tables, trees, or detailed views

### Key Design Patterns

1. **API Pagination with Limits**: `GitLabClient.paginate()` handles GitLab API pagination (100 items per page) and supports a global `--limit` parameter to stop fetching once enough results are retrieved
2. **Hierarchical Processing**: Groups use a two-pass algorithm to build parent-child relationships from flat API data
3. **Opt-in Member Fetching**: Group members are NOT fetched by default for better performance. Use `--include-members` to fetch them
4. **Search Support**: All APIs that support search (groups, projects, merge requests) expose it via `--search` parameter
5. **Access Level Mapping**: Translates numeric GitLab access levels (0-50) to human-readable descriptions
6. **Modular Commands**: Each domain (groups, projects, mergerequests, pipelines) has its own command module for easy extension

## Key Learnings

### Rich Clickable Links

To add clickable links in Rich table outputs, use the `[link=URL]text[/link]` syntax:

```python
# In display.py formatters
link = f"[link={entity.web_url}]🔗[/link]" if entity.web_url else ""
table.add_column("URL", style="dim", no_wrap=True)
table.add_row(..., link)
```

This creates clickable 🔗 links that open the URL in the browser when clicked in a compatible terminal.

### Consistent Formatter Patterns

When adding columns to formatters, follow these patterns:

**Rich Display (`display.py`):**

- Add column with `table.add_column("Name", style="...")`
- Create link with conditional: `link = f"[link={obj.web_url}]🔗[/link]" if obj.web_url else ""`
- Add row with the link as last parameter

**CSV Formatter (`csv_formatter.py`):**

- Add column name to header: `writer.writerow([..., "URL"])`
- Add value to row: `obj.web_url or ""`

### Web URL Handling

Always handle `web_url` fields that may be `None`:

```python
# Safe access pattern
url = entity.web_url if entity.web_url else ""
link = f"[link={url}]🔗[/link]" if url else ""
```

## Development

### Code Formatting

```bash
black src/
```

### Linting

```bash
ruff check src/
```

### Testing

```bash
pytest
```

Or using uv to run commands in the project environment:

```bash
uv run pytest
uv run black src/
uv run ruff check src/
```

## Adding New Commands

To add a new command domain:

1. Create model in `src/gitlab_toolbox/models/`
2. Create API wrapper in `src/gitlab_toolbox/api/`
3. Add display formatters in `src/gitlab_toolbox/formatters/display.py`
4. Add CSV formatter in `src/gitlab_toolbox/formatters/csv_formatter.py`
5. Create command module in `src/gitlab_toolbox/commands/`
6. Register command group in `src/gitlab_toolbox/cli.py`

## Important Implementation Details

### GitLab API Access

All GitLab API calls are made via `glab api` commands. The tool assumes `glab` is properly configured with authentication. Error handling in `GitLabClient._run_glab_command()` catches both subprocess failures and JSON parsing errors.

### URL Encoding

Project paths in API calls must be URL-encoded (e.g., `group/project` becomes `group%2Fproject`). This is handled automatically in the API layer using `project_path.replace("/", "%2F")`.

### Group Hierarchy

GitLab groups have a `parent_id` field that establishes hierarchy. Root groups have `parent_id` as null/None. The `GroupsAPI.build_group_tree()` method uses a two-pass algorithm with dictionary lookup for O(1) parent-child linking.
