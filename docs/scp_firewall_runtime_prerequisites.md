# SCP Firewall Runtime Prerequisites

All inputs and environment assumptions required for real read-only execution of the SCP Firewall collector path.

---

## 1. Python Environment

| Requirement | Version / Detail |
|-------------|-----------------|
| Python | 3.11+ (f-strings, `list[T]` type hints, `str \| None`) |
| openpyxl | Required for workbook parsing (`parse_s2d_with_summary`) |
| Standard library only | `hmac`, `hashlib`, `base64`, `urllib.request`, `json`, `time` — no extra HTTP client needed |

Install from repo root:

```bash
pip install -r requirements.txt
```

No third-party HTTP library (requests, httpx) is required. The collector uses `urllib.request` with manual HMAC-SHA256 signing.

---

## 2. Environment Variables

The collector reads three variables. If any is missing, it falls back to `dry_run=True` automatically:

```bash
export SCP_ENDPOINT="https://firewall.{region}.{env}.samsungsdscloud.com"
export SCP_ACCESS_KEY="<your-access-key-id>"
export SCP_SECRET_KEY="<your-secret-key>"
```

### `SCP_ENDPOINT`

Format: `https://firewall.{region}.{env}.samsungsdscloud.com`

| Placeholder | Example values |
|-------------|----------------|
| `{region}` | `kr-west1`, `kr-east1`, etc. |
| `{env}` | `e` (external/commercial), `gov` |

**This is a service-specific base URL**, not the generic `openapi.samsungsdscloud.com`. The firewall API does not share the generic endpoint.

Do not append a trailing slash. The collector does `endpoint.rstrip("/") + path`.

### `SCP_ACCESS_KEY`

The Access Key ID assigned to the SCP project IAM user. Visible in the SCP Console under IAM → Access Keys.

Used in:
- `Scp-Accesskey` header (plaintext)
- HMAC signature message: `METHOD + PATH + TIMESTAMP + ACCESS_KEY`

### `SCP_SECRET_KEY`

The HMAC signing key corresponding to the Access Key ID. Shown once at creation time in the SCP Console.

Used as the HMAC-SHA256 key: `hmac_sha256(secret_key.encode(), message.encode())`.

**Never commit or log this value.**

---

## 3. IAM Permissions

The Access Key must belong to an IAM user (or role) with **read-only** firewall permissions in the target SCP project.

Minimum permissions required:

| Operation | API Path | Permission |
|-----------|----------|-----------|
| List firewalls | `GET /v1/firewalls` | `firewall:list` or equivalent |
| List firewall rules | `GET /v1/firewalls/rules` | `firewall:rule:list` or equivalent |

Verify in SCP Console: **IAM → Policies → Firewall → Read** before running live.

No write permissions are needed or used in this path.

---

## 4. Network Access

The machine running the script must be able to reach the SCP Firewall API endpoint over HTTPS (port 443).

Checklist:
- [ ] Outbound HTTPS allowed from the execution host to `*.samsungsdscloud.com`
- [ ] No corporate proxy intercepts the TLS connection (would break HMAC signature verification)
- [ ] DNS resolves `firewall.{region}.{env}.samsungsdscloud.com`

Quick check:

```bash
curl -v https://firewall.{region}.{env}.samsungsdscloud.com/v1/firewalls \
  -H "Scp-Accesskey: <key>" 2>&1 | grep -E "< HTTP|SSL|Connected"
```

Expected: `< HTTP/1.1 401` (auth error proves connectivity; 200 would require correct headers).

---

## 5. Workbook Requirements

Required only for `debug_scp_firewall_validate_realized_real.py`, not for `debug_scp_firewall_actual_real.py`.

| Requirement | Detail |
|-------------|--------|
| Format | `.xlsx` (Excel Open XML) |
| Required sheets | `Accinfo`, `NWInfo`, `ServerInfo`, `FileSystem`, `SecurityGroup` |
| Location | Pass as CLI argument, or place in `samples/` for auto-discovery |
| Completeness | `SecurityGroup` must have at least one valid firewall rule candidate row |

The workbook drives desired-state generation. If the workbook is empty or has no TGW candidates, `flat_realized` will be empty and the validation result will show 0 realized rules with all actual rules as `unexpected`.

---

## 6. Output Directory

Both scripts write to `outputs/`. The directory is created automatically if absent:

```python
out_path.parent.mkdir(parents=True, exist_ok=True)
```

Verify write permission before running:

```bash
touch outputs/.write_test && rm outputs/.write_test
```

---

## 7. Dry-Run Behavior

If any of the three environment variables is absent, the collector defaults to `dry_run=True`:

```python
dry_run = not (endpoint and access_key and secret_key)
```

In dry-run mode:
- No HTTP requests are made
- `collect()` returns `[]`
- Output JSON contains `"dry_run": true, "actual_count": 0`
- Validation shows all realized rules as `missing`, all actual as empty

This is safe to run at any time without credentials.

---

## 8. Quick Preflight Checklist

Before running live:

- [ ] `SCP_ENDPOINT` set and resolves in DNS
- [ ] `SCP_ACCESS_KEY` and `SCP_SECRET_KEY` exported in the current shell
- [ ] IAM read permissions confirmed in SCP Console
- [ ] Network connectivity to SCP endpoint verified
- [ ] Workbook path known (for validate script)
- [ ] `outputs/` directory is writable
- [ ] Running from repo root so `sys.path` resolution works

```bash
# Confirm env vars are set
echo "Endpoint: $SCP_ENDPOINT"
echo "AccessKey: ${SCP_ACCESS_KEY:0:6}..."

# Confirm Python path
python -c "from src.collector.scp_firewall_collector import ScpFirewallCollector; print('import ok')"
```
