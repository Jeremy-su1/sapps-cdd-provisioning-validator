"""Debug script: collect actual SCP Firewall rule state.

Runs in dry_run mode by default (no real API calls).
Set SCP_ENDPOINT, SCP_ACCESS_KEY, SCP_SECRET_KEY environment variables for real collection.

API: GET /v1/firewalls  →  GET /v1/firewalls/rules?firewall_id={id}&fetch_all=true
     Base URL: https://firewall.{region}.{env}.samsungsdscloud.com

Pipeline:
  1. ScpFirewallCollector(dry_run=True)  → actual_rules (empty in dry_run)
  2. Normalize each raw rule via normalize_rule()
  3. Write outputs/debug_scp_firewall_actual.json

Usage (from repo root):
    python scripts/debug_scp_firewall_actual.py

    SCP_ENDPOINT=https://firewall.kr-west1.e.samsungsdscloud.com \\
    SCP_ACCESS_KEY=mykey SCP_SECRET_KEY=mysecret \\
    python scripts/debug_scp_firewall_actual.py
"""
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.collector.scp_firewall_collector import ScpFirewallCollector, CollectorError
from src.config import load_env_file


def main() -> None:
    load_env_file(_REPO_ROOT / ".env")
    endpoint   = os.environ.get("SCP_ENDPOINT", "")
    access_key = os.environ.get("SCP_ACCESS_KEY", "")
    secret_key = os.environ.get("SCP_SECRET_KEY", "")
    dry_run    = not (endpoint and access_key and secret_key)

    if dry_run:
        print("dry_run=True  (set SCP_ENDPOINT, SCP_ACCESS_KEY, SCP_SECRET_KEY to run live)")
    else:
        print(f"dry_run=False  endpoint={endpoint!r}")

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

    print(f"\nActual rules collected: {len(actual_rules)}")
    if actual_rules:
        sample = actual_rules[0]
        print(f"  Sample rule: id={sample.get('resource_id')}  "
              f"src={sample.get('source_ip')}  dst={sample.get('target_ip')}  "
              f"protocol={sample.get('protocol')}  port={sample.get('port')}  "
              f"action={sample.get('action')}")

    output = {
        "dry_run":      dry_run,
        "actual_count": len(actual_rules),
        "actual_rules": actual_rules,
    }

    out_path = _REPO_ROOT / "outputs" / "debug_scp_firewall_actual.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    print(f"Written: {out_path}")


if __name__ == "__main__":
    main()
