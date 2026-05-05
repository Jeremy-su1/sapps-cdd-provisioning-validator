"""S2D parse introspection — summary and coverage reporting.

Provides run_parse_with_introspection(wb) as an alternative to _parse_wb()
that returns per-sheet parse records alongside the desired-state dict:

    state, summary, coverage = run_parse_with_introspection(wb)

ParseSummary  — one SheetParseRecord per SHEET_REGISTRY entry.
ParseCoverage — compares workbook sheets vs registered vs parsed vs unsupported.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.parser.registry import SHEET_REGISTRY
from src.parser import _empty_state


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class SheetParseRecord:
    sheet_name:     str
    required:       bool
    structure_type: str     # StructureType.value string
    drift_method:   str
    output_domain:  str
    parsed:         bool
    warning_count:  int

    def to_dict(self) -> dict:
        return {
            "sheet_name":     self.sheet_name,
            "required":       self.required,
            "structure_type": self.structure_type,
            "drift_method":   self.drift_method,
            "output_domain":  self.output_domain,
            "parsed":         self.parsed,
            "warning_count":  self.warning_count,
        }


@dataclass
class ParseSummary:
    sheets:         list[SheetParseRecord]
    total_warnings: int

    @property
    def parsed_count(self) -> int:
        return sum(1 for r in self.sheets if r.parsed)

    @property
    def skipped_count(self) -> int:
        return len(self.sheets) - self.parsed_count

    def to_dict(self) -> dict:
        return {
            "total_warnings": self.total_warnings,
            "parsed_count":   self.parsed_count,
            "skipped_count":  self.skipped_count,
            "sheets":         [r.to_dict() for r in self.sheets],
        }


@dataclass
class ParseCoverage:
    workbook_sheets:    list[str]
    registered_sheets:  list[str]
    parsed_sheets:      list[str]
    unsupported_sheets: list[str]  # in workbook but not in registry

    @property
    def workbook_sheet_count(self) -> int:
        return len(self.workbook_sheets)

    @property
    def registered_sheet_count(self) -> int:
        return len(self.registered_sheets)

    @property
    def parsed_sheet_count(self) -> int:
        return len(self.parsed_sheets)

    @property
    def unsupported_sheet_count(self) -> int:
        return len(self.unsupported_sheets)

    def to_dict(self) -> dict:
        return {
            "workbook_sheet_count":    self.workbook_sheet_count,
            "registered_sheet_count":  self.registered_sheet_count,
            "parsed_sheet_count":      self.parsed_sheet_count,
            "unsupported_sheet_count": self.unsupported_sheet_count,
            "workbook_sheets":         self.workbook_sheets,
            "registered_sheets":       self.registered_sheets,
            "parsed_sheets":           self.parsed_sheets,
            "unsupported_sheets":      self.unsupported_sheets,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_sheet_names(wb) -> list[str]:
    """Return sheet names from an openpyxl Workbook or a FakeWb test double."""
    if hasattr(wb, "sheetnames"):       # openpyxl Workbook
        return list(wb.sheetnames)
    if hasattr(wb, "_sheets"):          # FakeWb used in tests
        return list(wb._sheets.keys())
    return []


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_parse_with_introspection(wb) -> tuple[dict, ParseSummary, ParseCoverage]:
    """Parse wb and return (desired_state, ParseSummary, ParseCoverage).

    Mirrors the _parse_wb() loop but tracks per-sheet parse status and
    warning counts so callers can build audit reports.
    """
    state = _empty_state()
    records: list[SheetParseRecord] = []
    parsed_sheet_names: list[str] = []

    for cfg in SHEET_REGISTRY:
        warnings_before = len(state["parser_warnings"])
        try:
            ws = wb[cfg.sheet_name]
            parsed = True
        except KeyError:
            parsed = False
            if cfg.required:
                state["parser_warnings"].append(
                    f"Missing required sheet: {cfg.sheet_name!r}"
                )

        if parsed:
            result = cfg.parse_fn(ws)
            cfg.merge_fn(result, state)
            parsed_sheet_names.append(cfg.sheet_name)

        records.append(SheetParseRecord(
            sheet_name     = cfg.sheet_name,
            required       = cfg.required,
            structure_type = cfg.structure_type.value,
            drift_method   = cfg.drift_method,
            output_domain  = cfg.output_domain,
            parsed         = parsed,
            warning_count  = len(state["parser_warnings"]) - warnings_before,
        ))

    wb_sheet_names  = _get_sheet_names(wb)
    registered_set  = {cfg.sheet_name for cfg in SHEET_REGISTRY}

    summary = ParseSummary(
        sheets         = records,
        total_warnings = len(state["parser_warnings"]),
    )
    coverage = ParseCoverage(
        workbook_sheets    = wb_sheet_names,
        registered_sheets  = [cfg.sheet_name for cfg in SHEET_REGISTRY],
        parsed_sheets      = parsed_sheet_names,
        unsupported_sheets = [s for s in wb_sheet_names if s not in registered_set],
    )
    return state, summary, coverage
