"""Shared parser utilities."""

import re

_IP_PAT = re.compile(r'(\d{1,3}(?:\.\d{1,3}){3})')


def split_phost(raw: str | None, known_ip: str | None = None) -> tuple[str, str]:
    """Split a concatenated 'phost<IP>' string into (hostname, ip).

    ServerInfo col 2 merges physical hostname and admin IP without a separator.
    Pass known_ip (from col 23) for exact suffix stripping when the hostname
    ends in digits that overlap with the IP first octet (e.g. '...0110.x.x.x').
    Falls back to regex-based detection when known_ip is absent or doesn't match.
    """
    if not raw:
        return "", ""
    raw = str(raw)

    if known_ip:
        suffix = str(known_ip).strip()
        if raw.endswith(suffix):
            return raw[: -len(suffix)].strip(), suffix

    m = _IP_PAT.search(raw)
    if m:
        return raw[: m.start()].strip(), m.group(1)
    return raw.strip(), ""


def normalize_bool(value) -> bool:
    """Return True only when value is the string 'O' (case-insensitive, stripped)."""
    return str(value).strip().upper() == "O"


def normalize_cidr_list(raw: str | None) -> list[str]:
    """Split a newline-separated CIDR string into a list, dropping blank entries."""
    if not raw:
        return []
    return [s.strip() for s in str(raw).splitlines() if s.strip()]


def is_blank_row(row: tuple) -> bool:
    """Return True if every cell in the row is None."""
    return all(v is None for v in row)
