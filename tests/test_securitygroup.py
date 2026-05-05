"""Tests for src/parser/securitygroup.py — written before implementation."""
import pytest
from src.parser.securitygroup import parse_securitygroup

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_N_COLS = 17

# Three header rows the parser must skip
_HDR1 = tuple([None] * _N_COLS)           # row 0: spacer
_HDR2 = ("Source", None, None, None, None, "Target", None, None, None,
          None, None, "ETC", None, "Work", None, None, None)  # row 1: grouping
_HDR3 = (                                  # row 2: actual column headers
    "System", "Category", "Hostname", "IP", "Landscape",
    "System", "Category", "Hostname", "IP",
    "Port", "Protocol", "Expiration", "Purpose",
    "CUS FW", "CUS SG", "PSM FW", "PSM SG",
)
_HEADERS = (_HDR1, _HDR2, _HDR3)


def _blank_17():
    return tuple([None] * _N_COLS)


def _row(
    source_system="S4H",
    source_category="APP",
    source_hostname="vhexample01",
    source_ip="10.0.0.1",
    source_landscape="PRD",
    target_system="S4H",
    target_category="DB",
    target_hostname="vhexample02",
    target_ip="10.0.0.2",
    port="3200-3299",
    protocol="TCP",
    expiration=None,
    purpose="HANA SQL",
    cus_fw="O",
    cus_sg="O",
    psm_fw="X",
    psm_sg="X",
):
    r = [None] * _N_COLS
    r[0]  = source_system
    r[1]  = source_category
    r[2]  = source_hostname
    r[3]  = source_ip
    r[4]  = source_landscape
    r[5]  = target_system
    r[6]  = target_category
    r[7]  = target_hostname
    r[8]  = target_ip
    r[9]  = port
    r[10] = protocol
    r[11] = expiration
    r[12] = purpose
    r[13] = cus_fw
    r[14] = cus_sg
    r[15] = psm_fw
    r[16] = psm_sg
    return tuple(r)


def _sparse_row(**kwargs):
    """A row where only cols 13-16 have values (cols 0-12 blank → must be skipped)."""
    r = [None] * _N_COLS
    r[13] = kwargs.get("cus_fw", "O")
    r[14] = kwargs.get("cus_sg", "O")
    r[15] = kwargs.get("psm_fw", "X")
    r[16] = kwargs.get("psm_sg", "X")
    return tuple(r)


class FakeWs:
    def __init__(self, rows):
        self._rows = rows

    def iter_rows(self, values_only=True):
        return iter(self._rows)


def _ws(*data_rows):
    """Wrap data rows with the 3 header rows."""
    return FakeWs(list(_HEADERS) + list(data_rows))


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:
    def test_returns_two_tuple(self):
        result = parse_securitygroup(_ws())
        assert isinstance(result, tuple) and len(result) == 2

    def test_first_element_is_list(self):
        candidates, _ = parse_securitygroup(_ws())
        assert isinstance(candidates, list)

    def test_second_element_is_list(self):
        _, warnings = parse_securitygroup(_ws())
        assert isinstance(warnings, list)

    def test_empty_sheet_returns_empty_list(self):
        candidates, warnings = parse_securitygroup(_ws())
        assert candidates == []
        assert warnings == []


# ---------------------------------------------------------------------------
# Header rows are skipped
# ---------------------------------------------------------------------------

class TestHeaderSkip:
    def test_three_header_rows_not_parsed(self):
        # Only headers → no candidates
        candidates, _ = parse_securitygroup(_ws())
        assert candidates == []

    def test_header_content_produces_no_warnings(self):
        _, warnings = parse_securitygroup(_ws())
        assert warnings == []


# ---------------------------------------------------------------------------
# Skip rule: cols 0-12 all blank → row is skipped (not termination)
# ---------------------------------------------------------------------------

class TestSkipRule:
    def test_row_with_all_blank_cols_0_to_12_is_skipped(self):
        candidates, _ = parse_securitygroup(_ws(_sparse_row()))
        assert candidates == []

    def test_fully_blank_row_is_skipped(self):
        candidates, _ = parse_securitygroup(_ws(_blank_17()))
        assert candidates == []

    def test_blank_row_does_not_stop_parsing(self):
        # Unlike other parsers, blank rows are skipped — NOT a terminator.
        rows = [
            _row(source_system="S4H_A"),
            _blank_17(),
            _row(source_system="S4H_B"),
        ]
        candidates, _ = parse_securitygroup(_ws(*rows))
        systems = [c["source_system"] for c in candidates]
        assert "S4H_A" in systems
        assert "S4H_B" in systems

    def test_multiple_blank_rows_between_data_rows_all_skipped(self):
        rows = [_blank_17(), _row(source_system="S4H_X"), _blank_17()]
        candidates, _ = parse_securitygroup(_ws(*rows))
        assert len(candidates) == 1

    def test_row_with_only_col_12_populated_is_included(self):
        # cols 0-11 blank, col 12 has purpose → NOT all blank → include
        r = list(_blank_17())
        r[12] = "SAP logon"
        candidates, _ = parse_securitygroup(_ws(tuple(r)))
        assert len(candidates) == 1


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------

class TestFieldMapping:
    def setup_method(self):
        self.c = parse_securitygroup(_ws(_row(
            source_system="ERP",
            source_category="APP",
            source_hostname="vhsrc01",
            source_ip="10.0.1.1",
            source_landscape="PRD",
            target_system="HDB",
            target_category="DB",
            target_hostname="vhtgt01",
            target_ip="10.0.2.1",
            port="30013",
            protocol="TCP",
            expiration="2026-12-31",
            purpose="HANA SQL",
            cus_fw="O",
            cus_sg="X",
            psm_fw="O",
            psm_sg="X",
        )))[0][0]

    def test_source_system(self):
        assert self.c["source_system"] == "ERP"

    def test_source_category(self):
        assert self.c["source_category"] == "APP"

    def test_source_hostname(self):
        assert self.c["source_hostname"] == "vhsrc01"

    def test_source_ip(self):
        assert self.c["source_ip"] == "10.0.1.1"

    def test_source_landscape(self):
        assert self.c["source_landscape"] == "PRD"

    def test_target_system(self):
        assert self.c["target_system"] == "HDB"

    def test_target_category(self):
        assert self.c["target_category"] == "DB"

    def test_target_hostname(self):
        assert self.c["target_hostname"] == "vhtgt01"

    def test_target_ip(self):
        assert self.c["target_ip"] == "10.0.2.1"

    def test_port(self):
        assert self.c["port"] == "30013"

    def test_protocol(self):
        assert self.c["protocol"] == "TCP"

    def test_expiration(self):
        assert self.c["expiration"] == "2026-12-31"

    def test_purpose(self):
        assert self.c["purpose"] == "HANA SQL"

    def test_cus_fw_O_is_true(self):
        assert self.c["cus_fw"] is True

    def test_cus_sg_X_is_false(self):
        assert self.c["cus_sg"] is False

    def test_psm_fw_O_is_true(self):
        assert self.c["psm_fw"] is True

    def test_psm_sg_X_is_false(self):
        assert self.c["psm_sg"] is False


# ---------------------------------------------------------------------------
# Port format: stored as raw string, not parsed
# ---------------------------------------------------------------------------

class TestPortFormat:
    def _candidate(self, raw_port):
        return parse_securitygroup(_ws(_row(port=raw_port)))[0][0]

    def _get_port(self, raw_port):
        return self._candidate(raw_port)["port"]

    def test_single_integer_port(self):
        assert self._get_port(443) == "443"

    def test_comma_separated_ports(self):
        assert self._get_port("1128,1129") == "1128,1129"

    def test_hyphen_range(self):
        assert self._get_port("3200-3399") == "3200-3399"

    def test_tilde_range(self):
        assert self._get_port("30200~30298") == "30200~30298"

    def test_none_port_stays_none(self):
        assert self._get_port(None) is None


class TestPortExpression:
    def _expr(self, raw_port):
        return parse_securitygroup(_ws(_row(port=raw_port)))[0][0]["port_expression"]

    def test_single_digit_port_is_not_expression(self):
        assert self._expr(443) is False

    def test_none_port_is_not_expression(self):
        assert self._expr(None) is False

    def test_comma_separated_is_expression(self):
        assert self._expr("1128,1129") is True

    def test_hyphen_range_is_expression(self):
        assert self._expr("3200-3399") is True

    def test_tilde_range_is_expression(self):
        assert self._expr("30200~30298") is True

    def test_string_digit_only_port_is_not_expression(self):
        assert self._expr("443") is False


# ---------------------------------------------------------------------------
# Boolean normalization for all four flag fields
# ---------------------------------------------------------------------------

class TestBooleanFields:
    def _flags(self, cus_fw, cus_sg, psm_fw, psm_sg):
        c = parse_securitygroup(_ws(_row(
            cus_fw=cus_fw, cus_sg=cus_sg, psm_fw=psm_fw, psm_sg=psm_sg,
        )))[0][0]
        return c["cus_fw"], c["cus_sg"], c["psm_fw"], c["psm_sg"]

    def test_all_O_are_true(self):
        assert self._flags("O", "O", "O", "O") == (True, True, True, True)

    def test_all_X_are_false(self):
        assert self._flags("X", "X", "X", "X") == (False, False, False, False)

    def test_all_none_are_false(self):
        assert self._flags(None, None, None, None) == (False, False, False, False)

    def test_mixed_flags(self):
        cus_fw, cus_sg, psm_fw, psm_sg = self._flags("O", "X", None, "O")
        assert cus_fw is True
        assert cus_sg is False
        assert psm_fw is False
        assert psm_sg is True


# ---------------------------------------------------------------------------
# Multiple data rows
# ---------------------------------------------------------------------------

class TestMultipleRows:
    def test_all_qualifying_rows_included(self):
        rows = [_row(source_system=f"SYS{i}") for i in range(5)]
        candidates, _ = parse_securitygroup(_ws(*rows))
        assert len(candidates) == 5

    def test_output_key_is_firewall_rule_candidates_compatible(self):
        # Each candidate is a dict with at minimum source/target/port fields
        candidates, _ = parse_securitygroup(_ws(_row()))
        assert len(candidates) == 1
        c = candidates[0]
        for key in ("source_system", "target_system", "port", "cus_fw", "psm_fw"):
            assert key in c, f"missing key: {key}"
