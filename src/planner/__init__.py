"""Deterministic provisioning planner."""

from typing import Any, Literal

ActionKind = Literal["create", "update", "skip", "conflict"]


def build_action_plan(
    desired_state: dict[str, Any],
    current_state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return ordered action list. Not yet implemented."""
    raise NotImplementedError("provisioning-planner not yet implemented")
