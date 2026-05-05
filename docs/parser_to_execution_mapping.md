# Parser to Execution Mapping

Source of truth: `src/parser/registry.py` (SHEET_REGISTRY) and confirmed implemented modules.

**Downstream status definitions**

| Status | Meaning |
|--------|---------|
| `parser-only` | `src/parser/` exists; no planner, collector, or validator wired |
| `planner-ready` | `src/transforms/` realizer exists and produces executable rule objects |
| `collector-ready` | `src/collector/` can fetch actual state from the backend |
| `validator-ready` | `src/validator/` can compare desired vs actual and produce a result |
| `execution-ready` | Full pipeline end-to-end: parser → planner → collector → validator |

---

## Registered Sheet Pipeline Status

### Accinfo

| Field | Value |
|-------|-------|
| Structure type | `key_value_vertical` — label=col[0], value=col[6] |
| Output domain | `project_metadata`, `global_network_context` |
| Drift method | `scp_vpc_subnet_api` |
| Backend target | SCP (VPC metadata, subnet CIDR context) |
| Downstream status | **parser-only** |

**Notes:** Produces customer name, domain, timezone, IP ranges, DNS, and connectivity type. These fields are consumed as context inputs by downstream classifiers (e.g., `platform_networks` used in `classify_candidates()`), but no dedicated SCP VPC collector or metadata validator has been built yet.

---

### NWInfo

| Field | Value |
|-------|-------|
| Structure type | `semi_structured` — state machine over section/env markers |
| Output domain | `network` (`subnets[]`, `routing_table[]`) |
| Drift method | `scp_subnet_cidr` |
| Backend target | SCP (VPC subnet CIDRs) |
| Downstream status | **parser-only** (primary); auxiliary input to TGW classification |

**Notes:** `network.subnets[]` is actively consumed by `build_subnet_networks()` and `_build_platform_networks()` in the SCP Firewall classification step. This makes NWInfo a load-bearing input for the SecurityGroup → TGW Firewall pipeline, even though NWInfo itself has no standalone collector or validator.

---

### ServerInfo

| Field | Value |
|-------|-------|
| Structure type | `merged_header` — row2+row3 composite header, `entry_type="server"` filter |
| Output domain | `vmware_vm[]` |
| Drift method | `vmware_api` |
| Backend target | VMware vCenter |
| Downstream status | **parser-only** |

**Notes:** Produces VM identity, compute spec, network addresses (service/admin/backup/DR IPs), and availability flags (HA, DR, Pacemaker). No VMware collector or validator implemented yet. `build_vm_hostnames()` in `src/classification/firewall_rules.py` consumes the parsed VM list to identify internal hostnames for firewall classification.

---

### FileSystem

| Field | Value |
|-------|-------|
| Structure type | `simple_table` — row1 blank, row2 header, row3+ data |
| Output domain | `filesystem[]` |
| Drift method | `os_df_output` |
| Backend target | Ansible / OS inspection script |
| Downstream status | **parser-only** |

**Notes:** Produces mount points, sizes, VG names, and NFS group assignments. Actual-state collection requires running `df -h` or an equivalent OS inspection script on each target host. No collector, planner, or validator implemented yet.

---

### SecurityGroup — TGW Firewall path

| Field | Value |
|-------|-------|
| Structure type | `simple_table` — row1-2 blank, row3 header, row4+ data |
| Output domain | `firewall_rule_candidates[]` |
| Drift method | `scp_vpc_subnet_api` → TGW Firewall API |
| Backend target | SCP TGW Firewall |
| Downstream status | **execution-ready** |

**Pipeline modules**

| Stage | Module | Status |
|-------|--------|--------|
| Parse | `src/parser/securitygroup.py` | ✅ |
| Classify | `src/classification/firewall_rules.py` → `classify_candidates()` | ✅ |
| Realize | `src/transforms/scp_firewall_realizer.py` → `realize_rules()` | ✅ |
| Collect | `src/collector/scp_firewall_collector.py` → HMAC-signed API, two-phase | ✅ |
| Validate | `src/validator/scp_firewall_validator.py` → `validate_realized_vs_actual()` | ✅ |
| Debug scripts | `scripts/debug_scp_firewall_*.py` | ✅ |

**Notes:** `classify_candidates()` filters `firewall_rule_candidates[]` into `tgw_candidates` (for this path) and `dfw_candidates` (see below). The TGW path handles `direct_create`, `split_create`, `reference_only`, and `unsupported` rule categories. Content-based matching key: `(source_ip, target_ip, protocol, port)`.

---

### SecurityGroup — NSX-T DFW path

| Field | Value |
|-------|-------|
| Structure type | same sheet as above (`SecurityGroup`) |
| Output domain | `firewall_rule_candidates[]` → `dfw_candidates` after classification |
| Drift method | `nsxt_dfw_api` |
| Backend target | NSX-T Distributed Firewall |
| Downstream status | **parser-only** |

**Notes:** `classify_candidates()` populates `dfw_candidates` from the same `SecurityGroup` sheet, but no NSX-T realizer, collector, or validator has been implemented yet. The classification step itself is wired; the downstream execution path is not.

---

## Summary Table

| Sheet | Backend | Status |
|-------|---------|--------|
| Accinfo | SCP VPC | parser-only |
| NWInfo | SCP Subnet | parser-only (feeds TGW classifier) |
| ServerInfo | VMware vCenter | parser-only |
| FileSystem | Ansible / OS | parser-only |
| SecurityGroup → TGW Firewall | SCP TGW Firewall | **execution-ready** |
| SecurityGroup → NSX-T DFW | NSX-T | parser-only |

---

## Next Implementation Targets

Suggested priority order based on MVP scope (TGW → Firewall → VMware VM → NSX-T DFW):

1. **NSX-T DFW path** — classifier already produces `dfw_candidates`; add realizer, collector (`GET /policy/api/v1/infra/domains/default/security-policies`), validator
2. **VMware VM** — add VMware vCenter collector (`GET /rest/vcenter/vm`), spec comparator
3. **NWInfo** — add SCP VPC/Subnet collector, CIDR comparison validator
4. **Accinfo** — metadata validator (low priority; primarily context input)
5. **FileSystem** — requires Ansible playbook or OS inspection integration; out of SCP/VMware scope
