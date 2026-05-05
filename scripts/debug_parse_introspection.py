"""Debug script: parse summary and coverage report for an S2D workbook.

Shows per-sheet parse status (parsed / skipped), warning count per sheet,
structure type, output domain, and drift method — all derived from the
SHEET_REGISTRY without modifying any parser logic.

Also reports coverage: which workbook sheets are registered, which are
unsupported (in workbook but not in registry), and which are missing
(registered but absent from workbook).

Writes:
  outputs/debug_parse_summary.json
  outputs/debug_parse_coverage.json

Usage (from repo root):
    python scripts/debug_parse_introspection.py [path/to/workbook.xlsx]
"""

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.parser import parse_s2d_with_summary


def _find_sample() -> Path:
    samples = sorted((_REPO_ROOT / "samples").glob("*.xlsx"))
    if not samples:
        raise FileNotFoundError("No .xlsx file found in samples/.")
    return samples[0]


def main(workbook_path: Path) -> None:
    print("=" * 70)
    print("S2D Parse Introspection")
    print("=" * 70)
    print(f"\nWorkbook: {workbook_path.name}")

    state, summary, coverage = parse_s2d_with_summary(str(workbook_path))

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n[Parse Summary]  ({summary.parsed_count}/{len(summary.sheets)} sheets parsed)")
    print(f"  total_warnings: {summary.total_warnings}")
    print()

    name_w = max(len(r.sheet_name) for r in summary.sheets) + 2
    for r in summary.sheets:
        status = "parsed " if r.parsed else "SKIPPED"
        warn   = f"  warnings={r.warning_count}" if r.warning_count else ""
        print(f"  {r.sheet_name:{name_w}} {status}  "
              f"type={r.structure_type}  "
              f"domain={r.output_domain}  "
              f"drift={r.drift_method}"
              f"{warn}")

    # ── Coverage ──────────────────────────────────────────────────────────────
    print(f"\n[Coverage]")
    print(f"  workbook sheets:    {coverage.workbook_sheet_count}  {coverage.workbook_sheets}")
    print(f"  registered sheets:  {coverage.registered_sheet_count}  {coverage.registered_sheets}")
    print(f"  parsed sheets:      {coverage.parsed_sheet_count}  {coverage.parsed_sheets}")
    if coverage.unsupported_sheets:
        print(f"  unsupported (in workbook, not registered): {coverage.unsupported_sheets}")
    else:
        print(f"  unsupported:        0")

    missing = [s for s in coverage.registered_sheets if s not in coverage.parsed_sheets]
    if missing:
        print(f"  missing (registered but absent in workbook): {missing}")

    # ── Write outputs ─────────────────────────────────────────────────────────
    out_dir = _REPO_ROOT / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_path = out_dir / "debug_parse_summary.json"
    summary_path.write_text(
        json.dumps(
            {"workbook": workbook_path.name, **summary.to_dict()},
            ensure_ascii=False, indent=2, default=str,
        )
    )

    coverage_path = out_dir / "debug_parse_coverage.json"
    coverage_path.write_text(
        json.dumps(
            {"workbook": workbook_path.name, **coverage.to_dict()},
            ensure_ascii=False, indent=2, default=str,
        )
    )

    print(f"\nWritten: {summary_path}")
    print(f"Written: {coverage_path}")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _find_sample()
    main(path)
