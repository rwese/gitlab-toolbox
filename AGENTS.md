# GitLab Toolbox - Agent Instructions

**Repository**: [https://github.com/rwese/gitlab-toolbox](https://github.com/rwese/gitlab-toolbox)

A Python CLI tool for GitLab operations using direct HTTP API calls via `glab`.

## Design Philosophy

This tool is designed for **scripting and shell exploration**. All commands should:

- Work well when piped/scripted (output to stdout/stderr appropriately)
- Support `--dry-run` for safe testing
- Support `--output` for file-based workflows
- Use JSON as the primary machine-readable format
- Use Rich formatting for human-readable table output in interactive shells
- Avoid interactive prompts (except optional `--yes` confirmations when necessary)

## Project Specifications

Reference these documents for detailed guidance:

- [Architecture](specs/architecture.md) - Layer structure and design patterns
- [Coding Standards](specs/coding-standards.md) - Formatting, linting, and patterns
- [Git Workflow](specs/git-workflow.md) - Branch naming and commit conventions

## Quick Start

```bash
# Development commands
uv run pytest          # Run tests
uv run black src/      # Format code
uv run ruff check src/ # Lint code

# Run the tool
uv run gitlab-toolbox --help
```

## Project Structure

```
src/gitlab_toolbox/
├── cli.py              # Main entry point
├── api/               # API wrappers (glab)
├── models/            # Data models (dataclasses)
├── commands/          # Click command implementations
└── formatters/        # Output formatters (Rich, CSV, JSON, Markdown)
```

## Key Guidelines

### 1. GitLab API Patterns

- Use `glab api` commands (not direct HTTP)
- URL-encode project paths: `group/project` → `group%2Fproject`
- Groups use `parent_id` for hierarchy (two-pass algorithm)

### 2. Output Design

- **stdout**: Machine-readable output (JSON, CSV, raw data)
- **stderr**: Status messages, progress, user feedback
- Rich tables for interactive shell display (auto-detected via TTY)
- JSON output when piped/scripted

```python
link = f"[link={entity.web_url}]🔗[/link]" if entity.web_url else ""
```

### 3. Command Design

All commands should support:

```bash
# Script-friendly: output to file
gitlab-toolbox pipeline-schedules export -o schedules.json

# Dry-run for safe testing
gitlab-toolbox pipeline-schedules import -i schedules.json --dry-run

# JSON output for piping
gitlab-toolbox pipeline-schedules list --output json | jq '.[] | .id'
```

### 4. Adding New Commands

1. Create model in `models/`
2. Create API wrapper in `api/`
3. Add formatters in `formatters/`
4. Create command in `commands/`
5. Register in `cli.py`

### 5. Conventional Commits

- Follow the repository-local commit format from `specs/git-workflow.md`: `<type>(<scope>): <description>`
- Use Conventional Commits types that are already accepted by the repo: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- Keep scope short and specific to the affected area, such as `api`, `cli`, `projects`, or `readme`
- Write the description as a concise imperative summary
- Split unrelated changes into separate commits instead of combining multiple concerns into one message
- When a change is breaking, use Conventional Commits breaking-change syntax and include context in the commit body or footer

Examples:

```text
feat(projects): add search functionality
fix(api): handle timeout on slow connections
docs(readme): update installation instructions
```

## Task Validation

Before completing any task:

1. Run: `uv run ruff check src/`
2. Run: `uv run black --check src/`
3. Run: `uv run pytest`
4. Update relevant documentation

## Environment Variables

- `GITLAB_TOKEN`: Personal access token (optional)
- `GITLAB_URL`: GitLab instance URL (default: https://gitlab.com)
