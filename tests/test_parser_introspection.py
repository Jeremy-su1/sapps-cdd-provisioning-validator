"""Tests for src/parser/introspection.py — parse summary and coverage."""

import pytest
from src.parser.introspection import (
    SheetParseRecord,
    ParseSummary,
    ParseCoverage,
    run_parse_with_introspection,
)
from src.parser.registry import SHEET_REGISTRY, StructureType


# ---------------------------------------------------------------------------
# Minimal fake workbook (needs _sheets so _get_sheet_names() can resolve names)
# ---------------------------------------------------------------------------

class _FakeWs:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def iter_rows(self, values_only=True):
        return iter(self._rows)


class _FakeWb:
    def __init__(self, sheets: dict):
        self._sheets = sheets

    def __getitem__(self, name):
        return self._sheets[name]


def _empty_wb():
    """Minimal workbook with all 5 registered sheets present and empty."""
    return _FakeWb({
        "Accinfo":       _FakeWs(),
        "NWInfo":        _FakeWs(),
        "ServerInfo":    _FakeWs([
            tuple([None] * 43),
            ("Phase", "vhost", "phost", "Landscape", "SID", "Type",
             "Main Solution", *([None] * 36)),
            tuple([None] * 43),
        ]),
        "FileSystem":    _FakeWs([
            tuple([None] * 19),
            tuple(["Header"] + [None] * 18),
        ]),
        "SecurityGroup": _FakeWs([
            tuple([None] * 17),
            tuple([None] * 17),
            tuple(["Source"] + [None] * 16),
        ]),
    })


def _wb_with_extra(extra_name="OSUserInfo"):
    """All 5 registered sheets + one extra unregistered sheet."""
    sheets = dict(_empty_wb()._sheets)
    sheets[extra_name] = _FakeWs()
    return _FakeWb(sheets)


def _wb_missing(sheet_name):
    """All registered sheets except the named one."""
    sheets = dict(_empty_wb()._sheets)
    del sheets[sheet_name]
    return _FakeWb(sheets)


# ---------------------------------------------------------------------------
# TestSheetParseRecord
# ---------------------------------------------------------------------------

class TestSheetParseRecord:
    def test_has_sheet_name(self):
        r = SheetParseRecord(
            sheet_name="Accinfo",
            required=True,
            structure_type="key_value_vertical",
            drift_method="scp_vpc_subnet_api",
            output_domain="project_metadata, global_network_context",
            parsed=True,
            warning_count=0,
        )
        assert r.sheet_name == "Accinfo"

    def test_parsed_false(self):
        r = SheetParseRecord(
            sheet_name="Missing",
            required=True,
            structure_type="simple_table",
            drift_method="os_df_output",
            output_domain="filesystem",
            parsed=False,
            warning_count=1,
        )
        assert r.parsed is False
        assert r.warning_count == 1

    def test_to_dict_has_all_fields(self):
        r = SheetParseRecord(
            sheet_name="NWInfo",
            required=True,
            structure_type="semi_structured",
            drift_method="scp_subnet_cidr",
            output_domain="network",
            parsed=True,
            warning_count=0,
        )
        d = r.to_dict()
        assert d["sheet_name"] == "NWInfo"
        assert d["required"] is True
        assert d["structure_type"] == "semi_structured"
        assert d["drift_method"] == "scp_subnet_cidr"
        assert d["output_domain"] == "network"
        assert d["parsed"] is True
        assert d["warning_count"] == 0


# ---------------------------------------------------------------------------
# TestParseSummary
# ---------------------------------------------------------------------------

class TestParseSummary:
    def _make_record(self, name="Sheet", parsed=True, warnings=0):
        return SheetParseRecord(
            sheet_name=name,
            required=True,
            structure_type="simple_table",
            drift_method="some_api",
            output_domain="some_key",
            parsed=parsed,
            warning_count=warnings,
        )

    def test_has_sheets_and_total_warnings(self):
        s = ParseSummary(sheets=[self._make_record()], total_warnings=0)
        assert len(s.sheets) == 1
        assert s.total_warnings == 0

    def test_to_dict_contains_sheets(self):
        s = ParseSummary(sheets=[self._make_record("A"), self._make_record("B")], total_warnings=0)
        d = s.to_dict()
        assert len(d["sheets"]) == 2
        assert d["sheets"][0]["sheet_name"] == "A"

    def test_to_dict_contains_total_warnings(self):
        s = ParseSummary(sheets=[self._make_record(warnings=2)], total_warnings=2)
        d = s.to_dict()
        assert d["total_warnings"] == 2

    def test_parsed_count(self):
        records = [
            self._make_record("A", parsed=True),
            self._make_record("B", parsed=False),
            self._make_record("C", parsed=True),
        ]
        s = ParseSummary(sheets=records, total_warnings=0)
        d = s.to_dict()
        assert d["parsed_count"] == 2
        assert d["skipped_count"] == 1


# ---------------------------------------------------------------------------
# TestParseCoverage
# ---------------------------------------------------------------------------

class TestParseCoverage:
    def _make(self, wb=None, registered=None, parsed=None, unsupported=None):
        return ParseCoverage(
            workbook_sheets   = wb          or ["Accinfo", "NWInfo", "Extra"],
            registered_sheets = registered  or ["Accinfo", "NWInfo"],
            parsed_sheets     = parsed      or ["Accinfo", "NWInfo"],
            unsupported_sheets= unsupported or ["Extra"],
        )

    def test_has_four_lists(self):
        c = self._make()
        assert isinstance(c.workbook_sheets,    list)
        assert isinstance(c.registered_sheets,  list)
        assert isinstance(c.parsed_sheets,      list)
        assert isinstance(c.unsupported_sheets, list)

    def test_to_dict_has_all_keys(self):
        c = self._make()
        d = c.to_dict()
        assert "workbook_sheets" in d
        assert "registered_sheets" in d
        assert "parsed_sheets" in d
        assert "unsupported_sheets" in d

    def test_to_dict_counts(self):
        c = self._make(
            wb=["A", "B", "C"],
            registered=["A", "B"],
            parsed=["A"],
            unsupported=["C"],
        )
        d = c.to_dict()
        assert d["workbook_sheet_count"]    == 3
        assert d["registered_sheet_count"]  == 2
        assert d["parsed_sheet_count"]      == 1
        assert d["unsupported_sheet_count"] == 1

    def test_unsupported_sheets_not_in_registered(self):
        c = self._make()
        for s in c.unsupported_sheets:
            assert s not in c.registered_sheets


# ---------------------------------------------------------------------------
# TestRunParseWithIntrospection
# ---------------------------------------------------------------------------

class TestRunParseWithIntrospection:
    def test_returns_three_tuple(self):
        result = run_parse_with_introspection(_empty_wb())
        assert len(result) == 3

    def test_first_element_is_state_dict(self):
        state, _, _ = run_parse_with_introspection(_empty_wb())
        assert "project_metadata" in state
        assert "firewall_rule_candidates" in state

    def test_second_element_is_parse_summary(self):
        _, summary, _ = run_parse_with_introspection(_empty_wb())
        assert isinstance(summary, ParseSummary)

    def test_third_element_is_parse_coverage(self):
        _, _, coverage = run_parse_with_introspection(_empty_wb())
        assert isinstance(coverage, ParseCoverage)

    def test_all_sheets_present_all_parsed(self):
        _, summary, _ = run_parse_with_introspection(_empty_wb())
        assert all(r.parsed for r in summary.sheets)

    def test_summary_has_one_record_per_registry_entry(self):
        _, summary, _ = run_parse_with_introspection(_empty_wb())
        assert len(summary.sheets) == len(SHEET_REGISTRY)

    def test_missing_required_sheet_record_is_not_parsed(self):
        _, summary, _ = run_parse_with_introspection(_wb_missing("FileSystem"))
        fs_record = next(r for r in summary.sheets if r.sheet_name == "FileSystem")
        assert fs_record.parsed is False

    def test_missing_required_sheet_adds_warning(self):
        state, summary, _ = run_parse_with_introspection(_wb_missing("FileSystem"))
        fs_record = next(r for r in summary.sheets if r.sheet_name == "FileSystem")
        assert fs_record.warning_count >= 1

    def test_missing_required_sheet_adds_to_state_warnings(self):
        state, _, _ = run_parse_with_introspection(_wb_missing("FileSystem"))
        assert any("FileSystem" in w for w in state["parser_warnings"])

    def test_extra_sheet_appears_in_coverage_unsupported(self):
        _, _, coverage = run_parse_with_introspection(_wb_with_extra("OSUserInfo"))
        assert "OSUserInfo" in coverage.unsupported_sheets

    def test_extra_sheet_not_in_registered_sheets(self):
        _, _, coverage = run_parse_with_introspection(_wb_with_extra("OSUserInfo"))
        assert "OSUserInfo" not in coverage.registered_sheets

    def test_coverage_workbook_sheets_includes_all(self):
        _, _, coverage = run_parse_with_introspection(_wb_with_extra("OSUserInfo"))
        assert "OSUserInfo" in coverage.workbook_sheets
        assert "Accinfo" in coverage.workbook_sheets

    def test_coverage_registered_matches_registry(self):
        _, _, coverage = run_parse_with_introspection(_empty_wb())
        assert set(coverage.registered_sheets) == {c.sheet_name for c in SHEET_REGISTRY}

    def test_record_structure_type_matches_registry(self):
        _, summary, _ = run_parse_with_introspection(_empty_wb())
        acc = next(r for r in summary.sheets if r.sheet_name == "Accinfo")
        assert acc.structure_type == StructureType.KEY_VALUE_VERTICAL.value

    def test_record_drift_method_matches_registry(self):
        _, summary, _ = run_parse_with_introspection(_empty_wb())
        nw = next(r for r in summary.sheets if r.sheet_name == "NWInfo")
        assert nw.drift_method == "scp_subnet_cidr"

    def test_record_output_domain_is_nonempty(self):
        _, summary, _ = run_parse_with_introspection(_empty_wb())
        for r in summary.sheets:
            assert r.output_domain, f"{r.sheet_name} has no output_domain"

    def test_warning_count_zero_when_no_warnings(self):
        _, summary, _ = run_parse_with_introspection(_empty_wb())
        for r in summary.sheets:
            assert r.warning_count == 0, f"{r.sheet_name} has unexpected warnings"

    def test_total_warnings_matches_state(self):
        state, summary, _ = run_parse_with_introspection(_wb_missing("FileSystem"))
        assert summary.total_warnings == len(state["parser_warnings"])
