"""Lightweight consistency checker — cross-sheet reference validation.

Reads the full desired-state from the sample workbook and reports:
  1. Filesystem entries unmatched to any VM (by hostname or admin_ip)
  2. Firewall candidates with source/target hostnames not in the VM inventory
  3. IPs that fall outside all known subnet ranges
  4. Malformed or suspicious subnet CIDRs

Usage (from repo root):
    python scripts/check_consistency.py [path/to/workbook.xlsx]

Defaults to the first .xlsx found in samples/ if no path is given.
Writes results to outputs/consistency_report.json and prints a summary.

NOTE: This is a diagnostic tool, not a validator. Findings are expected in
any real workbook (external FW endpoints, NAT IPs, etc.). The output is
intended to guide human review, not to block provisioning.
"""
import ipaddress
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.parser import parse_s2d
from src.parser._utils import is_valid_ipv4

# CIDRs with prefix shorter than this are treated as suspicious (misconfigured).
_MIN_PREFIX_LEN = 8

# Placeholder values for IP fields — not real IPs.
_IP_PLACEHOLDERS = {"0", "1", "2", "3", "4", "-", "", "None"}

_CIDR_PAT = re.compile(r'^\d{1,3}(\.\d{1,3}){3}/\d{1,2}$')


# ---------------------------------------------------------------------------
# Build index structures
# ---------------------------------------------------------------------------

def _build_vm_index(vms: list[dict]) -> dict:
    """Return sets for fast VM lookup by hostname and IP."""
    phosts        = set()
    admin_ips     = set()
    all_hostnames = set()   # vhost, phost, service_hostname, admin_hostname, backup_hostname

    for vm in vms:
        for field in ("vhost", "phost"):
            h = vm["identity"].get(field)
            if h:
                all_hostnames.add(h)
                if field == "phost":
                    phosts.add(h)

        for field in ("service_hostname", "admin_hostname", "backup_hostname"):
            h = vm["network"].get(field)
            if h:
                all_hostnames.add(h)

        ip = vm["network"].get("admin_ip")
        if ip and str(ip) not in _IP_PLACEHOLDERS and is_valid_ipv4(ip):
            admin_ips.add(str(ip))

    return {
        "phosts":        phosts,
        "admin_ips":     admin_ips,
        "all_hostnames": all_hostnames,
    }


def _parse_subnets(subnets: list[dict]) -> tuple[list, list]:
    """Parse subnet ip_range and nat_ip_range into network objects.

    Returns (valid_networks, malformed_cidrs).
    Networks with prefix < _MIN_PREFIX_LEN are flagged as suspicious.
    """
    valid    = []
    malformed = []

    for s in subnets:
        for field in ("ip_range", "nat_ip_range"):
            raw = s.get(field)
            if not raw:
                continue
            raw_str = str(raw).strip()
            if raw_str.upper() in ("N/A", "NONE", "", "NAT FOR PUBLIC"):
                continue
            if not _CIDR_PAT.match(raw_str):
                malformed.append({
                    "raw":    raw_str,
                    "source": f"subnet {s.get('group','?')}/{s.get('env','?')} {field}",
                    "reason": "not a valid CIDR pattern",
                })
                continue
            try:
                net = ipaddress.ip_network(raw_str, strict=True)
                if net.prefixlen < _MIN_PREFIX_LEN:
                    malformed.append({
                        "raw":    raw_str,
                        "source": f"subnet {s.get('group','?')}/{s.get('env','?')} {field}",
                        "reason": f"suspiciously short prefix /{net.prefixlen}",
                    })
                else:
                    valid.append(net)
            except ValueError:
                try:
                    # Host bits set — common typo (e.g. 192.167.16.128/2 → /25)
                    net = ipaddress.ip_network(raw_str, strict=False)
                    malformed.append({
                        "raw":      raw_str,
                        "network":  str(net),
                        "source":   f"subnet {s.get('group','?')}/{s.get('env','?')} {field}",
                        "reason":   "host bits set — possible prefix length typo",
                    })
                except ValueError:
                    malformed.append({
                        "raw":    raw_str,
                        "source": f"subnet {s.get('group','?')}/{s.get('env','?')} {field}",
                        "reason": "unparseable CIDR",
                    })

    return valid, malformed


def _ip_in_nets(ip_str, networks: list) -> bool:
    if not ip_str or str(ip_str) in _IP_PLACEHOLDERS:
        return True   # skip placeholders — not a real mismatch
    if not is_valid_ipv4(ip_str):
        return True   # skip non-IPv4 (dash, text) — not actionable
    try:
        addr = ipaddress.ip_address(str(ip_str))
        return any(addr in net for net in networks)
    except ValueError:
        return True


# ---------------------------------------------------------------------------
# Check 1: Filesystem entries unmatched to VMs
# ---------------------------------------------------------------------------

def _check_fs_vm_match(filesystem: list[dict], vm_index: dict) -> list[dict]:
    unmatched = []
    for fs in filesystem:
        hostname = fs.get("hostname") or ""
        admin_ip = str(fs.get("admin_ip") or "")
        by_host  = bool(hostname) and hostname in vm_index["phosts"]
        by_ip    = admin_ip not in _IP_PLACEHOLDERS and admin_ip in vm_index["admin_ips"]
        if not by_host and not by_ip:
            unmatched.append({
                "hostname":    hostname or None,
                "admin_ip":    admin_ip or None,
                "landscape":   fs.get("landscape"),
                "sid":         fs.get("sid"),
                "server_type": fs.get("server_type"),
                "mount_point": fs.get("mount_point"),
            })
    return unmatched


# ---------------------------------------------------------------------------
# Check 2: Firewall candidates with unresolved hostnames
# ---------------------------------------------------------------------------

def _check_fw_hostnames(candidates: list[dict], vm_index: dict) -> list[dict]:
    known = vm_index["all_hostnames"]
    unresolved = []
    for fw in candidates:
        for role in ("source", "target"):
            h = fw.get(f"{role}_hostname")
            if h and h not in known:
                unresolved.append({
                    "role":    role,
                    "hostname": h,
                    "system":  fw.get(f"{role}_system"),
                    "ip":      fw.get(f"{role}_ip"),
                    "purpose": fw.get("purpose"),
                })
    return unresolved


# ---------------------------------------------------------------------------
# Check 3: IPs outside known subnet ranges
# ---------------------------------------------------------------------------

_VM_IP_FIELDS = [
    ("service_ip",    "service"),
    ("admin_ip",      "admin"),
    ("admin_nat_ip",  "nat"),
    ("backup_ip",     "backup"),
    ("sr_dr_ip",      "sr_dr"),
    ("internode_ip",  "internode"),
    ("hb_ip",         "hb"),
]


def _check_ip_coverage(
    vms: list[dict],
    filesystem: list[dict],
    candidates: list[dict],
    networks: list,
) -> list[dict]:
    outside = []

    def _record(ip, role, context):
        if not _ip_in_nets(ip, networks):
            outside.append({"ip": str(ip), "role": role, "context": context})

    for vm in vms:
        vhost = vm["identity"]["vhost"]
        for field, label in _VM_IP_FIELDS:
            ip = vm["network"].get(field)
            if ip:
                _record(ip, label, f"vm:{vhost}")

    seen_fs_ips = set()
    for fs in filesystem:
        ip = fs.get("admin_ip")
        if ip and str(ip) not in seen_fs_ips:
            seen_fs_ips.add(str(ip))
            _record(ip, "fs_admin", f"fs:{fs.get('hostname','?')}")

    seen_fw_ips = set()
    for fw in candidates:
        for role in ("source_ip", "target_ip"):
            ip = fw.get(role)
            key = (role, str(ip))
            if ip and key not in seen_fw_ips:
                seen_fw_ips.add(key)
                _record(ip, role, f"fw:{fw.get('purpose','?')}")

    return outside


# ---------------------------------------------------------------------------
# Summarise and print
# ---------------------------------------------------------------------------

def _print_report(report: dict) -> None:
    fs_unmatched = report["filesystem_unmatched_to_vm"]
    fw_unresolved = report["firewall_unresolved_hostnames"]
    ip_outside = report["ips_outside_subnets"]
    malformed = report["malformed_subnet_cidrs"]

    print(f"\n--- Consistency Check Summary ---")
    print(f"  Filesystem entries unmatched to VMs:         {len(fs_unmatched)}")
    print(f"  Firewall hostname references not in VMs:     {len(fw_unresolved)}")
    print(f"  IPs outside known subnet ranges:             {len(ip_outside)}")
    print(f"  Malformed or suspicious subnet CIDRs:        {len(malformed)}")

    if malformed:
        print(f"\n  Malformed CIDRs:")
        for m in malformed:
            print(f"    {m['raw']!r} — {m['reason']}")

    if fs_unmatched:
        print(f"\n  Filesystem entries unmatched to VMs:")
        for fs in fs_unmatched[:10]:
            print(f"    hostname={fs['hostname']}  admin_ip={fs['admin_ip']}"
                  f"  sid={fs['sid']}  server_type={fs['server_type']}")
        if len(fs_unmatched) > 10:
            print(f"    ... and {len(fs_unmatched) - 10} more")

    if fw_unresolved:
        by_system = Counter(r["system"] for r in fw_unresolved)
        print(f"\n  Firewall unresolved hostnames by system (top 10):")
        for sys_name, count in by_system.most_common(10):
            print(f"    {sys_name}: {count}")
        unique_hosts = {r["hostname"] for r in fw_unresolved}
        print(f"  Unique unresolved hostnames: {len(unique_hosts)}")

    if ip_outside:
        by_role = Counter(r["role"] for r in ip_outside)
        print(f"\n  IPs outside subnets by role:")
        for role, count in sorted(by_role.items()):
            print(f"    {role}: {count}")
        unique_ips = {r["ip"] for r in ip_outside}
        print(f"  Unique IPs outside subnets: {len(unique_ips)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _find_sample() -> Path:
    samples = sorted((_REPO_ROOT / "samples").glob("*.xlsx"))
    if not samples:
        raise FileNotFoundError(
            "No .xlsx file found in samples/. "
            "Place the S2D workbook there and retry."
        )
    return samples[0]


def main(workbook_path: Path) -> None:
    print(f"Opening: {workbook_path}")
    result = parse_s2d(str(workbook_path))

    vms        = result["vmware_vm"]
    filesystem = result["filesystem"]
    candidates = result["firewall_rule_candidates"]
    subnets    = result["network"]["subnets"]

    vm_index = _build_vm_index(vms)
    networks, malformed_cidrs = _parse_subnets(subnets)

    report = {
        "filesystem_unmatched_to_vm":     _check_fs_vm_match(filesystem, vm_index),
        "firewall_unresolved_hostnames":  _check_fw_hostnames(candidates, vm_index),
        "ips_outside_subnets":            _check_ip_coverage(vms, filesystem, candidates, networks),
        "malformed_subnet_cidrs":         malformed_cidrs,
    }

    out_path = _REPO_ROOT / "outputs" / "consistency_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"Written:  {out_path}")

    _print_report(report)


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _find_sample()
    main(path)
