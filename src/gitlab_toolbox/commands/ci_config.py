"""CI/CD configuration inventory commands.

Registered onto the ``ci`` command group:

* ``ci variables list``  — variables with inheritance provenance
* ``ci tokens list``     — access/deploy/trigger tokens and deploy keys
* ``ci inventory``       — both, as a single JSON document

All commands are read-only and assume a non-admin token: instance-level
variables are never requested, so a variable's ``origin`` is relative to the
readable group chain.
"""

import sys
from dataclasses import asdict
from typing import List, Optional

import click
from rich.console import Console

from ..api.ci_tokens import CITokensAPI
from ..api.ci_variables import CIVariablesAPI
from ..models.ci_token import ALL_KINDS, KIND_ALIASES
from ..formatters import json_output as json
from ..formatters.format_decorator import format_decorator
from ._scope import resolve_scopes, scope_options

console = Console(file=sys.stderr)

FORMATS = ["table", "json", "markdown", "csv"]


@click.group(name="variables")
def variables_cli():
    """Inspect CI/CD variables and their inheritance."""
    pass


@click.group(name="tokens")
def tokens_cli():
    """Inspect CI/CD credentials (access, deploy, trigger tokens, deploy keys)."""
    pass


def _write_output(content: str, output_file: Optional[str]) -> None:
    """Write ``content`` to a file, or to stdout when no file is given."""
    if output_file:
        with open(output_file, "w") as handle:
            handle.write(content)
        console.print(f"[green]✓ Wrote {output_file}[/green]")
    else:
        print(content)


def _warn_reveal(reveal: bool) -> None:
    """Warn on stderr when secret values are printed."""
    if reveal:
        console.print(
            "[yellow]⚠ --reveal: raw variable values are included in the output.[/yellow]"
        )


def _resolve_kinds(kind: Optional[str]) -> Optional[List[str]]:
    """Map ``--kind`` CLI values onto model kinds."""
    if not kind:
        return None
    kinds: List[str] = []
    for item in kind.split(","):
        item = item.strip().lower()
        if not item:
            continue
        if item in KIND_ALIASES:
            kinds.extend(KIND_ALIASES[item])
        elif item in ALL_KINDS:
            kinds.append(item)
        else:
            raise click.BadParameter(
                f"unknown kind {item!r}; expected one of " f"{', '.join(sorted(KIND_ALIASES))}"
            )
    return kinds or None


@variables_cli.command(name="list")
@scope_options
@format_decorator(
    formats=FORMATS,
    interactive_default="table",
    script_default="json",
    entity_type="ci_variables",
)
@click.option(
    "--direct-only",
    is_flag=True,
    help="Only variables defined on the scope itself; skips the parent-group chain.",
)
@click.option(
    "--show-shadowed",
    is_flag=True,
    help="Also list parent-group entries masked by an override.",
)
@click.option("--reveal", is_flag=True, help="Show raw values instead of fingerprints.")
@click.option("--environment", help="Filter by environment scope (wildcard aware).")
@click.option(
    "--type",
    "variable_type",
    type=click.Choice(["env_var", "file"]),
    help="Filter by variable type.",
)
@click.option("-O", "--output-file", type=click.Path(), help="Write output to a file.")
def list_variables(
    projects,
    groups,
    include_subgroups,
    include_projects,
    archived,
    limit,
    concurrency,
    format_handler,
    direct_only,
    show_shadowed,
    reveal,
    environment,
    variable_type,
    output_file,
):
    """List CI/CD variables, marking inherited and overridden entries.

    By default the effective set is shown: variables defined on the scope plus
    everything inherited from its parent groups. Each entry is tagged as
    'direct', 'inherited' or 'override' (with the masked scope in 'overrides').
    Use --direct-only to list just the scope's own variables.
    """
    if direct_only and show_shadowed:
        raise click.UsageError("--direct-only cannot be combined with --show-shadowed")

    _warn_reveal(reveal)

    scopes, skipped = resolve_scopes(
        projects, groups, include_subgroups, include_projects, archived, limit
    )
    if not scopes:
        return

    variables, var_skipped = CIVariablesAPI.resolve(
        scopes,
        direct_only=direct_only,
        show_shadowed=show_shadowed,
        reveal=reveal,
        environment=environment,
        variable_type=variable_type,
        concurrency=concurrency,
    )

    _emit(
        format_handler,
        variables,
        skipped + var_skipped,
        output_file,
        reveal=reveal,
    )


@tokens_cli.command(name="list")
@scope_options
@format_decorator(
    formats=FORMATS,
    interactive_default="table",
    script_default="json",
    entity_type="ci_tokens",
)
@click.option(
    "--kind",
    help="Comma-separated kinds to include: access, deploy, trigger, key (default: all).",
)
@click.option(
    "--state",
    type=click.Choice(["active", "expired", "revoked", "all"]),
    default="all",
    show_default=True,
    help="Filter by lifecycle state.",
)
@click.option(
    "--expiring-in",
    type=int,
    help="Only tokens expiring within this many days (negative days = already expired).",
)
@click.option(
    "--unused-for",
    type=int,
    help="Only tokens never used, or unused for at least this many days.",
)
@click.option("-O", "--output-file", type=click.Path(), help="Write output to a file.")
def list_tokens(
    projects,
    groups,
    include_subgroups,
    include_projects,
    archived,
    limit,
    concurrency,
    format_handler,
    kind,
    state,
    expiring_in,
    unused_for,
    output_file,
):
    """List access tokens, deploy tokens, trigger tokens and deploy keys.

    Deploy tokens expose neither a creation time nor usage data, and
    'last_used_ips' is only available for the caller's own personal access
    tokens; both render as 'n/a'.
    """
    kinds = _resolve_kinds(kind)

    scopes, skipped = resolve_scopes(
        projects, groups, include_subgroups, include_projects, archived, limit
    )
    if not scopes:
        return

    tokens, token_skipped = CITokensAPI.get_tokens(scopes, kinds=kinds, concurrency=concurrency)
    tokens = CITokensAPI.filter_tokens(
        tokens, state=state, expiring_in=expiring_in, unused_for=unused_for
    )

    _emit(format_handler, tokens, skipped + token_skipped, output_file)


@click.command(name="inventory")
@scope_options
@click.option(
    "--direct-only",
    is_flag=True,
    help="Only variables defined on the scope itself; skips the parent-group chain.",
)
@click.option("--reveal", is_flag=True, help="Show raw values instead of fingerprints.")
@click.option("-O", "--output-file", type=click.Path(), help="Write output to a file.")
def inventory(
    projects,
    groups,
    include_subgroups,
    include_projects,
    archived,
    limit,
    concurrency,
    direct_only,
    reveal,
    output_file,
):
    """Dump variables and credentials for the selected scopes as one JSON document."""
    _warn_reveal(reveal)

    scopes, skipped = resolve_scopes(
        projects, groups, include_subgroups, include_projects, archived, limit
    )
    if not scopes:
        return

    variables, var_skipped = CIVariablesAPI.resolve(
        scopes, direct_only=direct_only, reveal=reveal, concurrency=concurrency
    )
    tokens, token_skipped = CITokensAPI.get_tokens(scopes, concurrency=concurrency)

    document = {
        "instance_scope_included": False,
        "reveal": reveal,
        "scopes": [asdict(scope) for scope in scopes],
        "skipped": [asdict(entry) for entry in skipped + var_skipped + token_skipped],
        "variables": [variable.to_dict() for variable in variables],
        "tokens": [token.to_dict() for token in tokens],
    }

    _write_output(json.dumps(document, indent=2), output_file)


def _emit(format_handler, data, skipped, output_file, **kwargs) -> None:
    """Run the format handler, optionally capturing its output into a file.

    Rich tables are written through the module-level stdout console, so that
    console is swapped as well as ``sys.stdout`` while capturing.
    """
    if not output_file:
        format_handler(data, skipped=skipped, **kwargs)
        return

    import io
    from contextlib import redirect_stdout

    from rich.console import Console as RichConsole

    from ..formatters import display as display_module

    buffer = io.StringIO()
    original_console = display_module.console_stdout
    display_module.console_stdout = RichConsole(file=buffer, width=200)
    try:
        with redirect_stdout(buffer):
            format_handler(data, skipped=skipped, **kwargs)
    finally:
        display_module.console_stdout = original_console

    _write_output(buffer.getvalue(), output_file)


def register(ci_group: click.Group) -> None:
    """Attach the CI/CD configuration commands to the ``ci`` group."""
    ci_group.add_command(variables_cli)
    ci_group.add_command(tokens_cli)
    ci_group.add_command(inventory)
