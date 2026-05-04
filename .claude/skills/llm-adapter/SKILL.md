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

The no-op stub returns the input term unchanged for `map_term`,
an empty string for `explain_drift`, and an empty dict for `parse_change_intent`.

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

# Recommended Workflow

1. Define the LLMAdapter ABC
2. Implement NoOpAdapter as default
3. Inject adapter at the application entry point
4. Optionally implement AnthropicAdapter behind the same interface
5. Log every real LLM call with input and output

---

# Implementation Guidance

Prefer:
- a single LLMAdapter ABC with a NoOpAdapter default
- dependency injection at the application entry point
- a logging wrapper around any real LLM call

Avoid:
- importing the Anthropic SDK outside this module
- calling LLM from validator, planner, or parser directly
- making LLM calls synchronous in hot paths
