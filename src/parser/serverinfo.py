"""ServerInfo sheet parser — extracts VM/server records."""

from src.parser._utils import split_phost, normalize_bool, is_blank_row, is_valid_ipv4

_HEADER_ROWS = 3
_ENTRY_TYPE_COL = 9   # col J: "server" | "vip" | "lb"


def _parse_nfs(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().upper() == "N/A":
        return None
    return value


def _resolve_phost(row: tuple) -> str:
    adm_ip = row[23]
    adm_hostname = row[22]
    if is_valid_ipv4(adm_ip):
        phost, _ = split_phost(row[2], known_ip=adm_ip)
        return phost
    if adm_hostname:
        return str(adm_hostname).strip()
    phost, _ = split_phost(row[2])
    return phost


def _build_vm(row: tuple) -> dict:
    return {
        "identity": {
            "vhost":         row[1],
            "phost":         _resolve_phost(row),
            "landscape":     row[3],
            "sid":           row[4],
            "role_type":     row[5],
            "main_solution": row[6],
        },
        "compute": {
            "os_version":      row[15],
            "cpu_vcores":      row[16],
            "memory_gb":       row[17],
            "appl_storage_gb": row[18],
            "nfs_storage_gb":  _parse_nfs(row[19]),
            "scp_image":       row[14],
        },
        "network": {
            "service_hostname": row[20],
            "service_ip":       row[21],
            "admin_hostname":   row[22],
            "admin_ip":         row[23],
            "admin_nat_ip":     row[24],
            "backup_hostname":  row[25],
            "backup_ip":        row[26],
            "sr_dr_ip":         row[27],
            "internode_ip":     row[28],
            "hb_ip":            row[29],
        },
        "availability": {
            "sla":            row[30],
            "ha":             normalize_bool(row[31]),
            "dr":             normalize_bool(row[32]),
            "pacemaker":      normalize_bool(row[33]),
            "db_sr":          normalize_bool(row[34]),
            "hana_haf":       normalize_bool(row[35]),
            "backup_enabled": normalize_bool(row[36]),
        },
        "metadata": {
            "phase":            row[0],
            "entry_type":       row[9],
            "role_description": row[10],
            "host_no":          row[11],
            "vm_or_bm":         row[12],
        },
    }


def parse_serverinfo(ws) -> tuple[list[dict], list[str]]:
    """Parse the ServerInfo sheet.

    Returns (vm_list, warnings). Skips the first 3 header rows.
    Only rows whose entry_type (col 9) == 'server' are included.
    Stops at the first fully-blank row.
    """
    vms: list[dict] = []
    warnings: list[str] = []

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < _HEADER_ROWS:
            continue
        if is_blank_row(row):
            break
        entry_type = row[_ENTRY_TYPE_COL]
        if isinstance(entry_type, str) and entry_type.strip().lower() == "server":
            vms.append(_build_vm(row))

    return vms, warnings
