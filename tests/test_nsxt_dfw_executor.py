"""Tests for src/executor/nsxt_dfw_executor.py — dry-run and real execution interface."""
import pytest
from src.executor.nsxt_dfw_executor import NsxtDfwExecutor, ExecutionResult, ExecutorError


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _create_item(rule_id="rule-001"):
    return {
        "action":        "create",
        "resource_type": "nsxt_dfw_rule",
        "resource_id":   rule_id,
        "desired":       {"rule_id": rule_id, "action": "permit", "port": "443"},
        "actual":        None,
        "requires_approval": False,
    }

def _skip_item(rule_id="rule-002"):
    return {
        "action":        "skip",
        "resource_type": "nsxt_dfw_rule",
        "resource_id":   rule_id,
        "desired":       {"rule_id": rule_id, "action": "permit", "port": "80"},
        "actual":        {"rule_id": rule_id, "action": "permit", "port": "80"},
        "requires_approval": False,
    }

def _conflict_item(rule_id="rule-003"):
    return {
        "action":        "conflict",
        "resource_type": "nsxt_dfw_rule",
        "resource_id":   rule_id,
        "desired":       {"rule_id": rule_id},
        "actual":        None,
        "requires_approval": True,
    }


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestExecutionResult:
    def test_is_dataclass(self):
        r = ExecutionResult(applied=[], skipped=[], errors=[])
        assert isinstance(r, ExecutionResult)

    def test_has_applied(self):
        r = ExecutionResult(applied=[], skipped=[], errors=[])
        assert isinstance(r.applied, list)

    def test_has_skipped(self):
        r = ExecutionResult(applied=[], skipped=[], errors=[])
        assert isinstance(r.skipped, list)

    def test_has_errors(self):
        r = ExecutionResult(applied=[], skipped=[], errors=[])
        assert isinstance(r.errors, list)


# ---------------------------------------------------------------------------
# Executor interface
# ---------------------------------------------------------------------------

class TestExecutorInterface:
    def test_instantiates(self):
        ex = NsxtDfwExecutor(host="nsxt.example.com", token="tok", dry_run=True)
        assert ex is not None

    def test_has_apply_method(self):
        ex = NsxtDfwExecutor(host="nsxt.example.com", token="tok", dry_run=True)
        assert callable(ex.apply)

    def test_dry_run_defaults_to_true(self):
        ex = NsxtDfwExecutor(host="nsxt.example.com", token="tok")
        assert ex.dry_run is True

    def test_executor_error_is_exception(self):
        assert issubclass(ExecutorError, Exception)


# ---------------------------------------------------------------------------
# Dry-run execution
# ---------------------------------------------------------------------------

class TestDryRunExecution:
    def _executor(self):
        return NsxtDfwExecutor(host="nsxt.example.com", token="tok", dry_run=True)

    def test_empty_plan_returns_empty_result(self):
        result = self._executor().apply([])
        assert result.applied == []
        assert result.skipped == []
        assert result.errors == []

    def test_create_item_goes_to_applied_in_dry_run(self):
        result = self._executor().apply([_create_item()])
        assert len(result.applied) == 1

    def test_applied_item_has_resource_id(self):
        result = self._executor().apply([_create_item("rule-999")])
        assert result.applied[0]["resource_id"] == "rule-999"

    def test_applied_item_dry_run_flag(self):
        result = self._executor().apply([_create_item()])
        assert result.applied[0].get("dry_run") is True

    def test_skip_item_goes_to_skipped(self):
        result = self._executor().apply([_skip_item()])
        assert len(result.skipped) == 1
        assert result.applied == []

    def test_conflict_item_goes_to_errors(self):
        result = self._executor().apply([_conflict_item()])
        assert len(result.errors) == 1
        assert result.applied == []

    def test_mixed_plan(self):
        plan = [_create_item("r1"), _skip_item("r2"), _conflict_item("r3")]
        result = self._executor().apply(plan)
        assert len(result.applied) == 1
        assert len(result.skipped) == 1
        assert len(result.errors) == 1

    def test_no_api_calls_in_dry_run(self):
        # If dry_run=True, apply must not raise even with invalid host/token
        ex = NsxtDfwExecutor(host="not-a-real-host", token="bad-token", dry_run=True)
        result = ex.apply([_create_item()])
        assert len(result.applied) == 1


# ---------------------------------------------------------------------------
# Real execution (not implemented yet)
# ---------------------------------------------------------------------------

class TestRealExecutionNotImplemented:
    def test_real_mode_raises_not_implemented(self):
        ex = NsxtDfwExecutor(host="nsxt.example.com", token="tok", dry_run=False)
        with pytest.raises(NotImplementedError):
            ex.apply([_create_item()])

    def test_real_mode_raises_executor_error_without_credentials(self):
        ex = NsxtDfwExecutor(host=None, token=None, dry_run=False)
        with pytest.raises(ExecutorError):
            ex.apply([_create_item()])
