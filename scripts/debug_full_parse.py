"""Debug script: run parse_s2d() on the sample workbook and write full output.

Usage (from repo root):
    python scripts/debug_full_parse.py [path/to/workbook.xlsx]

Defaults to the first .xlsx found in samples/ if no path is given.
Output is written to outputs/debug_full_parse.json (pretty-printed).
"""
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.parser import parse_s2d


def _find_sample() -> Path:
    samples = sorted((_REPO_ROOT / "samples").glob("*.xlsx"))
    if not samples:
        raise FileNotFoundError(
            "No .xlsx file found in samples/. "
            "Place the S2D workbook there and retry."
        )
    return samples[0]


def _summary(result: dict) -> None:
    vms      = result["vmware_vm"]
    fs       = result["filesystem"]
    fw       = result["firewall_rule_candidates"]
    subnets  = result["network"]["subnets"]
    routes   = result["network"]["routing_table"]
    warnings = result["parser_warnings"]
    ignored  = result["ignored_labels"]

    print(f"  VMs (vmware_vm):             {len(vms)}")
    print(f"  Filesystem entries:          {len(fs)}")
    print(f"  Firewall rule candidates:    {len(fw)}")
    print(f"  Subnets:                     {len(subnets)}")
    print(f"  Routing table entries:       {len(routes)}")
    print(f"  Parser warnings:             {len(warnings)}")
    print(f"  Ignored labels:              {len(ignored)}")

    customer_name = result["project_metadata"].get("customer_name")
    if customer_name:
        print(f"  Customer:                    {customer_name}")


def main(workbook_path: Path) -> None:
    print(f"Opening: {workbook_path}")
    result = parse_s2d(str(workbook_path))

    out_path = _REPO_ROOT / "outputs" / "debug_full_parse.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    print(f"Written:  {out_path}")
    _summary(result)

    if result["parser_warnings"]:
        print(f"\n  Parser warnings:")
        for w in result["parser_warnings"]:
            print(f"    {w}")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _find_sample()
    main(path)
