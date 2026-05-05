"""S2D sheet registry — declares structure type, parser, and drift method per sheet.

Each entry in SHEET_REGISTRY answers three questions for a given S2D sheet:
  1. How is the sheet structured? (StructureType)
  2. Which function parses it, and how does its result merge into desired-state?
  3. What actual-state source is used for drift validation? (drift_method)

Adding a new sheet means adding one SheetConfig entry here.
No changes to _parse_wb() are required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from src.parser.accinfo import parse_accinfo
from src.parser.nwinfo import parse_nwinfo
from src.parser.serverinfo import parse_serverinfo
from src.parser.filesystem import parse_filesystem
from src.parser.securitygroup import parse_securitygroup


class StructureType(str, Enum):
    """Structural layout of an S2D sheet — determines how headers and data are located."""

    KEY_VALUE_VERTICAL = "key_value_vertical"
    # Label in col[0], value in col[6]; rows are key-value pairs (AccInfo).

    SEMI_STRUCTURED    = "semi_structured"
    # Multi-section; header row is detected by a sentinel in col[0] or col[1] (NWInfo).

    MERGED_HEADER      = "merged_header"
    # Two or more header rows merged to form composite column labels (ServerInfo).

    SIMPLE_TABLE       = "simple_table"
    # Fixed header row(s) followed by data rows (FileSystem, OSUserInfo, SecurityGroup).

    NARRATIVE          = "narrative"
    # Free-form text; used as RAG source only — no structured extraction (OSParam_*).


@dataclass
class SheetConfig:
    sheet_name:     str
    structure_type: StructureType
    parse_fn:       Callable        # (ws) → parse result (shape varies by sheet)
    merge_fn:       Callable        # (result, state: dict) → None
    drift_method:   str             # annotation: which actual-state source to compare against
    output_domain:  str = ""        # desired-state key(s) this sheet populates
    required:       bool = True     # if True, missing sheet adds a parser warning


# ---------------------------------------------------------------------------
# Merge helpers — one per sheet, handles the specific parse_fn return shape
# ---------------------------------------------------------------------------

def _merge_accinfo(result, state: dict) -> None:
    project_metadata, network_context, warnings, ignored = result
    state["project_metadata"].update(project_metadata)
    state["global_network_context"].update(network_context)
    state["parser_warnings"].extend(warnings)
    state["ignored_labels"].extend(ignored)


def _merge_nwinfo(result, state: dict) -> None:
    network, warnings = result
    state["network"].update(network)
    state["parser_warnings"].extend(warnings)


def _merge_serverinfo(result, state: dict) -> None:
    vmware_vm, warnings = result
    state["vmware_vm"].extend(vmware_vm)
    state["parser_warnings"].extend(warnings)


def _merge_filesystem(result, state: dict) -> None:
    filesystem, warnings = result
    state["filesystem"].extend(filesystem)
    state["parser_warnings"].extend(warnings)


def _merge_securitygroup(result, state: dict) -> None:
    firewall_rule_candidates, warnings = result
    state["firewall_rule_candidates"].extend(firewall_rule_candidates)
    state["parser_warnings"].extend(warnings)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SHEET_REGISTRY: list[SheetConfig] = [
    SheetConfig(
        sheet_name     = "Accinfo",
        structure_type = StructureType.KEY_VALUE_VERTICAL,
        parse_fn       = parse_accinfo,
        merge_fn       = _merge_accinfo,
        drift_method   = "scp_vpc_subnet_api",
        output_domain  = "project_metadata, global_network_context",
    ),
    SheetConfig(
        sheet_name     = "NWInfo",
        structure_type = StructureType.SEMI_STRUCTURED,
        parse_fn       = parse_nwinfo,
        merge_fn       = _merge_nwinfo,
        drift_method   = "scp_subnet_cidr",
        output_domain  = "network",
    ),
    SheetConfig(
        sheet_name     = "ServerInfo",
        structure_type = StructureType.MERGED_HEADER,
        parse_fn       = parse_serverinfo,
        merge_fn       = _merge_serverinfo,
        drift_method   = "vmware_api",
        output_domain  = "vmware_vm",
    ),
    SheetConfig(
        sheet_name     = "FileSystem",
        structure_type = StructureType.SIMPLE_TABLE,
        parse_fn       = parse_filesystem,
        merge_fn       = _merge_filesystem,
        drift_method   = "os_df_output",
        output_domain  = "filesystem",
    ),
    SheetConfig(
        sheet_name     = "SecurityGroup",
        structure_type = StructureType.SIMPLE_TABLE,
        parse_fn       = parse_securitygroup,
        merge_fn       = _merge_securitygroup,
        drift_method   = "nsxt_dfw_api",
        output_domain  = "firewall_rule_candidates",
    ),
    # ── Out of current MVP scope — uncomment and wire parse_fn when adding ──
    # SheetConfig("OSUserInfo",   StructureType.SIMPLE_TABLE, ..., _merge_..., "os_getent_passwd", "os_users"),
    # SheetConfig("OSParam_NW",   StructureType.NARRATIVE,    ..., _merge_..., "llm_rag",          "rag_os_nw"),
    # SheetConfig("OSParam_HANA", StructureType.NARRATIVE,    ..., _merge_..., "llm_rag",          "rag_os_hana"),
]
