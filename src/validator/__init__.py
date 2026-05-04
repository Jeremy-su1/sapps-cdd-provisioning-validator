"""Drift detection — compares desired state vs actual state."""

from typing import Any


def detect_drift(
    desired_state: dict[str, Any],
    actual_state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return list of drift findings. Not yet implemented."""
    raise NotImplementedError("drift-validator not yet implemented")
