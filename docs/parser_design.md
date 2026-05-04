# S2D Parser Design

**Scope:** Accinfo, NWInfo, ServerInfo, FileSystem, SecurityGroup  
**Out of scope:** DNS sheets, Saprouttab, Build_Status/Tasks, provisioning executor, validation engine, LLM

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

**Layout:** Not a table. Each field is a label:value pair.
- Column A = field label
- Column G = value
- Section headers appear in column A (e.g. "General Information", "SID Information")
- Blank rows separate sections; skip them

**Key observations:**
- Multi-value fields (e.g. Customer N/W) use newline (`\n`) as separator — must be split into lists
- SID Information section (rows ~29+) is a nested table with landscape columns — parse separately as `sid_table` or defer to a later phase
- Some fields will be empty (e.g. VPC Name) — emit `None`, do not warn

**Required fields to extract:**
```
Customer Name         → project_metadata.customer_name
Customer (CID)        → project_metadata.customer_id
IP Range              → global_network_context.ip_range
DR IP Range           → global_network_context.dr_ip_range
Domain Name           → project_metadata.domain_name
Customer Connectivity → global_network_context.connectivity_type
Customer N/W          → global_network_context.customer_networks  (list)
Customer DNS Server (Primary)   → global_network_context.dns_primary
Customer DNS Server (Secondary) → global_network_context.dns_secondary
System Timezone       → project_metadata.timezone
```

**Header/section detection:** Match col A string (stripped, case-insensitive) against a fixed label map. Unknown labels are logged as parse_warnings, not errors.

---

### 2.2 NWInfo

**Layout:** Multi-section, each section has a section-header row followed by a sub-section row, followed by a column-header row, followed by data rows.

**Section structure:**
```
Row with col A = "Customer"          → customer network group
Row with col A = "Internal - plan…"  → internal/storage network group
Row with col A = "Server Routing Table" → routing table section
```

Within each network group:
```
col B = "PRD/non-PRD"  → PRD subnet block starts
col B = "DR"           → DR subnet block starts
col B = "No."          → column headers for tabular rows below
  → columns: No. | purpose | IP Range | NAT IP Range | hostname_pattern | ...
```

**Data rows** (numeric in col B) are subnet entries.  
**Routing table** (rows after "Server Routing Table"): col A = No., col B = Routing Name, col C = Target, col D = Source, col E = Remark

**Required outputs:**
- `network.subnets[]` — one entry per IP range row
- `network.routing_table[]` — one entry per routing table row

**Parsing rule:** Section boundaries are detected by value in col A (`row[0]`). Do not use row numbers — row positions can shift.

---

### 2.3 ServerInfo

**Layout:** Tabular. Rows 1 (annotations), 2–3 (two-row merged header), data from row 4.

**Header reconstruction (rows 2–3 merged):**

| Col index | Effective header |
|-----------|-----------------|
| 0 | phase |
| 1 | vhost |
| 2 | phost_raw (contains phost + admin_ip concatenated — see note) |
| 3 | landscape |
| 4 | sid |
| 5 | role_type (MT/AS/ER/AP/DB/WD) |
| 6 | main_solution |
| 7 | sid_category_1 |
| 8 | sid_category_2 |
| 9 | entry_type (server/vip/lb) |
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

**Critical anomaly — phost concatenation bug:**  
`phost` (col 2) in the actual sheet contains the physical hostname and admin IP merged into one string without a separator, e.g. `"phexamplehost0110.83.214.11"`. Split using a regex on the IP pattern:

```python
import re
_IP_PAT = re.compile(r'(\d{1,3}(?:\.\d{1,3}){3})')

def split_phost(raw: str) -> tuple[str, str]:
    m = _IP_PAT.search(raw)
    if m:
        return raw[:m.start()].strip(), m.group(1)
    return raw.strip(), ""
```

**Filter rule:** Only emit rows where `entry_type` (col 9) == `"server"`. Skip `vip` and `lb` entries — they are virtual addresses, not provisionable VMs.

**Boolean normalization:** Values `"O"` → `True`, `"X"` / `None` → `False`.

---

### 2.4 FileSystem

**Layout:** Tabular. Row 1 = input/auto annotations (skip). Row 2 = headers. Data from row 3.

**Column mapping:**

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
| 14 | fs_type (xfs / swap / NFS) |
| 15 | vg_name |
| 16 | nfs_group |
| 17 | remark |
| 18 | check |

**Size anomaly:** Some size values contain formula expressions (`"MIN(256,1024)"`, `"1.5*256"`). Store as strings; do not evaluate. Flag as `size_formula` in the output if not a plain integer.

**Grouping:** The parser should return a flat list of filesystem entries. Each entry carries `hostname` and `admin_ip` for cross-referencing to the VM list. Grouping by VM is the consumer's responsibility (planner/validator), not the parser's.

---

### 2.5 SecurityGroup

**Layout:** Tabular. Row 1 = empty. Row 2 = top-level section labels (Source / Target / ETC / Work). Row 3 = column headers. Data from row 4.

**Column mapping (from row 3):**

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

**Port format:** Port values can be a single number, comma-separated list, or range string with `~` or `-` (e.g. `"443"`, `"1128,1129"`, `"3200-3399"`, `"30200~30298"`). Store as a string — do not parse port ranges. Mark as `port_expression`.

**Control flags:** `"O"` → `True`, `"X"` or `None` → `False`.

**Skip condition:** Skip rows where all of cols 0–12 are `None` (fully blank rows between sections).

---

## 3. Header / Section Detection Strategy

| Sheet | Detection method |
|-------|-----------------|
| Accinfo | Match `row[0]` (stripped, lower) against `ACCINFO_LABEL_MAP` dict |
| NWInfo | Match `row[0]` against known section markers (`"customer"`, `"internal"`, `"server routing table"`); match `row[1]` for sub-sections (`"prd/non-prd"`, `"dr"`, `"no."`) |
| ServerInfo | Fixed rows 2–3 as headers; data starts row 4; detect end by all-None row |
| FileSystem | Fixed row 2 as header; data starts row 3; end on all-None row |
| SecurityGroup | Fixed row 3 as header; data starts row 4; skip all-None rows inline |

**General rule:** Never use absolute row numbers for section boundaries. Always detect by value matching so the parser is resilient to inserted blank rows.

---

## 4. Mapping: Sheets → Desired-State Objects

```
Accinfo      →  desired_state.project_metadata
                desired_state.global_network_context

NWInfo       →  desired_state.network.subnets[]
                desired_state.network.routing_table[]

ServerInfo   →  desired_state.vmware_vm[]   (filtered: entry_type == "server")

FileSystem   →  desired_state.filesystem[]  (flat list, keyed by hostname)

SecurityGroup → desired_state.firewall_rules[]
```

### Top-level desired-state shape

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
        "purpose": "<purpose string>",
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
      "vhost": "<virtual hostname>",
      "phost": "<physical hostname>",
      "landscape": "<PRD | DEV | QAS | DR>",
      "sid": "<SID>",
      "role_type": "<MT | AS | ER | AP | DB | WD>",
      "main_solution": "<solution string>",
      "os_version": "<RHEL 9.4 | ...>",
      "cpu_vcores": 0,
      "memory_gb": 0,
      "appl_storage_gb": 0,
      "service_ip": "<IP>",
      "admin_ip": "<IP>",
      "admin_nat_ip": "<IP or null>",
      "sla": "<percent string>",
      "ha": false,
      "dr": false,
      "backup_enabled": false
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
  "firewall_rules": [
    {
      "source": {
        "system": "<system>",
        "category": "<category>",
        "hostname": "<hostname>",
        "ip": "<IP or CIDR>",
        "landscape": "<env>"
      },
      "target": {
        "system": "<system>",
        "category": "<category>",
        "hostname": "<hostname>",
        "ip": "<IP or CIDR>"
      },
      "port": "<port expression>",
      "protocol": "<TCP | UDP>",
      "expiration": "<Permanent | date>",
      "purpose": "<string>",
      "controls": {
        "cus_fw": true,
        "cus_sg": true,
        "psm_fw": true,
        "psm_sg": true
      }
    }
  ]
}
```

---

## 5. Recommended Parser Function Structure

```
src/
  parser/
    __init__.py          ← parse_s2d() entry point; orchestrates all sub-parsers
    accinfo.py           ← parse_accinfo(ws) → dict
    nwinfo.py            ← parse_nwinfo(ws) → dict
    serverinfo.py        ← parse_serverinfo(ws) → list[dict]
    filesystem.py        ← parse_filesystem(ws) → list[dict]
    securitygroup.py     ← parse_securitygroup(ws) → list[dict]
    _utils.py            ← shared helpers: split_phost(), normalize_bool(), normalize_cidr_list()
```

### Entry point (`__init__.py`)

```python
def parse_s2d(workbook_path: str) -> tuple[ParseResult, ParseWarnings]:
    wb = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    warnings: ParseWarnings = []

    project_metadata, network_context, w = parse_accinfo(wb["Accinfo"])
    warnings.extend(w)

    network, w = parse_nwinfo(wb["NWInfo"])
    warnings.extend(w)

    vmware_vm, w = parse_serverinfo(wb["ServerInfo"])
    warnings.extend(w)

    filesystem, w = parse_filesystem(wb["FileSystem"])
    warnings.extend(w)

    firewall_rules, w = parse_securitygroup(wb["SecurityGroup"])
    warnings.extend(w)

    return {
        "project_metadata": project_metadata,
        "global_network_context": network_context,
        "network": network,
        "vmware_vm": vmware_vm,
        "filesystem": filesystem,
        "firewall_rules": firewall_rules,
    }, warnings
```

### Each sub-parser signature

```python
# accinfo.py
def parse_accinfo(ws) -> tuple[dict, dict, list[str]]:
    """Returns (project_metadata, global_network_context, warnings)."""

# nwinfo.py
def parse_nwinfo(ws) -> tuple[dict, list[str]]:
    """Returns (network_dict, warnings). network_dict has 'subnets' and 'routing_table'."""

# serverinfo.py
def parse_serverinfo(ws) -> tuple[list[dict], list[str]]:
    """Returns (vm_list, warnings). Only 'server' entry_type rows included."""

# filesystem.py
def parse_filesystem(ws) -> tuple[list[dict], list[str]]:
    """Returns (filesystem_list, warnings). Flat list keyed by hostname."""

# securitygroup.py
def parse_securitygroup(ws) -> tuple[list[dict], list[str]]:
    """Returns (firewall_rules, warnings)."""
```

### Shared utilities (`_utils.py`)

```python
import re
_IP_PAT = re.compile(r'(\d{1,3}(?:\.\d{1,3}){3})')

def split_phost(raw: str | None) -> tuple[str, str]:
    """Split concatenated 'phost<IP>' string → (hostname, ip)."""
    if not raw:
        return "", ""
    m = _IP_PAT.search(str(raw))
    if m:
        return str(raw)[:m.start()].strip(), m.group(1)
    return str(raw).strip(), ""

def normalize_bool(value) -> bool:
    """'O' → True, anything else → False."""
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

## 6. Implementation Order

Implement in this order — each parser is independently testable:

### Step 1: `_utils.py`
- Implement and unit-test: `split_phost`, `normalize_bool`, `normalize_cidr_list`, `is_blank_row`
- Fixture: simple inline unit tests, no Excel file needed

### Step 2: `accinfo.py`
- Simplest layout (key-value form, small sheet)
- Define `ACCINFO_LABEL_MAP` dict mapping label strings → output keys
- Test with a minimal fixture dict simulating the ws rows

### Step 3: `serverinfo.py`
- Most important for VM provisioning
- Implement `split_phost` usage here
- Filter on `entry_type == "server"`
- Test with a 5-row fixture covering VM, VIP, and LB rows

### Step 4: `filesystem.py`
- Tabular, straightforward
- Handle `size_formula` edge case
- Test with fixture including NFS and formula-size rows

### Step 5: `securitygroup.py`
- Tabular, straightforward
- Handle port expression passthrough
- Handle `None` control flags → `False`
- Test with fixture including multi-port and range port rows

### Step 6: `nwinfo.py`
- Most complex (section detection logic)
- Implement section state machine
- Test with fixture covering Customer + Internal + Routing sections

### Step 7: Wire `parse_s2d()` in `__init__.py`
- Integration smoke test using the actual sample workbook
- Verify top-level keys present, vmware_vm list non-empty, no unhandled exceptions

---

## 7. Key Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| phost+IP concatenation in ServerInfo col 2 | `split_phost()` regex in `_utils.py`; test with known examples |
| NWInfo section boundaries shift if rows inserted | Detect by col A value, not row index |
| FileSystem size_gb contains formula strings | Store as string in `size_formula`, set `size_gb = None` |
| Accinfo SID table (rows 29+) is complex nested structure | Out of scope for initial parser; skip after "SID Information" label |
| SecurityGroup port ranges contain `~` (not `-`) | Store as raw string; consumer normalizes when needed |
| Blank rows within data sections | `is_blank_row()` guard in all tabular parsers |
| openpyxl `data_only=True` may not resolve formula values | Document this constraint; size_formula field handles it |
