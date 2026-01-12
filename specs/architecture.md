# Architecture Specification

## Overview

GitLab Toolbox follows a layered architecture with clear separation of concerns between CLI handling, API communication, data modeling, and presentation.

## Layer Structure

```
src/gitlab_toolbox/
├── cli.py                    # Main CLI entry point
├── api/                      # API layer - wraps glab CLI
├── models/                   # Data models (dataclasses)
├── commands/                 # Click command implementations
└── formatters/               # Display formatters
```

## Layer Responsibilities

### CLI Layer (`commands/`)

- Click-based command definitions
- User input handling
- Orchestrates API calls
- Format selection

### API Layer (`api/`)

- Wraps `glab api` commands
- Handles pagination (100 items per page)
- Returns structured data
- Error handling

### Model Layer (`models/`)

- Dataclasses defining domain models
- GitLab entity representations
- Type hints and validation

### Presentation Layer (`formatters/`)

- Rich-based formatters (tables, trees, detailed views)
- CSV, JSON, Markdown output
- Clickable link support

## Key Design Patterns

### 1. API Pagination with Limits

```python
GitLabClient.paginate():
- Handles GitLab API pagination (100 items per page)
- Supports global --limit parameter
- Stops fetching when limit reached
```

### 2. Hierarchical Processing

Groups use a two-pass algorithm:

1. Fetch all groups as flat list
2. Build parent-child relationships using `parent_id`
3. Dictionary lookup for O(1) linking

### 3. Opt-in Member Fetching

- Group members NOT fetched by default
- Use `--include-members` flag
- Better performance for large groups

### 4. Modular Commands

Each domain has its own command module:

- `groups.py`
- `projects.py`
- `mergerequests.py`
- `pipelines.py`
- `pipeline_schedules.py`

## Access Level Mapping

GitLab access levels are numeric (0-50):

- 0: No access
- 10: Guest
- 20: Reporter
- 30: Developer
- 40: Maintainer
- 50: Owner

Always translate to human-readable descriptions.

## Web URL Handling

Always handle `web_url` fields that may be `None`:

```python
url = entity.web_url if entity.web_url else ""
link = f"[link={url}]🔗[/link]" if url else ""
```
