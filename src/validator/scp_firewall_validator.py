"""SCP Firewall desired-vs-actual rule validator.

Two comparison modes:
  validate_scp_firewall        — ID-based match: desired resource_id vs actual resource_id
  validate_realized_vs_actual  — content-based match: (source_ip, target_ip, protocol, port)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_COMPARE_FIELDS = ("action", "port", "protocol", "source_ip", "target_ip")
_CONTENT_KEY_FIELDS = ("source_ip", "target_ip", "protocol", "port")


@dataclass
class ScpFirewallValidationResult:
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
        if dv != av:
            diff[f] = {"desired": dv, "actual": av}
    return diff


def validate_scp_firewall(
    desired_rules: list[dict],
    actual_rules: list[dict],
) -> ScpFirewallValidationResult:
    """Compare desired SCP Firewall rules against actual collected state.

    Args:
        desired_rules:  List of desired rule dicts (from planner or desired_state).
        actual_rules:   List of actual rule dicts (from collector), each keyed by 'resource_id'.

    Returns:
        ScpFirewallValidationResult with matched, unmatched, and unexpected buckets.
    """
    result     = ScpFirewallValidationResult()
    actual_map = {r["resource_id"]: r for r in actual_rules}
    seen_ids:  set[str] = set()

    for desired in desired_rules:
        resource_id = desired["resource_id"]
        actual      = actual_map.get(resource_id)

        if actual is None:
            result.unmatched.append({
                "resource_id": resource_id,
                "status":      "missing",
                "desired":     desired,
                "actual":      None,
            })
        else:
            seen_ids.add(resource_id)
            diff = _field_diff(desired, actual)
            if diff:
                result.unmatched.append({
                    "resource_id": resource_id,
                    "status":      "diverged",
                    "desired":     desired,
                    "actual":      actual,
                    "diff":        diff,
                })
            else:
                result.matched.append({
                    "resource_id": resource_id,
                    "status":      "matched",
                    "desired":     desired,
                    "actual":      actual,
                })

    desired_ids = {d["resource_id"] for d in desired_rules}
    for actual in actual_rules:
        if actual["resource_id"] not in desired_ids:
            result.unexpected.append({
                "resource_id": actual["resource_id"],
                "status":      "unexpected",
                "actual":      actual,
            })

    return result


# ---------------------------------------------------------------------------
# Content-based realized-vs-actual validation
# ---------------------------------------------------------------------------

def _content_key(rule: dict) -> tuple:
    return tuple(rule.get(f) for f in _CONTENT_KEY_FIELDS)


@dataclass
class RealizedValidationResult:
    matched:    list[dict[str, Any]] = field(default_factory=list)
    missing:    list[dict[str, Any]] = field(default_factory=list)
    unexpected: list[dict[str, Any]] = field(default_factory=list)

    _realized_count: int = field(default=0, repr=False)
    _actual_count:   int = field(default=0, repr=False)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "realized_rules": self._realized_count,
            "actual_rules":   self._actual_count,
            "matched":        len(self.matched),
            "missing":        len(self.missing),
            "unexpected":     len(self.unexpected),
        }


def validate_realized_vs_actual(
    realized_rules: list[dict],
    actual_rules: list[dict],
) -> RealizedValidationResult:
    """Compare realized SCP Firewall rules against actual collected state.

    Uses content-based matching on (source_ip, target_ip, protocol, port).
    Actual rules may have different native IDs from the SCP API — ID-based
    matching is not reliable here.

    Args:
        realized_rules: Flat list of realized rule dicts from ScpFirewallRealizationResult.flat_rules.
        actual_rules:   List of normalized actual rule dicts from ScpFirewallCollector.collect().

    Returns:
        RealizedValidationResult with matched, missing, and unexpected buckets.
    """
    result = RealizedValidationResult(
        _realized_count=len(realized_rules),
        _actual_count=len(actual_rules),
    )

    actual_by_key: dict[tuple, dict] = {}
    for actual in actual_rules:
        key = _content_key(actual)
        actual_by_key[key] = actual

    matched_keys: set[tuple] = set()

    for realized in realized_rules:
        key = _content_key(realized)
        actual = actual_by_key.get(key)
        if actual is not None:
            matched_keys.add(key)
            result.matched.append({
                "realized_rule_id": realized.get("realized_rule_id"),
                "status":           "matched",
                "realized":         realized,
                "actual":           actual,
            })
        else:
            result.missing.append({
                "realized_rule_id": realized.get("realized_rule_id"),
                "status":           "missing",
                "realized":         realized,
            })

    for actual in actual_rules:
        key = _content_key(actual)
        if key not in matched_keys:
            result.unexpected.append({
                "resource_id": actual.get("resource_id"),
                "status":      "unexpected",
                "actual":      actual,
            })

    return result
