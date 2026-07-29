"""Unified offline S1.6 structural and label-semantics evaluator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.stage1_label_semantics import validate_label_semantics
from bpc_hybrid.stage1_process import sha256_file, validate_process_record


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_VERSION = "stage1_evaluator_contract@1.0.0"
REPORT_VERSION = "stage1_evaluation_report@1.0.0"
METHODS = ("P0", "P1")
STRUCTURE_COMPONENTS = (
    "pools",
    "lanes",
    "activities",
    "events",
    "gateways",
    "sequence_flows",
    "direct_edges",
    "activity_order_relations",
)
SEMANTIC_FIELDS = ("actor", "action", "business_object")


class Stage1EvaluationError(ValueError):
    """Raised when the S1.6 evaluator contract fails closed."""


@dataclass(frozen=True)
class ReportValidation:
    valid: bool
    errors: tuple[str, ...]


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage1EvaluationError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1EvaluationError(f"{label} root must be an object")
    return value


def load_evaluator_contract(path: Path) -> dict[str, Any]:
    contract = _load_json(path, "S1.6 evaluator contract")
    if (
        contract.get("schema_version") != CONTRACT_VERSION
        or contract.get("task_ids") != ["S1.6"]
        or contract.get("status")
        != "verified_offline_evaluator_contract_pending_formal_membership_and_gold"
    ):
        raise Stage1EvaluationError("S1.6 contract identity changed")
    schema = contract.get("report_schema", {})
    schema_path = _project_path(str(schema.get("path", "")))
    if (
        schema.get("schema_version") != REPORT_VERSION
        or not schema_path.is_file()
        or sha256_file(schema_path) != schema.get("sha256")
    ):
        raise Stage1EvaluationError("S1.6 report schema binding changed")
    if tuple(contract.get("methods", ())) != METHODS:
        raise Stage1EvaluationError("S1.6 method set changed")
    if tuple(contract.get("structure_components", ())) != STRUCTURE_COMPONENTS:
        raise Stage1EvaluationError("S1.6 structure component set changed")
    if tuple(contract.get("semantic_fields", ())) != SEMANTIC_FIELDS:
        raise Stage1EvaluationError("S1.6 semantic field set changed")
    if contract.get("metric_rules") != {
        "structure": "micro_set_precision_recall_f1_per_component_and_overall",
        "semantic_match": "case_sensitive_exact_surface_value",
        "wrong_nonnull_value": "one_false_positive_and_one_false_negative",
        "gold_absent_prediction_absent": "true_negative",
        "semantic": "field_micro_precision_recall_f1_and_exact_value_accuracy",
        "triple": "all_three_fields_exact_per_activity",
        "zero_denominator": 0.0,
        "terminal_error": "null_records_retained_in_denominator",
        "invalid_prediction": "retained_in_denominator_and_scored_as_empty",
    }:
        raise Stage1EvaluationError("S1.6 metric rules changed")
    membership = contract.get("membership", {})
    if membership != {
        "attempt_key": ["method", "process_id"],
        "exact_method_process_cartesian_product": True,
        "duplicates": "reject",
        "missing_or_extra": "reject",
    }:
        raise Stage1EvaluationError("S1.6 membership rules changed")
    upstream = contract.get("upstream", {})
    label_manifest = _project_path(str(upstream.get("stage1_label_manifest_path", "")))
    annotation_manifest = _project_path(
        str(upstream.get("stage1_annotation_manifest_path", ""))
    )
    if (
        not label_manifest.is_file()
        or sha256_file(label_manifest) != upstream.get("stage1_label_manifest_sha256")
        or not annotation_manifest.is_file()
        or sha256_file(annotation_manifest)
        != upstream.get("stage1_annotation_manifest_sha256")
    ):
        raise Stage1EvaluationError("S1.6 upstream binding changed")
    safety = contract.get("safety", {})
    if safety != {
        "synthetic_fixture_only": True,
        "synthetic_reference_is_human_gold": False,
        "formal_bpmn_read": False,
        "human_gold_read_or_modified": False,
        "llm_api_called": False,
        "network_called": False,
        "formal_performance_evaluation": False,
        "formal_results_written": False,
        "no_overwrite": True,
    }:
        raise Stage1EvaluationError("S1.6 safety boundary changed")
    return contract


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _count_metric(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": _ratio(2 * precision * recall, precision + recall),
    }


def _semantic_metric(tp: int, fp: int, fn: int, tn: int) -> dict[str, Any]:
    result = _count_metric(tp, fp, fn)
    return {
        **result,
        "tn": tn,
        "exact_value_accuracy": _ratio(tp + tn, tp + fp + fn + tn),
    }


def _structure_sets(record: Mapping[str, Any] | None) -> dict[str, set[Any]]:
    if record is None:
        return {name: set() for name in STRUCTURE_COMPONENTS}
    return {
        "pools": {item["id"] for item in record["pools"]},
        "lanes": {item["id"] for item in record["lanes"]},
        "activities": {item["id"] for item in record["activities"]},
        "events": {item["id"] for item in record["events"]},
        "gateways": {item["id"] for item in record["gateways"]},
        "sequence_flows": {
            (item["id"], item["source_ref"], item["target_ref"])
            for item in record["sequence_flows"]
        },
        "direct_edges": {
            (item["source_ref"], item["target_ref"])
            for item in record["control_flow"]["direct_edges"]
        },
        "activity_order_relations": {
            (item["before_activity_id"], item["after_activity_id"])
            for item in record["control_flow"]["activity_order_relations"]
        },
    }


def _prediction_values(label_record: Mapping[str, Any] | None) -> dict[str, dict[str, str | None]]:
    if label_record is None:
        return {}
    return {
        item["activity_id"]: {
            "actor": item["actor_surface"],
            "action": item["action_surface"],
            "business_object": item["business_object_surface"],
        }
        for item in label_record["activities"]
    }


def evaluate_stage1(
    *,
    gold_process_records: Sequence[Mapping[str, Any]],
    gold_semantics: Mapping[str, Mapping[str, Mapping[str, str | None]]],
    attempts: Sequence[Mapping[str, Any]],
    label_contract: Mapping[str, Any],
    evaluator_contract: Mapping[str, Any],
    scope: str,
) -> dict[str, Any]:
    if scope not in {"synthetic_contract_verification", "formal"}:
        raise Stage1EvaluationError("unknown evaluation scope")
    if scope == "formal":
        raise Stage1EvaluationError("formal S1.6 evaluation is blocked by membership/Gold gates")
    if tuple(evaluator_contract.get("methods", ())) != METHODS:
        raise Stage1EvaluationError("evaluator contract method set changed")
    gold_by_id: dict[str, Mapping[str, Any]] = {}
    for record in gold_process_records:
        report = validate_process_record(record)
        if not report.valid:
            raise Stage1EvaluationError("invalid synthetic structure reference")
        process_id = record["process_id"]
        if process_id in gold_by_id:
            raise Stage1EvaluationError(f"duplicate Gold process_id: {process_id}")
        gold_by_id[process_id] = record
    membership = sorted(gold_by_id)
    if not membership or set(gold_semantics) != set(membership):
        raise Stage1EvaluationError("semantic reference membership mismatch")
    for process_id in membership:
        activity_ids = {item["id"] for item in gold_by_id[process_id]["activities"]}
        if set(gold_semantics[process_id]) != activity_ids:
            raise Stage1EvaluationError("semantic activity membership mismatch")
        for values in gold_semantics[process_id].values():
            if set(values) != set(SEMANTIC_FIELDS):
                raise Stage1EvaluationError("semantic reference fields changed")
            if any(value is not None and not isinstance(value, str) for value in values.values()):
                raise Stage1EvaluationError("semantic reference value must be string or null")
    attempt_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    required_attempt_keys = {"method", "process_id", "process_record", "label_record", "error"}
    for attempt in attempts:
        if set(attempt) != required_attempt_keys:
            raise Stage1EvaluationError("attempt envelope properties changed")
        key = (attempt["method"], attempt["process_id"])
        if key in attempt_by_key:
            raise Stage1EvaluationError(f"duplicate attempt: {key}")
        attempt_by_key[key] = attempt
    expected_keys = {(method, process_id) for method in METHODS for process_id in membership}
    if set(attempt_by_key) != expected_keys:
        raise Stage1EvaluationError("attempt membership is not the exact method/process product")

    method_reports: dict[str, Any] = {}
    for method in METHODS:
        structure_counts = {name: [0, 0, 0] for name in STRUCTURE_COMPONENTS}
        semantic_counts = {name: [0, 0, 0, 0] for name in SEMANTIC_FIELDS}
        terminal_errors = 0
        invalid_predictions = 0
        structure_records = 0
        label_records = 0
        triple_exact = 0
        total_activities = 0
        for process_id in membership:
            attempt = attempt_by_key[(method, process_id)]
            process_prediction = attempt["process_record"]
            label_prediction = attempt["label_record"]
            error = attempt["error"]
            if error is not None:
                if not isinstance(error, str) or not error or process_prediction is not None or label_prediction is not None:
                    raise Stage1EvaluationError("terminal error attempt must contain only a non-empty error")
                terminal_errors += 1
                process_prediction = None
                label_prediction = None
            else:
                process_valid = (
                    isinstance(process_prediction, Mapping)
                    and validate_process_record(process_prediction).valid
                    and process_prediction.get("process_id") == process_id
                )
                if process_valid:
                    structure_records += 1
                else:
                    process_prediction = None
                label_valid = False
                if process_prediction is not None and isinstance(label_prediction, Mapping):
                    label_report = validate_label_semantics(
                        label_prediction,
                        process_record=process_prediction,
                        contract=label_contract,
                    )
                    label_valid = (
                        label_report.valid
                        and label_prediction.get("method", {}).get("baseline") == method
                    )
                if label_valid:
                    label_records += 1
                else:
                    label_prediction = None
                if not process_valid or not label_valid:
                    invalid_predictions += 1
            gold_sets = _structure_sets(gold_by_id[process_id])
            pred_sets = _structure_sets(process_prediction)
            for component in STRUCTURE_COMPONENTS:
                tp = len(gold_sets[component] & pred_sets[component])
                fp = len(pred_sets[component] - gold_sets[component])
                fn = len(gold_sets[component] - pred_sets[component])
                structure_counts[component][0] += tp
                structure_counts[component][1] += fp
                structure_counts[component][2] += fn
            predicted_values = _prediction_values(label_prediction)
            for activity_id, gold_values in gold_semantics[process_id].items():
                total_activities += 1
                pred_values = predicted_values.get(
                    activity_id,
                    {field: None for field in SEMANTIC_FIELDS},
                )
                if all(pred_values[field] == gold_values[field] for field in SEMANTIC_FIELDS):
                    triple_exact += 1
                for field in SEMANTIC_FIELDS:
                    gold_value = gold_values[field]
                    pred_value = pred_values[field]
                    if gold_value is not None and pred_value == gold_value:
                        semantic_counts[field][0] += 1
                    elif pred_value is not None:
                        semantic_counts[field][1] += 1
                    if gold_value is not None and pred_value != gold_value:
                        semantic_counts[field][2] += 1
                    if gold_value is None and pred_value is None:
                        semantic_counts[field][3] += 1
        structure_by_component = {
            component: _count_metric(*structure_counts[component])
            for component in STRUCTURE_COMPONENTS
        }
        structure_micro_counts = [
            sum(counts[index] for counts in structure_counts.values())
            for index in range(3)
        ]
        semantic_by_field = {
            field: _semantic_metric(*semantic_counts[field])
            for field in SEMANTIC_FIELDS
        }
        semantic_micro_counts = [
            sum(counts[index] for counts in semantic_counts.values())
            for index in range(4)
        ]
        attempts_count = len(membership)
        method_reports[method] = {
            "attempts": attempts_count,
            "terminal_errors": terminal_errors,
            "invalid_predictions": invalid_predictions,
            "structure_record_coverage": _ratio(structure_records, attempts_count),
            "label_record_coverage": _ratio(label_records, attempts_count),
            "structure": {
                "by_component": structure_by_component,
                "micro": _count_metric(*structure_micro_counts),
            },
            "semantics": {
                "by_field": semantic_by_field,
                "micro": _semantic_metric(*semantic_micro_counts),
            },
            "semantic_triple_exact_accuracy": _ratio(triple_exact, total_activities),
        }
    report = {
        "schema_version": REPORT_VERSION,
        "scope": scope,
        "membership": membership,
        "methods": method_reports,
    }
    validation = validate_stage1_report(report)
    if not validation.valid:
        raise Stage1EvaluationError("generated report is invalid: " + "; ".join(validation.errors))
    return report


def validate_stage1_report(report: Mapping[str, Any]) -> ReportValidation:
    errors: list[str] = []
    if not isinstance(report, Mapping) or set(report) != {
        "schema_version",
        "scope",
        "membership",
        "methods",
    }:
        return ReportValidation(False, ("report properties changed",))
    if report.get("schema_version") != REPORT_VERSION:
        errors.append("report schema_version changed")
    if report.get("scope") not in {"synthetic_contract_verification", "formal"}:
        errors.append("report scope changed")
    membership = report.get("membership")
    if (
        not isinstance(membership, list)
        or any(not isinstance(item, str) or not item for item in membership)
        or membership != sorted(membership)
        or len(membership) != len(set(membership))
    ):
        errors.append("report membership must be unique and sorted")
    methods = report.get("methods")
    if not isinstance(methods, Mapping) or set(methods) != set(METHODS):
        errors.append("report methods changed")
        return ReportValidation(not errors, tuple(errors))
    method_keys = {
        "attempts",
        "terminal_errors",
        "invalid_predictions",
        "structure_record_coverage",
        "label_record_coverage",
        "structure",
        "semantics",
        "semantic_triple_exact_accuracy",
    }
    count_keys = {"tp", "fp", "fn", "precision", "recall", "f1"}
    semantic_keys = count_keys | {"tn", "exact_value_accuracy"}
    for method, value in methods.items():
        if not isinstance(value, Mapping) or set(value) != method_keys:
            errors.append(f"{method} report properties changed")
            continue
        for key in ("attempts", "terminal_errors", "invalid_predictions"):
            if not isinstance(value[key], int) or isinstance(value[key], bool) or value[key] < 0:
                errors.append(f"{method}.{key} invalid")
        for key in (
            "structure_record_coverage",
            "label_record_coverage",
            "semantic_triple_exact_accuracy",
        ):
            if not isinstance(value[key], (int, float)) or isinstance(value[key], bool) or not 0 <= value[key] <= 1:
                errors.append(f"{method}.{key} invalid")
        structure = value["structure"]
        semantics = value["semantics"]
        if (
            not isinstance(structure, Mapping)
            or set(structure) != {"by_component", "micro"}
            or set(structure["by_component"]) != set(STRUCTURE_COMPONENTS)
        ):
            errors.append(f"{method}.structure changed")
        else:
            for metric in [*structure["by_component"].values(), structure["micro"]]:
                if not isinstance(metric, Mapping) or set(metric) != count_keys:
                    errors.append(f"{method}.structure metric changed")
                    break
        if (
            not isinstance(semantics, Mapping)
            or set(semantics) != {"by_field", "micro"}
            or set(semantics["by_field"]) != set(SEMANTIC_FIELDS)
        ):
            errors.append(f"{method}.semantics changed")
        else:
            for metric in [*semantics["by_field"].values(), semantics["micro"]]:
                if not isinstance(metric, Mapping) or set(metric) != semantic_keys:
                    errors.append(f"{method}.semantic metric changed")
                    break
    return ReportValidation(not errors, tuple(errors))
