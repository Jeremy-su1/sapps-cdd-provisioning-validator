"""Accinfo sheet parser — extracts project metadata and global network context."""

from src.parser._utils import normalize_cidr_list, is_blank_row

_LABEL_COL = 0
_VALUE_COL = 6  # column G, 0-indexed

# Maps normalized label → (output_section, field_key)
# "project_metadata" or "network_context"
_LABEL_MAP: dict[str, tuple[str, str]] = {
    "customer name":                   ("project_metadata",    "customer_name"),
    "customer (cid)":                  ("project_metadata",    "customer_id"),
    "domain name":                     ("project_metadata",    "domain_name"),
    "system timezone":                 ("project_metadata",    "timezone"),
    "ip range":                        ("network_context",     "ip_range"),
    "dr ip range":                     ("network_context",     "dr_ip_range"),
    "customer connectivity":           ("network_context",     "connectivity_type"),
    "customer n/w":                    ("network_context",     "customer_networks"),
    "customer dns server (primary)":   ("network_context",     "dns_primary"),
    "customer dns server (secondary)": ("network_context",     "dns_secondary"),
}

# Section headers: silently skip — neither warning nor ignored
_SECTION_HEADERS = {
    "general information",
    "scp information",
}

# "SID Information" stops parsing entirely (deferred to a later phase)
_DEFER_SENTINEL = "sid information"

# Valid labels that are out of MVP scope → go to ignored_labels
_KNOWN_IGNORED_LABELS = {
    "vpc name",
    "master password",
    "s-user for sap service marketplace",
    "technical communication user for sap service marketplace",
    "rise with sap installation number",
    "scp customer account number",
    "scp project name",
    "subnet",
    "customer connectivity",   # kept here in case label format varies
    "vpc name",
    "system install sla",
    "hbr sla",
}

# Multi-value fields that must be split on newline
_MULTILINE_FIELDS = {"customer_networks"}


def _default_project_metadata() -> dict:
    return {
        "customer_name": None,
        "customer_id":   None,
        "domain_name":   None,
        "timezone":      None,
    }


def _default_network_context() -> dict:
    return {
        "ip_range":          None,
        "dr_ip_range":       None,
        "connectivity_type": None,
        "customer_networks": [],
        "dns_primary":       None,
        "dns_secondary":     None,
    }


def parse_accinfo(ws) -> tuple[dict, dict, list[str], list[str]]:
    """Parse the Accinfo sheet.

    Returns (project_metadata, global_network_context, parser_warnings, ignored_labels).
    """
    meta = _default_project_metadata()
    ctx  = _default_network_context()
    warnings: list[str] = []
    ignored:  list[str] = []

    for raw_row in ws.iter_rows(values_only=True):
        if is_blank_row(raw_row):
            continue

        label_raw = raw_row[_LABEL_COL]
        if label_raw is None:
            continue

        label_norm = str(label_raw).strip().lower()

        # Stop parsing after SID Information sentinel
        if label_norm == _DEFER_SENTINEL:
            break

        # Skip known section headers silently
        if label_norm in _SECTION_HEADERS:
            continue

        value = raw_row[_VALUE_COL] if len(raw_row) > _VALUE_COL else None

        # In-scope field
        if label_norm in _LABEL_MAP:
            section, field = _LABEL_MAP[label_norm]
            if field in _MULTILINE_FIELDS:
                parsed = normalize_cidr_list(value)
            else:
                parsed = str(value).strip() if value is not None else None

            if section == "project_metadata":
                meta[field] = parsed
            else:
                ctx[field] = parsed
            continue

        # Known out-of-scope label
        if label_norm in _KNOWN_IGNORED_LABELS:
            ignored.append(label_norm)
            continue

        # Truly unknown label
        warnings.append(f"unknown label: {label_raw!r}")

    return meta, ctx, warnings, ignored
