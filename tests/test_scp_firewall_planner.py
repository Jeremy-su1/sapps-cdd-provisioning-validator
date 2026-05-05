"""Tests for src/planner/scp_firewall_planner.py — dry-run SCP firewall action planning."""
import pytest
from src.planner.scp_firewall_planner import plan_scp_firewall, ScpFirewallPlanResult


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _candidate(
    origin_idx=0,
    source_system="vhapp01",
    source_ip="10.0.1.11",
    target_system="external-service",
    target_ip="203.0.113.10",
    protocol="TCP",
    port="443",
    port_expression=False,
    requires_manual_review=False,
):
    return {
        "origin_idx":             origin_idx,
        "source_system":          source_system,
        "source_ip":              source_ip,
        "source_hostname":        source_system,
        "target_system":          target_system,
        "target_ip":              target_ip,
        "target_hostname":        None,
        "port":                   port,
        "port_expression":        port_expression,
        "protocol":               protocol,
        "expiration":             None,
        "purpose":                "allow outbound HTTPS",
        "requires_manual_review": requires_manual_review,
    }


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:
    def test_returns_scp_firewall_plan_result(self):
        result = plan_scp_firewall([], None)
        assert isinstance(result, ScpFirewallPlanResult)

    def test_has_actions(self):
        result = plan_scp_firewall([], None)
        assert isinstance(result.actions, list)

    def test_has_conflicts(self):
        result = plan_scp_firewall([], None)
        assert isinstance(result.conflicts, list)

    def test_has_summary(self):
        result = plan_scp_firewall([], None)
        assert isinstance(result.summary, dict)

    def test_summary_keys(self):
        result = plan_scp_firewall([], None)
        for key in ("create", "skip", "conflict"):
            assert key in result.summary

    def test_empty_candidates_returns_empty(self):
        result = plan_scp_firewall([], None)
        assert result.actions == []
        assert result.conflicts == []


# ---------------------------------------------------------------------------
# No actual state → create
# ---------------------------------------------------------------------------

class TestCreateActions:
    def test_single_candidate_no_actual_is_create(self):
        result = plan_scp_firewall([_candidate()], None)
        assert len(result.actions) == 1
        assert result.actions[0]["action"] == "create"

    def test_create_resource_type(self):
        result = plan_scp_firewall([_candidate()], None)
        assert result.actions[0]["resource_type"] == "scp_firewall_rule"

    def test_create_resource_id_derived_from_origin_idx(self):
        result = plan_scp_firewall([_candidate(origin_idx=7)], None)
        assert result.actions[0]["resource_id"] == "scp-fw-7"

    def test_create_has_desired(self):
        result = plan_scp_firewall([_candidate()], None)
        assert "desired" in result.actions[0]

    def test_create_actual_is_none(self):
        result = plan_scp_firewall([_candidate()], None)
        assert result.actions[0]["actual"] is None

    def test_create_has_backend_hint(self):
        result = plan_scp_firewall([_candidate()], None)
        assert result.actions[0]["backend_hint"] == "scp"

    def test_create_has_execution_method_candidates(self):
        result = plan_scp_firewall([_candidate()], None)
        assert result.actions[0]["execution_method_candidates"] == ["scp_api", "scp_cli"]

    def test_summary_create_count(self):
        candidates = [_candidate(origin_idx=i) for i in range(4)]
        result = plan_scp_firewall(candidates, None)
        assert result.summary["create"] == 4


# ---------------------------------------------------------------------------
# Matching actual state → skip
# ---------------------------------------------------------------------------

class TestSkipActions:
    def test_matching_actual_is_skip(self):
        c = _candidate(origin_idx=0)
        actual = [{"resource_id": "scp-fw-0", "port": "443", "protocol": "TCP"}]
        result = plan_scp_firewall([c], actual)
        assert result.actions[0]["action"] == "skip"

    def test_skip_resource_id(self):
        c = _candidate(origin_idx=3)
        actual = [{"resource_id": "scp-fw-3"}]
        result = plan_scp_firewall([c], actual)
        assert result.actions[0]["resource_id"] == "scp-fw-3"

    def test_skip_has_backend_hint(self):
        c = _candidate(origin_idx=0)
        actual = [{"resource_id": "scp-fw-0"}]
        result = plan_scp_firewall([c], actual)
        assert result.actions[0]["backend_hint"] == "scp"

    def test_summary_skip_count(self):
        candidates = [_candidate(origin_idx=i) for i in range(2)]
        actual = [{"resource_id": "scp-fw-0"}, {"resource_id": "scp-fw-1"}]
        result = plan_scp_firewall(candidates, actual)
        assert result.summary["skip"] == 2


# ---------------------------------------------------------------------------
# requires_manual_review=True → conflict
# ---------------------------------------------------------------------------

class TestManualReviewConflicts:
    def test_requires_manual_review_is_conflict(self):
        c = _candidate(requires_manual_review=True)
        result = plan_scp_firewall([c], None)
        assert len(result.conflicts) == 1
        assert result.conflicts[0]["action"] == "conflict"

    def test_conflict_resource_type(self):
        c = _candidate(requires_manual_review=True)
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["resource_type"] == "scp_firewall_rule"

    def test_conflict_resource_id(self):
        c = _candidate(origin_idx=5, requires_manual_review=True)
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["resource_id"] == "scp-fw-5"

    def test_conflict_requires_approval(self):
        c = _candidate(requires_manual_review=True)
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["requires_approval"] is True

    def test_conflict_has_reason(self):
        c = _candidate(requires_manual_review=True)
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["reason"]

    def test_conflict_reason_is_requires_manual_review(self):
        c = _candidate(requires_manual_review=True)
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["conflict_reason"] == "requires_manual_review"

    def test_conflict_not_in_actions(self):
        c = _candidate(requires_manual_review=True)
        result = plan_scp_firewall([c], None)
        assert result.actions == []

    def test_summary_conflict_count(self):
        candidates = [
            _candidate(origin_idx=0, requires_manual_review=True),
            _candidate(origin_idx=1, requires_manual_review=True),
        ]
        result = plan_scp_firewall(candidates, None)
        assert result.summary["conflict"] == 2

    def test_mixed_review_and_clean(self):
        candidates = [
            _candidate(origin_idx=0, requires_manual_review=True),
            _candidate(origin_idx=1, requires_manual_review=False),
        ]
        result = plan_scp_firewall(candidates, None)
        assert result.summary["conflict"] == 1
        assert result.summary["create"] == 1


# ---------------------------------------------------------------------------
# Action item structure
# ---------------------------------------------------------------------------

class TestActionItemStructure:
    def test_create_item_has_required_keys(self):
        result = plan_scp_firewall([_candidate()], None)
        item = result.actions[0]
        for key in ("action", "resource_type", "resource_id", "desired", "actual",
                    "requires_approval", "backend_hint", "execution_method_candidates"):
            assert key in item

    def test_create_requires_approval_false(self):
        result = plan_scp_firewall([_candidate()], None)
        assert result.actions[0]["requires_approval"] is False

    def test_conflict_item_has_required_keys(self):
        c = _candidate(requires_manual_review=True)
        result = plan_scp_firewall([c], None)
        item = result.conflicts[0]
        for key in ("action", "resource_type", "resource_id", "desired", "actual",
                    "reason", "conflict_reason", "requires_approval",
                    "backend_hint", "execution_method_candidates"):
            assert key in item


# ---------------------------------------------------------------------------
# Conflict reason taxonomy — derived from enriched endpoint fields
# ---------------------------------------------------------------------------

class TestConflictReasonTaxonomy:
    def test_cidr_source_gives_cidr_subnet_rule(self):
        c = _candidate(requires_manual_review=True)
        c["src_is_cidr"] = True
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["conflict_reason"] == "cidr_subnet_rule"

    def test_cidr_target_gives_cidr_subnet_rule(self):
        c = _candidate(requires_manual_review=True)
        c["tgt_is_cidr"] = True
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["conflict_reason"] == "cidr_subnet_rule"

    def test_complex_port_no_cidr_gives_complex_port_expression(self):
        c = _candidate(requires_manual_review=True, port_expression=True)
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["conflict_reason"] == "complex_port_expression"

    def test_unknown_source_gives_unknown_source_endpoint(self):
        c = _candidate(requires_manual_review=True)
        c["src_endpoint_class"] = "unknown"
        c["tgt_endpoint_class"] = "customer_external"
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["conflict_reason"] == "unknown_source_endpoint"

    def test_unknown_target_gives_unknown_target_endpoint(self):
        c = _candidate(requires_manual_review=True)
        c["src_endpoint_class"] = "customer_external"
        c["tgt_endpoint_class"] = "unknown"
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["conflict_reason"] == "unknown_target_endpoint"

    def test_unknown_both_gives_unknown_both_endpoints(self):
        c = _candidate(requires_manual_review=True)
        c["src_endpoint_class"] = "unknown"
        c["tgt_endpoint_class"] = "unknown"
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["conflict_reason"] == "unknown_both_endpoints"

    def test_no_specific_reason_falls_back_to_requires_manual_review(self):
        c = _candidate(requires_manual_review=True)
        # No CIDR flags, no complex port, no endpoint classes set → catch-all
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["conflict_reason"] == "requires_manual_review"

    def test_cidr_takes_priority_over_complex_port(self):
        c = _candidate(requires_manual_review=True, port_expression=True)
        c["src_is_cidr"] = True
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["conflict_reason"] == "cidr_subnet_rule"

    def test_unknown_endpoint_takes_priority_over_cidr(self):
        c = _candidate(requires_manual_review=True)
        c["src_endpoint_class"] = "unknown"
        c["src_is_cidr"] = True
        result = plan_scp_firewall([c], None)
        assert result.conflicts[0]["conflict_reason"] == "unknown_source_endpoint"

    def test_conflict_flags_present(self):
        c = _candidate(requires_manual_review=True, port_expression=True)
        c["src_is_cidr"] = True
        result = plan_scp_firewall([c], None)
        assert "conflict_flags" in result.conflicts[0]

    def test_conflict_flags_includes_secondary_reasons(self):
        c = _candidate(requires_manual_review=True, port_expression=True)
        c["src_is_cidr"] = True
        result = plan_scp_firewall([c], None)
        # Primary reason is cidr_subnet_rule; complex_port_expression is secondary
        assert "complex_port_expression" in result.conflicts[0]["conflict_flags"]
