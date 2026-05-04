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
   └─▶ src/parser      →  desired_state.json
   └─▶ src/schema      →  validated desired state
   └─▶ src/planner     →  action_plan.json
   └─▶ src/validator   →  drift_results.json
   └─▶ src/llm         →  explanations, semantic mapping (optional)
   └─▶ src/reporter    →  validation_report.md / report.json
```

LLM is used only for semantic mapping and explanation — never for state decisions.

## Public-safe principles

- No real endpoints, tokens, or customer identifiers in this repository
- All fixtures and samples use generic placeholder values
- Real S2D files must never be committed

## Development

```bash
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
