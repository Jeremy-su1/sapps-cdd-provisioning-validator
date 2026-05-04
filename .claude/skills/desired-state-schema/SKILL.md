---
name: desired-state-schema
description: Define and maintain the normalized desired-state schema for onboarding provisioning and validation.
---

# Purpose

Use this skill to define, refine, and validate the normalized desired-state schema used across:
- parsing
- provisioning
- validation
- reporting

This skill ensures schema consistency and stable keys.

---

# Use this skill when

Use this skill when:
- a new resource type is added
- schema fields are changing
- parser output must be normalized
- executor input contracts are being defined
- validator comparison keys are being formalized

---

# Current MVP Resources

Schema coverage should currently include only:
- TGW
- Firewall
- VMware VM
- NSX-T Distributed Firewall

Do not expand resource coverage without explicit instruction.

---

# Schema Principles

1. Keep keys stable.
2. Prefer explicit nested objects over ambiguous flattened structures.
3. Separate:
   - desired configuration
   - runtime metadata
   - comparison metadata
4. Keep public examples generic.
5. Design schema so it can support:
   - create
   - validate
   - diff
   - report

---

# Required Deliverables

This skill should help produce:
- JSON schema definitions
- canonical example objects
- required vs optional field lists
- field-level normalization rules

---

# Recommended Sections

Each resource schema should define:
- resource_type
- unique identity fields
- provisioning attributes
- validation attributes
- optional metadata

---

# Example Guidance

A VMware VM schema should separate:
- identity: name
- provisioning: cpu, memory, template
- placement: cluster, datastore, network refs
- metadata: source sheet, environment

A firewall schema should separate:
- identity
- source
- destination
- service
- action
- direction
- priority if needed

---

# Rules

1. If schema changes, update parser fixtures and validator fixtures.
2. Do not use inconsistent synonyms for the same field.
3. Prefer canonical key names even if S2D source wording varies.
4. Keep semantic alias handling outside the core schema when possible.

---

# Implementation Guidance

Prefer:
- pydantic models or explicit dataclasses
- resource-specific schema modules
- example fixtures

Avoid:
- schema drift across parser/planner/validator
- implicit fields with unclear ownership