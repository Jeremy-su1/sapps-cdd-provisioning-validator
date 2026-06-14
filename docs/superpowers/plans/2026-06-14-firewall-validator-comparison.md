# Firewall Validator Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure ID-based SCP Firewall and NSX-T DFW validation reports managed-field differences and one-sided missing values as drift.

**Architecture:** Keep each validator's explicit managed-field allowlist and public result types unchanged. Expand the SCP allowlist, then simplify both `_field_diff()` helpers so ordinary Python equality determines drift, including `None` on only one side.

**Tech Stack:** Python 3.11+, pytest

---

## File Structure

- `src/validator/scp_firewall_validator.py`: SCP managed-field comparison.
- `tests/test_scp_firewall_validator.py`: SCP drift regression coverage.
- `src/validator/dfw_validator.py`: NSX-T DFW managed-field comparison.
- `tests/test_dfw_validator.py`: DFW missing-value regression coverage.

### Task 1: Correct SCP Firewall Field Comparison

**Files:**
- Modify: `tests/test_scp_firewall_validator.py`
- Modify: `src/validator/scp_firewall_validator.py:13-39`

- [ ] **Step 1: Write failing SCP regression tests**

Extend the test helpers with `target_ip` and `action`, then add:

```python
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

def test_actual_missing_managed_field_is_diverged(self):
    result = validate_scp_firewall(
        [_desired(port="443")],
        [_actual(port=None)],
    )
    assert result.unmatched[0]["diff"]["port"] == {
        "desired": "443",
        "actual": None,
    }

def test_desired_missing_managed_field_is_diverged(self):
    result = validate_scp_firewall(
        [_desired(port=None)],
        [_actual(port="443")],
    )
    assert result.unmatched[0]["diff"]["port"] == {
        "desired": None,
        "actual": "443",
    }
```

- [ ] **Step 2: Run the SCP tests and verify RED**

Run:

```bash
PYTHONPATH='../.venv/lib/python3.9/site-packages' PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_scp_firewall_validator.py -q
```

Expected: the four new tests fail because `target_ip` and `action` are not compared and one-sided `None` values are ignored.

- [ ] **Step 3: Implement the minimal SCP comparison fix**

Use:

```python
_COMPARE_FIELDS = ("action", "port", "protocol", "source_ip", "target_ip")


def _field_diff(desired: dict, actual: dict) -> dict:
    diff = {}
    for field in _COMPARE_FIELDS:
        desired_value = desired.get(field)
        actual_value = actual.get(field)
        if desired_value != actual_value:
            diff[field] = {
                "desired": desired_value,
                "actual": actual_value,
            }
    return diff
```

- [ ] **Step 4: Run the SCP tests and verify GREEN**

Run the command from Step 2.

Expected: all tests in `tests/test_scp_firewall_validator.py` pass.

### Task 2: Correct DFW Missing-Value Comparison

**Files:**
- Modify: `tests/test_dfw_validator.py`
- Modify: `src/validator/dfw_validator.py:30-37`

- [ ] **Step 1: Write failing DFW regression tests**

Add:

```python
def test_actual_missing_managed_field_is_diverged(self):
    result = validate_dfw(
        [_desired(port="443")],
        [_actual(port=None)],
    )
    assert result.unmatched[0]["diff"]["port"] == {
        "desired": "443",
        "actual": None,
    }

def test_desired_missing_managed_field_is_diverged(self):
    result = validate_dfw(
        [_desired(port=None)],
        [_actual(port="443")],
    )
    assert result.unmatched[0]["diff"]["port"] == {
        "desired": None,
        "actual": "443",
    }
```

- [ ] **Step 2: Run the DFW tests and verify RED**

Run:

```bash
PYTHONPATH='../.venv/lib/python3.9/site-packages' PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_dfw_validator.py -q
```

Expected: the two new tests fail because one-sided `None` values are ignored.

- [ ] **Step 3: Implement the minimal DFW comparison fix**

Use:

```python
def _field_diff(desired: dict, actual: dict) -> dict:
    diff = {}
    for field in _COMPARE_FIELDS:
        desired_value = desired.get(field)
        actual_value = actual.get(field)
        if desired_value != actual_value:
            diff[field] = {
                "desired": desired_value,
                "actual": actual_value,
            }
    return diff
```

- [ ] **Step 4: Run the DFW tests and verify GREEN**

Run the command from Step 2.

Expected: all tests in `tests/test_dfw_validator.py` pass.

### Task 3: Verify the Complete Change

**Files:**
- Verify: `src/validator/scp_firewall_validator.py`
- Verify: `src/validator/dfw_validator.py`
- Verify: `tests/test_scp_firewall_validator.py`
- Verify: `tests/test_dfw_validator.py`

- [ ] **Step 1: Run the complete test suite**

Run:

```bash
PYTHONPATH='../.venv/lib/python3.9/site-packages' PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Check the patch**

Run:

```bash
git diff --check
git diff -- src/validator/scp_firewall_validator.py src/validator/dfw_validator.py tests/test_scp_firewall_validator.py tests/test_dfw_validator.py
```

Expected: no whitespace errors and only the approved comparison behavior changes.

- [ ] **Step 3: Commit the implementation**

```bash
git add src/validator/scp_firewall_validator.py src/validator/dfw_validator.py tests/test_scp_firewall_validator.py tests/test_dfw_validator.py docs/superpowers/plans/2026-06-14-firewall-validator-comparison.md
git commit -m "fix: detect firewall managed-field drift"
```
