"""Debug script: classify firewall rule candidates from the sample workbook.

Usage (from repo root):
    python scripts/debug_firewall_classification.py [path/to/workbook.xlsx]

Output is written to outputs/debug_firewall_classification.json.
"""
import json
import sys
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


def _find_sample() -> Path:
    samples = sorted((_REPO_ROOT / "samples").glob("*.xlsx"))
    if not samples:
        raise FileNotFoundError("No .xlsx file found in samples/.")
    return samples[0]


def _summary(result) -> None:
    tgw = result.tgw_candidates
    dfw = result.dfw_candidates
    ref = result.reference_only

    review_count = sum(1 for r in tgw if r.get("requires_manual_review"))
    psm_count    = sum(1 for r in ref if r.get("reason") == "psm_managed")
    unclear      = sum(1 for r in ref if r.get("reason") == "unclassifiable")

    print(f"  TGW firewall candidates:      {len(tgw)}")
    print(f"    — requires manual review:   {review_count}")
    print(f"  NSX-T DFW candidates:         {len(dfw)}")
    print(f"  Reference-only rules:         {len(ref)}")
    print(f"    — PSM managed:              {psm_count}")
    print(f"    — Unclassifiable:           {unclear}")
    if result.warnings:
        print(f"  Classification warnings:      {len(result.warnings)}")


def main(workbook_path: Path) -> None:
    print(f"Opening: {workbook_path}")
    state = parse_s2d(str(workbook_path))

    vm_hostnames    = build_vm_hostnames(state["vmware_vm"])
    subnet_networks = build_subnet_networks(state["network"]["subnets"])
    print(f"VM hostname index: {len(vm_hostnames)} entries")
    print(f"Subnet network index: {len(subnet_networks)} networks")

    result = classify_candidates(
        state["firewall_rule_candidates"],
        vm_hostnames,
        subnet_networks,
    )

    output = {
        "tgw_candidates":   result.tgw_candidates,
        "dfw_candidates":   result.dfw_candidates,
        "reference_only":   result.reference_only,
        "warnings":         result.warnings,
    }

    out_path = _REPO_ROOT / "outputs" / "debug_firewall_classification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))

    print(f"Written:  {out_path}")
    _summary(result)


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _find_sample()
    main(path)
