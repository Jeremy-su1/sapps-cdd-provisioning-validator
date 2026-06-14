# sapps-cdd-provisioning-validator

Generic scaffold for S2D-driven infrastructure provisioning and validation on SCP.

## What this is

This repository provides a scaffold and working prototype for converting SAP PS S2D Excel documents
into desired-state definitions, driving SCP API/CLI-based provisioning flows, collecting actual state,
and validating drift against the intended configuration.

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

## Quick start

```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -v
```

## Local runtime setup

The live SCP firewall scripts read credentials from a local `.env` file in the repository root.
This keeps secrets out of the shell history and avoids committing real keys.

For the real validation path, the script expects:

- `SCP_ENDPOINT`
- `SCP_ACCESS_KEY`
- `SCP_SECRET_KEY`
- an `.xlsx` workbook path for the parse/validation flow

1. Copy the template:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your real values:

   ```env
   SCP_ENDPOINT=https://firewall.{region}.{env}.samsungsdscloud.com
   SCP_ACCESS_KEY=your-access-key
   SCP_SECRET_KEY=your-secret-key
   ```

3. Install the runtime dependencies from the repo root:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Run the live validation script with a workbook path:

   ```bash
   python scripts/debug_scp_firewall_validate_realized_real.py samples/your-workbook.xlsx
   ```

   You can also run the read-only collector first:

   ```bash
   python scripts/debug_scp_firewall_actual.py
   ```

If any of the three SCP environment variables are missing, the collector falls back to `dry_run=True` automatically.

## Security note

- Do not commit `.env`.
- Keep `.env` local to your machine.
- Use `.env.example` as the safe template for collaborators.

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
