# GitLab Toolbox - Agent Instructions

**Repository**: [https://github.com/rwese/gitlab-toolbox](https://github.com/rwese/gitlab-toolbox)

A Python CLI tool for GitLab operations using direct HTTP API calls via `glab`.

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

### 2. Rich Output Pattern

```python
link = f"[link={entity.web_url}]🔗[/link]" if entity.web_url else ""
```

### 3. Adding New Commands

1. Create model in `models/`
2. Create API wrapper in `api/`
3. Add formatters in `formatters/`
4. Create command in `commands/`
5. Register in `cli.py`

## Task Validation

Before completing any task:

1. Run: `uv run ruff check src/`
2. Run: `uv run black --check src/`
3. Run: `uv run pytest`
4. Update relevant documentation

## Environment Variables

- `GITLAB_TOKEN`: Personal access token (optional)
- `GITLAB_URL`: GitLab instance URL (default: https://gitlab.com)
