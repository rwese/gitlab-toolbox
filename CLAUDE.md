# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GitLab Toolbox is a comprehensive Python CLI tool for GitLab operations, providing commands for managing groups, projects, merge requests, and CI/CD pipelines. The tool uses direct HTTP API calls to GitLab for maximum compatibility and no external dependencies.

## Prerequisites

- **Python 3.8+**: Required for the package
- **Python dependencies**: `click` (CLI framework), `rich` (terminal formatting), and `requests` (HTTP client)
- **GitLab Access Token**: Personal access token for authenticated operations (optional for public GitLab.com data)

## Installation & Setup

```bash
# Install in development mode
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
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

## Project Structure

```
src/gitlab_toolbox/
├── cli.py              # Main CLI entry point, registers all command groups
├── api/                # API layer - wraps glab CLI
│   ├── client.py       # Base GitLabClient with pagination support
│   ├── groups.py       # Groups API operations
│   ├── projects.py     # Projects API operations
│   ├── merge_requests.py  # MRs API operations
│   └── pipelines.py    # Pipelines/jobs API operations
├── models/             # Data models (dataclasses)
│   ├── group.py        # Group and GroupMember models
│   ├── project.py      # Project model
│   ├── merge_request.py  # MergeRequest model
│   └── pipeline.py     # Pipeline and Job models
├── commands/           # Click command implementations
│   ├── groups.py       # Groups CLI commands
│   ├── projects.py     # Projects CLI commands
│   ├── merge_requests.py  # MRs CLI commands
│   └── pipelines.py    # Pipelines CLI commands
└── formatters/         # Display formatters
    └── display.py      # Rich-based formatters for all entity types
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

## Adding New Commands

To add a new command domain:

1. Create model in `src/gitlab_toolbox/models/`
2. Create API wrapper in `src/gitlab_toolbox/api/`
3. Add display formatters in `src/gitlab_toolbox/formatters/display.py`
4. Create command module in `src/gitlab_toolbox/commands/`
5. Register command group in `src/gitlab_toolbox/cli.py`

## Important Implementation Details

### GitLab API Access
All GitLab API calls are made via `glab api` commands. The tool assumes `glab` is properly configured with authentication. Error handling in `GitLabClient._run_glab_command()` catches both subprocess failures and JSON parsing errors.

### URL Encoding
Project paths in API calls must be URL-encoded (e.g., `group/project` becomes `group%2Fproject`). This is handled automatically in the API layer using `project_path.replace("/", "%2F")`.

### Group Hierarchy
GitLab groups have a `parent_id` field that establishes hierarchy. Root groups have `parent_id` as null/None. The `GroupsAPI.build_group_tree()` method uses a two-pass algorithm with dictionary lookup for O(1) parent-child linking.
