# GitLab Toolbox

A comprehensive CLI toolbox for GitLab operations, built on top of the `glab` command-line tool.

## Prerequisites

- [glab](https://gitlab.com/gitlab-org/cli) CLI tool installed and configured
- Python 3.8 or higher

## Installation

```bash
# Install in development mode
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

## Configuration

Since this tool wraps the `glab` CLI, it needs to run in the context of a Git repository that's connected to your GitLab instance. You can specify the repository path in two ways:

1. **Using the `--repo-path` flag:**
   ```bash
   gitlab-toolbox --repo-path /path/to/your/gitlab/repo mergerequests list
   ```

2. **Using the `GITLAB_REPO_PATH` environment variable:**
   ```bash
   export GITLAB_REPO_PATH=/path/to/your/gitlab/repo
   gitlab-toolbox mergerequests list
   ```

### Debug Mode

Enable verbose output to see the exact `glab` commands being executed:

```bash
# Using flag
gitlab-toolbox --debug mergerequests list

# Using environment variable
export GITLAB_DEBUG=1
gitlab-toolbox mergerequests list
```

## Usage

### Groups
```bash
# List groups (members not fetched by default for speed)
gitlab-toolbox groups list [--format tree|table] [--include-members] [--summary] [--search QUERY] [--limit N]

# Show specific group (members not fetched by default)
gitlab-toolbox groups show GROUP_PATH [--format tree|table] [--include-members]
```

### Projects
```bash
# List projects
gitlab-toolbox projects list [--group GROUP_PATH] [--search QUERY] [--limit N]

# Show project details
gitlab-toolbox projects show PROJECT_PATH
```

### Merge Requests
```bash
# List merge requests
gitlab-toolbox mergerequests list [--project PROJECT_PATH] [--state opened|merged|closed|all] [--search QUERY] [--limit N]

# Show merge request details
gitlab-toolbox mergerequests show PROJECT_PATH MR_IID

# Trigger pipelines for your merge requests
gitlab-toolbox mergerequests list --author your-username --no-drafts --trigger-pipeline
```

### CI/CD Pipelines
```bash
# List pipelines
gitlab-toolbox pipelines list PROJECT_PATH [--status running|pending|success|failed|canceled|skipped] [--limit N]

# Show pipeline details
gitlab-toolbox pipelines show PROJECT_PATH PIPELINE_ID

# List pipeline jobs
gitlab-toolbox pipelines jobs PROJECT_PATH PIPELINE_ID
```

## Features

- **Groups & Users**: Explore GitLab groups, subgroups, and optionally their members with hierarchical visualization
- **Projects**: List and search projects across groups
- **Merge Requests**: View, search, and filter merge requests
- **CI/CD Pipelines**: Monitor pipeline status, view jobs, and check artifacts
- **Performance**: Global `--limit` parameter stops fetching once enough results are retrieved
- **Search**: Search support for groups, projects, and merge requests where API supports it

## Common Options

- `--limit N`: Limit the number of results fetched (saves time on large instances)
- `--search QUERY`: Search for items by name/title (available for groups, projects, merge requests)
- `--include-members`: Fetch group members (groups only, off by default for better performance)

## Development

```bash
# Format code
black src/

# Lint code
ruff check src/

# Run tests
pytest
```
