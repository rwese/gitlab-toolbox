"""CI/CD variable inventory with client-side inheritance resolution.

GitLab does not expose where an effective variable comes from, so the chain
``outermost group -> ... -> parent group -> scope`` is merged client-side by
``(key, environment_scope)``, nearest scope wins. Instance-level variables are
deliberately not read: ``admin/ci/variables`` is admin-only and this tool
assumes a non-admin token, so ``origin`` is relative to the readable group
chain. See ``docs/architecture.md`` for the architecture overview.
"""

import sys
from typing import Dict, List, Optional, Tuple

from rich.console import Console

from ..models.ci_scope import SCOPE_GROUP, Scope, SkippedScope
from ..models.ci_variable import (
    ORIGIN_DIRECT,
    ORIGIN_INHERITED,
    ORIGIN_OVERRIDE,
    ORIGIN_SHADOWED,
    CIVariable,
    fingerprint,
)
from .client import GitLabClient
from .scope import ancestor_group_paths, map_concurrent

console = Console(file=sys.stderr)

# Instance-level variables require an admin token and are out of scope.
INSTANCE_SCOPE_INCLUDED = False


class CIVariablesAPI:
    """API wrapper for project and group CI/CD variables."""

    @classmethod
    def get_scope_variables(cls, scope: Scope) -> Tuple[Optional[List[dict]], Optional[str]]:
        """Fetch the variables defined directly on a scope.

        Args:
            scope: The project or group scope.

        Returns:
            Tuple of (raw variable dicts, reason). ``reason`` is set when the
            token may not read the scope's variables.
        """
        collection = "groups" if scope.kind == SCOPE_GROUP else "projects"
        return GitLabClient.paginate_safe(f"{collection}/{scope.api_id}/variables")

    @classmethod
    def resolve(
        cls,
        scopes: List[Scope],
        direct_only: bool = False,
        show_shadowed: bool = False,
        reveal: bool = False,
        environment: Optional[str] = None,
        variable_type: Optional[str] = None,
        concurrency: int = 8,
    ) -> Tuple[List[CIVariable], List[SkippedScope]]:
        """Resolve effective variables for each scope.

        Args:
            scopes: Scopes to report on.
            direct_only: Skip the parent-group chain entirely.
            show_shadowed: Also emit parent entries masked by an override.
            reveal: Include raw values instead of fingerprints.
            environment: Filter by environment scope (wildcard aware).
            variable_type: Filter by ``env_var`` or ``file``.
            concurrency: Parallel API fan-out for scope fetches.

        Returns:
            Tuple of (variables, skipped scopes).
        """
        skipped: List[SkippedScope] = []
        cache: Dict[str, Optional[List[dict]]] = {}

        # Collect every scope whose variables we need, deduplicated.
        needed: List[Scope] = []
        seen = set()

        def need(scope: Scope) -> None:
            if scope.ref not in seen:
                seen.add(scope.ref)
                needed.append(scope)

        chains: Dict[str, List[Scope]] = {}
        for scope in scopes:
            chain: List[Scope] = []
            if not direct_only:
                chain = [
                    Scope(kind=SCOPE_GROUP, path=path)
                    for path in ancestor_group_paths(scope.path, scope.kind)
                ]
            chains[scope.ref] = chain
            for ancestor in chain:
                need(ancestor)
            need(scope)

        def fetch(scope: Scope) -> Tuple[str, Optional[List[dict]], Optional[str]]:
            data, reason = cls.get_scope_variables(scope)
            return scope.ref, data, reason

        with console.status("[bold green]Fetching CI/CD variables..."):
            for ref, data, reason in map_concurrent(fetch, needed, concurrency):
                cache[ref] = data
                if reason:
                    kind, _, path = ref.partition(":")
                    skipped.append(SkippedScope(kind, path, "variables", reason))

        variables: List[CIVariable] = []
        for scope in scopes:
            variables.extend(
                cls._resolve_scope(
                    scope,
                    chains[scope.ref],
                    cache,
                    show_shadowed=show_shadowed,
                    reveal=reveal,
                )
            )

        variables = cls._filter(variables, environment=environment, variable_type=variable_type)
        variables.sort(key=lambda v: (v.scope_path, v.key.lower(), v.environment_scope))
        return variables, skipped

    @classmethod
    def _resolve_scope(
        cls,
        scope: Scope,
        chain: List[Scope],
        cache: Dict[str, Optional[List[dict]]],
        show_shadowed: bool = False,
        reveal: bool = False,
    ) -> List[CIVariable]:
        """Merge the chain for a single scope into provenance-tagged variables."""
        # Layers ordered innermost first: depth 0 is the queried scope itself.
        layers: List[Tuple[int, Scope]] = [(0, scope)]
        for depth, ancestor in enumerate(reversed(chain), start=1):
            layers.append((depth, ancestor))

        # Group candidates per merge key, innermost first.
        candidates: Dict[tuple, List[Tuple[int, Scope, dict]]] = {}
        for depth, layer_scope in layers:
            for raw in cache.get(layer_scope.ref) or []:
                key = (raw.get("key"), raw.get("environment_scope", "*"))
                candidates.setdefault(key, []).append((depth, layer_scope, raw))

        resolved: List[CIVariable] = []
        for entries in candidates.values():
            winner_depth, winner_scope, winner_raw = entries[0]
            masked = entries[1:]

            if winner_depth == 0:
                origin = ORIGIN_OVERRIDE if masked else ORIGIN_DIRECT
            else:
                origin = ORIGIN_INHERITED

            variable = cls._parse(
                winner_raw,
                scope=scope,
                defined_in=winner_scope.ref,
                origin=origin,
                depth=winner_depth,
                reveal=reveal,
            )
            if masked:
                variable.overrides = masked[0][1].ref
            resolved.append(variable)

            if show_shadowed:
                for depth, layer_scope, raw in masked:
                    shadowed = cls._parse(
                        raw,
                        scope=scope,
                        defined_in=layer_scope.ref,
                        origin=ORIGIN_SHADOWED,
                        depth=depth,
                        reveal=reveal,
                    )
                    shadowed.overridden_by = winner_scope.ref
                    resolved.append(shadowed)

        return resolved

    @staticmethod
    def _parse(
        data: dict,
        scope: Scope,
        defined_in: str,
        origin: str,
        depth: int,
        reveal: bool = False,
    ) -> CIVariable:
        """Parse a raw variable payload into a :class:`CIVariable`."""
        value = data.get("value")
        variable = CIVariable(
            key=data.get("key", ""),
            variable_type=data.get("variable_type", "env_var"),
            environment_scope=data.get("environment_scope", "*"),
            protected=bool(data.get("protected", False)),
            masked=bool(data.get("masked", False)),
            hidden=bool(data.get("hidden", False)),
            raw=bool(data.get("raw", False)),
            description=data.get("description"),
            scope_kind=scope.kind,
            scope_path=scope.path,
            defined_in=defined_in,
            origin=origin,
            inheritance_depth=depth,
        )

        if reveal:
            variable.value = value
            variable.value_redacted = False
        else:
            variable.value_redacted = True
            variable.value_fingerprint = fingerprint(value)
            variable.value_length = len(value) if value is not None else None

        return variable

    @staticmethod
    def _matches_environment(variable: CIVariable, environment: str) -> bool:
        """Return True if the variable applies to ``environment``.

        GitLab treats ``*`` as a wildcard, both as the whole scope and as a
        trailing wildcard such as ``review/*``.
        """
        scope_value = variable.environment_scope or "*"
        if scope_value == "*" or scope_value == environment:
            return True
        if scope_value.endswith("*"):
            return environment.startswith(scope_value[:-1])
        return False

    @classmethod
    def _filter(
        cls,
        variables: List[CIVariable],
        environment: Optional[str] = None,
        variable_type: Optional[str] = None,
    ) -> List[CIVariable]:
        """Apply environment and type filters."""
        result = variables
        if environment:
            result = [v for v in result if cls._matches_environment(v, environment)]
        if variable_type:
            result = [v for v in result if v.variable_type == variable_type]
        return result
