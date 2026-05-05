"""Debug script: full NSX-T DFW end-to-end pipeline in dry-run mode.

Pipeline:
  1. parse_s2d()           → desired_state
  2. classify_candidates() → dfw_candidates
  3. plan_dfw()            → action plan
  4. NsxtDfwExecutor       → dry-run execution result
  5. NsxtDfwCollector      → empty actual state (dry-run)
  6. validate_dfw()        → validation result
  7. Write outputs/debug_nsxt_dfw_e2e.json

Usage (from repo root):
    python scripts/debug_nsxt_dfw_e2e.py [path/to/workbook.xlsx]

No API calls are made. All execution and collection is dry-run.
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
from src.planner.dfw_planner import plan_dfw
from src.executor.nsxt_dfw_executor import NsxtDfwExecutor
from src.collector.nsxt_dfw_collector import NsxtDfwCollector
from src.validator.dfw_validator import validate_dfw


def _find_sample() -> Path:
    samples = sorted((_REPO_ROOT / "samples").glob("*.xlsx"))
    if not samples:
        raise FileNotFoundError("No .xlsx file found in samples/.")
    return samples[0]


def _inject_mock_dfw_candidates() -> list[dict]:
    """Return synthetic DFW candidates when real workbook produces zero.

    Used so the e2e pipeline can demonstrate all code paths without a real
    workbook that happens to contain internal→internal rules.
    """
    return [
        {
            "rule_id":               "mock-dfw-001",
            "rule_name":             "allow-app-to-db",
            "src_hostname":          "vhapp01",
            "src_ip":                "10.0.1.11",
            "dst_hostname":          "vhdb01",
            "dst_ip":                "10.0.1.21",
            "protocol":              "TCP",
            "port":                  "1521",
            "port_expression":       False,
            "action":                "permit",
            "applied_to":            "source",
            "requires_manual_review": False,
        },
        {
            "rule_id":               "mock-dfw-002",
            "rule_name":             "allow-app-to-nfs",
            "src_hostname":          "vhapp02",
            "src_ip":                "10.0.1.12",
            "dst_hostname":          "vhnfs01",
            "dst_ip":                "10.0.1.31",
            "protocol":              "TCP",
            "port":                  "2049",
            "port_expression":       False,
            "action":                "permit",
            "applied_to":            "source",
            "requires_manual_review": False,
        },
        {
            "rule_id":               "mock-dfw-003",
            "rule_name":             "allow-hana-sr",
            "src_hostname":          "vhdb01",
            "src_ip":                "10.0.1.21",
            "dst_hostname":          "vhdb02",
            "dst_ip":                "10.0.1.22",
            "protocol":              "TCP",
            "port":                  "40000-40099",
            "port_expression":       True,
            "action":                "permit",
            "applied_to":            "both",
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

    dfw_candidates = classification.dfw_candidates
    if not dfw_candidates:
        print("  No DFW candidates from workbook — injecting mock data for pipeline demo")
        dfw_candidates = _inject_mock_dfw_candidates()
    else:
        print(f"  DFW candidates from workbook: {len(dfw_candidates)}")

    # ── Step 2: Plan ─────────────────────────────────────────────────────────
    print("\n[Plan]")
    plan_result = plan_dfw(dfw_candidates, actual_rules=None)
    _print_summary("Plan summary", plan_result.summary)
    if plan_result.conflicts:
        print("  Conflicts:")
        for c in plan_result.conflicts:
            print(f"    [{c['resource_id']}] {c['reason']}")

    all_plan_items = plan_result.actions + plan_result.conflicts

    # ── Step 3: Execute (dry-run) ─────────────────────────────────────────────
    print("\n[Execute — dry-run]")
    executor      = NsxtDfwExecutor(host="nsxt.example.com", token="<placeholder>", dry_run=True)
    exec_result   = executor.apply(all_plan_items)
    _print_summary("Execution summary", {
        "applied": len(exec_result.applied),
        "skipped": len(exec_result.skipped),
        "errors":  len(exec_result.errors),
    })

    # ── Step 4: Collect actual state (dry-run → empty) ───────────────────────
    print("\n[Collect actual state — dry-run]")
    collector    = NsxtDfwCollector(host="nsxt.example.com", token="<placeholder>", dry_run=True)
    actual_rules = collector.collect()
    print(f"  Actual rules collected: {len(actual_rules)} (dry-run returns empty)")

    # ── Step 5: Validate ──────────────────────────────────────────────────────
    print("\n[Validate]")
    val_result = validate_dfw(dfw_candidates, actual_rules)
    _print_summary("Validation summary", val_result.summary)

    # ── Write output ──────────────────────────────────────────────────────────
    output = {
        "dfw_candidates": dfw_candidates,
        "plan": {
            "actions":   plan_result.actions,
            "conflicts": plan_result.conflicts,
            "summary":   plan_result.summary,
        },
        "execution": {
            "applied": exec_result.applied,
            "skipped": exec_result.skipped,
            "errors":  exec_result.errors,
            "dry_run": True,
        },
        "actual_rules": actual_rules,
        "validation": {
            "matched":    val_result.matched,
            "unmatched":  val_result.unmatched,
            "unexpected": val_result.unexpected,
            "summary":    val_result.summary,
        },
    }

    out_path = _REPO_ROOT / "outputs" / "debug_nsxt_dfw_e2e.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _find_sample()
    main(path)
