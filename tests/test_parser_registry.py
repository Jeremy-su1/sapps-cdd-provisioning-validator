"""Tests for src/parser/registry.py — sheet registry structure and dispatch."""

import pytest
from src.parser.registry import SHEET_REGISTRY, SheetConfig, StructureType


# ---------------------------------------------------------------------------
# Minimal fake workbook infrastructure (local copy avoids cross-test deps)
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


def _make_wb(**overrides):
    """Minimal workbook with correct header structure for all 5 current sheets."""
    sheets = {
        "Accinfo":       _FakeWs(),
        "NWInfo":        _FakeWs(),
        "ServerInfo":    _FakeWs([
            tuple([None] * 43),
            ("Phase", "vhost", "phost", "Landscape", "SID", "Type",
             "Main Solution", "SID Cat I", "SID Cat II", "Type", "Role",
             "Host No", "VM/BM", "CDD", "SCP Image", "OS Version",
             *([None] * 27)),
            tuple([None] * 43),
        ]),
        "FileSystem":    _FakeWs([
            tuple([None] * 19),
            ("No.", "Landscape", "SID", "Server Type", "FS Cat1",
             "FS Cat2", "SLA Tier", "HA", "FS Count", "FS Seq",
             "Hostname", "Admin IP", "Mount Point", "Size (GB)", "FS Type",
             "VG Name", "NFS Group", "Remark", "Check"),
        ]),
        "SecurityGroup": _FakeWs([
            tuple([None] * 17),
            tuple([None] * 17),
            ("System", "Category", "Hostname", "IP", "Landscape",
             "System", "Category", "Hostname", "IP",
             "Port", "Protocol", "Expiration", "Purpose",
             "CUS FW", "CUS SG", "PSM FW", "PSM SG"),
        ]),
    }
    sheets.update(overrides)
    return _FakeWb(sheets)


# ---------------------------------------------------------------------------
# TestStructureType
# ---------------------------------------------------------------------------

class TestStructureType:
    def test_key_value_vertical_exists(self):
        assert StructureType.KEY_VALUE_VERTICAL == "key_value_vertical"

    def test_semi_structured_exists(self):
        assert StructureType.SEMI_STRUCTURED == "semi_structured"

    def test_merged_header_exists(self):
        assert StructureType.MERGED_HEADER == "merged_header"

    def test_simple_table_exists(self):
        assert StructureType.SIMPLE_TABLE == "simple_table"

    def test_narrative_exists(self):
        assert StructureType.NARRATIVE == "narrative"

    def test_all_five_types_defined(self):
        assert len(StructureType) == 5


# ---------------------------------------------------------------------------
# TestSheetRegistry — structure validation
# ---------------------------------------------------------------------------

class TestSheetRegistry:
    def test_registry_is_a_list(self):
        assert isinstance(SHEET_REGISTRY, list)

    def test_five_active_entries(self):
        assert len(SHEET_REGISTRY) == 5

    def test_all_entries_are_sheet_config(self):
        for entry in SHEET_REGISTRY:
            assert isinstance(entry, SheetConfig)

    def test_sheet_names_are_strings(self):
        for entry in SHEET_REGISTRY:
            assert isinstance(entry.sheet_name, str)
            assert entry.sheet_name

    def test_structure_types_are_valid(self):
        valid = set(StructureType)
        for entry in SHEET_REGISTRY:
            assert entry.structure_type in valid

    def test_parse_fns_are_callable(self):
        for entry in SHEET_REGISTRY:
            assert callable(entry.parse_fn)

    def test_merge_fns_are_callable(self):
        for entry in SHEET_REGISTRY:
            assert callable(entry.merge_fn)

    def test_drift_methods_are_strings(self):
        for entry in SHEET_REGISTRY:
            assert isinstance(entry.drift_method, str)
            assert entry.drift_method

    def test_required_is_bool(self):
        for entry in SHEET_REGISTRY:
            assert isinstance(entry.required, bool)

    def test_accinfo_uses_key_value_vertical(self):
        acc = next(e for e in SHEET_REGISTRY if e.sheet_name == "Accinfo")
        assert acc.structure_type == StructureType.KEY_VALUE_VERTICAL

    def test_nwinfo_uses_semi_structured(self):
        nw = next(e for e in SHEET_REGISTRY if e.sheet_name == "NWInfo")
        assert nw.structure_type == StructureType.SEMI_STRUCTURED

    def test_serverinfo_uses_merged_header(self):
        sv = next(e for e in SHEET_REGISTRY if e.sheet_name == "ServerInfo")
        assert sv.structure_type == StructureType.MERGED_HEADER

    def test_filesystem_uses_simple_table(self):
        fs = next(e for e in SHEET_REGISTRY if e.sheet_name == "FileSystem")
        assert fs.structure_type == StructureType.SIMPLE_TABLE

    def test_securitygroup_uses_simple_table(self):
        sg = next(e for e in SHEET_REGISTRY if e.sheet_name == "SecurityGroup")
        assert sg.structure_type == StructureType.SIMPLE_TABLE

    def test_accinfo_drift_method(self):
        acc = next(e for e in SHEET_REGISTRY if e.sheet_name == "Accinfo")
        assert acc.drift_method == "scp_vpc_subnet_api"

    def test_nwinfo_drift_method(self):
        nw = next(e for e in SHEET_REGISTRY if e.sheet_name == "NWInfo")
        assert nw.drift_method == "scp_subnet_cidr"

    def test_serverinfo_drift_method(self):
        sv = next(e for e in SHEET_REGISTRY if e.sheet_name == "ServerInfo")
        assert sv.drift_method == "vmware_api"

    def test_filesystem_drift_method(self):
        fs = next(e for e in SHEET_REGISTRY if e.sheet_name == "FileSystem")
        assert fs.drift_method == "os_df_output"

    def test_securitygroup_drift_method(self):
        sg = next(e for e in SHEET_REGISTRY if e.sheet_name == "SecurityGroup")
        assert sg.drift_method == "nsxt_dfw_api"

    def test_no_duplicate_sheet_names(self):
        names = [e.sheet_name for e in SHEET_REGISTRY]
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# TestRegistryDispatch — _parse_wb() uses the registry
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_all_five_sheets_returns_correct_keys(self):
        from src.parser import _parse_wb
        result = _parse_wb(_make_wb())
        expected_keys = {
            "project_metadata", "global_network_context", "network",
            "vmware_vm", "filesystem", "firewall_rule_candidates",
            "parser_warnings", "ignored_labels",
        }
        assert set(result.keys()) == expected_keys

    def test_missing_required_sheet_adds_warning(self):
        from src.parser import _parse_wb
        wb = _FakeWb({
            "Accinfo":       _FakeWs(),
            "NWInfo":        _FakeWs(),
            "ServerInfo":    _make_wb()._sheets["ServerInfo"],
            # FileSystem intentionally missing
            "SecurityGroup": _make_wb()._sheets["SecurityGroup"],
        })
        result = _parse_wb(wb)
        assert any("FileSystem" in w for w in result["parser_warnings"])

    def test_missing_required_sheet_returns_empty_list_for_that_key(self):
        from src.parser import _parse_wb
        wb = _FakeWb({
            "Accinfo":       _FakeWs(),
            "NWInfo":        _FakeWs(),
            "ServerInfo":    _make_wb()._sheets["ServerInfo"],
            # FileSystem intentionally missing
            "SecurityGroup": _make_wb()._sheets["SecurityGroup"],
        })
        result = _parse_wb(wb)
        assert result["filesystem"] == []

    def test_empty_sheets_produce_empty_collections(self):
        from src.parser import _parse_wb
        result = _parse_wb(_make_wb())
        assert result["vmware_vm"] == []
        assert result["filesystem"] == []
        assert result["firewall_rule_candidates"] == []
