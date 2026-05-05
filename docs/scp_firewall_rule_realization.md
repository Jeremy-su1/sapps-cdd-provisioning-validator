# SCP Firewall Rule Realization Design

**Version:** 1.0  
**Module:** `src/transforms/scp_firewall_realizer.py`  
**Input:** enriched TGW candidates from `classify_candidates()`  
**Output:** four categorized rule sets per candidate  

---

## 1. Purpose

The realization layer converts enriched TGW firewall candidates into execution-ready SCP firewall rule dicts. It is the final preparation step before executor calls.

The realizer:
- **does not call any API**
- **does not mutate** the input candidates
- **is fully deterministic** — same input always produces the same output
- **does not enforce human approval** — that is the planner's responsibility

---

## 2. Input Shape

Each input candidate is an enriched TGW entry produced by `classify_candidates()`:

```json
{
  "origin_idx":         0,
  "source_ip":          "10.83.214.11",
  "target_ip":          "192.168.251.45",
  "protocol":           "TCP",
  "port":               "80,443,3200-3399",
  "port_expression":    true,
  "action":             "permit",
  "src_endpoint_class": "internal",
  "tgt_endpoint_class": "customer_external",
  "src_is_cidr":        false,
  "tgt_is_cidr":        false,
  "requires_manual_review": false
}
```

---

## 3. Output Categories

| Category | Meaning | Auto-provisionable |
|---|---|---|
| `direct_create` | One rule, zero splitting needed | Yes (after human approval) |
| `split_create` | One candidate expands to N rules by port splitting | Yes (after human approval) |
| `reference_only` | Candidate is logged but not realized | No |
| `unsupported` | Port expression is malformed or technically incompatible | No |

---

## 4. Port Expression Handling

### 4.1 Port Normalization

Before categorizing, every port expression is normalized:
- `~` is replaced with `-` (tilde is a non-standard range separator observed in workbooks)
- Each comma-separated token is stripped of surrounding whitespace

### 4.2 Token Types After Normalization

| Raw expression | Normalized tokens | Kind |
|---|---|---|
| `"443"` | `["443"]` | `single` |
| `"3200-3399"` | `["3200-3399"]` | `range` |
| `"5000~5999"` | `["5000-5999"]` | `range` (after normalization) |
| `"1128,1129"` | `["1128", "1129"]` | `multi` |
| `"80,443,3200-3399"` | `["80", "443", "3200-3399"]` | `multi` |
| `"80,5000~5999"` | `["80", "5000-5999"]` | `multi` (after normalization) |
| `None` / `""` | `[]` | `empty` |
| `"not-a-port"` | `[]` | `malformed` |

### 4.3 Realization Decision by Port Kind

| Port kind | Realization |
|---|---|
| `single` | `direct_create` — one rule as-is |
| `range` | `direct_create` — one rule, range notation preserved |
| `multi` | `split_create` — one rule per token |
| `empty` | `reference_only` (reason: `no_port_defined`) |
| `malformed` | `unsupported` (reason: `malformed_port_expression`) |

### 4.4 Range Notation Semantics

A range like `"3200-3399"` is treated as a single port range token. The SCP API is expected to support port ranges natively. The realizer does **not** expand ranges into individual port numbers — doing so would generate hundreds of rules and is never correct at the policy level.

---

## 5. Endpoint Handling

### 5.1 Both Endpoints Unknown → `reference_only`

If both `src_endpoint_class` and `tgt_endpoint_class` are `"unknown"`, the rule cannot be meaningfully realized. It is emitted as `reference_only` with reason `unknown_both_endpoints`. This check takes priority over port parsing.

### 5.2 CIDR Sources and Targets

CIDR notation (`src_is_cidr`, `tgt_is_cidr`) does **not** affect the realization category by itself. A CIDR-source rule with a single port is still `direct_create`. The CIDR flag is preserved in the realized rule for the executor to handle correctly.

The SCP API is expected to accept CIDR notation in source/target fields. If a future executor discovers this is not supported, that is an executor-level concern — not a realizer concern.

### 5.3 One Endpoint Unknown

If only one endpoint is unknown but the other is resolved, the rule is still realizable. The unknown endpoint is preserved as-is in the realized rule. A human reviewer can confirm the IP before execution.

---

## 6. Realized Rule Shape

Each execution-ready rule produced by the realizer has the following shape:

```json
{
  "realized_rule_id":            "scp-fw-0-p2",
  "origin_idx":                  0,
  "origin_resource_id":          "scp-fw-0",
  "source_ip":                   "10.83.214.11",
  "source_is_cidr":              false,
  "target_ip":                   "192.168.251.45",
  "target_is_cidr":              false,
  "protocol":                    "TCP",
  "port":                        "3200-3399",
  "port_original":               "80,443,3200-3399",
  "action":                      "permit",
  "backend_hint":                "scp",
  "execution_method_candidates": ["scp_api", "scp_cli"],
  "src_endpoint_class":          "internal",
  "tgt_endpoint_class":          "customer_external"
}
```

`realized_rule_id` format: `scp-fw-{origin_idx}-p{port_index}`.  
For `direct_create` rules, `port_index` is always `0`.

---

## 7. Realization Logic (Decision Order)

```
for each candidate:
  1. if src_endpoint_class == "unknown" AND tgt_endpoint_class == "unknown":
       → reference_only (reason: unknown_both_endpoints)
       continue

  2. parse_port_expression(candidate.port) → (tokens, kind)

  3. if kind == "empty":
       → reference_only (reason: no_port_defined)
       continue

  4. if kind == "malformed":
       → unsupported (reason: malformed_port_expression)
       continue

  5. if kind in ("single", "range"):
       → direct_create (one realized rule with tokens[0] as port)

  6. if kind == "multi":
       → split_create (one realized rule per token)
```

---

## 8. `split_create` Output Structure

Each `split_create` group preserves the link between the original candidate and its derived rules:

```json
{
  "origin_idx":          0,
  "origin_resource_id":  "scp-fw-0",
  "port_original":       "80,443,3200-3399",
  "rules": [
    { "realized_rule_id": "scp-fw-0-p0", "port": "80",       ... },
    { "realized_rule_id": "scp-fw-0-p1", "port": "443",      ... },
    { "realized_rule_id": "scp-fw-0-p2", "port": "3200-3399", ... }
  ]
}
```

---

## 9. Observed Results (Real Workbook)

| Category | Candidates | Realized rules |
|---|---|---|
| `direct_create` | 8 | 8 |
| `split_create` | 102 | ≫ 102 (varies per expression) |
| `reference_only` | 0 | — |
| `unsupported` | 0 | — |

All 110 TGW candidates from the real workbook are realizable. The `reference_only` and `unsupported` categories are guarded paths for data quality issues not present in this workbook.

---

## 10. Not In Scope

| Concern | Where it belongs |
|---|---|
| Human approval before execution | Planner (`requires_manual_review` + conflict tracking) |
| Port range expansion to individual ports | Never — subnet-level policies use ranges |
| CIDR validation against SCP API capabilities | Executor layer |
| Protocol-specific validation (e.g., ICMP has no ports) | Pre-flight validation (future) |
| Action other than `"permit"` | Future (deny rules not in current S2D workbook) |
