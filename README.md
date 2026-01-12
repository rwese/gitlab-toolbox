# GitLab Toolbox

A comprehensive CLI for GitLab operations using direct HTTP API calls with no external dependencies.

**Repository**: [https://github.com/rwese/gitlab-toolbox](https://github.com/rwese/gitlab-toolbox)

## Install with uv

```bash
# Install directly from GitHub (no clone needed)
uv pip install git+https://github.com/rwese/gitlab-toolbox.git

# Or install as a global tool
uv tool install git+https://github.com/rwese/gitlab-toolbox.git

# Or run directly without installation
uvx gitlab-toolbox --help

# Or install in development mode (from local clone)
uv pip install -e .
```

## Quickstart

```bash
# Install
uv pip install -e .

# Configure (set environment variables or use flags)
export GITLAB_TOKEN=your_token

# List groups
gitlab-toolbox groups list

# List merge requests
gitlab-toolbox mergerequests list --project group/project

# Check pipelines
gitlab-toolbox pipelines list --project group/project

# Get help
gitlab-toolbox --help
```

## Installation

```bash
# Install in development mode
uv pip install -e .

# With dev dependencies (black, ruff, pytest)
uv pip install -e ".[dev]"
```

## Configuration

### Authentication

```bash
# Using environment variable (recommended)
export GITLAB_TOKEN=your_personal_access_token

# Using flag
gitlab-toolbox --token YOUR_TOKEN groups list
```

**Supported token environment variables** (in order of precedence):

- `GITLAB_TOKEN`
- `CI_JOB_TOKEN` (for GitLab CI/CD)
- `GL_TOKEN`

### GitLab Instance

```bash
# Using environment variable
export GITLAB_URL=https://your-gitlab-instance.com

# Using flag
gitlab-toolbox --gitlab-url https://your-gitlab-instance.com groups list
```

### Debug Mode

```bash
# Enable verbose output
gitlab-toolbox --debug mergerequests list

# Or via environment variable
export GITLAB_DEBUG=1
```

## Usage

### Groups

```bash
# List groups (members not fetched by default)
gitlab-toolbox groups list [--format tree|table] [--include-members] [--summary] [--search QUERY] [--limit N]

# Show specific group
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

# Trigger pipelines for MRs
gitlab-toolbox mergerequests list --author your-username --no-drafts --trigger-pipeline

# Find MRs with failed pipelines
gitlab-toolbox mergerequests list --pipeline-status failed --trigger-pipeline
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

### Pipeline Schedules

```bash
# List schedules
gitlab-toolbox pipeline-schedules list --project PROJECT_PATH [--state active|inactive] [--limit N]

# Show schedule details
gitlab-toolbox pipeline-schedules show --project PROJECT_PATH SCHEDULE_ID

# Trigger a schedule
gitlab-toolbox pipeline-schedules trigger --project PROJECT_PATH SCHEDULE_ID
```

## Features

- **Groups & Members**: Explore groups, subgroups, and members with hierarchical visualization
- **Projects**: List and search projects across groups
- **Merge Requests**: View, search, and filter with advanced pipeline status filtering
- **CI/CD Pipelines**: Monitor pipeline status and view jobs
- **Pipeline Schedules**: List, view, and trigger schedules with full details
- **Pipeline Status Filtering**: Filter MRs by latest pipeline status (like GitLab's UI)
- **Performance**: Optimized API calls with date filtering and source type restrictions
- **Search**: Search support for groups, projects, and merge requests

## Common Options

| Option                            | Description                                   |
| --------------------------------- | --------------------------------------------- |
| `--limit N`                       | Limit results (saves time on large instances) |
| `--search QUERY`                  | Search by name/title                          |
| `--pipeline-status STATUS`        | Filter MRs by pipeline status                 |
| `--include-members`               | Fetch group members (groups only)             |
| `--format table\|tree\|json\|csv` | Output format                                 |

## Output

- **STDOUT**: Data output (tables, details, JSON) - ideal for piping
- **STDERR**: Status messages and debug output

```bash
# Data to file, status to terminal
gitlab-toolbox mergerequests list > mrs.txt

# Data through pipe
gitlab-toolbox mergerequests list | grep "failed"
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Format code
black src/

# Lint code
ruff check src/

# Run tests
pytest

# Run CLI
uv run gitlab-toolbox --help
```

## Prerequisites

- Python 3.8+
- GitLab personal access token (for private repositories)
- [uv](https://github.com/astral-sh/uv) package manager

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```
