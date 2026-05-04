---
name: s2d-parser
description: Parse standard S2D Excel files into normalized desired-state JSON for provisioning and validation.
---

# Purpose

Use this skill to convert fixed-format S2D Excel input into normalized desired-state JSON.

This skill is responsible for:
- reading workbook structure
- validating required sheets/columns
- extracting supported onboarding fields
- building normalized desired-state objects

---

# Use this skill when

Use this skill when:
- the task involves reading an S2D Excel file
- desired-state JSON must be generated
- parser logic must be updated
- S2D workbook structure must be validated
- onboarding data needs to be mapped into provisioning schema

---

# Current MVP Coverage

Only support the current MVP resource categories unless explicitly expanded:

- TGW
- Firewall
- VMware VM
- NSX-T Distributed Firewall

Ignore unsupported sections rather than guessing.

---

# Inputs

Typical inputs:
- S2D Excel workbook
- fixed sheet structure
- required columns
- parser configuration
- mapping tables for generic term normalization

---

# Outputs

Expected outputs:
- normalized desired-state JSON
- parse summary
- list of unsupported or missing fields
- parser validation result

---

# Rules

1. Do not guess sheet names or column names.
2. Validate required sheets and columns first.
3. If required data is missing, mark it explicitly.
4. Keep desired-state keys stable.
5. Separate raw extraction from normalization logic.
6. Unsupported fields must be recorded, not silently ignored.
7. Never embed company-specific real values in public examples.

---

# Recommended Workflow

1. Inspect workbook structure
2. Validate required sheets
3. Validate required columns
4. Extract raw values
5. Normalize into desired-state schema
6. Record missing or ambiguous fields
7. Produce parse summary

---

# Implementation Guidance

Prefer:
- small parser functions per sheet
- explicit field mapping tables
- schema-aware normalization
- fixture-based parser tests

Avoid:
- giant monolithic parser functions
- implicit field guessing
- mixing parser logic with API execution

---

# Example Output Shape

```json
{
  "customer": "placeholder-customer",
  "environment": "prd",
  "resources": {
    "tgw": [],
    "firewall": [],
    "vmware_vm": [],
    "nsxt_dfw": []
  },
  "metadata": {
    "source_file": "example.xlsx",
    "unsupported_sections": []
  }
}
```
