# S2D Parser Design

**Scope:** `Accinfo`, `NWInfo`, `ServerInfo`, `FileSystem`, `SecurityGroup`  
**Out of scope:** DNS sheets, `Saprouttab`, `Build_Status`/`Build_Tasks`, provisioning executor, validation engine, LLM layer

---

## 1. Workbook Structure Summary

| Sheet | Layout type | Header rows | Data start | Rows (approx) |
|-------|-------------|-------------|------------|----------------|
| Accinfo | Key-value form (NOT tabular) | None | N/A | ~104 |
| NWInfo | Multi-section hierarchical | Per-section inline | After section header | ~35 |
| ServerInfo | Tabular, merged 2-row header | Rows 2–3 | Row 4 | ~97 |
| FileSystem | Tabular, annotation+header | Rows 1–2 | Row 3 | ~410 |
| SecurityGroup | Tabular, 2-row header | Rows 2–3 | Row 4 | ~120 |

---

## 2. Sheet-by-Sheet Parsing Assumptions

### 2.1 Accinfo

#### Layout
Not a table. Each field is a label:value pair.
- Column A = field label
- Column G = value
- Section headers appear in column A (for example: `General Information`, `SID Information`)
- Blank rows separate sections and should be skipped

#### Key observations
- Multi-value fields (for example: `Customer N/W`) use newline (`\n`) separators and must be split into lists
- The `SID Information` section (around row 29+) is a nested table with landscape columns and should be parsed separately later or deferred
- Some fields may be empty (for example: `VPC Name`) and should be emitted as `None` without warning

#### Required fields to extract
```text
Customer Name                    → project_metadata.customer_name
Customer (CID)                   → project_metadata.customer_id
IP Range                         → global_network_context.ip_range
DR IP Range                      → global_network_context.dr_ip_range
Domain Name                      → project_metadata.domain_name
Customer Connectivity            → global_network_context.connectivity_type
Customer N/W                     → global_network_context.customer_networks
Customer DNS Server (Primary)    → global_network_context.dns_primary
Customer DNS Server (Secondary)  → global_network_context.dns_secondary
System Timezone                  → project_metadata.timezone
```

#### Header/section detection
Match column A string (stripped, case-insensitive) against a fixed `ACCINFO_LABEL_MAP`.

- Unknown labels that look malformed or ambiguous should go to `parser_warnings`
- Valid labels that are currently out of MVP scope should go to `ignored_labels`

#### Ignored labels vs warnings
The parser should distinguish between:
- `parser_warnings`: ambiguous, malformed, or partially missing values
- `ignored_labels`: valid labels that are currently out of MVP scope

This prevents over-reporting normal out-of-scope items as warnings.

---

### 2.2 NWInfo

#### Layout
Multi-section sheet. Each section has:
1. a section header row
2. a subsection row
3. a column header row
4. data rows

#### Section structure
```text
Column A = "Customer"             → customer network group
Column A = "Internal - plan..."   → internal/storage network group
Column A = "Server Routing Table" → routing table section
```

Within each network group:
```text
Column B = "PRD/non-PRD"  → PRD subnet block starts
Column B = "DR"           → DR subnet block starts
Column B = "No."          → table header row begins
```

Typical data columns below the `No.` row:
- No.
- purpose
- IP Range
- NAT IP Range
- hostname/FQDN pattern
- optional remarks or usage notes

Routing table rows:
- Column A = No.
- Column B = Routing Name
- Column C = Target
- Column D = Source
- Column E = Remark

#### Required outputs
- `network.subnets[]`
- `network.routing_table[]`

#### Parsing rule
Section boundaries must be detected by cell values, not fixed row numbers.

#### Canonical purpose key
The parser must preserve the original subnet purpose text as `purpose_raw`, but also emit a normalized internal key as `purpose_key`.

Recommended canonical values:
- `production_service`
- `non_production_service`
- `admin`
- `heartbeat`
- `public`
- `storage`
- `backup`
- `other`

Examples:
- `Production Service` → `production_service`
- `HeartBeat` → `heartbeat`

This is required so downstream planner, validator, and executor logic can rely on stable internal values even if source wording varies.

---

### 2.3 ServerInfo

#### Layout
Tabular sheet.
- Row 1 = annotation / human note
- Rows 2–3 = merged logical header
- Data starts at row 4

#### Header reconstruction

| Col index | Effective header |
|-----------|------------------|
| 0 | phase |
| 1 | vhost |
| 2 | phost_raw |
| 3 | landscape |
| 4 | sid |
| 5 | role_type |
| 6 | main_solution |
| 7 | sid_category_1 |
| 8 | sid_category_2 |
| 9 | entry_type |
| 10 | role_description |
| 11 | host_no |
| 12 | vm_or_bm |
| 13 | cdd_date |
| 14 | scp_image |
| 15 | os_version |
| 16 | cpu_vcores |
| 17 | memory_gb |
| 18 | appl_storage_gb |
| 19 | nfs_storage_gb |
| 20 | service_hostname |
| 21 | service_ip |
| 22 | admin_hostname |
| 23 | admin_ip |
| 24 | admin_nat_ip |
| 25 | backup_hostname |
| 26 | backup_ip |
| 27 | sr_dr_ip |
| 28 | internode_ip |
| 29 | hb_ip |
| 30 | sla |
| 31 | ha |
| 32 | dr |
| 33 | pacemaker |
| 34 | db_sr |
| 35 | hana_haf |
| 36 | backup_enabled |
| 37–42 | security agents (siem, soar, va, edr, antivirus, cspm) |

#### Critical anomaly — `phost` concatenation
`phost_raw` may contain physical hostname and admin IP concatenated without a separator, for example:

```text
phgenericap0110.1.0.11
```

Recommended split helper:

```python
import re
_IP_PAT = re.compile(r'(\d{1,3}(?:\.\d{1,3}){3})')

def split_phost(raw: str) -> tuple[str, str]:
    m = _IP_PAT.search(raw)
    if m:
        return raw[:m.start()].strip(), m.group(1)
    return raw.strip(), ""
```

#### Filter rule
Only emit rows where `entry_type == "server"`.
Skip `vip` and `lb` entries because they are not provisionable VM instances.

#### Boolean normalization
- `"O"` → `True`
- `"X"` or `None` → `False`

#### Required output shape
`ServerInfo` should be normalized into `vmware_vm[]` entries using nested sections:

- `identity`
- `compute`
- `network`
- `availability`
- `metadata`

#### Example output
```json
{
  "vmware_vm": [
    {
      "identity": {
        "vhost": "vhgenericap01",
        "phost": "phgenericap01",
        "landscape": "PRD",
        "sid": "TST",
        "role_type": "AP",
        "main_solution": "S/4HANA"
      },
      "compute": {
        "os_version": "RHEL 9.4",
        "cpu_vcores": 16,
        "memory_gb": 256,
        "appl_storage_gb": 100,
        "nfs_storage_gb": 50,
        "scp_image": "RHEL9-GI"
      },
      "network": {
        "service_hostname": "vhgenericap01",
        "service_ip": "10.0.0.11",
        "admin_hostname": "phgenericap01",
        "admin_ip": "10.1.0.11",
        "admin_nat_ip": "192.168.7.11",
        "backup_hostname": null,
        "backup_ip": null,
        "sr_dr_ip": null,
        "internode_ip": null,
        "hb_ip": null
      },
      "availability": {
        "sla": "99.9%",
        "ha": true,
        "dr": false,
        "pacemaker": true,
        "db_sr": false,
        "hana_haf": false,
        "backup_enabled": true
      },
      "metadata": {
        "phase": "Phase 1",
        "entry_type": "server",
        "role_description": "PAS#01",
        "host_no": 1,
        "vm_or_bm": "VM"
      }
    }
  ]
}
```

---

### 2.4 FileSystem

#### Layout
Tabular sheet.
- Row 1 = annotation/input notes
- Row 2 = header
- Data starts at row 3

#### Column mapping

| Col index | Field |
|-----------|-------|
| 0 | seq_no |
| 1 | landscape |
| 2 | sid |
| 3 | server_type |
| 4 | fs_category_1 |
| 5 | fs_category_2 |
| 6 | sla_tier |
| 7 | ha_flag |
| 8 | fs_count_max |
| 9 | fs_seq_in_host |
| 10 | hostname |
| 11 | admin_ip |
| 12 | mount_point |
| 13 | size_gb |
| 14 | fs_type |
| 15 | vg_name |
| 16 | nfs_group |
| 17 | remark |
| 18 | check |

#### Size anomaly
Some `size_gb` values are formulas or expressions such as:
- `MIN(256,1024)`
- `1.5*256`

Do not evaluate them.
Store:
- `size_gb = None`
- `size_formula = "<raw string>"`

if the value is not a plain integer.

#### Grouping rule
The parser should return a flat list of filesystem entries.
Grouping by VM is the responsibility of planner or validator, not the parser.

#### Join strategy
The parser must preserve enough fields for downstream matching.

Recommended join priority:
1. `hostname`
2. fallback: `admin_ip`
3. fallback: `landscape + sid + server_type`

If no reliable match can be established later, downstream logic should emit a validation warning rather than forcing an implicit match.

---

### 2.5 SecurityGroup

#### Layout
Tabular sheet.
- Row 1 = empty / spacer
- Row 2 = top-level grouping row (`Source`, `Target`, `ETC`, `Work`)
- Row 3 = actual column headers
- Data starts at row 4

#### Column mapping

| Col index | Field |
|-----------|-------|
| 0 | source_system |
| 1 | source_category |
| 2 | source_hostname |
| 3 | source_ip |
| 4 | source_landscape |
| 5 | target_system |
| 6 | target_category |
| 7 | target_hostname |
| 8 | target_ip |
| 9 | port |
| 10 | protocol |
| 11 | expiration |
| 12 | purpose |
| 13 | cus_fw |
| 14 | cus_sg |
| 15 | psm_fw |
| 16 | psm_sg |

#### Port format
Port values may be:
- single value: `443`
- comma-separated: `1128,1129`
- range: `3200-3399`
- tilde range: `30200~30298`

Do not parse ranges at parser stage.
Store raw string and optionally mark it as `port_expression`.

#### Boolean normalization
- `"O"` → `True`
- `"X"` or `None` → `False`

#### Skip rule
Skip rows where columns 0–12 are all blank.

#### Parser output role
In the parser phase, this sheet should first be normalized into a generic rule candidate list:

- `firewall_rule_candidates[]`

Do not fully decide platform-specific rule execution targets yet.
That transformation should happen later in normalization/planning, where candidates may be split into:

- `tgw_firewall_rules[]`
- `nsxt_dfw_rules[]`

This is necessary because the same source row can map differently depending on source/target identity, network scope, and platform-specific execution constraints.

---

## 3. Header / Section Detection Strategy

| Sheet | Detection method |
|-------|------------------|
| Accinfo | Match `row[0]` (stripped, lower) against `ACCINFO_LABEL_MAP` |
| NWInfo | Match `row[0]` against section markers (`customer`, `internal`, `server routing table`); use `row[1]` for subsection markers (`prd/non-prd`, `dr`, `no.`) |
| ServerInfo | Fixed rows 2–3 as header; data starts at row 4; detect end by blank row |
| FileSystem | Fixed row 2 as header; data starts at row 3; stop on blank row |
| SecurityGroup | Fixed row 3 as header; data starts at row 4; skip blank rows inline |

### General rule
Never rely on absolute row numbers for section boundaries where section text can be matched.
Use value-based detection whenever possible so the parser remains resilient to inserted rows or formatting shifts.

---

## 4. Mapping: Sheets → Desired-State Objects

```text
Accinfo       → desired_state.project_metadata
                desired_state.global_network_context

NWInfo        → desired_state.network.subnets[]
                desired_state.network.routing_table[]

ServerInfo    → desired_state.vmware_vm[]
                (filtered where entry_type == "server")

FileSystem    → desired_state.filesystem[]
                (flat list, not grouped)

SecurityGroup → desired_state.firewall_rule_candidates[]
```

---

## 5. Top-Level Desired-State Shape

```json
{
  "project_metadata": {
    "customer_name": "<placeholder>",
    "customer_id": "<CID>",
    "domain_name": "<placeholder.example.com>",
    "timezone": "<TZ string>"
  },
  "global_network_context": {
    "ip_range": "<CIDR>",
    "dr_ip_range": "<CIDR>",
    "connectivity_type": "<Cloud Peering | Direct Connect | ...>",
    "customer_networks": ["<CIDR>", "..."],
    "dns_primary": "<IP>",
    "dns_secondary": "<IP>"
  },
  "network": {
    "subnets": [
      {
        "group": "<customer | internal>",
        "env": "<prd | dr>",
        "seq_no": 1,
        "purpose_raw": "<purpose string>",
        "purpose_key": "<canonical value>",
        "ip_range": "<CIDR>",
        "nat_ip_range": "<CIDR or N/A>",
        "hostname_pattern": "<pattern or null>"
      }
    ],
    "routing_table": [
      {
        "routing_name": "<name>",
        "target_cidr": "<CIDR>",
        "source_ip": "<IP>",
        "remark": "<string or null>"
      }
    ]
  },
  "vmware_vm": [
    {
      "identity": {},
      "compute": {},
      "network": {},
      "availability": {},
      "metadata": {}
    }
  ],
  "filesystem": [
    {
      "hostname": "<physical hostname>",
      "admin_ip": "<IP>",
      "landscape": "<env>",
      "sid": "<SID>",
      "mount_point": "<path>",
      "size_gb": 0,
      "size_formula": null,
      "fs_type": "<xfs | swap | NFS>",
      "nfs_group": "<group name or null>",
      "remark": "<string or null>"
    }
  ],
  "firewall_rule_candidates": [],
  "parser_warnings": [],
  "ignored_labels": []
}
```

---

## 6. Recommended Parser Function Structure

```text
src/
  parser/
    __init__.py
    accinfo.py
    nwinfo.py
    serverinfo.py
    filesystem.py
    securitygroup.py
    _utils.py
```

### Module roles

- `__init__.py`  
  Entry point. Loads workbook and orchestrates sub-parsers.

- `accinfo.py`  
  Parses global metadata and network context.

- `nwinfo.py`  
  Parses subnet definitions and routing table.

- `serverinfo.py`  
  Parses VM/server entries.

- `filesystem.py`  
  Parses filesystem/storage entries.

- `securitygroup.py`  
  Parses firewall rule candidates.

- `_utils.py`  
  Shared helpers such as:
  - `split_phost()`
  - `normalize_bool()`
  - `normalize_cidr_list()`
  - `is_blank_row()`

---

## 7. Entry Point Design

Internal sub-parsers may return `(data, warnings)` tuples, but the top-level `parse_s2d()` function should return a single structured result object that includes parser warnings.

### Recommended shape

```python
def parse_s2d(workbook_path: str) -> dict:
    ...
    return {
        "project_metadata": project_metadata,
        "global_network_context": network_context,
        "network": network,
        "vmware_vm": vmware_vm,
        "filesystem": filesystem,
        "firewall_rule_candidates": firewall_rule_candidates,
        "parser_warnings": warnings,
        "ignored_labels": ignored_labels,
    }
```

This makes downstream reporting, fixture comparison, and consumer integration simpler than returning a separate tuple.

### Example entry point

```python
def parse_s2d(workbook_path: str) -> dict:
    wb = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    warnings: list[str] = []
    ignored_labels: list[str] = []

    project_metadata, network_context, w, ignored = parse_accinfo(wb["Accinfo"])
    warnings.extend(w)
    ignored_labels.extend(ignored)

    network, w = parse_nwinfo(wb["NWInfo"])
    warnings.extend(w)

    vmware_vm, w = parse_serverinfo(wb["ServerInfo"])
    warnings.extend(w)

    filesystem, w = parse_filesystem(wb["FileSystem"])
    warnings.extend(w)

    firewall_rule_candidates, w = parse_securitygroup(wb["SecurityGroup"])
    warnings.extend(w)

    return {
        "project_metadata": project_metadata,
        "global_network_context": network_context,
        "network": network,
        "vmware_vm": vmware_vm,
        "filesystem": filesystem,
        "firewall_rule_candidates": firewall_rule_candidates,
        "parser_warnings": warnings,
        "ignored_labels": ignored_labels,
    }
```

---

## 8. Sub-Parser Signatures

```python
# accinfo.py
def parse_accinfo(ws) -> tuple[dict, dict, list[str], list[str]]:
    """Returns (project_metadata, global_network_context, warnings, ignored_labels)."""

# nwinfo.py
def parse_nwinfo(ws) -> tuple[dict, list[str]]:
    """Returns (network_dict, warnings)."""

# serverinfo.py
def parse_serverinfo(ws) -> tuple[list[dict], list[str]]:
    """Returns (vm_list, warnings). Only rows with entry_type == 'server' are included."""

# filesystem.py
def parse_filesystem(ws) -> tuple[list[dict], list[str]]:
    """Returns (filesystem_list, warnings)."""

# securitygroup.py
def parse_securitygroup(ws) -> tuple[list[dict], list[str]]:
    """Returns (firewall_rule_candidates, warnings)."""
```

---

## 9. Shared Utilities

```python
import re

_IP_PAT = re.compile(r'(\d{1,3}(?:\.\d{1,3}){3})')

def split_phost(raw: str | None) -> tuple[str, str]:
    """Split concatenated 'phost<IP>' string into (hostname, ip)."""
    if not raw:
        return "", ""
    raw = str(raw)
    m = _IP_PAT.search(raw)
    if m:
        return raw[:m.start()].strip(), m.group(1)
    return raw.strip(), ""

def normalize_bool(value) -> bool:
    """Return True only for 'O'."""
    return str(value).strip().upper() == "O"

def normalize_cidr_list(raw: str | None) -> list[str]:
    """Split newline-separated CIDR strings into a list."""
    if not raw:
        return []
    return [s.strip() for s in str(raw).splitlines() if s.strip()]

def is_blank_row(row: tuple) -> bool:
    return all(v is None for v in row)
```

---

## 10. Implementation Order

Implement in this order:

### Step 1: `_utils.py`
Implement and unit-test:
- `split_phost`
- `normalize_bool`
- `normalize_cidr_list`
- `is_blank_row`

No Excel fixture required.

---

### Step 2: `accinfo.py`
Why first:
- simplest layout
- defines global context
- fixes top-level output structure early

Implement:
- `ACCINFO_LABEL_MAP`
- label matching
- `project_metadata`
- `global_network_context`
- `ignored_labels`

---

### Step 3: `serverinfo.py`
Why before `nwinfo.py`:
`ServerInfo` is implemented earlier because it provides the highest-value provisioning input for the MVP and has a more deterministic tabular structure than the multi-section `NWInfo` sheet.

Implement:
- merged-header reconstruction
- `split_phost()` integration
- `entry_type == "server"` filter
- nested VM object structure

---

### Step 4: `filesystem.py`
Implement:
- flat filesystem entry parsing
- `size_formula` handling
- no grouping yet

---

### Step 5: `securitygroup.py`
Implement:
- row parsing into `firewall_rule_candidates`
- port expression passthrough
- boolean control flag normalization
- blank row skipping

---

### Step 6: `nwinfo.py`
Implement:
- section state machine
- subnet group parsing
- routing table parsing
- `purpose_key` normalization

This parser is more complex and should come after the simpler deterministic parsers.

---

### Step 7: `parse_s2d()` in `__init__.py`
Integrate all sub-parsers and return the final desired-state object.

---

## 11. Key Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| `phost_raw` contains hostname and IP merged | use `split_phost()` and fixture tests |
| `NWInfo` section boundaries shift | use text-based section detection, not row positions |
| `FileSystem.size_gb` contains formulas | keep raw value in `size_formula`, set numeric field to `None` |
| `Accinfo` contains many out-of-scope labels | track them under `ignored_labels` |
| `SecurityGroup` rules may later split into multiple platform outputs | keep parser output generic as `firewall_rule_candidates` |
| blank rows appear inside table sections | use `is_blank_row()` in all tabular parsers |
| formula cells may not resolve under `data_only=True` | document limitation and keep raw-compatible fallback behavior |
