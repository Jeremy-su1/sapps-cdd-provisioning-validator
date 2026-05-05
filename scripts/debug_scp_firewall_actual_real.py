"""Debug script: collect actual SCP Firewall rule state (real API path).

Shows the full collection pipeline including:
- HMAC authentication headers built
- Phase 1: GET /v1/firewalls (TGW-type firewalls only)
- Phase 2: GET /v1/firewalls/rules?firewall_id={id}&fetch_all=true
- normalize_rule() applied to each raw rule

Writes: outputs/debug_scp_firewall_actual_real.json

Usage (from repo root):
    python scripts/debug_scp_firewall_actual_real.py                  # dry_run mode

    SCP_ENDPOINT=https://firewall.kr-west1.e.samsungsdscloud.com \\
    SCP_ACCESS_KEY=mykey \\
    SCP_SECRET_KEY=mysecret \\
    python scripts/debug_scp_firewall_actual_real.py
"""
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.collector.scp_firewall_collector import ScpFirewallCollector, CollectorError


def main() -> None:
    endpoint   = os.environ.get("SCP_ENDPOINT", "")
    access_key = os.environ.get("SCP_ACCESS_KEY", "")
    secret_key = os.environ.get("SCP_SECRET_KEY", "")
    dry_run    = not (endpoint and access_key and secret_key)

    print("=" * 60)
    print("SCP Firewall Actual State Collector")
    print("=" * 60)

    if dry_run:
        print("Mode:  dry_run=True  (no API calls — returns empty list)")
        print("       Set SCP_ENDPOINT, SCP_ACCESS_KEY, SCP_SECRET_KEY to run live")
    else:
        print(f"Mode:  live API")
        print(f"       Endpoint:    {endpoint}")
        print(f"       Access key:  {access_key[:6]}...")

    collector = ScpFirewallCollector(
        endpoint=endpoint or None,
        access_key=access_key or None,
        secret_key=secret_key or None,
        dry_run=dry_run,
    )

    # Show what headers would be built (even in dry-run, to verify signing)
    if access_key and secret_key:
        sample_headers = collector._build_auth_headers("GET", "/v1/firewalls")
        print(f"\n[Auth headers sample]")
        print(f"  Scp-Accesskey:   {sample_headers['Scp-Accesskey']}")
        print(f"  Scp-Timestamp:   {sample_headers['Scp-Timestamp']}")
        print(f"  Scp-Api-Version: {sample_headers['Scp-Api-Version']}")
        print(f"  Scp-Signature:   {sample_headers['Scp-Signature'][:20]}...")

    try:
        actual_rules = collector.collect()
        error_msg = None
    except CollectorError as exc:
        print(f"\n[CollectorError] {exc}")
        actual_rules = []
        error_msg = str(exc)

    print(f"\n[Collection Result]")
    print(f"  Actual rules collected: {len(actual_rules)}")

    # Protocol distribution
    if actual_rules:
        from collections import Counter
        protocols = Counter(r.get("protocol") for r in actual_rules)
        actions   = Counter(r.get("action") for r in actual_rules)
        print(f"  Protocols: {dict(protocols.most_common())}")
        print(f"  Actions:   {dict(actions.most_common())}")
        print(f"\n  Sample rules (up to 3):")
        for rule in actual_rules[:3]:
            print(f"    {rule.get('resource_id'):30}  "
                  f"src={rule.get('source_ip'):20}  "
                  f"dst={rule.get('target_ip'):20}  "
                  f"{rule.get('protocol'):6}  "
                  f"port={rule.get('port')}  "
                  f"action={rule.get('action')}")

    output = {
        "dry_run":      dry_run,
        "endpoint":     endpoint or None,
        "actual_count": len(actual_rules),
        "error":        error_msg,
        "actual_rules": actual_rules,
    }

    out_path = _REPO_ROOT / "outputs" / "debug_scp_firewall_actual_real.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
