# Endpoint Resolution Design

**Version:** 1.0  
**Module:** `src/classification/endpoint_resolver.py`  
**Used by:** `src/classification/firewall_rules.py` (TGW candidate enrichment)

---

## 1. Purpose

The endpoint resolver converts a raw source or target endpoint (IP, CIDR, hostname) into one of five named endpoint classes. This classification is the basis for:

- **Conflict reason taxonomy** in the SCP Firewall planner
- **Auto-resolution candidate identification** in conflict analysis
- **Audit visibility** into what kind of systems firewall rules connect

The resolver is fully deterministic. Given the same inputs, it always produces the same output.

---

## 2. Endpoint Classes

| Class | Meaning | Examples |
|---|---|---|
| `internal` | IP or CIDR overlaps with our managed subnets, or hostname is a known VM | `10.83.212.5`, `10.83.212.0/24`, `vhapp01` |
| `customer_external` | Private RFC 1918 not in our subnets, or a SAP landscape label hostname | `10.100.0.0/16`, `172.16.0.0/12`, hostname `"PRD"`, `"Non-PRD"` |
| `shared_platform` | IP or CIDR in the explicitly configured platform network list (PSM, backup, SR) | `192.167.14.200`, `192.167.15.0/26` |
| `managed_external` | Public internet — not RFC 1918, not in our subnets, not in platform networks | `203.0.113.5`, `16.3.17.0/24`, `166.79.1.0/24` |
| `unknown` | Placeholder value, empty, or genuinely unresolvable | `0`, `1`, `-`, `""`, `None`, non-IP strings |

---

## 3. Resolution Priority

The resolver checks conditions in this strict order; the **first match wins**:

```
1. hostname ∈ vm_hostnames              → internal
2. hostname is a landscape label        → customer_external
3. raw_ip is placeholder or empty       → unknown
4. raw_ip is CIDR notation:
     overlaps any subnet_network        → internal
     overlaps any platform_network      → shared_platform
     overlaps any RFC 1918 range        → customer_external
     else                               → managed_external
5. raw_ip is a valid host IP:
     addr ∈ any subnet_network          → internal
     addr ∈ any platform_network        → shared_platform
     addr ∈ any RFC 1918 range          → customer_external
     else                               → managed_external
6. (none matched)                       → unknown
```

---

## 4. Key Design Decisions

### 4.1 Hostname Takes Priority over IP

A rule with `source_hostname="vhapp01"` is classified `internal` even if its IP is external or missing. Hostnames are more stable identifiers than IPs in this workbook, so they win.

### 4.2 Landscape Labels Are Not Real Hostnames

SAP landscape environment labels (`PRD`, `DR`, `QAS`, `DEV`, `Non-PRD`, `Non-DR`, `Build`) appear in the workbook as pseudo-hostnames that represent entire landscape zones, not individual servers. They are resolved to `customer_external` so they do not get confused with VM hostnames.

### 4.3 CIDR Notation Is Handled Explicitly

`is_valid_ipv4()` rejects CIDR strings like `10.83.212.0/24`. The resolver detects the `/` prefix and parses using `ipaddress.ip_network(strict=False)`. This is the primary source of conflict reduction — almost all conflicts in the real workbook are CIDR-based subnet rules, not truly unknown endpoints.

### 4.4 Platform Networks Are Configurable, Not Hardcoded

The `platform_networks` parameter (list of `IPv4Network` objects) is optional. It is populated from the `internal` group subnets in the NWInfo sheet. This allows PSM backup and SR subnets (which use non-RFC-1918 addresses like `192.167.x.x`) to be correctly identified as `shared_platform` rather than `managed_external`.

### 4.5 CIDR Overlap Semantics

For CIDR sources/targets, the resolver checks `net.overlaps(sn)` against each managed subnet. This means:

- A source CIDR that **contains** one of our subnets → `internal` (supernet rule covering our space)
- A source CIDR that is **within** one of our subnets → `internal` (subnet rule within our space)
- A source CIDR that shares no overlap with our subnets → classified by RFC 1918 or public status

---

## 5. CIDR Flag

The helper function `is_cidr_notation(raw)` returns `True` when the raw value is a valid IP network with a prefix length (e.g., `10.83.212.0/24`). This flag is separate from the endpoint class and is stored as `src_is_cidr` / `tgt_is_cidr` in TGW candidate entries.

CIDR notation matters for the planner because subnet-level rules require **subnet-level firewall policy** from the SCP API, which is a different API operation from host-level rules.

---

## 6. Conflict Reason Taxonomy (SCP Firewall Planner)

When `requires_manual_review=True`, the planner derives a specific conflict reason from the enriched endpoint fields. Priority order:

| Priority | Conflict Reason | Condition |
|---|---|---|
| 1 | `unknown_both_endpoints` | `src_endpoint_class == "unknown"` AND `tgt_endpoint_class == "unknown"` |
| 2 | `unknown_source_endpoint` | `src_endpoint_class == "unknown"` |
| 3 | `unknown_target_endpoint` | `tgt_endpoint_class == "unknown"` |
| 4 | `cidr_subnet_rule` | `src_is_cidr OR tgt_is_cidr` |
| 5 | `complex_port_expression` | `port_expression == True` |
| 6 | `requires_manual_review` | catch-all |

Secondary reasons that apply alongside the primary are stored in `conflict_flags`.

---

## 7. Auto-Resolution Candidates

A conflict is **auto-resolvable** (sufficient data exists to propose a rule, but human approval still required) when:

- Primary reason is NOT `unknown_*` (both endpoints are resolved to a known class)
- Neither `src_endpoint_class` nor `tgt_endpoint_class` is `"unknown"`

This means all `cidr_subnet_rule` conflicts where endpoints resolve to `internal`, `customer_external`, `shared_platform`, or `managed_external` are auto-resolvable candidates.

**Observed result on real workbook:**

| Metric | Count |
|---|---|
| Total TGW candidates | 110 |
| Clean creates (no review) | 32 |
| Conflicts | 78 |
| Primary reason: `cidr_subnet_rule` | 78 (100%) |
| Secondary flag: `complex_port_expression` | 76 |
| Auto-resolvable | 78 (100%) |
| Requires investigation | 0 |

**Root cause of all 78 conflicts:** The original endpoint classifier (`classify_endpoint`) used `is_valid_ipv4()` which rejects CIDR notation, causing every CIDR-based endpoint to fall into the `unknown` bucket. The enhanced resolver handles CIDRs explicitly, revealing that all 78 conflicted rules are cross-landscape subnet rules — not genuinely ambiguous endpoints.

---

## 8. Endpoint Class Combinations Observed

From the real workbook (78 conflicts):

| Source class | Target class | Count | Interpretation |
|---|---|---|---|
| `managed_external` | `internal` | 34 | Public CIDR → our internal subnet (inbound) |
| `internal` | `managed_external` | 32 | Our subnet → public CIDR (outbound) |
| `customer_external` | `customer_external` | 5 | Private CIDR → private CIDR (off-subnet) |
| `internal` | `internal` | 4 | Our subnet → our subnet (cross-landscape) |
| `shared_platform` | `internal` | 2 | PSM platform → our subnet |
| `customer_external` | `internal` | 1 | Private off-subnet → our subnet |

The `managed_external` entries are public CIDR ranges belonging to SCP/HP platform services (e.g., `16.3.x.x`, `166.79.x.x`). These are correctly identified as external services rather than unknown endpoints.

---

## 9. Future Enhancements

| Enhancement | Condition |
|---|---|
| Auto-promote `cidr_subnet_rule` to `create` | Requires SCP API confirmation that CIDR-based policies are supported |
| Port expression expansion | Parse and validate complex port expressions before provisioning |
| Platform IP registry | Maintain a curated list of known platform CIDRs to improve `shared_platform` classification |
| Landscape label IP mapping | Map landscape labels (`PRD`, `Non-PRD`) to their IP ranges for richer endpoint context |

---

## 10. Module Interface

```python
from src.classification.endpoint_resolver import resolve_endpoint, is_cidr_notation

# 5-way endpoint classification
resolve_endpoint(
    raw_ip: object,
    hostname: str | None,
    vm_hostnames: set[str],
    subnet_networks: list[IPv4Network],
    platform_networks: list[IPv4Network] | None = None,
) -> EndpointClass   # "internal" | "customer_external" | "shared_platform" | "managed_external" | "unknown"

# CIDR detection helper
is_cidr_notation(raw: object) -> bool
```
