# SCP Firewall First Apply Test

The smallest safe real-create test that can be executed once the provisioning path is implemented.

> **Status:** Create execution is not yet implemented (`POST /v1/firewalls/rules` is not wired). This document defines the test plan so it can be executed immediately when the executor is added. No new code is written here.

---

## Scope and Safety Constraints

This test is intentionally as small and reversible as possible:

- **One rule only** — not a full workbook batch
- **Non-production TGW firewall only** — must target a sandbox or dev environment
- **Specific IPs only** — no wildcards (`0.0.0.0/0`), no CIDR ranges wider than /32
- **No real traffic impact** — source and destination must be test IPs that carry no production load
- **Delete immediately after validation** — the rule is treated as a verification artifact, not a persistent change

---

## Preconditions

All must be satisfied before creating a rule.

### Environment

- [ ] Read-only test plan has passed completely (see `scp_firewall_readonly_test_plan.md`)
- [ ] `actual_rules` from Script 1 collected successfully — baseline rule set is known
- [ ] Baseline output archived: `cp outputs/debug_scp_firewall_actual_real.json outputs/baseline_before_apply.json`
- [ ] Target firewall ID identified (from the baseline output `"firewall_id"` field in a sample rule)
- [ ] Target firewall is **not** a production TGW firewall — verified in SCP Console

### IAM

- [ ] Access Key has **write** permission on the target firewall (`firewall:rule:create`)
- [ ] Write permission is scoped to the test project or test firewall only, not project-wide

### Test Rule Definition

Choose a rule that will never match real traffic:

```json
{
  "firewall_id":          "<target-test-firewall-id>",
  "name":                 "prov-validator-test-001",
  "description":          "provisioning validator smoke test — delete after verification",
  "action":               "ALLOW",
  "direction":            "INBOUND",
  "source_address":       ["192.0.2.1"],
  "destination_address":  ["192.0.2.2"],
  "service": [
    { "service_type": "TCP", "service_value": "9999" }
  ],
  "sequence":             9999
}
```

IP range `192.0.2.0/24` is reserved for documentation (RFC 5737) and will never carry real traffic.
Port `9999` is not a standard service port.
Sequence `9999` places the rule at the end of the policy list, minimizing traffic impact.

---

## Execution Steps

### Step 1 — Capture baseline

```bash
SCP_ENDPOINT="https://firewall.{region}.{env}.samsungsdscloud.com" \
SCP_ACCESS_KEY="<access-key>" \
SCP_SECRET_KEY="<secret-key>" \
python scripts/debug_scp_firewall_actual_real.py

cp outputs/debug_scp_firewall_actual_real.json outputs/baseline_before_apply.json
```

Record:
- Total rule count before apply: `actual_count = N`
- Target firewall ID: `<firewall-id>`

---

### Step 2 — Create the test rule

When the executor is implemented, the create call will be:

```
POST /v1/firewalls/rules
Content-Type: application/json
<HMAC-signed headers>

{
  "firewall_id":          "<target-test-firewall-id>",
  "name":                 "prov-validator-test-001",
  "description":          "provisioning validator smoke test — delete after verification",
  "action":               "ALLOW",
  "direction":            "INBOUND",
  "source_address":       ["192.0.2.1"],
  "destination_address":  ["192.0.2.2"],
  "service": [{ "service_type": "TCP", "service_value": "9999" }],
  "sequence":             9999
}
```

Expected response: `HTTP 200` or `201` with a response body containing the assigned `id`.

Record the assigned rule ID from the response: `<created-rule-id>`

---

### Step 3 — Read back and verify

Re-run collection immediately after create:

```bash
SCP_ENDPOINT="..." SCP_ACCESS_KEY="..." SCP_SECRET_KEY="..." \
python scripts/debug_scp_firewall_actual_real.py
```

**Checkpoint — rule appeared:**
- [ ] `actual_count` increased by exactly 1 (now `N + 1`)
- [ ] The new rule appears in `outputs/debug_scp_firewall_actual_real.json` with:
  - `source_ip: "192.0.2.1"`
  - `target_ip: "192.0.2.2"`
  - `protocol: "TCP"`
  - `port: "9999"`
  - `action: "permit"` (normalized from `ALLOW`)
  - `resource_id: "<created-rule-id>"`
- [ ] All other rules are unchanged compared to the baseline

---

### Step 4 — Validate against realized rules

```bash
SCP_ENDPOINT="..." SCP_ACCESS_KEY="..." SCP_SECRET_KEY="..." \
python scripts/debug_scp_firewall_validate_realized_real.py samples/your_workbook.xlsx
```

If the test rule IP/port is present in the workbook's `SecurityGroup` sheet, it will appear in `matched`. If not, it will appear in `unexpected` — which is the expected outcome for a synthetic test rule.

**Checkpoint:**
- [ ] `matched` count equals the expected number from the workbook
- [ ] The synthetic test rule (`192.0.2.1 → 192.0.2.2 TCP 9999`) appears in `unexpected` (it is not from the workbook)
- [ ] No existing matched rules disappeared

---

### Step 5 — Rollback (delete the test rule)

Delete the created rule immediately after verification:

```
DELETE /v1/firewalls/rules/{created-rule-id}
<HMAC-signed headers>
```

Expected response: `HTTP 200` or `204`.

---

### Step 6 — Verify rollback

Re-run collection:

```bash
SCP_ENDPOINT="..." SCP_ACCESS_KEY="..." SCP_SECRET_KEY="..." \
python scripts/debug_scp_firewall_actual_real.py
```

**Checkpoint — rule is gone:**
- [ ] `actual_count` returned to `N` (original baseline count)
- [ ] No rule with `source_ip: "192.0.2.1"` appears in the output

If the count does not return to `N`, the delete failed — investigate via SCP Console before proceeding to any further apply operations.

---

## Failure Modes and Response

| Failure point | Response |
|---------------|----------|
| Step 2 returns HTTP 403 | Check IAM write permissions; do not retry |
| Step 2 returns HTTP 4xx (not 403) | Log the response body; check firewall_id is correct and the rule body is valid |
| Step 3 count does not increase | API accepted the call but the rule is not visible; wait 5 seconds and re-poll; escalate if still missing |
| Step 3 count increased by more than 1 | Duplicate creates occurred; delete all rules matching `name: "prov-validator-test-001"` |
| Step 5 delete returns HTTP 404 | Rule was already deleted or ID was wrong; verify via re-collection |
| Step 6 count does not return to N | Delete did not take effect; escalate to manual cleanup via SCP Console |

**Abort condition:** If any step fails and the rule is still present after two delete attempts, stop all provisioning activity and escalate. Do not proceed to bulk apply with an unresolved test artifact in the environment.

---

## What This Test Proves

| Claim | Verified by |
|-------|-------------|
| HMAC auth signing is correct | HTTP 200 on create (Step 2) |
| Create payload structure is accepted | HTTP 200 on create (Step 2) |
| Collector normalizes newly created rules correctly | `source_ip`, `target_ip`, `protocol`, `port`, `action` all correct in Step 3 |
| Delete returns the environment to its original state | Count returns to N in Step 6 |
| Validation pipeline handles unexpected rules gracefully | Synthetic rule appears in `unexpected`, not as an error, in Step 4 |

Passing this test end-to-end proves the create + read-back + delete cycle is safe before any workbook-driven bulk provisioning is attempted.

---

## Gate: Before Bulk Apply

Do not proceed to workbook-driven bulk provisioning until:

1. This first apply test passes completely (Steps 1–6 all green)
2. The `missing` count in Step 4 matches the expected count from the workbook
3. An explicit sign-off has been given for the target environment
4. A dry-run preview of all rules to be created has been reviewed and approved

Bulk apply is outside the current implementation scope and will be documented separately when the executor is built.
