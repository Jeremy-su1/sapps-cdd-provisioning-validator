"""SCP Firewall rule realization — converts enriched TGW candidates into execution-ready rules.

Realization categories:
  direct_create   — one rule, no splitting needed (single port or port range)
  split_create    — comma-separated port expression → N rules, one per token
  reference_only  — cannot be realized automatically (unknown endpoints or missing port)
  unsupported     — malformed port expression; technically incompatible

Decision order per candidate:
  1. Both endpoints unknown → reference_only
  2. Port is empty          → reference_only
  3. Port is malformed      → unsupported
  4. Port kind == single / range → direct_create
  5. Port kind == multi          → split_create

Port normalization:
  - '~' is replaced with '-' (non-standard range separator from workbooks)
  - whitespace is stripped from each token
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_BACKEND_HINT                = "scp"
_EXECUTION_METHOD_CANDIDATES = ["scp_api", "scp_cli"]


# ---------------------------------------------------------------------------
# Port expression parsing
# ---------------------------------------------------------------------------

def _is_valid_port_token(token: str) -> bool:
    """Return True for a valid single port integer or a range like 'N-M'."""
    token = token.strip()
    if "-" in token:
        parts = token.split("-", 1)
        return (len(parts) == 2
                and parts[0].strip().isdigit()
                and parts[1].strip().isdigit())
    return token.isdigit()


def parse_port_expression(raw_port: object) -> tuple[list[str], str]:
    """Parse and normalize a port expression string.

    Normalization applied before parsing:
      - '~' replaced with '-' (tilde is a non-standard range separator)
      - each token stripped of whitespace

    Returns:
        (tokens, kind) where kind is one of:
        "single"   — one plain port number
        "range"    — one port range like "3200-3399"
        "multi"    — two or more tokens (comma-separated)
        "empty"    — None or blank string
        "malformed"— contains a token that is not a valid port or range
    """
    if raw_port is None:
        return [], "empty"

    s = str(raw_port).strip()
    if not s:
        return [], "empty"

    raw_tokens = [t.strip() for t in s.split(",")]
    raw_tokens = [t for t in raw_tokens if t]

    if not raw_tokens:
        return [], "empty"

    tokens: list[str] = []
    for t in raw_tokens:
        normalized = t.replace("~", "-")
        if not _is_valid_port_token(normalized):
            return [], "malformed"
        tokens.append(normalized)

    if len(tokens) == 1:
        return (tokens, "range") if "-" in tokens[0] else (tokens, "single")

    return tokens, "multi"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ScpFirewallRealizationResult:
    direct_create:  list[dict[str, Any]] = field(default_factory=list)
    split_create:   list[dict[str, Any]] = field(default_factory=list)
    reference_only: list[dict[str, Any]] = field(default_factory=list)
    unsupported:    list[dict[str, Any]] = field(default_factory=list)

    @property
    def flat_rules(self) -> list[dict]:
        """Flat list of all realized rules (direct_create + split_create rules)."""
        rules = list(self.direct_create)
        for group in self.split_create:
            rules.extend(group["rules"])
        return rules

    @property
    def summary(self) -> dict[str, int | str]:
        split_rule_count = sum(len(g["rules"]) for g in self.split_create)
        total_candidates = (len(self.direct_create) + len(self.split_create)
                            + len(self.reference_only) + len(self.unsupported))
        return {
            "direct_create_rules":  len(self.direct_create),
            "split_create_groups":  len(self.split_create),
            "split_create_rules":   split_rule_count,
            "reference_only":       len(self.reference_only),
            "unsupported":          len(self.unsupported),
            "total_candidates":     total_candidates,
            "total_realized_rules": len(self.direct_create) + split_rule_count,
        }


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------

def _rule_id(origin_idx: int, port_idx: int) -> str:
    return f"scp-fw-{origin_idx}-p{port_idx}"


def _realized_rule(candidate: dict, port: str, port_idx: int) -> dict:
    origin_idx = candidate.get("origin_idx", 0)
    return {
        "realized_rule_id":            _rule_id(origin_idx, port_idx),
        "origin_idx":                  origin_idx,
        "origin_resource_id":          f"scp-fw-{origin_idx}",
        "source_ip":                   candidate.get("source_ip"),
        "source_is_cidr":              candidate.get("src_is_cidr", False),
        "target_ip":                   candidate.get("target_ip"),
        "target_is_cidr":              candidate.get("tgt_is_cidr", False),
        "protocol":                    candidate.get("protocol"),
        "port":                        port,
        "port_original":               candidate.get("port"),
        "action":                      candidate.get("action", "permit"),
        "backend_hint":                _BACKEND_HINT,
        "execution_method_candidates": _EXECUTION_METHOD_CANDIDATES,
        "src_endpoint_class":          candidate.get("src_endpoint_class"),
        "tgt_endpoint_class":          candidate.get("tgt_endpoint_class"),
    }


def _reference_entry(candidate: dict, reason: str) -> dict:
    origin_idx = candidate.get("origin_idx", 0)
    return {
        "origin_idx":        origin_idx,
        "origin_resource_id": f"scp-fw-{origin_idx}",
        "reason":            reason,
        "candidate":         candidate,
    }


def _unsupported_entry(candidate: dict, reason: str) -> dict:
    origin_idx = candidate.get("origin_idx", 0)
    return {
        "origin_idx":        origin_idx,
        "origin_resource_id": f"scp-fw-{origin_idx}",
        "reason":            reason,
        "candidate":         candidate,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def realize_rules(candidates: list[dict]) -> ScpFirewallRealizationResult:
    """Convert enriched TGW candidates into execution-ready SCP firewall rule sets.

    Args:
        candidates: Enriched TGW candidate dicts from classify_candidates(),
                    each carrying src_endpoint_class, tgt_endpoint_class,
                    src_is_cidr, tgt_is_cidr, port, protocol, etc.

    Returns:
        ScpFirewallRealizationResult with direct_create, split_create,
        reference_only, and unsupported rule lists.
    """
    result = ScpFirewallRealizationResult()

    for candidate in candidates:
        src_class = candidate.get("src_endpoint_class")
        tgt_class = candidate.get("tgt_endpoint_class")

        # ── 1. Both endpoints unknown → reference_only ────────────────────────
        if src_class == "unknown" and tgt_class == "unknown":
            result.reference_only.append(
                _reference_entry(candidate, "unknown_both_endpoints")
            )
            continue

        # ── 2–3. Parse port expression ────────────────────────────────────────
        tokens, kind = parse_port_expression(candidate.get("port"))

        if kind == "empty":
            result.reference_only.append(
                _reference_entry(candidate, "no_port_defined")
            )
            continue

        if kind == "malformed":
            result.unsupported.append(
                _unsupported_entry(candidate, "malformed_port_expression")
            )
            continue

        # ── 4. Single port or range → direct_create ──────────────────────────
        if kind in ("single", "range"):
            result.direct_create.append(
                _realized_rule(candidate, tokens[0], 0)
            )

        # ── 5. Multi → split_create ───────────────────────────────────────────
        else:
            origin_idx = candidate.get("origin_idx", 0)
            rules = [
                _realized_rule(candidate, port, i)
                for i, port in enumerate(tokens)
            ]
            result.split_create.append({
                "origin_idx":        origin_idx,
                "origin_resource_id": f"scp-fw-{origin_idx}",
                "port_original":     candidate.get("port"),
                "rules":             rules,
            })

    return result
