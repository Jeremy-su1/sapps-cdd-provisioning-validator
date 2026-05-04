# Scaffold Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the complete scaffold — 6 skill definitions, src/tests package structure, and an updated README — so that future sessions can implement each layer independently.

**Architecture:** Each of the 6 layers (parser, schema, planner, validator, reporter, llm-adapter) maps 1:1 to a skill and a src sub-package. Tests are fixture-driven; fixtures live in `tests/fixtures/`. LLM calls are isolated behind a stub interface so the system runs without a real LLM.

**Tech Stack:** Python 3.10+, pytest, plain JSON fixtures, no external frameworks.

---

## File Structure

### Skills (`.claude/skills/`)

| File | Action |
|------|--------|
| `.claude/skills/s2d-parser/SKILL.md` | Fill (currently empty) |
| `.claude/skills/desired-state-schema/SKILL.md` | Fill (currently empty) |
| `.claude/skills/llm-adapter/SKILL.md` | Create new (6th skill) |
| `.claude/skills/provisioning-planner/SKILL.md` | Already complete — no change |
| `.claude/skills/drift-validator/SKILL.md` | Already complete — no change |
| `.claude/skills/report-generator/SKILL.md` | Already complete — no change |

### Source (`src/`)

| File | Responsibility |
|------|----------------|
| `src/__init__.py` | Package marker |
| `src/parser/__init__.py` | S2D Excel → desired-state JSON |
| `src/schema/__init__.py` | JSON schema definitions + validate() |
| `src/planner/__init__.py` | Deterministic action planner |
| `src/validator/__init__.py` | Drift comparison engine |
| `src/reporter/__init__.py` | JSON + Markdown renderers |
| `src/llm/__init__.py` | LLM adapter interface + no-op stub |

### Tests (`tests/`)

| File | Responsibility |
|------|----------------|
| `tests/__init__.py` | Package marker |
| `tests/fixtures/sample_desired_state.json` | Generic desired-state fixture |
| `tests/fixtures/sample_actual_state.json` | Generic actual-state fixture |
| `tests/fixtures/sample_action_plan.json` | Generic planned-actions fixture |
| `tests/test_parser.py` | Parser smoke test (fixture round-trip) |
| `tests/test_planner.py` | Planner create/skip/conflict test |
| `tests/test_validator.py` | Drift detection test (missing + mismatch) |

---

## Task 1: Fill `s2d-parser/SKILL.md`

**Files:**
- Modify: `.claude/skills/s2d-parser/SKILL.md`

- [ ] **Step 1: Write the skill file**

```markdown
---
name: s2d-parser
description: Parse standard S2D Excel files into normalized desired-state JSON for provisioning and validation.
---

# Purpose

Use this skill to convert an S2D Excel document into a normalized desired-state JSON object.

This skill is responsible for:
- reading S2D Excel sheets by known column headers
- normalising row data into typed resource records
- producing a structured desired_state.json
- flagging unparseable or ambiguous rows without failing silently

---

# Use this skill when

Use this skill when:
- an S2D Excel file is provided as input
- desired state must be derived from a spreadsheet
- column mappings must be validated before processing
- raw rows must be normalized into typed resource dicts

---

# Supported Resource Types (MVP)

- TGW attachments and route tables
- Firewall rules and zones
- VMware VMs (name, network, sizing)
- NSX-T Distributed Firewall sections and rules

---

# Inputs

- S2D Excel file path (or in-memory workbook)
- Optional sheet-name overrides

---

# Outputs

- desired_state.json with top-level keys per resource type
- parse_warnings list for ambiguous or skipped rows

---

# Rules

1. Never silently drop rows — emit a warning entry instead.
2. Column header matching must be case-insensitive.
3. Required fields must be validated before emitting a resource record.
4. Output must be deterministic given the same input.
5. Do not mix parsing and planning logic.

---

# Recommended Workflow

1. Load workbook
2. Identify sheet-to-resource-type mapping
3. Iterate rows, map columns to schema fields
4. Validate required fields
5. Append to typed lists in desired_state
6. Return desired_state dict + warnings

---

# Implementation Guidance

Prefer:
- explicit column-map dicts per resource type
- row-level try/except that appends to warnings
- pure functions that take a sheet and return a list

Avoid:
- hardcoded row indices
- mixing Excel I/O with business logic
```

- [ ] **Step 2: Verify file is non-empty**

```bash
wc -l .claude/skills/s2d-parser/SKILL.md
```
Expected: `> 5`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/s2d-parser/SKILL.md
git commit -m "docs: fill s2d-parser SKILL.md"
```

---

## Task 2: Fill `desired-state-schema/SKILL.md`

**Files:**
- Modify: `.claude/skills/desired-state-schema/SKILL.md`

- [ ] **Step 1: Write the skill file**

```markdown
---
name: desired-state-schema
description: Define and validate the normalized desired-state JSON schema for all MVP resource types.
---

# Purpose

Use this skill to define, validate, and evolve the desired-state JSON schema.

This skill is responsible for:
- specifying required and optional fields for each resource type
- providing a validate() entry point used by the parser and planner
- documenting field semantics and allowed values
- keeping schema keys stable across versions

---

# Use this skill when

Use this skill when:
- desired-state JSON structure needs to be defined or changed
- a new resource type must be added to the schema
- parser output must be validated before planning
- fixture files must be updated after a schema change

---

# Top-Level Structure

```json
{
  "tgw": [],
  "firewall": [],
  "vm": [],
  "nsxt_dfw": []
}
```

---

# Field Rules

## tgw item
Required: id, attachment_id, route_table_id
Optional: tags

## firewall item
Required: rule_id, source_zone, destination_zone, action
Optional: protocol, port, description

## vm item
Required: name, network, cpu, memory_gb, os_template
Optional: tags, datastore

## nsxt_dfw item
Required: section_name, rule_name, source, destination, action
Optional: applied_to, logged

---

# Schema Stability Rules

1. Never rename existing required fields without a migration plan.
2. New optional fields must have a default or be nullable.
3. Any schema change requires updating fixtures and tests together.
4. Keep field names lowercase with underscores.

---

# Outputs

- Validated desired_state dict (raise on hard error, warn on soft)
- Validation error list with field paths

---

# Implementation Guidance

Prefer:
- a single validate(desired_state: dict) -> ValidationResult function
- per-resource-type validators composed into the top-level validator
- explicit error messages with field paths

Avoid:
- runtime schema generation
- mixing schema validation with parsing logic
```

- [ ] **Step 2: Verify file is non-empty**

```bash
wc -l .claude/skills/desired-state-schema/SKILL.md
```
Expected: `> 5`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/desired-state-schema/SKILL.md
git commit -m "docs: fill desired-state-schema SKILL.md"
```

---

## Task 3: Create `llm-adapter` skill (6th skill)

**Files:**
- Create: `.claude/skills/llm-adapter/SKILL.md`

- [ ] **Step 1: Create the skill file**

```markdown
---
name: llm-adapter
description: Isolate all LLM calls behind a single interface so the system runs in reduced mode without a real LLM.
---

# Purpose

Use this skill to build and maintain the LLM adapter layer.

This skill is responsible for:
- defining the LLMAdapter interface
- providing a no-op stub that returns safe defaults
- providing an Anthropic-backed implementation (optional, off by default)
- ensuring the rest of the system never calls an LLM directly

---

# Use this skill when

Use this skill when:
- semantic term mapping must be added
- drift explanation generation is needed
- severity wording support must be implemented
- natural-language change intent must be parsed
- the LLM backend needs to be swapped or disabled

---

# Allowed LLM Uses

The LLM adapter may only be used for:
- mapping ambiguous terminology (e.g. "deny" vs "block" in firewall rules)
- generating human-readable drift explanations
- wording severity guidance for operators
- interpreting natural-language add-on change requests

---

# Forbidden LLM Uses

Never use the LLM adapter to:
- decide create / update / delete actions
- override deterministic comparison results
- generate or modify infrastructure state
- bypass dry-run or planning-first workflows

---

# Interface Contract

```python
class LLMAdapter:
    def map_term(self, term: str, context: str) -> str: ...
    def explain_drift(self, drift_item: dict) -> str: ...
    def parse_change_intent(self, text: str) -> dict: ...
```

The no-op stub returns the input term unchanged for map_term,
an empty string for explain_drift, and an empty dict for parse_change_intent.

---

# Reduced Mode

The system must work end-to-end without the LLM adapter.
All callers must handle an empty or passthrough response gracefully.

---

# Rules

1. LLM is never the source of truth for state decisions.
2. The adapter interface must be stable; swap implementations without changing callers.
3. All LLM calls must be logged so they can be audited.
4. The no-op stub must always be the default.

---

# Implementation Guidance

Prefer:
- a single LLMAdapter ABC with a NoOpAdapter default
- dependency injection at the application entry point
- logging wrapper around any real LLM call

Avoid:
- importing anthropic SDK outside this module
- calling LLM from validator, planner, or parser directly
```

- [ ] **Step 2: Verify file was created**

```bash
wc -l .claude/skills/llm-adapter/SKILL.md
```
Expected: `> 5`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/llm-adapter/SKILL.md
git commit -m "docs: add llm-adapter skill (6th skill)"
```

---

## Task 4: Create `src/` Python package structure

**Files:**
- Create: `src/__init__.py`
- Create: `src/parser/__init__.py`
- Create: `src/schema/__init__.py`
- Create: `src/planner/__init__.py`
- Create: `src/validator/__init__.py`
- Create: `src/reporter/__init__.py`
- Create: `src/llm/__init__.py`

- [ ] **Step 1: Create `src/__init__.py`**

```python
```
(empty file — package marker only)

- [ ] **Step 2: Create `src/parser/__init__.py`**

```python
"""S2D Excel parser — converts spreadsheet rows to desired_state dict."""

from typing import Any

ParseResult = dict[str, Any]
ParseWarnings = list[str]


def parse_s2d(workbook_path: str) -> tuple[ParseResult, ParseWarnings]:
    """Return (desired_state, warnings). Not yet implemented."""
    raise NotImplementedError("s2d-parser not yet implemented")
```

- [ ] **Step 3: Create `src/schema/__init__.py`**

```python
"""Desired-state JSON schema definitions and validation."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def validate(desired_state: dict[str, Any]) -> ValidationResult:
    """Validate desired_state against the schema. Not yet implemented."""
    raise NotImplementedError("desired-state-schema validator not yet implemented")
```

- [ ] **Step 4: Create `src/planner/__init__.py`**

```python
"""Deterministic provisioning planner."""

from typing import Any, Literal

ActionKind = Literal["create", "update", "skip", "conflict"]


def build_action_plan(
    desired_state: dict[str, Any],
    current_state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return ordered action list. Not yet implemented."""
    raise NotImplementedError("provisioning-planner not yet implemented")
```

- [ ] **Step 5: Create `src/validator/__init__.py`**

```python
"""Drift detection — compares desired state vs actual state."""

from typing import Any


def detect_drift(
    desired_state: dict[str, Any],
    actual_state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return list of drift findings. Not yet implemented."""
    raise NotImplementedError("drift-validator not yet implemented")
```

- [ ] **Step 6: Create `src/reporter/__init__.py`**

```python
"""Report renderers — JSON and Markdown outputs."""

import json
from typing import Any


def to_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def to_markdown(data: dict[str, Any]) -> str:
    """Render data as a Markdown report. Not yet implemented."""
    raise NotImplementedError("report-generator markdown renderer not yet implemented")
```

- [ ] **Step 7: Create `src/llm/__init__.py`**

```python
"""LLM adapter interface and no-op stub."""

from abc import ABC, abstractmethod
from typing import Any


class LLMAdapter(ABC):
    @abstractmethod
    def map_term(self, term: str, context: str) -> str: ...

    @abstractmethod
    def explain_drift(self, drift_item: dict[str, Any]) -> str: ...

    @abstractmethod
    def parse_change_intent(self, text: str) -> dict[str, Any]: ...


class NoOpAdapter(LLMAdapter):
    """Default adapter — returns safe pass-through values without any LLM call."""

    def map_term(self, term: str, context: str) -> str:
        return term

    def explain_drift(self, drift_item: dict[str, Any]) -> str:
        return ""

    def parse_change_intent(self, text: str) -> dict[str, Any]:
        return {}


def get_default_adapter() -> LLMAdapter:
    return NoOpAdapter()
```

- [ ] **Step 8: Commit**

```bash
git add src/
git commit -m "feat: add src/ package scaffold with stub interfaces"
```

---

## Task 5: Create `tests/` structure with fixtures and stub tests

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/fixtures/sample_desired_state.json`
- Create: `tests/fixtures/sample_actual_state.json`
- Create: `tests/fixtures/sample_action_plan.json`
- Create: `tests/test_parser.py`
- Create: `tests/test_planner.py`
- Create: `tests/test_validator.py`

- [ ] **Step 1: Create `tests/__init__.py`**

```python
```
(empty file)

- [ ] **Step 2: Create `tests/fixtures/sample_desired_state.json`**

```json
{
  "tgw": [
    {
      "id": "tgw-example-001",
      "attachment_id": "attach-example-001",
      "route_table_id": "rtb-example-001"
    }
  ],
  "firewall": [
    {
      "rule_id": "fw-rule-001",
      "source_zone": "zone-a",
      "destination_zone": "zone-b",
      "action": "allow"
    }
  ],
  "vm": [
    {
      "name": "vm-example-001",
      "network": "net-example-001",
      "cpu": 2,
      "memory_gb": 4,
      "os_template": "rhel8-generic"
    }
  ],
  "nsxt_dfw": [
    {
      "section_name": "section-example-001",
      "rule_name": "rule-example-001",
      "source": "group-a",
      "destination": "group-b",
      "action": "allow"
    }
  ]
}
```

- [ ] **Step 3: Create `tests/fixtures/sample_actual_state.json`**

```json
{
  "tgw": [
    {
      "id": "tgw-example-001",
      "attachment_id": "attach-example-001",
      "route_table_id": "rtb-example-999"
    }
  ],
  "firewall": [
    {
      "rule_id": "fw-rule-001",
      "source_zone": "zone-a",
      "destination_zone": "zone-b",
      "action": "deny"
    }
  ],
  "vm": [],
  "nsxt_dfw": []
}
```

- [ ] **Step 4: Create `tests/fixtures/sample_action_plan.json`**

```json
{
  "actions": [
    {
      "resource_type": "tgw",
      "resource_id": "tgw-example-001",
      "action": "create",
      "reason": "resource not found in current state"
    },
    {
      "resource_type": "firewall",
      "resource_id": "fw-rule-001",
      "action": "update",
      "reason": "action field differs: desired=allow actual=deny"
    }
  ],
  "skipped": [],
  "conflicts": []
}
```

- [ ] **Step 5: Create `tests/test_parser.py`**

```python
import pytest
from src.parser import parse_s2d


def test_parse_s2d_not_yet_implemented():
    with pytest.raises(NotImplementedError):
        parse_s2d("nonexistent.xlsx")
```

- [ ] **Step 6: Create `tests/test_planner.py`**

```python
import json
import pytest
from pathlib import Path
from src.planner import build_action_plan

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_build_action_plan_not_yet_implemented():
    desired = load("sample_desired_state.json")
    with pytest.raises(NotImplementedError):
        build_action_plan(desired, current_state=None)
```

- [ ] **Step 7: Create `tests/test_validator.py`**

```python
import json
import pytest
from pathlib import Path
from src.validator import detect_drift

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_detect_drift_not_yet_implemented():
    desired = load("sample_desired_state.json")
    actual = load("sample_actual_state.json")
    with pytest.raises(NotImplementedError):
        detect_drift(desired, actual)
```

- [ ] **Step 8: Run tests to confirm stubs are correctly wired**

```bash
python -m pytest tests/ -v
```

Expected output: 3 tests PASSED (each catches NotImplementedError)

- [ ] **Step 9: Commit**

```bash
git add tests/
git commit -m "test: add fixture-based test stubs for parser, planner, validator"
```

---

## Task 6: Update `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite README**

```markdown
# sapps-cdd-provisioning-validator

Generic scaffold for S2D-driven infrastructure provisioning and validation on SCP.

## What this is

This repository provides a scaffold for converting SAP PS S2D Excel documents
into executable desired-state definitions, provisioning selected infrastructure
resources, and validating the actual state against the desired state.

It is intentionally generic and public-safe.
No company-specific endpoints, credentials, or real infrastructure values are included.

## MVP Scope

- TGW provisioning and validation
- Firewall provisioning and validation
- VMware VM provisioning and validation
- NSX-T Distributed Firewall provisioning and validation

## Three operating modes

| Mode | Description |
|------|-------------|
| Provision | Parse S2D → plan → execute create/update actions |
| Validation | Collect actual state → compare vs desired state → report drift |
| Incremental add-on | Parse change intent → plan delta → provision only changed items |

## Architecture

```
S2D Excel
   └─▶ parser          →  desired_state.json
   └─▶ schema          →  validated desired state
   └─▶ planner         →  action_plan.json
   └─▶ executor        →  actual provisioning (API/CLI calls)
   └─▶ validator       →  drift_results.json
   └─▶ llm-adapter     →  explanations, semantic mapping (optional)
   └─▶ reporter        →  validation_report.md / report.json
```

LLM is used only for semantic mapping and explanation — never for state decisions.

## Public-safe principles

- No real endpoints, tokens, or customer identifiers in this repository
- All fixtures and samples use generic placeholder values
- Real S2D files must never be committed

## Development

```bash
# Install dependencies (none required for scaffold)
python -m pytest tests/ -v
```

## Skills

Claude Code skill definitions live in `.claude/skills/`:

| Skill | Purpose |
|-------|---------|
| `s2d-parser` | Parse S2D Excel into desired-state JSON |
| `desired-state-schema` | Schema definitions and validation |
| `provisioning-planner` | Deterministic action planning |
| `drift-validator` | Drift detection and comparison |
| `report-generator` | Markdown and JSON report rendering |
| `llm-adapter` | Isolated LLM interface (no-op by default) |
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README with project purpose and public-safe principles"
```

---

## Self-Review

**Spec coverage check:**
- [x] 6 skill directories → Tasks 1–3 cover all 6 (3 new/filled + 3 unchanged)
- [x] `src/` package structure → Task 4 covers all 6 subpackages
- [x] `tests/` structure → Task 5 covers fixtures + 3 stub tests
- [x] README → Task 6
- [x] No real company info → all fixtures use `example-*` placeholders
- [x] LLM isolation → `llm-adapter` skill + `src/llm/` interface

**Placeholder scan:** No "TBD", "TODO", or vague steps — every step has the exact file content.

**Type consistency:**
- `ParseResult = dict[str, Any]` defined in `src/parser/__init__.py` — not referenced by other stubs yet (intentional at scaffold stage)
- `LLMAdapter` ABC defined in `src/llm/__init__.py`, `NoOpAdapter` implements it
- Fixture keys (`tgw`, `firewall`, `vm`, `nsxt_dfw`) consistent across all three fixture files
