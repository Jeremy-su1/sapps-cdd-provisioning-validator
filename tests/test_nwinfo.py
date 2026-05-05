"""Tests for src/parser/nwinfo.py — written before implementation.

NWInfo sheet layout (value-based, no fixed header rows):
  col 0 = section marker   : "Customer" | "Internal ..." | "Server Routing Table"
  col 1 = subsection marker: "PRD/non-PRD" | "DR" | "No."  (also seq_no in data rows)

Subnet data rows (after "No." header in col 1):
  col 0: blank/merged
  col 1: seq_no  (integer)
  col 2: purpose_raw
  col 3: ip_range
  col 4: nat_ip_range
  col 5: hostname_pattern

Routing data rows (after "No." header in col 0):
  col 0: seq_no  (integer)
  col 1: routing_name
  col 2: target_cidr
  col 3: source_ip
  col 4: remark
"""
import pytest
from src.parser.nwinfo import parse_nwinfo

# ---------------------------------------------------------------------------
# Row-builder helpers
# ---------------------------------------------------------------------------

_N_COLS = 8


def _pad(row):
    lst = list(row)
    lst += [None] * (_N_COLS - len(lst))
    return tuple(lst)


def _blank():
    return _pad(())


# Section header rows (col 0)
def _section(name):
    return _pad((name,))


# Subsection rows (col 1): "PRD/non-PRD", "DR"
def _subsection(marker):
    return _pad((None, marker))


# Column-header row in subnet sections: col 1 = "No."
def _subnet_header():
    return _pad((None, "No.", "Purpose", "IP Range", "NAT IP Range", "Hostname"))


# Subnet data row
def _subnet(seq_no=1, purpose="Production Service",
            ip_range="10.0.0.0/24", nat_ip_range=None, hostname_pattern=None):
    return _pad((None, seq_no, purpose, ip_range, nat_ip_range, hostname_pattern))


# Column-header row in routing section: col 0 = "No."
def _routing_header():
    return _pad(("No.", "Routing Name", "Target", "Source", "Remark"))


# Routing data row
def _routing(seq_no=1, routing_name="Route A",
             target_cidr="10.0.0.0/8", source_ip="172.16.0.1", remark=None):
    return _pad((seq_no, routing_name, target_cidr, source_ip, remark))


class FakeWs:
    def __init__(self, rows):
        self._rows = rows

    def iter_rows(self, values_only=True):
        return iter(self._rows)


def _ws(*rows):
    return FakeWs(list(rows))


# ---------------------------------------------------------------------------
# Convenience full-sheet builder
# ---------------------------------------------------------------------------

def _full_sheet():
    return _ws(
        # Customer section — PRD block
        _section("Customer"),
        _subsection("PRD/non-PRD"),
        _subnet_header(),
        _subnet(1, "Production Service", "10.0.0.0/24", None, "vhexample*"),
        _subnet(2, "Admin", "10.1.0.0/24", "192.168.0.0/24", None),
        # Customer section — DR block
        _subsection("DR"),
        _subnet_header(),
        _subnet(1, "Production Service", "10.4.0.0/24", None, None),
        # Internal section — PRD block
        _section("Internal - Storage Network"),
        _subsection("PRD/non-PRD"),
        _subnet_header(),
        _subnet(1, "Storage", "10.2.0.0/24", None, None),
        # Routing table
        _section("Server Routing Table"),
        _routing_header(),
        _routing(1, "Customer Route", "10.100.0.0/16", "10.0.0.1", "Main"),
        _routing(2, "DR Route", "10.104.0.0/16", "10.0.0.1", None),
    )


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:
    def test_returns_two_tuple(self):
        result = parse_nwinfo(_ws())
        assert isinstance(result, tuple) and len(result) == 2

    def test_first_element_is_dict(self):
        network, _ = parse_nwinfo(_ws())
        assert isinstance(network, dict)

    def test_second_element_is_list(self):
        _, warnings = parse_nwinfo(_ws())
        assert isinstance(warnings, list)

    def test_network_has_subnets_key(self):
        network, _ = parse_nwinfo(_ws())
        assert "subnets" in network

    def test_network_has_routing_table_key(self):
        network, _ = parse_nwinfo(_ws())
        assert "routing_table" in network

    def test_subnets_is_list(self):
        network, _ = parse_nwinfo(_ws())
        assert isinstance(network["subnets"], list)

    def test_routing_table_is_list(self):
        network, _ = parse_nwinfo(_ws())
        assert isinstance(network["routing_table"], list)

    def test_empty_sheet_returns_empty_lists(self):
        network, warnings = parse_nwinfo(_ws())
        assert network["subnets"] == []
        assert network["routing_table"] == []
        assert warnings == []


# ---------------------------------------------------------------------------
# Section detection: group assignment
# ---------------------------------------------------------------------------

class TestGroupDetection:
    def test_customer_section_sets_group_customer(self):
        ws = _ws(
            _section("Customer"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
            _subnet(1, "Admin", "10.1.0.0/24"),
        )
        network, _ = parse_nwinfo(ws)
        assert network["subnets"][0]["group"] == "customer"

    def test_internal_section_sets_group_internal(self):
        ws = _ws(
            _section("Internal - Storage Network"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
            _subnet(1, "Storage", "10.2.0.0/24"),
        )
        network, _ = parse_nwinfo(ws)
        assert network["subnets"][0]["group"] == "internal"

    def test_customer_case_insensitive(self):
        ws = _ws(
            _section("CUSTOMER"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
            _subnet(1, "Admin", "10.1.0.0/24"),
        )
        network, _ = parse_nwinfo(ws)
        assert network["subnets"][0]["group"] == "customer"

    def test_internal_partial_match(self):
        # "Internal - plan description" → group = "internal"
        ws = _ws(
            _section("Internal - plan description"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
            _subnet(1, "Storage", "10.2.0.0/24"),
        )
        network, _ = parse_nwinfo(ws)
        assert network["subnets"][0]["group"] == "internal"


# ---------------------------------------------------------------------------
# Subsection detection: env assignment
# ---------------------------------------------------------------------------

class TestEnvDetection:
    def test_prd_non_prd_subsection_sets_env_prd(self):
        ws = _ws(
            _section("Customer"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
            _subnet(1, "Admin", "10.1.0.0/24"),
        )
        network, _ = parse_nwinfo(ws)
        assert network["subnets"][0]["env"] == "prd"

    def test_dr_subsection_sets_env_dr(self):
        ws = _ws(
            _section("Customer"),
            _subsection("DR"),
            _subnet_header(),
            _subnet(1, "Admin", "10.4.0.0/24"),
        )
        network, _ = parse_nwinfo(ws)
        assert network["subnets"][0]["env"] == "dr"

    def test_env_resets_when_new_subsection_starts(self):
        ws = _ws(
            _section("Customer"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
            _subnet(1, "Admin", "10.1.0.0/24"),
            _subsection("DR"),
            _subnet_header(),
            _subnet(1, "Admin", "10.4.0.0/24"),
        )
        network, _ = parse_nwinfo(ws)
        envs = [s["env"] for s in network["subnets"]]
        assert envs == ["prd", "dr"]


# ---------------------------------------------------------------------------
# Subnet field mapping
# ---------------------------------------------------------------------------

class TestSubnetFieldMapping:
    def setup_method(self):
        ws = _ws(
            _section("Customer"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
            _subnet(3, "Production Service", "10.0.1.0/24", "192.168.1.0/24", "vhexample*"),
        )
        network, _ = parse_nwinfo(ws)
        self.s = network["subnets"][0]

    def test_group(self):
        assert self.s["group"] == "customer"

    def test_env(self):
        assert self.s["env"] == "prd"

    def test_seq_no(self):
        assert self.s["seq_no"] == 3

    def test_purpose_raw(self):
        assert self.s["purpose_raw"] == "Production Service"

    def test_ip_range(self):
        assert self.s["ip_range"] == "10.0.1.0/24"

    def test_nat_ip_range(self):
        assert self.s["nat_ip_range"] == "192.168.1.0/24"

    def test_hostname_pattern(self):
        assert self.s["hostname_pattern"] == "vhexample*"

    def test_nat_ip_range_none(self):
        ws = _ws(
            _section("Customer"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
            _subnet(1, "Admin", "10.1.0.0/24", None, None),
        )
        network, _ = parse_nwinfo(ws)
        assert network["subnets"][0]["nat_ip_range"] is None

    def test_hostname_pattern_none(self):
        ws = _ws(
            _section("Customer"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
            _subnet(1, "Admin", "10.1.0.0/24", None, None),
        )
        network, _ = parse_nwinfo(ws)
        assert network["subnets"][0]["hostname_pattern"] is None


# ---------------------------------------------------------------------------
# purpose_key normalization
# ---------------------------------------------------------------------------

class TestPurposeKey:
    def _key(self, purpose_raw):
        ws = _ws(
            _section("Customer"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
            _subnet(1, purpose_raw, "10.0.0.0/24"),
        )
        network, _ = parse_nwinfo(ws)
        return network["subnets"][0]["purpose_key"]

    def test_production_service(self):
        assert self._key("Production Service") == "production_service"

    def test_heartbeat(self):
        assert self._key("HeartBeat") == "heartbeat"

    def test_admin(self):
        assert self._key("Admin") == "admin"

    def test_storage(self):
        assert self._key("Storage") == "storage"

    def test_backup(self):
        assert self._key("Backup") == "backup"

    def test_public(self):
        assert self._key("Public") == "public"

    def test_unknown_maps_to_other(self):
        assert self._key("Exotic Network Zone") == "other"

    def test_none_maps_to_other(self):
        assert self._key(None) == "other"

    def test_public_subnet_maps_to_public(self):
        assert self._key("Public Subnet") == "public"

    def test_purpose_raw_preserved_unchanged(self):
        ws = _ws(
            _section("Customer"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
            _subnet(1, "Production Service", "10.0.0.0/24"),
        )
        network, _ = parse_nwinfo(ws)
        assert network["subnets"][0]["purpose_raw"] == "Production Service"


# ---------------------------------------------------------------------------
# Routing table field mapping
# ---------------------------------------------------------------------------

class TestRoutingTableFieldMapping:
    def setup_method(self):
        ws = _ws(
            _section("Server Routing Table"),
            _routing_header(),
            _routing(2, "Customer Route", "10.100.0.0/16", "10.0.0.1", "Primary"),
        )
        network, _ = parse_nwinfo(ws)
        self.r = network["routing_table"][0]

    def test_routing_name(self):
        assert self.r["routing_name"] == "Customer Route"

    def test_target_cidr(self):
        assert self.r["target_cidr"] == "10.100.0.0/16"

    def test_source_ip(self):
        assert self.r["source_ip"] == "10.0.0.1"

    def test_remark(self):
        assert self.r["remark"] == "Primary"

    def test_remark_none(self):
        ws = _ws(
            _section("Server Routing Table"),
            _routing_header(),
            _routing(1, "DR Route", "10.104.0.0/16", "10.0.0.2", None),
        )
        network, _ = parse_nwinfo(ws)
        assert network["routing_table"][0]["remark"] is None


# ---------------------------------------------------------------------------
# Header / marker rows not included in output
# ---------------------------------------------------------------------------

class TestMarkerRowsExcluded:
    def test_section_header_not_in_subnets(self):
        ws = _ws(_section("Customer"))
        network, _ = parse_nwinfo(ws)
        assert network["subnets"] == []

    def test_subsection_row_not_in_subnets(self):
        ws = _ws(
            _section("Customer"),
            _subsection("PRD/non-PRD"),
        )
        network, _ = parse_nwinfo(ws)
        assert network["subnets"] == []

    def test_column_header_row_not_in_subnets(self):
        ws = _ws(
            _section("Customer"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
        )
        network, _ = parse_nwinfo(ws)
        assert network["subnets"] == []

    def test_routing_header_not_in_routing_table(self):
        ws = _ws(
            _section("Server Routing Table"),
            _routing_header(),
        )
        network, _ = parse_nwinfo(ws)
        assert network["routing_table"] == []

    def test_data_rows_before_no_header_not_included(self):
        # Rows appear in section but before the "No." header → not collected
        ws = _ws(
            _section("Customer"),
            _subsection("PRD/non-PRD"),
            # No _subnet_header() → in_data never set
            _subnet(1, "Admin", "10.1.0.0/24"),
        )
        network, _ = parse_nwinfo(ws)
        assert network["subnets"] == []


# ---------------------------------------------------------------------------
# Blank row handling
# ---------------------------------------------------------------------------

class TestBlankRows:
    def test_blank_row_within_subnet_data_is_skipped(self):
        ws = _ws(
            _section("Customer"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
            _subnet(1, "Admin", "10.1.0.0/24"),
            _blank(),
            _subnet(2, "Storage", "10.2.0.0/24"),
        )
        network, _ = parse_nwinfo(ws)
        assert len(network["subnets"]) == 2

    def test_blank_row_within_routing_data_is_skipped(self):
        ws = _ws(
            _section("Server Routing Table"),
            _routing_header(),
            _routing(1, "Route A", "10.0.0.0/8", "10.0.0.1"),
            _blank(),
            _routing(2, "Route B", "10.1.0.0/8", "10.0.0.1"),
        )
        network, _ = parse_nwinfo(ws)
        assert len(network["routing_table"]) == 2


# ---------------------------------------------------------------------------
# Multiple sections / full-sheet integration
# ---------------------------------------------------------------------------

class TestMultipleSections:
    def setup_method(self):
        self.network, self.warnings = parse_nwinfo(_full_sheet())

    def test_customer_and_internal_subnets_all_collected(self):
        groups = [s["group"] for s in self.network["subnets"]]
        assert "customer" in groups
        assert "internal" in groups

    def test_prd_and_dr_subnets_both_collected(self):
        envs = [s["env"] for s in self.network["subnets"]]
        assert "prd" in envs
        assert "dr" in envs

    def test_routing_table_has_all_entries(self):
        assert len(self.network["routing_table"]) == 2

    def test_total_subnet_count(self):
        # 2 customer-prd + 1 customer-dr + 1 internal-prd = 4
        assert len(self.network["subnets"]) == 4

    def test_no_warnings_on_well_formed_sheet(self):
        assert self.warnings == []


# ---------------------------------------------------------------------------
# Routing section: annotation rows inside routing table must not reset state
# ---------------------------------------------------------------------------

class TestRoutingAnnotationRows:
    def test_customer_annotation_inside_routing_does_not_reset_section(self):
        # Real NWInfo sheet has a "Customer" annotation row inside the routing
        # table section (used as a visual sub-header). Must not re-trigger
        # the customer-section detection and discard routing rows.
        ws = _ws(
            _section("Server Routing Table"),
            _section("Customer"),          # annotation, NOT a new section
            _routing_header(),
            _routing(1, "Admin Route", "192.168.0.0/16", "10.0.0.1"),
        )
        network, _ = parse_nwinfo(ws)
        assert len(network["routing_table"]) == 1

    def test_routing_entry_collected_after_customer_annotation(self):
        ws = _ws(
            _section("Server Routing Table"),
            _section("Customer"),
            _routing_header(),
            _routing(1, "Admin Route", "192.168.0.0/16", "10.0.0.1", "Main"),
            _routing(2, "Backup Route", "192.167.0.0/16", "192.167.14.1", None),
        )
        network, _ = parse_nwinfo(ws)
        assert len(network["routing_table"]) == 2
        assert network["routing_table"][0]["routing_name"] == "Admin Route"

    def test_subnet_sections_before_routing_still_work(self):
        ws = _ws(
            _section("Customer"),
            _subsection("PRD/non-PRD"),
            _subnet_header(),
            _subnet(1, "Admin", "10.1.0.0/24"),
            _section("Server Routing Table"),
            _section("Customer"),          # annotation inside routing
            _routing_header(),
            _routing(1, "Admin Route", "192.168.0.0/16", "10.0.0.1"),
        )
        network, _ = parse_nwinfo(ws)
        assert len(network["subnets"]) == 1
        assert len(network["routing_table"]) == 1
