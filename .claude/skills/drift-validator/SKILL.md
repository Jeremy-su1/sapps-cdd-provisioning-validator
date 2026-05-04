---
name: drift-validator
description: Compare desired state and actual state to detect exact, structural, and semantic drift.
---

# Purpose

Use this skill to validate infrastructure state after provisioning or during audit mode.

This skill is responsible for:
- comparing desired state vs actual state
- detecting missing, mismatched, extra, or structurally inconsistent items
- classifying drift categories
- producing audit-friendly validation results

---

# Use this skill when

Use this skill when:
- validation mode is requested
- provisioning results must be checked
- actual state has been collected from APIs or CLI
- drift results must be rendered into reports

---

# Drift Categories

Support drift classification such as:
- missing
- mismatch
- extra
- structural_mismatch
- semantic_mismatch

---

# Validation Layers

Validation should distinguish:
- exact match validation
- structural validation
- semantic validation

Truth should come from deterministic comparison.
LLM may be used only to help explain or map ambiguous terminology.

---

# Inputs

Typical inputs:
- desired_state.json
- actual_state.json
- comparison rules
- optional alias mapping tables

---

# Outputs

Expected outputs:
- drift_results.json
- validation summary
- severity-ready findings for explanation layer
- evidence-rich comparison items

---

# Rules

1. Truth comes from rules, not LLM.
2. Every drift item should include evidence.
3. Distinguish clearly between hard mismatch and semantic ambiguity.
4. Do not auto-correct silently.
5. Preserve raw compared values in the result.

---

# Recommended Workflow

1. Match desired resources to actual resources
2. Run exact comparison
3. Run structural comparison
4. Run semantic comparison where needed
5. Record drift findings with evidence
6. Generate validation summary

---

# Implementation Guidance

Prefer:
- explicit comparison functions
- resource-specific validators
- evidence-rich result objects
- fixture-based tests

Avoid:
- overloading one validator with all resource logic
- hiding uncertainty in semantic comparison