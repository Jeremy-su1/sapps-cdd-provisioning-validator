"""Desired-state JSON schema definitions and validation."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def validate(desired_state: dict[str, Any]) -> ValidationResult:
    """Validate desired_state against the schema. Not yet implemented."""
    raise NotImplementedError("desired-state-schema validator not yet implemented")
