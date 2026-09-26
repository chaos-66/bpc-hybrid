# -*- coding: utf-8 -*-
"""Independent evaluator for the bounded S3.9-EXT-PC-V1 mechanism diagnosis.

The evaluator refuses to read expected/pair/side metadata until the prediction
freeze file has been hash-verified against the persisted prediction bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.s3_ext_pc_v1 import (  # noqa: E402
    bind_action,
    bind_condition_edges,
    normalize_action,
    normalize_condition,
)
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file  # noqa: E402

MECH_DIR = ROOT / "data/development/stage3_ext_pc_v1"
MANIFEST = MECH_DIR / "mechanism_case_manifest_v1.json"
INFERENCE_VIEW = MECH_DIR / "inference_view_v1.json"
LEGACY_DISPOSITION = MECH_DIR / "legacy_semantic_disposition_v1.json"
PREDICTION_FREEZE = ROOT / "outputs/development/s3_ext_pc_v1/prediction_freeze_v1.json"
PREDICTIONS = ROOT / "outputs/development/s3_ext_pc_v1/predictions.jsonl"
REPORT_JSON = ROOT / "outputs/reports/s3_ext_pc_v1.json"
REPORT_MD = ROOT / "outputs/reports/s3_ext_pc_v1.md"
REPORT_MANIFEST = ROOT / "outputs/reports/s3_ext_pc_v1.manifest.json"
STAGE1_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
GDPR7_BPMN_DIR = ROOT / "data/input/stage1_stage3/gdpr7"
GDPR7_INPUT = ROOT / "data/input/gdpr7_stage2_input_v1.json"
DIRECT_PREDICTIONS = ROOT / "data/predictions/gdpr7_direct_llm_v1/predictions.json"
RULE_ONLY_PREDICTIONS = ROOT / "data/predictions/gdpr7_sun_rule_only_v1/predictions.json"
FAILURE_CHAINS = ROOT / "outputs/evidence/s3_semantic_grounding_v5/constraint_exception_failure_chains.json"


class PredictionFreezeError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_frozen_predictions(predictions_path: Path, freeze_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read predictions only after exact hash verification against the freeze."""

    if not freeze_path.exists():
        raise PredictionFreezeError("prediction freeze file missing")
    freeze = _load_json(freeze_path)
    if freeze.get("status") != "PREDICTIONS_FROZEN_BEFORE_EVALUATION":
        raise PredictionFreezeError("prediction freeze status is not frozen")
    if not predictions_path.exists():
        raise PredictionFreezeError("prediction file missing")
    actual = _sha256_file(predictions_path)
    if actual != freeze.get("prediction_sha256"):
        raise PredictionFreezeError("prediction hash mismatch")
    return _load_jsonl(predictions_path), freeze


def load_targets_after_prediction_freeze(
    predictions_path: Path,
    freeze_path: Path,
    manifest_loader: Callable[[], Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], Mapping[str, Any]]:
    """Ordering helper used by tests: hash first, expected targets second."""

    rows, freeze = load_frozen_predictions(predictions_path, freeze_path)
    manifest = manifest_loader()
    return rows, freeze, manifest


def _p_r_f1(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = (tp / (tp + fp)) if (tp + fp) else None
    recall = (tp / (tp + fn)) if (tp + fn) else None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = None
    return {"precision": precision, "recall": recall, "f1": f1}


def compute_mechanism_metrics(manifest: Mapping[str, Any],
                              predictions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pred_by_id = {row["object_id"]: row for row in predictions}
    objects = list(manifest.get("objects") or [])
    by_family: dict[str, dict[str, Any]] = {}
    failed_cases: list[dict[str, Any]] = []
    all_decided = 0
    all_eligible = 0
    total_pair_success = 0

    for family in ("prohibition", "necessary_precondition"):
        family_objects = [obj for obj in objects if obj.get("family") == family and obj.get("kind") == "pair_member"]
        variants = [obj for obj in family_objects if obj.get("side") == "variant"]
        controls = [obj for obj in family_objects if obj.get("side") == "control"]
        tp = fp = tn = fnobs = fnunknown = negunknown = 0
        for obj in variants:
            pred = pred_by_id.get(obj["object_id"], {})
            decision = pred.get("decision")
            if decision == "violation":
                tp += 1
            elif decision == "satisfied":
                fnobs += 1
                failed_cases.append(_failed_case(obj, pred))
            elif decision == "unknown":
                fnunknown += 1
                failed_cases.append(_failed_case(obj, pred))
            else:
                failed_cases.append(_failed_case(obj, pred))
        for obj in controls:
            pred = pred_by_id.get(obj["object_id"], {})
            decision = pred.get("decision")
            if decision == "satisfied":
                tn += 1
            elif decision == "violation":
                fp += 1
                failed_cases.append(_failed_case(obj, pred))
            elif decision == "unknown":
                negunknown += 1
                failed_cases.append(_failed_case(obj, pred))
            else:
                failed_cases.append(_failed_case(obj, pred))
        positives = len(variants)
        negatives = len(controls)
        eligible = positives + negatives
        decided = tp + fnobs + tn + fp
        all_decided += decided
        all_eligible += eligible
        metrics = _p_r_f1(tp, fp, fnobs + fnunknown)
        # Pair success follows the task definition exactly.
        pair_ids = {obj.get("pair_id") for obj in family_objects if obj.get("pair_id")}
        pair_success = 0
        for pair_id in sorted(pair_ids):
            var = next((obj for obj in variants if obj.get("pair_id") == pair_id), None)
            ctrl = next((obj for obj in controls if obj.get("pair_id") == pair_id), None)
            if not var or not ctrl:
                continue
            if (pred_by_id.get(var["object_id"], {}).get("decision") == "violation"
                    and pred_by_id.get(ctrl["object_id"], {}).get("decision") == "satisfied"):
                pair_success += 1
        total_pair_success += pair_success
        by_family[family] = {
            "positive": {
                "total": positives,
                "tp": tp,
                "fn_observed_negative": fnobs,
                "fn_unknown": fnunknown,
            },
            "negative": {
                "total": negatives,
                "tn": tn,
                "fp": fp,
                "negative_unknown": negunknown,
            },
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "coverage": (decided / eligible) if eligible else None,
            "decided": decided,
            "eligible": eligible,
            "positive_unknown_rate": (fnunknown / positives) if positives else None,
            "negative_unknown_rate": (negunknown / negatives) if negatives else None,
            "pair_success": pair_success,
            "pair_total": len(pair_ids),
            "all_denominators": {
                "positive_total": positives,
                "negative_total": negatives,
                "precision_denominator_tp_plus_fp": tp + fp,
                "recall_denominator_positive_total": positives,
                "coverage_denominator_eligible_sides": eligible,
            },
        }

    return {
        "by_family": by_family,
        "overall": {
            "pair_success": total_pair_success,
            "pair_total": 10,
            "pair_success_rate": total_pair_success / 10,
            "coverage": (all_decided / all_eligible) if all_eligible else None,
            "eligible_sides": all_eligible,
            "decided_sides": all_decided,
            "positive_unknown_count": sum(v["positive"]["fn_unknown"] for v in by_family.values()),
            "positive_total": sum(v["positive"]["total"] for v in by_family.values()),
            "negative_unknown_count": sum(v["negative"]["negative_unknown"] for v in by_family.values()),
            "negative_total": sum(v["negative"]["total"] for v in by_family.values()),
        },
        "failed_or_nonideal_cases": failed_cases,
    }


def _failed_case(obj: Mapping[str, Any], pred: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "object_id": obj["object_id"],
        "case_id": obj.get("case_id"),
        "family": obj.get("family"),
        "side": obj.get("side"),
        "expected_applicability": obj.get("expected_applicability"),
        "expected_decision": obj.get("expected_decision"),
        "actual_applicability": pred.get("applicability"),
        "actual_decision": pred.get("decision"),
        "actual_reason": pred.get("reason"),
        "semantic_subtype": pred.get("semantic_subtype"),
        "evidence": pred.get("evidence"),
    }


def evaluate_counterexamples(manifest: Mapping[str, Any],
                             predictions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    pred_by_id = {row["object_id"]: row for row in predictions}
    results = []
    for obj in manifest.get("objects") or []:
        if obj.get("kind") != "counterexample":
            continue
        pred = pred_by_id.get(obj["object_id"], {})
        expected_status = obj.get("expected_decision")
        actual_applicability = pred.get("applicability")
        actual_decision = pred.get("decision")
        if expected_status in {"not_applicable", "unsupported"}:
            matched = actual_applicability == expected_status and actual_decision is None
            actual_status = actual_applicability
        else:
            matched = actual_decision == expected_status
            actual_status = actual_decision
        results.append({
            "object_id": obj["object_id"],
            "case_id": obj.get("case_id"),
            "expected": expected_status,
            "actual_applicability": actual_applicability,
            "actual_decision": actual_decision,
            "actual_status": actual_status,
            "matched": matched,
            "reason": pred.get("reason"),
            "semantic_subtype": pred.get("semantic_subtype"),
        })
    return results


# ---------------------------------------------------------------------------
# Existing real-extraction linkage diagnosis (Table B)
# ---------------------------------------------------------------------------

REL_PROHIBITION = "direct_unconditional_action_prohibition"
REL_NECESSARY = "necessary_precondition"
REL_TRIGGER = "trigger_obligation_C_implies_OA"


def _source_sentence_map() -> dict[str, str]:
    data = _load_json(GDPR7_INPUT)
    mapping = {}
    for rule in data.get("rules") or []:
        for sentence in rule.get("sentences") or []:
            mapping[sentence["sample_id"]] = sentence["approved_text_en"]
    return mapping


def _method_record_map(path: Path) -> dict[str, Mapping[str, Any]]:
    data = _load_json(path)
    return {row["sample_id"]: row for row in data.get("records") or []}


def _span_texts(source_text: str, spans: Any) -> list[str]:
    texts = []
    if not isinstance(spans, list):
        return texts
    for span in spans:
        if not isinstance(span, Mapping):
            continue
        start = span.get("start")
        end = span.get("end")
        if isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= len(source_text):
            texts.append(source_text[start:end])
    return texts


def _clauses_for_sample(record: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not record or record.get("request_status") != "ok":
        return []
    inner = record.get("record") or {}
    clauses = inner.get("clauses") or []
    return [clause for clause in clauses if isinstance(clause, Mapping)]


def _gdpr7_activity_labels() -> set[str]:
    contract = load_stage1_contract(STAGE1_CONTRACT)
    labels: set[str] = set()
    for path in sorted(GDPR7_BPMN_DIR.glob("*.bpmn")):
        try:
            record = parse_bpmn_file(path, contract=contract)
        except Exception:
            continue
        for activity in record.get("activities") or []:
            labels.add(normalize_action(activity.get("name") or ""))
    labels.discard("")
    return labels


def _projection_for_ref(ref: str, source_text: str) -> str:
    lowered = source_text.casefold()
    if "only if" in lowered or "only when" in lowered:
        return "necessary_precondition_conservative_projection"
    if ref == "gdpr_article33_s001":
        return "trigger_obligation_not_necessary_precondition"
    if ref in {"gdpr_article22_s002", "gdpr_article17_s009", "gdpr_article20_s004"}:
        return "rule_applicability_not_necessary_precondition"
    if ref == "gdpr_article7_s003":
        return "legal_effect_or_state_not_necessary_precondition"
    if ref == "gdpr_article22_s001":
        return "right_or_prohibition_ambiguous_not_v1_direct"
    return "not_necessary_precondition"


def build_real_linkage_diagnosis() -> dict[str, Any]:
    view = _load_json(INFERENCE_VIEW)
    source_map = _source_sentence_map()
    direct = _method_record_map(DIRECT_PREDICTIONS)
    rule_only = _method_record_map(RULE_ONLY_PREDICTIONS)
    activity_labels = _gdpr7_activity_labels()
    refs = sorted({
        obj.get("rule_spec", {}).get("source_clause_ref")
        for obj in view.get("objects") or []
        if obj.get("rule_spec", {}).get("source_clause_ref") not in {None, "AI_constructed"}
        and not str(obj.get("rule_spec", {}).get("source_clause_ref")).startswith("AI_constructed")
    })
    rows = []
    for ref in refs:
        source_text = source_map.get(ref)
        if not source_text:
            rows.append({"source_clause_ref": ref, "status": "missing_existing_source_sentence", "methods": []})
            continue
        projection = _projection_for_ref(ref, source_text)
        method_rows = []
        for method_name, records in (("direct_llm", direct), ("sun_rule_only", rule_only)):
            record = records.get(ref)
            clauses = _clauses_for_sample(record)
            action_spans: list[str] = []
            condition_spans: list[str] = []
            constraint_spans: list[str] = []
            exception_spans: list[str] = []
            modality_labels: list[str] = []
            for clause in clauses:
                modality = clause.get("modality") or {}
                if isinstance(modality, Mapping) and modality.get("label"):
                    modality_labels.append(str(modality["label"]))
                action_spans.extend(_span_texts(source_text, clause.get("actions")))
                condition_spans.extend(_span_texts(source_text, clause.get("conditions")))
                constraint_spans.extend(_span_texts(source_text, clause.get("constraints")))
                exception_spans.extend(_span_texts(source_text, clause.get("exceptions")))
            action_binding_status = "missing_existing_prediction"
            if record is not None:
                if not action_spans:
                    action_binding_status = "action_span_missing"
                elif any(normalize_action(text) in activity_labels for text in action_spans):
                    action_binding_status = "bound_exact_normalized_to_a_gdpr7_activity"
                else:
                    action_binding_status = "unresolved_no_exact_normalized_gdpr7_activity"
            condition_binding_status = "condition_span_missing"
            if condition_spans:
                condition_binding_status = "not_attempted_without_full_process_rule_linkage"
            if projection == "necessary_precondition_conservative_projection":
                if record is None:
                    checker_decision = "unknown"
                    checker_reason = "missing_existing_prediction"
                elif not action_spans:
                    checker_decision = "unknown"
                    checker_reason = "action_span_missing"
                elif action_binding_status != "bound_exact_normalized_to_a_gdpr7_activity":
                    checker_decision = "unknown"
                    checker_reason = "action_binding_unresolved_or_ambiguous"
                elif not condition_spans:
                    checker_decision = "unknown"
                    checker_reason = "representation_insufficiency_condition_span_missing"
                else:
                    checker_decision = "unknown"
                    checker_reason = "representation_insufficiency_relation_direction_not_encoded"
            else:
                checker_decision = "not_applicable"
                checker_reason = projection
            method_rows.append({
                "method": method_name,
                "prediction_available": record is not None and record.get("request_status") == "ok",
                "request_status": None if record is None else record.get("request_status"),
                "modality_labels": sorted(set(modality_labels)),
                "has_prohibition_modality": "prohibition" in modality_labels,
                "action_spans": sorted(set(action_spans)),
                "condition_spans": sorted(set(condition_spans)),
                "constraint_spans": sorted(set(constraint_spans)),
                "exception_spans": sorted(set(exception_spans)),
                "action_binding_status": action_binding_status,
                "condition_binding_status": condition_binding_status,
                "relation_projection": projection,
                "checker_decision": checker_decision,
                "checker_reason": checker_reason,
            })
        rows.append({
            "source_clause_ref": ref,
            "source_text": source_text,
            "relation_projection": projection,
            "methods": method_rows,
        })
    return {
        "scope": "existing real Stage2 prediction linkage diagnosis; not a new method comparison",
        "note": "No API, no LLM, no new prediction. Missing predictions are reported as missing_existing_prediction.",
        "direct_llm_predictions_sha256": _sha256_file(DIRECT_PREDICTIONS),
        "sun_rule_only_predictions_sha256": _sha256_file(RULE_ONLY_PREDICTIONS),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Constraint / exception boundary analysis
# ---------------------------------------------------------------------------

def build_boundary_analysis() -> dict[str, Any]:
    chains = _load_json(FAILURE_CHAINS)
    return {
        "source": FAILURE_CHAINS.relative_to(ROOT).as_posix(),
        "constraint_chain": {
            "historical_item": chains.get("constraint", {}).get("item_id"),
            "side": chains.get("constraint", {}).get("side"),
            "six_categories": {
                "extraction_error": "not the primary cause in this chain; the rule fields contain an explicit 72-hour constraint",
                "mapping_error": "verified: the action grounder bound 'notify the personal data breach' to the exception-handler node",
                "representation_insufficiency": "the six-element Rule Record does not encode the temporal anchor/origin of the 72-hour clock",
                "process_information_missing": "ordinary BPMN task order/text does not prove whether the clock starts at breach occurrence, discovery, awareness, or internal case opening",
                "decision_semantics_error": "the old checker treated absence of a time bound on the wrongly anchored node as a violation; v5 guard demoted this to unknown",
                "evaluation_limitation": "deadline compliance cannot be established from this process slice without start-event/time semantics",
            },
            "correct_interpretation": "mapping error plus decision-guard repair; not evidence that the LLM cannot perform temporal reasoning.",
            "constraint_heterogeneity": [
                "time", "amount", "quantity", "purpose", "legal_reference",
            ],
            "heterogeneity_statement": "These are different predicates; a single similarity formula is not claimed to solve all constraints.",
        },
        "exception_chain": {
            "historical_item": chains.get("exception", {}).get("item_id"),
            "side": chains.get("exception", {}).get("side"),
            "logical_warning": "E -> not O(A) does not entail E -> FORBID(A); voluntarily performing A while E holds is not automatically a violation.",
            "requires": [
                "whether E holds",
                "which obligation E targets",
                "its effect on the path",
                "priority relations with other rules",
            ],
            "six_categories": {
                "extraction_error": "the historical action 'referred to' is not an executable activity label",
                "mapping_error": "the matcher could not bind 'referred to' to the process activity 'Communication with data subject'",
                "representation_insufficiency": "the Rule Record does not encode exception scope, priority, or obligation target",
                "process_information_missing": "no dedicated handler structure was present in the frozen process",
                "decision_semantics_error": "absence of a matched handler must not be promoted to a violation without actionable exception semantics",
                "evaluation_limitation": "current process and schema cannot support a determinate exception verdict",
            },
            "conclusion": "This is a joint extraction/representation/mapping issue, not an 'LLM cannot reason' claim or a general unobservability excuse.",
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# S3.9-EXT-PC-V1 bounded mechanism diagnosis")
    lines.append("")
    lines.append("**Status:** development-only AI-constructed mechanism evidence; not a formal benchmark, unseen test, or human Gold.")
    lines.append("")
    lines.append("## Semantics")
    lines.append("")
    lines.append("- Prohibition v1: `FORBID(A)`; violation iff A is an executable activity reachable from a start node.")
    lines.append("- Necessary-precondition v1: `A only if C`; violation iff A remains reachable after removing all C-enforcing sequence-flow edges.")
    lines.append("- Legacy target name `required_condition_not_enforced` is retained only as a compatibility field; the semantic subtype is `necessary_precondition_bypass_v1`.")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append("| Family | Pos TP | Pos FN-observed | Pos FN-unknown | Neg TN | Neg FP | Neg unknown | Precision | Recall | F1 | Coverage | Pair success |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for family, metrics in report["mechanism_metrics"]["by_family"].items():
        def fmt(value: Any) -> str:
            return "null" if value is None else (f"{value:.4f}" if isinstance(value, float) else str(value))
        lines.append(
            f"| {family} | {metrics['positive']['tp']} | {metrics['positive']['fn_observed_negative']} | "
            f"{metrics['positive']['fn_unknown']} | {metrics['negative']['tn']} | {metrics['negative']['fp']} | "
            f"{metrics['negative']['negative_unknown']} | {fmt(metrics['precision'])} | {fmt(metrics['recall'])} | "
            f"{fmt(metrics['f1'])} | {fmt(metrics['coverage'])} | {metrics['pair_success']}/{metrics['pair_total']} |"
        )
    overall = report["mechanism_metrics"]["overall"]
    lines.append("")
    lines.append(f"- 10-pair total pair success: **{overall['pair_success']}/{overall['pair_total']}**")
    lines.append(f"- Overall coverage: **{overall['coverage']}**")
    lines.append(f"- Positive unknown: **{overall['positive_unknown_count']}/{overall['positive_total']}**")
    lines.append(f"- Negative unknown: **{overall['negative_unknown_count']}/{overall['negative_total']}**")
    lines.append("")
    lines.append("## Counterexamples (non-scoring)")
    lines.append("")
    lines.append("| Case | Expected | Actual applicability | Actual decision | Matched | Reason |")
    lines.append("|---|---|---|---|---|---|")
    for row in report["counterexamples"]:
        lines.append(f"| {row['case_id']} | {row['expected']} | {row['actual_applicability']} | {row['actual_decision']} | {row['matched']} | {row['reason']} |")
    lines.append("")
    lines.append("## Failure / unknown cases")
    lines.append("")
    if not report["mechanism_metrics"]["failed_or_nonideal_cases"]:
        lines.append("- none")
    for row in report["mechanism_metrics"]["failed_or_nonideal_cases"]:
        lines.append(f"- `{row['object_id']}` ({row['side']}): expected {row['expected_decision']}, got {row['actual_decision']} / {row['actual_reason']}")
    lines.append("")
    lines.append("## Legacy 20-case semantic disposition")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(report["legacy_disposition_summary"], ensure_ascii=False, indent=2, sort_keys=True))
    lines.append("```")
    lines.append("")
    lines.append("## Existing real extraction linkage (Table B)")
    lines.append("")
    lines.append("Separate from the mechanism table; no new API calls and no overall method ranking.")
    for row in report["real_extraction_linkage"]["rows"]:
        lines.append(f"- `{row['source_clause_ref']}`: projection `{row['relation_projection']}`")
        for method in row.get("methods", []):
            lines.append(
                f"  - {method['method']}: modality={method['modality_labels']}, "
                f"action_binding={method['action_binding_status']}, checker={method['checker_decision']} ({method['checker_reason']})"
            )
    lines.append("")
    lines.append("## Constraint / exception capability boundary")
    lines.append("")
    lines.append(json.dumps(report["constraint_exception_boundary"], ensure_ascii=False, indent=2, sort_keys=True))
    lines.append("")
    lines.append("## Paper method material and limitations")
    lines.append("")
    lines.append(json.dumps(report["paper_method_material"], ensure_ascii=False, indent=2, sort_keys=True))
    lines.append("")
    lines.append("## Isolation and safety")
    lines.append("")
    lines.append(f"- real_api_calls={report['safety']['real_api_calls']}")
    lines.append(f"- network_experiment_calls={report['safety']['network_experiment_calls']}")
    lines.append(f"- gold_status={report['safety']['gold_status']}")
    lines.append("- Main paper-facing Table 3, Table 1 and Table 2 are unchanged by this task.")
    lines.append("")
    return "\n".join(lines)


def build_report() -> dict[str, Any]:
    predictions, freeze = load_frozen_predictions(PREDICTIONS, PREDICTION_FREEZE)
    manifest = _load_json(MANIFEST)
    metrics = compute_mechanism_metrics(manifest, predictions)
    counterexamples = evaluate_counterexamples(manifest, predictions)
    legacy = _load_json(LEGACY_DISPOSITION)
    real_linkage = build_real_linkage_diagnosis()
    boundary = build_boundary_analysis()
    inference_sha = _sha256_file(INFERENCE_VIEW)
    if inference_sha != freeze.get("input_binding", {}).get("inference_view_sha256"):
        raise PredictionFreezeError("inference-view hash mismatch after prediction freeze")
    report = {
        "schema_version": "s3_ext_pc_v1_report@1.0.0",
        "revision": "s3_ext_pc_v1",
        "status": "DEVELOPMENT_MECHANISM_EVIDENCE",
        "development_only": True,
        "not_formal_benchmark": True,
        "not_unseen_test": True,
        "not_human_gold": True,
        "semantic_definitions": {
            "direct_unconditional_action_prohibition_v1": "FORBID(A); violation iff an executable action activity bound to A is reachable from a start node.",
            "necessary_precondition_bypass_v1": "A only if C; remove all C-enforcing sequence-flow edges E_C and test reachability of A.",
            "legacy_target_type": "required_condition_not_enforced",
            "semantic_subtype": "necessary_precondition_bypass_v1",
        },
        "supported_bpmn_fragment": _load_json(MECH_DIR / "mechanism_plan_v1.json")["supported_bpmn_fragment"],
        "mechanism_metrics": metrics,
        "counterexamples": counterexamples,
        "legacy_disposition_summary": legacy.get("summary"),
        "real_extraction_linkage": real_linkage,
        "constraint_exception_boundary": boundary,
        "paper_method_material": {
            "bounded_semantic_definition": "Direct unconditional prohibition over reachable executable BPMN activities; necessary precondition bypass by sequence-flow enforcement edges.",
            "formula": "V_proh = exists a in B_A: Reach_G(S,a); bypass = Reach_G_without_E_C(S,a).",
            "supported_fragment": "flat, acyclic BPMN fragment with start/end events, executable activities, sequence flows, XOR gateways and explicit conditionExpression / guarded flow labels.",
            "mechanism_result": metrics,
            "failure_example": next((row for row in metrics["failed_or_nonideal_cases"]), None),
            "limitation_statement": "This is development evidence on AI-constructed mechanism cases; it does not establish generalization to unseen legal text or full BPMN semantics.",
            "cannot_claim": [
                "our method generalizes",
                "formal benchmark proves",
                "outperforms Sun",
                "outperforms Winter",
                "first to",
                "new five-type Table 3",
            ],
        },
        "execution_binding": {
            "prediction_freeze": freeze,
            "inference_view_sha256": inference_sha,
            "case_manifest_sha256": _sha256_file(MANIFEST),
        },
        "safety": {
            "real_api_calls": 0,
            "network_experiment_calls": 0,
            "gold_status": "AI_constructed_development_not_gold",
            "main_paper_facing_table3_unchanged": True,
            "table1_unchanged": True,
            "table2_unchanged": True,
        },
        "limitations": [
            "AI-constructed development material; not human Gold and not an independent generalization benchmark.",
            "Mechanism RuleSpecs are ideal structured inputs; results cannot be attributed to Direct-LLM extraction performance.",
            "Real-extraction linkage is diagnostic only and preserves missing_existing_prediction where applicable.",
            "No constraint or exception checker is implemented in this task.",
            "No conditional prohibition, loop, subprocess, AND/inclusive gateway, event-state, or dynamic data-state semantics are supported.",
        ],
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify frozen predictions and regenerate report deterministically")
    args = parser.parse_args(argv)
    report = build_report()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    report_text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    md_text = render_markdown(report)
    if args.check:
        if not REPORT_JSON.exists() or not REPORT_MD.exists():
            raise SystemExit("report files missing")
        if REPORT_JSON.read_text(encoding="utf-8") != report_text:
            raise SystemExit("report JSON is not reproducible")
        if REPORT_MD.read_text(encoding="utf-8") != md_text:
            raise SystemExit("report Markdown is not reproducible")
        print("report check: OK")
        return 0
    REPORT_JSON.write_text(report_text, encoding="utf-8", newline="\n")
    REPORT_MD.write_text(md_text, encoding="utf-8", newline="\n")
    manifest = {
        "schema_version": "s3_ext_pc_v1_report_manifest@1.0.0",
        "revision": "s3_ext_pc_v1",
        "status": "development_only",
        "report_json": REPORT_JSON.relative_to(ROOT).as_posix(),
        "report_json_sha256": _sha256_file(REPORT_JSON),
        "report_md": REPORT_MD.relative_to(ROOT).as_posix(),
        "report_md_sha256": _sha256_file(REPORT_MD),
        "prediction_freeze_sha256": _sha256_file(PREDICTION_FREEZE),
        "prediction_sha256": _sha256_file(PREDICTIONS),
        "evaluator_sha256": _sha256_file(Path(__file__).resolve()),
        "real_api_calls": 0,
        "network_experiment_calls": 0,
        "gold_status": "AI_constructed_development_not_gold",
    }
    REPORT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"report_json": manifest["report_json"], "report_json_sha256": manifest["report_json_sha256"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
