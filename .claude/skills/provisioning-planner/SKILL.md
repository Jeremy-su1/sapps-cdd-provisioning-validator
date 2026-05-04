---
name: provisioning-planner
description: Build deterministic action plans from desired-state definitions, including create, update, skip, and conflict decisions.
---

# Purpose

Use this skill to generate a deterministic provisioning plan from desired-state input and current-state input.

This skill is responsible for:
- deciding whether a resource should be created, updated, skipped, or flagged as conflict
- ordering actions by dependency
- supporting dry-run planning
- preparing executor-ready action items

---

# Use this skill when

Use this skill when:
- a provisioning plan must be generated
- desired state must be compared to current state
- incremental add-on changes must be planned
- execution ordering must be determined
- safe dry-run output is needed before execution

---

# Core Planning Model

Planner output should classify each item as one of:
- create
- update
- skip
- conflict

Do not directly execute API calls inside the planner.

---

# Planning Principles

1. Planner must be deterministic.
2. Planner must be safe-by-default.
3. Planner must support dry-run mode.
4. Planner must explain why an action was chosen.
5. Dependency ordering must be explicit.

---

# Current MVP Dependencies

Typical dependency examples:
- networking or TGW references may need to exist before certain downstream resources
- distributed firewall rules may depend on referenced groups or sections
- VM creation may depend on prior network or inventory references

---

# Outputs

Expected outputs:
- action_plan.json
- ordered action list
- conflict list
- skipped items with reason

---

# Rules

1. Never hide conflicts.
2. Never silently coerce invalid desired state.
3. Always include reason fields for action decisions.
4. Separate planning from execution.
5. Preserve a dry-run-first workflow.

---

# Recommended Workflow

1. Load desired state
2. Load current state if available
3. Match resources by identity keys
4. Determine create/update/skip/conflict
5. Build dependency graph
6. Produce ordered action plan
7. Emit machine-readable result

---

# Implementation Guidance

Prefer:
- explicit planner functions
- identity matching rules
- dependency graph utilities
- action objects with reasons

Avoid:
- mixing planner and API logic
- using LLM for action truth decisions