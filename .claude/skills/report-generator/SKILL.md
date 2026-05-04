---
name: report-generator
description: Generate machine-readable and operator-friendly provisioning and validation reports.
---

# Purpose

Use this skill to render provisioning and validation results into human-readable and machine-readable outputs.

This skill is responsible for:
- summarizing action plan results
- summarizing validation findings
- rendering drift evidence
- producing Markdown and JSON reports

---

# Use this skill when

Use this skill when:
- validation output needs to be rendered
- provisioning results need operator-facing summaries
- drift explanations must be organized
- report templates are being updated

---

# Required Report Types

At minimum support:
- JSON result output
- Markdown report output

Optional later:
- HTML report
- CSV export

---

# Report Principles

1. Reports must be auditable.
2. Reports must preserve evidence.
3. Reports must separate facts from explanations.
4. Reports must clearly distinguish:
   - planned actions
   - executed actions
   - validation findings
   - recommended next actions

---

# Suggested Sections

Provisioning report:
- summary
- planned actions
- executed actions
- failed actions
- next steps

Validation report:
- summary
- compliant items
- drift findings
- evidence
- severity
- operator guidance

---

# Rules

1. Do not hide failures.
2. Do not merge fact and LLM explanation into one ambiguous sentence.
3. Preserve resource identifiers in generic form.
4. Keep Markdown concise and scan-friendly.

---

# Implementation Guidance

Prefer:
- small renderers
- stable templates
- structured input models

Avoid:
- embedding business logic in the renderer
- free-form unstructured report generation