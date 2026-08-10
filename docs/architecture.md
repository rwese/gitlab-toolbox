# Architecture

## Overview

GitLab Toolbox is a layered Python CLI that communicates with GitLab through its
HTTP REST (`/api/v4`) and GraphQL (`/api/graphql`) APIs. It uses `requests` for
API traffic; `glab` is not the API transport. The authentication module can
read existing `glab` credentials as a compatibility fallback, but never manages
or changes `glab` configuration.

## Layer Structure

```
src/gitlab_toolbox/
├── cli.py                    # Main CLI entry point and command registration
├── api/                      # HTTP API clients and scope resolution
├── models/                   # Dataclasses representing domain entities
├── commands/                 # Click command implementations
└── formatters/               # Table, JSON, CSV, and Markdown presentation
```

## Layer Responsibilities

### CLI Layer (`commands/`)

- Defines Click commands and options.
- Validates user input and orchestrates API calls.
- Selects an output formatter and writes command results.

### API Layer (`api/`)

- Uses `GitLabClient` to make authenticated HTTP requests with `requests`.
- Uses the REST API for standard endpoints and GraphQL where appropriate.
- Handles pagination, request timeouts, API errors, and URL encoding.
- Provides safe/optional request helpers when an inaccessible or missing resource
  is an expected outcome.

### Model Layer (`models/`)

- Dataclasses defining domain models.
- GitLab entity representations and parsing helpers.
- Type annotations and validation at API boundaries.

### Presentation Layer (`formatters/`)

- Rich tables and other interactive views.
- JSON, CSV, and Markdown output for scripting and files.
- Clickable link support when a `web_url` is present.

## Key Design Patterns

### 1. HTTP API Client and Pagination

`GitLabClient._run_api_request()` makes an authenticated request to
`{base_url}/api/v4/{endpoint}` and returns decoded JSON. `paginate()` requests
100 items per page and stops once its caller-provided limit is met. The client
also provides `_run_graphql_query()` for GitLab GraphQL requests.

Authentication is configured from `GITLAB_URL` / `CI_SERVER_URL` and supported
token environment variables, with an optional read-only fallback to an existing
`glab` credential for the requested host. When a configured credential receives a
401 response, the HTTP request is retried once with the host's existing `glab`
credential. `auth status` likewise validates the configured credential before
consulting that fallback. Neither path invokes `glab api` or modifies `glab`
configuration.

### 2. Hierarchical Processing

Groups use a two-pass algorithm:

1. Fetch all groups as a flat list.
2. Build parent-child relationships using `parent_id` and dictionary lookup.

### 3. Opt-in Member Fetching

- Group members are not fetched by default.
- `--include-members` enables member lookup.
- This avoids unnecessary requests for large group hierarchies.

### 4. Modular Commands

Each domain has its own command module, including:

- `groups.py`
- `projects.py`
- `merge_requests.py`
- `pipelines.py`
- `pipeline_schedules.py`
- `ci.py` and `ci_config.py` (variables, tokens, and inventory under `ci`)

### 5. Scope Resolution and Degradation

CI/CD configuration commands operate on a set of scopes rather than a single
project:

- `commands/_scope.py` provides shared project and group options.
- `api/scope.py` resolves them into `Scope` objects and uses `map_concurrent()`
  for fan-out (default concurrency: 8).
- `_run_api_request_safe()` and `paginate_safe()` turn 401, 403, and 404
  responses into a reason that can be reported as a `SkippedScope`, rather than
  aborting a group sweep.

### 6. Variable Inheritance

GitLab does not report an effective variable's origin. `api/ci_variables.py`
constructs its merge layers from the queried (innermost) scope through its
ancestors, keyed by `(key, environment_scope)`, so the nearest value wins. Entries record `origin`,
`defined_in`, `overrides`, and `inheritance_depth`.

Ancestor group paths are derived from a namespace path (`a/b/c` → `a`, `a/b`),
without additional parent-ID lookups. Instance-level variables are out of scope
because their endpoint requires an admin token.

### 7. Secret Redaction

Variable values are redacted by default in every output format. Consumers get a
short SHA-256 fingerprint and value length for comparison. `--reveal` opts in to
raw values and emits a warning on stderr.

## Access Level Mapping

GitLab access levels are numeric:

- 0: No access
- 5: Minimal Access
- 10: Guest
- 20: Reporter
- 30: Developer
- 40: Maintainer
- 50: Owner

Always translate them to human-readable descriptions.

## Web URL Handling

Always handle nullable `web_url` fields:

```python
url = entity.web_url or ""
link = f"[link={url}]🔗[/link]" if url else ""
```
