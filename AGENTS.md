# GitLab Toolbox — Agent Instructions

**Repository**: [github.com/rwese/gitlab-toolbox](https://github.com/rwese/gitlab-toolbox)

GitLab Toolbox is a Python CLI for GitLab operations. It uses direct HTTP REST and
GraphQL requests; it does not use `glab api`. Existing host-matched `glab`
credentials may be read as an authentication fallback, but this project must not
create, modify, or remove them.

## Required Documentation

Read the relevant document before changing the corresponding area:

- [Architecture](docs/architecture.md) — layers, API client, authentication,
  pagination, scope resolution, and CI variable inheritance.
- [Coding standards](docs/coding-standards.md) — formatting, typing, HTTP error
  handling, Click commands, tests, and documentation.
- [Git workflow](docs/git-workflow.md) — branches, Conventional Commits, validation,
  and review.

Keep these documents and the README aligned with implementation changes.

## Design Principles

Commands should:

- Work well in scripts and pipelines.
- Send result data to stdout and status/progress messages to stderr.
- Provide machine-readable output where supported, with JSON as the primary format.
- Use Rich tables for interactive output.
- Avoid interactive prompts unless a command explicitly requires confirmation.
- Redact secret values by default.

Do not assume every command supports `--dry-run` or file output; preserve and test the
actual interface of the command being changed.

## Project Structure

```
src/gitlab_toolbox/
├── cli.py              # Main entry point and command registration
├── api/                # HTTP API clients and scope resolution
├── models/             # Domain dataclasses
├── commands/           # Click command implementations
└── formatters/         # Rich, JSON, CSV, and Markdown output
tests/                  # pytest suite
docs/                   # Architecture and contributor documentation
```

## Implementation Guidelines

### GitLab API

- Use `GitLabClient` and `requests`; never shell out to `glab api`.
- URL-encode project and group identifiers used in REST endpoint paths.
- Use pagination helpers rather than duplicating pagination loops.
- Use optional/safe request helpers for expected missing or inaccessible resources.
- Keep `glab` integration read-only, host-specific, and limited to authentication
  fallback after configured authentication is absent or receives a 401.

### Adding Commands

As applicable:

1. Add or update a model in `models/`.
2. Add API behavior in `api/`.
3. Add formatters in `formatters/`.
4. Implement the Click command in `commands/`.
5. Register it in `cli.py` or its parent command group.
6. Add tests and update user-facing documentation.

### Commits

Use `<type>(<scope>): <description>` with accepted types `feat`, `fix`, `docs`,
`style`, `refactor`, `test`, and `chore`. Keep changes focused and do not push without
explicit user instruction.

## Validation

Before completing work, run:

```bash
uv run ruff check src/ tests/
uv run black --check src/ tests/
uv run pytest
```

Update relevant files under `docs/`, plus README.md or AGENTS.md when behavior or
contributor guidance changes.

## Environment Variables

- `GITLAB_URL`: GitLab instance URL (default: `https://gitlab.com`)
- `GITLAB_TOKEN`, `GL_TOKEN`, `CI_JOB_TOKEN`, `CI_API_TOKEN`,
  `GITLAB_ACCESS_TOKEN`: supported token sources in precedence order
