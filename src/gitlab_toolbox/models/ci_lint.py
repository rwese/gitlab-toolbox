"""CI lint data models."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LintJob:
    """Represents a resolved job from the GitLab CI Lint API.

    Populated only when the API was called with ``include_jobs=true``.
    Field names mirror the GitLab documentation.
    """

    name: str
    stage: Optional[str] = None
    before_script: List[str] = field(default_factory=list)
    script: List[str] = field(default_factory=list)
    after_script: List[str] = field(default_factory=list)
    tag_list: List[str] = field(default_factory=list)
    only: Optional[Dict[str, Any]] = None
    except_config: Optional[Dict[str, Any]] = None
    environment: Optional[str] = None
    when: Optional[str] = None
    allow_failure: bool = False
    needs: Optional[Any] = None


@dataclass
class CILintResult:
    """Represents the response of the GitLab CI Lint API.

    Wraps both ``POST /projects/:id/ci/lint`` and
    ``GET /projects/:id/ci/lint`` which share the same response shape.
    """

    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    merged_yaml: Optional[str] = None
    includes: List[Dict[str, Any]] = field(default_factory=list)
    jobs: List[LintJob] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Return True if the lint result has validation errors."""
        return not self.valid or bool(self.errors)

    @property
    def has_warnings(self) -> bool:
        """Return True if the lint result has warnings."""
        return bool(self.warnings)
