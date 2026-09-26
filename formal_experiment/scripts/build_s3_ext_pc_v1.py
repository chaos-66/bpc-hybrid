# -*- coding: utf-8 -*-
"""S3.9-EXT-PC-V1 development builder.

Phase A: read-only semantic disposition of the 20 historical
prohibition/condition pair families in
``synthetic_controlled_error_extension_v2.json``.  This module never edits the
historical panel, historical predictions, or historical labels.

The script is also the intended home for later Phase B mechanism-case
construction.  Phase A intentionally runs before any new detector is written
or any new result is observed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
    validate_process_record,
)

LEGACY_PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
STAGE1_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
LEGACY_OUT_DIR = ROOT / "data/development/stage3_ext_pc_v1"
LEGACY_DISPOSITION = LEGACY_OUT_DIR / "legacy_semantic_disposition_v1.json"
V5_PREDICTIONS = ROOT / "outputs/development/s3_semantic_grounding_v5/predictions.jsonl"

LEGACY_TARGETS = ("prohibited_action_present", "required_condition_not_enforced")
REVIEWER_IDENTITY = "AI_research_semantic_audit"

# ---------------------------------------------------------------------------
# Phase A semantic assessment table
# ---------------------------------------------------------------------------

# This table is the research-semantic audit result.  It is deliberately
# written before any new detector exists and is not derived from the historical
# target_type.  Fields:
#   assessment: one of the value vocabulary required by the task prompt.
#   eligibility: eligible_for_new_v1_semantics | not_applicable | unsupported
#   reason: concise reason when not directly reusable under v1.
SEMANTIC_AUDIT: dict[str, dict[str, str]] = {
    "syn_v2_prohibited_action_01": {
        "assessment": "direct_unconditional_action_prohibition",
        "eligibility": "eligible_for_new_v1_semantics",
        "reason": (
            "The source expresses a direct prohibition of subjecting the data "
            "subject to an automated decision.  The historical extracted action "
            "'affects similarly significantly him or her' is a relative-clause "
            "fragment, not the executable prohibited act; the clause would need "
            "canonical action rebinding before it could be reused by the new "
            "checker."
        ),
    },
    "syn_v2_prohibited_action_02": {
        "assessment": "direct_unconditional_action_prohibition",
        "eligibility": "eligible_for_new_v1_semantics",
        "reason": (
            "Same source semantics as 01.  Historical action extraction is not "
            "the executable prohibited action and must not be treated as a "
            "valid binding under the new exact-canonical mechanism contract."
        ),
    },
    "syn_v2_prohibited_action_03": {
        "assessment": "rule_applicability",
        "eligibility": "not_applicable",
        "reason": "Paragraph 1 shall not apply if ... is rule applicability, not a process-action prohibition.",
    },
    "syn_v2_prohibited_action_04": {
        "assessment": "rule_applicability",
        "eligibility": "not_applicable",
        "reason": "Same rule-applicability construction as 03; 'apply' is not an executable process action here.",
    },
    "syn_v2_prohibited_action_05": {
        "assessment": "legal_effect_or_state",
        "eligibility": "not_applicable",
        "reason": "'shall not be binding' is a legal effect/state, not an executable process-action prohibition.",
    },
    "syn_v2_prohibited_action_06": {
        "assessment": "legal_effect_or_state",
        "eligibility": "not_applicable",
        "reason": "Same legal-effect/state construction as 05.",
    },
    "syn_v2_prohibited_action_07": {
        "assessment": "legal_effect_or_state",
        "eligibility": "not_applicable",
        "reason": "The sentence concerns the legal effect of withdrawal on prior lawfulness, not an executable action prohibition.",
    },
    "syn_v2_prohibited_action_08": {
        "assessment": "legal_effect_or_state",
        "eligibility": "not_applicable",
        "reason": "The sentence concerns the legal effect of the right to obtain a copy on the rights of others.",
    },
    "syn_v2_prohibited_action_09": {
        "assessment": "rule_applicability",
        "eligibility": "not_applicable",
        "reason": "That right shall not apply ... is legal rule applicability, not an executable process action.",
    },
    "syn_v2_prohibited_action_10": {
        "assessment": "rule_applicability",
        "eligibility": "not_applicable",
        "reason": "Paragraphs 1 and 2 shall not apply ... is legal rule applicability, not an executable process action.",
    },
}
for _idx in ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10"):
    SEMANTIC_AUDIT[f"syn_v2_required_condition_{_idx}"] = {
        "assessment": "trigger_obligation_C_implies_OA",
        "eligibility": "not_applicable",
        "reason": "The condition triggers or qualifies an obligation/right; it is not the necessary-precondition relation A only if C.",
    }


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(value), encoding="utf-8", newline="\n")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _process_summary(record: Mapping[str, Any]) -> dict[str, Any]:
    activities = list(record.get("activities") or [])
    gateways = list(record.get("gateways") or [])
    events = list(record.get("events") or [])
    flows = list(record.get("sequence_flows") or [])
    control = dict(record.get("control_flow") or {})
    return {
        "source_sha256": (record.get("source") or {}).get("sha256"),
        "activity_count": len(activities),
        "activity_labels": sorted({a.get("name") or "" for a in activities}),
        "gateway_count": len(gateways),
        "gateway_types": sorted({g.get("type") for g in gateways}),
        "event_count": len(events),
        "sequence_flow_count": len(flows),
        "condition_expression_flow_count": sum(1 for f in flows if f.get("condition_expression")),
        "named_flow_count": sum(1 for f in flows if f.get("name")),
        "default_flow_count": sum(1 for f in flows if f.get("is_default")),
        "start_event_ids": list(control.get("start_event_ids") or []),
        "end_event_ids": list(control.get("end_event_ids") or []),
        "unreachable_node_ids": list(control.get("unreachable_node_ids") or []),
        "cycle_detected": bool(control.get("cycle_detected")),
        "parallel_gateway_ids": list(control.get("parallel_gateway_ids") or []),
    }


def _target_check(row: Mapping[str, Any], target_type: str) -> dict[str, Any]:
    checks = row.get("checks") or {}
    check = checks.get(target_type) or {}
    decision = row.get("decision") or {}
    return {
        "status": check.get("status"),
        "observable": check.get("observable"),
        "violation": check.get("violation"),
        "reason": check.get("reason"),
        "score": check.get("score"),
        "overall_decision": decision.get("decision"),
        "overall_predicted": decision.get("predicted"),
    }


def build_legacy_disposition() -> dict[str, Any]:
    panel = _load_json(LEGACY_PANEL)
    predictions = {
        (row.get("item_id"), row.get("side")): row
        for row in _load_jsonl(V5_PREDICTIONS)
    }
    contract = load_stage1_contract(STAGE1_CONTRACT)
    items: list[dict[str, Any]] = []
    for variant in sorted(panel.get("variants") or [], key=lambda x: x.get("variant_id", "")):
        target = variant.get("mutation_type")
        if target not in LEGACY_TARGETS:
            continue
        item_id = variant["variant_id"]
        audit = SEMANTIC_AUDIT.get(item_id)
        if not audit:
            raise ValueError(f"missing semantic audit for {item_id}")
        rule_element = variant.get("rule_element") or {}
        control_record = parse_bpmn_file(ROOT / variant["control_bpmn"], contract=contract)
        variant_record = parse_bpmn_file(ROOT / variant["variant_bpmn"], contract=contract)
        item = {
            "historical_item_id": item_id,
            "source_sentence": rule_element.get("sentence_text"),
            "historical_extracted_modality_action_condition": {
                "modality": rule_element.get("modality"),
                "action": rule_element.get("action"),
                "condition": rule_element.get("condition"),
                "constraint": rule_element.get("constraint"),
                "exception": rule_element.get("exception"),
            },
            "historical_target_type": target,
            "semantic_relation_assessment": audit["assessment"],
            "new_v1_eligibility": audit["eligibility"],
            "ineligible_or_unsupported_reason": audit["reason"],
            "bpmn_relevant_structure_summary": {
                "control": _process_summary(control_record),
                "variant": _process_summary(variant_record),
            },
            "historical_v5_decision": {
                "variant": _target_check(predictions.get((item_id, "variant"), {}), target),
                "control": _target_check(predictions.get((item_id, "control"), {}), target),
            },
            "reviewer_identity": REVIEWER_IDENTITY,
            "not_human_gold": True,
        }
        items.append(item)

    assessment_counts: dict[str, int] = {}
    eligibility_counts: dict[str, int] = {}
    target_counts: dict[str, int] = {}
    for item in items:
        assessment_counts[item["semantic_relation_assessment"]] = assessment_counts.get(item["semantic_relation_assessment"], 0) + 1
        eligibility_counts[item["new_v1_eligibility"]] = eligibility_counts.get(item["new_v1_eligibility"], 0) + 1
        target_counts[item["historical_target_type"]] = target_counts.get(item["historical_target_type"], 0) + 1

    result = {
        "schema_version": "s3_ext_pc_v1_legacy_semantic_disposition@1.0.0",
        "revision": "s3_ext_pc_v1",
        "status": "development_only_semantic_audit",
        "scope": "read_only_review_of_20_historical_pair_families",
        "source_panel": {
            "path": LEGACY_PANEL.relative_to(ROOT).as_posix(),
            "sha256": _sha256_file(LEGACY_PANEL),
            "historical_item_count": len(items),
            "target_types": list(LEGACY_TARGETS),
        },
        "historical_v5_predictions_read_only": {
            "path": V5_PREDICTIONS.relative_to(ROOT).as_posix(),
            "sha256": _sha256_file(V5_PREDICTIONS),
        },
        "assessment_value_vocabulary": [
            "direct_unconditional_action_prohibition",
            "conditional_action_prohibition",
            "permission",
            "absence_of_obligation",
            "rule_applicability",
            "legal_effect_or_state",
            "trigger_obligation_C_implies_OA",
            "necessary_precondition_A_implies_C",
            "ambiguous",
            "other",
        ],
        "new_v1_eligibility_value_vocabulary": [
            "eligible_for_new_v1_semantics",
            "not_applicable",
            "unsupported",
        ],
        "summary": {
            "total": len(items),
            "historical_target_counts": target_counts,
            "semantic_relation_assessment_counts": assessment_counts,
            "new_v1_eligibility_counts": eligibility_counts,
            "eligible_for_new_v1_semantics_but_requiring_canonical_action_rebinding": sum(
                1 for item in items
                if item["new_v1_eligibility"] == "eligible_for_new_v1_semantics"
            ),
            "old_required_condition_pairs_reused": 0,
        },
        "items": items,
        "review_boundary": {
            "reviewer_identity": REVIEWER_IDENTITY,
            "not_human_gold": True,
            "historical_files_modified": False,
            "historical_labels_rewritten": False,
            "gold_created": False,
            "api_calls": 0,
            "network_experiment_calls": 0,
            "note": (
                "This file records a new AI semantic audit only.  It does not "
                "modify synthetic_controlled_error_extension_v2.json, does not "
                "re-label old expected labels, and does not establish new Gold."
            ),
        },
    }
    return result


def _write_legacy_disposition() -> str:
    result = build_legacy_disposition()
    _write_json(LEGACY_DISPOSITION, result)
    return _sha256_file(LEGACY_DISPOSITION)


def _check_legacy_disposition() -> None:
    if not LEGACY_DISPOSITION.exists():
        raise SystemExit(f"missing {LEGACY_DISPOSITION}")
    expected = build_legacy_disposition()
    actual = _load_json(LEGACY_DISPOSITION)
    if actual != expected:
        raise SystemExit("legacy_semantic_disposition_v1.json is not reproducible/current")
    print("legacy disposition check: OK")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--legacy-disposition", action="store_true", help="build the Phase A legacy semantic disposition")
    group.add_argument("--check", action="store_true", help="recompute the Phase A disposition and compare byte-semantically")
    args = parser.parse_args(argv)

    if args.check:
        _check_legacy_disposition()
        return 0

    digest = _write_legacy_disposition()
    print(f"wrote {LEGACY_DISPOSITION.relative_to(ROOT).as_posix()} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
