"""SCP Firewall rule executor.

dry_run=True (default): records what would be applied without calling any API or CLI.
dry_run=False: raises NotImplementedError (live execution not yet implemented).

execution_method selects between "scp_api" and "scp_cli" for future real execution.
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


class ScpFirewallExecutor:
    """Apply SCP Firewall action plan items via SCP API or SCP CLI.

    Args:
        endpoint:         SCP API base URL or CLI target identifier.
        token:            API token or credential for SCP.
        dry_run:          When True (default), simulate execution without API/CLI calls.
        execution_method: "scp_api" (default) or "scp_cli".
    """

    def __init__(
        self,
        endpoint: str | None,
        token: str | None,
        dry_run: bool = True,
        execution_method: str = "scp_api",
    ) -> None:
        self.endpoint         = endpoint
        self.token            = token
        self.dry_run          = dry_run
        self.execution_method = execution_method

    def apply(self, plan_items: list[dict]) -> ExecutionResult:
        """Execute a list of SCP Firewall action plan items.

        In dry_run mode: records what would be applied, no API/CLI calls.
        In real mode: raises NotImplementedError.
        """
        if not self.dry_run:
            if not self.endpoint or not self.token:
                raise ExecutorError(
                    "SCP endpoint and token are required for real execution."
                )
            raise NotImplementedError(
                f"Live SCP Firewall execution via {self.execution_method!r} not yet implemented. "
                "Use dry_run=True."
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
