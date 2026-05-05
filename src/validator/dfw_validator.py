"""NSX-T DFW desired-vs-actual rule validator.

Compares a list of desired DFW rules against the collected actual state.
Returns matched, unmatched (missing or diverged), and unexpected rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_COMPARE_FIELDS = ("action", "port", "protocol")


@dataclass
class DfwValidationResult:
    matched:    list[dict[str, Any]] = field(default_factory=list)
    unmatched:  list[dict[str, Any]] = field(default_factory=list)
    unexpected: list[dict[str, Any]] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "matched":    len(self.matched),
            "unmatched":  len(self.unmatched),
            "unexpected": len(self.unexpected),
        }


def _field_diff(desired: dict, actual: dict) -> dict:
    diff = {}
    for f in _COMPARE_FIELDS:
        dv = desired.get(f)
        av = actual.get(f)
        if dv is not None and av is not None and dv != av:
            diff[f] = {"desired": dv, "actual": av}
    return diff


def validate_dfw(
    desired_rules: list[dict],
    actual_rules: list[dict],
) -> DfwValidationResult:
    """Compare desired DFW rules against actual collected state.

    Args:
        desired_rules:  List of desired rule dicts (from planner or desired_state).
        actual_rules:   List of actual rule dicts (from collector).

    Returns:
        DfwValidationResult with matched, unmatched, and unexpected buckets.
    """
    result     = DfwValidationResult()
    actual_map = {r["rule_id"]: r for r in actual_rules}
    seen_ids:  set[str] = set()

    for desired in desired_rules:
        rule_id = desired["rule_id"]
        actual  = actual_map.get(rule_id)

        if actual is None:
            result.unmatched.append({
                "resource_id": rule_id,
                "status":      "missing",
                "desired":     desired,
                "actual":      None,
            })
        else:
            seen_ids.add(rule_id)
            diff = _field_diff(desired, actual)
            if diff:
                result.unmatched.append({
                    "resource_id": rule_id,
                    "status":      "diverged",
                    "desired":     desired,
                    "actual":      actual,
                    "diff":        diff,
                })
            else:
                result.matched.append({
                    "resource_id": rule_id,
                    "status":      "matched",
                    "desired":     desired,
                    "actual":      actual,
                })

    for actual in actual_rules:
        rule_id = actual["rule_id"]
        if rule_id not in seen_ids:
            desired_ids = {d["rule_id"] for d in desired_rules}
            if rule_id not in desired_ids:
                result.unexpected.append({
                    "resource_id": rule_id,
                    "status":      "unexpected",
                    "actual":      actual,
                })

    return result
