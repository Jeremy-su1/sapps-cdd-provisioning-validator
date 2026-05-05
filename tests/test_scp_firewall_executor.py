"""Tests for src/executor/scp_firewall_executor.py — dry-run and real execution interface."""
import pytest
from src.executor.scp_firewall_executor import ScpFirewallExecutor, ExecutionResult, ExecutorError


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _create_item(resource_id="scp-fw-0"):
    return {
        "action":                      "create",
        "resource_type":               "scp_firewall_rule",
        "resource_id":                 resource_id,
        "desired":                     {"resource_id": resource_id, "port": "443"},
        "actual":                      None,
        "requires_approval":           False,
        "backend_hint":                "scp",
        "execution_method_candidates": ["scp_api", "scp_cli"],
    }

def _skip_item(resource_id="scp-fw-1"):
    return {
        "action":                      "skip",
        "resource_type":               "scp_firewall_rule",
        "resource_id":                 resource_id,
        "desired":                     {"resource_id": resource_id, "port": "80"},
        "actual":                      {"resource_id": resource_id, "port": "80"},
        "requires_approval":           False,
        "backend_hint":                "scp",
        "execution_method_candidates": ["scp_api", "scp_cli"],
    }

def _conflict_item(resource_id="scp-fw-2"):
    return {
        "action":                      "conflict",
        "resource_type":               "scp_firewall_rule",
        "resource_id":                 resource_id,
        "desired":                     {"resource_id": resource_id},
        "actual":                      None,
        "requires_approval":           True,
        "backend_hint":                "scp",
        "execution_method_candidates": ["scp_api", "scp_cli"],
    }


# ---------------------------------------------------------------------------
# ExecutionResult structure
# ---------------------------------------------------------------------------

class TestExecutionResult:
    def test_is_dataclass(self):
        r = ExecutionResult(applied=[], skipped=[], errors=[])
        assert isinstance(r, ExecutionResult)

    def test_has_applied(self):
        assert isinstance(ExecutionResult(applied=[], skipped=[], errors=[]).applied, list)

    def test_has_skipped(self):
        assert isinstance(ExecutionResult(applied=[], skipped=[], errors=[]).skipped, list)

    def test_has_errors(self):
        assert isinstance(ExecutionResult(applied=[], skipped=[], errors=[]).errors, list)


# ---------------------------------------------------------------------------
# Executor interface
# ---------------------------------------------------------------------------

class TestExecutorInterface:
    def test_instantiates(self):
        ex = ScpFirewallExecutor(endpoint="https://scp.example.com", token="tok", dry_run=True)
        assert ex is not None

    def test_has_apply_method(self):
        ex = ScpFirewallExecutor(endpoint="https://scp.example.com", token="tok", dry_run=True)
        assert callable(ex.apply)

    def test_dry_run_defaults_to_true(self):
        ex = ScpFirewallExecutor(endpoint="https://scp.example.com", token="tok")
        assert ex.dry_run is True

    def test_executor_error_is_exception(self):
        assert issubclass(ExecutorError, Exception)

    def test_execution_method_stored(self):
        ex = ScpFirewallExecutor(endpoint="e", token="t", execution_method="scp_cli")
        assert ex.execution_method == "scp_cli"

    def test_execution_method_defaults_to_scp_api(self):
        ex = ScpFirewallExecutor(endpoint="e", token="t")
        assert ex.execution_method == "scp_api"


# ---------------------------------------------------------------------------
# Dry-run execution
# ---------------------------------------------------------------------------

class TestDryRunExecution:
    def _executor(self):
        return ScpFirewallExecutor(endpoint="https://scp.example.com", token="tok", dry_run=True)

    def test_empty_plan_returns_empty_result(self):
        result = self._executor().apply([])
        assert result.applied == []
        assert result.skipped == []
        assert result.errors == []

    def test_create_item_goes_to_applied_in_dry_run(self):
        result = self._executor().apply([_create_item()])
        assert len(result.applied) == 1

    def test_applied_item_has_resource_id(self):
        result = self._executor().apply([_create_item("scp-fw-99")])
        assert result.applied[0]["resource_id"] == "scp-fw-99"

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
        plan = [_create_item("r0"), _skip_item("r1"), _conflict_item("r2")]
        result = self._executor().apply(plan)
        assert len(result.applied) == 1
        assert len(result.skipped) == 1
        assert len(result.errors) == 1

    def test_no_api_calls_in_dry_run(self):
        ex = ScpFirewallExecutor(endpoint="not-real", token="bad", dry_run=True)
        result = ex.apply([_create_item()])
        assert len(result.applied) == 1


# ---------------------------------------------------------------------------
# Real execution (not implemented yet)
# ---------------------------------------------------------------------------

class TestRealExecutionNotImplemented:
    def test_real_mode_raises_not_implemented(self):
        ex = ScpFirewallExecutor(endpoint="https://scp.example.com", token="tok", dry_run=False)
        with pytest.raises(NotImplementedError):
            ex.apply([_create_item()])

    def test_real_mode_raises_executor_error_without_credentials(self):
        ex = ScpFirewallExecutor(endpoint=None, token=None, dry_run=False)
        with pytest.raises(ExecutorError):
            ex.apply([_create_item()])
