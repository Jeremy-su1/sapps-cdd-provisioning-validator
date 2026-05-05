"""NSX-T DFW rule executor.

dry_run=True (default): records what would be applied without calling any API.
dry_run=False: raises NotImplementedError (live execution not yet implemented).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ExecutorError(Exception):
    """Raised when execution cannot proceed due to configuration problems."""


@dataclass
class ExecutionResult:
    applied: list[dict[str, Any]]
    skipped: list[dict[str, Any]]
    errors:  list[dict[str, Any]]


class NsxtDfwExecutor:
    """Apply NSX-T DFW action plan items.

    Args:
        host:     NSX-T Manager hostname or IP.
        token:    Bearer token for API authentication.
        dry_run:  When True (default), simulate execution without API calls.
    """

    def __init__(self, host: str | None, token: str | None, dry_run: bool = True) -> None:
        self.host    = host
        self.token   = token
        self.dry_run = dry_run

    def apply(self, plan_items: list[dict]) -> ExecutionResult:
        """Execute a list of DFW action plan items.

        In dry_run mode: records what would be applied, no API calls.
        In real mode: raises NotImplementedError.
        """
        if not self.dry_run:
            if not self.host or not self.token:
                raise ExecutorError(
                    "NSX-T Manager host and token are required for real execution."
                )
            raise NotImplementedError(
                "Live NSX-T DFW execution not yet implemented. Use dry_run=True."
            )

        return self._apply_dry_run(plan_items)

    def _apply_dry_run(self, plan_items: list[dict]) -> ExecutionResult:
        applied: list[dict] = []
        skipped: list[dict] = []
        errors:  list[dict] = []

        for item in plan_items:
            action = item.get("action")
            if action == "create":
                applied.append({**item, "dry_run": True})
            elif action == "skip":
                skipped.append(item)
            else:
                errors.append(item)

        return ExecutionResult(applied=applied, skipped=skipped, errors=errors)
