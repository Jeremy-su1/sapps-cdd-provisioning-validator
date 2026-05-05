"""Tests for src/planner/vmware_planner.py — dry-run VMware action planning."""
import pytest
from src.planner.vmware_planner import plan_vmware, VmwarePlanResult


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _vm(
    vhost="vhexample01",
    phost="phexample01",
    landscape="PRD",
    sid="TST",
    role_type="AP",
    os_version="RHEL 9.4",
    cpu_vcores=8,
    memory_gb=32,
    appl_storage_gb=100,
    service_ip="10.0.0.11",
    admin_ip="10.1.0.11",
    ha=True,
    dr=False,
    backup_enabled=True,
    host_no="01",
):
    return {
        "identity": {
            "vhost":         vhost,
            "phost":         phost,
            "landscape":     landscape,
            "sid":           sid,
            "role_type":     role_type,
            "main_solution": "S/4HANA",
        },
        "compute": {
            "os_version":      os_version,
            "cpu_vcores":      cpu_vcores,
            "memory_gb":       memory_gb,
            "appl_storage_gb": appl_storage_gb,
            "nfs_storage_gb":  None,
            "scp_image":       None,
        },
        "network": {
            "service_hostname": vhost,
            "service_ip":       service_ip,
            "admin_hostname":   phost,
            "admin_ip":         admin_ip,
            "admin_nat_ip":     None,
            "backup_hostname":  None,
            "backup_ip":        None,
            "sr_dr_ip":         None,
            "internode_ip":     None,
            "hb_ip":            None,
        },
        "availability": {
            "sla":            "99.9%",
            "ha":             ha,
            "dr":             dr,
            "pacemaker":      False,
            "db_sr":          False,
            "hana_haf":       False,
            "backup_enabled": backup_enabled,
        },
        "metadata": {
            "phase":            1,
            "entry_type":       "server",
            "role_description": "PAS#01",
            "host_no":          host_no,
            "vm_or_bm":         "VM",
        },
    }


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:
    def test_returns_vmware_plan_result(self):
        result = plan_vmware([], None)
        assert isinstance(result, VmwarePlanResult)

    def test_has_actions(self):
        result = plan_vmware([], None)
        assert isinstance(result.actions, list)

    def test_has_conflicts(self):
        result = plan_vmware([], None)
        assert isinstance(result.conflicts, list)

    def test_has_summary(self):
        result = plan_vmware([], None)
        assert isinstance(result.summary, dict)

    def test_summary_has_action_counts(self):
        result = plan_vmware([], None)
        for key in ("create", "update", "skip", "conflict"):
            assert key in result.summary

    def test_empty_desired_returns_empty(self):
        result = plan_vmware([], None)
        assert result.actions == []
        assert result.conflicts == []
        assert result.summary["create"] == 0


# ---------------------------------------------------------------------------
# No actual state → create
# ---------------------------------------------------------------------------

class TestCreateActions:
    def test_single_vm_no_actual_is_create(self):
        result = plan_vmware([_vm()], None)
        assert len(result.actions) == 1
        assert result.actions[0]["action"] == "create"

    def test_multiple_vms_no_actual_all_create(self):
        vms = [_vm(vhost=f"vhtest{i:02d}", phost=f"phtest{i:02d}") for i in range(3)]
        result = plan_vmware(vms, None)
        assert all(a["action"] == "create" for a in result.actions)

    def test_create_action_resource_type(self):
        result = plan_vmware([_vm()], None)
        assert result.actions[0]["resource_type"] == "vmware_vm"

    def test_create_action_resource_id_is_vhost(self):
        result = plan_vmware([_vm(vhost="vhspecial01")], None)
        assert result.actions[0]["resource_id"] == "vhspecial01"

    def test_create_action_has_desired(self):
        result = plan_vmware([_vm()], None)
        assert "desired" in result.actions[0]

    def test_create_action_actual_is_none(self):
        result = plan_vmware([_vm()], None)
        assert result.actions[0]["actual"] is None

    def test_summary_create_count_correct(self):
        vms = [_vm(vhost=f"vhtest{i:02d}", phost=f"phtest{i:02d}") for i in range(4)]
        result = plan_vmware(vms, None)
        assert result.summary["create"] == 4


# ---------------------------------------------------------------------------
# Matching actual state → skip
# ---------------------------------------------------------------------------

class TestSkipActions:
    def test_vm_matching_actual_is_skip(self):
        vm = _vm()
        actual = [{"vhost": "vhexample01", "cpu_vcores": 8, "memory_gb": 32}]
        result = plan_vmware([vm], actual)
        assert result.actions[0]["action"] == "skip"

    def test_skip_has_resource_id(self):
        vm = _vm(vhost="vhskip01")
        actual = [{"vhost": "vhskip01", "cpu_vcores": 8, "memory_gb": 32}]
        result = plan_vmware([vm], actual)
        assert result.actions[0]["resource_id"] == "vhskip01"

    def test_summary_skip_count(self):
        vms = [_vm(vhost=f"vhtest{i:02d}", phost=f"phtest{i:02d}") for i in range(2)]
        actual = [{"vhost": "vhtest00"}, {"vhost": "vhtest01"}]
        result = plan_vmware(vms, actual)
        assert result.summary["skip"] == 2


# ---------------------------------------------------------------------------
# Diverged actual state → update
# ---------------------------------------------------------------------------

class TestUpdateActions:
    def test_vm_with_changed_cpu_is_update(self):
        vm = _vm(cpu_vcores=16)
        actual = [{"vhost": "vhexample01", "cpu_vcores": 8, "memory_gb": 32}]
        result = plan_vmware([vm], actual)
        assert result.actions[0]["action"] == "update"

    def test_update_has_diff(self):
        vm = _vm(cpu_vcores=16)
        actual = [{"vhost": "vhexample01", "cpu_vcores": 8, "memory_gb": 32}]
        result = plan_vmware([vm], actual)
        assert "diff" in result.actions[0]

    def test_update_diff_shows_changed_fields(self):
        vm = _vm(cpu_vcores=16)
        actual = [{"vhost": "vhexample01", "cpu_vcores": 8, "memory_gb": 32}]
        result = plan_vmware([vm], actual)
        diff = result.actions[0]["diff"]
        assert "cpu_vcores" in diff

    def test_summary_update_count(self):
        vm = _vm(cpu_vcores=32)
        actual = [{"vhost": "vhexample01", "cpu_vcores": 8}]
        result = plan_vmware([vm], actual)
        assert result.summary["update"] == 1


# ---------------------------------------------------------------------------
# Placeholder IP values → conflict
# ---------------------------------------------------------------------------

class TestPlaceholderConflicts:
    def _plan_with_ip(self, admin_ip):
        vm = _vm(admin_ip=admin_ip)
        return plan_vmware([vm], None)

    def test_integer_zero_admin_ip_is_conflict(self):
        result = self._plan_with_ip(0)
        assert len(result.conflicts) == 1
        assert result.conflicts[0]["action"] == "conflict"

    def test_integer_one_admin_ip_is_conflict(self):
        result = self._plan_with_ip(1)
        assert len(result.conflicts) == 1

    def test_string_zero_admin_ip_is_conflict(self):
        result = self._plan_with_ip("0")
        assert len(result.conflicts) == 1

    def test_string_two_admin_ip_is_conflict(self):
        result = self._plan_with_ip("2")
        assert len(result.conflicts) == 1

    def test_dash_admin_ip_is_conflict(self):
        result = self._plan_with_ip("-")
        assert len(result.conflicts) == 1

    def test_conflict_resource_id_is_vhost(self):
        result = self._plan_with_ip(0)
        assert result.conflicts[0]["resource_id"] == "vhexample01"

    def test_conflict_has_reason(self):
        result = self._plan_with_ip(0)
        assert "reason" in result.conflicts[0]

    def test_conflict_not_in_actions(self):
        result = self._plan_with_ip(0)
        assert result.actions == []

    def test_summary_conflict_count(self):
        vms = [_vm(vhost=f"vhtest{i:02d}", phost=f"phtest{i:02d}", admin_ip=0) for i in range(3)]
        result = plan_vmware(vms, None)
        assert result.summary["conflict"] == 3

    def test_valid_ip_is_not_conflict(self):
        result = self._plan_with_ip("10.1.0.11")
        assert result.conflicts == []

    def test_requires_approval_true_for_conflicts(self):
        result = self._plan_with_ip(0)
        assert result.conflicts[0]["requires_approval"] is True

    def test_conflict_reason_is_placeholder_ip(self):
        result = self._plan_with_ip(0)
        assert result.conflicts[0]["conflict_reason"] == "placeholder_ip"

    def test_conflict_reason_placeholder_ip_for_dash(self):
        result = self._plan_with_ip("-")
        assert result.conflicts[0]["conflict_reason"] == "placeholder_ip"


# ---------------------------------------------------------------------------
# Missing required fields → conflict
# ---------------------------------------------------------------------------

class TestMissingRequiredFields:
    def test_empty_vhost_is_conflict(self):
        vm = _vm(vhost="")
        result = plan_vmware([vm], None)
        assert len(result.conflicts) == 1

    def test_none_phost_is_conflict(self):
        vm = _vm()
        vm["identity"]["phost"] = None
        result = plan_vmware([vm], None)
        assert len(result.conflicts) == 1

    def test_none_os_version_is_conflict(self):
        vm = _vm()
        vm["compute"]["os_version"] = None
        result = plan_vmware([vm], None)
        assert len(result.conflicts) == 1

    def test_none_cpu_vcores_is_conflict(self):
        vm = _vm()
        vm["compute"]["cpu_vcores"] = None
        result = plan_vmware([vm], None)
        assert len(result.conflicts) == 1

    def test_none_memory_gb_is_conflict(self):
        vm = _vm()
        vm["compute"]["memory_gb"] = None
        result = plan_vmware([vm], None)
        assert len(result.conflicts) == 1

    def test_conflict_reason_is_missing_required_field(self):
        vm = _vm()
        vm["compute"]["cpu_vcores"] = None
        result = plan_vmware([vm], None)
        assert result.conflicts[0]["conflict_reason"] == "missing_required_field"

    def test_conflict_reason_missing_field_for_empty_vhost(self):
        vm = _vm(vhost="")
        result = plan_vmware([vm], None)
        assert result.conflicts[0]["conflict_reason"] == "missing_required_field"


# ---------------------------------------------------------------------------
# Ordering: PRD > DR > QAS > DEV, then host_no ascending
# ---------------------------------------------------------------------------

class TestOrdering:
    def test_prd_before_dev(self):
        vms = [
            _vm(vhost="vhdev01",  phost="phdev01",  landscape="DEV", host_no="01"),
            _vm(vhost="vhprd01",  phost="phprd01",  landscape="PRD", host_no="01"),
        ]
        result = plan_vmware(vms, None)
        ids = [a["resource_id"] for a in result.actions]
        assert ids.index("vhprd01") < ids.index("vhdev01")

    def test_prd_before_dr_before_qas_before_dev(self):
        vms = [
            _vm(vhost="vhdev01",  landscape="DEV"),
            _vm(vhost="vhqas01",  landscape="QAS"),
            _vm(vhost="vhdr01",   landscape="DR"),
            _vm(vhost="vhprd01",  landscape="PRD"),
        ]
        result = plan_vmware(vms, None)
        ids = [a["resource_id"] for a in result.actions]
        assert ids == ["vhprd01", "vhdr01", "vhqas01", "vhdev01"]

    def test_same_landscape_ordered_by_host_no(self):
        vms = [
            _vm(vhost="vhprd03", landscape="PRD", host_no="03"),
            _vm(vhost="vhprd01", landscape="PRD", host_no="01"),
            _vm(vhost="vhprd02", landscape="PRD", host_no="02"),
        ]
        result = plan_vmware(vms, None)
        ids = [a["resource_id"] for a in result.actions]
        assert ids == ["vhprd01", "vhprd02", "vhprd03"]

    def test_conflicts_excluded_from_ordered_actions(self):
        vms = [
            _vm(vhost="vhprd01", landscape="PRD", admin_ip=0),    # conflict
            _vm(vhost="vhprd02", landscape="PRD", admin_ip="10.1.0.11"),  # create
        ]
        result = plan_vmware(vms, None)
        assert len(result.actions) == 1
        assert result.actions[0]["resource_id"] == "vhprd02"
        assert len(result.conflicts) == 1
