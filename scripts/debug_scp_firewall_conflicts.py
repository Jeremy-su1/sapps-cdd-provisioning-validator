"""Debug script: analyze SCP Firewall conflicts by taxonomy.

Pipeline:
  1. parse_s2d()               → desired_state
  2. classify_candidates()     → tgw_candidates (with enriched endpoint fields)
  3. plan_scp_firewall()       → action plan with rich conflict_reason / conflict_flags
  4. Analyze conflicts by:
       - conflict_reason (primary)
       - conflict_flags (secondary)
       - src/tgt endpoint_class combinations
       - CIDR vs host-IP distribution
       - auto-resolvable candidates
  5. Write outputs/debug_scp_firewall_conflicts.json

Usage (from repo root):
    python scripts/debug_scp_firewall_conflicts.py [path/to/workbook.xlsx]
"""
import json
import sys
import ipaddress
from collections import Counter
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


def _find_sample() -> Path:
    samples = sorted((_REPO_ROOT / "samples").glob("*.xlsx"))
    if not samples:
        raise FileNotFoundError("No .xlsx file found in samples/.")
    return samples[0]


def _build_platform_networks(subnets: list[dict]) -> list:
    """Extract platform (internal group) subnets for use as platform_networks."""
    nets = []
    for s in subnets:
        if s.get("group") == "internal":
            raw = s.get("ip_range")
            if raw:
                try:
                    nets.append(ipaddress.ip_network(str(raw).strip(), strict=False))
                except ValueError:
                    pass
    return nets


def _is_auto_resolvable(conflict: dict) -> bool:
    """Heuristic: can this conflict likely be auto-resolved after further validation?

    Auto-resolvable when:
    - Primary reason is cidr_subnet_rule (CIDR policy, not ambiguous endpoint)
    - Both endpoints are NOT unknown (we know what they are, just CIDR format)
    - Port expression is the only secondary concern (can be validated)

    These candidates still require human sign-off but the data is sufficient
    to auto-generate a proposed rule without further investigation.
    """
    reason  = conflict.get("conflict_reason")
    desired = conflict.get("desired", {})
    src_cls = desired.get("src_endpoint_class")
    tgt_cls = desired.get("tgt_endpoint_class")

    if reason in ("unknown_both_endpoints", "unknown_source_endpoint", "unknown_target_endpoint"):
        return False
    if src_cls == "unknown" or tgt_cls == "unknown":
        return False
    if reason in ("cidr_subnet_rule", "complex_port_expression", "requires_manual_review"):
        return True
    return False


def main(workbook_path: Path) -> None:
    print(f"Opening: {workbook_path}")
    state = parse_s2d(str(workbook_path))

    vm_hostnames    = build_vm_hostnames(state["vmware_vm"])
    subnet_networks = build_subnet_networks(state["network"]["subnets"])
    platform_networks = _build_platform_networks(state["network"]["subnets"])

    classification = classify_candidates(
        state["firewall_rule_candidates"],
        vm_hostnames,
        subnet_networks,
        platform_networks=platform_networks,
    )

    tgw_candidates = classification.tgw_candidates
    plan_result    = plan_scp_firewall(tgw_candidates, actual_rules=None)
    conflicts      = plan_result.conflicts

    print(f"\nTotal TGW candidates: {len(tgw_candidates)}")
    print(f"  → create:   {plan_result.summary['create']}")
    print(f"  → conflict: {plan_result.summary['conflict']}")

    # ── Conflict breakdown by primary reason ──────────────────────────────────
    reason_counts = Counter(c["conflict_reason"] for c in conflicts)
    print("\nConflict breakdown by primary reason:")
    for reason, count in reason_counts.most_common():
        print(f"  {reason:<35} {count:>4}")

    # ── Breakdown by secondary flags ──────────────────────────────────────────
    flag_counts: Counter = Counter()
    for c in conflicts:
        for f in c.get("conflict_flags", []):
            flag_counts[f] += 1
    if flag_counts:
        print("\nSecondary conflict flags:")
        for flag, count in flag_counts.most_common():
            print(f"  {flag:<35} {count:>4}")

    # ── Endpoint class combinations ───────────────────────────────────────────
    combo_counts: Counter = Counter()
    for c in conflicts:
        d = c.get("desired", {})
        src = d.get("src_endpoint_class", "?")
        tgt = d.get("tgt_endpoint_class", "?")
        combo_counts[f"{src} → {tgt}"] += 1
    print("\nEndpoint class combinations in conflicts:")
    for combo, count in combo_counts.most_common():
        print(f"  {combo:<45} {count:>4}")

    # ── CIDR distribution ─────────────────────────────────────────────────────
    src_cidr = sum(1 for c in conflicts if c["desired"].get("src_is_cidr"))
    tgt_cidr = sum(1 for c in conflicts if c["desired"].get("tgt_is_cidr"))
    both_cidr = sum(1 for c in conflicts
                    if c["desired"].get("src_is_cidr") and c["desired"].get("tgt_is_cidr"))
    print(f"\nCIDR notation usage in conflicts:")
    print(f"  src_is_cidr:  {src_cidr}")
    print(f"  tgt_is_cidr:  {tgt_cidr}")
    print(f"  both CIDR:    {both_cidr}")

    # ── Auto-resolvable candidates ────────────────────────────────────────────
    auto_res = [c for c in conflicts if _is_auto_resolvable(c)]
    needs_inv = [c for c in conflicts if not _is_auto_resolvable(c)]
    print(f"\nAuto-resolvable candidates (data sufficient, needs human approval): {len(auto_res)}")
    print(f"Requires investigation (endpoints genuinely unknown):                {len(needs_inv)}")

    # ── Write output ──────────────────────────────────────────────────────────
    summary_by_reason = dict(reason_counts.most_common())
    summary_by_flag   = dict(flag_counts.most_common())
    summary_by_combo  = dict(combo_counts.most_common())

    output = {
        "totals": {
            "tgw_candidates": len(tgw_candidates),
            "clean_creates":  plan_result.summary["create"],
            "conflicts":      plan_result.summary["conflict"],
        },
        "conflict_breakdown": {
            "by_primary_reason":     summary_by_reason,
            "by_secondary_flag":     summary_by_flag,
            "by_endpoint_class_pair": summary_by_combo,
            "cidr_distribution": {
                "src_is_cidr":  src_cidr,
                "tgt_is_cidr":  tgt_cidr,
                "both_cidr":    both_cidr,
            },
        },
        "auto_resolution": {
            "auto_resolvable_count":    len(auto_res),
            "requires_investigation":   len(needs_inv),
            "auto_resolvable_criteria": (
                "primary_reason in (cidr_subnet_rule, complex_port_expression, requires_manual_review) "
                "AND neither endpoint is unknown"
            ),
        },
        "auto_resolvable_candidates": auto_res,
        "requires_investigation":     needs_inv,
        "all_conflicts":              conflicts,
    }

    out_path = _REPO_ROOT / "outputs" / "debug_scp_firewall_conflicts.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _find_sample()
    main(path)
