# GitLab Toolbox

A comprehensive CLI toolbox for GitLab operations using direct HTTP API calls.

## Prerequisites

- Python 3.8 or higher
- GitLab personal access token (for private repositories and authenticated operations)
- [uv](https://github.com/astral-sh/uv) package manager (recommended for faster, more reliable installs)

## Installation

```bash
# Install in development mode
uv pip install -e .

# Or install with dev dependencies
uv pip install -e ".[dev]"

# Alternative: sync from lockfile (recommended for reproducible installs)
uv pip sync
```

## Configuration

### Authentication

Configure your GitLab instance and authentication:

1. **GitLab Instance URL:**
   ```bash
   # Using flag (defaults to https://gitlab.com)
   gitlab-toolbox --gitlab-url https://your-gitlab-instance.com groups list

   # Using environment variable
   export GITLAB_URL=https://your-gitlab-instance.com
   gitlab-toolbox groups list
   ```

2. **Personal Access Token:**
   ```bash
   # Using flag
   gitlab-toolbox --token YOUR_TOKEN groups list

   # Using environment variable (recommended for security)
   export GITLAB_TOKEN=YOUR_TOKEN
   gitlab-toolbox groups list
   ```

   Supported token environment variables (in order of precedence):
   - `GITLAB_TOKEN`
   - `CI_JOB_TOKEN` (for GitLab CI/CD)
   - `GL_TOKEN`

### Repository Context (Optional)

For operations that benefit from repository context:

```bash
# Using flag
gitlab-toolbox --repo-path /path/to/your/gitlab/repo mergerequests list

# Using environment variable
export GITLAB_REPO_PATH=/path/to/your/gitlab/repo
gitlab-toolbox mergerequests list
```

### Debug Mode

Enable verbose output to see HTTP requests and responses:

```bash
# Using flag
gitlab-toolbox --debug mergerequests list

# Using environment variable
export GITLAB_DEBUG=1
gitlab-toolbox mergerequests list
```

### Output Behavior

- **STDOUT**: Contains data output (tables, details, JSON) - perfect for piping to other tools
- **STDERR**: Contains status messages, progress info, and debug output - visible in terminal but excluded from pipes

```bash
# Data goes to file, status messages stay in terminal
gitlab-toolbox mergerequests list > mrs.txt

# Only data goes through pipe
gitlab-toolbox mergerequests list | grep "failed"
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
gitlab-toolbox mergerequests list [--project PROJECT_PATH] [--state opened|merged|closed|all] [--search QUERY] [--author USERNAME] [--no-drafts] [--pipeline-status STATUS] [--limit N]

# Show merge request details
gitlab-toolbox mergerequests show PROJECT_PATH MR_IID

# Trigger pipelines for your merge requests
gitlab-toolbox mergerequests list --author your-username --no-drafts --trigger-pipeline

# Find MRs with failed pipelines (considers only the latest pipeline per MR, like GitLab's UI)
gitlab-toolbox mergerequests list --pipeline-status failed --trigger-pipeline

# Find your draft MRs with running pipelines
gitlab-toolbox mergerequests list --author your-username --pipeline-status running
```

### CI/CD Pipelines
```bash
# List pipelines
gitlab-toolbox pipelines list --project PROJECT_PATH [--status running|pending|success|failed|canceled|skipped] [--limit N]

# Show pipeline details
gitlab-toolbox pipelines show --project PROJECT_PATH PIPELINE_ID

# List pipeline jobs
gitlab-toolbox pipelines jobs --project PROJECT_PATH PIPELINE_ID
```

### CI/CD Pipeline Schedules
```bash
# List pipeline schedules (sorted by description, shows active status and most recent pipeline status if available)
gitlab-toolbox pipeline-schedules list --project PROJECT_PATH [--state active|inactive] [--limit N] [--include-last-pipeline]

# Note: --include-last-pipeline fetches the most recent pipeline for each schedule using individual API calls for accuracy

# Show schedule details (includes owner, last pipeline info, and custom variables)
gitlab-toolbox pipeline-schedules show --project PROJECT_PATH SCHEDULE_ID

# Trigger a pipeline schedule to run immediately (creates a new pipeline)
gitlab-toolbox pipeline-schedules trigger --project PROJECT_PATH SCHEDULE_ID [--format table|json|csv]

# List pipelines triggered by a specific schedule
gitlab-toolbox pipeline-schedules pipelines --project PROJECT_PATH SCHEDULE_ID [--limit N]
```

## Features

- **Groups & Users**: Explore GitLab groups, subgroups, and optionally their members with hierarchical visualization
- **Projects**: List and search projects across groups
- **Merge Requests**: View, search, and filter merge requests with advanced pipeline status filtering
- **CI/CD Pipelines**: Monitor pipeline status, view jobs, and check artifacts
- **CI/CD Pipeline Schedules**: List, view, and trigger pipeline schedules with state filtering, schedule status, last pipeline run information, and triggered pipeline history (GraphQL-optimized for efficiency)
- **Pipeline Status Filtering**: Filter merge requests by their latest pipeline status (success, failed, running, etc.), just like GitLab's web interface
- **Performance**: Optimized API calls with date filtering (last 30 days) and source type restrictions (merge request pipelines only) to reduce data transfer
- **Search**: Search support for groups, projects, and merge requests where API supports it

## Common Options

- `--limit N`: Limit the number of results fetched (saves time on large instances)
- `--search QUERY`: Search for items by name/title (available for groups, projects, merge requests)
- `--pipeline-status STATUS`: Filter merge requests by latest pipeline status (success, failed, running, pending, canceled, skipped)
- `--include-members`: Fetch group members (groups only, off by default for better performance)

## Development

```bash
# Sync development dependencies
uv pip sync --extra dev

# Format code
black src/

# Lint code
ruff check src/

# Run tests
pytest

# Generate requirements.txt from pyproject.toml (if needed for CI/CD)
uv pip compile pyproject.toml -o requirements.txt

# Run the CLI (after installing)
uv run gitlab-toolbox --help
```

## CI/CD

For continuous integration, you can use uv with GitHub Actions:

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: "latest"
      - name: Install dependencies
        run: uv pip install -e ".[dev]"
      - name: Run tests
        run: uv run pytest
      - name: Check formatting
        run: uv run black --check src/
      - name: Lint code
        run: uv run ruff check src/
```
