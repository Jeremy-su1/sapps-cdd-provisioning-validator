# Firewall Validator Comparison Design

## Goal

Prevent SCP Firewall and NSX-T DFW validators from reporting a rule as
matched when a managed field differs or is missing from either desired or
actual state.

## Scope

Update only the ID-based firewall validation paths:

- `validate_scp_firewall()`
- `validate_dfw()`

Content-based duplicate matching and planner behavior remain outside this
change.

## Comparison Rules

SCP Firewall validation compares these managed fields:

- `action`
- `port`
- `protocol`
- `source_ip`
- `target_ip`

NSX-T DFW validation compares its existing managed fields:

- `action`
- `port`
- `protocol`

For every managed field, values are considered equal only when
`desired.get(field) == actual.get(field)`. A value present on one side and
missing (`None`) on the other is therefore a divergence.

Fields outside the managed comparison lists are ignored so API metadata does
not create false drift findings.

## Result Contract

The public result structure remains unchanged. Diverged entries continue to
use:

```json
{
  "status": "diverged",
  "diff": {
    "field_name": {
      "desired": "desired value",
      "actual": "actual value"
    }
  }
}
```

Missing rules and unexpected rules retain their current behavior.

## Tests

Add regression tests proving:

- SCP target IP differences are reported as diverged.
- SCP action differences are reported as diverged.
- SCP fields missing from actual state are reported as diverged.
- SCP fields missing from desired state are reported as diverged.
- DFW fields missing from either side are reported as diverged.
- Existing validator tests continue to pass.
