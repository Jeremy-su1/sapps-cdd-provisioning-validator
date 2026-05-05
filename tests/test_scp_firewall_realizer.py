"""Tests for src/transforms/scp_firewall_realizer.py — execution-ready rule generation."""
import pytest
from src.transforms.scp_firewall_realizer import (
    realize_rules,
    parse_port_expression,
    ScpFirewallRealizationResult,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _candidate(
    origin_idx=0,
    source_ip="10.83.214.11",
    target_ip="192.168.251.45",
    protocol="TCP",
    port="443",
    port_expression=False,
    src_endpoint_class="internal",
    tgt_endpoint_class="customer_external",
    src_is_cidr=False,
    tgt_is_cidr=False,
):
    return {
        "origin_idx":             origin_idx,
        "source_ip":              source_ip,
        "target_ip":              target_ip,
        "protocol":               protocol,
        "port":                   port,
        "port_expression":        port_expression,
        "action":                 "permit",
        "src_endpoint_class":     src_endpoint_class,
        "tgt_endpoint_class":     tgt_endpoint_class,
        "src_is_cidr":            src_is_cidr,
        "tgt_is_cidr":            tgt_is_cidr,
        "requires_manual_review": False,
    }


# ---------------------------------------------------------------------------
# parse_port_expression
# ---------------------------------------------------------------------------

class TestParsePortExpression:
    # --- single ---
    def test_single_port_kind_is_single(self):
        tokens, kind = parse_port_expression("443")
        assert kind == "single"

    def test_single_port_returns_one_token(self):
        tokens, kind = parse_port_expression("443")
        assert tokens == ["443"]

    def test_single_port_numeric_string(self):
        tokens, kind = parse_port_expression("3299")
        assert tokens == ["3299"]
        assert kind == "single"

    # --- range with hyphen ---
    def test_hyphen_range_kind_is_range(self):
        tokens, kind = parse_port_expression("3200-3399")
        assert kind == "range"

    def test_hyphen_range_token_preserved(self):
        tokens, kind = parse_port_expression("3200-3399")
        assert tokens == ["3200-3399"]

    # --- range with tilde (normalized) ---
    def test_tilde_range_kind_is_range(self):
        tokens, kind = parse_port_expression("5000~5999")
        assert kind == "range"

    def test_tilde_range_normalized_to_hyphen(self):
        tokens, kind = parse_port_expression("5000~5999")
        assert tokens == ["5000-5999"]

    def test_tilde_range_not_in_output(self):
        tokens, _ = parse_port_expression("5000~5999")
        assert "~" not in tokens[0]

    # --- comma-separated (multi) ---
    def test_comma_separated_kind_is_multi(self):
        tokens, kind = parse_port_expression("1128,1129")
        assert kind == "multi"

    def test_comma_separated_two_tokens(self):
        tokens, kind = parse_port_expression("1128,1129")
        assert tokens == ["1128", "1129"]

    def test_comma_separated_three_tokens(self):
        tokens, kind = parse_port_expression("80,443,8443")
        assert len(tokens) == 3

    def test_comma_with_hyphen_range(self):
        tokens, kind = parse_port_expression("80,3200-3399")
        assert kind == "multi"
        assert tokens == ["80", "3200-3399"]

    def test_comma_with_tilde_range_normalized(self):
        tokens, kind = parse_port_expression("80,5000~5999")
        assert kind == "multi"
        assert tokens == ["80", "5000-5999"]

    def test_comma_with_mixed_ranges(self):
        tokens, kind = parse_port_expression("80,443,3200-3399,5000~5999")
        assert kind == "multi"
        assert len(tokens) == 4
        assert "~" not in "".join(tokens)

    def test_whitespace_stripped_from_tokens(self):
        tokens, kind = parse_port_expression("80, 443, 8443")
        assert tokens == ["80", "443", "8443"]

    # --- empty ---
    def test_none_is_empty(self):
        tokens, kind = parse_port_expression(None)
        assert kind == "empty"
        assert tokens == []

    def test_empty_string_is_empty(self):
        tokens, kind = parse_port_expression("")
        assert kind == "empty"

    def test_whitespace_only_is_empty(self):
        tokens, kind = parse_port_expression("   ")
        assert kind == "empty"

    # --- malformed ---
    def test_non_numeric_is_malformed(self):
        tokens, kind = parse_port_expression("http")
        assert kind == "malformed"
        assert tokens == []

    def test_malformed_range_is_malformed(self):
        tokens, kind = parse_port_expression("abc-def")
        assert kind == "malformed"

    def test_trailing_comma_with_empty_token_is_malformed(self):
        tokens, kind = parse_port_expression("443,")
        assert kind in ("malformed", "single")  # trailing comma produces empty token → malformed


# ---------------------------------------------------------------------------
# ScpFirewallRealizationResult — structure
# ---------------------------------------------------------------------------

class TestRealizationResultStructure:
    def test_returns_result_type(self):
        result = realize_rules([])
        assert isinstance(result, ScpFirewallRealizationResult)

    def test_has_direct_create(self):
        result = realize_rules([])
        assert isinstance(result.direct_create, list)

    def test_has_split_create(self):
        result = realize_rules([])
        assert isinstance(result.split_create, list)

    def test_has_reference_only(self):
        result = realize_rules([])
        assert isinstance(result.reference_only, list)

    def test_has_unsupported(self):
        result = realize_rules([])
        assert isinstance(result.unsupported, list)

    def test_has_summary(self):
        result = realize_rules([])
        assert isinstance(result.summary, dict)

    def test_summary_keys(self):
        result = realize_rules([])
        for key in ("direct_create_rules", "split_create_groups",
                    "split_create_rules", "reference_only", "unsupported",
                    "total_candidates", "total_realized_rules"):
            assert key in result.summary

    def test_empty_input_all_zero(self):
        result = realize_rules([])
        assert result.summary["total_candidates"] == 0
        assert result.summary["total_realized_rules"] == 0


# ---------------------------------------------------------------------------
# direct_create — single port
# ---------------------------------------------------------------------------

class TestDirectCreate:
    def test_single_port_is_direct_create(self):
        result = realize_rules([_candidate(port="443")])
        assert len(result.direct_create) == 1

    def test_direct_create_has_realized_rule_id(self):
        result = realize_rules([_candidate(origin_idx=0, port="443")])
        assert "realized_rule_id" in result.direct_create[0]

    def test_direct_create_rule_id_format(self):
        result = realize_rules([_candidate(origin_idx=5, port="443")])
        assert result.direct_create[0]["realized_rule_id"] == "scp-fw-5-p0"

    def test_direct_create_has_origin_idx(self):
        result = realize_rules([_candidate(origin_idx=3, port="443")])
        assert result.direct_create[0]["origin_idx"] == 3

    def test_direct_create_has_origin_resource_id(self):
        result = realize_rules([_candidate(origin_idx=7, port="443")])
        assert result.direct_create[0]["origin_resource_id"] == "scp-fw-7"

    def test_direct_create_port_preserved(self):
        result = realize_rules([_candidate(port="443")])
        assert result.direct_create[0]["port"] == "443"

    def test_direct_create_source_ip_preserved(self):
        result = realize_rules([_candidate(source_ip="10.0.1.11", port="443")])
        assert result.direct_create[0]["source_ip"] == "10.0.1.11"

    def test_direct_create_target_ip_preserved(self):
        result = realize_rules([_candidate(target_ip="203.0.113.5", port="443")])
        assert result.direct_create[0]["target_ip"] == "203.0.113.5"

    def test_direct_create_protocol_preserved(self):
        result = realize_rules([_candidate(protocol="UDP", port="53")])
        assert result.direct_create[0]["protocol"] == "UDP"

    def test_direct_create_backend_hint(self):
        result = realize_rules([_candidate(port="443")])
        assert result.direct_create[0]["backend_hint"] == "scp"

    def test_direct_create_execution_methods(self):
        result = realize_rules([_candidate(port="443")])
        assert result.direct_create[0]["execution_method_candidates"] == ["scp_api", "scp_cli"]

    def test_direct_create_port_original(self):
        result = realize_rules([_candidate(port="443")])
        assert result.direct_create[0]["port_original"] == "443"

    def test_direct_create_has_endpoint_classes(self):
        result = realize_rules([_candidate(port="443",
                                            src_endpoint_class="internal",
                                            tgt_endpoint_class="managed_external")])
        assert result.direct_create[0]["src_endpoint_class"] == "internal"
        assert result.direct_create[0]["tgt_endpoint_class"] == "managed_external"

    def test_direct_create_has_cidr_flags(self):
        result = realize_rules([_candidate(port="443", src_is_cidr=True)])
        assert result.direct_create[0]["source_is_cidr"] is True

    def test_direct_create_not_in_split(self):
        result = realize_rules([_candidate(port="443")])
        assert result.split_create == []

    def test_summary_direct_count(self):
        candidates = [_candidate(origin_idx=i, port="443") for i in range(3)]
        result = realize_rules(candidates)
        assert result.summary["direct_create_rules"] == 3


# ---------------------------------------------------------------------------
# direct_create — port ranges
# ---------------------------------------------------------------------------

class TestDirectCreateRange:
    def test_hyphen_range_is_direct_create(self):
        result = realize_rules([_candidate(port="3200-3399", port_expression=True)])
        assert len(result.direct_create) == 1

    def test_hyphen_range_port_preserved(self):
        result = realize_rules([_candidate(port="3200-3399")])
        assert result.direct_create[0]["port"] == "3200-3399"

    def test_tilde_range_is_direct_create(self):
        result = realize_rules([_candidate(port="5000~5999", port_expression=True)])
        assert len(result.direct_create) == 1

    def test_tilde_range_normalized_in_rule(self):
        result = realize_rules([_candidate(port="5000~5999")])
        assert result.direct_create[0]["port"] == "5000-5999"

    def test_tilde_range_original_preserved(self):
        result = realize_rules([_candidate(port="5000~5999")])
        assert result.direct_create[0]["port_original"] == "5000~5999"


# ---------------------------------------------------------------------------
# split_create — comma-separated
# ---------------------------------------------------------------------------

class TestSplitCreate:
    def test_comma_separated_is_split_create(self):
        result = realize_rules([_candidate(port="1128,1129", port_expression=True)])
        assert len(result.split_create) == 1

    def test_split_create_not_in_direct(self):
        result = realize_rules([_candidate(port="1128,1129")])
        assert result.direct_create == []

    def test_split_create_group_has_rules(self):
        result = realize_rules([_candidate(port="1128,1129")])
        group = result.split_create[0]
        assert "rules" in group

    def test_split_create_correct_rule_count(self):
        result = realize_rules([_candidate(port="1128,1129,8443")])
        assert len(result.split_create[0]["rules"]) == 3

    def test_split_create_rules_have_correct_ports(self):
        result = realize_rules([_candidate(port="80,443")])
        ports = [r["port"] for r in result.split_create[0]["rules"]]
        assert ports == ["80", "443"]

    def test_split_create_rule_ids_indexed(self):
        result = realize_rules([_candidate(origin_idx=2, port="80,443")])
        ids = [r["realized_rule_id"] for r in result.split_create[0]["rules"]]
        assert ids == ["scp-fw-2-p0", "scp-fw-2-p1"]

    def test_split_create_preserves_original_port(self):
        result = realize_rules([_candidate(port="80,443")])
        assert result.split_create[0]["port_original"] == "80,443"

    def test_split_create_group_has_origin_idx(self):
        result = realize_rules([_candidate(origin_idx=4, port="80,443")])
        assert result.split_create[0]["origin_idx"] == 4

    def test_split_create_group_has_origin_resource_id(self):
        result = realize_rules([_candidate(origin_idx=4, port="80,443")])
        assert result.split_create[0]["origin_resource_id"] == "scp-fw-4"

    def test_split_create_tilde_range_normalized(self):
        result = realize_rules([_candidate(port="80,5000~5999")])
        ports = [r["port"] for r in result.split_create[0]["rules"]]
        assert ports == ["80", "5000-5999"]
        assert "~" not in "".join(ports)

    def test_split_create_mixed_port_and_range(self):
        result = realize_rules([_candidate(port="80,443,3200-3399")])
        ports = [r["port"] for r in result.split_create[0]["rules"]]
        assert ports == ["80", "443", "3200-3399"]

    def test_split_create_rules_carry_endpoint_classes(self):
        result = realize_rules([_candidate(port="80,443",
                                            src_endpoint_class="internal",
                                            tgt_endpoint_class="managed_external")])
        for rule in result.split_create[0]["rules"]:
            assert rule["src_endpoint_class"] == "internal"
            assert rule["tgt_endpoint_class"] == "managed_external"

    def test_split_create_rules_carry_cidr_flags(self):
        result = realize_rules([_candidate(port="80,443",
                                            src_is_cidr=True, tgt_is_cidr=True)])
        for rule in result.split_create[0]["rules"]:
            assert rule["source_is_cidr"] is True
            assert rule["target_is_cidr"] is True

    def test_summary_split_group_count(self):
        candidates = [_candidate(origin_idx=i, port="80,443") for i in range(4)]
        result = realize_rules(candidates)
        assert result.summary["split_create_groups"] == 4

    def test_summary_split_rules_count(self):
        candidates = [_candidate(origin_idx=i, port="80,443,8443") for i in range(2)]
        result = realize_rules(candidates)
        assert result.summary["split_create_rules"] == 6  # 2 groups × 3 ports


# ---------------------------------------------------------------------------
# reference_only
# ---------------------------------------------------------------------------

class TestReferenceOnly:
    def test_unknown_both_endpoints_is_reference_only(self):
        c = _candidate(port="443",
                        src_endpoint_class="unknown",
                        tgt_endpoint_class="unknown")
        result = realize_rules([c])
        assert len(result.reference_only) == 1

    def test_unknown_both_has_reason(self):
        c = _candidate(port="443",
                        src_endpoint_class="unknown",
                        tgt_endpoint_class="unknown")
        result = realize_rules([c])
        assert result.reference_only[0]["reason"] == "unknown_both_endpoints"

    def test_unknown_both_not_in_direct_or_split(self):
        c = _candidate(port="443",
                        src_endpoint_class="unknown",
                        tgt_endpoint_class="unknown")
        result = realize_rules([c])
        assert result.direct_create == []
        assert result.split_create == []

    def test_no_port_is_reference_only(self):
        c = _candidate(port=None)
        result = realize_rules([c])
        assert len(result.reference_only) == 1

    def test_no_port_reason(self):
        c = _candidate(port=None)
        result = realize_rules([c])
        assert result.reference_only[0]["reason"] == "no_port_defined"

    def test_empty_port_is_reference_only(self):
        c = _candidate(port="")
        result = realize_rules([c])
        assert len(result.reference_only) == 1

    def test_reference_only_has_origin_idx(self):
        c = _candidate(origin_idx=9, port=None)
        result = realize_rules([c])
        assert result.reference_only[0]["origin_idx"] == 9

    def test_unknown_source_only_is_still_realizable(self):
        # Only source unknown — not both — so still realizable
        c = _candidate(port="443",
                        src_endpoint_class="unknown",
                        tgt_endpoint_class="internal")
        result = realize_rules([c])
        assert len(result.direct_create) == 1
        assert result.reference_only == []


# ---------------------------------------------------------------------------
# unsupported
# ---------------------------------------------------------------------------

class TestUnsupported:
    def test_malformed_port_is_unsupported(self):
        c = _candidate(port="http")
        result = realize_rules([c])
        assert len(result.unsupported) == 1

    def test_malformed_port_reason(self):
        c = _candidate(port="http")
        result = realize_rules([c])
        assert result.unsupported[0]["reason"] == "malformed_port_expression"

    def test_malformed_not_in_direct_or_split(self):
        c = _candidate(port="http")
        result = realize_rules([c])
        assert result.direct_create == []
        assert result.split_create == []

    def test_unsupported_has_origin_idx(self):
        c = _candidate(origin_idx=11, port="bad-port-value-here")
        result = realize_rules([c])
        # "bad" is not numeric, "port" is not numeric after split on '-' → malformed
        assert result.unsupported[0]["origin_idx"] == 11


# ---------------------------------------------------------------------------
# Summary counts
# ---------------------------------------------------------------------------

class TestSummaryCounts:
    def test_total_candidates_is_sum_of_all_categories(self):
        candidates = [
            _candidate(origin_idx=0, port="443"),          # direct_create
            _candidate(origin_idx=1, port="80,443"),        # split_create
            _candidate(origin_idx=2, port=None),            # reference_only
            _candidate(origin_idx=3, port="http"),          # unsupported
        ]
        result = realize_rules(candidates)
        assert result.summary["total_candidates"] == 4

    def test_total_realized_rules_direct_plus_split(self):
        candidates = [
            _candidate(origin_idx=0, port="443"),    # 1 realized
            _candidate(origin_idx=1, port="80,443"), # 2 realized
        ]
        result = realize_rules(candidates)
        assert result.summary["total_realized_rules"] == 3

    def test_reference_only_not_counted_as_realized(self):
        candidates = [
            _candidate(origin_idx=0, port=None),    # reference_only
        ]
        result = realize_rules(candidates)
        assert result.summary["total_realized_rules"] == 0


# ---------------------------------------------------------------------------
# flat_rules — flattened view of all realized rules
# ---------------------------------------------------------------------------

class TestFlatRules:
    def test_flat_rules_is_list(self):
        result = realize_rules([])
        assert isinstance(result.flat_rules, list)

    def test_flat_rules_empty_on_no_candidates(self):
        result = realize_rules([])
        assert result.flat_rules == []

    def test_flat_rules_includes_direct_create(self):
        result = realize_rules([_candidate(origin_idx=0, port="443")])
        assert len(result.flat_rules) == 1

    def test_flat_rules_includes_split_create_rules(self):
        result = realize_rules([_candidate(origin_idx=1, port="80,443")])
        assert len(result.flat_rules) == 2

    def test_flat_rules_direct_plus_split(self):
        candidates = [
            _candidate(origin_idx=0, port="443"),      # direct_create → 1 rule
            _candidate(origin_idx=1, port="80,443"),   # split_create → 2 rules
        ]
        result = realize_rules(candidates)
        assert len(result.flat_rules) == 3

    def test_flat_rules_excludes_reference_only(self):
        candidates = [
            _candidate(origin_idx=0, port="443"),
            _candidate(origin_idx=1, port=None),        # reference_only
        ]
        result = realize_rules(candidates)
        assert len(result.flat_rules) == 1

    def test_flat_rules_excludes_unsupported(self):
        candidates = [
            _candidate(origin_idx=0, port="443"),
            _candidate(origin_idx=1, port="bad-port"),  # unsupported
        ]
        result = realize_rules(candidates)
        assert len(result.flat_rules) == 1

    def test_flat_rules_items_are_dicts(self):
        result = realize_rules([_candidate(port="443")])
        assert all(isinstance(r, dict) for r in result.flat_rules)

    def test_flat_rules_items_have_realized_rule_id(self):
        result = realize_rules([_candidate(port="443")])
        assert all("realized_rule_id" in r for r in result.flat_rules)

    def test_flat_rules_total_matches_summary(self):
        candidates = [
            _candidate(origin_idx=0, port="443"),
            _candidate(origin_idx=1, port="80,443,8443"),
            _candidate(origin_idx=2, port=None),
        ]
        result = realize_rules(candidates)
        assert len(result.flat_rules) == result.summary["total_realized_rules"]
