# -*- coding: utf-8 -*-
"""Build the Stage 3 paired compliance benchmark (variant + compliant control).

Zero-API, zero-write to existing artifacts.  This turns the existing 30-item
mutation panel into a PAIRED benchmark that can actually be scored:

- 30 VARIANT items: the mutated BPMN, whose Ground Truth is the mutation's
  violation type (missing_action / incorrect_actor / out_of_order);
- 30 CONTROL items: the SAME process with its UNMUTATED BPMN restored from the
  frozen Stage 1 membership file.  These are `compliant` - no violation of any
  of the three types - which is what gives precision / specificity a
  denominator.

Why controls come from the frozen original BPMN
-----------------------------------------------
The mutation manifest already pins `source_bpmn` + `source_bpmn_sha256` for
every variant, and `verify_stage1_stage3_gdpr7.py` independently pins the
frozen GDPR7 membership.  Re-using those bytes means the compliant control is
byte-identical to the frozen Stage 1 process — it is not a newly authored
"compliant-looking" process, so no human re-annotation is needed and nothing
can drift.

Grounding contract (recorded per item, never inferred)
------------------------------------------------------
The benchmark DOES NOT pretend that grounding rule text onto BPMN activities is
free.  Each item carries an explicit `grounding` block naming:

- `rule_action_text`      - the rule-side action the item is about;
- `target_activity_id`    - the process-side node it is bound to;
- `expected_actor_lane`   - the lane that legitimately performs it;
- `order_pair`            - the ordered node pair, for out_of_order.

A detector may either consume that binding directly (the grounded path) or try
to re-derive it (the similarity path).  Recording it makes the two comparable
instead of silently hiding which one an arm used.

Anti-degeneracy validation
--------------------------
Every item is checked so the benchmark cannot silently become unmeasurable
again:

- the control must NOT exhibit the target violation;
- the variant MUST exhibit it;
- a control and its variant must differ (the mutation must be observable).

Any failing item is reported, never dropped silently.

Outputs (new files only, existing panel untouched):

- ``data/development/stage3_synth/stage3_paired_benchmark_v1.json``
- ``outputs/reports/stage3_paired_benchmark_v1.{json,md}``

Usage:
    python scripts/build_stage3_paired_benchmark_v1.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
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

PANEL = (ROOT / "data/development/stage3_synth"
         / "synthetic_controlled_error_extension_v1.json")
INFERENCE_PACK = (ROOT / "data/development/human_review"
                  / "stage3_gold_inference_v1.json")
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
OUT_MANIFEST = (ROOT / "data/development/stage3_synth"
                / "stage3_paired_benchmark_v1.json")
TYPES = ("missing_action", "incorrect_actor", "out_of_order")
COMPLIANT = "compliant"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    flow = record.get("control_flow") or {}
    out: set[tuple[str, str]] = set()
    for item in flow.get("reachable_pairs") or []:
        if isinstance(item, dict):
            src, dst = item.get("source_ref"), item.get("target_ref")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            src, dst = item
        else:
            raise TypeError(f"unexpected reachable_pairs element: {item!r}")
        if src and dst:
            out.add((src, dst))
    return out


def _activities(record: dict[str, Any]) -> set[str]:
    return {a["id"] for a in record.get("activities") or []}


def _lane_of(record: dict[str, Any], activity_id: str) -> str | None:
    owner = None
    for lane in record.get("lanes") or []:
        if activity_id in (lane.get("flow_node_refs") or []):
            owner = lane.get("name") or lane.get("id")
    return owner


def observe(record: dict[str, Any], violation_type: str,
            target_activity_id: str | None,
            order_pair: list[str]) -> dict[str, Any]:
    """Structural observation of ONE violation type on ONE process.

    Returns ``{"violated": bool | None, "detail": {...}}``.  ``None`` means the
    type is not answerable from the process alone for this item.
    """
    if violation_type == "missing_action":
        present = target_activity_id in _activities(record)
        return {"violated": not present,
                "detail": {"target_present": present}}
    if violation_type == "incorrect_actor":
        lane = _lane_of(record, target_activity_id)
        # the frozen GDPR7 processes carry ONE (unnamed) lane that owns every
        # node; the mutation injects an ADDITIONAL named lane and moves the
        # target into it.  A second, named lane owning the target is therefore
        # the structural signature of the incorrect-actor mutation.
        named_lanes = [l for l in record.get("lanes") or []
                       if (l.get("name") or "").strip()]
        moved = bool(lane) and any(
            (l.get("name") or "") == lane for l in named_lanes)
        return {"violated": moved,
                "detail": {"target_lane": lane,
                           "named_lane_count": len(named_lanes)}}
    if violation_type == "out_of_order":
        if len(order_pair) != 2:
            return {"violated": None, "detail": {"reason": "no_order_pair"}}
        edges = _edges(record)
        reach = _reachable(record)
        forward = (order_pair[0], order_pair[1])
        backward = (order_pair[1], order_pair[0])
        fwd = forward in edges or forward in reach
        back = backward in edges or backward in reach
        return {"violated": bool(back and not fwd),
                "detail": {"forward_holds": fwd, "backward_holds": back}}
    raise ValueError(f"unknown violation type: {violation_type}")


def build() -> dict[str, Any]:
    panel = _load(PANEL)
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    inference = _load(INFERENCE_PACK)
    rule_text = {i["rule_id"]: i.get("rule_text", "")
                 for i in inference.get("matching_items", [])}

    parse_cache: dict[str, Any] = {}

    def parsed(path: Path):
        key = str(path)
        if key not in parse_cache:
            parse_cache[key] = parse_bpmn_file(path, contract=contract)
        return parse_cache[key]

    items: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []

    for variant in panel["variants"]:
        target_type = variant["mutation_type"]
        target_activity = variant.get("target_activity_id")
        diff = (variant.get("mutation_config") or {}).get("diff") or {}
        order_pair = [n for n in (diff.get("pair") or []) if n]
        control_path = ROOT / variant["source_bpmn"]
        variant_path = ROOT / variant["variant_bpmn"]
        control_record = parsed(control_path)
        variant_record = parsed(variant_path)

        grounding = {
            "rule_id": variant["rule_id"],
            "process_id": variant["process_id"],
            "rule_action_text": rule_text.get(variant["rule_id"], ""),
            "target_activity_id": target_activity,
            "control_target_lane": _lane_of(control_record, target_activity),
            "variant_target_lane": _lane_of(variant_record, target_activity),
            "order_pair": order_pair,
            "grounding_source": "locked_panel_mutation_manifest",
        }

        obs_control = observe(control_record, target_type, target_activity,
                              order_pair)
        obs_variant = observe(variant_record, target_type, target_activity,
                              order_pair)

        # ---- anti-degeneracy checks -------------------------------------
        if obs_control["violated"] is None or obs_variant["violated"] is None:
            problems.append({"variant_id": variant["variant_id"],
                             "reason": "type_not_answerable_structurally"})
        else:
            if obs_control["violated"]:
                problems.append({
                    "variant_id": variant["variant_id"],
                    "reason": "control_already_violates",
                    "detail": obs_control["detail"]})
            if not obs_variant["violated"]:
                problems.append({
                    "variant_id": variant["variant_id"],
                    "reason": "variant_does_not_violate",
                    "detail": obs_variant["detail"]})

        base = f"{variant['variant_id']}"
        control_item = {
            "item_id": f"{base}__control",
            "pair_id": base,
            "role": "control",
            "bpmn_path": str(control_path.relative_to(ROOT)).replace("\\", "/"),
            "bpmn_sha256": _sha256(control_path),
            "rule_id": variant["rule_id"],
            "process_id": variant["process_id"],
            "target_violation_type": target_type,
            "gold_violation_type": COMPLIANT,
            "grounding": grounding,
            "structural_observation": obs_control,
        }
        variant_item = {
            "item_id": f"{base}__variant",
            "pair_id": base,
            "role": "variant",
            "bpmn_path": str(variant_path.relative_to(ROOT)).replace("\\", "/"),
            "bpmn_sha256": _sha256(variant_path),
            "rule_id": variant["rule_id"],
            "process_id": variant["process_id"],
            "target_violation_type": target_type,
            "gold_violation_type": target_type,
            "grounding": grounding,
            "structural_observation": obs_variant,
        }
        items.extend([control_item, variant_item])
        pairs.append((control_item, variant_item))

    by_type = Counter(i["target_violation_type"] for i in items)
    gold_dist = Counter(i["gold_violation_type"] for i in items)

    return {
        "schema_version": "stage3_paired_compliance_benchmark@1.0.0",
        "benchmark_id": "stage3_paired_benchmark_v1",
        "status": "dev_only_benchmark_not_human_gold",
        "source_panel": str(PANEL.relative_to(ROOT)).replace("\\", "/"),
        "source_panel_sha256": _sha256(PANEL),
        "controls_source": (
            "the frozen Stage 1 GDPR7 membership BPMN "
            "(data/input/stage1_stage3/gdpr7/), re-used via each variant's "
            "manifest-declared source_bpmn + source_bpmn_sha256; no new "
            "compliant process was authored"),
        "violation_types": list(TYPES),
        "compliant_label": COMPLIANT,
        "counts": {
            "items": len(items),
            "pairs": len(pairs),
            "by_role": dict(Counter(i["role"] for i in items)),
            "by_target_type": dict(by_type),
            "by_gold_label": dict(gold_dist),
        },
        "grounding_contract": (
            "each item declares its rule->process binding explicitly; a "
            "detector may consume it (grounded path) or re-derive it "
            "(similarity path), and the two are comparable because the binding "
            "is recorded rather than assumed"),
        "anti_degeneracy": {
            "rule": ("every control must NOT exhibit its target violation and "
                     "every variant MUST exhibit it"),
            "problems": problems,
            "problems_count": len(problems),
            "passed": not problems,
        },
        "scoring_denominator": (
            "60 items = 30 control (compliant) + 30 variant, so precision, "
            "recall, F1 and compliant specificity all have a denominator"),
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "gold_modified": False,
            "existing_panel_modified": False,
            "original_bpmn_modified": False,
            "panel_is_human_gold": False,
        },
        "items": items,
    }


def render(benchmark: dict[str, Any]) -> str:
    lines: list[str] = []
    counts = benchmark["counts"]
    lines.append("# Stage 3 paired compliance benchmark (v1)")
    lines.append("")
    lines.append(f"Benchmark id: `{benchmark['benchmark_id']}` - status "
                 f"`{benchmark['status']}` - zero LLM calls.")
    lines.append("")
    lines.append("## What this fixes")
    lines.append("")
    lines.append("The 30-item mutation panel had no compliant items, so "
                 "precision and specificity had no denominator, and every "
                 "reported per-type F1 was degenerate. This benchmark pairs "
                 "each mutated BPMN with the **frozen original** of the same "
                 "process as a compliant control.")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- Items: **{counts['items']}** ({counts['pairs']} pairs)")
    lines.append(f"- By role: {counts['by_role']}")
    lines.append(f"- By target violation type: {counts['by_target_type']}")
    lines.append(f"- By gold label: {counts['by_gold_label']}")
    lines.append("")
    lines.append("## Anti-degeneracy validation")
    lines.append("")
    ad = benchmark["anti_degeneracy"]
    lines.append(f"Rule: {ad['rule']}.")
    lines.append("")
    lines.append(f"Result: **{'PASS' if ad['passed'] else 'FAIL'}** "
                 f"({ad['problems_count']} problem(s)).")
    if ad["problems"]:
        lines.append("")
        lines.append("| Pair | Reason |")
        lines.append("|---|---|")
        for problem in ad["problems"]:
            lines.append(f"| {problem['variant_id']} | {problem['reason']} |")
    lines.append("")
    lines.append("## Grounding contract")
    lines.append("")
    lines.append(benchmark["grounding_contract"] + ".")
    lines.append("")
    lines.append("## Per-pair structural observation")
    lines.append("")
    lines.append("| Pair | Type | Control | Variant | Separable |")
    lines.append("|---|---|---|---|---|")
    for item in benchmark["items"]:
        if item["role"] != "control":
            continue
        variant = next(i for i in benchmark["items"]
                       if i["pair_id"] == item["pair_id"]
                       and i["role"] == "variant")
        c = item["structural_observation"]["violated"]
        v = variant["structural_observation"]["violated"]
        lines.append(f"| {item['pair_id']} | {item['target_violation_type']} | "
                     f"{'violates' if c else 'compliant'} | "
                     f"{'violates' if v else 'compliant'} | "
                     f"{'YES' if (not c and v) else 'no'} |")
    lines.append("")
    lines.append("## Provenance")
    lines.append("")
    lines.append(f"- Source panel: `{benchmark['source_panel']}` "
                 f"(sha256 `{benchmark['source_panel_sha256']}`)")
    lines.append(f"- Controls: {benchmark['controls_source']}")
    lines.append(f"- Scoring denominator: {benchmark['scoring_denominator']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(ROOT / "outputs" / "reports"))
    args = parser.parse_args()

    benchmark = build()
    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    if OUT_MANIFEST.exists():
        raise SystemExit(
            f"refusing to overwrite existing benchmark manifest: {OUT_MANIFEST}")
    OUT_MANIFEST.write_text(
        json.dumps(benchmark, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n", encoding="utf-8")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stage3_paired_benchmark_v1.json").write_text(
        json.dumps(benchmark, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n", encoding="utf-8")
    text = render(benchmark)
    (out_dir / "stage3_paired_benchmark_v1.md").write_text(text,
                                                           encoding="utf-8")

    print(f"wrote {OUT_MANIFEST}")
    print(f"wrote {out_dir / 'stage3_paired_benchmark_v1.json'}")
    print(f"wrote {out_dir / 'stage3_paired_benchmark_v1.md'}")
    print()
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    return 0 if benchmark["anti_degeneracy"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
