# Desired-State Schema

**Version:** 1.0  
**Baseline:** full parse of a real S2D workbook — 68 VMs, 408 filesystem entries, 110 firewall rule candidates, 15 subnets, 4 routing entries.

---

## 1. Top-Level Structure

```json
{
  "project_metadata":         { ... },
  "global_network_context":   { ... },
  "network":                  { "subnets": [...], "routing_table": [...] },
  "vmware_vm":                [ ... ],
  "filesystem":               [ ... ],
  "firewall_rule_candidates": [ ... ],
  "parser_warnings":          [ "string", ... ],
  "ignored_labels":           [ "string", ... ]
}
```

All keys are **stable and canonical**. Downstream planners, validators, and executors must reference only these keys. Changes to key names require a schema version bump and simultaneous update of all fixtures and tests.

---

## 2. Field Classification

### 2.1 Required vs Optional

A field is **required** if it must be non-null for the resource to be provisionable.  
A field is **optional** if it may be null without blocking provisioning.

**Notation:**

| Symbol | Meaning |
|--------|---------|
| `R` | Required — null is a data quality issue |
| `O` | Optional — null is expected in some configurations |
| `O*` | Conditionally optional — required only when a related flag is true |

---

## 3. `project_metadata`

```json
{
  "customer_name": "string",
  "customer_id":   "string",
  "domain_name":   "string",
  "timezone":      "string"
}
```

| Field | Class | Notes |
|-------|-------|-------|
| `customer_name` | R | Used in report headers |
| `customer_id` | R | Used as namespace prefix in resource naming |
| `domain_name` | O | Used for FQDN construction; null allowed if no DNS automation |
| `timezone` | O | Informational |

---

## 4. `global_network_context`

```json
{
  "ip_range":           "10.83.212.0/22",
  "dr_ip_range":        "10.83.216.0/22",
  "connectivity_type":  "Cloud Peering",
  "customer_networks":  ["10.0.0.0/8"],
  "dns_primary":        "10.x.x.x",
  "dns_secondary":      "10.x.x.x"
}
```

| Field | Class | Notes |
|-------|-------|-------|
| `ip_range` | R | The main allocated CIDR for this customer environment |
| `dr_ip_range` | O | May be absent if no DR is provisioned |
| `connectivity_type` | R | Informs TGW and routing design |
| `customer_networks` | O | List of CIDRs; may be empty |
| `dns_primary` | O | Required if DNS-based hostname resolution is needed |
| `dns_secondary` | O | |

---

## 5. `network`

### 5.1 `subnets[]`

```json
{
  "group":            "customer | internal",
  "env":              "prd | dr",
  "seq_no":           1,
  "purpose_raw":      "Production Service",
  "purpose_key":      "production_service",
  "ip_range":         "10.x.x.x/24",
  "nat_ip_range":     "192.168.x.x/24 | N/A | null",
  "hostname_pattern": "vh<hostname>.example.com | null"
}
```

| Field | Class | Notes |
|-------|-------|-------|
| `group` | R | `"customer"` or `"internal"` |
| `env` | R | `"prd"` or `"dr"` |
| `seq_no` | O | Sequence number within subsection |
| `purpose_raw` | O | Preserved verbatim from source; informational |
| `purpose_key` | R | Canonical normalized value — see §5.3 |
| `ip_range` | R | Must be a valid CIDR; flag as data quality issue if host bits set |
| `nat_ip_range` | O | String `"N/A"` is treated as null |
| `hostname_pattern` | O | Pattern string; not enforced by the planner |

### 5.2 `routing_table[]`

```json
{
  "routing_name": "Admin",
  "target_cidr":  "192.168.0.0/16",
  "source_ip":    "10.83.214.1",
  "remark":       "string | null"
}
```

| Field | Class | Notes |
|-------|-------|-------|
| `routing_name` | O | Human label |
| `target_cidr` | R | Destination network |
| `source_ip` | R | The gateway or next-hop IP |
| `remark` | O | |

### 5.3 Canonical `purpose_key` Values

| `purpose_key` | Accepted `purpose_raw` inputs (case-insensitive) |
|---------------|--------------------------------------------------|
| `production_service` | "Production Service" |
| `non_production_service` | "Non-Production Service", "Non Production Service" |
| `admin` | "Admin", "Administration" |
| `heartbeat` | "HeartBeat" |
| `public` | "Public", "Public Subnet" |
| `storage` | "Storage" |
| `backup` | "Backup" |
| `other` | anything not in the above list |

`"other"` is valid output, not an error. Downstream components must handle it. Known real-world values that map to `"other"` in this baseline:
- `"Service"` (DR customer service network — ambiguous intent)
- `"SR(DR, HA)"` (storage replication)
- `"Inter-Node(HANA Scale-out)"` (HANA internode network)

---

## 6. `vmware_vm[]`

### 6.1 Full Structure

```json
{
  "identity":     { ... },
  "compute":      { ... },
  "network":      { ... },
  "availability": { ... },
  "metadata":     { ... }
}
```

### 6.2 `identity`

| Field | Class | Notes |
|-------|-------|-------|
| `vhost` | R | Virtual hostname — primary resource identity key |
| `phost` | R | Physical hostname — required for storage provisioning |
| `landscape` | R | One of: `PRD`, `DR`, `QAS`, `DEV` |
| `sid` | R | SAP System ID |
| `role_type` | R | Short role code (e.g. `AP`, `DB`, `MT`, `WD`) |
| `main_solution` | O | SAP product name |

### 6.3 `compute`

| Field | Class | Notes |
|-------|-------|-------|
| `os_version` | R | Required for VM template selection |
| `cpu_vcores` | R | |
| `memory_gb` | R | |
| `appl_storage_gb` | R | |
| `nfs_storage_gb` | O | Null in all 68 VMs in this baseline |
| `scp_image` | O | Null in all 68 VMs; not yet populated in this workbook version |

### 6.4 `network`

| Field | Class | Notes |
|-------|-------|-------|
| `service_hostname` | R | |
| `service_ip` | O* | Required when `metadata.entry_type == "server"`; 18 VMs have placeholder values |
| `admin_hostname` | R | Used as phost resolution fallback |
| `admin_ip` | O* | Required for provisioning; 18 VMs have placeholder values (0, 1, 2, 3, 4) |
| `admin_nat_ip` | O | Null for VMs without NAT; placeholder (`-`) treated as null |
| `backup_hostname` | O | |
| `backup_ip` | O | |
| `sr_dr_ip` | O | Null in 65 of 68 VMs |
| `internode_ip` | O | Null in all 68 VMs in this baseline |
| `hb_ip` | O | Null in 64 of 68 VMs |

### 6.5 `availability`

All fields are boolean, normalized from `"O"` / `"X"` / null.

| Field | Class | Notes |
|-------|-------|-------|
| `sla` | O | SLA tier string |
| `ha` | R | High availability flag |
| `dr` | R | DR flag — determines DR resource inclusion |
| `pacemaker` | O* | Required if `ha == true` |
| `db_sr` | O* | Required for HANA DB role |
| `hana_haf` | O | |
| `backup_enabled` | R | |

### 6.6 `metadata`

| Field | Class | Notes |
|-------|-------|-------|
| `phase` | O | Delivery phase |
| `entry_type` | R | Always `"server"` in output (parser filters non-server rows) |
| `role_description` | O | Free-text description |
| `host_no` | O | Position index within a host group |
| `vm_or_bm` | O | `"VM"` or `"BM"` (bare metal) |

---

## 7. `filesystem[]`

```json
{
  "seq_no":         1,
  "landscape":      "PRD",
  "sid":            "CGS",
  "server_type":    "MT",
  "fs_category_1":  "CGS",
  "fs_category_2":  "PRDR1",
  "sla_tier":       "99.90%",
  "ha_flag":        false,
  "fs_count_max":   5,
  "fs_seq_in_host": 1,
  "hostname":       "phexample01",
  "admin_ip":       "10.x.x.x",
  "mount_point":    "/usr/sap",
  "size_gb":        50,
  "size_formula":   null,
  "fs_type":        "xfs",
  "vg_name":        null,
  "nfs_group":      null,
  "remark":         null,
  "check":          null
}
```

### Join Strategy

The filesystem list is flat. Downstream components must join entries to VMs in priority order:

1. `hostname` matches `vmware_vm[].identity.phost` (primary)
2. `admin_ip` matches `vmware_vm[].network.admin_ip` (fallback)
3. `landscape + sid + server_type` triple match (last resort; may be ambiguous)

When no reliable match can be established, the downstream component must emit a warning rather than forcing an implicit match.

### `size_gb` / `size_formula` Invariant

Exactly one of `size_gb` (integer) and `size_formula` (string) is non-null per entry. Both null means the cell was empty. Neither is null only when the cached formula value is also an integer (covered by `data_only=True` openpyxl mode).

| Field | Class | Notes |
|-------|-------|-------|
| `hostname` | R | Required for VM join; all 408 entries populated in this baseline |
| `admin_ip` | O* | Required for fallback join; 21 entries have placeholder values |
| `landscape` | R | |
| `sid` | R | |
| `server_type` | R | |
| `mount_point` | R | |
| `size_gb` | O* | Required when `size_formula` is null |
| `size_formula` | O | Present when openpyxl reads a cached formula string |
| `fs_type` | R | |
| `ha_flag` | R | Normalized boolean |

---

## 8. `firewall_rule_candidates[]`

```json
{
  "source_system":    "string",
  "source_category":  "string",
  "source_hostname":  "string | null",
  "source_ip":        "string | null",
  "source_landscape": "string | null",
  "target_system":    "string",
  "target_category":  "string",
  "target_hostname":  "string | null",
  "target_ip":        "string | null",
  "port":             "string | null",
  "port_expression":  false,
  "protocol":         "TCP | UDP | null",
  "expiration":       "Permanent | date | null",
  "purpose":          "string",
  "cus_fw":           true,
  "cus_sg":           true,
  "psm_fw":           false,
  "psm_sg":           false
}
```

### Endpoint Identity

Each endpoint (source/target) may be identified by hostname, IP, or both. In this baseline:
- 86 of 110 rules have endpoints where neither hostname nor IP resolves to a known VM — these are external endpoints (customer network, PSM infrastructure, internet).
- 20 rules have an external source and an internal target.
- 4 rules are fully internal (both endpoints are VMs in the inventory).

### Control Flags

| Flag | Meaning |
|------|---------|
| `cus_fw` | Apply to customer-managed TGW/perimeter firewall |
| `cus_sg` | Apply to customer security group (cloud SG/ACL) |
| `psm_fw` | Apply to PSM (partner)-managed firewall |
| `psm_sg` | Apply to PSM security group |

Observed combinations in this baseline:

| `cus_fw` | `cus_sg` | `psm_fw` | `psm_sg` | Count |
|----------|----------|----------|----------|-------|
| true | true | false | false | 66 |
| true | true | true | true | 32 |
| false | true | false | false | 12 |

### Port Field

`port` is always stored as a raw string. `port_expression` is `true` when the string contains commas, hyphens, or tildes (range/multi-port expressions). Do not parse port ranges at this stage.

---

## 9. Data Quality Issues

Parser warnings and consistency findings are not blocking errors — they are structured observations that downstream components must handle explicitly.

### 9.1 Placeholder IP Values

IPs with values `0`, `1`, `2`, `3`, `4`, or `"-"` in VM network fields indicate unresolved addresses in the source workbook. The parser normalizes these but does not remove them.

**Effect on provisioning:** A VM with a placeholder `admin_ip` cannot be matched to filesystem entries by IP. The join falls back to `hostname`. If both are unresolvable, provisioning for that VM must be deferred or flagged as a conflict.

### 9.2 Malformed Subnet CIDRs

CIDRs with host bits set (e.g., `192.167.16.128/2`) indicate a prefix-length typo in the workbook. The parser stores the raw value. The consistency checker flags it.

**Effect on provisioning:** IP-range-based validation for affected subnets will be inaccurate until the workbook is corrected.

### 9.3 Unresolved Firewall Endpoints

Firewall candidates where `source_hostname` or `target_hostname` is not in the VM inventory are classified as external endpoints. They are not provisioning errors — external hostnames are expected. However, rules where both endpoints are unknown should be flagged for manual review before execution.

### 9.4 Data Quality Issue Structure

Structured data quality findings should be emitted as:

```json
{
  "issue_type":  "placeholder_ip | malformed_cidr | unresolved_endpoint | unmatched_filesystem",
  "severity":    "error | warning | info",
  "resource":    "vmware_vm | subnet | firewall_rule | filesystem",
  "resource_id": "vhexample01 | 10.x.x.x/24 | rule[42]",
  "field":       "admin_ip | ip_range | source_hostname",
  "raw_value":   "0 | 192.167.16.128/2 | phpsmpsrpsr",
  "message":     "human-readable description"
}
```

---

## 10. Stability Contract

The following keys are **locked** — they must not be renamed without a schema version bump:

- Top-level: `project_metadata`, `global_network_context`, `network`, `vmware_vm`, `filesystem`, `firewall_rule_candidates`, `parser_warnings`, `ignored_labels`
- VM sections: `identity`, `compute`, `network`, `availability`, `metadata`
- VM identity: `vhost`, `phost`, `landscape`, `sid`
- Firewall: `source_system`, `target_system`, `port`, `port_expression`, `cus_fw`, `cus_sg`, `psm_fw`, `psm_sg`
- Filesystem join keys: `hostname`, `admin_ip`, `landscape`, `sid`, `server_type`
- Subnet: `group`, `env`, `purpose_key`, `ip_range`

Any addition of new optional fields does not require a version bump. Removal or renaming of any key above does.
