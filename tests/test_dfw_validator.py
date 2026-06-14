"""Tests for src/validator/dfw_validator.py — desired vs actual DFW rule comparison."""
import pytest
from src.validator.dfw_validator import validate_dfw, DfwValidationResult


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _desired(rule_id="rule-001", action="permit", port="443", protocol="TCP"):
    return {
        "rule_id":  rule_id,
        "action":   action,
        "port":     port,
        "protocol": protocol,
    }

def _actual(rule_id="rule-001", action="permit", port="443", protocol="TCP"):
    return {
        "rule_id":  rule_id,
        "action":   action,
        "port":     port,
        "protocol": protocol,
    }


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:
    def test_returns_dfw_validation_result(self):
        result = validate_dfw([], [])
        assert isinstance(result, DfwValidationResult)

    def test_has_matched(self):
        result = validate_dfw([], [])
        assert isinstance(result.matched, list)

    def test_has_unmatched(self):
        result = validate_dfw([], [])
        assert isinstance(result.unmatched, list)

    def test_has_unexpected(self):
        result = validate_dfw([], [])
        assert isinstance(result.unexpected, list)

    def test_has_summary(self):
        result = validate_dfw([], [])
        assert isinstance(result.summary, dict)

    def test_summary_keys(self):
        result = validate_dfw([], [])
        for key in ("matched", "unmatched", "unexpected"):
            assert key in result.summary

    def test_empty_both_returns_empty(self):
        result = validate_dfw([], [])
        assert result.matched == []
        assert result.unmatched == []
        assert result.unexpected == []


# ---------------------------------------------------------------------------
# Matching rules
# ---------------------------------------------------------------------------

class TestMatchedRules:
    def test_identical_rule_is_matched(self):
        result = validate_dfw([_desired()], [_actual()])
        assert len(result.matched) == 1

    def test_matched_has_resource_id(self):
        result = validate_dfw([_desired(rule_id="rule-abc")], [_actual(rule_id="rule-abc")])
        assert result.matched[0]["resource_id"] == "rule-abc"

    def test_matched_status(self):
        result = validate_dfw([_desired()], [_actual()])
        assert result.matched[0]["status"] == "matched"

    def test_summary_matched_count(self):
        desired = [_desired(rule_id=f"rule-{i:03d}") for i in range(3)]
        actual  = [_actual(rule_id=f"rule-{i:03d}") for i in range(3)]
        result = validate_dfw(desired, actual)
        assert result.summary["matched"] == 3


# ---------------------------------------------------------------------------
# Unmatched rules (desired but not in actual or fields differ)
# ---------------------------------------------------------------------------

class TestUnmatchedRules:
    def test_desired_not_in_actual_is_unmatched(self):
        result = validate_dfw([_desired()], [])
        assert len(result.unmatched) == 1

    def test_unmatched_has_resource_id(self):
        result = validate_dfw([_desired(rule_id="rule-miss")], [])
        assert result.unmatched[0]["resource_id"] == "rule-miss"

    def test_unmatched_status_missing(self):
        result = validate_dfw([_desired()], [])
        assert result.unmatched[0]["status"] == "missing"

    def test_field_divergence_is_unmatched(self):
        result = validate_dfw(
            [_desired(port="443")],
            [_actual(port="80")],
        )
        assert len(result.unmatched) == 1

    def test_diverged_status(self):
        result = validate_dfw(
            [_desired(port="443")],
            [_actual(port="80")],
        )
        assert result.unmatched[0]["status"] == "diverged"

    def test_diverged_has_diff(self):
        result = validate_dfw(
            [_desired(port="443")],
            [_actual(port="80")],
        )
        assert "diff" in result.unmatched[0]
        assert "port" in result.unmatched[0]["diff"]

    def test_actual_missing_port_is_diverged(self):
        result = validate_dfw(
            [_desired(port="443")],
            [_actual(port=None)],
        )
        assert result.unmatched[0]["status"] == "diverged"
        assert result.unmatched[0]["diff"]["port"] == {
            "desired": "443",
            "actual": None,
        }

    def test_desired_missing_port_is_diverged(self):
        result = validate_dfw(
            [_desired(port=None)],
            [_actual(port="443")],
        )
        assert result.unmatched[0]["status"] == "diverged"
        assert result.unmatched[0]["diff"]["port"] == {
            "desired": None,
            "actual": "443",
        }

    def test_summary_unmatched_count(self):
        desired = [_desired(rule_id="rule-001"), _desired(rule_id="rule-002")]
        actual  = [_actual(rule_id="rule-001")]
        result = validate_dfw(desired, actual)
        assert result.summary["unmatched"] == 1


# ---------------------------------------------------------------------------
# Unexpected rules (actual but not in desired)
# ---------------------------------------------------------------------------

class TestUnexpectedRules:
    def test_actual_not_in_desired_is_unexpected(self):
        result = validate_dfw([], [_actual(rule_id="rule-ghost")])
        assert len(result.unexpected) == 1

    def test_unexpected_has_resource_id(self):
        result = validate_dfw([], [_actual(rule_id="rule-ghost")])
        assert result.unexpected[0]["resource_id"] == "rule-ghost"

    def test_unexpected_status(self):
        result = validate_dfw([], [_actual()])
        assert result.unexpected[0]["status"] == "unexpected"

    def test_summary_unexpected_count(self):
        result = validate_dfw([], [_actual(rule_id="r1"), _actual(rule_id="r2")])
        assert result.summary["unexpected"] == 2


# ---------------------------------------------------------------------------
# Mixed scenario
# ---------------------------------------------------------------------------

class TestMixedScenario:
    def test_mixed_classification(self):
        desired = [
            _desired(rule_id="rule-001"),          # matched
            _desired(rule_id="rule-002", port="443"),  # diverged (actual has port=80)
            _desired(rule_id="rule-003"),          # missing
        ]
        actual = [
            _actual(rule_id="rule-001"),           # matched
            _actual(rule_id="rule-002", port="80"),    # diverged
            _actual(rule_id="rule-999"),           # unexpected
        ]
        result = validate_dfw(desired, actual)
        assert result.summary["matched"] == 1
        assert result.summary["unmatched"] == 2   # diverged + missing
        assert result.summary["unexpected"] == 1
