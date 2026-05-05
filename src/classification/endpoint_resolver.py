"""Enhanced endpoint classification — 5-way taxonomy for SCP Firewall planning.

Endpoint classes:
  internal          — VM hostname match, or IP/CIDR in our managed subnet space
  customer_external — private RFC 1918 outside our subnets, or landscape label hostnames
  shared_platform   — SCP/PSM platform service networks (configurable)
  managed_external  — public internet IP or CIDR
  unknown           — placeholder, empty, or genuinely unresolvable

Resolution priority (first match wins):
  1. Hostname in vm_hostnames          → internal
  2. Hostname is a landscape label     → customer_external
  3. Raw value is a placeholder/empty  → unknown
  4. Parse as CIDR or host IP:
       Overlaps one of our subnets     → internal
       Overlaps a platform network     → shared_platform
       Private RFC 1918                → customer_external
       Public (not RFC 1918)           → managed_external
  5. Not parseable                     → unknown
"""

from __future__ import annotations

import ipaddress

from src.parser._utils import is_valid_ipv4

EndpointClass = str  # Literal["internal","customer_external","shared_platform","managed_external","unknown"]

_PLACEHOLDER_IPS: set[str] = {"0", "1", "2", "3", "4", "-", "", "None"}

# SAP landscape environment labels that appear as pseudo-hostnames.
_LANDSCAPE_LABELS: set[str] = {"PRD", "DR", "QAS", "DEV", "NON-PRD", "NON-DR", "BUILD"}

_RFC1918 = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]


def is_cidr_notation(raw: object) -> bool:
    """Return True when raw looks like an IP network in CIDR notation (has a prefix)."""
    s = str(raw).strip() if raw is not None else ""
    if "/" not in s:
        return False
    try:
        ipaddress.ip_network(s, strict=False)
        return True
    except ValueError:
        return False


def _classify_network(
    net: ipaddress.IPv4Network,
    subnet_networks: list,
    platform_networks: list | None,
) -> EndpointClass:
    """Classify an already-parsed network against known address spaces."""
    # Overlaps with any of our managed subnets → internal
    for sn in subnet_networks:
        if net.overlaps(sn):
            return "internal"
    # Overlaps with a known platform network → shared_platform
    if platform_networks:
        for pn in platform_networks:
            if net.overlaps(pn):
                return "shared_platform"
    # Private RFC 1918 but outside our subnets → customer_external
    for rfc in _RFC1918:
        if net.overlaps(rfc):
            return "customer_external"
    # Public internet
    return "managed_external"


def resolve_endpoint(
    raw_ip: object,
    hostname: str | None,
    vm_hostnames: set[str],
    subnet_networks: list,
    platform_networks: list | None = None,
) -> EndpointClass:
    """Classify an endpoint into one of five endpoint classes.

    Args:
        raw_ip:           Raw IP string, CIDR string, or numeric placeholder from workbook.
        hostname:         Hostname string (may be a landscape label like "PRD").
        vm_hostnames:     Set of all known VM/host names in our managed environment.
        subnet_networks:  List of ipaddress.IPv4Network objects representing our subnets.
        platform_networks: Optional list of IPv4Network objects for shared platform services.

    Returns:
        One of: "internal", "customer_external", "shared_platform", "managed_external", "unknown".
    """
    # ── Priority 1: Hostname in our VM set ───────────────────────────────────
    if hostname and hostname in vm_hostnames:
        return "internal"

    # ── Priority 2: Landscape label hostname ─────────────────────────────────
    if hostname and hostname.strip().upper() in _LANDSCAPE_LABELS:
        return "customer_external"

    # ── Priority 3: Raw value missing or placeholder ──────────────────────────
    s = str(raw_ip).strip() if raw_ip is not None else ""
    if not s or s in _PLACEHOLDER_IPS:
        return "unknown"

    # ── Priority 4a: CIDR notation ────────────────────────────────────────────
    if "/" in s:
        try:
            net = ipaddress.ip_network(s, strict=False)
            return _classify_network(net, subnet_networks, platform_networks)
        except ValueError:
            return "unknown"

    # ── Priority 4b: Host IP ──────────────────────────────────────────────────
    if not is_valid_ipv4(s):
        return "unknown"

    try:
        addr = ipaddress.ip_address(s)
        # In one of our managed subnets → internal
        if any(addr in sn for sn in subnet_networks):
            return "internal"
        # Platform network → shared_platform
        if platform_networks and any(addr in pn for pn in platform_networks):
            return "shared_platform"
        # Private RFC 1918 → customer_external
        if any(addr in rfc for rfc in _RFC1918):
            return "customer_external"
        return "managed_external"
    except ValueError:
        return "unknown"
