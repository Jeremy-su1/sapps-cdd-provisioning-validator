"""VMware VM provisioning planner — dry-run mode only.

Input:  vmware_vm[] from desired_state, optional list of actual VM dicts.
Output: VmwarePlanResult(actions, conflicts, summary)

Actions are ordered: PRD → DR → QAS → DEV, then by host_no ascending.
Conflicts are emitted (not silently skipped) for:
  - placeholder IP values (0, 1, 2, 3, 4, "-")
  - missing required fields (vhost, phost, os_version, cpu_vcores, memory_gb)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.parser._utils import is_valid_ipv4
from src.schema.issues import DataQualityIssue

# Placeholder values that indicate an unresolved IP in the source workbook.
_PLACEHOLDER_IPS = {"0", "1", "2", "3", "4", "-", "", "None"}

# Provisioning order by landscape.
_LANDSCAPE_ORDER = {"PRD": 0, "DR": 1, "QAS": 2, "DEV": 3}

# Required fields checked before planning.
_REQUIRED_IDENTITY = ("vhost", "phost", "landscape", "sid", "role_type")
_REQUIRED_COMPUTE  = ("os_version", "cpu_vcores", "memory_gb", "appl_storage_gb")


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class VmwarePlanResult:
    actions:   list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    issues:    list[DataQualityIssue] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {"create": 0, "update": 0, "skip": 0, "conflict": 0}
        for a in self.actions:
            counts[a["action"]] += 1
        counts["conflict"] += len(self.conflicts)
        return counts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_placeholder_ip(value: object) -> bool:
    return str(value).strip() in _PLACEHOLDER_IPS


def _sort_key(vm: dict) -> tuple:
    landscape = vm.get("identity", {}).get("landscape", "")
    host_no   = str(vm.get("metadata", {}).get("host_no") or "99")
    order     = _LANDSCAPE_ORDER.get(landscape, 99)
    # Sort host_no numerically when possible.
    try:
        return (order, int(host_no))
    except (ValueError, TypeError):
        return (order, host_no)


def _conflict_item(vhost: str, reason: str, desired: dict, actual: Any, conflict_reason: str) -> dict:
    return {
        "action":            "conflict",
        "resource_type":     "vmware_vm",
        "resource_id":       vhost,
        "desired":           desired,
        "actual":            actual,
        "diff":              None,
        "reason":            reason,
        "conflict_reason":   conflict_reason,
        "requires_approval": True,
    }


def _action_item(action: str, vhost: str, desired: dict, actual: Any, diff: dict | None) -> dict:
    return {
        "action":            action,
        "resource_type":     "vmware_vm",
        "resource_id":       vhost,
        "desired":           desired,
        "actual":            actual,
        "diff":              diff,
        "reason":            None,
        "requires_approval": False,
    }


def _compute_diff(desired: dict, actual: dict) -> dict:
    """Return flat dict of fields that differ between desired compute/network and actual."""
    diff: dict = {}
    desired_flat = {**desired.get("compute", {}), **desired.get("network", {})}
    for k, dv in desired_flat.items():
        av = actual.get(k)
        if av is not None and av != dv:
            diff[k] = {"desired": dv, "actual": av}
    return diff


# ---------------------------------------------------------------------------
# Pre-flight validation
# ---------------------------------------------------------------------------

def _validate_vm(vm: dict) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    identity = vm.get("identity", {})
    compute  = vm.get("compute",  {})
    network  = vm.get("network",  {})
    vhost    = identity.get("vhost") or ""

    for f in _REQUIRED_IDENTITY:
        if not identity.get(f):
            issues.append(DataQualityIssue(
                issue_type="missing_required_field",
                severity="error",
                resource="vmware_vm",
                resource_id=vhost or "<unknown>",
                field=f"identity.{f}",
                raw_value=identity.get(f),
                message=f"identity.{f} is required but empty or null",
            ))

    for f in _REQUIRED_COMPUTE:
        if compute.get(f) is None:
            issues.append(DataQualityIssue(
                issue_type="missing_required_field",
                severity="error",
                resource="vmware_vm",
                resource_id=vhost or "<unknown>",
                field=f"compute.{f}",
                raw_value=None,
                message=f"compute.{f} is required but null",
            ))

    admin_ip = network.get("admin_ip")
    if admin_ip is not None and _is_placeholder_ip(admin_ip):
        issues.append(DataQualityIssue(
            issue_type="placeholder_ip",
            severity="error",
            resource="vmware_vm",
            resource_id=vhost or "<unknown>",
            field="network.admin_ip",
            raw_value=admin_ip,
            message=f"network.admin_ip is a placeholder value ({admin_ip!r}); cannot provision without a real IP",
        ))

    return issues


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

def plan_vmware(
    desired_vms: list[dict],
    actual_vms: list[dict] | None,
) -> VmwarePlanResult:
    """Plan VMware VM provisioning actions in dry-run mode.

    Args:
        desired_vms:  vmware_vm[] from parse_s2d() output.
        actual_vms:   List of actual VM state dicts keyed by 'vhost', or None
                      when no actual state is available (all become 'create').

    Returns:
        VmwarePlanResult with ordered actions, conflicts, and a summary count.
    """
    result     = VmwarePlanResult()
    actual_map = {v["vhost"]: v for v in (actual_vms or [])}
    pending:   list[dict] = []       # validated VMs to plan

    # ── Pre-flight validation ────────────────────────────────────────────────
    for vm in desired_vms:
        issues = _validate_vm(vm)
        result.issues.extend(issues)
        if issues:
            vhost = vm.get("identity", {}).get("vhost") or "<unknown>"
            reason = "; ".join(i.message for i in issues)
            primary_type = issues[0].issue_type
            conflict_reason = primary_type if primary_type in ("placeholder_ip", "missing_required_field") else "missing_required_field"
            result.conflicts.append(
                _conflict_item(vhost, reason, vm, actual_map.get(vhost), conflict_reason)
            )
        else:
            pending.append(vm)

    # ── Sort valid VMs by provisioning order ─────────────────────────────────
    pending.sort(key=_sort_key)

    # ── Plan each validated VM ───────────────────────────────────────────────
    for vm in pending:
        vhost  = vm["identity"]["vhost"]
        actual = actual_map.get(vhost)

        if actual is None:
            result.actions.append(_action_item("create", vhost, vm, None, None))
        else:
            diff = _compute_diff(vm, actual)
            if diff:
                result.actions.append(_action_item("update", vhost, vm, actual, diff))
            else:
                result.actions.append(_action_item("skip", vhost, vm, actual, None))

    return result
