"""SCP Firewall rule provisioning planner — dry-run mode only.

Input:  tgw_candidates[] from classification layer, optional list of actual rule dicts.
Output: ScpFirewallPlanResult(actions, conflicts, summary)

Rules with requires_manual_review=True are always emitted as conflict, not create.
Action items carry backend_hint and execution_method_candidates so the executor
layer can select between SCP API and SCP CLI without planner changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_BACKEND_HINT              = "scp"
_EXECUTION_METHOD_CANDIDATES = ["scp_api", "scp_cli"]


def _resource_id(candidate: dict) -> str:
    return f"scp-fw-{candidate.get('origin_idx', 0)}"


@dataclass
class ScpFirewallPlanResult:
    actions:   list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {"create": 0, "skip": 0, "conflict": 0}
        for a in self.actions:
            counts[a["action"]] += 1
        counts["conflict"] += len(self.conflicts)
        return counts


def _derive_conflict_reason(rule: dict) -> tuple[str, list[str]]:
    """Return (primary_reason, secondary_flags) from enriched candidate fields.

    Priority order (first matching rule wins as primary):
      1. unknown_both_endpoints  — src AND tgt both unknown after endpoint resolution
      2. unknown_source_endpoint — source endpoint class is "unknown"
      3. unknown_target_endpoint — target endpoint class is "unknown"
      4. cidr_subnet_rule        — source or target is CIDR notation
      5. complex_port_expression — port field contains a complex expression
      6. requires_manual_review  — catch-all
    """
    src_class      = rule.get("src_endpoint_class")
    tgt_class      = rule.get("tgt_endpoint_class")
    src_is_cidr    = rule.get("src_is_cidr", False)
    tgt_is_cidr    = rule.get("tgt_is_cidr", False)
    complex_port   = rule.get("port_expression", False)

    flags: list[str] = []
    if src_is_cidr or tgt_is_cidr:
        flags.append("cidr_subnet_rule")
    if complex_port:
        flags.append("complex_port_expression")

    if src_class == "unknown" and tgt_class == "unknown":
        primary = "unknown_both_endpoints"
    elif src_class == "unknown":
        primary = "unknown_source_endpoint"
    elif tgt_class == "unknown":
        primary = "unknown_target_endpoint"
    elif src_is_cidr or tgt_is_cidr:
        primary = "cidr_subnet_rule"
    elif complex_port:
        primary = "complex_port_expression"
    else:
        primary = "requires_manual_review"

    secondary = [f for f in flags if f != primary]
    return primary, secondary


def _conflict_item(resource_id: str, reason: str, desired: dict, actual: Any, conflict_reason: str, conflict_flags: list[str]) -> dict:
    return {
        "action":                      "conflict",
        "resource_type":               "scp_firewall_rule",
        "resource_id":                 resource_id,
        "desired":                     desired,
        "actual":                      actual,
        "reason":                      reason,
        "conflict_reason":             conflict_reason,
        "conflict_flags":              conflict_flags,
        "requires_approval":           True,
        "backend_hint":                _BACKEND_HINT,
        "execution_method_candidates": _EXECUTION_METHOD_CANDIDATES,
    }


def _action_item(action: str, resource_id: str, desired: dict, actual: Any) -> dict:
    return {
        "action":                      action,
        "resource_type":               "scp_firewall_rule",
        "resource_id":                 resource_id,
        "desired":                     desired,
        "actual":                      actual,
        "requires_approval":           False,
        "backend_hint":                _BACKEND_HINT,
        "execution_method_candidates": _EXECUTION_METHOD_CANDIDATES,
    }


def plan_scp_firewall(
    desired_rules: list[dict],
    actual_rules: list[dict] | None,
) -> ScpFirewallPlanResult:
    """Plan SCP Firewall rule provisioning actions in dry-run mode.

    Args:
        desired_rules:  tgw_candidates[] from classify_candidates().
        actual_rules:   List of actual SCP firewall rule dicts keyed by 'resource_id', or None.

    Returns:
        ScpFirewallPlanResult with ordered actions, conflicts, and a summary count.
    """
    result     = ScpFirewallPlanResult()
    actual_map = {r["resource_id"]: r for r in (actual_rules or [])}

    for rule in desired_rules:
        rid = _resource_id(rule)

        if rule.get("requires_manual_review"):
            primary, secondary = _derive_conflict_reason(rule)
            result.conflicts.append(
                _conflict_item(
                    rid,
                    "Rule requires manual review before provisioning",
                    rule,
                    actual_map.get(rid),
                    primary,
                    secondary,
                )
            )
            continue

        actual = actual_map.get(rid)
        if actual is None:
            result.actions.append(_action_item("create", rid, rule, None))
        else:
            result.actions.append(_action_item("skip", rid, rule, actual))

    return result
