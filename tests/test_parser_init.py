"""Tests for src/parser/__init__.py — parse_s2d entry point.

Tests operate on _parse_wb(wb) with fake workbook objects so no real
Excel file is required. parse_s2d(path) is verified only for basic
error propagation (non-existent path).
"""
import pytest
from src.parser import _parse_wb, parse_s2d

# ---------------------------------------------------------------------------
# Shared fake infrastructure
# ---------------------------------------------------------------------------

class FakeWs:
    def __init__(self, rows):
        self._rows = rows

    def iter_rows(self, values_only=True):
        return iter(self._rows)


class FakeWb:
    def __init__(self, sheets: dict):
        self._sheets = sheets

    def __getitem__(self, name):
        return self._sheets[name]


# ---------------------------------------------------------------------------
# Minimal empty worksheets (correct header structure, no data rows)
# ---------------------------------------------------------------------------

def _accinfo_ws(rows=()):
    return FakeWs(list(rows))


def _nwinfo_ws(rows=()):
    return FakeWs(list(rows))


def _serverinfo_ws(rows=()):
    # 3 header rows the parser skips, then optional data rows
    hdr1 = tuple([None] * 43)
    hdr2 = ("Phase", "vhost", "phost", "Landscape", "SID", "Type",
            "Main Solution", "SID Cat I", "SID Cat II", "Type", "Role",
            "Host No", "VM/BM", "CDD", "SCP Image", "OS Version",
            *([None] * 27))
    hdr3 = tuple([None] * 43)
    return FakeWs([hdr1, hdr2, hdr3] + list(rows))


def _filesystem_ws(rows=()):
    hdr1 = tuple([None] * 19)
    hdr2 = ("No.", "Landscape", "SID", "Server Type", "FS Cat1",
            "FS Cat2", "SLA Tier", "HA", "FS Count", "FS Seq",
            "Hostname", "Admin IP", "Mount Point", "Size (GB)", "FS Type",
            "VG Name", "NFS Group", "Remark", "Check")
    return FakeWs([hdr1, hdr2] + list(rows))


def _securitygroup_ws(rows=()):
    hdr1 = tuple([None] * 17)
    hdr2 = tuple([None] * 17)
    hdr3 = ("System", "Category", "Hostname", "IP", "Landscape",
            "System", "Category", "Hostname", "IP",
            "Port", "Protocol", "Expiration", "Purpose",
            "CUS FW", "CUS SG", "PSM FW", "PSM SG")
    return FakeWs([hdr1, hdr2, hdr3] + list(rows))


def _empty_wb():
    return FakeWb({
        "Accinfo":       _accinfo_ws(),
        "NWInfo":        _nwinfo_ws(),
        "ServerInfo":    _serverinfo_ws(),
        "FileSystem":    _filesystem_ws(),
        "SecurityGroup": _securitygroup_ws(),
    })


# ---------------------------------------------------------------------------
# Minimal data-row builders
# ---------------------------------------------------------------------------

def _accinfo_label_row(label, value=None):
    r = [None] * 17
    r[0] = label
    r[6] = value
    return tuple(r)


def _server_row(vhost="vhtest01", entry_type="server"):
    r = [None] * 43
    r[1]  = vhost
    r[9]  = entry_type
    r[23] = "10.1.0.1"
    return tuple(r)


def _fs_row(hostname="phtest01"):
    r = [None] * 19
    r[10] = hostname
    r[13] = 50   # size_gb integer
    return tuple(r)


def _sg_row(source_system="SYS_A"):
    r = [None] * 17
    r[0] = source_system
    r[9] = "443"
    r[10] = "TCP"
    r[12] = "Test purpose"
    return tuple(r)


def _nwinfo_with_subnet():
    # Customer section → PRD → header → one subnet data row
    pad = lambda row: tuple(list(row) + [None] * (8 - len(row)))
    return _nwinfo_ws([
        pad(("Customer",)),
        pad((None, "PRD/non-PRD")),
        pad((None, "No.", "Purpose", "IP Range", "NAT IP", "Hostname")),
        pad((None, 1, "Admin", "10.1.0.0/24", None, None)),
    ])


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:
    def setup_method(self):
        self.result = _parse_wb(_empty_wb())

    def test_returns_dict(self):
        assert isinstance(self.result, dict)

    def test_has_project_metadata(self):
        assert "project_metadata" in self.result

    def test_has_global_network_context(self):
        assert "global_network_context" in self.result

    def test_has_network(self):
        assert "network" in self.result

    def test_has_vmware_vm(self):
        assert "vmware_vm" in self.result

    def test_has_filesystem(self):
        assert "filesystem" in self.result

    def test_has_firewall_rule_candidates(self):
        assert "firewall_rule_candidates" in self.result

    def test_has_parser_warnings(self):
        assert "parser_warnings" in self.result

    def test_has_ignored_labels(self):
        assert "ignored_labels" in self.result


# ---------------------------------------------------------------------------
# Default types with empty sheets
# ---------------------------------------------------------------------------

class TestDefaultTypes:
    def setup_method(self):
        self.r = _parse_wb(_empty_wb())

    def test_project_metadata_is_dict(self):
        assert isinstance(self.r["project_metadata"], dict)

    def test_global_network_context_is_dict(self):
        assert isinstance(self.r["global_network_context"], dict)

    def test_network_is_dict(self):
        assert isinstance(self.r["network"], dict)

    def test_network_has_subnets(self):
        assert "subnets" in self.r["network"]

    def test_network_has_routing_table(self):
        assert "routing_table" in self.r["network"]

    def test_vmware_vm_is_list(self):
        assert isinstance(self.r["vmware_vm"], list)

    def test_filesystem_is_list(self):
        assert isinstance(self.r["filesystem"], list)

    def test_firewall_rule_candidates_is_list(self):
        assert isinstance(self.r["firewall_rule_candidates"], list)

    def test_parser_warnings_is_list(self):
        assert isinstance(self.r["parser_warnings"], list)

    def test_ignored_labels_is_list(self):
        assert isinstance(self.r["ignored_labels"], list)

    def test_empty_sheets_produce_empty_lists(self):
        assert self.r["vmware_vm"] == []
        assert self.r["filesystem"] == []
        assert self.r["firewall_rule_candidates"] == []
        assert self.r["parser_warnings"] == []
        assert self.r["ignored_labels"] == []


# ---------------------------------------------------------------------------
# Data routing — each sheet's data lands in the right output key
# ---------------------------------------------------------------------------

class TestDataRouting:
    def test_accinfo_customer_name_in_project_metadata(self):
        wb = FakeWb({
            "Accinfo": _accinfo_ws([_accinfo_label_row("Customer Name", "Test Corp")]),
            "NWInfo":        _nwinfo_ws(),
            "ServerInfo":    _serverinfo_ws(),
            "FileSystem":    _filesystem_ws(),
            "SecurityGroup": _securitygroup_ws(),
        })
        result = _parse_wb(wb)
        assert result["project_metadata"]["customer_name"] == "Test Corp"

    def test_serverinfo_server_row_in_vmware_vm(self):
        wb = FakeWb({
            "Accinfo":       _accinfo_ws(),
            "NWInfo":        _nwinfo_ws(),
            "ServerInfo":    _serverinfo_ws([_server_row("vhtest01", "server")]),
            "FileSystem":    _filesystem_ws(),
            "SecurityGroup": _securitygroup_ws(),
        })
        result = _parse_wb(wb)
        assert len(result["vmware_vm"]) == 1
        assert result["vmware_vm"][0]["identity"]["vhost"] == "vhtest01"

    def test_serverinfo_vip_row_excluded_from_vmware_vm(self):
        wb = FakeWb({
            "Accinfo":       _accinfo_ws(),
            "NWInfo":        _nwinfo_ws(),
            "ServerInfo":    _serverinfo_ws([_server_row("vhvip01", "vip")]),
            "FileSystem":    _filesystem_ws(),
            "SecurityGroup": _securitygroup_ws(),
        })
        result = _parse_wb(wb)
        assert result["vmware_vm"] == []

    def test_filesystem_row_in_filesystem(self):
        wb = FakeWb({
            "Accinfo":       _accinfo_ws(),
            "NWInfo":        _nwinfo_ws(),
            "ServerInfo":    _serverinfo_ws(),
            "FileSystem":    _filesystem_ws([_fs_row("phtest01")]),
            "SecurityGroup": _securitygroup_ws(),
        })
        result = _parse_wb(wb)
        assert len(result["filesystem"]) == 1
        assert result["filesystem"][0]["hostname"] == "phtest01"

    def test_securitygroup_row_in_firewall_rule_candidates(self):
        wb = FakeWb({
            "Accinfo":       _accinfo_ws(),
            "NWInfo":        _nwinfo_ws(),
            "ServerInfo":    _serverinfo_ws(),
            "FileSystem":    _filesystem_ws(),
            "SecurityGroup": _securitygroup_ws([_sg_row("SYS_A")]),
        })
        result = _parse_wb(wb)
        assert len(result["firewall_rule_candidates"]) == 1
        assert result["firewall_rule_candidates"][0]["source_system"] == "SYS_A"

    def test_nwinfo_subnet_in_network_subnets(self):
        wb = FakeWb({
            "Accinfo":       _accinfo_ws(),
            "NWInfo":        _nwinfo_with_subnet(),
            "ServerInfo":    _serverinfo_ws(),
            "FileSystem":    _filesystem_ws(),
            "SecurityGroup": _securitygroup_ws(),
        })
        result = _parse_wb(wb)
        assert len(result["network"]["subnets"]) == 1
        assert result["network"]["subnets"][0]["group"] == "customer"


# ---------------------------------------------------------------------------
# Warning aggregation
# ---------------------------------------------------------------------------

class TestWarningAggregation:
    def test_accinfo_unknown_label_appears_in_parser_warnings(self):
        wb = FakeWb({
            "Accinfo": _accinfo_ws([
                _accinfo_label_row("Completely Unknown Field XYZ", "some value"),
            ]),
            "NWInfo":        _nwinfo_ws(),
            "ServerInfo":    _serverinfo_ws(),
            "FileSystem":    _filesystem_ws(),
            "SecurityGroup": _securitygroup_ws(),
        })
        result = _parse_wb(wb)
        assert any("Completely Unknown Field XYZ" in w for w in result["parser_warnings"])

    def test_warnings_from_multiple_parsers_are_combined(self):
        # Two separate unknown labels in accinfo → two warnings
        wb = FakeWb({
            "Accinfo": _accinfo_ws([
                _accinfo_label_row("Unknown Field A"),
                _accinfo_label_row("Unknown Field B"),
            ]),
            "NWInfo":        _nwinfo_ws(),
            "ServerInfo":    _serverinfo_ws(),
            "FileSystem":    _filesystem_ws(),
            "SecurityGroup": _securitygroup_ws(),
        })
        result = _parse_wb(wb)
        assert len(result["parser_warnings"]) >= 2


# ---------------------------------------------------------------------------
# ignored_labels passthrough
# ---------------------------------------------------------------------------

class TestIgnoredLabels:
    def test_out_of_scope_label_in_ignored_labels(self):
        wb = FakeWb({
            "Accinfo": _accinfo_ws([
                _accinfo_label_row("VPC Name", None),
            ]),
            "NWInfo":        _nwinfo_ws(),
            "ServerInfo":    _serverinfo_ws(),
            "FileSystem":    _filesystem_ws(),
            "SecurityGroup": _securitygroup_ws(),
        })
        result = _parse_wb(wb)
        assert any("vpc name" in label.lower() for label in result["ignored_labels"])

    def test_ignored_labels_not_in_parser_warnings(self):
        wb = FakeWb({
            "Accinfo": _accinfo_ws([
                _accinfo_label_row("VPC Name", None),
            ]),
            "NWInfo":        _nwinfo_ws(),
            "ServerInfo":    _serverinfo_ws(),
            "FileSystem":    _filesystem_ws(),
            "SecurityGroup": _securitygroup_ws(),
        })
        result = _parse_wb(wb)
        assert not any("vpc name" in w.lower() for w in result["parser_warnings"])


# ---------------------------------------------------------------------------
# parse_s2d entry point — file I/O boundary
# ---------------------------------------------------------------------------

class TestParseSd2EntryPoint:
    def test_nonexistent_path_raises(self):
        with pytest.raises(Exception):
            parse_s2d("/nonexistent/path/to/file.xlsx")
