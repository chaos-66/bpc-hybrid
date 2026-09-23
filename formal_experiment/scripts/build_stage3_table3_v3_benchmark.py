# -*- coding: utf-8 -*-
"""Build the blinded, full-rule-base Stage 3 Table 3 v3 benchmark surface.

This script does not run inference and does not modify the v1/v2 benchmark.
It creates three new, versioned artifacts:

1. a Gold-blind inference view containing only ``case_id``, ``bpmn_path`` and
   ``process_id``;
2. a case map kept separate from inference, with the pair/role/target labels
   used only by the evaluator after predictions are persisted;
3. a control-compliance and exclusion audit built from the frozen mutation
   manifest and the human-approved binding reference.

The audit is deliberately narrow: it establishes the target-seed control
state (the unmutated source BPMN) and marks every out-of-order pair
unavailable because no rule record carries a real order relation.  It does
not pretend that the source BPMNs are complete multi-label annotations for
all nine rules.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = (
    ROOT / "data/development/stage3_synth/stage3_paired_benchmark_v1.json"
)
ELIGIBILITY = (
    ROOT / "data/development/stage3_synth"
    / "stage3_paired_benchmark_eligibility_v1.json"
)
MUTATIONS = (
    ROOT / "data/development/stage3_synth"
    / "synthetic_controlled_error_extension_v1.json"
)
BINDING_REFERENCE = (
    ROOT / "data/development/stage3_synth"
    / "stage3_binding_resolved_reference_v1.json"
)
INFERENCE_VIEW = (
    ROOT / "data/development/stage3_synth"
    / "stage3_sun_style_inference_view_v3.json"
)
CASE_MAP = (
    ROOT / "data/development/stage3_synth"
    / "stage3_sun_style_case_map_v3.json"
)
AUDIT_JSON = ROOT / "outputs/reports/stage3_sun_style_benchmark_audit_v3.json"
AUDIT_MD = ROOT / "outputs/reports/stage3_sun_style_benchmark_audit_v3.md"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case_id(index: int) -> str:
    return f"case_{index:04d}"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _blank_control_basis(item: dict[str, Any], eligibility_row: dict[str, Any],
                         mutation: dict[str, Any]) -> dict[str, Any]:
    structural = item.get("structural_observation") or {}
    return {
        "eligible": bool(eligibility_row.get("eligible")),
        "eligibility_reason": eligibility_row.get("reason"),
        "binding_completeness": eligibility_row.get("binding_completeness"),
        "mutation_validation": mutation.get("validation_checks"),
        "control_structural_observation": structural,
        "source_bpmn": mutation.get("source_bpmn"),
        "source_bpmn_sha256": mutation.get("source_bpmn_sha256"),
        "variant_bpmn": mutation.get("variant_bpmn"),
        "variant_bpmn_sha256": mutation.get("variant_bpmn_sha256"),
        "scope": (
            "target-seed construction evidence only; the unmutated source "
            "BPMN is the control and the mutation manifest verifies that only "
            "the declared target changed. Full multi-label compliance for all "
            "nine rules is not asserted by this audit."
        ),
    }


def build() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    benchmark = _load(BENCHMARK)
    eligibility = _load(ELIGIBILITY)
    mutations_doc = _load(MUTATIONS)
    binding_doc = _load(BINDING_REFERENCE)

    if benchmark.get("safety", {}).get("panel_is_human_gold") is not False:
        raise ValueError("unexpected benchmark safety state")
    if benchmark.get("source_panel_sha256") != _sha256(MUTATIONS):
        raise ValueError("benchmark source mutation panel hash mismatch")

    eligibility_by_pair = {
        str(row.get("pair_id")): row for row in eligibility.get("records") or []
    }
    mutation_by_variant = {
        str(row.get("variant_id")): row for row in mutations_doc.get("variants") or []
    }
    binding_by_pair = {
        str(row.get("pair_id")): row for row in binding_doc.get("records") or []
    }

    items = sorted(benchmark.get("items") or [], key=lambda row: str(row["item_id"]))
    inference_items: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        cid = _case_id(index)
        inference_items.append({
            "case_id": cid,
            "bpmn_path": str(item["bpmn_path"]),
            "process_id": str(item["process_id"]),
        })
        pair_id = str(item["pair_id"])
        case_rows.append({
            "case_id": cid,
            "item_id": str(item["item_id"]),
            "pair_id": pair_id,
            "role": str(item["role"]),
            "process_id": str(item["process_id"]),
            "bpmn_path": str(item["bpmn_path"]),
            "bpmn_sha256": str(item["bpmn_sha256"]),
            "target_rule_id": str(item["rule_id"]),
            "target_violation_type": str(item["target_violation_type"]),
            "gold_violation_type": str(item["gold_violation_type"]),
            "eligible": bool(
                eligibility_by_pair.get(pair_id, {}).get("eligible", False)),
            "eligibility_reason": eligibility_by_pair.get(pair_id, {}).get("reason"),
        })

    controls = [r for r in case_rows if r["role"] == "control"]
    variants = [r for r in case_rows if r["role"] == "variant"]
    eligible_pairs = sorted({
        r["pair_id"] for r in case_rows if r["eligible"]
    })
    by_type = Counter(str(r["target_violation_type"]) for r in variants)
    audit_pairs: list[dict[str, Any]] = []
    for pair_id in sorted({str(r["pair_id"]) for r in case_rows}):
        pair_cases = [r for r in case_rows if r["pair_id"] == pair_id]
        control = next(r for r in pair_cases if r["role"] == "control")
        variant = next(r for r in pair_cases if r["role"] == "variant")
        variant_id = variant["item_id"][:-len("__variant")]
        mutation = mutation_by_variant.get(variant_id, {})
        eligibility_row = eligibility_by_pair.get(pair_id, {})
        binding = binding_by_pair.get(pair_id, {})
        target_type = variant["target_violation_type"]
        action_res = binding.get("action_resolution") or {}
        actor_res = binding.get("actor_resolution") or {}
        order_res = binding.get("order_resolution") or {}
        order_relation = (
            (mutation.get("mutation_config") or {}).get("diff") or {}
        ).get("pair") or []
        audit_pairs.append({
            "pair_id": pair_id,
            "target_rule_id": variant["target_rule_id"],
            "target_violation_type": target_type,
            "control_case_id": control["case_id"],
            "variant_case_id": variant["case_id"],
            "control_bpmn_path": control["bpmn_path"],
            "variant_bpmn_path": variant["bpmn_path"],
            "eligible": bool(eligibility_row.get("eligible", False)),
            "eligibility_reason": eligibility_row.get("reason"),
            "human_binding": {
                "action_status": action_res.get("status"),
                "action_text": action_res.get("text"),
                "actor_status": actor_res.get("status"),
                "actor_text": actor_res.get("text"),
                "order_status": order_res.get("status"),
            },
            "control_basis": _blank_control_basis(
                next(r for r in benchmark["items"] if r["item_id"] == control["item_id"]),
                eligibility_row,
                mutation,
            ),
            "rule_side_order_relation": order_relation,
            "order_eligible": bool(
                order_relation and order_res.get("status") == "not_applicable"
                and target_type == "out_of_order"
            ),
            "exclusion_reason": (
                None if eligibility_row.get("eligible") else
                (eligibility_row.get("reason") or "ineligible")
            ),
        })

    inference_view = {
        "schema_version": "stage3_sun_style_inference_view_v3@1.0.0",
        "view_id": "stage3_sun_style_inference_view_v3",
        "source_benchmark": str(BENCHMARK.relative_to(ROOT)).replace("\\", "/"),
        "source_benchmark_sha256": _sha256(BENCHMARK),
        "allowed_item_keys": ["case_id", "bpmn_path", "process_id"],
        "safety": {
            "pair_role_present": False,
            "gold_labels_present": False,
            "rule_id_present": False,
            "target_violation_type_present": False,
            "target_activity_present": False,
            "mutation_type_present": False,
        },
        "items": inference_items,
    }

    case_map = {
        "schema_version": "stage3_sun_style_case_map_v3@1.0.0",
        "inference_view": str(INFERENCE_VIEW.relative_to(ROOT)).replace("\\", "/"),
        "inference_view_sha256": None,
        "cases": case_rows,
        "counts": {
            "cases": len(case_rows),
            "controls": len(controls),
            "variants": len(variants),
            "unique_bpmn": len({r["bpmn_path"] for r in case_rows}),
            "unique_control_bpmn": len({r["bpmn_path"] for r in controls}),
            "duplicate_control_items": len(controls) - len({r["bpmn_path"] for r in controls}),
            "duplicate_control_items_eligible": (
                sum(1 for r in controls if r["eligible"])
                - len({r["bpmn_path"] for r in controls if r["eligible"]})
            ),
            "eligible_pairs": len(eligible_pairs),
            "eligible_cases": sum(1 for r in case_rows if r["eligible"]),
            "by_target_violation_type_variants": dict(sorted(by_type.items())),
        },
        "label_read_policy": (
            "This map contains Gold labels. The inference runner must not read "
            "it. The evaluator may read it only after predictions are persisted."
        ),
    }

    unavailable_order = [
        p for p in audit_pairs if p["target_violation_type"] == "out_of_order"
    ]
    audit = {
        "schema_version": "stage3_sun_style_benchmark_audit_v3@1.0.0",
        "benchmark_id": benchmark.get("benchmark_id"),
        "source_mutation_panel": str(MUTATIONS.relative_to(ROOT)).replace("\\", "/"),
        "source_mutation_panel_sha256": _sha256(MUTATIONS),
        "target_scope": (
            "single-mutation target seeds; full-rule-base matching is run, but "
            "checking metrics are scoped to the labeled target rule/type and "
            "the matching stage is evaluated separately with AP/MAP"
        ),
        "counts": {
            "pairs": len(audit_pairs),
            "eligible_pairs": len(eligible_pairs),
            "eligible_missing_action": sum(
                1 for p in audit_pairs if p["eligible"]
                and p["target_violation_type"] == "missing_action"),
            "eligible_incorrect_actor": sum(
                1 for p in audit_pairs if p["eligible"]
                and p["target_violation_type"] == "incorrect_actor"),
            "eligible_out_of_order": sum(
                1 for p in audit_pairs if p["eligible"]
                and p["target_violation_type"] == "out_of_order"),
            "out_of_order_unavailable": len(unavailable_order),
            "excluded_pairs": sum(1 for p in audit_pairs if not p["eligible"]),
        },
        "control_compliance": {
            "target_seed_evidence": (
                "unmutated source BPMN; mutation manifest verifies "
                "source_bytes_untouched and non-target-unchanged; human binding "
                "reference confirms the target action/actor relation for "
                "eligible pairs"
            ),
            "full_rule_base_multi_label_gold": False,
            "full_rule_base_control_compliance_established": False,
            "note": (
                "The audit supports the target-seed control state only. It does "
                "not claim that every one of the nine rules has a complete "
                "control-vs-violation annotation."
            ),
        },
        "pairs": audit_pairs,
    }

    return inference_view, case_map, audit


def _render_md(audit: dict[str, Any], case_map: dict[str, Any]) -> str:
    lines = [
        "# Stage 3 v3 blinded benchmark and control audit",
        "",
        f"- source mutation panel: `{audit['source_mutation_panel']}`",
        f"- pairs: {audit['counts']['pairs']}",
        f"- eligible pairs: {audit['counts']['eligible_pairs']}",
        f"- eligible missing-action: {audit['counts']['eligible_missing_action']}",
        f"- eligible incorrect-actor: {audit['counts']['eligible_incorrect_actor']}",
        f"- eligible out-of-order: {audit['counts']['eligible_out_of_order']}",
        f"- out-of-order unavailable: {audit['counts']['out_of_order_unavailable']}",
        f"- unique control BPMNs: {case_map['counts']['unique_control_bpmn']}",
        "",
        "## Scope",
        "",
        audit["target_scope"],
        "",
        "## Control compliance",
        "",
        f"- target-seed evidence: {audit['control_compliance']['target_seed_evidence']}",
        "- full multi-label Gold: **not available**",
        "- full-rule-base control compliance established: **no**",
        "",
        "## Pair audit",
        "",
        "| Pair | Type | Eligible | Reason |",
        "|---|---|---|---|",
    ]
    for pair in audit["pairs"]:
        lines.append(
            f"| {pair['pair_id']} | {pair['target_violation_type']} | "
            f"{'yes' if pair['eligible'] else 'no'} | {pair['exclusion_reason'] or 'eligible'} |"
        )
    lines += [
        "",
        "## Inference-view guarantee",
        "",
        "The v3 inference view contains only `case_id`, `bpmn_path`, and `process_id`.",
        "It contains no pair role, rule id, target type, mutation type, target activity, or Gold label.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    for path in (INFERENCE_VIEW, CASE_MAP, AUDIT_JSON, AUDIT_MD):
        if path.exists() and not args.overwrite:
            raise SystemExit(f"refusing to overwrite existing {path}")
    inference_view, case_map, audit = build()
    case_map["inference_view_sha256"] = None
    _write_json(INFERENCE_VIEW, inference_view)
    case_map["inference_view_sha256"] = _sha256(INFERENCE_VIEW)
    _write_json(CASE_MAP, case_map)
    _write_json(AUDIT_JSON, audit)
    AUDIT_MD.write_text(_render_md(audit, case_map), encoding="utf-8",
                        newline="\n")
    print(json.dumps({
        "inference_view": str(INFERENCE_VIEW),
        "case_map": str(CASE_MAP),
        "audit_json": str(AUDIT_JSON),
        "cases": case_map["counts"]["cases"],
        "eligible_pairs": case_map["counts"]["eligible_pairs"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
