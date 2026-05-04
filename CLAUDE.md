# CLAUDE.md

## Project Overview

This repository is a generic scaffold for an SAP PS(Premium Supplier) S2D-driven infrastructure onboarding automation system in SCP.

The project goal is to convert standard S2D Excel documents into executable desired-state definitions, provision selected infrastructure resources, validate the actual state against the desired state, and support incremental add-on changes.

This public repository must remain generic and safe for open publication.
Do not include company-confidential values, customer-specific payloads, real endpoints, credentials, or proprietary naming conventions.

---

## Current MVP Scope

The current MVP scope is intentionally limited to the following onboarding layers and resources:

1. TGW-related provisioning and validation
2. Firewall provisioning and validation
3. VMware VM provisioning and validation
4. NSX-T Distributed Firewall provisioning and validation

The MVP must support three modes:

- Provision mode
- Validation mode
- Incremental add-on change mode

Do not expand scope unless explicitly requested.

---

## Core Architecture Principles

The system follows this flow:

1. Parse S2D Excel
2. Build normalized desired-state JSON
3. Generate deterministic provisioning plan
4. Execute create/read operations via API or CLI
5. Collect actual state
6. Compare desired state vs actual state
7. Use LLM only for semantic mapping, explanation, severity support, and change intent parsing
8. Render machine-readable and human-readable reports

---

## Non-Negotiable Rules

### Deterministic truth first
All provisioning, validation, and drift detection logic must be deterministic.
Truth must come from explicit schema validation and rule-based comparison.

### LLM is not the source of truth
Use LLM only for:
- semantic term mapping
- explanation generation
- severity wording support
- human-readable correction guidance
- natural-language change request interpretation

Do not let LLM directly decide destructive or state-changing actions.

### Safety first
Never auto-execute destructive actions.
Never generate delete operations unless explicitly requested and clearly isolated.
Always support dry-run or planning-first workflow before real execution.

### Minimal, surgical changes
Prefer minimal changes over broad rewrites.
Do not redesign the whole repository when a targeted implementation is sufficient.

### Schema stability
Keep desired-state keys stable once defined.
If schema changes are required, update fixtures and regression tests together.

### Public repository constraints
This repository must not contain:
- real company endpoints
- real authentication values
- customer-specific identifiers
- actual S2D files
- real firewall rules
- real infrastructure topology values

Use placeholders, mocks, and generic examples only.

---

## Engineering Style

### Think before coding
Before writing code:
- identify inputs
- identify outputs
- identify dependencies
- identify what must remain deterministic
- propose a small plan first

### Simplicity first
Prefer:
- plain Python
- explicit JSON schemas
- small adapters
- testable helper functions

Avoid over-engineering, unnecessary frameworks, and premature abstractions.

### Plan before execution
For non-trivial work:
1. summarize the task
2. propose a short implementation plan
3. identify assumptions
4. then implement

### Evidence over claims
When validating or comparing infrastructure state, always show evidence fields and comparison basis.

---

## Project-Specific Implementation Rules

### Desired State
Desired state must be normalized JSON derived from S2D Excel.
It should be cleanly separated from actual collected state.

### Provisioning
Provisioning should be driven by a planner that emits action items such as:
- create
- update
- skip
- conflict

Provisioning must not be mixed directly with parsing logic.

### Validation
Validation must compare:
- desired state
- actual state
- comparison rules

Comparison categories should be separated into:
- exact match
- structural match
- semantic match

### LLM Layer
LLM calls must be isolated behind an interface.
The system must still work in a reduced mode without LLM.

### Reporting
Reports must support at least:
- JSON output
- Markdown output

Markdown reports should be concise, auditable, and operator-friendly.

---

## Expected Outputs

Common outputs include:
- desired_state.json
- actual_state.json
- action_plan.json
- drift_results.json
- validation_report.md

---

## Testing Expectations

Every parser, planner, and validator change should be covered by fixture-based tests where possible.

At minimum, support:
- one parser fixture
- one planner fixture
- one drift validation fixture

If schemas change, update sample fixtures and tests together.

---

## Session Guidance for Claude

When working in this repository:

1. Read this file first
2. Check relevant skill instructions under `.claude/skills/`
3. Keep changes minimal and modular
4. Prefer deterministic logic before LLM usage
5. Ask for missing assumptions only when truly necessary
6. Preserve public-safe generic implementation style