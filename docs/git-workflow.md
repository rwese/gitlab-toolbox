# Git Workflow

## Branch Naming

- `feat/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation updates
- `refactor/*` - Code refactoring

Example:

```
feat/add-pipeline-schedules
fix/project-search-timeout
docs/update-api-examples
```

## Commit Messages

Format: `<type>(<scope>): <description>`

Types:

- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `style` - Formatting
- `refactor` - Restructuring
- `test` - Testing
- `chore` - Maintenance

Examples:

```
feat(projects): add search functionality
fix(api): handle timeout on slow connections
docs(readme): update installation instructions
```

## Pre-commit Hooks

The repository provides `scripts/pre-commit`, which can be run manually. It
validates:

1. **Code formatting** with Black
2. **Linting** with Ruff
3. **Test collection** with pytest
4. **Agent instructions** (`AGENTS.md` exists)

It is not automatically installed as a Git hook.

Run manually:

```bash
./scripts/pre-commit
```

## Validation Before Commit

Always run these commands:

```bash
uv run black --check src/
uv run ruff check src/
uv run pytest --co -q
```

## Code Review

1. Create pull request with clear description
2. Link related issues
3. Request review from maintainers
4. Address feedback iteratively
5. Squash commits before merge

## Dependencies

- Use `uv` for package management
- Update `pyproject.toml` when adding dependencies
- Run `uv sync` after dependency changes
