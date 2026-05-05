"""Debug script: run VMware planner in dry-run mode against sample workbook.

Usage (from repo root):
    python scripts/debug_vmware_plan.py [path/to/workbook.xlsx]

Actual state is mocked: VMs whose vhost starts with 'vh' and landscape == PRD
are treated as already existing with matching compute specs, to exercise the
skip/update paths alongside the create path.

Output is written to outputs/debug_vmware_plan.json.
"""
import json
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.parser import parse_s2d
from src.planner.vmware_planner import plan_vmware


def _find_sample() -> Path:
    samples = sorted((_REPO_ROOT / "samples").glob("*.xlsx"))
    if not samples:
        raise FileNotFoundError("No .xlsx file found in samples/.")
    return samples[0]


def _mock_actual_state(vms: list[dict]) -> list[dict]:
    """Build a mock actual state for demonstration.

    - PRD landscape VMs: treated as existing with matching specs → skip
    - DR landscape VMs: treated as existing but with half the memory → update
    - QAS/DEV VMs: not in actual state → create
    """
    actual = []
    for vm in vms:
        landscape = vm["identity"]["landscape"]
        vhost     = vm["identity"]["vhost"]
        cpu       = vm["compute"]["cpu_vcores"]
        mem       = vm["compute"]["memory_gb"]

        if landscape == "PRD":
            actual.append({"vhost": vhost, "cpu_vcores": cpu, "memory_gb": mem})
        elif landscape == "DR":
            actual.append({"vhost": vhost, "cpu_vcores": cpu, "memory_gb": (mem or 0) // 2})
    return actual


def _summary(result) -> None:
    s = result.summary
    print(f"  create:   {s['create']}")
    print(f"  update:   {s['update']}")
    print(f"  skip:     {s['skip']}")
    print(f"  conflict: {s['conflict']}")

    if result.conflicts:
        print(f"\n  Conflict details:")
        for c in result.conflicts[:5]:
            print(f"    [{c['resource_id']}] {c['reason']}")
        if len(result.conflicts) > 5:
            print(f"    ... and {len(result.conflicts) - 5} more")


def main(workbook_path: Path) -> None:
    print(f"Opening: {workbook_path}")
    state = parse_s2d(str(workbook_path))
    vms   = state["vmware_vm"]
    print(f"Desired VMs: {len(vms)}")

    actual = _mock_actual_state(vms)
    print(f"Mock actual state: {len(actual)} VMs (PRD=skip, DR=update, QAS/DEV=create)")

    result = plan_vmware(vms, actual)

    output = {
        "actions":   result.actions,
        "conflicts": result.conflicts,
        "summary":   result.summary,
        "issues":    [i.to_dict() for i in result.issues],
    }

    out_path = _REPO_ROOT / "outputs" / "debug_vmware_plan.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))

    print(f"Written:  {out_path}")
    _summary(result)


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _find_sample()
    main(path)
