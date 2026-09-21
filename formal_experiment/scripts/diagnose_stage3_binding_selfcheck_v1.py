# -*- coding: utf-8 -*-
"""READ-ONLY probe: can a detector self-check a declared binding from the Rule
Record, without any human annotation and without embedding similarity?

Motivation
----------
The paired benchmark declares, per item, WHICH BPMN activity was mutated
(``target_activity_id``) but never which rule action that activity realizes.
Deriving that link by embedding similarity is the step measured to fail. Before
concluding that a human annotation is unavoidable, this probe tests a different
route: a SEMANTIC CONSTRAINT check.

For ``out_of_order`` specifically the panel records an ordered node pair
(``mutation_config.diff.pair``).  That is a process-side fact.  If the Rule
Record carries ordering information, the two can be compared; and even without
it, the mutation itself can be validated against the reachability relation that
the rule's own endpoint mapping would have to satisfy.

This probe reports, for every item:

- whether the declared ordered pair is actually ordered in the CONTROL BPMN
  (if not, the item's premise is broken);
- whether the pair's ordering is inverted in the VARIANT (the intended effect);
- whether the Rule Record supplies any ordering information at all.

Nothing is written.  No LLM/API.  No similarity model.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
)

BENCHMARK = (ROOT / "data/development/stage3_synth"
             / "stage3_paired_benchmark_v1.json")
GOLD_RULES = ROOT / "data/gold/stage3/gdpr7_gold_rule_records_v1.json"
DIRECT_LLM_CAPSULE = (ROOT / "data" / "predictions" / "gdpr7_direct_llm_v1"
                      / "predictions.json")
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _edges(record: dict[str, Any]) -> set[tuple[str, str]]:
    out = set()
    for item in (record.get("control_flow") or {}).get("direct_edges") or []:
        if isinstance(item, dict):
            src, dst = item.get("source_ref"), item.get("target_ref")
            if src and dst:
                out.add((src, dst))
    return out


def _reachable(record: dict[str, Any]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for item in ((record.get("control_flow") or {}).get("reachable_pairs")
                 or []):
        if isinstance(item, dict):
            src, dst = item.get("source_ref"), item.get("target_ref")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            src, dst = item
        else:
            raise TypeError(f"unexpected reachable_pairs element: {item!r}")
        if src and dst:
            out.add((src, dst))
    return out


def _ordering(record: dict[str, Any], a: str, b: str) -> dict[str, bool]:
    edges = _edges(record)
    reach = _reachable(record)
    forward = (a, b) in edges or (a, b) in reach
    backward = (b, a) in edges or (b, a) in reach
    return {"forward": forward, "backward": backward,
            "ordered_forward_only": forward and not backward}


def main() -> int:
    benchmark = _load(BENCHMARK)
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)

    parse_cache: dict[str, Any] = {}

    def parsed(path: Path):
        key = str(path)
        if key not in parse_cache:
            parse_cache[key] = parse_bpmn_file(path, contract=contract)
        return parse_cache[key]

    print("=" * 100)
    print("A. out_of_order items: is the declared pair genuinely ordered in "
          "the CONTROL, and inverted in the VARIANT?")
    print("=" * 100)
    print(f"{'pair':<26}{'control fwd':>12}{'control bwd':>12}"
          f"{'control ordered':>16}{'variant fwd':>12}{'variant bwd':>12}"
          f"{'inverted':>10}")
    print("-" * 100)

    stats: Counter = Counter()
    for item in benchmark["items"]:
        if item["role"] != "control":
            continue
        if item["target_violation_type"] != "out_of_order":
            continue
        pair = [n for n in (item["grounding"].get("order_pair") or []) if n]
        if len(pair) != 2:
            stats["no_pair"] += 1
            continue
        control = parsed(ROOT / item["bpmn_path"])
        variant_item = next(i for i in benchmark["items"]
                            if i["pair_id"] == item["pair_id"]
                            and i["role"] == "variant")
        variant = parsed(ROOT / variant_item["bpmn_path"])
        co = _ordering(control, pair[0], pair[1])
        va = _ordering(variant, pair[0], pair[1])
        inverted = (co["ordered_forward_only"]
                    and va["backward"] and not va["forward"])
        stats["control_ordered_forward_only" if co["ordered_forward_only"]
              else "control_not_forward_ordered"] += 1
        stats["variant_inverted" if inverted else "variant_not_inverted"] += 1
        print(f"{item['pair_id']:<26}{str(co['forward']):>12}"
              f"{str(co['backward']):>12}"
              f"{str(co['ordered_forward_only']):>16}"
              f"{str(va['forward']):>12}{str(va['backward']):>12}"
              f"{str(inverted):>10}")

    print()
    print("A summary:", dict(stats))
    print()

    print("=" * 100)
    print("B. Does the Rule Record supply ordering information at all?")
    print("=" * 100)
    gold = _load(GOLD_RULES)
    total_clauses = 0
    clauses_with_or = 0
    order_links = 0
    for record in gold["records"]:
        for clause in record.get("clauses") or []:
            total_clauses += 1
            links = clause.get("order_relations") or []
            if links:
                clauses_with_or += 1
                order_links += len(links)
    print(f"  Gold Rule Records: {total_clauses} clauses, "
          f"{clauses_with_or} with order relations "
          f"({order_links} links)")
    if DIRECT_LLM_CAPSULE.is_file():
        capsule = _load(DIRECT_LLM_CAPSULE)
        rows = capsule.get("records") or capsule.get("predictions") or []
        cap_clauses = 0
        cap_with_or = 0
        cap_links = 0
        for row in rows:
            record = row.get("record") or {}
            for clause in record.get("clauses") or []:
                cap_clauses += 1
                links = clause.get("order_relations") or []
                if links:
                    cap_with_or += 1
                    cap_links += len(links)
        print(f"  Direct-LLM capsule: {len(rows)} rows, {cap_clauses} clauses, "
              f"{cap_with_or} with order relations ({cap_links} links)")
    else:
        print(f"  Direct-LLM capsule: NOT FOUND at "
              f"{DIRECT_LLM_CAPSULE.relative_to(ROOT)}")
    print()

    print("=" * 100)
    print("C. Verdict")
    print("=" * 100)
    ordered = stats.get("control_ordered_forward_only", 0)
    inverted = stats.get("variant_inverted", 0)
    print(f"  out_of_order pairs whose CONTROL is forward-ordered : "
          f"{ordered}/10")
    print(f"  out_of_order pairs whose VARIANT is inverted         : "
          f"{inverted}/10")
    print(f"  order relations available from the rule side         : "
          f"gold={order_links}"
          + (f", direct_llm={cap_links}"
             if DIRECT_LLM_CAPSULE.is_file() else ""))
    print()
    print("  If the CONTROL pair is forward-ordered and the VARIANT is its")
    print("  inversion, then out_of_order is decidable from the PROCESS")
    print("  SIDE ALONE once the rule names the two endpoints. The rule side")
    print("  is what carries no ordering information, which is precisely why")
    print("  the endpoint binding has to be annotated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
