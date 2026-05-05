"""SecurityGroup sheet parser — extracts firewall rule candidates."""

import re

from src.parser._utils import normalize_bool

_HEADER_ROWS = 3
_SKIP_COLS = range(13)   # cols 0-12: if all blank → skip row

_SIMPLE_PORT = re.compile(r'^\d+$')


def _is_content_row(row: tuple) -> bool:
    """Return True if at least one of cols 0-12 is non-None."""
    return any(row[i] is not None for i in _SKIP_COLS)


def _normalize_port(raw) -> tuple[str | None, bool]:
    """Return (port_str, port_expression).

    port_expression is True when the port string contains non-digit characters
    (commas, hyphens, tildes) indicating a range or multi-port expression.
    """
    if raw is None:
        return None, False
    s = str(raw)
    return s, not bool(_SIMPLE_PORT.match(s))


def _build_candidate(row: tuple) -> dict:
    port, port_expression = _normalize_port(row[9])
    return {
        "source_system":    row[0],
        "source_category":  row[1],
        "source_hostname":  row[2],
        "source_ip":        row[3],
        "source_landscape": row[4],
        "target_system":    row[5],
        "target_category":  row[6],
        "target_hostname":  row[7],
        "target_ip":        row[8],
        "port":             port,
        "port_expression":  port_expression,
        "protocol":         row[10],
        "expiration":       row[11],
        "purpose":          row[12],
        "cus_fw":           normalize_bool(row[13]),
        "cus_sg":           normalize_bool(row[14]),
        "psm_fw":           normalize_bool(row[15]),
        "psm_sg":           normalize_bool(row[16]),
    }


def parse_securitygroup(ws) -> tuple[list[dict], list[str]]:
    """Parse the SecurityGroup sheet.

    Returns (firewall_rule_candidates, warnings). Skips the first 3 header rows.
    Rows where cols 0-12 are all blank are skipped (not a terminator —
    blank spacer rows may appear between valid data rows).
    """
    candidates: list[dict] = []
    warnings: list[str] = []

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < _HEADER_ROWS:
            continue
        if not _is_content_row(row):
            continue
        candidates.append(_build_candidate(row))

    return candidates, warnings
