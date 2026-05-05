"""Tests for src/parser/serverinfo.py — written before implementation."""
import pytest
from src.parser.serverinfo import parse_serverinfo

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_N_COLS = 43

# Three header rows the parser must skip (annotation + 2 header rows)
_HDR1 = tuple([None] * _N_COLS)
_HDR2 = ("Phase", "vhost", "phost", "Landscape", "SID", "Type", "Main Solution",
          "SID Cate. I", "SID Cate. II", "Type II", "Role", "Host No.",
          "Type (VM/BM)", "CDD", "SCP Image", "OS Version",
          "Resource", None, "Storage", None,
          "Service", None, "Admin", None, None,
          "Backup", None, "SR/DR", "Inter-node", "HB",
          "SLA", "HA", "DR", "Pacemaker", "DB SR", "HANA HAF", "Backup",
          "SIEM", "SOAR", "VA", "Ahnlab EDR", "Anti Virus", "CSPM")
_HDR3 = tuple([None] * _N_COLS)
_HEADERS = (_HDR1, _HDR2, _HDR3)


def _blank():
    return tuple([None] * _N_COLS)


def _row(
    phase=1,
    vhost="vhexample01",
    phost_raw="phexample01",      # phost_raw col 2
    landscape="PRD",
    sid="EXP",
    role_type="AP",
    main_solution="S/4HANA",
    sid_cat1="S/4HANA",
    sid_cat2="APP",
    entry_type="server",
    role_desc="PAS#01",
    host_no="01",
    vm_or_bm="VM",
    cdd_date=None,
    scp_image=None,
    os_version="RHEL 9.4",
    cpu=8,
    mem_gb=32,
    appl_gb=100,
    nfs="N/A",
    svc_hostname="vhexample01",
    svc_ip="10.0.0.1",
    adm_hostname="phexample01",
    adm_ip="10.1.0.1",
    adm_nat_ip="192.168.0.1",
    bk_hostname=None,
    bk_ip=None,
    sr_dr_ip=None,
    internode_ip=None,
    hb_ip=None,
    sla="95.00%",
    ha="O",
    dr="X",
    pacemaker="O",
    db_sr=None,
    hana_haf=None,
    backup_enabled="O",
    siem="O",
    soar="O",
    va="O",
    edr="O",
    antivirus="O",
    cspm="O",
):
    r = [None] * _N_COLS
    r[0]  = phase
    r[1]  = vhost
    r[2]  = phost_raw
    r[3]  = landscape
    r[4]  = sid
    r[5]  = role_type
    r[6]  = main_solution
    r[7]  = sid_cat1
    r[8]  = sid_cat2
    r[9]  = entry_type
    r[10] = role_desc
    r[11] = host_no
    r[12] = vm_or_bm
    r[13] = cdd_date
    r[14] = scp_image
    r[15] = os_version
    r[16] = cpu
    r[17] = mem_gb
    r[18] = appl_gb
    r[19] = nfs
    r[20] = svc_hostname
    r[21] = svc_ip
    r[22] = adm_hostname
    r[23] = adm_ip
    r[24] = adm_nat_ip
    r[25] = bk_hostname
    r[26] = bk_ip
    r[27] = sr_dr_ip
    r[28] = internode_ip
    r[29] = hb_ip
    r[30] = sla
    r[31] = ha
    r[32] = dr
    r[33] = pacemaker
    r[34] = db_sr
    r[35] = hana_haf
    r[36] = backup_enabled
    r[37] = siem
    r[38] = soar
    r[39] = va
    r[40] = edr
    r[41] = antivirus
    r[42] = cspm
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
        result = parse_serverinfo(_ws())
        assert isinstance(result, tuple) and len(result) == 2

    def test_first_element_is_list(self):
        vms, _ = parse_serverinfo(_ws())
        assert isinstance(vms, list)

    def test_second_element_is_list(self):
        _, warnings = parse_serverinfo(_ws())
        assert isinstance(warnings, list)

    def test_empty_sheet_returns_empty_list(self):
        vms, warnings = parse_serverinfo(_ws())
        assert vms == []
        assert warnings == []


# ---------------------------------------------------------------------------
# entry_type filter
# ---------------------------------------------------------------------------

class TestEntryTypeFilter:
    def test_server_row_is_included(self):
        vms, _ = parse_serverinfo(_ws(_row(entry_type="server")))
        assert len(vms) == 1

    def test_vip_row_is_excluded(self):
        vms, _ = parse_serverinfo(_ws(_row(entry_type="vip")))
        assert vms == []

    def test_lb_row_is_excluded(self):
        vms, _ = parse_serverinfo(_ws(_row(entry_type="lb")))
        assert vms == []

    def test_mixed_rows_only_server_included(self):
        rows = [
            _row(entry_type="vip", vhost="vhvip"),
            _row(entry_type="server", vhost="vhsrv"),
            _row(entry_type="lb",  vhost="vhlb"),
        ]
        vms, _ = parse_serverinfo(_ws(*rows))
        assert len(vms) == 1
        assert vms[0]["identity"]["vhost"] == "vhsrv"

    def test_multiple_server_rows_all_included(self):
        rows = [
            _row(vhost="vhexample01", adm_ip="10.1.0.1"),
            _row(vhost="vhexample02", adm_ip="10.1.0.2"),
        ]
        vms, _ = parse_serverinfo(_ws(*rows))
        assert len(vms) == 2


# ---------------------------------------------------------------------------
# Identity section
# ---------------------------------------------------------------------------

class TestIdentitySection:
    def setup_method(self):
        self.vm, *_ = parse_serverinfo(_ws(_row(
            vhost="vhexampleap01",
            phost_raw="phexampleap0110.1.0.11",   # concatenated
            landscape="PRD",
            sid="EXP",
            role_type="AP",
            main_solution="S/4HANA",
            adm_ip="10.1.0.11",
        )))[0]

    def test_vhost(self):
        assert self.vm["identity"]["vhost"] == "vhexampleap01"

    def test_phost_stripped_of_ip(self):
        # phost_raw = "phexampleap0110.1.0.11", admin_ip = "10.1.0.11"
        # split_phost(known_ip) strips the IP suffix exactly
        assert self.vm["identity"]["phost"] == "phexampleap01"

    def test_landscape(self):
        assert self.vm["identity"]["landscape"] == "PRD"

    def test_sid(self):
        assert self.vm["identity"]["sid"] == "EXP"

    def test_role_type(self):
        assert self.vm["identity"]["role_type"] == "AP"

    def test_main_solution(self):
        assert self.vm["identity"]["main_solution"] == "S/4HANA"


# ---------------------------------------------------------------------------
# Compute section
# ---------------------------------------------------------------------------

class TestComputeSection:
    def setup_method(self):
        self.vm, *_ = parse_serverinfo(_ws(_row(
            os_version="RHEL 9.4",
            cpu=16,
            mem_gb=64,
            appl_gb=180,
            nfs="N/A",
            scp_image="RHEL9-GI",
        )))[0]

    def test_os_version(self):
        assert self.vm["compute"]["os_version"] == "RHEL 9.4"

    def test_cpu_vcores(self):
        assert self.vm["compute"]["cpu_vcores"] == 16

    def test_memory_gb(self):
        assert self.vm["compute"]["memory_gb"] == 64

    def test_appl_storage_gb(self):
        assert self.vm["compute"]["appl_storage_gb"] == 180

    def test_nfs_storage_na_becomes_none(self):
        assert self.vm["compute"]["nfs_storage_gb"] is None

    def test_scp_image(self):
        assert self.vm["compute"]["scp_image"] == "RHEL9-GI"


class TestComputeNfsVariants:
    def test_nfs_integer_value_preserved(self):
        vm = parse_serverinfo(_ws(_row(nfs=512)))[0][0]
        assert vm["compute"]["nfs_storage_gb"] == 512

    def test_nfs_none_becomes_none(self):
        vm = parse_serverinfo(_ws(_row(nfs=None)))[0][0]
        assert vm["compute"]["nfs_storage_gb"] is None


# ---------------------------------------------------------------------------
# Network section
# ---------------------------------------------------------------------------

class TestNetworkSection:
    def setup_method(self):
        self.vm, *_ = parse_serverinfo(_ws(_row(
            svc_hostname="vhexample01",
            svc_ip="10.0.0.1",
            adm_hostname="phexample01",
            adm_ip="10.1.0.1",
            adm_nat_ip="192.168.0.1",
            bk_hostname="phexample01-bk",
            bk_ip="192.167.0.1",
            sr_dr_ip="192.167.1.1",
            internode_ip=None,
            hb_ip="10.2.0.1",
        )))[0]

    def test_service_hostname(self):
        assert self.vm["network"]["service_hostname"] == "vhexample01"

    def test_service_ip(self):
        assert self.vm["network"]["service_ip"] == "10.0.0.1"

    def test_admin_hostname(self):
        assert self.vm["network"]["admin_hostname"] == "phexample01"

    def test_admin_ip(self):
        assert self.vm["network"]["admin_ip"] == "10.1.0.1"

    def test_admin_nat_ip(self):
        assert self.vm["network"]["admin_nat_ip"] == "192.168.0.1"

    def test_backup_hostname(self):
        assert self.vm["network"]["backup_hostname"] == "phexample01-bk"

    def test_backup_ip(self):
        assert self.vm["network"]["backup_ip"] == "192.167.0.1"

    def test_sr_dr_ip(self):
        assert self.vm["network"]["sr_dr_ip"] == "192.167.1.1"

    def test_internode_ip_none(self):
        assert self.vm["network"]["internode_ip"] is None

    def test_hb_ip(self):
        assert self.vm["network"]["hb_ip"] == "10.2.0.1"


# ---------------------------------------------------------------------------
# Availability section — boolean normalization
# ---------------------------------------------------------------------------

class TestAvailabilitySection:
    def setup_method(self):
        self.vm, *_ = parse_serverinfo(_ws(_row(
            sla="99.90%",
            ha="O",
            dr="O",
            pacemaker="O",
            db_sr="X",
            hana_haf=None,
            backup_enabled="O",
        )))[0]

    def test_sla(self):
        assert self.vm["availability"]["sla"] == "99.90%"

    def test_ha_O_is_true(self):
        assert self.vm["availability"]["ha"] is True

    def test_dr_O_is_true(self):
        assert self.vm["availability"]["dr"] is True

    def test_pacemaker_O_is_true(self):
        assert self.vm["availability"]["pacemaker"] is True

    def test_db_sr_X_is_false(self):
        assert self.vm["availability"]["db_sr"] is False

    def test_hana_haf_none_is_false(self):
        assert self.vm["availability"]["hana_haf"] is False

    def test_backup_enabled_O_is_true(self):
        assert self.vm["availability"]["backup_enabled"] is True


# ---------------------------------------------------------------------------
# Metadata section
# ---------------------------------------------------------------------------

class TestMetadataSection:
    def setup_method(self):
        self.vm, *_ = parse_serverinfo(_ws(_row(
            phase=2,
            entry_type="server",
            role_desc="HANA-Primary",
            host_no="01",
            vm_or_bm="VM",
        )))[0]

    def test_phase(self):
        assert self.vm["metadata"]["phase"] == 2

    def test_entry_type(self):
        assert self.vm["metadata"]["entry_type"] == "server"

    def test_role_description(self):
        assert self.vm["metadata"]["role_description"] == "HANA-Primary"

    def test_host_no(self):
        assert self.vm["metadata"]["host_no"] == "01"

    def test_vm_or_bm(self):
        assert self.vm["metadata"]["vm_or_bm"] == "VM"


# ---------------------------------------------------------------------------
# phost resolution — placeholder admin_ip handling
# ---------------------------------------------------------------------------

class TestPhostResolution:
    """Tests for the phost split / admin_hostname fallback logic.

    Rule: admin_ip is used as known_ip only when it is a valid IPv4 (X.X.X.X).
    Placeholder values (0, 1, "0", "1", None) trigger admin_hostname fallback.
    """

    def _phost(self, **kwargs):
        vm = parse_serverinfo(_ws(_row(**kwargs)))[0][0]
        return vm["identity"]["phost"]

    # --- valid IP: existing split behaviour unchanged ---

    def test_valid_ip_strips_concatenated_suffix(self):
        # phost_raw = hostname + IP joined; valid admin_ip → exact suffix strip
        assert self._phost(
            phost_raw="phexampleap0110.1.0.11",
            adm_hostname="phexampleap01",
            adm_ip="10.1.0.11",
        ) == "phexampleap01"

    def test_valid_hostname_ending_in_digits_not_overtrimmed(self):
        # phost_raw is already clean (no IP appended); hostname ends in "01"
        # valid admin_ip path: endswith("10.1.0.11") is False → regex fallback
        # regex finds no IP in a clean hostname → full string returned intact
        assert self._phost(
            phost_raw="phexampleap01",
            adm_hostname="phexampleap01",
            adm_ip="10.1.0.11",
        ) == "phexampleap01"

    # --- integer placeholder 0: leaked into phost_raw, falsy → BUG before fix ---

    def test_integer_zero_admin_ip_uses_admin_hostname(self):
        # admin_ip=0 is falsy; phost_raw has trailing "0" from concatenation
        # BUG: split_phost skips known_ip (falsy), regex finds nothing,
        #      returns raw string "phexampleap010" with leaked "0".
        # FIX: detect 0 as placeholder, use admin_hostname directly.
        assert self._phost(
            phost_raw="phexampleap010",   # "phexampleap01" + placeholder "0"
            adm_hostname="phexampleap01",
            adm_ip=0,
        ) == "phexampleap01"

    def test_string_zero_admin_ip_uses_admin_hostname(self):
        assert self._phost(
            phost_raw="phexampleap010",
            adm_hostname="phexampleap01",
            adm_ip="0",
        ) == "phexampleap01"

    # --- integer placeholder 1: truthy, accidentally strips last char ---

    def test_integer_one_admin_ip_uses_admin_hostname(self):
        # admin_ip=1: truthy, str(1)="1"; phost_raw ends in "1" → split_phost
        # strips it, which may give a correct result only by coincidence.
        # When phost_raw has no appended IP (clean hostname ends in "1"),
        # the trim would corrupt it: "phexampleap01"[:-1] = "phexampleap0".
        # FIX: detect 1 as placeholder, use admin_hostname directly.
        assert self._phost(
            phost_raw="phexampleap01",    # clean hostname, no IP appended
            adm_hostname="phexampleap01",
            adm_ip=1,
        ) == "phexampleap01"

    def test_string_one_admin_ip_uses_admin_hostname(self):
        assert self._phost(
            phost_raw="phexampleap01",
            adm_hostname="phexampleap01",
            adm_ip="1",
        ) == "phexampleap01"

    # --- None admin_ip: no known_ip, use admin_hostname ---

    def test_none_admin_ip_uses_admin_hostname(self):
        assert self._phost(
            phost_raw="phexampleap01",
            adm_hostname="phexampleap01",
            adm_ip=None,
        ) == "phexampleap01"

    # --- admin_hostname also absent: last-resort regex on phost_raw ---

    def test_no_admin_ip_no_admin_hostname_regex_fallback(self):
        # Neither admin_ip nor admin_hostname available → regex on phost_raw
        assert self._phost(
            phost_raw="phexamplehost10.1.0.1",  # unambiguous: hostname has no trailing digits
            adm_hostname=None,
            adm_ip=None,
        ) == "phexamplehost"


# ---------------------------------------------------------------------------
# Blank row terminates parsing
# ---------------------------------------------------------------------------

class TestBlankRowTermination:
    def test_blank_row_stops_reading(self):
        rows = [
            _row(vhost="vhfirst"),
            _blank(),
            _row(vhost="vhafter_blank"),   # must NOT appear
        ]
        vms, _ = parse_serverinfo(_ws(*rows))
        vhosts = [v["identity"]["vhost"] for v in vms]
        assert "vhfirst" in vhosts
        assert "vhafter_blank" not in vhosts

    def test_blank_row_among_only_vip_still_stops(self):
        rows = [_row(entry_type="vip"), _blank(), _row(vhost="vhafter")]
        vms, _ = parse_serverinfo(_ws(*rows))
        assert vms == []

    def test_sheet_with_only_blank_data_rows(self):
        vms, _ = parse_serverinfo(_ws(_blank()))
        assert vms == []


# ---------------------------------------------------------------------------
# Header rows are skipped
# ---------------------------------------------------------------------------

class TestHeaderSkip:
    def test_first_three_rows_are_not_parsed_as_data(self):
        # A sheet with exactly the 3 header rows and no data rows
        vms, _ = parse_serverinfo(_ws())
        assert vms == []

    def test_header_content_does_not_cause_warnings(self):
        _, warnings = parse_serverinfo(_ws())
        assert warnings == []
