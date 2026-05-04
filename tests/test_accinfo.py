"""Tests for src/parser/accinfo.py — written before implementation."""
import pytest
from src.parser.accinfo import parse_accinfo

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_VALUE_COL = 6   # column G, 0-indexed
_N_COLS = 17


def _row(label=None, value=None):
    r = [None] * _N_COLS
    r[0] = label
    r[_VALUE_COL] = value
    return tuple(r)


def _blank():
    return tuple([None] * _N_COLS)


class FakeWs:
    def __init__(self, rows):
        self._rows = rows

    def iter_rows(self, values_only=True):
        return iter(self._rows)


# ---------------------------------------------------------------------------
# Minimal valid worksheet
# ---------------------------------------------------------------------------

_FULL_ROWS = [
    _row("General Information"),                           # section header → skip
    _row("Customer Name", "Generic Corp"),
    _row("Customer (CID)", "GCI"),
    _blank(),
    _row("IP Range", "10.0.0.0/22"),
    _row("DR IP Range", "10.0.4.0/22"),
    _row("Domain Name", "sap.generic.net"),
    _row("Customer Connectivity", "Cloud Peering"),
    _row("Customer N/W", "10.100.0.0/24\n10.100.1.0/24"),
    _row("Customer DNS Server (Primary)", "10.0.0.10"),
    _row("Customer DNS Server (Secondary)", "10.0.0.11"),
    _row("System Timezone", "KST (UTC+09:00)"),
    _row("VPC Name", None),                                # empty, out-of-scope → ignored_labels
    _row("Master Password", "placeholder"),                # out-of-scope → ignored_labels
    _row("SID Information"),                               # defer sentinel → stop parsing
    _row("S/4HANA", "APP"),                                # after SID → must be skipped
]


# ---------------------------------------------------------------------------
# Return-type contract
# ---------------------------------------------------------------------------

class TestReturnStructure:
    def test_returns_four_tuple(self):
        result = parse_accinfo(FakeWs(_FULL_ROWS))
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_project_metadata_is_dict(self):
        meta, _, _, _ = parse_accinfo(FakeWs(_FULL_ROWS))
        assert isinstance(meta, dict)

    def test_global_network_context_is_dict(self):
        _, ctx, _, _ = parse_accinfo(FakeWs(_FULL_ROWS))
        assert isinstance(ctx, dict)

    def test_warnings_is_list(self):
        _, _, warnings, _ = parse_accinfo(FakeWs(_FULL_ROWS))
        assert isinstance(warnings, list)

    def test_ignored_labels_is_list(self):
        _, _, _, ignored = parse_accinfo(FakeWs(_FULL_ROWS))
        assert isinstance(ignored, list)


# ---------------------------------------------------------------------------
# project_metadata fields
# ---------------------------------------------------------------------------

class TestProjectMetadata:
    def setup_method(self):
        self.meta, _, _, _ = parse_accinfo(FakeWs(_FULL_ROWS))

    def test_customer_name(self):
        assert self.meta["customer_name"] == "Generic Corp"

    def test_customer_id(self):
        assert self.meta["customer_id"] == "GCI"

    def test_domain_name(self):
        assert self.meta["domain_name"] == "sap.generic.net"

    def test_timezone(self):
        assert self.meta["timezone"] == "KST (UTC+09:00)"


# ---------------------------------------------------------------------------
# global_network_context fields
# ---------------------------------------------------------------------------

class TestGlobalNetworkContext:
    def setup_method(self):
        _, self.ctx, _, _ = parse_accinfo(FakeWs(_FULL_ROWS))

    def test_ip_range(self):
        assert self.ctx["ip_range"] == "10.0.0.0/22"

    def test_dr_ip_range(self):
        assert self.ctx["dr_ip_range"] == "10.0.4.0/22"

    def test_connectivity_type(self):
        assert self.ctx["connectivity_type"] == "Cloud Peering"

    def test_dns_primary(self):
        assert self.ctx["dns_primary"] == "10.0.0.10"

    def test_dns_secondary(self):
        assert self.ctx["dns_secondary"] == "10.0.0.11"

    def test_customer_networks_split_by_newline(self):
        assert self.ctx["customer_networks"] == ["10.100.0.0/24", "10.100.1.0/24"]


# ---------------------------------------------------------------------------
# Empty / None value handling
# ---------------------------------------------------------------------------

class TestEmptyValues:
    def test_none_value_emits_none_not_warning(self):
        rows = [_row("Customer Name", None)]
        meta, _, warnings, _ = parse_accinfo(FakeWs(rows))
        assert meta.get("customer_name") is None
        assert not warnings

    def test_missing_field_key_still_present_as_none(self):
        # Worksheet with no Domain Name row → key exists as None
        rows = [_row("Customer Name", "Generic Corp")]
        meta, _, _, _ = parse_accinfo(FakeWs(rows))
        assert "domain_name" in meta
        assert meta["domain_name"] is None

    def test_blank_rows_produce_no_warnings(self):
        rows = [_blank(), _blank(), _row("Customer Name", "X")]
        _, _, warnings, _ = parse_accinfo(FakeWs(rows))
        assert not warnings


# ---------------------------------------------------------------------------
# Section header handling
# ---------------------------------------------------------------------------

class TestSectionHeaders:
    def test_known_section_headers_not_in_warnings(self):
        rows = [
            _row("General Information"),
            _row("SCP Information"),
        ]
        _, _, warnings, _ = parse_accinfo(FakeWs(rows))
        assert not warnings

    def test_known_section_headers_not_in_ignored(self):
        rows = [_row("General Information")]
        _, _, _, ignored = parse_accinfo(FakeWs(rows))
        assert not ignored


# ---------------------------------------------------------------------------
# SID Information deferral
# ---------------------------------------------------------------------------

class TestSidDeferral:
    def test_rows_after_sid_information_are_skipped(self):
        rows = [
            _row("Customer Name", "Generic Corp"),
            _row("SID Information"),
            _row("Customer (CID)", "SHOULD_NOT_APPEAR"),  # after SID
        ]
        meta, _, _, _ = parse_accinfo(FakeWs(rows))
        # customer_id must remain None — rows after SID skipped
        assert meta.get("customer_id") is None

    def test_sid_information_header_not_in_warnings(self):
        rows = [_row("SID Information")]
        _, _, warnings, _ = parse_accinfo(FakeWs(rows))
        assert not warnings


# ---------------------------------------------------------------------------
# Label classification: ignored_labels vs parser_warnings
# ---------------------------------------------------------------------------

class TestLabelClassification:
    def test_out_of_scope_label_goes_to_ignored_labels(self):
        rows = [_row("VPC Name", None)]
        _, _, warnings, ignored = parse_accinfo(FakeWs(rows))
        assert any("vpc name" in entry.lower() for entry in ignored)
        assert not warnings

    def test_out_of_scope_label_with_value_goes_to_ignored(self):
        rows = [_row("Master Password", "placeholder")]
        _, _, warnings, ignored = parse_accinfo(FakeWs(rows))
        assert any("master password" in entry.lower() for entry in ignored)
        assert not warnings

    def test_unknown_label_goes_to_warnings_not_ignored(self):
        rows = [_row("Completely Unknown Field XYZ", "some value")]
        _, _, warnings, ignored = parse_accinfo(FakeWs(rows))
        assert warnings
        assert not ignored

    def test_case_insensitive_label_matching(self):
        rows = [_row("customer name", "Generic Corp")]
        meta, _, warnings, _ = parse_accinfo(FakeWs(rows))
        assert meta["customer_name"] == "Generic Corp"
        assert not warnings


# ---------------------------------------------------------------------------
# Default output keys
# ---------------------------------------------------------------------------

class TestDefaultKeys:
    def test_project_metadata_has_all_expected_keys(self):
        meta, _, _, _ = parse_accinfo(FakeWs([]))
        for key in ("customer_name", "customer_id", "domain_name", "timezone"):
            assert key in meta, f"missing key: {key}"

    def test_global_network_context_has_all_expected_keys(self):
        _, ctx, _, _ = parse_accinfo(FakeWs([]))
        for key in ("ip_range", "dr_ip_range", "connectivity_type",
                    "customer_networks", "dns_primary", "dns_secondary"):
            assert key in ctx, f"missing key: {key}"

    def test_empty_worksheet_returns_all_none_values(self):
        meta, ctx, warnings, ignored = parse_accinfo(FakeWs([]))
        assert all(v is None or v == [] for v in meta.values())
        assert all(v is None or v == [] for v in ctx.values())
        assert not warnings
        assert not ignored
