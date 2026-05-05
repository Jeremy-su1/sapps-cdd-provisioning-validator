# Unsupported Sheet Triage

Source of truth: `scripts/debug_parse_introspection.py` coverage output against a real S2D workbook.

**Counts:** 72 workbook sheets total — 5 registered, 67 unsupported.

Unsupported means the sheet is present in the workbook but has no entry in `SHEET_REGISTRY`. No parser, planner, collector, or validator is wired for it. The sheet is silently skipped.

---

## Triage Categories

### 1. Out of current MVP scope — infra-related

Sheets that describe infrastructure resources within the MVP domain but whose parsers have not been built yet.

| Sheet | Description | Likely backend |
|-------|-------------|----------------|
| `DNScust` | Customer-side DNS server config | OS / DNS service |
| `DNSpsadm` | PS admin DNS config | OS / DNS service |
| `DNSint` | Internal DNS entries | OS / DNS service |
| `Saprouttab` | SAP router table entries | OS / SAP |
| `SolInfo` | Solution metadata (SIDs, roles, landscape) | Reference / SCP metadata |
| `BackupInfo` | Backup job and policy definitions | Backup agent / SCP |
| `Port` | Port assignments per service | SCP SG / NSX-T |
| `HWReadiness` | Hardware readiness checklist | VMware / BMC |
| `Customer System Info` | System overview / summary table | Reference only |
| `ArchiDesign` | Architecture design reference | Reference only |

**Action:** Do not implement in current sprint. Add to `SHEET_REGISTRY` as `required=False` stubs when the corresponding collector or validator is scoped.

---

### 2. Future OS / config scope

Sheets that target OS-level configuration, users, and parameters. Parsers for these will feed OS inspection and Ansible-based validators, not SCP or VMware APIs.

> **Explicitly called out:** `OSUserInfo`, `OSParam_NW`, `OSParam_HANA`

| Sheet | Structure hint | Output domain | Drift method | Notes |
|-------|----------------|---------------|--------------|-------|
| `OSUserInfo` | `simple_table` (row2 header, row3+ data) | `os_users` | `os_getent_passwd` | OS accounts (`id` / `getent passwd`). Already stubbed in registry comments. |
| `OSParam_NW` | `narrative` (free-form text) | `rag_os_nw` | `llm_rag` | OS network tuning params. RAG source only — no structured extraction; LLM compares against OS check output. Already stubbed in registry comments. |
| `OSParam_HANA` | `narrative` (free-form text) | `rag_os_hana` | `llm_rag` | OS HANA-specific params. Same RAG-only treatment as `OSParam_NW`. Already stubbed in registry comments. |
| `ApplUserInfo` | `simple_table` | `appl_users` | `os_getent_passwd` | Application-level user accounts |
| `ApplRoleInfo` | `simple_table` | `appl_roles` | `os_id` | Application role assignments |
| `CArkOS` | `simple_table` | `cark_os` | `cyberark_api` | CyberArk OS account provisioning |
| `CArkApp` | `simple_table` | `cark_app` | `cyberark_api` | CyberArk application account provisioning |
| `CArkSafeUser` | `simple_table` | `cark_safe_user` | `cyberark_api` | CyberArk Safe/User mapping |
| `Audit_Config` | `simple_table` | `audit_config` | `os_auditctl` | OS audit rules |
| `Users` | `simple_table` | `os_users` | `os_getent_passwd` | May overlap with `OSUserInfo` |
| `SWAP` | `simple_table` | `swap_config` | `os_swapon` | Swap space configuration |
| `Raw.osuser` | raw data | — | — | Source data for `OSUserInfo`; likely not parsed directly |
| `Raw.fs` | raw data | — | — | Source data for `FileSystem`; may duplicate already-registered sheet |
| `TDD_U.GID` | `simple_table` | — | — | GID reference table; supplementary to `OSUserInfo` |
| `TDD_FileSys` | `simple_table` | — | — | TDD fixture for `FileSystem`; not a standalone sheet to parse |

**Action for `OSUserInfo`:** Add to `SHEET_REGISTRY` as `simple_table`, `required=False`, `drift_method="os_getent_passwd"` when OS user validation is scoped. Parser stub already exists as a commented registry entry.

**Action for `OSParam_NW` / `OSParam_HANA`:** Add to `SHEET_REGISTRY` as `narrative`, `required=False` when LLM-RAG layer is scoped. Read as raw text block; pass to LLM for semantic comparison with OS inspection results. Parser stubs already exist as commented registry entries.

---

### 3. Future SAP / application scope

Sheets that capture SAP application parameters, hardening rules, and configuration references. These are outside the SCP/VMware/NSX-T infrastructure layer and require SAP-specific collectors or LLM-based semantic comparison.

| Sheet | Description |
|-------|-------------|
| `NetWeaverParam` | SAP NetWeaver OS/system parameter spec |
| `HANAParam` | SAP HANA OS/system parameter spec |
| `ABAPConfig` | ABAP stack configuration |
| `JAVAConfig` | Java stack (NWJAVA) configuration |
| `000Client` | SAP 000 client settings |
| `Inst_R` | Installation record |
| `Hard_NWABAP` | ABAP hardening checklist |
| `Hard_HANA` | HANA hardening checklist |
| `Hard_NWJAVA` | NWJAVA hardening checklist |
| `Hard_ASE` | Sybase ASE hardening checklist |
| `Hard_Tomcat` | Tomcat hardening checklist |
| `Hard_BOBJ` | BusinessObjects hardening checklist |
| `TDD_InstNo` | Installation number TDD reference |
| `TDD_NWParam` | NetWeaver parameter TDD reference |
| `TDD_HANAParam` | HANA parameter TDD reference |
| `TDD_ASEParam` | ASE parameter TDD reference |
| `TDD_BOBJParam` | BOBJ parameter TDD reference |
| `TDD_IQParam` | SAP IQ parameter TDD reference |
| `TDD_MaxParam` | MaxDB parameter TDD reference |
| `SolInfo` | Solution info (SIDs, component landscape) |

**Action:** Out of MVP scope. Do not implement. These require SAP-layer LLM validation or SAP API integration, which is not in the current sprint backlog.

---

### 4. Ignore — process tracking and versioning

Sheets used for project management, task tracking, or version history within the workbook. They carry no infra desired-state and should never be parsed.

| Sheet | Reason to ignore |
|-------|-----------------|
| `Build_Status` | Build process tracking; not desired-state data |
| `Build_Tasks` | Task checklist for the delivery engineer |
| `Build_Tasks_bak` | Backup copy of `Build_Tasks` |
| `3.0.0` | Version/phase sheet (version tag as sheet name) |
| `5.0.0` | Version/phase sheet |
| `6.0.0` | Version/phase sheet |
| `7.0.0` | Version/phase sheet |
| `8-1.0.0` | Version/phase sheet |
| `8-2.0.0` | Version/phase sheet |
| `9-1.0.0` | Version/phase sheet |
| `9-2.0.0` | Version/phase sheet |
| `10.0.0` | Version/phase sheet |
| `11-1.0.0` | Version/phase sheet |
| `11-2.0.0` | Version/phase sheet |
| `12.0.0` | Version/phase sheet |
| `12.4.0` | Version/phase sheet |
| `13.0.0` | Version/phase sheet |
| `14-1.0.0` | Version/phase sheet |
| `14-2.0.0` | Version/phase sheet |
| `15-1.0.0` | Version/phase sheet |
| `15-2.0.0` | Version/phase sheet |
| `16.0.0` | Version/phase sheet |
| `17.0.0` | Version/phase sheet |

**Action:** No registry entry. These sheets must remain unsupported indefinitely. Consider filtering them from the coverage `unsupported_sheets` list in a future coverage report improvement (e.g., by name-pattern exclusion or an explicit ignore list in the registry).

---

## Triage Summary

| Category | Count | Action |
|----------|-------|--------|
| Out of MVP scope — infra-related | 10 | Add to registry as stubs when scoped |
| Future OS / config scope | 15 | `OSUserInfo`, `OSParam_NW`, `OSParam_HANA` already stubbed; others pending |
| Future SAP / application scope | 20 | Out of MVP; no action |
| Ignore — process tracking / versioning | 22 | Never parse; consider exclusion filter |
| **Total unsupported** | **67** | |

---

## Registry Stub Candidates

Sheets that are close enough to MVP scope to warrant a commented registry stub now:

```python
# In src/parser/registry.py SHEET_REGISTRY (already present as comments):
# SheetConfig("OSUserInfo",   StructureType.SIMPLE_TABLE, ..., "os_getent_passwd", "os_users",   required=False),
# SheetConfig("OSParam_NW",   StructureType.NARRATIVE,    ..., "llm_rag",          "rag_os_nw",  required=False),
# SheetConfig("OSParam_HANA", StructureType.NARRATIVE,    ..., "llm_rag",          "rag_os_hana",required=False),

# Candidates to add when OS scope is expanded:
# SheetConfig("ApplUserInfo", StructureType.SIMPLE_TABLE, ..., "os_getent_passwd", "appl_users", required=False),
# SheetConfig("CArkOS",       StructureType.SIMPLE_TABLE, ..., "cyberark_api",     "cark_os",    required=False),
# SheetConfig("Port",         StructureType.SIMPLE_TABLE, ..., "nsxt_dfw_api",     "port_map",   required=False),
```
