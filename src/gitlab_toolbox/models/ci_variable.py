"""CI/CD variable model with inheritance provenance and value redaction."""

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

# Origin of a variable relative to the queried scope.
ORIGIN_DIRECT = "direct"
ORIGIN_INHERITED = "inherited"
ORIGIN_OVERRIDE = "override"
ORIGIN_SHADOWED = "shadowed"

ORIGIN_MARKERS = {
    ORIGIN_DIRECT: "",
    ORIGIN_INHERITED: "↑ ",
    ORIGIN_OVERRIDE: "⤺ ",
    ORIGIN_SHADOWED: "✗ ",
}


def fingerprint(value: Optional[str]) -> Optional[str]:
    """Return a short, non-reversible fingerprint of a variable value.

    Args:
        value: The raw variable value, or None if unavailable.

    Returns:
        ``sha256:<8 hex chars>`` or None when there is no value.
    """
    if value is None:
        return None
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:8]}"


@dataclass
class CIVariable:
    """A CI/CD variable as seen from a queried scope.

    Values are redacted by default: ``value`` stays None and the caller only
    gets a fingerprint plus the length, which is enough to tell whether an
    override actually changes the inherited value.
    """

    key: str
    variable_type: str = "env_var"
    environment_scope: str = "*"
    protected: bool = False
    masked: bool = False
    hidden: bool = False
    raw: bool = False
    description: Optional[str] = None

    # Provenance
    scope_kind: str = ""  # queried scope kind ('project' / 'group')
    scope_path: str = ""  # queried scope path
    defined_in: str = ""  # 'group:ps/devops' / 'project:ps/devops/app'
    origin: str = ORIGIN_DIRECT
    overrides: Optional[str] = None  # scope ref masked by this entry
    overridden_by: Optional[str] = None  # scope ref masking this entry
    inheritance_depth: int = 0

    # Value handling
    value: Optional[str] = None
    value_redacted: bool = True
    value_fingerprint: Optional[str] = None
    value_length: Optional[int] = None

    @property
    def merge_key(self) -> tuple:
        """Return the key GitLab uses to distinguish variables."""
        return (self.key, self.environment_scope)

    @property
    def display_key(self) -> str:
        """Return the key prefixed with its origin marker."""
        return f"{ORIGIN_MARKERS.get(self.origin, '')}{self.key}"

    @property
    def display_value(self) -> str:
        """Return the value or its redacted stand-in for display."""
        if self.hidden:
            return "<hidden>"
        if not self.value_redacted:
            return self.value if self.value is not None else ""
        if self.value_fingerprint is None:
            return "<n/a>"
        return f"{self.value_fingerprint} ({self.value_length} chars)"

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable dict honouring the redaction policy."""
        data: Dict[str, Any] = {
            "key": self.key,
            "variable_type": self.variable_type,
            "environment_scope": self.environment_scope,
            "protected": self.protected,
            "masked": self.masked,
            "hidden": self.hidden,
            "raw": self.raw,
            "description": self.description,
            "scope_kind": self.scope_kind,
            "scope_path": self.scope_path,
            "defined_in": self.defined_in,
            "origin": self.origin,
            "overrides": self.overrides,
            "overridden_by": self.overridden_by,
            "inheritance_depth": self.inheritance_depth,
        }
        if self.value_redacted:
            data.update(
                {
                    "value": None,
                    "value_redacted": True,
                    "value_fingerprint": self.value_fingerprint,
                    "value_length": self.value_length,
                }
            )
        else:
            data.update({"value": self.value, "value_redacted": False})
        return data
