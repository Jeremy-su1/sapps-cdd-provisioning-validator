"""Tests for src/classification/endpoint_resolver.py — 5-way endpoint classification."""
import ipaddress
import pytest
from src.classification.endpoint_resolver import resolve_endpoint, is_cidr_notation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _nets(*cidrs):
    return [ipaddress.ip_network(c, strict=False) for c in cidrs]


# Customer application subnets (10.83.x.x) — do NOT include platform subnets here.
_SUBNETS = _nets("10.83.212.0/24", "10.83.213.0/25", "10.83.214.0/24")
_VM_HOSTS = {"vhapp01", "vhdb01", "phapp01"}
# Platform (PSM/backup) subnets — 192.167.x.x is non-RFC-1918 public-but-internal range.
_PLATFORM = _nets("192.167.14.128/25", "192.167.15.0/26")


# ---------------------------------------------------------------------------
# is_cidr_notation
# ---------------------------------------------------------------------------

class TestIsCidrNotation:
    def test_cidr_with_slash_is_cidr(self):
        assert is_cidr_notation("10.83.212.0/24") is True

    def test_host_ip_is_not_cidr(self):
        assert is_cidr_notation("10.83.212.5") is False

    def test_none_is_not_cidr(self):
        assert is_cidr_notation(None) is False

    def test_placeholder_is_not_cidr(self):
        assert is_cidr_notation("0") is False

    def test_empty_is_not_cidr(self):
        assert is_cidr_notation("") is False

    def test_public_cidr_is_cidr(self):
        assert is_cidr_notation("203.0.113.0/24") is True

    def test_host_prefix_32_is_cidr(self):
        assert is_cidr_notation("10.0.0.1/32") is True


# ---------------------------------------------------------------------------
# resolve_endpoint — internal
# ---------------------------------------------------------------------------

class TestResolveInternal:
    def test_hostname_in_vm_set_is_internal(self):
        r = resolve_endpoint("10.99.99.1", "vhapp01", _VM_HOSTS, _SUBNETS)
        assert r == "internal"

    def test_ip_in_our_subnet_is_internal(self):
        r = resolve_endpoint("10.83.212.5", None, _VM_HOSTS, _SUBNETS)
        assert r == "internal"

    def test_ip_in_second_subnet_is_internal(self):
        r = resolve_endpoint("10.83.213.10", None, _VM_HOSTS, _SUBNETS)
        assert r == "internal"

    def test_cidr_overlapping_our_subnet_is_internal(self):
        r = resolve_endpoint("10.83.212.0/24", None, _VM_HOSTS, _SUBNETS)
        assert r == "internal"

    def test_cidr_subset_of_our_subnet_is_internal(self):
        # /26 is a subset of our /24
        r = resolve_endpoint("10.83.212.0/26", None, _VM_HOSTS, _SUBNETS)
        assert r == "internal"


# ---------------------------------------------------------------------------
# resolve_endpoint — customer_external
# ---------------------------------------------------------------------------

class TestResolveCustomerExternal:
    def test_private_ip_not_in_our_subnets_is_customer_external(self):
        r = resolve_endpoint("10.0.5.100", None, _VM_HOSTS, _SUBNETS)
        assert r == "customer_external"

    def test_private_cidr_not_overlapping_our_subnets_is_customer_external(self):
        r = resolve_endpoint("10.100.0.0/16", None, _VM_HOSTS, _SUBNETS)
        assert r == "customer_external"

    def test_172_private_not_in_subnets_is_customer_external(self):
        r = resolve_endpoint("172.16.10.0/24", None, _VM_HOSTS, _SUBNETS)
        assert r == "customer_external"

    def test_192_168_not_in_subnets_is_customer_external(self):
        r = resolve_endpoint("192.168.1.0/24", None, _VM_HOSTS, _SUBNETS)
        assert r == "customer_external"

    def test_landscape_label_hostname_is_customer_external(self):
        r = resolve_endpoint(None, "PRD", _VM_HOSTS, _SUBNETS)
        assert r == "customer_external"

    def test_non_prd_label_is_customer_external(self):
        r = resolve_endpoint("10.83.213.0/25", "Non-PRD", _VM_HOSTS, _SUBNETS)
        # hostname "Non-PRD" is landscape label → customer_external even though IP is internal
        # hostname takes priority
        assert r == "customer_external"

    def test_dr_label_is_customer_external(self):
        r = resolve_endpoint(None, "DR", _VM_HOSTS, _SUBNETS)
        assert r == "customer_external"

    def test_dev_label_is_customer_external(self):
        r = resolve_endpoint(None, "DEV", _VM_HOSTS, _SUBNETS)
        assert r == "customer_external"


# ---------------------------------------------------------------------------
# resolve_endpoint — managed_external
# ---------------------------------------------------------------------------

class TestResolveManagedExternal:
    def test_public_host_ip_is_managed_external(self):
        r = resolve_endpoint("203.0.113.5", None, _VM_HOSTS, _SUBNETS)
        assert r == "managed_external"

    def test_public_cidr_is_managed_external(self):
        r = resolve_endpoint("16.3.17.0/24", None, _VM_HOSTS, _SUBNETS)
        assert r == "managed_external"

    def test_another_public_cidr_is_managed_external(self):
        r = resolve_endpoint("166.79.1.0/24", None, _VM_HOSTS, _SUBNETS)
        assert r == "managed_external"

    def test_public_ip_with_null_hostname_is_managed_external(self):
        r = resolve_endpoint("70.222.32.43", None, _VM_HOSTS, _SUBNETS)
        assert r == "managed_external"


# ---------------------------------------------------------------------------
# resolve_endpoint — shared_platform
# ---------------------------------------------------------------------------

class TestResolveSharedPlatform:
    def test_ip_in_platform_networks_is_shared_platform(self):
        r = resolve_endpoint("192.167.14.200", None, _VM_HOSTS, _SUBNETS,
                             platform_networks=_PLATFORM)
        assert r == "shared_platform"

    def test_cidr_overlapping_platform_is_shared_platform(self):
        r = resolve_endpoint("192.167.14.128/25", None, _VM_HOSTS, _SUBNETS,
                             platform_networks=_PLATFORM)
        assert r == "shared_platform"

    def test_no_platform_networks_falls_back_to_managed_external(self):
        # 192.167.14.200 is NOT RFC1918 (192.168.0.0/16 is RFC1918, 192.167.x.x is not).
        # Without platform_networks it is treated as managed_external.
        r = resolve_endpoint("192.167.14.200", None, _VM_HOSTS,
                             _nets("10.83.212.0/24"))
        assert r == "managed_external"


# ---------------------------------------------------------------------------
# resolve_endpoint — unknown
# ---------------------------------------------------------------------------

class TestResolveUnknown:
    def test_placeholder_zero_is_unknown(self):
        r = resolve_endpoint("0", None, _VM_HOSTS, _SUBNETS)
        assert r == "unknown"

    def test_placeholder_dash_is_unknown(self):
        r = resolve_endpoint("-", None, _VM_HOSTS, _SUBNETS)
        assert r == "unknown"

    def test_none_ip_none_hostname_is_unknown(self):
        r = resolve_endpoint(None, None, _VM_HOSTS, _SUBNETS)
        assert r == "unknown"

    def test_empty_string_is_unknown(self):
        r = resolve_endpoint("", None, _VM_HOSTS, _SUBNETS)
        assert r == "unknown"

    def test_integer_zero_is_unknown(self):
        r = resolve_endpoint(0, None, _VM_HOSTS, _SUBNETS)
        assert r == "unknown"

    def test_non_ip_string_is_unknown(self):
        r = resolve_endpoint("not-an-ip", None, _VM_HOSTS, _SUBNETS)
        assert r == "unknown"


# ---------------------------------------------------------------------------
# resolve_endpoint — priority: hostname before IP
# ---------------------------------------------------------------------------

class TestResolutionPriority:
    def test_vm_hostname_beats_external_ip(self):
        # IP is external but hostname is in our VM set → internal
        r = resolve_endpoint("203.0.113.5", "vhdb01", _VM_HOSTS, _SUBNETS)
        assert r == "internal"

    def test_landscape_label_beats_internal_ip(self):
        # IP is in our subnet but hostname is "PRD" landscape label → customer_external
        r = resolve_endpoint("10.83.212.5", "PRD", _VM_HOSTS, _SUBNETS)
        assert r == "customer_external"

    def test_empty_hostname_falls_through_to_ip(self):
        r = resolve_endpoint("10.83.212.5", "", _VM_HOSTS, _SUBNETS)
        assert r == "internal"

    def test_none_hostname_falls_through_to_ip(self):
        r = resolve_endpoint("10.83.212.5", None, _VM_HOSTS, _SUBNETS)
        assert r == "internal"
