"""NSX-T DFW rule provisioning planner — dry-run mode only.

Input:  dfw_candidates[] from classification layer, optional list of actual rule dicts.
Output: DfwPlanResult(actions, conflicts, summary)

Rules with requires_manual_review=True are always emitted as conflict, not create.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DfwPlanResult:
    actions:   list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {"create": 0, "skip": 0, "conflict": 0}
        for a in self.actions:
            counts[a["action"]] += 1
        counts["conflict"] += len(self.conflicts)
        return counts


def _conflict_item(rule_id: str, reason: str, desired: dict, actual: Any, conflict_reason: str) -> dict:
    return {
        "action":            "conflict",
        "resource_type":     "nsxt_dfw_rule",
        "resource_id":       rule_id,
        "desired":           desired,
        "actual":            actual,
        "reason":            reason,
        "conflict_reason":   conflict_reason,
        "requires_approval": True,
    }


def _action_item(action: str, rule_id: str, desired: dict, actual: Any) -> dict:
    return {
        "action":            action,
        "resource_type":     "nsxt_dfw_rule",
        "resource_id":       rule_id,
        "desired":           desired,
        "actual":            actual,
        "requires_approval": False,
    }


def plan_dfw(
    desired_rules: list[dict],
    actual_rules: list[dict] | None,
) -> DfwPlanResult:
    """Plan NSX-T DFW rule provisioning actions in dry-run mode.

    Args:
        desired_rules:  dfw_candidates[] from classify_candidates().
        actual_rules:   List of actual DFW rule dicts keyed by 'rule_id', or None.

    Returns:
        DfwPlanResult with ordered actions, conflicts, and a summary count.
    """
    result     = DfwPlanResult()
    actual_map = {r["rule_id"]: r for r in (actual_rules or [])}

    for rule in desired_rules:
        rule_id = rule.get("rule_id", "<unknown>")

        if rule.get("requires_manual_review"):
            result.conflicts.append(
                _conflict_item(
                    rule_id,
                    "Rule requires manual review before provisioning",
                    rule,
                    actual_map.get(rule_id),
                    "requires_manual_review",
                )
            )
            continue

        actual = actual_map.get(rule_id)
        if actual is None:
            result.actions.append(_action_item("create", rule_id, rule, None))
        else:
            result.actions.append(_action_item("skip", rule_id, rule, actual))

    return result
