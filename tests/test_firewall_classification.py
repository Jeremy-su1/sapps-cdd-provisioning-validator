"""Tests for src/classification/firewall_rules.py."""
import ipaddress
import pytest
from src.classification.firewall_rules import (
    classify_endpoint,
    classify_candidates,
    ClassificationResult,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

_VM_HOSTNAMES = {"vhinternal01", "phinternal01", "vhinternal02", "phinternal02"}
_INTERNAL_NET = [ipaddress.ip_network("10.0.0.0/24")]


def _cand(**overrides):
    """Build a minimal firewall rule candidate."""
    base = {
        "source_system":    "SRC",
        "source_category":  "APP",
        "source_hostname":  None,
        "source_ip":        None,
        "source_landscape": None,
        "target_system":    "TGT",
        "target_category":  "DB",
        "target_hostname":  None,
        "target_ip":        None,
        "port":             "443",
        "port_expression":  False,
        "protocol":         "TCP",
        "expiration":       "Permanent",
        "purpose":          "test purpose",
        "cus_fw":           True,
        "cus_sg":           True,
        "psm_fw":           False,
        "psm_sg":           False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# classify_endpoint
# ---------------------------------------------------------------------------

class TestClassifyEndpoint:
    def test_hostname_in_vm_set_is_internal(self):
        assert classify_endpoint("1.2.3.4", "vhinternal01", _VM_HOSTNAMES, _INTERNAL_NET) == "internal"

    def test_ip_in_subnet_is_internal(self):
        assert classify_endpoint("10.0.0.50", None, set(), _INTERNAL_NET) == "internal"

    def test_valid_ip_outside_subnet_is_external(self):
        assert classify_endpoint("192.168.1.1", None, set(), _INTERNAL_NET) == "external"

    def test_external_hostname_outside_vm_set_uses_ip(self):
        assert classify_endpoint("192.168.1.1", "phpsmhost01", set(), _INTERNAL_NET) == "external"

    def test_none_ip_and_none_hostname_is_unknown(self):
        assert classify_endpoint(None, None, _VM_HOSTNAMES, _INTERNAL_NET) == "unknown"

    def test_placeholder_ip_zero_and_no_hostname_is_unknown(self):
        assert classify_endpoint("0", None, _VM_HOSTNAMES, _INTERNAL_NET) == "unknown"

    def test_placeholder_ip_dash_and_no_hostname_is_unknown(self):
        assert classify_endpoint("-", None, _VM_HOSTNAMES, _INTERNAL_NET) == "unknown"

    def test_none_ip_with_known_hostname_is_internal(self):
        assert classify_endpoint(None, "vhinternal01", _VM_HOSTNAMES, _INTERNAL_NET) == "internal"

    def test_none_ip_with_unknown_hostname_is_unknown(self):
        assert classify_endpoint(None, "vhunknown99", _VM_HOSTNAMES, _INTERNAL_NET) == "unknown"

    def test_internal_ip_overrides_external_hostname(self):
        # If IP is internal, endpoint is internal regardless of hostname
        assert classify_endpoint("10.0.0.5", "vhunknown99", _VM_HOSTNAMES, _INTERNAL_NET) == "internal"


# ---------------------------------------------------------------------------
# ClassificationResult structure
# ---------------------------------------------------------------------------

class TestClassificationResult:
    def test_empty_input_returns_empty_result(self):
        r = classify_candidates([], _VM_HOSTNAMES, _INTERNAL_NET)
        assert r.tgw_candidates == []
        assert r.dfw_candidates == []
        assert r.reference_only == []
        assert r.warnings == []

    def test_result_is_classification_result_instance(self):
        r = classify_candidates([], _VM_HOSTNAMES, _INTERNAL_NET)
        assert isinstance(r, ClassificationResult)

    def test_result_has_warnings_list(self):
        r = classify_candidates([], _VM_HOSTNAMES, _INTERNAL_NET)
        assert isinstance(r.warnings, list)


# ---------------------------------------------------------------------------
# PSM-flagged rules → reference_only (always)
# ---------------------------------------------------------------------------

class TestPsmFlaggedRules:
    def test_psm_fw_true_goes_to_reference_only(self):
        c = _cand(psm_fw=True, psm_sg=False, cus_fw=False, cus_sg=False)
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert len(r.reference_only) == 1
        assert r.reference_only[0]["reason"] == "psm_managed"

    def test_psm_sg_true_goes_to_reference_only(self):
        c = _cand(psm_fw=False, psm_sg=True, cus_fw=False, cus_sg=False)
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert len(r.reference_only) == 1

    def test_psm_co_managed_also_added_to_tgw(self):
        # cus_fw=True + psm_fw=True + external source → reference_only AND tgw
        c = _cand(
            cus_fw=True, cus_sg=True, psm_fw=True, psm_sg=True,
            source_ip="192.168.1.1",   # external
            target_ip="10.0.0.50",     # internal
        )
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert len(r.reference_only) >= 1
        assert len(r.tgw_candidates) == 1

    def test_psm_only_does_not_go_to_tgw(self):
        c = _cand(psm_fw=True, psm_sg=True, cus_fw=False, cus_sg=False)
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert r.tgw_candidates == []
        assert r.dfw_candidates == []


# ---------------------------------------------------------------------------
# Internal → internal → NSX-T DFW
# ---------------------------------------------------------------------------

class TestInternalToInternalDfw:
    def test_both_internal_ips_goes_to_dfw(self):
        c = _cand(
            psm_fw=False, psm_sg=False,
            source_ip="10.0.0.10",
            target_ip="10.0.0.20",
        )
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert len(r.dfw_candidates) == 1
        assert r.tgw_candidates == []
        assert r.reference_only == []

    def test_internal_hostnames_goes_to_dfw(self):
        c = _cand(
            psm_fw=False, psm_sg=False,
            source_hostname="vhinternal01",
            target_hostname="vhinternal02",
        )
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert len(r.dfw_candidates) == 1

    def test_dfw_entry_has_origin_idx(self):
        c = _cand(source_ip="10.0.0.10", target_ip="10.0.0.20")
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert "origin_idx" in r.dfw_candidates[0]
        assert r.dfw_candidates[0]["origin_idx"] == 0


# ---------------------------------------------------------------------------
# External endpoint + cus_fw → TGW
# ---------------------------------------------------------------------------

class TestExternalToInternalTgw:
    def test_external_source_cus_fw_goes_to_tgw(self):
        c = _cand(
            cus_fw=True, psm_fw=False,
            source_ip="1.2.3.4",      # external
            target_ip="10.0.0.50",    # internal
        )
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert len(r.tgw_candidates) == 1

    def test_external_target_cus_fw_goes_to_tgw(self):
        c = _cand(
            cus_fw=True, psm_fw=False,
            source_ip="10.0.0.10",    # internal
            target_ip="1.2.3.4",      # external
        )
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert len(r.tgw_candidates) == 1

    def test_tgw_entry_requires_manual_review_false_for_known_endpoints(self):
        c = _cand(
            cus_fw=True,
            source_ip="1.2.3.4",
            target_ip="10.0.0.50",
        )
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert r.tgw_candidates[0]["requires_manual_review"] is False

    def test_tgw_entry_has_origin_idx(self):
        candidates = [
            _cand(source_ip="10.0.0.10", target_ip="10.0.0.20"),  # dfw
            _cand(source_ip="1.2.3.4", target_ip="10.0.0.50"),     # tgw at idx=1
        ]
        r = classify_candidates(candidates, _VM_HOSTNAMES, _INTERNAL_NET)
        assert r.tgw_candidates[0]["origin_idx"] == 1


# ---------------------------------------------------------------------------
# Unknown endpoints with cus_sg → TGW with review flag
# ---------------------------------------------------------------------------

class TestUnknownEndpointReview:
    def test_unknown_source_cus_sg_goes_to_tgw_with_review(self):
        c = _cand(
            cus_fw=False, cus_sg=True, psm_fw=False, psm_sg=False,
            source_ip=None, source_hostname=None,
            target_ip="10.0.0.50",
        )
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert len(r.tgw_candidates) == 1
        assert r.tgw_candidates[0]["requires_manual_review"] is True

    def test_unknown_both_cus_sg_goes_to_tgw_with_review(self):
        c = _cand(
            cus_fw=True, cus_sg=True, psm_fw=False, psm_sg=False,
            source_ip=None, source_hostname=None,
            target_ip=None, target_hostname=None,
        )
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert len(r.tgw_candidates) == 1
        assert r.tgw_candidates[0]["requires_manual_review"] is True


# ---------------------------------------------------------------------------
# Unclassifiable → reference_only
# ---------------------------------------------------------------------------

class TestUnclassifiable:
    def test_no_flags_set_goes_to_reference(self):
        c = _cand(cus_fw=False, cus_sg=False, psm_fw=False, psm_sg=False)
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert len(r.reference_only) == 1
        assert r.reference_only[0]["reason"] == "unclassifiable"

    def test_unclassifiable_not_in_tgw_or_dfw(self):
        c = _cand(cus_fw=False, cus_sg=False, psm_fw=False, psm_sg=False)
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        assert r.tgw_candidates == []
        assert r.dfw_candidates == []


# ---------------------------------------------------------------------------
# TGW candidate field shape
# ---------------------------------------------------------------------------

class TestTgwCandidateShape:
    def setup_method(self):
        c = _cand(
            cus_fw=True,
            source_system="ERP", source_ip="1.2.3.4",
            target_system="HDB", target_ip="10.0.0.50",
            port="443", port_expression=False,
            protocol="TCP", expiration="Permanent",
            purpose="HANA access",
        )
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        self.entry = r.tgw_candidates[0]

    def test_has_origin_idx(self):
        assert "origin_idx" in self.entry

    def test_has_source_system(self):
        assert self.entry["source_system"] == "ERP"

    def test_has_target_system(self):
        assert self.entry["target_system"] == "HDB"

    def test_has_port(self):
        assert self.entry["port"] == "443"

    def test_has_port_expression(self):
        assert self.entry["port_expression"] is False

    def test_has_protocol(self):
        assert self.entry["protocol"] == "TCP"

    def test_has_purpose(self):
        assert self.entry["purpose"] == "HANA access"

    def test_has_expiration(self):
        assert self.entry["expiration"] == "Permanent"

    def test_has_requires_manual_review(self):
        assert "requires_manual_review" in self.entry


# ---------------------------------------------------------------------------
# DFW candidate field shape
# ---------------------------------------------------------------------------

class TestDfwCandidateShape:
    def setup_method(self):
        c = _cand(
            psm_fw=False, psm_sg=False,
            source_ip="10.0.0.10", source_hostname="vhinternal01",
            target_ip="10.0.0.20", target_hostname="vhinternal02",
            port="3200-3299", port_expression=True,
            protocol="TCP", purpose="HANA SQL",
        )
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        self.entry = r.dfw_candidates[0]

    def test_has_origin_idx(self):
        assert "origin_idx" in self.entry

    def test_has_source_ip(self):
        assert self.entry["source_ip"] == "10.0.0.10"

    def test_has_target_ip(self):
        assert self.entry["target_ip"] == "10.0.0.20"

    def test_has_port(self):
        assert self.entry["port"] == "3200-3299"

    def test_has_applied_to(self):
        assert self.entry["applied_to"] == "both"


# ---------------------------------------------------------------------------
# Reference-only field shape
# ---------------------------------------------------------------------------

class TestReferenceOnlyShape:
    def setup_method(self):
        c = _cand(psm_fw=True, cus_fw=False, cus_sg=False,
                  source_system="EXT", target_system="INT", purpose="PSM managed")
        r = classify_candidates([c], _VM_HOSTNAMES, _INTERNAL_NET)
        self.entry = r.reference_only[0]

    def test_has_origin_idx(self):
        assert "origin_idx" in self.entry

    def test_has_reason(self):
        assert "reason" in self.entry

    def test_has_source_system(self):
        assert self.entry["source_system"] == "EXT"

    def test_has_target_system(self):
        assert self.entry["target_system"] == "INT"

    def test_has_purpose(self):
        assert self.entry["purpose"] == "PSM managed"


# ---------------------------------------------------------------------------
# Multiple candidates — origin_idx integrity
# ---------------------------------------------------------------------------

class TestOriginIdxIntegrity:
    def test_origin_idx_matches_list_position(self):
        candidates = [
            _cand(source_ip="10.0.0.10", target_ip="10.0.0.20"),  # idx=0 → dfw
            _cand(source_ip="1.2.3.4", target_ip="10.0.0.50"),     # idx=1 → tgw
            _cand(cus_fw=False, cus_sg=False),                      # idx=2 → reference
        ]
        r = classify_candidates(candidates, _VM_HOSTNAMES, _INTERNAL_NET)
        assert r.dfw_candidates[0]["origin_idx"] == 0
        assert r.tgw_candidates[0]["origin_idx"] == 1


# ---------------------------------------------------------------------------
# Enriched TGW entries — endpoint classes and CIDR flags
# ---------------------------------------------------------------------------

class TestEnrichedTgwEntries:
    def _tgw_from_candidate(self, **kwargs):
        cand = _cand(cus_fw=True, **kwargs)
        r = classify_candidates([cand], _VM_HOSTNAMES, _INTERNAL_NET)
        assert r.tgw_candidates, "no TGW candidate produced"
        return r.tgw_candidates[0]

    def test_tgw_entry_has_src_endpoint_class(self):
        e = self._tgw_from_candidate(source_ip="1.2.3.4", target_ip="10.0.0.50")
        assert "src_endpoint_class" in e

    def test_tgw_entry_has_tgt_endpoint_class(self):
        e = self._tgw_from_candidate(source_ip="1.2.3.4", target_ip="10.0.0.50")
        assert "tgt_endpoint_class" in e

    def test_tgw_entry_has_src_is_cidr(self):
        e = self._tgw_from_candidate(source_ip="1.2.3.4", target_ip="10.0.0.50")
        assert "src_is_cidr" in e

    def test_tgw_entry_has_tgt_is_cidr(self):
        e = self._tgw_from_candidate(source_ip="1.2.3.4", target_ip="10.0.0.50")
        assert "tgt_is_cidr" in e

    def test_host_ip_not_flagged_as_cidr(self):
        e = self._tgw_from_candidate(source_ip="1.2.3.4", target_ip="10.0.0.50")
        assert e["src_is_cidr"] is False

    def test_cidr_source_flagged_as_cidr(self):
        e = self._tgw_from_candidate(source_ip="1.2.3.0/24", target_ip="10.0.0.50")
        assert e["src_is_cidr"] is True

    def test_cidr_target_flagged_as_cidr(self):
        e = self._tgw_from_candidate(source_ip="1.2.3.4", target_ip="10.0.0.0/24")
        assert e["tgt_is_cidr"] is True

    def test_internal_subnet_cidr_classified_as_internal(self):
        # Source is CIDR within our subnet → internal
        e = self._tgw_from_candidate(source_ip="10.0.0.0/24", target_ip="1.2.3.4")
        assert e["src_endpoint_class"] == "internal"

    def test_external_host_classified_as_managed_external(self):
        e = self._tgw_from_candidate(source_ip="1.2.3.4", target_ip="10.0.0.50")
        assert e["src_endpoint_class"] == "managed_external"

    def test_internal_host_ip_classified_as_internal(self):
        e = self._tgw_from_candidate(source_ip="10.0.0.50", target_ip="1.2.3.4")
        assert e["src_endpoint_class"] == "internal"
