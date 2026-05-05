# S2D Sheet Analysis

## 1. Purpose

This document defines which sheets in the SAP PS S2D Build Sheet are relevant for the current MVP and how they should be interpreted for provisioning and validation.

Goals:
- identify in-scope vs out-of-scope sheets
- define target desired-state objects per sheet
- guide implementation of sheet-specific semantic parsers
- serve as the input analysis baseline for the `s2d-parser`

---

## 2. MVP Scope

Current MVP supports only:

1. TGW-related provisioning
2. Firewall provisioning
3. VMware VM provisioning
4. NSX-T Distributed Firewall provisioning

Sheets in scope:
- `Accinfo`
- `NWInfo`
- `ServerInfo`
- `FileSystem`
- `SecurityGroup`

Sheets out of scope for now:
- `Build_Status`
- `Build_Tasks`
- `Build_Tasks_bak`
- `DNScust`
- `DNSpsadm`
- `DNSint`
- `Saprouttab`
- other app/install/hardening/ops sheets

---

## 3. Sheet Analysis

### 3.1 `Accinfo`

#### Role
Provides global project and customer metadata.
This sheet is not a resource table. It should be treated as global context for interpreting other sheets.

#### Important fields
- Customer Name
- Customer (CID)
- IP Range
- DR IP Range
- Domain Name
- Customer N/W
- Customer DNS server
- connectivity-related values
- common SLA / install metadata

#### Parser output role
Map this sheet into high-level shared objects such as:
- `project_metadata`
- `customer_context`
- `global_network_context`

#### Example output
```json
{
  "project_metadata": {
    "customer_name": "Generic Corp",
    "customer_id": "GCI",
    "domain_name": "sap.generic.net",
    "ip_range": "10.0.0.0/22",
    "dr_ip_range": "...",
    "customer_dns_servers": []
  }
}