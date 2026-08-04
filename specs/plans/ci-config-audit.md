# Plan: CI/CD Configuration & Credential Inventory Commands

Status: proposed
Scope: new `ci` subcommands to inventory CI/CD variables, access tokens, deploy tokens,
trigger tokens and deploy keys across projects and groups.

## 1. Goals

- Inventory every CI/CD-relevant configuration and credential for a project, a group,
  or a group tree (subgroups + projects).
- Report metadata that GitLab's UI hides or spreads across pages: creation time,
  scopes/permissions, access level, expiration, revoked/active state, last used at,
  and last used IPs where a non-admin token can read them (see §2).
- Show variable inheritance explicitly: which values come from a parent group, which
  are defined directly, and which project values override an inherited one.
- Stay script friendly: Rich tables interactively, JSON/CSV when piped, `--output`
  file support, read-only by design.

Non-goals: audit/risk scoring, TUI browser, write/rotate operations, secure files,
runners, job-token allowlists, variable diffing, and **anything that requires an admin
token**.

**Access assumption:** the tool is designed for a *non-admin* token holding
Maintainer/Owner on the queried projects and groups. No admin-only endpoint is called,
so instance-level variables (`admin/ci/variables`) and cross-user PAT lookups are out
of scope; features that would need them are dropped rather than conditionally enabled.

## 2. Verified API surface (checked against a GitLab 19.0-ee instance)

| Data | Endpoint | Useful fields |
|---|---|---|
| Project variables | `projects/:id/variables` | `key`, `value`, `variable_type`, `protected`, `masked`, `hidden`, `raw`, `environment_scope`, `description` |
| Group variables | `groups/:id/variables` | same as above |
| Project access tokens | `projects/:id/access_tokens` | `id`, `name`, `description`, `scopes`, `access_level`, `created_at`, `expires_at`, `last_used_at`, `active`, `revoked`, `user_id` |
| Group access tokens | `groups/:id/access_tokens` | same + `resource_type`, `resource_id` |
| Personal access tokens | `personal_access_tokens` | above **plus `last_used_ips`** |
| Deploy tokens | `projects/:id/deploy_tokens`, `groups/:id/deploy_tokens` | `id`, `name`, `username`, `scopes`, `expires_at`, `revoked`, `expired` (no created_at, no last_used) |
| Trigger tokens | `projects/:id/triggers` | `id`, `description`, `created_at`, `last_used`, `owner`, `token` (masked) |
| Deploy keys | `projects/:id/deploy_keys` | `id`, `title`, `created_at`, `expires_at`, `last_used_at`, `can_push`, `fingerprint` |

Notable gaps and how we handle them:

- **`last_used_ips` is not available for project/group access tokens.** The field
  exists only on the `personal_access_tokens` payload, and that endpoint returns only
  the *caller's own* tokens — resolving a resource token's bot user
  (`personal_access_tokens?user_id=<bot user_id>`) needs admin, which we do not assume.
  Consequence: `last_used_ips` is populated only for the caller's own PATs and rendered
  `n/a` everywhere else. No enrichment flag is implemented.
- **Instance-level variables are not read.** `admin/ci/variables` is admin-only
  (verified: 403 with a Maintainer token). `origin` labels are therefore documented as
  *relative to the group chain*, and the JSON envelope carries
  `instance_scope_included: false` so consumers know the chain starts at the outermost
  readable group.
- **Deploy tokens have no created_at / last_used.** Render `n/a`.
- **Variables need Maintainer+**, tokens need Owner/Maintainer. A 403 on one project
  must not abort a group sweep — record it as a `skipped` entry with the reason and
  surface a summary line on stderr.
- **Inheritance is not exposed by the API.** Group variables are resolved client-side
  by walking the project's namespace chain (`groups/:id` → `parent_id`) and merging
  by `(key, environment_scope)`, nearest scope wins.

## 3. CLI surface

All commands hang off the existing `ci` group (`commands/ci.py` → `ci_cli`).

```
gitlab-toolbox ci variables list [scope opts] [--reveal] [--direct-only]
                                 [--environment X] [--type env_var|file]
gitlab-toolbox ci tokens list    [scope opts] [--kind access,deploy,trigger,key]
                                 [--state active|expired|revoked|all]
                                 [--expiring-in 30] [--unused-for 90]
gitlab-toolbox ci inventory      [scope opts] [--reveal] [--direct-only]
```

Shared scope options (one reusable Click decorator in `commands/_scope.py`):

```
--project TEXT            repeatable; defaults to global --project / git remote
--group TEXT              repeatable
--include-subgroups       recurse groups
--include-projects        include projects of the selected group(s)
--archived / --no-archived   (default: skip archived projects)
--limit N                 cap projects fetched
--concurrency N           parallel API fan-out (default 8)
```

Output via the existing `format_decorator`: `table` interactive, `json` when piped,
plus `csv` and `markdown`. `-o/--output` picks format, `--output-file/-O` writes to
disk for script workflows.

### `ci variables list` — inheritance model

By default the command shows the **effective** set for each scope: variables defined
on the scope itself plus everything inherited from its parent group chain. Each row
carries an explicit origin:

| Field | Values | Meaning |
|---|---|---|
| `origin` | `direct` | defined on the queried scope itself |
| | `inherited` | comes from a parent group, not redefined locally |
| | `override` | defined locally **and** also present in a parent group |
| | `shadowed` | the parent-group entry that a local `override` masks (only with `--show-shadowed`) |
| `defined_in` | `group:acme/platform` / `project:acme/platform/app` | scope that actually holds the value |
| `overrides` | scope path or `null` | for `origin=override`: the scope being masked |
| `inheritance_depth` | int | 0 = direct, 1 = parent group, 2 = grandparent … |

Table rendering marks these visually: `direct` plain, `inherited` dimmed with a `↑`
prefix and the owning group in the `Defined in` column, `override` highlighted with a
`⤺` marker plus the masked scope in the `Overrides` column.

`--direct-only` skips the parent-chain walk entirely and lists only variables defined
on the queried scope (one API call per scope, no inheritance resolution). It is
mutually exclusive with `--show-shadowed`.

Merging rule: variables are keyed by `(key, environment_scope)`; the nearest scope in
the chain wins. `--environment X` filters to entries whose `environment_scope` matches
`X` exactly or via GitLab's `*` wildcard semantics.

### Redaction policy

Values are **redacted by default** in every format, including JSON:

```
value: null
value_redacted: true
value_fingerprint: "sha256:9f2b1c4d"      # first 8 hex chars of sha256(value)
value_length: 42
```

The fingerprint lets you tell an `override` that changes the value from one that
merely restates the parent value, without exposing secrets. `--reveal` fills `value`
and drops the redaction fields; it prints a warning to stderr. `hidden: true`
variables never return a value from the API at all.

## 4. Module layout

```
src/gitlab_toolbox/
├── models/
│   ├── ci_variable.py        CIVariable (+ origin, defined_in, overrides,
│   │                          inheritance_depth, redaction fields)
│   └── ci_token.py           CIToken (unified: kind, name, scopes, access_level,
│                              created_at, expires_at, last_used_at, last_used_ips,
│                              active, revoked, owner_kind, owner_path, web_url)
├── api/
│   ├── ci_variables.py       CIVariablesAPI.get_project / get_group /
│   │                          resolve_effective(scope, direct_only)
│   ├── ci_tokens.py          CITokensAPI.get_access/deploy/trigger/deploy_keys
│   └── scope.py              ScopeResolver: (--project/--group/...) -> [Scope],
│                              plus namespace-chain lookup for inheritance
├── commands/
│   ├── _scope.py             shared Click scope decorator
│   └── ci_config.py          variables/tokens/inventory subcommands,
│                              registered onto ci_cli
└── formatters/
    ├── display.py            + format_ci_variables / format_ci_tokens
    └── generic_handlers.py   + entity types "ci_variables", "ci_tokens"
```

`CIToken.kind ∈ {project_access, group_access, deploy, trigger, deploy_key}` keeps one
model and one table for all credential types; missing fields stay `None`.

Client additions in `api/client.py`:

- `_run_api_request_safe()` → `(data, error)` that swallows 401/403/404 so group
  sweeps continue and the reason can be reported.
- `paginate_many(endpoints, concurrency)` helper using `ThreadPoolExecutor` for fan-out.

Namespace chains are cached per run (`{group_id: parent_id}`), so a sweep of 200
projects in one group hierarchy fetches each group's variables once.

## 5. Implementation phases

1. **Foundations** — `models/ci_variable.py`, `models/ci_token.py`, `api/scope.py`,
   `_run_api_request_safe`, concurrency helper. Unit tests with mocked client.
2. **Variables (direct)** — `api/ci_variables.py`, redaction helper, `ci variables
   list --direct-only` + formatters.
3. **Inheritance** — namespace-chain walk, merge by `(key, environment_scope)`,
   `origin` / `defined_in` / `overrides` / `inheritance_depth`, `--show-shadowed`,
   table markers.
4. **Tokens** — `api/ci_tokens.py` for all five kinds, `ci tokens list` with
   `--state/--expiring-in/--unused-for` filters.
5. **Inventory & docs** — `ci inventory` single JSON document, README section,
   `specs/architecture.md` update.

Each phase is a separate Conventional Commit, e.g.
`feat(ci): add CI/CD variable inventory command`.

## 6. Testing

- `tests/test_ci_variables.py`: parsing, redaction, and the inheritance merge matrix
  (direct / inherited / override / shadowed, wildcard `environment_scope`, same-value
  override detected via fingerprint).
- `tests/test_ci_tokens.py`: parsing per kind, missing-field handling, filters.
- `tests/test_ci_scope.py`: scope resolution incl. subgroup recursion, namespace-chain
  caching, and 403 skip behaviour.
- `tests/test_ci_config_commands.py`: `CliRunner` smoke tests for each output format
  and for `--direct-only` vs default.
- Validation gate: `uv run ruff check src/`, `uv run black --check src/`, `uv run pytest`.

## 7. Decisions & open items

### 7.1 Instance-level variables — decided: out of scope

The tool assumes a non-admin token, so `GET /api/v4/admin/ci/variables` (403 for
Maintainers, unreadable for anyone on GitLab.com) is never called. Consequences that
must be documented in `--help` and the README:

- `origin` (`direct` / `inherited` / `override`) is **relative to the readable group
  chain**, not to GitLab's full precedence order
  (`instance -> group chain -> project`).
- A key that also exists as an instance variable will be reported as `direct` on the
  outermost group that defines it; the instance-level entry it masks is invisible.
- The JSON envelope always carries `instance_scope_included: false` so scripts can
  record that the chain is group-relative.

Revisit only if an admin-token use case appears; the design then is a single extra
call prepended to the chain with `origin_level: instance`.

### 7.2 Other open items

- Caching layer (on-disk TTL cache) for repeated sweeps of large groups — deferred
  until performance is a real problem; `--concurrency` plus per-run namespace caching
  should cover it initially.
