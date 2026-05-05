"""FileSystem sheet parser — extracts storage/filesystem entries."""

from src.parser._utils import normalize_bool, is_blank_row

_HEADER_ROWS = 2


def _parse_size(raw) -> tuple[int | None, str | None]:
    """Return (size_gb, size_formula).

    Plain integers pass through as size_gb.
    Strings and floats are treated as formulas.
    None produces (None, None).
    """
    if raw is None:
        return None, None
    if isinstance(raw, int):
        return raw, None
    # float or string → formula
    return None, str(raw)


def _build_entry(row: tuple) -> dict:
    size_gb, size_formula = _parse_size(row[13])
    return {
        "seq_no":          row[0],
        "landscape":       row[1],
        "sid":             row[2],
        "server_type":     row[3],
        "fs_category_1":   row[4],
        "fs_category_2":   row[5],
        "sla_tier":        row[6],
        "ha_flag":         normalize_bool(row[7]),
        "fs_count_max":    row[8],
        "fs_seq_in_host":  row[9],
        "hostname":        row[10],
        "admin_ip":        row[11],
        "mount_point":     row[12],
        "size_gb":         size_gb,
        "size_formula":    size_formula,
        "fs_type":         row[14],
        "vg_name":         row[15],
        "nfs_group":       row[16],
        "remark":          row[17],
        "check":           row[18],
    }


def parse_filesystem(ws) -> tuple[list[dict], list[str]]:
    """Parse the FileSystem sheet.

    Returns (filesystem_list, warnings). Skips the first 2 header rows.
    Stops at the first fully-blank row.
    """
    entries: list[dict] = []
    warnings: list[str] = []

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < _HEADER_ROWS:
            continue
        if is_blank_row(row):
            break
        entries.append(_build_entry(row))

    return entries, warnings
