"""Tests for src/planner/dfw_planner.py — dry-run NSX-T DFW action planning."""
import pytest
from src.planner.dfw_planner import plan_dfw, DfwPlanResult


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _candidate(
    rule_id="rule-001",
    rule_name="allow-app-to-db",
    src_hostname="vhapp01",
    src_ip="10.0.1.11",
    dst_hostname="vhdb01",
    dst_ip="10.0.1.21",
    protocol="TCP",
    port="1521",
    port_expression=False,
    action="permit",
    applied_to="source",
    requires_manual_review=False,
):
    return {
        "rule_id":               rule_id,
        "rule_name":             rule_name,
        "src_hostname":          src_hostname,
        "src_ip":                src_ip,
        "dst_hostname":          dst_hostname,
        "dst_ip":                dst_ip,
        "protocol":              protocol,
        "port":                  port,
        "port_expression":       port_expression,
        "action":                action,
        "applied_to":            applied_to,
        "requires_manual_review": requires_manual_review,
    }


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:
    def test_returns_dfw_plan_result(self):
        result = plan_dfw([], None)
        assert isinstance(result, DfwPlanResult)

    def test_has_actions(self):
        result = plan_dfw([], None)
        assert isinstance(result.actions, list)

    def test_has_conflicts(self):
        result = plan_dfw([], None)
        assert isinstance(result.conflicts, list)

    def test_has_summary(self):
        result = plan_dfw([], None)
        assert isinstance(result.summary, dict)

    def test_summary_keys(self):
        result = plan_dfw([], None)
        for key in ("create", "skip", "conflict"):
            assert key in result.summary

    def test_empty_candidates_returns_empty(self):
        result = plan_dfw([], None)
        assert result.actions == []
        assert result.conflicts == []


# ---------------------------------------------------------------------------
# No actual state → create
# ---------------------------------------------------------------------------

class TestCreateActions:
    def test_single_candidate_no_actual_is_create(self):
        result = plan_dfw([_candidate()], None)
        assert len(result.actions) == 1
        assert result.actions[0]["action"] == "create"

    def test_create_resource_type(self):
        result = plan_dfw([_candidate()], None)
        assert result.actions[0]["resource_type"] == "nsxt_dfw_rule"

    def test_create_resource_id_is_rule_id(self):
        result = plan_dfw([_candidate(rule_id="rule-999")], None)
        assert result.actions[0]["resource_id"] == "rule-999"

    def test_create_has_desired(self):
        result = plan_dfw([_candidate()], None)
        assert "desired" in result.actions[0]

    def test_create_actual_is_none(self):
        result = plan_dfw([_candidate()], None)
        assert result.actions[0]["actual"] is None

    def test_summary_create_count(self):
        candidates = [_candidate(rule_id=f"rule-{i:03d}") for i in range(3)]
        result = plan_dfw(candidates, None)
        assert result.summary["create"] == 3


# ---------------------------------------------------------------------------
# Matching actual state → skip
# ---------------------------------------------------------------------------

class TestSkipActions:
    def test_matching_actual_is_skip(self):
        c = _candidate()
        actual = [{"rule_id": "rule-001", "action": "permit", "port": "1521"}]
        result = plan_dfw([c], actual)
        assert result.actions[0]["action"] == "skip"

    def test_skip_resource_id(self):
        c = _candidate(rule_id="rule-042")
        actual = [{"rule_id": "rule-042", "action": "permit", "port": "1521"}]
        result = plan_dfw([c], actual)
        assert result.actions[0]["resource_id"] == "rule-042"

    def test_summary_skip_count(self):
        candidates = [_candidate(rule_id=f"rule-{i:03d}") for i in range(2)]
        actual = [{"rule_id": "rule-000"}, {"rule_id": "rule-001"}]
        result = plan_dfw(candidates, actual)
        assert result.summary["skip"] == 2


# ---------------------------------------------------------------------------
# requires_manual_review=True → conflict
# ---------------------------------------------------------------------------

class TestManualReviewConflicts:
    def test_requires_manual_review_is_conflict(self):
        c = _candidate(requires_manual_review=True)
        result = plan_dfw([c], None)
        assert len(result.conflicts) == 1
        assert result.conflicts[0]["action"] == "conflict"

    def test_conflict_resource_type(self):
        c = _candidate(requires_manual_review=True)
        result = plan_dfw([c], None)
        assert result.conflicts[0]["resource_type"] == "nsxt_dfw_rule"

    def test_conflict_resource_id(self):
        c = _candidate(rule_id="rule-rev", requires_manual_review=True)
        result = plan_dfw([c], None)
        assert result.conflicts[0]["resource_id"] == "rule-rev"

    def test_conflict_requires_approval(self):
        c = _candidate(requires_manual_review=True)
        result = plan_dfw([c], None)
        assert result.conflicts[0]["requires_approval"] is True

    def test_conflict_has_reason(self):
        c = _candidate(requires_manual_review=True)
        result = plan_dfw([c], None)
        assert result.conflicts[0]["reason"]

    def test_conflict_reason_is_manual_review(self):
        c = _candidate(requires_manual_review=True)
        result = plan_dfw([c], None)
        assert result.conflicts[0]["conflict_reason"] == "requires_manual_review"

    def test_manual_review_not_in_actions(self):
        c = _candidate(requires_manual_review=True)
        result = plan_dfw([c], None)
        assert result.actions == []

    def test_summary_conflict_count(self):
        candidates = [
            _candidate(rule_id="rule-001", requires_manual_review=True),
            _candidate(rule_id="rule-002", requires_manual_review=True),
        ]
        result = plan_dfw(candidates, None)
        assert result.summary["conflict"] == 2

    def test_mixed_review_and_clean(self):
        candidates = [
            _candidate(rule_id="rule-001", requires_manual_review=True),
            _candidate(rule_id="rule-002", requires_manual_review=False),
        ]
        result = plan_dfw(candidates, None)
        assert result.summary["conflict"] == 1
        assert result.summary["create"] == 1


# ---------------------------------------------------------------------------
# Action item structure
# ---------------------------------------------------------------------------

class TestActionItemStructure:
    def test_create_item_has_required_keys(self):
        result = plan_dfw([_candidate()], None)
        item = result.actions[0]
        for key in ("action", "resource_type", "resource_id", "desired", "actual", "requires_approval"):
            assert key in item

    def test_create_requires_approval_false(self):
        result = plan_dfw([_candidate()], None)
        assert result.actions[0]["requires_approval"] is False

    def test_conflict_item_has_required_keys(self):
        c = _candidate(requires_manual_review=True)
        result = plan_dfw([c], None)
        item = result.conflicts[0]
        for key in ("action", "resource_type", "resource_id", "desired", "actual", "reason", "conflict_reason", "requires_approval"):
            assert key in item
