# SCP Firewall Read-Only Test Plan

Safe execution procedure for both read-only debug scripts. Run in this exact order: dry-run first, then live.

---

## Script 1 — `debug_scp_firewall_actual_real.py`

**Purpose:** Verify Phase 1 (list TGW firewalls) and Phase 2 (list rules per firewall) are working against the real SCP API.

### Step 1 — Dry-run (always first)

```bash
python scripts/debug_scp_firewall_actual_real.py
```

**Expected output:**

```
============================================================
SCP Firewall Actual State Collector
============================================================
Mode:  dry_run=True  (no API calls — returns empty list)
       Set SCP_ENDPOINT, SCP_ACCESS_KEY, SCP_SECRET_KEY to run live

[Collection Result]
  Actual rules collected: 0

Written: outputs/debug_scp_firewall_actual_real.json
```

**Verify `outputs/debug_scp_firewall_actual_real.json`:**

```json
{
  "dry_run": true,
  "endpoint": null,
  "actual_count": 0,
  "error": null,
  "actual_rules": []
}
```

If this fails, the Python path or import chain is broken. Fix before proceeding.

---

### Step 2 — Auth header verification (credentials only, no live call)

Run with credentials but confirm the HMAC headers look correct before making real API calls:

```bash
SCP_ENDPOINT="https://firewall.{region}.{env}.samsungsdscloud.com" \
SCP_ACCESS_KEY="<access-key>" \
SCP_SECRET_KEY="<secret-key>" \
python scripts/debug_scp_firewall_actual_real.py
```

The script prints auth header samples before collection:

```
[Auth headers sample]
  Scp-Accesskey:   <your-access-key>
  Scp-Timestamp:   1700000000000
  Scp-Api-Version: firewall 1.0
  Scp-Signature:   abc123...  (first 20 chars)
```

**Checkpoints:**
- [ ] `Scp-Accesskey` matches the value you set (first 6 chars visible)
- [ ] `Scp-Timestamp` is a 13-digit millisecond epoch (not seconds)
- [ ] `Scp-Signature` is a non-empty base64 string
- [ ] `Scp-Api-Version` is `firewall 1.0`

If `Scp-Accesskey` is blank, the env var was not exported correctly.

---

### Step 3 — Live collection

If Step 2 looks correct, the same command proceeds to live collection.

**Expected success output:**

```
Mode:  live API
       Endpoint:    https://firewall.{region}.{env}.samsungsdscloud.com
       Access key:  abc123...

[Auth headers sample]
  ...

[Collection Result]
  Actual rules collected: N
  Protocols: {'TCP': N1, 'UDP': N2, ...}
  Actions:   {'permit': N3, 'deny': N4}

  Sample rules (up to 3):
    <resource_id>                   src=<source_ip>       dst=<target_ip>       TCP    port=443  action=permit
    ...

Written: outputs/debug_scp_firewall_actual_real.json
```

**Verify `outputs/debug_scp_firewall_actual_real.json`:**

- `"dry_run": false`
- `"actual_count"` > 0 if TGW firewalls with rules exist in the project
- `"actual_count"` == 0 is valid if the project has no TGW firewalls
- `"error": null` — no error field

---

### Troubleshooting — Script 1

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| `[CollectorError] SCP API request failed: HTTP 401` | Wrong credentials or malformed HMAC | Re-check `SCP_SECRET_KEY`; confirm message format is `METHOD+PATH+TIMESTAMP+ACCESS_KEY` |
| `[CollectorError] SCP API request failed: HTTP 403` | IAM permissions missing | Add firewall read policy in SCP Console IAM |
| `[CollectorError] … Name or service not known` | Endpoint DNS not resolving | Check `SCP_ENDPOINT` format; run `nslookup firewall.{region}.{env}.samsungsdscloud.com` |
| `[CollectorError] … timed out` | Network blocked | Check outbound HTTPS (port 443) to `*.samsungsdscloud.com` |
| `actual_count: 0` and no error | No TGW firewalls in the project | Verify the target project has TGW-type firewalls via SCP Console |
| Output JSON has rules but all `source_ip: null` | API response field changed | Inspect `"actual_rules"[0]` raw structure in the JSON; update `normalize_rule()` if field names differ |
| `Scp-Api-Version` rejected | Version string wrong | Check official docs; currently `"firewall 1.0"` |

---

## Script 2 — `debug_scp_firewall_validate_realized_real.py`

**Purpose:** Run the full pipeline — parse workbook → classify → realize → collect actual → validate — and compare desired vs actual.

### Step 1 — Dry-run

```bash
python scripts/debug_scp_firewall_validate_realized_real.py samples/your_workbook.xlsx
```

(Omit path to use the first `.xlsx` in `samples/` automatically.)

**Expected output:**

```
======================================================================
SCP Firewall: Realized Rules vs Actual State
======================================================================

[1] Opening workbook: your_workbook.xlsx

[2] Realization summary
    total_candidates:    N
    total_realized_rules:N
    direct_create:       N
    split_create groups: N  rules: N
    reference_only:      N
    unsupported:         N

[3] Collecting actual SCP Firewall state
    Mode: dry_run=True  (set SCP_ENDPOINT, SCP_ACCESS_KEY, SCP_SECRET_KEY for live)
    actual_rules collected: 0

[4] Validation summary  (content key: source_ip, target_ip, protocol, port)
    realized_rules: N
    actual_rules:   0
    matched:        0
    missing:        N  (realized but not found in actual)
    unexpected:     0  (actual but not in realized)

Written: outputs/debug_scp_firewall_validate_realized_real.json
```

**Checkpoint:** `realized_rules` must be > 0. If it is 0, the workbook has no TGW firewall rule candidates. Check that:
- The `SecurityGroup` sheet has valid rows
- At least one candidate is classified as a TGW candidate (not all `reference_only` or `unsupported`)

---

### Step 2 — Live validation

```bash
SCP_ENDPOINT="https://firewall.{region}.{env}.samsungsdscloud.com" \
SCP_ACCESS_KEY="<access-key>" \
SCP_SECRET_KEY="<secret-key>" \
python scripts/debug_scp_firewall_validate_realized_real.py samples/your_workbook.xlsx
```

**Expected section `[3]`:**

```
[3] Collecting actual SCP Firewall state
    Mode: live API  endpoint='https://firewall.{region}.{env}.samsungsdscloud.com'
    actual_rules collected: N
    protocols: {'TCP': N1, ...}
    actions:   {'permit': N2, ...}
```

**Expected section `[4]` — first run against an unprovisioned environment:**

```
[4] Validation summary
    realized_rules: N
    actual_rules:   M
    matched:        0
    missing:        N  (realized but not found in actual)
    unexpected:     M  (actual but not in realized)
```

This is the expected baseline state before any rules have been applied from the workbook.

**Expected after provisioning is complete:**

```
matched:        N
missing:        0
unexpected:     M   (rules that exist in SCP but are not in the workbook — expected for pre-existing rules)
match_rate:     100.0%
```

---

### Interpreting Validation Results

| Result | Meaning |
|--------|---------|
| `matched > 0` | Rules from the workbook exist in SCP with matching source_ip, target_ip, protocol, port |
| `missing > 0` | Workbook rules not yet in SCP — provisioning is incomplete or rules haven't been applied |
| `unexpected > 0` | Rules in SCP not derived from this workbook — expected for pre-existing manual rules; investigate if high count is surprising |
| `match_rate = 100%` | All realized rules are present in SCP; provisioning is complete from this workbook's perspective |

Note: `unexpected` is not an error. It means SCP has rules from other sources (manual, other workbooks, platform defaults). Only investigate `unexpected` if you expect a clean slate.

---

### Troubleshooting — Script 2

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| `FileNotFoundError: No .xlsx file found in samples/` | No workbook in `samples/` | Pass explicit path: `python scripts/... path/to/workbook.xlsx` |
| `realized_rules: 0` | Workbook has no TGW candidates | Check `SecurityGroup` sheet; run `debug_scp_firewall_realization.py` to inspect classification |
| `matched: 0` after live collection | Workbook rules not yet provisioned, or content key mismatch | Inspect `"missing"` entries in the JSON; compare `source_ip`/`target_ip` against what SCP returns |
| `actual_rules: 0` with no error | Project has no TGW firewalls | Confirm firewall exists via SCP Console; check `product_type` filter |
| High `unexpected` count | Many pre-existing rules in SCP | Review `"unexpected"` entries in JSON; this is informational, not a failure |
| `KeyError` during realization | Workbook structure changed | Re-run `debug_parse_introspection.py` to confirm all sheets parsed |

---

## Output Files

| File | When written | Key fields |
|------|-------------|-----------|
| `outputs/debug_scp_firewall_actual_real.json` | After Script 1 | `dry_run`, `actual_count`, `error`, `actual_rules[]` |
| `outputs/debug_scp_firewall_validate_realized_real.json` | After Script 2 | `dry_run`, `realization_summary`, `validation_summary`, `matched[]`, `missing[]`, `unexpected[]` |

Both files are overwritten on each run. Archive them if you need to compare runs across environments or dates.
