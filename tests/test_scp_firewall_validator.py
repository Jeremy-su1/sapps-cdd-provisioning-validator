"""Tests for src/validator/scp_firewall_validator.py — desired vs actual SCP firewall comparison."""
import pytest
from src.validator.scp_firewall_validator import (
    validate_scp_firewall,
    validate_realized_vs_actual,
    ScpFirewallValidationResult,
    RealizedValidationResult,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _desired(
    resource_id="scp-fw-0",
    port="443",
    protocol="TCP",
    source_ip="10.0.1.11",
    target_ip="203.0.113.5",
    action="permit",
):
    return {
        "resource_id": resource_id,
        "port":        port,
        "protocol":    protocol,
        "source_ip":   source_ip,
        "target_ip":   target_ip,
        "action":      action,
    }

def _actual(
    resource_id="scp-fw-0",
    port="443",
    protocol="TCP",
    source_ip="10.0.1.11",
    target_ip="203.0.113.5",
    action="permit",
):
    return {
        "resource_id": resource_id,
        "port":        port,
        "protocol":    protocol,
        "source_ip":   source_ip,
        "target_ip":   target_ip,
        "action":      action,
    }


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:
    def test_returns_scp_firewall_validation_result(self):
        result = validate_scp_firewall([], [])
        assert isinstance(result, ScpFirewallValidationResult)

    def test_has_matched(self):
        result = validate_scp_firewall([], [])
        assert isinstance(result.matched, list)

    def test_has_unmatched(self):
        result = validate_scp_firewall([], [])
        assert isinstance(result.unmatched, list)

    def test_has_unexpected(self):
        result = validate_scp_firewall([], [])
        assert isinstance(result.unexpected, list)

    def test_has_summary(self):
        result = validate_scp_firewall([], [])
        assert isinstance(result.summary, dict)

    def test_summary_keys(self):
        result = validate_scp_firewall([], [])
        for key in ("matched", "unmatched", "unexpected"):
            assert key in result.summary

    def test_empty_both_returns_empty(self):
        result = validate_scp_firewall([], [])
        assert result.matched == []
        assert result.unmatched == []
        assert result.unexpected == []


# ---------------------------------------------------------------------------
# Matched rules
# ---------------------------------------------------------------------------

class TestMatchedRules:
    def test_identical_rule_is_matched(self):
        result = validate_scp_firewall([_desired()], [_actual()])
        assert len(result.matched) == 1

    def test_matched_has_resource_id(self):
        result = validate_scp_firewall(
            [_desired(resource_id="scp-fw-7")],
            [_actual(resource_id="scp-fw-7")],
        )
        assert result.matched[0]["resource_id"] == "scp-fw-7"

    def test_matched_status(self):
        result = validate_scp_firewall([_desired()], [_actual()])
        assert result.matched[0]["status"] == "matched"

    def test_summary_matched_count(self):
        desired = [_desired(resource_id=f"scp-fw-{i}") for i in range(3)]
        actual  = [_actual(resource_id=f"scp-fw-{i}") for i in range(3)]
        result = validate_scp_firewall(desired, actual)
        assert result.summary["matched"] == 3


# ---------------------------------------------------------------------------
# Missing rules (desired but absent from actual)
# ---------------------------------------------------------------------------

class TestMissingRules:
    def test_desired_not_in_actual_is_unmatched(self):
        result = validate_scp_firewall([_desired()], [])
        assert len(result.unmatched) == 1

    def test_missing_status(self):
        result = validate_scp_firewall([_desired()], [])
        assert result.unmatched[0]["status"] == "missing"

    def test_missing_has_resource_id(self):
        result = validate_scp_firewall([_desired(resource_id="scp-fw-9")], [])
        assert result.unmatched[0]["resource_id"] == "scp-fw-9"

    def test_summary_unmatched_count_for_missing(self):
        desired = [_desired(resource_id="scp-fw-0"), _desired(resource_id="scp-fw-1")]
        actual  = [_actual(resource_id="scp-fw-0")]
        result = validate_scp_firewall(desired, actual)
        assert result.summary["unmatched"] == 1


# ---------------------------------------------------------------------------
# Diverged rules (present in actual but fields differ)
# ---------------------------------------------------------------------------

class TestDivergedRules:
    def test_field_divergence_is_unmatched(self):
        result = validate_scp_firewall(
            [_desired(port="443")],
            [_actual(port="80")],
        )
        assert len(result.unmatched) == 1

    def test_diverged_status(self):
        result = validate_scp_firewall(
            [_desired(port="443")],
            [_actual(port="80")],
        )
        assert result.unmatched[0]["status"] == "diverged"

    def test_diverged_has_diff(self):
        result = validate_scp_firewall(
            [_desired(port="443")],
            [_actual(port="80")],
        )
        assert "diff" in result.unmatched[0]
        assert "port" in result.unmatched[0]["diff"]

    def test_diverged_diff_shows_desired_and_actual(self):
        result = validate_scp_firewall(
            [_desired(port="443")],
            [_actual(port="80")],
        )
        diff = result.unmatched[0]["diff"]["port"]
        assert diff["desired"] == "443"
        assert diff["actual"] == "80"

    def test_protocol_divergence_is_diverged(self):
        result = validate_scp_firewall(
            [_desired(protocol="TCP")],
            [_actual(protocol="UDP")],
        )
        assert result.unmatched[0]["status"] == "diverged"
        assert "protocol" in result.unmatched[0]["diff"]

    def test_source_ip_divergence_is_diverged(self):
        result = validate_scp_firewall(
            [_desired(source_ip="10.0.1.11")],
            [_actual(source_ip="10.0.1.99")],
        )
        assert result.unmatched[0]["status"] == "diverged"

    def test_target_ip_divergence_is_diverged(self):
        result = validate_scp_firewall(
            [_desired(target_ip="203.0.113.5")],
            [_actual(target_ip="203.0.113.99")],
        )
        assert result.unmatched[0]["status"] == "diverged"
        assert "target_ip" in result.unmatched[0]["diff"]

    def test_action_divergence_is_diverged(self):
        result = validate_scp_firewall(
            [_desired(action="permit")],
            [_actual(action="deny")],
        )
        assert result.unmatched[0]["status"] == "diverged"
        assert "action" in result.unmatched[0]["diff"]

    def test_desired_port_with_missing_actual_port_is_diverged(self):
        result = validate_scp_firewall(
            [_desired(port="443")],
            [_actual(port=None)],
        )
        assert result.unmatched[0]["status"] == "diverged"
        assert result.unmatched[0]["diff"]["port"] == {
            "desired": "443",
            "actual": None,
        }

    def test_missing_desired_port_with_actual_port_is_diverged(self):
        result = validate_scp_firewall(
            [_desired(port=None)],
            [_actual(port="443")],
        )
        assert result.unmatched[0]["status"] == "diverged"
        assert result.unmatched[0]["diff"]["port"] == {
            "desired": None,
            "actual": "443",
        }


# ---------------------------------------------------------------------------
# Unexpected rules (actual but not in desired)
# ---------------------------------------------------------------------------

class TestUnexpectedRules:
    def test_actual_not_in_desired_is_unexpected(self):
        result = validate_scp_firewall([], [_actual(resource_id="scp-fw-ghost")])
        assert len(result.unexpected) == 1

    def test_unexpected_has_resource_id(self):
        result = validate_scp_firewall([], [_actual(resource_id="scp-fw-ghost")])
        assert result.unexpected[0]["resource_id"] == "scp-fw-ghost"

    def test_unexpected_status(self):
        result = validate_scp_firewall([], [_actual()])
        assert result.unexpected[0]["status"] == "unexpected"

    def test_summary_unexpected_count(self):
        result = validate_scp_firewall([], [_actual(resource_id="r1"), _actual(resource_id="r2")])
        assert result.summary["unexpected"] == 2


# ---------------------------------------------------------------------------
# Mixed scenario
# ---------------------------------------------------------------------------

class TestMixedScenario:
    def test_mixed_classification(self):
        desired = [
            _desired(resource_id="scp-fw-0"),
            _desired(resource_id="scp-fw-1", port="443"),
            _desired(resource_id="scp-fw-2"),
        ]
        actual = [
            _actual(resource_id="scp-fw-0"),
            _actual(resource_id="scp-fw-1", port="80"),
            _actual(resource_id="scp-fw-99"),
        ]
        result = validate_scp_firewall(desired, actual)
        assert result.summary["matched"] == 1
        assert result.summary["unmatched"] == 2
        assert result.summary["unexpected"] == 1


# ---------------------------------------------------------------------------
# validate_realized_vs_actual — content-based matching
# ---------------------------------------------------------------------------

def _realized_rule(
    realized_rule_id="scp-fw-0-p0",
    origin_idx=0,
    source_ip="10.0.1.11",
    target_ip="203.0.113.5",
    protocol="TCP",
    port="443",
):
    return {
        "realized_rule_id":  realized_rule_id,
        "origin_idx":        origin_idx,
        "origin_resource_id": f"scp-fw-{origin_idx}",
        "source_ip":         source_ip,
        "target_ip":         target_ip,
        "protocol":          protocol,
        "port":              port,
        "action":            "permit",
        "backend_hint":      "scp",
    }


def _collected(
    resource_id="fw-api-001",
    source_ip="10.0.1.11",
    target_ip="203.0.113.5",
    protocol="TCP",
    port="443",
):
    return {
        "resource_id": resource_id,
        "source_ip":   source_ip,
        "target_ip":   target_ip,
        "protocol":    protocol,
        "port":        port,
        "action":      "permit",
    }


class TestRealizedVsActualReturnStructure:
    def test_returns_realized_validation_result(self):
        result = validate_realized_vs_actual([], [])
        assert isinstance(result, RealizedValidationResult)

    def test_has_matched(self):
        result = validate_realized_vs_actual([], [])
        assert isinstance(result.matched, list)

    def test_has_missing(self):
        result = validate_realized_vs_actual([], [])
        assert isinstance(result.missing, list)

    def test_has_unexpected(self):
        result = validate_realized_vs_actual([], [])
        assert isinstance(result.unexpected, list)

    def test_has_summary(self):
        result = validate_realized_vs_actual([], [])
        assert isinstance(result.summary, dict)

    def test_summary_keys(self):
        result = validate_realized_vs_actual([], [])
        for key in ("realized_rules", "actual_rules", "matched", "missing", "unexpected"):
            assert key in result.summary

    def test_empty_both_all_zero(self):
        result = validate_realized_vs_actual([], [])
        assert result.summary["matched"] == 0
        assert result.summary["missing"] == 0
        assert result.summary["unexpected"] == 0


class TestRealizedVsActualMatching:
    def test_matching_rule_is_matched(self):
        result = validate_realized_vs_actual([_realized_rule()], [_collected()])
        assert len(result.matched) == 1
        assert result.missing == []

    def test_match_uses_all_four_key_fields(self):
        # Four-tuple match: source_ip, target_ip, protocol, port
        realized = [_realized_rule(source_ip="10.0.1.11", target_ip="1.2.3.4",
                                    protocol="TCP", port="443")]
        actual   = [_collected(source_ip="10.0.1.11", target_ip="1.2.3.4",
                                protocol="TCP", port="443")]
        result = validate_realized_vs_actual(realized, actual)
        assert result.summary["matched"] == 1

    def test_different_source_ip_is_not_matched(self):
        realized = [_realized_rule(source_ip="10.0.1.11")]
        actual   = [_collected(source_ip="10.0.1.99")]
        result = validate_realized_vs_actual(realized, actual)
        assert result.summary["matched"] == 0
        assert result.summary["missing"] == 1

    def test_different_target_ip_is_not_matched(self):
        realized = [_realized_rule(target_ip="203.0.113.5")]
        actual   = [_collected(target_ip="203.0.113.99")]
        result = validate_realized_vs_actual(realized, actual)
        assert result.summary["missing"] == 1

    def test_different_protocol_is_not_matched(self):
        realized = [_realized_rule(protocol="TCP")]
        actual   = [_collected(protocol="UDP")]
        result = validate_realized_vs_actual(realized, actual)
        assert result.summary["missing"] == 1

    def test_different_port_is_not_matched(self):
        realized = [_realized_rule(port="443")]
        actual   = [_collected(port="80")]
        result = validate_realized_vs_actual(realized, actual)
        assert result.summary["missing"] == 1

    def test_matched_entry_has_realized_rule_id(self):
        result = validate_realized_vs_actual([_realized_rule()], [_collected()])
        assert "realized_rule_id" in result.matched[0]

    def test_matched_entry_has_actual(self):
        result = validate_realized_vs_actual([_realized_rule()], [_collected()])
        assert "actual" in result.matched[0]

    def test_summary_counts_correct(self):
        realized = [
            _realized_rule(realized_rule_id="scp-fw-0-p0", port="443"),   # matches
            _realized_rule(realized_rule_id="scp-fw-1-p0", port="80"),    # missing
        ]
        actual = [
            _collected(resource_id="api-001", port="443"),                 # matched
            _collected(resource_id="api-002", port="8080"),                # unexpected
        ]
        result = validate_realized_vs_actual(realized, actual)
        assert result.summary["matched"] == 1
        assert result.summary["missing"] == 1
        assert result.summary["unexpected"] == 1

    def test_missing_entry_has_realized_rule_id(self):
        result = validate_realized_vs_actual([_realized_rule()], [])
        assert "realized_rule_id" in result.missing[0]

    def test_unexpected_entry_has_resource_id(self):
        result = validate_realized_vs_actual([], [_collected(resource_id="ghost-001")])
        assert result.unexpected[0]["resource_id"] == "ghost-001"

    def test_realized_rules_count_in_summary(self):
        result = validate_realized_vs_actual(
            [_realized_rule(), _realized_rule(realized_rule_id="scp-fw-1-p0")], []
        )
        assert result.summary["realized_rules"] == 2

    def test_actual_rules_count_in_summary(self):
        result = validate_realized_vs_actual(
            [], [_collected(resource_id="r1"), _collected(resource_id="r2")]
        )
        assert result.summary["actual_rules"] == 2

    def test_multiple_rules_all_matched(self):
        realized = [
            _realized_rule(realized_rule_id=f"scp-fw-{i}-p0",
                           source_ip=f"10.0.{i}.1", port="443")
            for i in range(4)
        ]
        actual = [
            _collected(resource_id=f"api-{i}", source_ip=f"10.0.{i}.1", port="443")
            for i in range(4)
        ]
        result = validate_realized_vs_actual(realized, actual)
        assert result.summary["matched"] == 4
        assert result.summary["missing"] == 0
        assert result.summary["unexpected"] == 0
