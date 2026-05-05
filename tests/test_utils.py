"""Tests for src/parser/_utils.py — run BEFORE implementation exists."""
import pytest
from src.parser._utils import split_phost, normalize_bool, normalize_cidr_list, is_blank_row, is_valid_ipv4


# ---------------------------------------------------------------------------
# split_phost
# ---------------------------------------------------------------------------

class TestSplitPhost:
    # --- known_ip path (primary, used by serverinfo.py with col 23) ---

    def test_known_ip_strips_suffix_exactly(self):
        # The digit-overlap case: hostname ends in '01', IP starts with '10.'
        # Without known_ip the regex is ambiguous; with it we get exact split.
        hostname, ip = split_phost("phexamplehost0110.1.0.11", known_ip="10.1.0.11")
        assert hostname == "phexamplehost01"
        assert ip == "10.1.0.11"

    def test_known_ip_nat_address(self):
        hostname, ip = split_phost("phexamplehost01192.168.7.11", known_ip="192.168.7.11")
        assert hostname == "phexamplehost01"
        assert ip == "192.168.7.11"

    def test_known_ip_falls_back_to_regex_when_suffix_mismatch(self):
        # known_ip does not match the suffix → fall back to regex
        hostname, ip = split_phost("phexamplehost10.1.0.11", known_ip="10.1.0.99")
        # regex finds 10.1.0.11 (unambiguous — hostname has no trailing digits)
        assert hostname == "phexamplehost"
        assert ip == "10.1.0.11"

    # --- regex fallback (when known_ip absent, used for unambiguous cases) ---

    def test_regex_fallback_unambiguous_hostname(self):
        # Hostname does not end with digits → no overlap → regex correct
        hostname, ip = split_phost("phexamplehost10.1.0.11")
        assert hostname == "phexamplehost"
        assert ip == "10.1.0.11"

    def test_clean_hostname_no_ip(self):
        hostname, ip = split_phost("phexamplehost01")
        assert hostname == "phexamplehost01"
        assert ip == ""

    def test_none_input(self):
        hostname, ip = split_phost(None)
        assert hostname == ""
        assert ip == ""

    def test_empty_string(self):
        hostname, ip = split_phost("")
        assert hostname == ""
        assert ip == ""

    def test_ip_only(self):
        hostname, ip = split_phost("10.1.0.11")
        assert hostname == ""
        assert ip == "10.1.0.11"

    def test_strips_whitespace_from_hostname(self):
        hostname, ip = split_phost("phexamplehost10.1.0.11")
        assert hostname == "phexamplehost"
        assert ip == "10.1.0.11"


# ---------------------------------------------------------------------------
# normalize_bool
# ---------------------------------------------------------------------------

class TestNormalizeBool:
    def test_uppercase_O_is_true(self):
        assert normalize_bool("O") is True

    def test_lowercase_o_is_true(self):
        assert normalize_bool("o") is True

    def test_O_with_surrounding_spaces_is_true(self):
        assert normalize_bool("  O  ") is True

    def test_uppercase_X_is_false(self):
        assert normalize_bool("X") is False

    def test_lowercase_x_is_false(self):
        assert normalize_bool("x") is False

    def test_none_is_false(self):
        assert normalize_bool(None) is False

    def test_empty_string_is_false(self):
        assert normalize_bool("") is False

    def test_integer_zero_is_false(self):
        assert normalize_bool(0) is False

    def test_arbitrary_string_is_false(self):
        assert normalize_bool("yes") is False


# ---------------------------------------------------------------------------
# normalize_cidr_list
# ---------------------------------------------------------------------------

class TestNormalizeCidrList:
    def test_single_cidr(self):
        assert normalize_cidr_list("10.0.0.0/24") == ["10.0.0.0/24"]

    def test_multiline_cidrs(self):
        raw = "10.0.0.0/24\n10.1.0.0/24\n10.2.0.0/24"
        assert normalize_cidr_list(raw) == ["10.0.0.0/24", "10.1.0.0/24", "10.2.0.0/24"]

    def test_none_returns_empty_list(self):
        assert normalize_cidr_list(None) == []

    def test_empty_string_returns_empty_list(self):
        assert normalize_cidr_list("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert normalize_cidr_list("   \n  \n  ") == []

    def test_leading_trailing_newlines_stripped(self):
        assert normalize_cidr_list("\n10.0.0.0/24\n") == ["10.0.0.0/24"]

    def test_inner_blank_lines_skipped(self):
        raw = "10.0.0.0/24\n\n10.1.0.0/24"
        assert normalize_cidr_list(raw) == ["10.0.0.0/24", "10.1.0.0/24"]

    def test_entries_are_stripped(self):
        raw = "  10.0.0.0/24  \n  10.1.0.0/24  "
        assert normalize_cidr_list(raw) == ["10.0.0.0/24", "10.1.0.0/24"]


# ---------------------------------------------------------------------------
# is_blank_row
# ---------------------------------------------------------------------------

class TestIsBlankRow:
    def test_all_none_is_blank(self):
        assert is_blank_row((None, None, None)) is True

    def test_one_value_is_not_blank(self):
        assert is_blank_row((None, "value", None)) is False

    def test_all_values_is_not_blank(self):
        assert is_blank_row(("a", "b", "c")) is False

    def test_single_none_is_blank(self):
        assert is_blank_row((None,)) is True

    def test_single_value_is_not_blank(self):
        assert is_blank_row(("x",)) is False

    def test_empty_tuple_is_blank(self):
        # all() of empty iterable is True — consistent with "no non-None values"
        assert is_blank_row(()) is True


# ---------------------------------------------------------------------------
# is_valid_ipv4
# ---------------------------------------------------------------------------

class TestIsValidIpv4:
    def test_standard_ipv4_is_valid(self):
        assert is_valid_ipv4("10.1.0.11") is True

    def test_private_192_range_is_valid(self):
        assert is_valid_ipv4("192.168.7.11") is True

    def test_integer_zero_is_invalid(self):
        # Placeholder value written into admin_ip column when IP is unresolved
        assert is_valid_ipv4(0) is False

    def test_integer_one_is_invalid(self):
        assert is_valid_ipv4(1) is False

    def test_string_zero_is_invalid(self):
        assert is_valid_ipv4("0") is False

    def test_string_one_is_invalid(self):
        assert is_valid_ipv4("1") is False

    def test_none_is_invalid(self):
        assert is_valid_ipv4(None) is False

    def test_empty_string_is_invalid(self):
        assert is_valid_ipv4("") is False

    def test_partial_ip_is_invalid(self):
        assert is_valid_ipv4("10.1.0") is False

    def test_hostname_string_is_invalid(self):
        assert is_valid_ipv4("phgenericap01") is False
