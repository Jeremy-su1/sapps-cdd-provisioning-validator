"""Tests for src/schema/issues.py — DataQualityIssue model."""
import pytest
from src.schema.issues import DataQualityIssue


class TestDataQualityIssueFields:
    def _make(self, **overrides):
        defaults = dict(
            issue_type="placeholder_ip",
            severity="error",
            resource="vmware_vm",
            resource_id="vhexample01",
            field="admin_ip",
            raw_value="0",
            message="admin_ip is a placeholder value",
        )
        defaults.update(overrides)
        return DataQualityIssue(**defaults)

    def test_stores_issue_type(self):
        assert self._make().issue_type == "placeholder_ip"

    def test_stores_severity(self):
        assert self._make().severity == "error"

    def test_stores_resource(self):
        assert self._make().resource == "vmware_vm"

    def test_stores_resource_id(self):
        assert self._make().resource_id == "vhexample01"

    def test_stores_field(self):
        assert self._make().field == "admin_ip"

    def test_stores_raw_value(self):
        assert self._make().raw_value == "0"

    def test_stores_message(self):
        assert self._make().message == "admin_ip is a placeholder value"

    def test_field_may_be_none(self):
        issue = self._make(field=None)
        assert issue.field is None

    def test_raw_value_may_be_none(self):
        issue = self._make(raw_value=None)
        assert issue.raw_value is None


class TestToDict:
    def _issue(self, **overrides):
        defaults = dict(
            issue_type="missing_required_field",
            severity="error",
            resource="vmware_vm",
            resource_id="vhexample02",
            field="phost",
            raw_value=None,
            message="phost is required but empty",
        )
        defaults.update(overrides)
        return DataQualityIssue(**defaults).to_dict()

    def test_has_issue_type(self):
        assert "issue_type" in self._issue()

    def test_has_severity(self):
        assert "severity" in self._issue()

    def test_has_resource(self):
        assert "resource" in self._issue()

    def test_has_resource_id(self):
        assert "resource_id" in self._issue()

    def test_has_field(self):
        assert "field" in self._issue()

    def test_has_raw_value(self):
        assert "raw_value" in self._issue()

    def test_has_message(self):
        assert "message" in self._issue()

    def test_none_raw_value_stays_none(self):
        assert self._issue(raw_value=None)["raw_value"] is None

    def test_string_raw_value_preserved(self):
        assert self._issue(raw_value="0")["raw_value"] == "0"

    def test_integer_raw_value_serialized_to_string(self):
        # Raw values come from Excel cells — may be integers
        assert self._issue(raw_value=0)["raw_value"] == "0"

    def test_values_match_constructor(self):
        d = self._issue(
            issue_type="malformed_cidr",
            severity="warning",
            resource="subnet",
            resource_id="10.x.x.x/2",
            field="ip_range",
            raw_value="192.167.16.128/2",
            message="host bits set",
        )
        assert d["issue_type"] == "malformed_cidr"
        assert d["severity"] == "warning"
        assert d["resource"] == "subnet"
        assert d["resource_id"] == "10.x.x.x/2"
        assert d["field"] == "ip_range"
        assert d["raw_value"] == "192.167.16.128/2"
        assert d["message"] == "host bits set"


class TestIssueTypes:
    """Smoke-test every documented issue_type — ensures spelling is locked."""

    def _make(self, issue_type):
        return DataQualityIssue(
            issue_type=issue_type,
            severity="warning",
            resource="vmware_vm",
            resource_id="x",
            field=None,
            raw_value=None,
            message="test",
        )

    def test_placeholder_ip(self):
        assert self._make("placeholder_ip").issue_type == "placeholder_ip"

    def test_malformed_cidr(self):
        assert self._make("malformed_cidr").issue_type == "malformed_cidr"

    def test_unresolved_endpoint(self):
        assert self._make("unresolved_endpoint").issue_type == "unresolved_endpoint"

    def test_unmatched_filesystem(self):
        assert self._make("unmatched_filesystem").issue_type == "unmatched_filesystem"

    def test_missing_required_field(self):
        assert self._make("missing_required_field").issue_type == "missing_required_field"

    def test_duplicate_resource_id(self):
        assert self._make("duplicate_resource_id").issue_type == "duplicate_resource_id"
