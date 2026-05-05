"""S2D Excel parser — entry point that orchestrates all sub-parsers."""

import openpyxl

from src.parser.registry import SHEET_REGISTRY


def _empty_state() -> dict:
    return {
        "project_metadata":         {},
        "global_network_context":   {},
        "network":                  {"subnets": [], "routing_table": []},
        "vmware_vm":                [],
        "filesystem":               [],
        "firewall_rule_candidates": [],
        "parser_warnings":          [],
        "ignored_labels":           [],
    }


def _parse_wb(wb) -> dict:
    """Orchestrate all sub-parsers against an open workbook object.

    Separated from parse_s2d() so tests can inject fake workbook objects
    without touching the filesystem. Sheet dispatch is driven by SHEET_REGISTRY
    in src/parser/registry.py — add new sheets there, not here.
    """
    state = _empty_state()
    for cfg in SHEET_REGISTRY:
        try:
            ws = wb[cfg.sheet_name]
        except KeyError:
            if cfg.required:
                state["parser_warnings"].append(
                    f"Missing required sheet: {cfg.sheet_name!r}"
                )
            continue
        result = cfg.parse_fn(ws)
        cfg.merge_fn(result, state)
    return state


def parse_s2d(workbook_path: str) -> dict:
    """Parse an S2D Excel workbook and return the normalized desired-state dict."""
    wb = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    return _parse_wb(wb)


def parse_s2d_with_summary(workbook_path: str) -> tuple:
    """Parse an S2D workbook and return (desired_state, ParseSummary, ParseCoverage).

    Use this instead of parse_s2d() when you need per-sheet audit data.
    """
    from src.parser.introspection import run_parse_with_introspection
    wb = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    return run_parse_with_introspection(wb)
