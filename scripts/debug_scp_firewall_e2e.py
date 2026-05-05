"""Debug script: full SCP Firewall end-to-end pipeline in dry-run mode.

Pipeline:
  1. parse_s2d()             → desired_state
  2. classify_candidates()   → tgw_candidates (SCP-managed customer firewall rules)
  3. plan_scp_firewall()     → action plan (create / skip / conflict)
  4. ScpFirewallExecutor     → dry-run execution result
  5. ScpFirewallCollector    → empty actual state (dry-run)
  6. validate_scp_firewall() → validation result (matched / unmatched / unexpected)
  7. Write outputs/debug_scp_firewall_e2e.json

Usage (from repo root):
    python scripts/debug_scp_firewall_e2e.py [path/to/workbook.xlsx]

No API or CLI calls are made. All execution and collection is dry-run.
backend_hint="scp" and execution_method_candidates=["scp_api","scp_cli"] appear
in every action item so the executor layer can select the integration method later.
"""
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.parser import parse_s2d
from src.classification.firewall_rules import (
    classify_candidates,
    build_vm_hostnames,
    build_subnet_networks,
)
from src.planner.scp_firewall_planner import plan_scp_firewall
from src.executor.scp_firewall_executor import ScpFirewallExecutor
from src.collector.scp_firewall_collector import ScpFirewallCollector
from src.validator.scp_firewall_validator import validate_scp_firewall


def _find_sample() -> Path:
    samples = sorted((_REPO_ROOT / "samples").glob("*.xlsx"))
    if not samples:
        raise FileNotFoundError("No .xlsx file found in samples/.")
    return samples[0]


def _inject_mock_tgw_candidates() -> list[dict]:
    """Return synthetic TGW candidates when the workbook produces an unusable set.

    Demonstrates all planner code paths: clean create, and manual-review conflict.
    """
    return [
        {
            "origin_idx":             0,
            "source_system":          "vhapp01",
            "source_category":        "cus_fw",
            "source_hostname":        "vhapp01",
            "source_ip":              "10.0.1.11",
            "target_system":          "external-dns",
            "target_category":        None,
            "target_hostname":        None,
            "target_ip":              "8.8.8.8",
            "port":                   "53",
            "port_expression":        False,
            "protocol":               "UDP",
            "expiration":             None,
            "purpose":                "allow DNS outbound",
            "requires_manual_review": False,
        },
        {
            "origin_idx":             1,
            "source_system":          "vhweb01",
            "source_category":        "cus_fw",
            "source_hostname":        "vhweb01",
            "source_ip":              "10.0.2.11",
            "target_system":          "cdn-endpoint",
            "target_category":        None,
            "target_hostname":        None,
            "target_ip":              "203.0.113.50",
            "port":                   "443",
            "port_expression":        False,
            "protocol":               "TCP",
            "expiration":             None,
            "purpose":                "allow HTTPS to CDN",
            "requires_manual_review": False,
        },
        {
            "origin_idx":             2,
            "source_system":          "unknown-system",
            "source_category":        "cus_sg",
            "source_hostname":        None,
            "source_ip":              "0",
            "target_system":          "vhdb01",
            "target_category":        None,
            "target_hostname":        "vhdb01",
            "target_ip":              "10.0.1.21",
            "port":                   "5432",
            "port_expression":        False,
            "protocol":               "TCP",
            "expiration":             None,
            "purpose":                "allow DB access from unknown source",
            "requires_manual_review": True,
        },
    ]


def _print_summary(label: str, data: dict) -> None:
    print(f"\n  {label}:")
    for k, v in data.items():
        print(f"    {k}: {v}")


def main(workbook_path: Path) -> None:
    print(f"Opening: {workbook_path}")
    state = parse_s2d(str(workbook_path))

    # ── Step 1: Classify firewall candidates ─────────────────────────────────
    vm_hostnames    = build_vm_hostnames(state["vmware_vm"])
    subnet_networks = build_subnet_networks(state["network"]["subnets"])
    classification  = classify_candidates(
        state["firewall_rule_candidates"],
        vm_hostnames,
        subnet_networks,
    )

    tgw_candidates = classification.tgw_candidates
    print(f"\n[Classify]")
    print(f"  TGW candidates from workbook: {len(tgw_candidates)}")
    print(f"  DFW candidates from workbook: {len(classification.dfw_candidates)}")
    print(f"  Reference-only rules:         {len(classification.reference_only)}")

    if not tgw_candidates:
        print("  No TGW candidates from workbook — injecting mock data for pipeline demo")
        tgw_candidates = _inject_mock_tgw_candidates()

    # ── Step 2: Plan ─────────────────────────────────────────────────────────
    print("\n[Plan]")
    plan_result = plan_scp_firewall(tgw_candidates, actual_rules=None)
    _print_summary("Plan summary", plan_result.summary)
    if plan_result.conflicts:
        print("  Conflicts:")
        for c in plan_result.conflicts:
            print(f"    [{c['resource_id']}] {c['reason']}")
    if plan_result.actions:
        sample = plan_result.actions[0]
        print(f"  backend_hint:                {sample['backend_hint']}")
        print(f"  execution_method_candidates: {sample['execution_method_candidates']}")

    all_plan_items = plan_result.actions + plan_result.conflicts

    # ── Step 3: Execute (dry-run) ─────────────────────────────────────────────
    print("\n[Execute — dry-run]")
    executor    = ScpFirewallExecutor(
        endpoint="https://scp.example.com",
        token="<placeholder>",
        dry_run=True,
        execution_method="scp_api",
    )
    exec_result = executor.apply(all_plan_items)
    _print_summary("Execution summary", {
        "applied": len(exec_result.applied),
        "skipped": len(exec_result.skipped),
        "errors":  len(exec_result.errors),
    })

    # ── Step 4: Collect actual state (dry-run → empty) ───────────────────────
    print("\n[Collect actual state — dry-run]")
    collector    = ScpFirewallCollector(
        endpoint="https://scp.example.com",
        token="<placeholder>",
        dry_run=True,
        execution_method="scp_api",
    )
    actual_rules = collector.collect()
    print(f"  Actual rules collected: {len(actual_rules)} (dry-run returns empty)")

    # ── Step 5: Validate ──────────────────────────────────────────────────────
    print("\n[Validate]")
    desired_for_validation = [
        {**rule, "resource_id": f"scp-fw-{rule['origin_idx']}"}
        for rule in tgw_candidates
        if not rule.get("requires_manual_review")
    ]
    val_result = validate_scp_firewall(desired_for_validation, actual_rules)
    _print_summary("Validation summary", val_result.summary)

    # ── Write output ──────────────────────────────────────────────────────────
    output = {
        "tgw_candidates": tgw_candidates,
        "plan": {
            "actions":   plan_result.actions,
            "conflicts": plan_result.conflicts,
            "summary":   plan_result.summary,
        },
        "execution": {
            "applied":          exec_result.applied,
            "skipped":          exec_result.skipped,
            "errors":           exec_result.errors,
            "dry_run":          True,
            "execution_method": executor.execution_method,
        },
        "actual_rules": actual_rules,
        "validation": {
            "matched":    val_result.matched,
            "unmatched":  val_result.unmatched,
            "unexpected": val_result.unexpected,
            "summary":    val_result.summary,
        },
    }

    out_path = _REPO_ROOT / "outputs" / "debug_scp_firewall_e2e.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _find_sample()
    main(path)
