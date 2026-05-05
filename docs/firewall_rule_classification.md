# Firewall Rule Classification Design

**Version:** 1.0  
**Input:** `firewall_rule_candidates[]` from `parse_s2d()`  
**Baseline:** 110 rule candidates from a real S2D workbook

---

## 1. Problem Statement

The parser emits `firewall_rule_candidates[]` — a flat, generic list derived directly from the SecurityGroup sheet. Each candidate describes what network access is desired, but does not specify which platform should enforce it.

The classification layer converts this list into platform-specific rule sets:

| Output | Platform |
|--------|----------|
| `tgw_firewall_rules[]` | Customer-managed TGW / perimeter firewall |
| `nsxt_dfw_rules[]` | NSX-T Distributed Firewall (east-west, workload layer) |
| `reference_only_rules[]` | External or PSM-managed — recorded but not executed |

This classification must remain **deterministic** — the same candidate must always produce the same output. No LLM or probabilistic logic should influence routing decisions.

---

## 2. Input Assumptions

From the baseline workbook:

### 2.1 Endpoint patterns

| Pattern | Count | Interpretation |
|---------|-------|----------------|
| internal → internal | 4 | Both endpoints are VMs in the parsed inventory |
| external → internal | 20 | Source is outside known subnets; target is an internal VM |
| unknown → unknown | 86 | Hostname not in VM inventory; IP outside known subnets |

"Internal" is defined as: the IP falls within a subnet defined in `network.subnets[]`.

### 2.2 Control flag distribution

| `cus_fw` | `cus_sg` | `psm_fw` | `psm_sg` | Count | Interpretation |
|----------|----------|----------|----------|-------|----------------|
| true | true | false | false | 66 | Customer-managed only |
| true | true | true | true | 32 | Both customer and PSM |
| false | true | false | false | 12 | Security group only, no TGW firewall |

### 2.3 Port expression prevalence

102 of 110 rules use multi-port or range expressions. Port parsing (splitting ranges) is deferred to the execution layer, not classification.

---

## 3. Classification Decision Tree

Classification is applied per candidate in order. The first matching rule wins.

```
For each firewall_rule_candidate:

  Step 1: Resolve endpoint type
    source_type = classify_endpoint(source_ip, source_hostname)
    target_type = classify_endpoint(target_ip, target_hostname)
    
    endpoint types: "internal" | "external" | "unknown"
    
    internal: IP falls in network.subnets[].ip_range OR
              hostname is in vmware_vm[].identity.vhost or .phost
    external: IP does not fall in any known subnet AND
              hostname is not in VM inventory
    unknown:  IP is null/placeholder AND hostname is null/not in VM inventory

  Step 2: Route by control flags and endpoint types
  
    IF psm_fw == true OR psm_sg == true:
      → add to reference_only_rules (PSM-managed; not executed by this system)
    
    ELSE IF source_type == "internal" AND target_type == "internal":
      → add to nsxt_dfw_rules (east-west, both endpoints are managed VMs)
    
    ELSE IF cus_fw == true AND (source_type == "external" OR target_type == "external"):
      → add to tgw_firewall_rules (north-south, perimeter)
    
    ELSE IF cus_sg == true AND source_type == "unknown":
      → add to tgw_firewall_rules with flag: requires_manual_review = true
    
    ELSE:
      → add to reference_only_rules (unclassifiable without more context)
```

> **Important:** A single candidate may produce entries in multiple output lists if control flags span multiple platforms (e.g., `cus_fw=true` and `psm_fw=true`). The classification layer must copy, not move, candidates in this case.

---

## 4. Endpoint Classification

```python
def classify_endpoint(ip, hostname, vm_hostnames, subnet_networks):
    # Hostname match takes priority — more reliable than IP in this workbook
    if hostname and hostname in vm_hostnames:
        return "internal"
    
    if ip and is_valid_ipv4(ip):
        addr = ipaddress.ip_address(ip)
        if any(addr in net for net in subnet_networks):
            return "internal"
        else:
            return "external"
    
    return "unknown"
```

`vm_hostnames` includes: `vhost`, `phost`, `service_hostname`, `admin_hostname`, `backup_hostname` from all VMs.

`subnet_networks` includes: all `ip_range` values from `network.subnets[]` that pass CIDR validation (exclude malformed entries).

---

## 5. Output Structures

### 5.1 `tgw_firewall_rules[]`

```json
{
  "origin_idx":           42,
  "source_system":        "string",
  "source_ip":            "string | null",
  "source_hostname":      "string | null",
  "target_system":        "string",
  "target_ip":            "string | null",
  "target_hostname":      "string | null",
  "port":                 "string | null",
  "port_expression":      false,
  "protocol":             "TCP | UDP | null",
  "purpose":              "string",
  "expiration":           "Permanent | date | null",
  "requires_manual_review": false
}
```

`origin_idx` links back to the index in `firewall_rule_candidates[]`.  
`requires_manual_review` is `true` when the endpoint type is `"unknown"`.

### 5.2 `nsxt_dfw_rules[]`

```json
{
  "origin_idx":        42,
  "source_vhost":      "vhexample01",
  "source_ip":         "10.x.x.x",
  "target_vhost":      "vhexample02",
  "target_ip":         "10.x.x.x",
  "port":              "string | null",
  "port_expression":   false,
  "protocol":          "TCP | UDP | null",
  "purpose":           "string",
  "applied_to":        "source | target | both"
}
```

`applied_to` indicates which VM(s) the DFW rule is applied to. Default: `"both"` for internal-to-internal rules.

### 5.3 `reference_only_rules[]`

```json
{
  "origin_idx":  42,
  "reason":      "psm_managed | unclassifiable | external_both_endpoints",
  "source_system": "string",
  "target_system": "string",
  "purpose":       "string",
  "note":          "string | null"
}
```

Reference-only rules are recorded in the output for audit purposes. They are not submitted to any API.

---

## 6. Expected Output Volumes (Baseline Estimate)

Based on the baseline workbook:

| Output List | Estimated Count | Basis |
|-------------|-----------------|-------|
| `tgw_firewall_rules` | ~66 | `cus_fw=true`, external or unknown source |
| `nsxt_dfw_rules` | ~4 | internal → internal, no PSM involvement |
| `reference_only_rules` | ~40 | `psm_fw=true` or unclassifiable |

These are estimates. Actual counts depend on runtime endpoint resolution.

---

## 7. Special Cases

### 7.1 PSM Co-managed Rules

When `psm_fw=true` alongside `cus_fw=true`, the rule must be submitted to the customer TGW firewall AND recorded in `reference_only_rules` for PSM coordination. The customer-side execution is not blocked by PSM status.

### 7.2 Rules with `cus_fw=false` and `cus_sg=true`

12 rules have this pattern. They apply only to cloud security groups (SG/ACL layer), not to TGW firewall policy. These should be emitted as `tgw_firewall_rules` with a `target_layer: "sg_only"` annotation rather than being discarded.

### 7.3 Expiration

`expiration = "Permanent"` is the expected value for non-temporary rules. Any non-"Permanent", non-null value should be converted to a date and stored for lifecycle management. Rules with a past expiration date should be flagged as stale.

### 7.4 Port-Only Rules (no hostname or IP)

Some rules have `source_hostname=null`, `source_ip=null`, and only `source_system` as an identifier. These cannot be classified as internal or external. They must be emitted as `reference_only_rules` with `reason="unclassifiable"`.

---

## 8. Implementation Order

The classification layer should be implemented after parsing is fully validated and before any provisioning executor is built.

Recommended order:

1. Implement `classify_endpoint()` with unit tests against known VM/subnet data
2. Implement the classification decision tree with unit tests covering all flag combinations
3. Run against the full desired-state to produce estimated output volumes
4. Add `requires_manual_review` detection and reporting
5. Connect output lists to planner as inputs (see `provisioning_planner_design.md`)

Classification must **not** make API calls. It is a pure transformation of the parsed desired state.

---

## 9. Deferred Decisions

The following decisions are **not made in this document** and require explicit scope expansion before implementation:

- Port range parsing and normalization (e.g., `3200-3399` → list of integers)
- Protocol validation (TCP/UDP enforcement, ICMP handling)
- Exact NSX-T DFW group membership resolution (tag-based vs IP-based)
- TGW route table attachment logic
- Lifecycle management for expiring rules
