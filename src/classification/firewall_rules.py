"""Firewall rule classification — converts generic candidates into platform-specific lists.

Decision tree (see docs/firewall_rule_classification.md):
  1. PSM-flagged rules → always reference_only (for audit/coordination).
     If also cus_fw=True with external endpoint → additionally added to tgw.
  2. internal → internal → nsxt_dfw_candidates
  3. cus_fw=True + external endpoint → tgw_candidates
  4. cus_sg=True + unknown source → tgw_candidates (requires_manual_review=True)
  5. else → reference_only (reason="unclassifiable")
"""

import ipaddress
from dataclasses import dataclass, field

from src.parser._utils import is_valid_ipv4
from src.classification.endpoint_resolver import resolve_endpoint, is_cidr_notation

# Placeholder values that indicate unresolved IPs — not real addresses.
_PLACEHOLDER_IPS = {"0", "1", "2", "3", "4", "-", "", "None"}


# ---------------------------------------------------------------------------
# Endpoint classification
# ---------------------------------------------------------------------------

EndpointType = str  # "internal" | "external" | "unknown"


def classify_endpoint(
    ip: object,
    hostname: str | None,
    vm_hostnames: set[str],
    subnet_networks: list,
) -> EndpointType:
    """Classify an endpoint as internal, external, or unknown.

    Priority:
      1. Hostname in known VM set → internal
      2. Valid IP in a known subnet → internal
      3. Valid IP not in any subnet → external
      4. Placeholder or missing → unknown
    """
    # Hostname match takes priority — more stable than IP in this workbook.
    if hostname and hostname in vm_hostnames:
        return "internal"

    ip_str = str(ip).strip() if ip is not None else ""
    if ip_str in _PLACEHOLDER_IPS or not ip_str:
        # No usable IP — fall back to hostname check (already done above).
        return "unknown"

    if not is_valid_ipv4(ip_str):
        return "unknown"

    try:
        addr = ipaddress.ip_address(ip_str)
        if any(addr in net for net in subnet_networks):
            return "internal"
        return "external"
    except ValueError:
        return "unknown"


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    tgw_candidates:  list[dict] = field(default_factory=list)
    dfw_candidates:  list[dict] = field(default_factory=list)
    reference_only:  list[dict] = field(default_factory=list)
    warnings:        list[str]  = field(default_factory=list)


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------

def _tgw_entry(
    idx: int,
    c: dict,
    review: bool,
    vm_hostnames: set[str],
    subnet_networks: list,
    platform_networks: list | None = None,
) -> dict:
    src_ip       = c.get("source_ip")
    tgt_ip       = c.get("target_ip")
    src_hostname = c.get("source_hostname")
    tgt_hostname = c.get("target_hostname")

    src_class = resolve_endpoint(src_ip, src_hostname, vm_hostnames, subnet_networks, platform_networks)
    tgt_class = resolve_endpoint(tgt_ip, tgt_hostname, vm_hostnames, subnet_networks, platform_networks)

    return {
        "origin_idx":             idx,
        "source_system":          c["source_system"],
        "source_category":        c.get("source_category"),
        "source_hostname":        src_hostname,
        "source_ip":              src_ip,
        "target_system":          c["target_system"],
        "target_category":        c.get("target_category"),
        "target_hostname":        tgt_hostname,
        "target_ip":              tgt_ip,
        "port":                   c.get("port"),
        "port_expression":        c.get("port_expression", False),
        "protocol":               c.get("protocol"),
        "expiration":             c.get("expiration"),
        "purpose":                c.get("purpose"),
        "requires_manual_review": review,
        "src_endpoint_class":     src_class,
        "tgt_endpoint_class":     tgt_class,
        "src_is_cidr":            is_cidr_notation(src_ip),
        "tgt_is_cidr":            is_cidr_notation(tgt_ip),
    }


def _dfw_entry(idx: int, c: dict) -> dict:
    return {
        "origin_idx":      idx,
        "source_hostname": c.get("source_hostname"),
        "source_ip":       c.get("source_ip"),
        "target_hostname": c.get("target_hostname"),
        "target_ip":       c.get("target_ip"),
        "port":            c.get("port"),
        "port_expression": c.get("port_expression", False),
        "protocol":        c.get("protocol"),
        "purpose":         c.get("purpose"),
        "applied_to":      "both",
    }


def _ref_entry(idx: int, c: dict, reason: str, note: str | None = None) -> dict:
    return {
        "origin_idx":    idx,
        "reason":        reason,
        "source_system": c.get("source_system"),
        "target_system": c.get("target_system"),
        "purpose":       c.get("purpose"),
        "note":          note,
    }


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------

def classify_candidates(
    candidates: list[dict],
    vm_hostnames: set[str],
    subnet_networks: list,
    platform_networks: list | None = None,
) -> ClassificationResult:
    """Classify firewall_rule_candidates into platform-specific rule lists.

    Args:
        candidates:      Output of parse_securitygroup().
        vm_hostnames:    Set of all known hostnames from vmware_vm[].
        subnet_networks: List of ipaddress.IPv4Network objects from network.subnets[].

    Returns:
        ClassificationResult with tgw_candidates, dfw_candidates, reference_only, warnings.
    """
    result = ClassificationResult()

    for idx, c in enumerate(candidates):
        src_type = classify_endpoint(
            c.get("source_ip"), c.get("source_hostname"), vm_hostnames, subnet_networks
        )
        tgt_type = classify_endpoint(
            c.get("target_ip"), c.get("target_hostname"), vm_hostnames, subnet_networks
        )

        psm_managed = c.get("psm_fw") or c.get("psm_sg")
        cus_fw      = c.get("cus_fw", False)
        cus_sg      = c.get("cus_sg", False)

        routed_to_customer = False

        # ── 1. PSM-flagged → always reference_only for audit ─────────────────
        if psm_managed:
            result.reference_only.append(_ref_entry(idx, c, "psm_managed"))
            # PSM co-managed with cus_fw: also route to tgw for customer execution.
            if cus_fw and (
                src_type == "external" or tgt_type == "external"
                or src_type == "unknown" or tgt_type == "unknown"
            ):
                result.tgw_candidates.append(
                    _tgw_entry(idx, c, review=False, vm_hostnames=vm_hostnames,
                               subnet_networks=subnet_networks, platform_networks=platform_networks)
                )
                routed_to_customer = True
            continue

        # ── 2. internal → internal → NSX-T DFW ───────────────────────────────
        if src_type == "internal" and tgt_type == "internal":
            result.dfw_candidates.append(_dfw_entry(idx, c))
            routed_to_customer = True

        # ── 3. cus_fw + external endpoint → TGW ──────────────────────────────
        elif cus_fw and (src_type == "external" or tgt_type == "external"):
            result.tgw_candidates.append(
                _tgw_entry(idx, c, review=False, vm_hostnames=vm_hostnames,
                           subnet_networks=subnet_networks, platform_networks=platform_networks)
            )
            routed_to_customer = True

        # ── 4. cus_sg + unknown source → TGW with review ─────────────────────
        elif cus_sg and (src_type == "unknown" or tgt_type == "unknown"):
            result.tgw_candidates.append(
                _tgw_entry(idx, c, review=True, vm_hostnames=vm_hostnames,
                           subnet_networks=subnet_networks, platform_networks=platform_networks)
            )
            routed_to_customer = True

        # ── 5. Unclassifiable ─────────────────────────────────────────────────
        if not routed_to_customer:
            result.reference_only.append(_ref_entry(idx, c, "unclassifiable"))

    return result


# ---------------------------------------------------------------------------
# Helpers for building index structures from desired-state
# ---------------------------------------------------------------------------

def build_vm_hostnames(vmware_vm: list[dict]) -> set[str]:
    """Extract all hostname identifiers from parsed vmware_vm list."""
    hostnames: set[str] = set()
    for vm in vmware_vm:
        for section, keys in [
            ("identity", ("vhost", "phost")),
            ("network",  ("service_hostname", "admin_hostname", "backup_hostname")),
        ]:
            for k in keys:
                h = vm.get(section, {}).get(k)
                if h:
                    hostnames.add(h)
    return hostnames


def build_subnet_networks(subnets: list[dict]) -> list:
    """Parse ip_range and nat_ip_range from subnet list into IPv4Network objects."""
    networks = []
    for s in subnets:
        for field in ("ip_range", "nat_ip_range"):
            raw = s.get(field)
            if not raw or str(raw).upper() in ("N/A", "NONE", "", "NAT FOR PUBLIC"):
                continue
            try:
                net = ipaddress.ip_network(str(raw).strip(), strict=True)
                if net.prefixlen >= 8:
                    networks.append(net)
            except ValueError:
                try:
                    # Host bits set — include with loose parsing for coverage.
                    net = ipaddress.ip_network(str(raw).strip(), strict=False)
                    if net.prefixlen >= 8:
                        networks.append(net)
                except ValueError:
                    pass
    return networks
