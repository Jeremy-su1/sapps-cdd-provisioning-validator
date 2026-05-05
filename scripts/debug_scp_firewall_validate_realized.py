"""Debug script: compare realized SCP Firewall rules vs actual collected state.

Pipeline:
  1. parse_s2d()              → desired_state
  2. classify_candidates()    → tgw_candidates (enriched)
  3. realize_rules()          → flat realized rules
  4. ScpFirewallCollector      → actual_rules (dry_run=True → empty)
  5. validate_realized_vs_actual() → matched / missing / unexpected
  6. Write outputs/debug_scp_firewall_validate_realized.json

Usage (from repo root):
    python scripts/debug_scp_firewall_validate_realized.py [path/to/workbook.xlsx]

    SCP_ENDPOINT=https://firewall.kr-west1.e.samsungsdscloud.com \\
    SCP_ACCESS_KEY=mykey SCP_SECRET_KEY=mysecret \\
    python scripts/debug_scp_firewall_validate_realized.py
"""
import json
import os
import sys
import ipaddress
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.parser import parse_s2d
from src.classification.firewall_rules import (
    classify_candidates,
    build_vm_hostnames,
    build_subnet_networks,
)
from src.transforms.scp_firewall_realizer import realize_rules
from src.collector.scp_firewall_collector import ScpFirewallCollector, CollectorError
from src.validator.scp_firewall_validator import validate_realized_vs_actual


def _find_sample() -> Path:
    samples = sorted((_REPO_ROOT / "samples").glob("*.xlsx"))
    if not samples:
        raise FileNotFoundError("No .xlsx file found in samples/.")
    return samples[0]


def _build_platform_networks(subnets: list[dict]) -> list:
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


def main(workbook_path: Path) -> None:
    print(f"Opening: {workbook_path}")
    state = parse_s2d(str(workbook_path))

    vm_hostnames      = build_vm_hostnames(state["vmware_vm"])
    subnet_networks   = build_subnet_networks(state["network"]["subnets"])
    platform_networks = _build_platform_networks(state["network"]["subnets"])

    classification = classify_candidates(
        state["firewall_rule_candidates"],
        vm_hostnames,
        subnet_networks,
        platform_networks=platform_networks,
    )

    realization   = realize_rules(classification.tgw_candidates)
    flat_realized = realization.flat_rules

    # ── Collect actual state ──────────────────────────────────────────────────
    endpoint   = os.environ.get("SCP_ENDPOINT", "")
    access_key = os.environ.get("SCP_ACCESS_KEY", "")
    secret_key = os.environ.get("SCP_SECRET_KEY", "")
    dry_run    = not (endpoint and access_key and secret_key)

    collector = ScpFirewallCollector(
        endpoint=endpoint or None,
        access_key=access_key or None,
        secret_key=secret_key or None,
        dry_run=dry_run,
    )

    try:
        actual_rules = collector.collect()
    except CollectorError as exc:
        print(f"[CollectorError] {exc}")
        actual_rules = []

    # ── Validate ──────────────────────────────────────────────────────────────
    validation = validate_realized_vs_actual(flat_realized, actual_rules)
    s = validation.summary

    print(f"\n[Realized vs Actual Summary]")
    print(f"  realized_rules: {s['realized_rules']}")
    print(f"  actual_rules:   {s['actual_rules']}  (dry_run={dry_run})")
    print(f"  matched:        {s['matched']}")
    print(f"  missing:        {s['missing']}")
    print(f"  unexpected:     {s['unexpected']}")

    # ── Write output ──────────────────────────────────────────────────────────
    output = {
        "dry_run":            dry_run,
        "realization_summary": realization.summary,
        "validation_summary":  s,
        "matched": [
            {
                "realized_rule_id": m["realized_rule_id"],
                "source_ip":        m["realized"].get("source_ip"),
                "target_ip":        m["realized"].get("target_ip"),
                "protocol":         m["realized"].get("protocol"),
                "port":             m["realized"].get("port"),
                "actual_resource_id": m["actual"].get("resource_id"),
            }
            for m in validation.matched[:5]
        ],
        "missing": [
            {
                "realized_rule_id": r["realized_rule_id"],
                "source_ip":        r["realized"].get("source_ip"),
                "target_ip":        r["realized"].get("target_ip"),
                "protocol":         r["realized"].get("protocol"),
                "port":             r["realized"].get("port"),
            }
            for r in validation.missing[:5]
        ],
        "unexpected": [
            {
                "resource_id": r["resource_id"],
                "source_ip":   r["actual"].get("source_ip"),
                "target_ip":   r["actual"].get("target_ip"),
                "protocol":    r["actual"].get("protocol"),
                "port":        r["actual"].get("port"),
            }
            for r in validation.unexpected[:5]
        ],
    }

    out_path = _REPO_ROOT / "outputs" / "debug_scp_firewall_validate_realized.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _find_sample()
    main(path)
