# Provisioning Planner Design

**Version:** 1.0  
**Position in pipeline:** after `parse_s2d()`, before any API executor  
**Input:** `desired_state.json`  
**Output:** `action_plan.json`

---

## 1. Role of the Planner

The planner is the **only component** that decides what actions to take. It does not execute them.

Its responsibilities:
- Compare desired state against actual state
- Emit a list of typed, ordered action items
- Flag conflicts that require human approval before execution
- Support dry-run output that can be reviewed and audited before any API call is made

The planner must be **fully deterministic**. The same desired state + same actual state must always produce the same action plan.

The planner must **never**:
- Call any API
- Execute destructive operations
- Infer actions from ambiguous input (emit `conflict` instead)

---

## 2. Action Types

Every item in `action_plan.json` has one of four action types:

| Action | Meaning |
|--------|---------|
| `create` | Resource does not exist in actual state; will be created |
| `update` | Resource exists but has diverged from desired state; will be updated |
| `skip` | Resource already matches desired state; no action needed |
| `conflict` | Desired vs actual state cannot be reconciled automatically; requires human decision |

### 2.1 When to Emit `conflict`

A conflict must be emitted — not guessed — when:

- The actual resource exists with a different identity that cannot be automatically migrated (e.g., different `vhost`, different `sid`)
- A required field in desired state is a placeholder value (e.g., `admin_ip = 0`)
- A destructive change is implied (e.g., resize would require recreation)
- The actual state is ambiguous or partially provisioned
- Two desired-state entries resolve to the same actual resource

Conflicts must be resolved by a human before the executor proceeds. The executor must not skip over conflicts silently.

---

## 3. Action Plan Structure

### 3.1 Top-Level Shape

```json
{
  "plan_id":        "uuid",
  "generated_at":   "ISO-8601 timestamp",
  "desired_state_hash": "sha256 of input",
  "resource_order": ["vmware_vm", "tgw", "firewall", "nsxt_dfw"],
  "actions":        [ ... ],
  "conflicts":      [ ... ],
  "skipped":        [ ... ],
  "summary": {
    "create":   0,
    "update":   0,
    "skip":     0,
    "conflict": 0
  }
}
```

`plan_id` is used to correlate plan generation with subsequent execution. If the desired state changes after the plan is generated, a new plan must be created — the executor must reject a plan whose `desired_state_hash` does not match the input.

### 3.2 Action Item Shape

```json
{
  "action":        "create | update | skip | conflict",
  "resource_type": "vmware_vm | tgw_route | firewall_rule | nsxt_dfw_rule | filesystem",
  "resource_id":   "vhexample01",
  "phase":         1,
  "depends_on":    ["resource_id_a", "resource_id_b"],
  "desired":       { ... },
  "actual":        { ... },
  "diff":          { ... },
  "reason":        "human-readable string explaining the action",
  "requires_approval": false
}
```

`diff` is only populated for `update` and `conflict` actions. It contains only the fields that differ between desired and actual.

`requires_approval` is `true` for any `conflict` action and for any destructive `update` (e.g., CPU/memory downsize, IP change).

---

## 4. Resource Order and Dependencies

The planner must emit actions in an order that respects resource dependencies. Resources must be provisioned in the following MVP sequence:

### Phase 1: VMware VM

VMware VMs must be provisioned first. All other resources depend on VM existence (IP addresses, hostnames, tags).

**Dependencies:** none  
**Blocks:** all other phases

Within Phase 1, the planner must order VMs by:
1. Landscape: `PRD` before `DR` before `QAS` before `DEV`
2. Within a landscape: by `host_no` ascending

VMs with placeholder `admin_ip` (values `0`, `1`, `2`, `3`, `4`) must be emitted as `conflict` unless actual state provides the resolved IP.

### Phase 2: TGW-Related Resources

After VMs are provisioned (or their IPs confirmed from actual state), TGW routes and attachments can be created.

**Dependencies:** Phase 1 VMs must exist and have valid IPs  
**Resources:** TGW route table entries derived from `network.routing_table[]`

### Phase 3: Firewall-Related Resources

Customer-managed firewall rules can be applied once the TGW layer is in place. These derive from `tgw_firewall_rules[]` (output of the classification layer).

**Dependencies:** Phase 2 TGW resources  
**Resources:** TGW firewall policy entries

PSM-managed rules (in `reference_only_rules[]`) must be logged as informational actions — `action: "skip"` with `reason: "psm_managed"` — so they appear in the plan for audit purposes without triggering execution.

### Phase 4: NSX-T DFW-Related Resources

East-west distributed firewall rules can be applied last, once workload VMs are running.

**Dependencies:** Phase 1 VMs  
**Resources:** NSX-T DFW rules from `nsxt_dfw_rules[]`

NSX-T DFW rules with `requires_manual_review=true` must be emitted as `conflict`, not `create`.

---

## 5. Dry-Run Workflow

The planner always operates in dry-run mode. No API is called during plan generation.

```
Workflow:
  1. parse_s2d(workbook_path)      → desired_state
  2. collect_actual_state()        → actual_state   (API read-only calls, separate module)
  3. classify_firewall_rules()     → classified rule lists (separate module)
  4. planner.build_plan(           → action_plan
       desired_state,
       actual_state,
       classified_rules
     )
  5. write action_plan.json        → human review
  6. human approves or rejects
  7. executor.apply(action_plan)   → API write calls (separate module, not yet implemented)
```

Steps 1–5 are the current scope. Steps 6–7 are deferred.

### 5.1 Actual State Collection

`collect_actual_state()` is a read-only operation. It must:
- Call APIs only to read current resource state
- Never modify any resource
- Return `None` (or an empty object) for resources that do not yet exist
- Distinguish between "does not exist" and "API call failed" — the latter is a `conflict`, not a `create`

### 5.2 Plan Idempotency

Running the planner twice against the same desired state and actual state must produce identical output. This is required for:
- Reproducible debugging
- Safe re-planning after partial execution failures
- Audit traceability

---

## 6. Conflict Resolution Protocol

When the planner emits a `conflict`, it must include enough context for a human to decide:

```json
{
  "action":        "conflict",
  "resource_type": "vmware_vm",
  "resource_id":   "vhexample01",
  "desired":       { "admin_ip": 0, "cpu_vcores": 16 },
  "actual":        null,
  "reason":        "admin_ip is a placeholder value (0); cannot provision without a real IP",
  "resolution_hint": "Update the S2D workbook with the assigned IP and re-run the planner",
  "requires_approval": true
}
```

Resolution hints are informational only and must not contain executable logic.

After a human resolves the conflict (e.g., corrects the workbook), the full plan must be regenerated from the corrected desired state. The executor must not accept a partial plan that skips conflicts.

---

## 7. Incremental Add-On Mode

In addition to initial provisioning, the planner must support incremental changes. When a new version of the S2D workbook is supplied:

1. Parse the new desired state
2. Collect actual state (what is currently provisioned)
3. Compare per resource:
   - New resources in desired state → `create`
   - Removed resources (in actual but not in desired) → `conflict` (no auto-delete)
   - Changed resources → `update` (non-destructive) or `conflict` (destructive change)
   - Unchanged resources → `skip`

**Auto-deletion is not permitted in MVP.** Resources present in actual state but absent from the new desired state must always emit `conflict`, not `create` with a delete action. Deletion requires an explicit out-of-band decision.

---

## 8. Planner Module Structure

```text
src/
  planner/
    __init__.py          # build_plan() entry point
    vm_planner.py        # VMware VM action items
    tgw_planner.py       # TGW route/attachment action items
    firewall_planner.py  # TGW firewall rule action items
    dfw_planner.py       # NSX-T DFW rule action items
    _diff.py             # Field-level diff helper
    _types.py            # ActionItem dataclass, action type constants
```

Each sub-planner follows the same interface:

```python
def plan_<resource>(
    desired: list[dict],
    actual: list[dict] | None,
) -> tuple[list[ActionItem], list[ActionItem]]:
    """Returns (action_items, conflicts)."""
```

The top-level `build_plan()` calls each sub-planner in phase order and aggregates results into the `action_plan` structure.

---

## 9. Validation Before Planning

Before the planner runs, a pre-flight validation pass must check:

| Check | Failure action |
|-------|----------------|
| All required VM fields are non-null | Emit `conflict` for that VM |
| All required filesystem join keys are present | Emit warning; continue |
| No duplicate `vhost` in desired state | Emit `conflict` for all duplicates |
| All subnet CIDRs are valid (no host-bits set) | Emit warning; exclude from coverage checks |
| All firewall rules have at least one resolvable endpoint | Emit warning; set `requires_manual_review=true` |

These validations run as a pure function against the desired state object before any actual state collection occurs.

---

## 10. Output Files

| File | Contents |
|------|----------|
| `outputs/action_plan.json` | Full structured action plan |
| `outputs/conflicts.json` | Conflicts only, for focused human review |
| `outputs/plan_summary.md` | Human-readable Markdown summary |

The Markdown summary must include:
- Total counts by action type
- All conflicts listed with reason and resolution hint
- Resource ordering with dependency annotations
- Plan ID and timestamp for audit trail

---

## 11. Execution Backend Notes

The planner output (`action_plan.json`) is **backend-agnostic**. It describes *what* must happen, not *how*. The executor layer (not yet implemented) is responsible for translating action items into API or CLI calls. Backend selection is determined by resource type, not by the planner.

Expected backend assignments by resource type:

| Resource type | Expected backend | Notes |
|---------------|-----------------|-------|
| `vmware_vm` | SCP API or SCP CLI | SCP-managed VMware; exact endpoint TBD |
| `tgw_route` | SCP API or SCP CLI | TGW attachment and routing within SCP |
| `firewall_rule` | SCP API or SCP CLI | Customer-managed perimeter firewall in SCP |
| `nsxt_dfw_rule` | NSX-T API | Standard NSX-T Manager REST API; not SCP-specific |
| Infrastructure layer (future) | Terraform | VPC, subnet, route table, NAT gateway, etc. |
| OS / configuration layer (future) | Ansible | OS hardening, agent install, filesystem mount |

### Backend-agnosticism requirements

The planner must not embed backend-specific identifiers in action items. Specifically:

- Do not include API endpoint URLs, region codes, or credential references in `action_plan.json`
- Do not include Terraform resource addresses or Ansible task names
- Do not assume a specific SCP API version in field names
- `resource_type` values (`vmware_vm`, `nsxt_dfw_rule`, etc.) are logical identifiers — the executor maps them to the correct backend at runtime

### NSX-T DFW specifics

NSX-T DFW rules (from `nsxt_dfw_candidates[]`) use the standard NSX-T Manager REST API independently of SCP. This means:

- DFW rules may be applied via a separate executor module from SCP VM provisioning
- DFW execution requires NSX-T Manager credentials distinct from SCP credentials
- The planner phase for NSX-T DFW (Phase 4) must complete after VMware VMs are provisioned (Phase 1), but is otherwise independent of SCP firewall phases (Phases 2–3)
- `applied_to` in DFW action items specifies the logical policy scope (`"source"`, `"target"`, or `"both"`); the executor resolves this to NSX-T groups or segment ports

### Future backend additions

Adding a new backend (e.g., Terraform for infrastructure, Ansible for OS config) must not require changes to the planner. The action plan schema is the stable interface between planning and execution. New `resource_type` values may be introduced, but existing ones must not be renamed or restructured.

---

## 12. Deferred to Later Phases

The following are explicitly out of scope for the planner MVP:

- API executor (apply phase)
- Drift detection after execution
- Rollback planning
- Scheduling or ordering within a phase (beyond the landscape/host_no rule)
- NSX-T tag management and group resolution
- Cloud-specific VM template selection (uses `scp_image` when populated)
- DNS record provisioning
- Terraform state management
- Ansible inventory generation
