"""Debug script: run the SCP Firewall rule realization layer.

Pipeline:
  1. parse_s2d()             → desired_state
  2. classify_candidates()   → tgw_candidates (with enriched endpoint fields)
  3. realize_rules()         → direct_create / split_create / reference_only / unsupported
  4. Summarize per category with representative examples
  5. Write outputs/debug_scp_firewall_realization.json

Usage (from repo root):
    python scripts/debug_scp_firewall_realization.py [path/to/workbook.xlsx]
"""
import json
import sys
import ipaddress
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.parser import parse_s2d
from src.classification.firewall_rules import (
    classify_candidates,
    build_vm_hostnames,
    build_subnet_networks,
)
from src.transforms.scp_firewall_realizer import realize_rules


def _find_sample() -> Path:
    samples = sorted((_REPO_ROOT / "samples").glob("*.xlsx"))
    if not samples:
        raise FileNotFoundError("No .xlsx file found in samples/.")
    return samples[0]


def _build_platform_networks(subnets: list[dict]) -> list:
    nets = []
    for s in subnets:
        if s.get("group") == "internal":
            raw = s.get("ip_range")
            if raw:
                try:
                    nets.append(ipaddress.ip_network(str(raw).strip(), strict=False))
                except ValueError:
                    pass
    return nets


def _pick_examples(items: list[dict], n: int = 3) -> list[dict]:
    """Pick up to n representative examples, stripping bulky nested 'candidate' key."""
    out = []
    for item in items[:n]:
        sample = {k: v for k, v in item.items() if k != "candidate"}
        out.append(sample)
    return out


def _split_examples(groups: list[dict], n: int = 3) -> list[dict]:
    """Pick up to n split_create groups, keeping first 3 rules per group."""
    out = []
    for g in groups[:n]:
        out.append({
            "origin_idx":        g["origin_idx"],
            "origin_resource_id": g["origin_resource_id"],
            "port_original":     g["port_original"],
            "rules_count":       len(g["rules"]),
            "first_3_rules":     g["rules"][:3],
        })
    return out


def main(workbook_path: Path) -> None:
    print(f"Opening: {workbook_path}")
    state = parse_s2d(str(workbook_path))

    vm_hostnames      = build_vm_hostnames(state["vmware_vm"])
    subnet_networks   = build_subnet_networks(state["network"]["subnets"])
    platform_networks = _build_platform_networks(state["network"]["subnets"])

    classification = classify_candidates(
        state["firewall_rule_candidates"],
        vm_hostnames,
        subnet_networks,
        platform_networks=platform_networks,
    )

    tgw_candidates = classification.tgw_candidates
    result = realize_rules(tgw_candidates)
    s = result.summary

    print(f"\n[Realization Summary]")
    print(f"  Total candidates:       {s['total_candidates']}")
    print(f"  Total realized rules:   {s['total_realized_rules']}")
    print(f"  direct_create rules:    {s['direct_create_rules']}")
    print(f"  split_create groups:    {s['split_create_groups']}")
    print(f"  split_create rules:     {s['split_create_rules']}")
    print(f"  reference_only:         {s['reference_only']}")
    print(f"  unsupported:            {s['unsupported']}")

    # ── Per-category analysis ─────────────────────────────────────────────────

    # direct_create: endpoint class distribution
    dc_src = Counter(r.get("src_endpoint_class") for r in result.direct_create)
    dc_tgt = Counter(r.get("tgt_endpoint_class") for r in result.direct_create)
    print(f"\ndirect_create src_endpoint_class: {dict(dc_src.most_common())}")
    print(f"direct_create tgt_endpoint_class: {dict(dc_tgt.most_common())}")

    # split_create: rules-per-group distribution
    if result.split_create:
        rules_per_group = [len(g["rules"]) for g in result.split_create]
        print(f"\nsplit_create rules-per-group: "
              f"min={min(rules_per_group)} max={max(rules_per_group)} "
              f"total={sum(rules_per_group)}")

        # endpoint class combos in split groups
        split_combos: Counter = Counter()
        for g in result.split_create:
            rules = g["rules"]
            if rules:
                src = rules[0].get("src_endpoint_class", "?")
                tgt = rules[0].get("tgt_endpoint_class", "?")
                split_combos[f"{src} → {tgt}"] += 1
        print("split_create endpoint combos:")
        for combo, count in split_combos.most_common(6):
            print(f"  {combo:<45} {count:>4}")

    # ── Write output ──────────────────────────────────────────────────────────
    output = {
        "summary": s,
        "direct_create": {
            "count":              len(result.direct_create),
            "src_endpoint_class": dict(dc_src.most_common()),
            "tgt_endpoint_class": dict(dc_tgt.most_common()),
            "examples":           result.direct_create[:5],
        },
        "split_create": {
            "count":        len(result.split_create),
            "total_rules":  s["split_create_rules"],
            "examples":     _split_examples(result.split_create, n=3),
        },
        "reference_only": {
            "count":    len(result.reference_only),
            "examples": _pick_examples(result.reference_only),
        },
        "unsupported": {
            "count":    len(result.unsupported),
            "examples": _pick_examples(result.unsupported),
        },
    }

    out_path = _REPO_ROOT / "outputs" / "debug_scp_firewall_realization.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _find_sample()
    main(path)
