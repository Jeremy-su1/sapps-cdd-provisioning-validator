"""Tests for src/collector/scp_firewall_collector.py — actual state collection interface."""
import pytest
from src.collector.scp_firewall_collector import ScpFirewallCollector, CollectorError


_EP  = "https://firewall.kr-west1.e.samsungsdscloud.com"
_AK  = "test-access-key"
_SK  = "test-secret-key"


def _make(endpoint=_EP, access_key=_AK, secret_key=_SK, dry_run=False, execution_method="scp_api"):
    return ScpFirewallCollector(
        endpoint=endpoint, access_key=access_key, secret_key=secret_key,
        dry_run=dry_run, execution_method=execution_method,
    )


class TestCollectorInterface:
    def test_instantiates_without_error(self):
        assert _make() is not None

    def test_has_collect_method(self):
        assert callable(_make().collect)

    def test_collect_raises_collector_error_without_credentials(self):
        with pytest.raises(CollectorError):
            ScpFirewallCollector(endpoint=None, access_key=None, secret_key=None).collect()

    def test_collect_raises_collector_error_missing_access_key(self):
        with pytest.raises(CollectorError):
            ScpFirewallCollector(endpoint=_EP, access_key=None, secret_key=_SK).collect()

    def test_collect_raises_collector_error_missing_secret_key(self):
        with pytest.raises(CollectorError):
            ScpFirewallCollector(endpoint=_EP, access_key=_AK, secret_key=None).collect()

    def test_collector_error_is_exception(self):
        assert issubclass(CollectorError, Exception)

    def test_dry_run_collect_returns_empty_list(self):
        assert _make(dry_run=True).collect() == []

    def test_dry_run_collect_returns_list_type(self):
        assert isinstance(_make(dry_run=True).collect(), list)

    def test_endpoint_stored(self):
        assert _make(endpoint=_EP).endpoint == _EP

    def test_access_key_stored(self):
        assert _make(access_key="my-key").access_key == "my-key"

    def test_secret_key_stored(self):
        assert _make(secret_key="my-secret").secret_key == "my-secret"

    def test_dry_run_flag_stored(self):
        assert _make(dry_run=True).dry_run is True

    def test_dry_run_defaults_to_false(self):
        assert _make().dry_run is False

    def test_execution_method_stored(self):
        assert _make(execution_method="scp_cli").execution_method == "scp_cli"

    def test_execution_method_defaults_to_scp_api(self):
        assert _make().execution_method == "scp_api"

    def test_real_mode_api_delegates_to_internal_method(self, monkeypatch):
        collector = _make()
        monkeypatch.setattr(collector, "_fetch_raw_rules_via_api", lambda: [])
        assert collector.collect() == []

    def test_real_mode_cli_delegates_to_internal_method(self, monkeypatch):
        collector = _make(execution_method="scp_cli")
        monkeypatch.setattr(collector, "_fetch_raw_rules_via_cli", lambda: [])
        assert collector.collect() == []

    def test_real_mode_api_returns_normalized_rules(self, monkeypatch):
        collector = _make()
        raw = [_raw_rule(id="fw-001", source_address=["10.0.1.11"])]
        monkeypatch.setattr(collector, "_fetch_raw_rules_via_api", lambda: raw)
        result = collector.collect()
        assert len(result) == 1
        assert result[0]["resource_id"] == "fw-001"
        assert result[0]["source_ip"] == "10.0.1.11"

    def test_real_mode_cli_returns_normalized_rules(self, monkeypatch):
        collector = _make(execution_method="scp_cli")
        raw = [_raw_rule(id="fw-002", source_address=["10.0.2.11"])]
        monkeypatch.setattr(collector, "_fetch_raw_rules_via_cli", lambda: raw)
        result = collector.collect()
        assert result[0]["resource_id"] == "fw-002"

    def test_fetch_raw_rules_via_api_exists(self):
        assert callable(_make()._fetch_raw_rules_via_api)

    def test_fetch_raw_rules_via_cli_exists(self):
        assert callable(_make()._fetch_raw_rules_via_cli)

    def test_fetch_raw_rules_via_cli_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            _make()._fetch_raw_rules_via_cli()

    def test_collect_returns_multiple_rules(self, monkeypatch):
        collector = _make()
        raw = [_raw_rule(id=f"fw-{i}") for i in range(2)]
        monkeypatch.setattr(collector, "_fetch_raw_rules_via_api", lambda: raw)
        assert len(collector.collect()) == 2


# ---------------------------------------------------------------------------
# normalize_rule — real SCP API response fields (snake_case, arrays)
# Confirmed from docs.e.samsungsdscloud.com/en/apireference/networking/firewall/
# ---------------------------------------------------------------------------

_UNSET = object()  # sentinel to distinguish None from "use default"


def _raw_rule(
    id="fw-rule-001",
    source_address=_UNSET,
    destination_address=_UNSET,
    service=_UNSET,
    action="ALLOW",
    direction="INBOUND",
    status="ENABLE",
    state="ACTIVE",
    firewall_id="fw-001",
    description="test rule",
    sequence=1,
):
    return {
        "id":                    id,
        "firewall_id":           firewall_id,
        "action":                action,
        "direction":             direction,
        "status":                status,
        "state":                 state,
        "description":           description,
        "sequence":              sequence,
        "source_address":        ["10.0.1.11"] if source_address is _UNSET else source_address,
        "destination_address":   ["203.0.113.5"] if destination_address is _UNSET else destination_address,
        "service":               [{"service_type": "TCP", "service_value": "443"}] if service is _UNSET else service,
        "source_interface":      "IFW1-v2501up",
        "destination_interface": "IFW1-v1001dn",
        "name":                  id,
        "vendor_rule_id":        "72",
        "created_at":            "2024-05-17T00:23:17Z",
        "created_by":            "abc123",
        "modified_at":           "2024-05-17T00:23:17Z",
        "modified_by":           "abc123",
    }


class TestNormalizeRule:
    def _collector(self):
        return ScpFirewallCollector(
            endpoint="https://firewall.kr-west1.e.samsungsdscloud.com",
            access_key="test-key", secret_key="test-secret", dry_run=True
        )

    # --- resource_id ---
    def test_normalize_rule_exists(self):
        assert callable(self._collector().normalize_rule)

    def test_normalize_rule_returns_dict(self):
        assert isinstance(self._collector().normalize_rule(_raw_rule()), dict)

    def test_normalize_maps_id_to_resource_id(self):
        result = self._collector().normalize_rule(_raw_rule(id="fw-rule-001"))
        assert result["resource_id"] == "fw-rule-001"

    # --- source_ip from source_address list ---
    def test_normalize_source_ip_is_first_element(self):
        raw = _raw_rule(source_address=["10.0.1.11", "10.0.1.12"])
        result = self._collector().normalize_rule(raw)
        assert result["source_ip"] == "10.0.1.11"

    def test_normalize_source_ip_strips_host_mask(self):
        raw = _raw_rule(source_address=["10.0.1.11/32"])
        result = self._collector().normalize_rule(raw)
        assert result["source_ip"] == "10.0.1.11"

    def test_normalize_source_ip_preserves_cidr(self):
        raw = _raw_rule(source_address=["10.83.212.0/24"])
        result = self._collector().normalize_rule(raw)
        assert result["source_ip"] == "10.83.212.0/24"

    def test_normalize_source_addresses_full_list_preserved(self):
        raw = _raw_rule(source_address=["10.0.1.11", "10.0.1.12"])
        result = self._collector().normalize_rule(raw)
        assert result["source_addresses"] == ["10.0.1.11", "10.0.1.12"]

    def test_normalize_source_ip_none_when_empty(self):
        raw = _raw_rule(source_address=[])
        result = self._collector().normalize_rule(raw)
        assert result["source_ip"] is None

    # --- target_ip from destination_address list ---
    def test_normalize_target_ip_is_first_element(self):
        raw = _raw_rule(destination_address=["203.0.113.5"])
        result = self._collector().normalize_rule(raw)
        assert result["target_ip"] == "203.0.113.5"

    def test_normalize_target_ip_strips_host_mask(self):
        raw = _raw_rule(destination_address=["203.0.113.5/32"])
        result = self._collector().normalize_rule(raw)
        assert result["target_ip"] == "203.0.113.5"

    def test_normalize_destination_addresses_full_list_preserved(self):
        raw = _raw_rule(destination_address=["203.0.113.5", "203.0.113.6"])
        result = self._collector().normalize_rule(raw)
        assert result["destination_addresses"] == ["203.0.113.5", "203.0.113.6"]

    def test_normalize_target_ip_none_when_empty(self):
        raw = _raw_rule(destination_address=[])
        result = self._collector().normalize_rule(raw)
        assert result["target_ip"] is None

    # --- protocol from service[0].service_type ---
    def test_normalize_protocol_from_service_type(self):
        raw = _raw_rule(service=[{"service_type": "TCP", "service_value": "443"}])
        result = self._collector().normalize_rule(raw)
        assert result["protocol"] == "TCP"

    def test_normalize_protocol_udp(self):
        raw = _raw_rule(service=[{"service_type": "UDP", "service_value": "53"}])
        result = self._collector().normalize_rule(raw)
        assert result["protocol"] == "UDP"

    def test_normalize_protocol_none_when_no_service(self):
        raw = _raw_rule(service=[])
        result = self._collector().normalize_rule(raw)
        assert result["protocol"] is None

    # --- port from service[0].service_value ---
    def test_normalize_port_from_service_value(self):
        raw = _raw_rule(service=[{"service_type": "TCP", "service_value": "443"}])
        result = self._collector().normalize_rule(raw)
        assert result["port"] == "443"

    def test_normalize_port_range_preserved(self):
        raw = _raw_rule(service=[{"service_type": "TCP", "service_value": "8080-9090"}])
        result = self._collector().normalize_rule(raw)
        assert result["port"] == "8080-9090"

    def test_normalize_port_none_for_all_service_type(self):
        raw = _raw_rule(service=[{"service_type": "ALL"}])
        result = self._collector().normalize_rule(raw)
        assert result["port"] is None

    # --- action mapping ALLOW→permit, DENY→deny ---
    def test_normalize_allow_maps_to_permit(self):
        raw = _raw_rule(action="ALLOW")
        result = self._collector().normalize_rule(raw)
        assert result["action"] == "permit"

    def test_normalize_deny_maps_to_deny(self):
        raw = _raw_rule(action="DENY")
        result = self._collector().normalize_rule(raw)
        assert result["action"] == "deny"

    def test_normalize_unknown_action_preserved(self):
        raw = _raw_rule(action="UNKNOWN")
        result = self._collector().normalize_rule(raw)
        assert result["action"] == "UNKNOWN"

    # --- scalar passthrough fields ---
    def test_normalize_direction_preserved(self):
        result = self._collector().normalize_rule(_raw_rule(direction="OUTBOUND"))
        assert result["direction"] == "OUTBOUND"

    def test_normalize_status_preserved(self):
        result = self._collector().normalize_rule(_raw_rule(status="DISABLE"))
        assert result["status"] == "DISABLE"

    def test_normalize_state_preserved(self):
        result = self._collector().normalize_rule(_raw_rule(state="ACTIVE"))
        assert result["state"] == "ACTIVE"

    def test_normalize_description_preserved(self):
        result = self._collector().normalize_rule(_raw_rule(description="my rule"))
        assert result["description"] == "my rule"

    def test_normalize_sequence_preserved(self):
        result = self._collector().normalize_rule(_raw_rule(sequence=42))
        assert result["sequence"] == 42

    def test_normalize_firewall_id_preserved(self):
        result = self._collector().normalize_rule(_raw_rule(firewall_id="fw-parent-001"))
        assert result["firewall_id"] == "fw-parent-001"

    # --- unknown fields go to _raw ---
    def test_normalize_unknown_fields_in_raw(self):
        raw = _raw_rule()
        raw["vendor_rule_id"] = "72"
        raw["some_future_field"] = "future-value"
        result = self._collector().normalize_rule(raw)
        assert "_raw" in result
        assert result["_raw"].get("some_future_field") == "future-value"

    def test_normalize_known_fields_not_in_raw(self):
        raw = _raw_rule()
        result = self._collector().normalize_rule(raw)
        # Fields like source_interface appear in the raw but are not mapped to top level
        if "_raw" in result:
            assert "source_interface" in result["_raw"] or result.get("source_interface") is None

    # --- missing fields are None not KeyError ---
    def test_normalize_missing_source_address_safe(self):
        raw = {"id": "fw-001", "action": "ALLOW"}
        result = self._collector().normalize_rule(raw)
        assert result["source_ip"] is None

    def test_normalize_missing_service_safe(self):
        raw = {"id": "fw-001", "action": "ALLOW"}
        result = self._collector().normalize_rule(raw)
        assert result["protocol"] is None
        assert result["port"] is None

    # --- batch normalization ---
    def test_normalize_list_resource_ids(self):
        collector = self._collector()
        raws = [_raw_rule(id=f"fw-{i}") for i in range(3)]
        results = [collector.normalize_rule(r) for r in raws]
        assert [r["resource_id"] for r in results] == ["fw-0", "fw-1", "fw-2"]


# ---------------------------------------------------------------------------
# _build_auth_headers — HMAC-SHA256 signed request headers
# Confirmed header names from docs.e.samsungsdscloud.com operation examples
# ---------------------------------------------------------------------------

class TestBuildAuthHeaders:
    def _collector(self):
        return _make(access_key="mykey", secret_key="mysecret")

    def test_build_auth_headers_exists(self):
        assert callable(self._collector()._build_auth_headers)

    def test_returns_dict(self):
        headers = self._collector()._build_auth_headers("GET", "/v1/firewalls")
        assert isinstance(headers, dict)

    def test_contains_scp_accesskey(self):
        headers = self._collector()._build_auth_headers("GET", "/v1/firewalls")
        assert "Scp-Accesskey" in headers
        assert headers["Scp-Accesskey"] == "mykey"

    def test_contains_scp_signature(self):
        headers = self._collector()._build_auth_headers("GET", "/v1/firewalls")
        assert "Scp-Signature" in headers
        assert len(headers["Scp-Signature"]) > 0

    def test_contains_scp_timestamp(self):
        headers = self._collector()._build_auth_headers("GET", "/v1/firewalls")
        assert "Scp-Timestamp" in headers
        assert headers["Scp-Timestamp"].isdigit()

    def test_contains_scp_client_type(self):
        headers = self._collector()._build_auth_headers("GET", "/v1/firewalls")
        assert headers.get("Scp-ClientType") == "Openapi"

    def test_contains_accept_language(self):
        headers = self._collector()._build_auth_headers("GET", "/v1/firewalls")
        assert "Accept-Language" in headers

    def test_contains_scp_api_version(self):
        headers = self._collector()._build_auth_headers("GET", "/v1/firewalls")
        assert headers.get("Scp-Api-Version") == "firewall 1.0"

    def test_signature_is_base64(self):
        import base64
        headers = self._collector()._build_auth_headers("GET", "/v1/firewalls")
        # Should not raise
        base64.b64decode(headers["Scp-Signature"])

    def test_different_methods_produce_different_signatures(self):
        c = self._collector()
        h_get  = c._build_auth_headers("GET",  "/v1/firewalls/rules")
        h_post = c._build_auth_headers("POST", "/v1/firewalls/rules")
        assert h_get["Scp-Signature"] != h_post["Scp-Signature"]

    def test_different_paths_produce_different_signatures(self):
        c = self._collector()
        h1 = c._build_auth_headers("GET", "/v1/firewalls")
        h2 = c._build_auth_headers("GET", "/v1/firewalls/rules?firewall_id=abc")
        assert h1["Scp-Signature"] != h2["Scp-Signature"]


# ---------------------------------------------------------------------------
# _api_get — HTTP GET with HMAC auth; monkeypatched urlopen
# ---------------------------------------------------------------------------

class TestApiGet:
    def _collector(self):
        return _make()

    def test_api_get_exists(self):
        assert callable(self._collector()._api_get)

    def test_api_get_returns_dict(self, monkeypatch):
        import json
        import io

        class _FakeResp:
            def read(self): return json.dumps({"firewalls": [], "count": 0}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): pass

        import urllib.request
        monkeypatch.setattr(urllib.request, "urlopen", lambda req: _FakeResp())
        result = self._collector()._api_get("/v1/firewalls")
        assert isinstance(result, dict)
        assert "firewalls" in result

    def test_api_get_with_params_builds_query_string(self, monkeypatch):
        import json, urllib.request

        captured = {}

        class _FakeResp:
            def read(self): return json.dumps({}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): pass

        def fake_urlopen(req):
            captured["url"] = req.full_url
            return _FakeResp()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        self._collector()._api_get("/v1/firewalls/rules", {"firewall_id": "fw-001", "fetch_all": "true"})
        assert "firewall_id=fw-001" in captured["url"]
        assert "fetch_all=true" in captured["url"]

    def test_api_get_array_param_repeats_key(self, monkeypatch):
        import json, urllib.request

        captured = {}

        class _FakeResp:
            def read(self): return json.dumps({}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): pass

        def fake_urlopen(req):
            captured["url"] = req.full_url
            return _FakeResp()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        self._collector()._api_get("/v1/firewalls", {"product_type": ["TGW_IGW", "TGW_GGW"]})
        assert "product_type=TGW_IGW" in captured["url"]
        assert "product_type=TGW_GGW" in captured["url"]

    def test_api_get_raises_collector_error_on_http_error(self, monkeypatch):
        import urllib.request, urllib.error

        def fake_urlopen(req):
            raise urllib.error.HTTPError(
                url=req.full_url, code=403, msg="Forbidden", hdrs={}, fp=None
            )

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(CollectorError):
            self._collector()._api_get("/v1/firewalls")

    def test_api_get_raises_collector_error_on_url_error(self, monkeypatch):
        import urllib.request, urllib.error

        def fake_urlopen(req):
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(CollectorError):
            self._collector()._api_get("/v1/firewalls")


# ---------------------------------------------------------------------------
# _fetch_raw_rules_via_api — two-phase: list firewalls → list rules per firewall
# ---------------------------------------------------------------------------

class TestFetchRawRulesViaApi:
    def _collector(self):
        return _make()

    def _fw_list_response(self, firewall_ids):
        return {
            "count": len(firewall_ids),
            "firewalls": [{"id": fid, "name": f"FW_{fid}"} for fid in firewall_ids],
            "page": 0, "size": 10000,
        }

    def _rule_list_response(self, rule_ids):
        return {
            "count": len(rule_ids),
            "firewall_rules": [_raw_rule(id=rid) for rid in rule_ids],
            "page": 0, "size": 20,
        }

    def test_returns_list(self, monkeypatch):
        collector = self._collector()
        monkeypatch.setattr(collector, "_api_get",
                            lambda path, params=None: self._fw_list_response([]))
        result = collector._fetch_raw_rules_via_api()
        assert isinstance(result, list)

    def test_empty_firewalls_returns_empty_rules(self, monkeypatch):
        collector = self._collector()
        monkeypatch.setattr(collector, "_api_get",
                            lambda path, params=None: self._fw_list_response([]))
        assert collector._fetch_raw_rules_via_api() == []

    def test_single_firewall_returns_its_rules(self, monkeypatch):
        collector = self._collector()

        def fake_api_get(path, params=None):
            if path == "/v1/firewalls":
                return self._fw_list_response(["fw-001"])
            return self._rule_list_response(["rule-A", "rule-B"])

        monkeypatch.setattr(collector, "_api_get", fake_api_get)
        result = collector._fetch_raw_rules_via_api()
        assert len(result) == 2
        assert result[0]["id"] == "rule-A"

    def test_multiple_firewalls_flattens_rules(self, monkeypatch):
        collector = self._collector()
        call_log = []

        def fake_api_get(path, params=None):
            call_log.append((path, params))
            if path == "/v1/firewalls":
                return self._fw_list_response(["fw-001", "fw-002"])
            fw_id = params.get("firewall_id") if params else None
            if fw_id == "fw-001":
                return self._rule_list_response(["rule-A"])
            return self._rule_list_response(["rule-B", "rule-C"])

        monkeypatch.setattr(collector, "_api_get", fake_api_get)
        result = collector._fetch_raw_rules_via_api()
        assert len(result) == 3

    def test_calls_list_firewalls_first(self, monkeypatch):
        collector = self._collector()
        call_order = []

        def fake_api_get(path, params=None):
            call_order.append(path)
            if path == "/v1/firewalls":
                return self._fw_list_response(["fw-001"])
            return self._rule_list_response([])

        monkeypatch.setattr(collector, "_api_get", fake_api_get)
        collector._fetch_raw_rules_via_api()
        assert call_order[0] == "/v1/firewalls"

    def test_calls_list_rules_with_fetch_all(self, monkeypatch):
        collector = self._collector()
        rule_params = {}

        def fake_api_get(path, params=None):
            if path == "/v1/firewalls":
                return self._fw_list_response(["fw-001"])
            rule_params.update(params or {})
            return self._rule_list_response([])

        monkeypatch.setattr(collector, "_api_get", fake_api_get)
        collector._fetch_raw_rules_via_api()
        assert rule_params.get("fetch_all") == "true"
        assert rule_params.get("firewall_id") == "fw-001"

    def test_list_firewalls_uses_tgw_product_type_filter(self, monkeypatch):
        collector = self._collector()
        fw_params = {}

        def fake_api_get(path, params=None):
            if path == "/v1/firewalls":
                fw_params.update(params or {})
                return self._fw_list_response([])
            return self._rule_list_response([])

        monkeypatch.setattr(collector, "_api_get", fake_api_get)
        collector._fetch_raw_rules_via_api()
        pt = fw_params.get("product_type", [])
        assert isinstance(pt, list)
        assert any("TGW" in t for t in pt)

    def test_firewall_without_rules_contributes_empty(self, monkeypatch):
        collector = self._collector()

        def fake_api_get(path, params=None):
            if path == "/v1/firewalls":
                return self._fw_list_response(["fw-empty"])
            return self._rule_list_response([])

        monkeypatch.setattr(collector, "_api_get", fake_api_get)
        assert collector._fetch_raw_rules_via_api() == []
