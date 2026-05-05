"""SCP Firewall actual state collector.

API reference: https://docs.e.samsungsdscloud.com/en/apireference/networking/firewall/
CLI reference: https://docs.e.samsungsdscloud.com/en/clireference/networking/firewall/

Collection strategy (read-only, API-first):
  Phase 1: GET /v1/firewalls?product_type=TGW_IGW&...&fetch_all unneeded (size=10000)
  Phase 2: For each firewallId: GET /v1/firewalls/rules?firewall_id={id}&fetch_all=true

Authentication: HMAC-SHA256 signed headers (Scp-Accesskey, Scp-Signature, Scp-Timestamp).

In dry-run mode: returns an empty list (no API or CLI calls made).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


_TGW_PRODUCT_TYPES = ["TGW_IGW", "TGW_GGW", "TGW_DGW", "TGW_SIGW", "TGW_BM"]
_ACTION_MAP = {"ALLOW": "permit", "DENY": "deny"}


class CollectorError(Exception):
    """Raised when collection cannot proceed due to missing configuration or API failure."""


def _strip_host_mask(ip: str) -> str:
    """Remove /32 suffix from single-host IPs; leave CIDR ranges untouched."""
    if ip and ip.endswith("/32"):
        return ip[:-3]
    return ip


class ScpFirewallCollector:
    """Collect actual SCP Firewall rule state via SCP API or SCP CLI.

    Args:
        endpoint:         SCP Firewall API base URL.
                          Format: https://firewall.{region}.{env}.samsungsdscloud.com
        access_key:       SCP Access Key ID (from SCP Console IAM).
        secret_key:       SCP Secret Key (used for HMAC-SHA256 signing).
        dry_run:          When True, skip all calls and return empty list.
        execution_method: "scp_api" (default) or "scp_cli".
    """

    def __init__(
        self,
        endpoint: str | None,
        access_key: str | None,
        secret_key: str | None,
        dry_run: bool = False,
        execution_method: str = "scp_api",
    ) -> None:
        self.endpoint         = endpoint
        self.access_key       = access_key
        self.secret_key       = secret_key
        self.dry_run          = dry_run
        self.execution_method = execution_method

    # -------------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------------

    def collect(self) -> list[dict]:
        """Return list of normalized actual SCP Firewall rule dicts.

        Returns an empty list in dry_run mode.
        Dispatches to _fetch_raw_rules_via_api or _fetch_raw_rules_via_cli,
        then normalizes each raw rule via normalize_rule().

        Raises:
            CollectorError: if credentials are missing in real mode.
        """
        if self.dry_run:
            return []

        if not self.endpoint or not self.access_key or not self.secret_key:
            raise CollectorError(
                "SCP endpoint, access_key, and secret_key are required for real collection. "
                "Set dry_run=True to skip calls."
            )

        if self.execution_method == "scp_cli":
            raw_rules = self._fetch_raw_rules_via_cli()
        else:
            raw_rules = self._fetch_raw_rules_via_api()

        return [self.normalize_rule(r) for r in raw_rules]

    def normalize_rule(self, raw: dict) -> dict:
        """Normalize a raw SCP Firewall API rule response into our internal schema.

        Confirmed field mapping from official docs (networking/firewall/models/firewallrule/):
          id                   → resource_id
          firewall_id          → firewall_id
          action               → action  (ALLOW→permit, DENY→deny)
          direction            → direction
          status               → status
          state                → state
          description          → description
          sequence             → sequence
          name                 → name
          source_address[0]    → source_ip  (/32 stripped on host IPs)
          source_address       → source_addresses (full list preserved)
          destination_address[0] → target_ip
          destination_address  → destination_addresses (full list preserved)
          service[0].service_type  → protocol
          service[0].service_value → port  (None for *_ALL / ALL service types)

        All remaining fields are preserved under '_raw' for audit.
        """
        _SCALAR_MAP: dict[str, str] = {
            "id":          "resource_id",
            "firewall_id": "firewall_id",
            "direction":   "direction",
            "status":      "status",
            "state":       "state",
            "description": "description",
            "sequence":    "sequence",
            "name":        "name",
        }
        _HANDLED = frozenset(
            list(_SCALAR_MAP) + ["action", "source_address", "destination_address", "service"]
        )

        normalized: dict[str, Any] = {}
        extra: dict[str, Any] = {}

        for k, v in raw.items():
            if k in _SCALAR_MAP:
                normalized[_SCALAR_MAP[k]] = v
            elif k not in _HANDLED:
                extra[k] = v

        # source_address list → source_ip scalar + full list
        src_list = raw.get("source_address") or []
        normalized["source_addresses"] = src_list
        normalized["source_ip"] = _strip_host_mask(src_list[0]) if src_list else None

        # destination_address list → target_ip scalar + full list
        dst_list = raw.get("destination_address") or []
        normalized["destination_addresses"] = dst_list
        normalized["target_ip"] = _strip_host_mask(dst_list[0]) if dst_list else None

        # service list → protocol + port from first entry
        svc_list = raw.get("service") or []
        if svc_list:
            first = svc_list[0]
            normalized["protocol"] = first.get("service_type")
            raw_value = first.get("service_value")
            normalized["port"] = raw_value if raw_value else None
        else:
            normalized["protocol"] = None
            normalized["port"] = None

        # action mapping
        raw_action = raw.get("action")
        normalized["action"] = _ACTION_MAP.get(raw_action, raw_action)

        # Ensure all known keys are present (None if absent from raw)
        for key in ("resource_id", "firewall_id", "direction", "status", "state",
                    "description", "sequence", "name",
                    "source_ip", "target_ip", "protocol", "port", "action"):
            normalized.setdefault(key, None)

        if extra:
            normalized["_raw"] = extra

        return normalized

    # -------------------------------------------------------------------------
    # Internal: authentication
    # -------------------------------------------------------------------------

    def _build_auth_headers(self, method: str, path: str) -> dict[str, str]:
        """Build HMAC-SHA256 signed SCP API request headers.

        Header names confirmed from all operation examples in official docs:
          Scp-Accesskey, Scp-Signature, Scp-Timestamp, Scp-ClientType,
          Accept-Language, Scp-Api-Version

        Signature message: METHOD + PATH + TIMESTAMP + ACCESS_KEY
        """
        timestamp = str(int(time.time() * 1000))
        message   = method + path + timestamp + (self.access_key or "")
        raw_sig   = hmac.new(
            (self.secret_key or "").encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(raw_sig).decode("utf-8")

        return {
            "Scp-Accesskey":   self.access_key or "",
            "Scp-Signature":   signature,
            "Scp-Timestamp":   timestamp,
            "Scp-ClientType":  "Openapi",
            "Accept-Language": "en-US",
            "Scp-Api-Version": "firewall 1.0",
        }

    # -------------------------------------------------------------------------
    # Internal: HTTP
    # -------------------------------------------------------------------------

    def _api_get(self, path: str, params: dict | None = None) -> dict:
        """Make an authenticated GET request to the SCP Firewall API.

        Array-valued params are repeated as separate query pairs
        (e.g. product_type=TGW_IGW&product_type=TGW_GGW).

        Returns:
            Parsed JSON response dict.

        Raises:
            CollectorError: on HTTP error or network failure.
        """
        if params:
            parts: list[str] = []
            for k, v in params.items():
                if isinstance(v, list):
                    for item in v:
                        parts.append(f"{urllib.parse.quote(k)}={urllib.parse.quote(str(item))}")
                else:
                    parts.append(f"{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}")
            full_path = path + "?" + "&".join(parts)
        else:
            full_path = path

        url     = (self.endpoint or "").rstrip("/") + full_path
        headers = self._build_auth_headers("GET", full_path)
        req     = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise CollectorError(
                f"SCP API request failed: HTTP {exc.code} {exc.reason} — {url}"
            ) from exc
        except urllib.error.URLError as exc:
            raise CollectorError(
                f"SCP API request failed: {exc.reason} — {url}"
            ) from exc

    # -------------------------------------------------------------------------
    # Internal: fetch strategies
    # -------------------------------------------------------------------------

    def _fetch_raw_rules_via_api(self) -> list[dict]:
        """Fetch all SCP Firewall rules via the REST API (two-phase).

        Phase 1: GET /v1/firewalls?product_type=TGW_*&size=10000
          → enumerate all TGW-attached firewalls in the project.

        Phase 2: For each firewallId:
          GET /v1/firewalls/rules?firewall_id={id}&fetch_all=true
          → retrieve all rules without pagination.

        Returns:
            Flat list of raw rule dicts (FirewallRule model, snake_case fields).
        """
        fw_response = self._api_get(
            "/v1/firewalls",
            {"product_type": _TGW_PRODUCT_TYPES, "size": "10000"},
        )
        firewalls = fw_response.get("firewalls") or []

        raw_rules: list[dict] = []
        for fw in firewalls:
            fw_id        = fw["id"]
            rule_response = self._api_get(
                "/v1/firewalls/rules",
                {"firewall_id": fw_id, "fetch_all": "true"},
            )
            raw_rules.extend(rule_response.get("firewall_rules") or [])

        return raw_rules

    def _fetch_raw_rules_via_cli(self) -> list[dict]:
        """Fetch all SCP Firewall rules via the scpcli CLI tool (secondary path).

        CLI commands confirmed from docs.e.samsungsdscloud.com/en/clireference/networking/firewall/:
          Phase 1: scpcli firewall firewall list --product_type TGW_IGW ...
          Phase 2: scpcli firewall firewall-rule list --firewall_id {id} --fetch_all true

        Raises:
            NotImplementedError: until CLI subprocess integration is wired.
        """
        raise NotImplementedError(
            "scpcli firewall-rule list not yet implemented. "
            "Install scpcli and wire subprocess calls. "
            "Use execution_method='scp_api' in the meantime."
        )
