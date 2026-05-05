"""Tests for src/parser/filesystem.py — written before implementation."""
import pytest
from src.parser.filesystem import parse_filesystem

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_N_COLS = 19

# Two header rows the parser must skip
_HDR1 = tuple([None] * _N_COLS)           # row 0: annotation
_HDR2 = (                                  # row 1: column labels
    "No.", "Landscape", "SID", "Server Type",
    "FS Cat.1", "FS Cat.2", "SLA Tier", "HA",
    "FS Count Max", "FS Seq", "Hostname", "Admin IP",
    "Mount Point", "Size (GB)", "FS Type", "VG Name",
    "NFS Group", "Remark", "Check",
)
_HEADERS = (_HDR1, _HDR2)


def _blank():
    return tuple([None] * _N_COLS)


def _row(
    seq_no=1,
    landscape="PRD",
    sid="EXP",
    server_type="AP",
    fs_category_1="OS",
    fs_category_2="root",
    sla_tier="Gold",
    ha_flag="O",
    fs_count_max=1,
    fs_seq_in_host=1,
    hostname="phexample01",
    admin_ip="10.1.0.1",
    mount_point="/",
    size_gb=50,
    fs_type="xfs",
    vg_name="vg_root",
    nfs_group=None,
    remark=None,
    check=None,
):
    r = [None] * _N_COLS
    r[0]  = seq_no
    r[1]  = landscape
    r[2]  = sid
    r[3]  = server_type
    r[4]  = fs_category_1
    r[5]  = fs_category_2
    r[6]  = sla_tier
    r[7]  = ha_flag
    r[8]  = fs_count_max
    r[9]  = fs_seq_in_host
    r[10] = hostname
    r[11] = admin_ip
    r[12] = mount_point
    r[13] = size_gb
    r[14] = fs_type
    r[15] = vg_name
    r[16] = nfs_group
    r[17] = remark
    r[18] = check
    return tuple(r)


class FakeWs:
    def __init__(self, rows):
        self._rows = rows

    def iter_rows(self, values_only=True):
        return iter(self._rows)


def _ws(*data_rows):
    """Wrap data rows with the 2 header rows."""
    return FakeWs(list(_HEADERS) + list(data_rows))


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:
    def test_returns_two_tuple(self):
        result = parse_filesystem(_ws())
        assert isinstance(result, tuple) and len(result) == 2

    def test_first_element_is_list(self):
        entries, _ = parse_filesystem(_ws())
        assert isinstance(entries, list)

    def test_second_element_is_list(self):
        _, warnings = parse_filesystem(_ws())
        assert isinstance(warnings, list)

    def test_empty_sheet_returns_empty_list(self):
        entries, warnings = parse_filesystem(_ws())
        assert entries == []
        assert warnings == []


# ---------------------------------------------------------------------------
# Header rows are skipped
# ---------------------------------------------------------------------------

class TestHeaderSkip:
    def test_two_header_rows_not_parsed(self):
        # Only headers → no entries
        entries, _ = parse_filesystem(_ws())
        assert entries == []

    def test_header_content_produces_no_warnings(self):
        _, warnings = parse_filesystem(_ws())
        assert warnings == []


# ---------------------------------------------------------------------------
# Blank row terminates parsing
# ---------------------------------------------------------------------------

class TestBlankRowTermination:
    def test_blank_row_stops_reading(self):
        rows = [
            _row(hostname="ph_first"),
            _blank(),
            _row(hostname="ph_after_blank"),
        ]
        entries, _ = parse_filesystem(_ws(*rows))
        hostnames = [e["hostname"] for e in entries]
        assert "ph_first" in hostnames
        assert "ph_after_blank" not in hostnames

    def test_sheet_with_only_blank_data_row_returns_empty(self):
        entries, _ = parse_filesystem(_ws(_blank()))
        assert entries == []


# ---------------------------------------------------------------------------
# All data rows included (no entry_type filter)
# ---------------------------------------------------------------------------

class TestAllRowsIncluded:
    def test_multiple_rows_all_included(self):
        rows = [
            _row(hostname="ph01", mount_point="/"),
            _row(hostname="ph01", mount_point="/usr/sap"),
            _row(hostname="ph02", mount_point="/"),
        ]
        entries, _ = parse_filesystem(_ws(*rows))
        assert len(entries) == 3

    def test_single_row_included(self):
        entries, _ = parse_filesystem(_ws(_row()))
        assert len(entries) == 1


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------

class TestFieldMapping:
    def setup_method(self):
        self.entry = parse_filesystem(_ws(_row(
            seq_no=3,
            landscape="PRD",
            sid="EXP",
            server_type="AP",
            fs_category_1="APP",
            fs_category_2="data",
            sla_tier="Gold",
            ha_flag="O",
            fs_count_max=2,
            fs_seq_in_host=1,
            hostname="phexample01",
            admin_ip="10.1.0.1",
            mount_point="/usr/sap/EXP",
            size_gb=128,
            fs_type="xfs",
            vg_name="vg_sap",
            nfs_group="nfs_grp_01",
            remark="primary app disk",
            check="OK",
        )))[0][0]

    def test_seq_no(self):
        assert self.entry["seq_no"] == 3

    def test_landscape(self):
        assert self.entry["landscape"] == "PRD"

    def test_sid(self):
        assert self.entry["sid"] == "EXP"

    def test_server_type(self):
        assert self.entry["server_type"] == "AP"

    def test_fs_category_1(self):
        assert self.entry["fs_category_1"] == "APP"

    def test_fs_category_2(self):
        assert self.entry["fs_category_2"] == "data"

    def test_sla_tier(self):
        assert self.entry["sla_tier"] == "Gold"

    def test_ha_flag_O_is_true(self):
        assert self.entry["ha_flag"] is True

    def test_fs_count_max(self):
        assert self.entry["fs_count_max"] == 2

    def test_fs_seq_in_host(self):
        assert self.entry["fs_seq_in_host"] == 1

    def test_hostname(self):
        assert self.entry["hostname"] == "phexample01"

    def test_admin_ip(self):
        assert self.entry["admin_ip"] == "10.1.0.1"

    def test_mount_point(self):
        assert self.entry["mount_point"] == "/usr/sap/EXP"

    def test_size_gb(self):
        assert self.entry["size_gb"] == 128

    def test_size_formula_none_when_integer(self):
        assert self.entry["size_formula"] is None

    def test_fs_type(self):
        assert self.entry["fs_type"] == "xfs"

    def test_vg_name(self):
        assert self.entry["vg_name"] == "vg_sap"

    def test_nfs_group(self):
        assert self.entry["nfs_group"] == "nfs_grp_01"

    def test_remark(self):
        assert self.entry["remark"] == "primary app disk"

    def test_check(self):
        assert self.entry["check"] == "OK"


# ---------------------------------------------------------------------------
# ha_flag boolean normalization
# ---------------------------------------------------------------------------

class TestHaFlag:
    def test_ha_O_is_true(self):
        entry = parse_filesystem(_ws(_row(ha_flag="O")))[0][0]
        assert entry["ha_flag"] is True

    def test_ha_X_is_false(self):
        entry = parse_filesystem(_ws(_row(ha_flag="X")))[0][0]
        assert entry["ha_flag"] is False

    def test_ha_none_is_false(self):
        entry = parse_filesystem(_ws(_row(ha_flag=None)))[0][0]
        assert entry["ha_flag"] is False

    def test_ha_lowercase_o_is_true(self):
        entry = parse_filesystem(_ws(_row(ha_flag="o")))[0][0]
        assert entry["ha_flag"] is True


# ---------------------------------------------------------------------------
# size_gb / size_formula anomaly handling
# ---------------------------------------------------------------------------

class TestSizeAnomaly:
    def test_integer_size_stored_as_size_gb(self):
        entry = parse_filesystem(_ws(_row(size_gb=256)))[0][0]
        assert entry["size_gb"] == 256
        assert entry["size_formula"] is None

    def test_none_size_stored_as_none(self):
        entry = parse_filesystem(_ws(_row(size_gb=None)))[0][0]
        assert entry["size_gb"] is None
        assert entry["size_formula"] is None

    def test_formula_string_min_expression(self):
        entry = parse_filesystem(_ws(_row(size_gb="MIN(256,1024)")))[0][0]
        assert entry["size_gb"] is None
        assert entry["size_formula"] == "MIN(256,1024)"

    def test_formula_string_multiplication_expression(self):
        entry = parse_filesystem(_ws(_row(size_gb="1.5*256")))[0][0]
        assert entry["size_gb"] is None
        assert entry["size_formula"] == "1.5*256"

    def test_float_treated_as_formula(self):
        # Floats are not plain integers; store as formula string
        entry = parse_filesystem(_ws(_row(size_gb=384.5)))[0][0]
        assert entry["size_gb"] is None
        assert entry["size_formula"] == "384.5"

    def test_zero_integer_is_valid_size(self):
        entry = parse_filesystem(_ws(_row(size_gb=0)))[0][0]
        assert entry["size_gb"] == 0
        assert entry["size_formula"] is None
