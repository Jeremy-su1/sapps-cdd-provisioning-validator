"""Debug script: compare realized SCP Firewall rules vs actual SCP API state (real path).

Full closed-loop pipeline:
  1. parse_s2d()                   → desired_state (from S2D workbook)
  2. classify_candidates()          → enriched TGW candidates
  3. realize_rules()                → flat realized rules (direct_create + split_create)
  4. ScpFirewallCollector.collect() → actual rules via real SCP API
       Phase 1: GET /v1/firewalls?product_type=TGW_*
       Phase 2: GET /v1/firewalls/rules?firewall_id={id}&fetch_all=true
  5. validate_realized_vs_actual()  → matched / missing / unexpected
     Content key: (source_ip, target_ip, protocol, port)

Writes: outputs/debug_scp_firewall_validate_realized_real.json

Usage (from repo root):
    python scripts/debug_scp_firewall_validate_realized_real.py         # dry_run

    SCP_ENDPOINT=https://firewall.kr-west1.e.samsungsdscloud.com \\
    SCP_ACCESS_KEY=mykey \\
    SCP_SECRET_KEY=mysecret \\
    python scripts/debug_scp_firewall_validate_realized_real.py [path/to/workbook.xlsx]
"""
import json
import os
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
    print("=" * 70)
    print("SCP Firewall: Realized Rules vs Actual State")
    print("=" * 70)

    # ── Step 1-3: Parse → Classify → Realize ─────────────────────────────────
    print(f"\n[1] Opening workbook: {workbook_path.name}")
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
    rs = realization.summary

    print(f"\n[2] Realization summary")
    print(f"    total_candidates:    {rs['total_candidates']}")
    print(f"    total_realized_rules:{rs['total_realized_rules']}")
    print(f"    direct_create:       {rs['direct_create_rules']}")
    print(f"    split_create groups: {rs['split_create_groups']}  rules: {rs['split_create_rules']}")
    print(f"    reference_only:      {rs['reference_only']}")
    print(f"    unsupported:         {rs['unsupported']}")

    # ── Step 4: Collect actual state ─────────────────────────────────────────
    endpoint   = os.environ.get("SCP_ENDPOINT", "")
    access_key = os.environ.get("SCP_ACCESS_KEY", "")
    secret_key = os.environ.get("SCP_SECRET_KEY", "")
    dry_run    = not (endpoint and access_key and secret_key)

    print(f"\n[3] Collecting actual SCP Firewall state")
    if dry_run:
        print(f"    Mode: dry_run=True  (set SCP_ENDPOINT, SCP_ACCESS_KEY, SCP_SECRET_KEY for live)")
    else:
        print(f"    Mode: live API  endpoint={endpoint!r}")

    collector = ScpFirewallCollector(
        endpoint=endpoint or None,
        access_key=access_key or None,
        secret_key=secret_key or None,
        dry_run=dry_run,
    )

    error_msg = None
    try:
        actual_rules = collector.collect()
    except CollectorError as exc:
        print(f"    [CollectorError] {exc}")
        actual_rules = []
        error_msg = str(exc)

    print(f"    actual_rules collected: {len(actual_rules)}")

    if actual_rules:
        proto_dist = Counter(r.get("protocol") for r in actual_rules)
        action_dist = Counter(r.get("action") for r in actual_rules)
        print(f"    protocols: {dict(proto_dist.most_common())}")
        print(f"    actions:   {dict(action_dist.most_common())}")

    # ── Step 5: Validate ──────────────────────────────────────────────────────
    validation = validate_realized_vs_actual(flat_realized, actual_rules)
    s = validation.summary

    print(f"\n[4] Validation summary  (content key: source_ip, target_ip, protocol, port)")
    print(f"    realized_rules: {s['realized_rules']}")
    print(f"    actual_rules:   {s['actual_rules']}")
    print(f"    matched:        {s['matched']}")
    print(f"    missing:        {s['missing']}  (realized but not found in actual)")
    print(f"    unexpected:     {s['unexpected']}  (actual but not in realized)")

    if s["matched"] > 0:
        match_rate = 100 * s["matched"] / s["realized_rules"]
        print(f"    match_rate:     {match_rate:.1f}%")

    if validation.matched:
        print(f"\n    Matched examples (up to 3):")
        for m in validation.matched[:3]:
            r = m["realized"]
            print(f"      {m['realized_rule_id']:20}  "
                  f"src={r.get('source_ip'):20}  dst={r.get('target_ip'):20}  "
                  f"{r.get('protocol'):6}  port={r.get('port')}")

    if validation.missing:
        print(f"\n    Missing examples (up to 3) — realized but absent in actual:")
        for m in validation.missing[:3]:
            r = m["realized"]
            print(f"      {m['realized_rule_id']:20}  "
                  f"src={r.get('source_ip'):20}  dst={r.get('target_ip'):20}  "
                  f"{r.get('protocol'):6}  port={r.get('port')}")

    if validation.unexpected:
        print(f"\n    Unexpected examples (up to 3) — in actual but not realized:")
        for u in validation.unexpected[:3]:
            a = u["actual"]
            print(f"      {u['resource_id']:30}  "
                  f"src={a.get('source_ip'):20}  dst={a.get('target_ip'):20}  "
                  f"{a.get('protocol'):6}  port={a.get('port')}")

    # ── Write output ──────────────────────────────────────────────────────────
    output = {
        "dry_run":             dry_run,
        "endpoint":            endpoint or None,
        "error":               error_msg,
        "workbook":            workbook_path.name,
        "realization_summary": rs,
        "validation_summary":  s,
        "matched": [
            {
                "realized_rule_id":   m["realized_rule_id"],
                "source_ip":          m["realized"].get("source_ip"),
                "target_ip":          m["realized"].get("target_ip"),
                "protocol":           m["realized"].get("protocol"),
                "port":               m["realized"].get("port"),
                "actual_resource_id": m["actual"].get("resource_id"),
            }
            for m in validation.matched[:10]
        ],
        "missing": [
            {
                "realized_rule_id": r["realized_rule_id"],
                "source_ip":        r["realized"].get("source_ip"),
                "target_ip":        r["realized"].get("target_ip"),
                "protocol":         r["realized"].get("protocol"),
                "port":             r["realized"].get("port"),
                "src_endpoint_class": r["realized"].get("src_endpoint_class"),
                "tgt_endpoint_class": r["realized"].get("tgt_endpoint_class"),
            }
            for r in validation.missing[:10]
        ],
        "unexpected": [
            {
                "resource_id": r["resource_id"],
                "source_ip":   r["actual"].get("source_ip"),
                "target_ip":   r["actual"].get("target_ip"),
                "protocol":    r["actual"].get("protocol"),
                "port":        r["actual"].get("port"),
                "firewall_id": r["actual"].get("firewall_id"),
            }
            for r in validation.unexpected[:10]
        ],
    }

    out_path = _REPO_ROOT / "outputs" / "debug_scp_firewall_validate_realized_real.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _find_sample()
    main(path)
