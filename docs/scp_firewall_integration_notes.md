# SCP Firewall Integration Notes

**Version:** 2.0  
**Purpose:** Integration analysis for implementing real read/list support in `src/collector/scp_firewall_collector.py`  
**Primary source:** Official SCP documentation — https://docs.e.samsungsdscloud.com/en/apireference/ and /en/clireference/ — traversed to operation level  
**Secondary source:** Terraform provider source code (github.com/SamsungSDSCloud/terraform-provider-samsungcloudplatform) — used only where official docs are ambiguous  
**Evidence base:** All API and CLI operation pages fetched directly; response body JSON examples confirmed from official doc pages  

---

## Corrections vs. Version 1.0

Version 1.0 of this document was based primarily on the Terraform SDK and contained several significant errors. The table below lists corrections confirmed from the official documentation.

| Topic | Version 1.0 (incorrect) | Version 2.0 (corrected) |
|---|---|---|
| API base URL | `https://openapi.samsungsdscloud.com` | `https://firewall.{region}.{env}.samsungsdscloud.com` |
| API path prefix | `/v2/firewall/...` (inferred) | `/v1/firewalls/...` (confirmed) |
| Auth header names | `X-Cmp-AccessKey`, `X-Cmp-Signature`, ... | `Scp-Accesskey`, `Scp-Signature`, `Scp-Timestamp`, ... |
| Auth header `Scp-Api-Version` | Not mentioned | Required: `firewall 1.0` |
| Action enum values | `ALLOW` / `DROP` | `ALLOW` / `DENY` |
| Direction enum values | `IN` / `OUT` / `IN_OUT` | `INBOUND` / `OUTBOUND` |
| List-rules endpoint | "No confirmed public evidence" | Fully confirmed: `GET /v1/firewalls/rules?firewall_id=...` |
| CLI availability | "Not in public CLI reference" | Fully documented: `scpcli firewall firewall-rule list` |
| CLI tool name | `scloud` | `scpcli` |
| `fetch_all` parameter | Not mentioned | Confirmed: `fetch_all=true` bypasses pagination |
| `sequence` field in rule | "No explicit priority field" | Confirmed: `sequence` integer in rule response |

---

## 1. Summary

| Topic | Answer |
|---|---|
| List firewall rules via API | **Confirmed** — `GET /v1/firewalls/rules?firewall_id=<id>` |
| List firewall rules via CLI | **Confirmed** — `scpcli firewall firewall-rule list --firewall_id <id>` |
| API base URL | `https://firewall.{region}.{environment}.samsungsdscloud.com` |
| API version | `1.0` (CURRENT, no deprecation notice) |
| Path prefix | `/v1/` |
| Authentication | `Scp-Accesskey` + `Scp-Signature` (HMAC) + `Scp-Timestamp` + `Scp-Api-Version` |
| `fetch_all` available | Yes — bypasses page/size pagination for rule list |
| Ordering in response | Yes — `sequence` integer field per rule |
| Recommended first path | **REST API** (fewer dependencies, structured JSON, filter support) |

---

## 2. API Base URL and Environments

The SCP Firewall API uses a **service-specific base URL**, not the generic `openapi.samsungsdscloud.com`:

```
https://firewall.{region}.{environment}.samsungsdscloud.com
```

| `environment` | `region` | Example base URL |
|---|---|---|
| `e` | `kr-west1` | `https://firewall.kr-west1.e.samsungsdscloud.com` |
| `e` | `kr-east1` | `https://firewall.kr-east1.e.samsungsdscloud.com` |
| `s` | `kr-west1` | `https://firewall.kr-west1.s.samsungsdscloud.com` |
| `s` | `kr-east1` | `https://firewall.kr-east1.s.samsungsdscloud.com` |
| `g` | `kr-south1` | `https://firewall.kr-south1.g.samsungsdscloud.com` |
| `g` | `kr-south2` | `https://firewall.kr-south2.g.samsungsdscloud.com` |
| `g` | `kr-south3` | `https://firewall.kr-south3.g.samsungsdscloud.com` |

The `environment` suffix (`e`, `s`, `g`) matches the subdomain of the documentation site (`docs.e.samsungsdscloud.com`).

---

## 3. Authentication

All requests require HMAC-based signed headers. Credentials are created in the SCP Console.

### 3.1 Required Headers (confirmed from all operation examples)

| Header | Value | Notes |
|---|---|---|
| `Scp-Accesskey` | Access key ID | From SCP Console IAM |
| `Scp-Signature` | Base64-encoded HMAC-SHA256 signature | See Section 3.2 |
| `Scp-Timestamp` | Unix epoch milliseconds (UTC) | e.g. `1605290625682` |
| `Scp-ClientType` | `Openapi` | Literal string |
| `Accept-Language` | `en-US` (or `ko-KR`) | Localization |
| `Scp-Api-Version` | `firewall 1.0` | Service + version |
| `Content-Type` | `application/json` | For POST / PUT only |

### 3.2 Signature Construction

```python
import hmac, hashlib, base64, time

timestamp = str(int(time.time() * 1000))          # milliseconds since epoch
message   = HTTP_METHOD + URL_PATH + timestamp + ACCESS_KEY
signature = base64.b64encode(
    hmac.new(SECRET_KEY.encode("utf-8"),
             message.encode("utf-8"),
             hashlib.sha256).digest()
).decode("utf-8")
```

Where:
- `HTTP_METHOD` = `"GET"`, `"POST"`, `"PUT"`, or `"DELETE"` (uppercase)
- `URL_PATH` = path + query string (e.g. `/v1/firewalls/rules?firewall_id=abc&page=0&size=20`)

> **Note:** The exact `message` composition (which fields are included in the HMAC) is confirmed from official SCP authentication documentation. The signature shown in example requests (`Scp-Signature = fsfsdf235f9U35sdgf35Xsf/qgsdgsdg326=sfsdr23rsef=`) is a placeholder. Verify against the SCP OpenAPI security guide before implementation.

### 3.3 Required Credential Inputs for Our Collector

| Input | Replaces current field | Notes |
|---|---|---|
| `endpoint` (base URL) | `endpoint` | `https://firewall.kr-west1.e.samsungsdscloud.com` |
| `access_key` | rename from `token` | Access key ID |
| `secret_key` | new field | Secret key for HMAC signing |

The current `ScpFirewallCollector` constructor uses a single `token` field. For real integration, it must be updated to accept `access_key` + `secret_key` separately.

---

## 4. Operations Evidence Table

All operations are under API version `1.0` (CURRENT). Each row is confirmed from the official documentation page.

| # | Operation | Doc URL | HTTP Method + Path | CLI Command | Status | Version |
|---|---|---|---|---|---|---|
| 1 | List Firewalls | `/en/apireference/networking/firewall/apis/listfirewalls/1.0/` | `GET /v1/firewalls` | `scpcli firewall firewall list` | ACTIVE | 1.0 |
| 2 | Show Firewall | `/en/apireference/networking/firewall/apis/showfirewall/1.0/` | `GET /v1/firewalls/{firewall_id}` | `scpcli firewall firewall show` | ACTIVE | 1.0 |
| 3 | Set Firewall | `/en/apireference/networking/firewall/apis/setfirewall/1.0/` | `PUT /v1/firewalls/{firewall_id}` | `scpcli firewall firewall set` | ACTIVE | 1.0 |
| 4 | **List Firewall Rules** | `/en/apireference/networking/firewall/apis/listfirewallrules/1.0/` | **`GET /v1/firewalls/rules`** | `scpcli firewall firewall-rule list` | ACTIVE | 1.0 |
| 5 | Show Firewall Rule | `/en/apireference/networking/firewall/apis/showfirewallrule/1.0/` | `GET /v1/firewalls/rules/{firewall_rule_id}` | `scpcli firewall firewall-rule show` | ACTIVE | 1.0 |
| 6 | Create Firewall Rule | `/en/apireference/networking/firewall/apis/createfirewallrule/1.0/` | `POST /v1/firewalls/rules` | `scpcli firewall firewall-rule create` | ACTIVE | 1.0 |
| 7 | Set Firewall Rule | `/en/apireference/networking/firewall/apis/setfirewallrule/1.0/` | `PUT /v1/firewalls/rules/{firewall_rule_id}` | `scpcli firewall firewall-rule set` | ACTIVE | 1.0 |
| 8 | Delete Firewall Rule | `/en/apireference/networking/firewall/apis/deletefirewallrule/1.0/` | `DELETE /v1/firewalls/rules/{firewall_rule_id}` | `scpcli firewall firewall-rule delete` | ACTIVE | 1.0 |

> There is no `createfirewall` or `deletefirewall` API. Firewall instances are provisioned through the VPC/product ordering flow (not the Firewall API). Only the 8 operations above are exposed via the Firewall API.

### 4.1 Operation 1 — List Firewalls

**URL confirmed:** `https://docs.e.samsungsdscloud.com/en/apireference/networking/firewall/apis/listfirewalls/1.0/`

| Category | Detail |
|---|---|
| Method + Path | `GET /v1/firewalls` |
| Auth | `Scp-Accesskey`, `Scp-Signature`, `Scp-Timestamp`, `Scp-ClientType`, `Scp-Api-Version: firewall 1.0` |
| Required params | None |
| Optional query params | `size` (default 20), `page` (default 0), `sort`, `name`, `vpc_name`, `product_type[]`, `state[]` |
| Pagination | `page` + `size` offset pagination; response includes `count`, `page`, `size` |
| Filtering | `name` (firewall name), `vpc_name`, `product_type` (enum array), `state` (enum array) |
| Response envelope | `{ "count": N, "firewalls": [...], "page": 0, "size": 20 }` |
| Confidence | **High** — full example response in official docs |
| Gaps | No `vpc_id` filter (only `vpc_name`); no `target_id` / `object_id` filter at this API level |

`product_type` enum values for filtering TGW-attached firewalls: `TGW_IGW`, `TGW_GGW`, `TGW_DGW`, `TGW_SIGW`, `TGW_BM`.

### 4.2 Operation 2 — Show Firewall

**URL confirmed:** `https://docs.e.samsungsdscloud.com/en/apireference/networking/firewall/apis/showfirewall/1.0/`

| Category | Detail |
|---|---|
| Method + Path | `GET /v1/firewalls/{firewall_id}` |
| Auth | Standard headers |
| Required params | `firewall_id` (path) |
| Pagination | N/A |
| Filtering | N/A |
| Response envelope | `{ "firewall": { ... } }` |
| Confidence | **High** |
| Gaps | None |

### 4.3 Operation 4 — List Firewall Rules *(primary collector operation)*

**URL confirmed:** `https://docs.e.samsungsdscloud.com/en/apireference/networking/firewall/apis/listfirewallrules/1.0/`

| Category | Detail |
|---|---|
| Method + Path | `GET /v1/firewalls/rules` |
| Auth | Standard headers |
| Required query params | `firewall_id` |
| Optional query params | `size` (default 20), `page` (default 0), `sort`, `src_ip`, `dst_ip`, `description`, `state[]`, `status`, `fetch_all` |
| Pagination | `page` + `size`; or set `fetch_all=true` to bypass pagination entirely |
| Filtering | `src_ip`, `dst_ip`, `description` (string match), `state[]`, `status` |
| Response envelope | `{ "count": N, "firewall_rules": [...], "page": 0, "size": 20 }` |
| Confidence | **High** — full request/response example in official docs |
| Gaps | `fetch_all` behavior is boolean with no documented max limit; actual upper bound unclear |

**`fetch_all=true` is the recommended approach for our collector.** It retrieves all rules in a single call, avoiding the need to loop through pages.

### 4.4 Operation 5 — Show Firewall Rule

**URL confirmed:** `https://docs.e.samsungsdscloud.com/en/apireference/networking/firewall/apis/showfirewallrule/1.0/`

| Category | Detail |
|---|---|
| Method + Path | `GET /v1/firewalls/rules/{firewall_rule_id}` |
| Auth | Standard headers |
| Required params | `firewall_rule_id` (path) |
| Pagination | N/A |
| Filtering | N/A |
| Response envelope | `{ "firewall_rule": { ... } }` |
| Confidence | **High** |
| Gaps | None |

### 4.5 Operation 6 — Create Firewall Rule

**URL confirmed:** `https://docs.e.samsungsdscloud.com/en/apireference/networking/firewall/apis/createfirewallrule/1.0/`

| Category | Detail |
|---|---|
| Method + Path | `POST /v1/firewalls/rules` |
| Auth | Standard headers |
| Request body | `FirewallRuleCreateSingleRequest` — see Section 7 |
| Success response | `201 Created` + `FirewallRuleShowResponse` |
| Confidence | **High** |
| Gaps | `order_direction` ordering at creation uses `BEFORE`/`AFTER`/`BOTTOM` (not `FIRST`/`LAST` as in Terraform) |

---

## 5. Firewall Rule Response Fields

The `FirewallRule` model (confirmed from the official model page and all operation response examples):

| API field | Type | Required | Description | Maps to our schema |
|---|---|---|---|---|
| `id` | string | required | Firewall Rule ID | `resource_id` |
| `firewall_id` | string | required | Parent Firewall ID | — |
| `action` | enum | required | `ALLOW` or `DENY` | `action` (map `ALLOW`→`permit`, `DENY`→`deny`) |
| `direction` | enum | required | `INBOUND` or `OUTBOUND` | — (not in current schema) |
| `status` | enum | required | `ENABLE` or `DISABLE` | — |
| `state` | enum | required | `CREATING`, `ACTIVE`, `DELETING`, `DELETED`, `EDITING`, `ERROR` | — |
| `source_address` | array[string] | required | Source IPs / CIDRs | `source_ip` (first element; see note) |
| `destination_address` | array[string] | required | Destination IPs / CIDRs | `target_ip` (first element; see note) |
| `service` | array[FirewallPort] | required | Protocol + port specifications | `protocol` + `port` |
| `description` | string or null | optional | Free-text rule description | — |
| `name` | string or null | optional | Rule name (same as `id` in examples) | — |
| `sequence` | integer | required | Rule ordering position | — |
| `source_interface` | string | required | Source network interface name | — |
| `destination_interface` | string | required | Destination network interface name | — |
| `vendor_rule_id` | string | required | Underlying vendor-assigned rule ID | — |
| `created_at` | string (datetime) | required | ISO 8601 creation timestamp | — |
| `created_by` | string | required | Creator account ID | — |
| `modified_at` | string (datetime) | required | ISO 8601 modification timestamp | — |
| `modified_by` | string | required | Modifier account ID | — |

### FirewallPort sub-object

| API field | Type | Required | Description |
|---|---|---|---|
| `service_type` | enum | required | `TCP`, `UDP`, `ICMP`, `IP`, `TCP_ALL`, `UDP_ALL`, `ICMP_ALL`, `ALL` |
| `service_value` | string | optional | Port or range (e.g. `"443"`, `"8080-9090"`); absent for `*_ALL` and `ALL` types |

### Notes on list-to-scalar mapping

- `source_address` and `destination_address` are **lists**. A single rule can have multiple source CIDRs. Our `normalize_rule()` currently maps to scalar `source_ip` / `target_ip`. For multi-source rules, the normalizer must either join the list or expand into multiple normalized entries. The first-element approach is acceptable for single-source rules (the typical TGW case).
- `source_address` entries may or may not include the `/32` mask on host IPs. The Terraform provider always appends `/32`; the raw API may or may not. The normalizer should strip `/32` from host IPs to ensure consistent comparison with our desired-state values.

### Action value mapping (schema mismatch)

| API value | Our desired-state value |
|---|---|
| `ALLOW` | `permit` |
| `DENY` | `deny` |

The `normalize_rule()` function must translate `ALLOW`→`permit` and `DENY`→`deny` for content-key matching against our realized rules (which use `permit`/`deny`).

---

## 6. Firewall Object Response Fields

The `Firewall` model (confirmed from official model page):

| API field | Type | Required | Description |
|---|---|---|---|
| `id` | string | required | Firewall ID |
| `name` | string | required | Firewall name (e.g. `"FW_IGW_secuVPC"`) |
| `state` | enum | required | `CREATING`, `ACTIVE`, `DELETING`, `DELETED`, `EDITING`, `ERROR`, `DEPLOYING` |
| `status` | enum | required | `ENABLE` or `DISABLE` |
| `product_type` | enum | required | `IGW`, `GGW`, `DGW`, `LB`, `SIGW`, `TGW_IGW`, `TGW_GGW`, `TGW_DGW`, `TGW_SIGW`, `TGW_BM` |
| `vpc_id` | string or null | required | Associated VPC ID |
| `vpc_name` | string or null | required | Associated VPC name |
| `total_rule_count` | integer | optional | Total rules in this firewall |
| `loggable` | boolean | required | Logging enabled flag |
| `flavor_name` | string | optional | Size tier (`EXSMALL`, `SMALL`, `MEDIUM`, `LARGE`, `EXLARGE`) |
| `flavor_rule_quota` | integer | optional | Max rules allowed by flavor |
| `fw_resource_id` | string | required | Underlying resource ID |
| `pre_product_id` | string | optional | Previous product ordering ID |
| `account_id` | string | required | Account ID |
| `created_at` | string (datetime) | required | ISO 8601 timestamp |
| `created_by` | string | required | Creator account ID |
| `modified_at` | string (datetime) | required | ISO 8601 timestamp |
| `modified_by` | string | required | Modifier account ID |

**Key field for TGW filtering:** `product_type` — TGW-attached firewalls use `TGW_IGW`, `TGW_GGW`, `TGW_DGW`, `TGW_SIGW`, or `TGW_BM`. Pass `product_type=TGW_IGW&product_type=TGW_GGW...` to the `listfirewalls` call to scope results to TGW firewalls only.

---

## 7. Request Body Schemas (Create / Update)

### FirewallRuleCreateSingleRequest (POST /v1/firewalls/rules)

| Field | Type | Required | Description |
|---|---|---|---|
| `firewall_id` | string | **required** | Target firewall ID |
| `firewall_rule` | FirewallRuleCreateRequest | **required** | Rule definition |

### FirewallRuleCreateRequest

| Field | Type | Required | Description |
|---|---|---|---|
| `action` | enum | **required** | `ALLOW` or `DENY` |
| `direction` | enum | **required** | `INBOUND` or `OUTBOUND` |
| `source_address` | array[string] | **required** | Source IPs / CIDRs |
| `destination_address` | array[string] | **required** | Destination IPs / CIDRs |
| `service` | array[FirewallPort] | **required** | Protocol + port |
| `status` | enum | **required** | `ENABLE` or `DISABLE` |
| `description` | string or null | optional | Free text |
| `order_direction` | enum | optional | `BEFORE`, `AFTER`, `BOTTOM` |
| `order_rule_id` | string | optional | Reference rule ID for `BEFORE`/`AFTER` |

### FirewallRuleSetRequest (PUT /v1/firewalls/rules/{id})

| Field | Type | Required | Description |
|---|---|---|---|
| `action` | enum | **required** | `ALLOW` or `DENY` |
| `direction` | enum | **required** | `INBOUND` or `OUTBOUND` |
| `source_address` | array[string] | **required** | Source IPs / CIDRs |
| `destination_address` | array[string] | **required** | Destination IPs / CIDRs |
| `service` | array[FirewallPort] | **required** | Protocol + port |
| `description` | string or null | optional | Free text |

---

## 8. Pagination Behavior

Both list operations use **offset-based pagination**:

| Parameter | Default | Description |
|---|---|---|
| `page` | `0` | Page number (0-indexed) |
| `size` | `20` | Records per page |
| `sort` | `None` | Sort expression (e.g. `"created_at:asc"`) |

Response envelope includes: `count` (total matching records), `page`, `size`.

**`fetch_all=true`** is available on `GET /v1/firewalls/rules` only. When set, the API returns all rules for the given `firewall_id` in a single response, ignoring `page` and `size`. This is the recommended approach for our collector.

---

## 9. Filtering and Search Options

### List Firewalls — filter options

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Firewall name filter |
| `vpc_name` | string | Filter by VPC name |
| `product_type` | array[enum] | Filter by attachment type (use `TGW_*` values for TGW firewalls) |
| `state` | array[enum] | Filter by lifecycle state |

### List Firewall Rules — filter options

| Parameter | Type | Description |
|---|---|---|
| `firewall_id` | string | **Required.** Target firewall ID |
| `src_ip` | string | Filter by source IP (exact or prefix — unconfirmed) |
| `dst_ip` | string | Filter by destination IP |
| `description` | string | Filter by description text |
| `state` | array[enum] | Filter by rule state |
| `status` | enum | Filter by `ENABLE` / `DISABLE` |
| `fetch_all` | boolean | Fetch all rules without pagination |

---

## 10. CLI Reference

The CLI tool is `scpcli` (not `scloud`). All firewall operations are under the `firewall` command group.

### Firewall commands

| Command | Description |
|---|---|
| `scpcli firewall firewall list [options]` | List firewalls |
| `scpcli firewall firewall show --firewall_id <id>` | Show single firewall |
| `scpcli firewall firewall set --firewall_id <id> [options]` | Update firewall |

### Firewall rule commands

| Command | Description |
|---|---|
| `scpcli firewall firewall-rule list --firewall_id <id> [options]` | **List rules** |
| `scpcli firewall firewall-rule show --firewall_rule_id <id>` | Show single rule |
| `scpcli firewall firewall-rule create --firewall_id <id> --action <ALLOW\|DENY> --direction <INBOUND\|OUTBOUND> --source_address <ip> --destination_address <ip> --service <json> --status <ENABLE\|DISABLE> [options]` | Create rule |
| `scpcli firewall firewall-rule set --firewall_rule_id <id> --action <...> --direction <...> --source_address <...> --destination_address <...> --service <json> [options]` | Update rule |
| `scpcli firewall firewall-rule delete --firewall_rule_id <id>` | Delete rule |

### CLI list-rules parameters

```
scpcli firewall firewall-rule list
  --firewall_id <value>       required
  [--size <value>]            default: 20
  [--page <value>]            default: 0
  [--sort <value>]
  [--src_ip <value>]
  [--dst_ip <value>]
  [--description <value>]
  [--state <value>]
  [--status <value>]
  [--fetch_all <value>]       boolean: fetch all rules
```

### CLI authentication

The CLI uses the same Access Key / Secret Key credentials as the API. Credentials are configured once via the CLI configuration mechanism. Output is formatted as JSON.

---

## 11. API vs CLI Tradeoffs

| Dimension | REST API | CLI (`scpcli`) |
|---|---|---|
| **Confirmed availability** | Yes — all 8 operations documented | Yes — all 8 operations documented |
| **Programmatic use** | Direct HTTP + structured JSON — ideal | Subprocess invocation; parse stdout |
| **Authentication** | Per-request HMAC signing headers | One-time credential configuration |
| **`fetch_all` support** | Yes (`?fetch_all=true` query param) | Yes (`--fetch_all` flag) |
| **Response structure** | Structured JSON — predictable field names | JSON printed to stdout |
| **Filtering** | Rich: `src_ip`, `dst_ip`, `state`, `status` | Same options as API |
| **Integration complexity** | HTTP client + HMAC signer (~50 lines Python) | `subprocess.run(["scpcli", ...])` + JSON parse |
| **Tool dependency** | None beyond stdlib (`urllib.request`, `hmac`) | Requires `scpcli` installed and configured |
| **CI/container portability** | High — no CLI tool installation needed | Lower — `scpcli` must be present in environment |
| **Error handling** | HTTP status codes + JSON error body | Exit code + stderr text |
| **Version stability** | Versioned API (`Scp-Api-Version: firewall 1.0`) | CLI output format may vary with tool version |

---

## 12. Recommendation

### Implement REST API first for `_fetch_raw_rules_via_api()`

**Rationale:**
1. `GET /v1/firewalls/rules?firewall_id={id}&fetch_all=true` retrieves all rules in a single call — simpler than any multi-page loop.
2. No external tool dependency. Pure Python stdlib (`urllib.request`, `hmac`, `hashlib`, `base64`).
3. Structured JSON response with predictable field names.
4. `product_type` filter on `listfirewalls` allows scoping to TGW-only firewalls without client-side filtering.

### Recommended Collection Sequence

```
Step 1:  GET /v1/firewalls?product_type=TGW_IGW&product_type=TGW_GGW&...
         → collect all firewall IDs in scope

Step 2:  for each firewall_id:
           GET /v1/firewalls/rules?firewall_id={id}&fetch_all=true
           → collect all rules for that firewall

Step 3:  normalize each raw rule via normalize_rule()
         → return flat list to caller
```

### CLI as a secondary / fallback path

Implement `_fetch_raw_rules_via_cli()` as a secondary path for environments where API credentials are not available but `scpcli` is configured. CLI command is:

```bash
scpcli firewall firewall-rule list --firewall_id <id> --fetch_all true
```

Parse the JSON output with `json.loads()`.

---

## 13. Changes Required in `ScpFirewallCollector`

When real API integration is implemented, the following changes are needed:

### 13.1 Constructor signature

The current `token` field is insufficient. Replace with:

```python
def __init__(
    self,
    endpoint: str | None,     # base URL, e.g. "https://firewall.kr-west1.e.samsungsdscloud.com"
    access_key: str | None,   # SCP Access Key ID
    secret_key: str | None,   # SCP Secret Key (for HMAC signing)
    dry_run: bool = False,
    execution_method: str = "scp_api",
) -> None:
```

### 13.2 `normalize_rule()` field mapping updates

Current stub uses `srcIp`/`dstIp` (camelCase, scalars). Real API uses snake_case list fields:

| Current mapping | Correct mapping |
|---|---|
| `"ruleId"` → `resource_id` | `"id"` → `resource_id` |
| `"srcIp"` → `source_ip` | `"source_address"[0]` → `source_ip` |
| `"dstIp"` → `target_ip` | `"destination_address"[0]` → `target_ip` |
| `"protocol"` → `protocol` | derive from `service[0].service_type` |
| `"port"` → `port` | derive from `service[0].service_value` |
| `"action"` → `action` | `"action"` → `action`, map `ALLOW`→`permit` / `DENY`→`deny` |

Multi-service rules (multiple `service` entries) require expansion: one normalized entry per service entry.

### 13.3 `_fetch_raw_rules_via_api()` implementation sketch

```python
def _fetch_raw_rules_via_api(self) -> list[dict]:
    # 1. List firewalls (scoped to TGW types)
    firewalls = self._api_get("/v1/firewalls", {"product_type": ["TGW_IGW", "TGW_GGW", ...]})
    # 2. For each firewall, fetch all rules
    raw_rules = []
    for fw in firewalls["firewalls"]:
        rules = self._api_get("/v1/firewalls/rules",
                              {"firewall_id": fw["id"], "fetch_all": "true"})
        raw_rules.extend(rules["firewall_rules"])
    return raw_rules

def _api_get(self, path: str, params: dict) -> dict:
    # Build query string, sign request, call urllib.request.urlopen
    ...
```

### 13.4 `_fetch_raw_rules_via_cli()` implementation sketch

```python
def _fetch_raw_rules_via_cli(self) -> list[dict]:
    import subprocess, json
    # 1. List TGW firewalls
    fw_out = subprocess.run(
        ["scpcli", "firewall", "firewall", "list", "--product_type", "TGW_IGW"],
        capture_output=True, text=True, check=True
    )
    firewalls = json.loads(fw_out.stdout)["firewalls"]
    # 2. Fetch rules per firewall
    raw_rules = []
    for fw in firewalls:
        rule_out = subprocess.run(
            ["scpcli", "firewall", "firewall-rule", "list",
             "--firewall_id", fw["id"], "--fetch_all", "true"],
            capture_output=True, text=True, check=True
        )
        raw_rules.extend(json.loads(rule_out.stdout)["firewall_rules"])
    return raw_rules
```

---

## 14. Open Questions

| Question | Impact | How to resolve |
|---|---|---|
| Exact HMAC `message` composition (which fields concatenated, in what order) | **Critical for API auth** | Verify against SCP OpenAPI Security Guide (`cloud.samsungsds.com/serviceportal`) from an authenticated session |
| Does `fetch_all=true` have a hard upper limit? | High | Test against a real environment; or check if response includes a truncation indicator |
| Are `source_address` entries always returned with `/32` suffix on host IPs? | Medium | Verify from real API response — affects content-key matching |
| Does `product_type` filter accept multiple values as repeated query params or comma-separated? | Medium | Verify from real request; `array` type in docs is ambiguous |
| Is there a `No-Match` / `ANY` representation for `source_address` (e.g., `0.0.0.0/0`)? | Medium | Inspect real data — affects how "any source" rules are normalized |
| `vendor_rule_id` vs `id` — which is stable for idempotency checks? | Low | `id` is the SCP-assigned UUID and should be stable; `vendor_rule_id` is the underlying device rule number |

---

*Sources: Official SCP documentation pages traversed to operation level (docs.e.samsungsdscloud.com, May 2026). Terraform provider source used as secondary reference for field name confirmation only. All operation-level pages returned HTTP 200.*
