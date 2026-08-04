"""Inventory of CI/CD-relevant credentials: access, deploy and trigger tokens plus deploy keys.

All calls stay within what a non-admin Maintainer/Owner token can read. Notably
``last_used_ips`` is only present on the ``personal_access_tokens`` payload,
which returns the caller's own tokens; resolving a project/group access token's
bot user requires admin, so that field stays ``None`` for resource tokens.
"""

import sys
from typing import List, Optional, Tuple

from rich.console import Console

from ..models.ci_scope import SCOPE_GROUP, SCOPE_PROJECT, Scope, SkippedScope
from ..models.ci_token import (
    KIND_DEPLOY,
    KIND_DEPLOY_KEY,
    KIND_GROUP_ACCESS,
    KIND_PROJECT_ACCESS,
    KIND_TRIGGER,
    CIToken,
)
from .client import GitLabClient
from .scope import map_concurrent

console = Console(file=sys.stderr)


class CITokensAPI:
    """API wrapper for project and group credentials."""

    @classmethod
    def get_tokens(
        cls,
        scopes: List[Scope],
        kinds: Optional[List[str]] = None,
        concurrency: int = 8,
    ) -> Tuple[List[CIToken], List[SkippedScope]]:
        """Fetch credentials for the given scopes.

        Args:
            scopes: Project and group scopes to inspect.
            kinds: Model kinds to include (defaults to all).
            concurrency: Parallel API fan-out.

        Returns:
            Tuple of (tokens, skipped scopes).
        """
        wanted = set(kinds) if kinds else None

        def fetch(scope: Scope) -> Tuple[List[CIToken], List[SkippedScope]]:
            return cls._get_scope_tokens(scope, wanted)

        tokens: List[CIToken] = []
        skipped: List[SkippedScope] = []

        with console.status("[bold green]Fetching CI/CD credentials..."):
            for scope_tokens, scope_skipped in map_concurrent(fetch, scopes, concurrency):
                tokens.extend(scope_tokens)
                skipped.extend(scope_skipped)

        tokens.sort(key=lambda t: (t.scope_path, t.kind, (t.name or "").lower()))
        return tokens, skipped

    @classmethod
    def _get_scope_tokens(
        cls, scope: Scope, wanted: Optional[set]
    ) -> Tuple[List[CIToken], List[SkippedScope]]:
        """Fetch every supported credential kind for one scope."""
        tokens: List[CIToken] = []
        skipped: List[SkippedScope] = []

        is_group = scope.kind == SCOPE_GROUP
        collection = "groups" if is_group else "projects"
        access_kind = KIND_GROUP_ACCESS if is_group else KIND_PROJECT_ACCESS

        sources = [
            (access_kind, f"{collection}/{scope.api_id}/access_tokens", "access_tokens"),
            (KIND_DEPLOY, f"{collection}/{scope.api_id}/deploy_tokens", "deploy_tokens"),
        ]
        if scope.kind == SCOPE_PROJECT:
            sources.append((KIND_TRIGGER, f"projects/{scope.api_id}/triggers", "triggers"))
            sources.append((KIND_DEPLOY_KEY, f"projects/{scope.api_id}/deploy_keys", "deploy_keys"))

        for kind, endpoint, resource in sources:
            if wanted is not None and kind not in wanted:
                continue

            data, reason = GitLabClient.paginate_safe(endpoint)
            if reason:
                skipped.append(SkippedScope(scope.kind, scope.path, resource, reason))
                continue

            for item in data or []:
                tokens.append(cls._parse(item, kind, scope))

        return tokens, skipped

    @classmethod
    def get_personal_tokens(cls, concurrency: int = 8) -> Tuple[List[CIToken], List[SkippedScope]]:
        """Fetch the caller's own personal access tokens.

        This is the only endpoint that exposes ``last_used_ips`` without admin
        rights, and it only ever covers the authenticated user.

        Returns:
            Tuple of (tokens, skipped scopes).
        """
        data, reason = GitLabClient.paginate_safe("personal_access_tokens")
        if reason:
            return [], [SkippedScope("user", "self", "personal_access_tokens", reason)]

        scope = Scope(kind="user", path="self")
        return [cls._parse(item, "personal", scope) for item in data or []], []

    @staticmethod
    def _parse(data: dict, kind: str, scope: Scope) -> CIToken:
        """Parse a raw credential payload into a :class:`CIToken`."""
        if kind == KIND_DEPLOY_KEY:
            return CIToken(
                kind=kind,
                id=data.get("id"),
                name=data.get("title", ""),
                scope_kind=scope.kind,
                scope_path=scope.path,
                created_at=data.get("created_at"),
                expires_at=data.get("expires_at"),
                last_used_at=data.get("last_used_at"),
                can_push=data.get("can_push"),
                fingerprint=data.get("fingerprint_sha256") or data.get("fingerprint"),
            )

        if kind == KIND_TRIGGER:
            owner = data.get("owner") or {}
            return CIToken(
                kind=kind,
                id=data.get("id"),
                name=data.get("description") or f"trigger-{data.get('id')}",
                scope_kind=scope.kind,
                scope_path=scope.path,
                description=data.get("description"),
                created_at=data.get("created_at"),
                last_used_at=data.get("last_used"),
                owner=owner.get("username"),
                user_id=owner.get("id"),
            )

        if kind == KIND_DEPLOY:
            return CIToken(
                kind=kind,
                id=data.get("id"),
                name=data.get("name", ""),
                scope_kind=scope.kind,
                scope_path=scope.path,
                username=data.get("username"),
                scopes=data.get("scopes", []) or [],
                expires_at=data.get("expires_at"),
                revoked=data.get("revoked"),
                expired=data.get("expired"),
            )

        # Project, group and personal access tokens share one payload shape.
        return CIToken(
            kind=kind,
            id=data.get("id"),
            name=data.get("name", ""),
            scope_kind=scope.kind,
            scope_path=scope.path,
            description=data.get("description"),
            scopes=data.get("scopes", []) or [],
            access_level=data.get("access_level"),
            created_at=data.get("created_at"),
            expires_at=data.get("expires_at"),
            last_used_at=data.get("last_used_at"),
            last_used_ips=data.get("last_used_ips"),
            revoked=data.get("revoked"),
            active=data.get("active"),
            user_id=data.get("user_id"),
        )

    @staticmethod
    def filter_tokens(
        tokens: List[CIToken],
        state: str = "all",
        expiring_in: Optional[int] = None,
        unused_for: Optional[int] = None,
    ) -> List[CIToken]:
        """Filter tokens by lifecycle state and usage.

        Args:
            tokens: Tokens to filter.
            state: ``active``, ``expired``, ``revoked`` or ``all``.
            expiring_in: Keep tokens expiring within this many days.
            unused_for: Keep tokens never used, or unused for this many days.

        Returns:
            Filtered list of tokens.
        """
        result = tokens

        if state and state != "all":
            result = [t for t in result if t.state == state]

        if expiring_in is not None:
            result = [
                t
                for t in result
                if t.days_until_expiry is not None and t.days_until_expiry <= expiring_in
            ]

        if unused_for is not None:

            def is_stale(token: CIToken) -> bool:
                if token.last_used_at is None:
                    # Never used: only meaningful when the token is old enough
                    # and the kind actually tracks usage.
                    if token.kind == KIND_DEPLOY:
                        return False
                    age = token.days_since_creation
                    return age is None or age >= unused_for
                since = token.days_since_last_use
                return since is not None and since >= unused_for

            result = [t for t in result if is_stale(t)]

        return result
