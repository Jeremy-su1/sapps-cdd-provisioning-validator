"""NWInfo sheet parser — extracts subnet definitions and routing table.

Sheet structure is multi-section and value-based (no fixed header rows).
State machine detects sections, subsections, and data rows by cell content.

Section markers (col 0):
  "Customer"             → group = "customer"
  "Internal ..."         → group = "internal"
  "Server Routing Table" → routing section

Subsection markers (col 1, within network groups):
  "PRD/non-PRD" → env = "prd"
  "DR"          → env = "dr"
  "No."         → column header row; data collection begins on next rows

Routing section column header (col 0):
  "No."         → column header row; routing data begins on next rows
"""

from src.parser._utils import is_blank_row

# ---------------------------------------------------------------------------
# Purpose-key normalization
# ---------------------------------------------------------------------------

_PURPOSE_KEY_MAP: dict[str, str] = {
    "production service":     "production_service",
    "non-production service": "non_production_service",
    "non production service": "non_production_service",
    "admin":                  "admin",
    "administration":         "admin",
    "heartbeat":              "heartbeat",
    "public":                 "public",
    "public subnet":          "public",
    "storage":                "storage",
    "backup":                 "backup",
}


def _normalize_purpose(raw) -> str:
    if not raw:
        return "other"
    return _PURPOSE_KEY_MAP.get(str(raw).strip().lower(), "other")


# ---------------------------------------------------------------------------
# Cell helpers
# ---------------------------------------------------------------------------

def _str(cell) -> str:
    """Return stripped-lower string; empty string for None."""
    return str(cell).strip().lower() if cell is not None else ""


def _get(row: tuple, idx: int):
    """Safe column access — returns None if column is absent."""
    return row[idx] if len(row) > idx else None


# ---------------------------------------------------------------------------
# Parser state machine
# ---------------------------------------------------------------------------

def _default_network() -> dict:
    return {"subnets": [], "routing_table": []}


def parse_nwinfo(ws) -> tuple[dict, list[str]]:
    """Parse the NWInfo sheet.

    Returns (network_dict, warnings).
    network_dict keys: subnets, routing_table.
    Section boundaries are detected by cell values, not fixed row positions.
    """
    network = _default_network()
    warnings: list[str] = []

    # State
    section: str | None = None   # "customer" | "internal" | "routing"
    env: str | None = None       # "prd" | "dr"
    in_data: bool = False        # True after the "No." column-header row

    for row in ws.iter_rows(values_only=True):
        if is_blank_row(row):
            continue

        col0 = _str(_get(row, 0))
        col1 = _str(_get(row, 1))

        # --- Section markers (col 0) ----------------------------------------
        # Customer/internal markers are only valid outside the routing section.
        # The real NWInfo sheet places a "Customer" annotation row inside the
        # routing table as a visual sub-header; it must not reset section state.
        if col0.startswith("customer") and section != "routing":
            section, env, in_data = "customer", None, False
            continue
        if col0.startswith("internal") and section != "routing":
            section, env, in_data = "internal", None, False
            continue
        if col0 == "server routing table":
            section, env, in_data = "routing", None, False
            continue

        # --- Routing column-header row (col 0 = "no.") ----------------------
        if col0 == "no." and section == "routing":
            in_data = True
            continue

        # --- Subnet subsection / column-header markers (col 1) --------------
        if col1 == "prd/non-prd":
            env, in_data = "prd", False
            continue
        if col1 == "dr":
            env, in_data = "dr", False
            continue
        if col1 == "no." and section in ("customer", "internal"):
            in_data = True
            continue

        # --- Data rows -------------------------------------------------------
        if not in_data or section is None:
            continue

        if section in ("customer", "internal"):
            network["subnets"].append({
                "group":            section,
                "env":              env,
                "seq_no":           _get(row, 1),
                "purpose_raw":      _get(row, 2),
                "purpose_key":      _normalize_purpose(_get(row, 2)),
                "ip_range":         _get(row, 3),
                "nat_ip_range":     _get(row, 4),
                "hostname_pattern": _get(row, 5),
            })
        elif section == "routing":
            network["routing_table"].append({
                "routing_name": _get(row, 1),
                "target_cidr":  _get(row, 2),
                "source_ip":    _get(row, 3),
                "remark":       _get(row, 4),
            })

    return network, warnings
