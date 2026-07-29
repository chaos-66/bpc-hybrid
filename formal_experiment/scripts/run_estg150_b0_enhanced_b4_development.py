"""Run the sole preregistered EStG-150 B4 All-150 development candidate."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    Estg150B0DevelopmentError,
    build_canonical_gold_records,
    load_object,
    sha256_file,
    summarize_evaluation,
)
from bpc_hybrid.estg150_b0_development_b4 import (  # noqa: E402
    METHOD_ID,
    METHOD_VARIANT,
    run_b0_batch_b4,
)
from bpc_hybrid.estg150_b0_development_v2 import (  # noqa: E402
    sun_table8_any_overlap_diagnostic,
)
from bpc_hybrid.stage2_evaluation_v3 import (  # noqa: E402
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    validate_evaluation_report,
)


DEFAULT_CONFIG = ROOT / "configs/models/estg150_b0_enhanced_s27_b4.json"
PARENT_DIR = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a"
PARENT_ATTEMPTS = PARENT_DIR / "b0_attempts.json"
PARENT_EVALUATION = PARENT_DIR / "evaluation_all150.json"
PARENT_TABLE8 = PARENT_DIR / "sun_table8_any_overlap_diagnostic.json"


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _load_array(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise Estg150B0DevelopmentError(f"expected JSON object array: {path}")
    return value


def _check_spec(root: Path, spec: Mapping[str, Any], label: str) -> Path:
    path = root / str(spec.get("path"))
    if not path.is_file() or sha256_file(path) != spec.get("sha256"):
        raise Estg150B0DevelopmentError(f"{label} is missing or hash-mismatched")
    return path


def _verify_preregistration(config_path: Path, config: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    prereg_rel = config.get("method", {}).get("preregistration", {}).get("path")
    if not isinstance(prereg_rel, str):
        raise Estg150B0DevelopmentError("B4 config is missing preregistration path")
    prereg_path = ROOT / prereg_rel
    prereg = load_object(prereg_path)
    if (
        prereg.get("schema_version") != "b0_enhanced_b4_preregistration@1.0.0"
        or prereg.get("status") != "preregistered_frozen_before_single_all150"
        or prereg.get("run_id") != "s27_estg150_b0_enhanced_b4"
        or prereg.get("method_variant") != METHOD_VARIANT
        or prereg.get("single_all150_run_max") != 1
    ):
        raise Estg150B0DevelopmentError("B4 preregistration identity/status changed")
    config_binding = prereg.get("config") or {}
    if (
        config_binding.get("path") != str(config_path.relative_to(ROOT)).replace("\\", "/")
        or config_binding.get("sha256") != sha256_file(config_path)
        or config_binding.get("bytes") != config_path.stat().st_size
    ):
        raise Estg150B0DevelopmentError("B4 config is not frozen by preregistration")
    for group in ("module_bindings", "resource_bindings"):
        bindings = prereg.get(group)
        if not isinstance(bindings, Mapping) or not bindings:
            raise Estg150B0DevelopmentError(f"B4 preregistration lacks {group}")
        for name, meta in bindings.items():
            if not isinstance(meta, Mapping):
                raise Estg150B0DevelopmentError(f"invalid B4 preregistration binding: {name}")
            path = ROOT / str(meta.get("path"))
            if (
                not path.is_file()
                or sha256_file(path) != meta.get("sha256")
                or path.stat().st_size != meta.get("bytes")
            ):
                raise Estg150B0DevelopmentError(f"B4 preregistration binding drifted: {name}")
    return prereg_path, prereg


def _evaluate(
    gold: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    *,
    contract: Mapping[str, Any],
    dataset_id: str,
) -> dict[str, Any]:
    report = evaluate_stage2(
        gold,
        attempts,
        contract=contract,
        dataset_id=dataset_id,
        method_id=METHOD_ID,
        expected_membership_sha256=membership_sha256(gold),
        claim_scope="development",
        formal_ready=False,
    )
    errors = validate_evaluation_report(report)
    if errors:
        raise Estg150B0DevelopmentError("B4 evaluation report invalid: " + "; ".join(errors))
    return report


def _check(name: str, passed: bool, actual: Any, expected: Any) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "actual": actual, "expected": expected}


def _span_key(span: Mapping[str, Any]) -> tuple[Any, ...]:
    return (span.get("start"), span.get("end"), span.get("text"), span.get("normalized"))


def _indexed_clauses(attempts: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], Mapping[str, Any]]:
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    for attempt in attempts:
        sample = str(attempt["sample_id"])
        for clause in attempt["record"].get("clauses") or []:
            key = (sample, str(clause["clause_id"]))
            if key in indexed:
                raise Estg150B0DevelopmentError(f"duplicate clause identity: {key}")
            indexed[key] = clause
    return indexed


def _attempt_diff(
    attempts: Sequence[Mapping[str, Any]],
    parent_attempts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    current = _indexed_clauses(attempts)
    parent = _indexed_clauses(parent_attempts)
    same_clause_keys = set(current) == set(parent)
    common = sorted(set(current) & set(parent))
    clause_span_mismatches = 0
    alignment_mismatches = 0
    modality_mismatches = 0
    edge_mismatches = 0
    field_span_mismatches = {field: 0 for field in ("actors", "actions", "conditions", "exceptions")}
    new_constraint_spans = 0
    removed_constraint_spans = 0
    changed_constraint_clauses = 0
    for key in common:
        clause = current[key]
        parent_clause = parent[key]
        clause_span_mismatches += clause.get("clause_span") != parent_clause.get("clause_span")
        alignment_mismatches += clause.get("alignment") != parent_clause.get("alignment")
        modality_mismatches += clause.get("modality") != parent_clause.get("modality")
        edge_mismatches += (
            clause.get("actor_action_map") != parent_clause.get("actor_action_map")
            or clause.get("edge_evidence") != parent_clause.get("edge_evidence")
        )
        for field in field_span_mismatches:
            current_spans = {_span_key(span) for span in clause.get(field) or []}
            parent_spans = {_span_key(span) for span in parent_clause.get(field) or []}
            field_span_mismatches[field] += current_spans != parent_spans
        current_constraints = {_span_key(span) for span in clause.get("constraints") or []}
        parent_constraints = {_span_key(span) for span in parent_clause.get("constraints") or []}
        added = current_constraints - parent_constraints
        removed = parent_constraints - current_constraints
        new_constraint_spans += len(added)
        removed_constraint_spans += len(removed)
        changed_constraint_clauses += bool(added or removed)
    return {
        "same_clause_keys": same_clause_keys,
        "candidate_clause_count": len(current),
        "parent_clause_count": len(parent),
        "clause_span_mismatches": clause_span_mismatches,
        "alignment_mismatches": alignment_mismatches,
        "modality_mismatches": modality_mismatches,
        "edge_mismatches": edge_mismatches,
        "field_span_mismatches": field_span_mismatches,
        "new_constraint_spans": new_constraint_spans,
        "removed_constraint_spans": removed_constraint_spans,
        "changed_constraint_clauses": changed_constraint_clauses,
    }


def evaluate_promotion_gates(
    *,
    report: Mapping[str, Any],
    attempts: Sequence[Mapping[str, Any]],
    runtime: Mapping[str, Any],
    table8: Mapping[str, Any],
    parent_report: Mapping[str, Any],
    parent_attempts: Sequence[Mapping[str, Any]],
    parent_table8: Mapping[str, Any],
    parent_runtime: Mapping[str, Any],
    gates: Mapping[str, Any],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    constraint = table8["per_field"]["constraint"]
    overall = table8["overall"]
    expected_parent = gates["fixed_parent_table8"]
    checks.append(_check("P0_parent_constraint_metrics_bound", parent_table8["per_field"]["constraint"] == expected_parent["constraint"], parent_table8["per_field"]["constraint"], expected_parent["constraint"]))
    checks.append(_check("P1_parent_overall_metrics_bound", parent_table8["overall"] == expected_parent["overall"], parent_table8["overall"], expected_parent["overall"]))
    for metric, op in (("tp", ">="), ("fp", "<="), ("fn", "<="), ("precision", ">="), ("recall", ">="), ("f1", ">=")):
        threshold = gates["constraint"][f"{metric}_{'max' if metric in {'fp', 'fn'} else 'min'}"]
        passed = constraint[metric] <= threshold if op == "<=" else constraint[metric] >= threshold
        checks.append(_check(f"C_constraint_{metric}", passed, constraint[metric], f"{op} {threshold}"))
    for metric, op in (("tp", ">="), ("fp", "<="), ("fn", "<="), ("precision", ">="), ("recall", ">="), ("f1", ">=")):
        threshold = gates["overall"][f"{metric}_{'max' if metric in {'fp', 'fn'} else 'min'}"]
        passed = overall[metric] <= threshold if op == "<=" else overall[metric] >= threshold
        checks.append(_check(f"O_overall_{metric}", passed, overall[metric], f"{op} {threshold}"))

    lexicon = runtime["lexicon_b4"]
    purity = gates["purity"]
    checks.extend(
        [
            _check("L1_new_active_marker_count", purity["new_active_marker_min"] <= lexicon["new_active_marker_count"] <= purity["new_active_marker_max"], lexicon["new_active_marker_count"], f"{purity['new_active_marker_min']}..{purity['new_active_marker_max']}"),
            _check("L2_invoked_unique_new_markers", lexicon["invoked_unique_new_marker_count"] >= purity["invoked_unique_new_marker_min"], lexicon["invoked_unique_new_marker_count"], f">= {purity['invoked_unique_new_marker_min']}"),
        ]
    )
    diff = _attempt_diff(attempts, parent_attempts)
    checks.extend(
        [
            _check("S1_same_clause_identity", diff["same_clause_keys"], diff["candidate_clause_count"], diff["parent_clause_count"]),
            _check("S2_final_new_constraint_span_count", purity["final_new_constraint_spans_min"] <= diff["new_constraint_spans"] <= purity["final_new_constraint_spans_max"], diff["new_constraint_spans"], f"{purity['final_new_constraint_spans_min']}..{purity['final_new_constraint_spans_max']}"),
            _check("S3_no_parent_constraint_span_removed", diff["removed_constraint_spans"] == 0, diff["removed_constraint_spans"], 0),
            _check("S4_clause_spans_exact_parent", diff["clause_span_mismatches"] == 0, diff["clause_span_mismatches"], 0),
            _check("S5_alignment_exact_parent", diff["alignment_mismatches"] == 0, diff["alignment_mismatches"], 0),
            _check("S6_modality_exact_parent", diff["modality_mismatches"] == 0, diff["modality_mismatches"], 0),
            _check("S7_edges_exact_parent", diff["edge_mismatches"] == 0, diff["edge_mismatches"], 0),
            _check("S8_all_other_field_span_sets_exact_parent", all(value == 0 for value in diff["field_span_mismatches"].values()), diff["field_span_mismatches"], {field: 0 for field in diff["field_span_mismatches"]}),
        ]
    )
    for field in ("actor", "action", "condition", "exception"):
        checks.append(_check(f"M_{field}_table8_exact_parent", table8["per_field"][field] == parent_table8["per_field"][field], table8["per_field"][field], parent_table8["per_field"][field]))

    runtime_keys = (
        "pattern_count",
        "match_count",
        "surgery_count",
        "terminal_tree_removal_count",
        "bridge_class",
        "bridge_source",
        "patterns_path",
        "tsurgeon_enabled",
        "predicted_clause_count",
        "record_count",
        "modality_route_counts",
        "final_hybrid_label_counts_by_clause",
        "alignment_summary",
        "edge_stats",
        "placeholder_classifier_count",
        "profile_id",
        "s26_config_rel",
    )
    runtime_drift = {key: {"candidate": runtime.get(key), "parent": parent_runtime.get(key)} for key in runtime_keys if runtime.get(key) != parent_runtime.get(key)}
    checks.append(_check("R1_fixed_runtime_outputs_exact_parent", not runtime_drift, runtime_drift, {}))
    parent_lexicon = parent_runtime["lexicon_v2"]
    checks.append(_check("R2_nonconstraint_lexicon_hashes_exact_parent", all(lexicon["category_file_sha256"][field] == parent_lexicon["category_file_sha256"][field] for field in ("modality", "condition", "exception", "actor")), {field: lexicon["category_file_sha256"][field] for field in ("modality", "condition", "exception", "actor")}, {field: parent_lexicon["category_file_sha256"][field] for field in ("modality", "condition", "exception", "actor")}))
    checks.append(_check("R3_parent_constraint_lexicon_hash_exact", lexicon["category_file_sha256"]["constraint"] == parent_lexicon["category_file_sha256"]["constraint"], lexicon["category_file_sha256"]["constraint"], parent_lexicon["category_file_sha256"]["constraint"]))

    candidate_summary = summarize_evaluation(report)
    parent_summary = summarize_evaluation(parent_report)
    checks.append(_check("E1_clause_segmentation_metrics_exact_parent", candidate_summary["clause_segmentation"] == parent_summary["clause_segmentation"], candidate_summary["clause_segmentation"], parent_summary["clause_segmentation"]))
    coverage = candidate_summary["semantic_coverage"]
    coverage_gates = gates["coverage"]
    checks.extend(
        [
            _check("E2_presence_recall", coverage["gold_required_presence_recall"] >= coverage_gates["presence_recall_min"], coverage["gold_required_presence_recall"], f">= {coverage_gates['presence_recall_min']}"),
            _check("E3_complete_record_rate", coverage["complete_record_rate"] >= coverage_gates["complete_record_rate_min"], coverage["complete_record_rate"], f">= {coverage_gates['complete_record_rate_min']}"),
            _check("E4_hallucinated_field_rate", coverage["hallucinated_field_rate"] <= coverage_gates["hallucinated_field_rate_max"], coverage["hallucinated_field_rate"], f"<= {coverage_gates['hallucinated_field_rate_max']}"),
            _check("E5_schema_valid_rate", coverage["schema_valid_rate"] == 1.0, coverage["schema_valid_rate"], 1.0),
            _check("E6_placeholder_classifier_count", runtime["placeholder_classifier_count"] == 0, runtime["placeholder_classifier_count"], 0),
            _check("E7_tsurgeon_disabled_and_zero_surgery", runtime["tsurgeon_enabled"] is False and runtime["surgery_count"] == 0, {"tsurgeon_enabled": runtime["tsurgeon_enabled"], "surgery_count": runtime["surgery_count"]}, {"tsurgeon_enabled": False, "surgery_count": 0}),
        ]
    )
    failed = [check["name"] for check in checks if not check["pass"]]
    return {
        "schema_version": "b4_promotion_gate_report@1.0.0",
        "promote": not failed,
        "decision": "promotion_eligible_user_decision_required" if not failed else "not_promoted_negative_evidence",
        "checks": checks,
        "failed_gates": failed,
        "constraint_delta": {
            "new_spans": diff["new_constraint_spans"],
            "removed_parent_spans": diff["removed_constraint_spans"],
            "changed_clauses": diff["changed_constraint_clauses"],
        },
        "active_registry_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--runtime-home", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    try:
        config_path = args.config.resolve()
        config = load_object(config_path)
        if (
            config.get("run_id") != "s27_estg150_b0_enhanced_b4"
            or config.get("method", {}).get("method_variant") != METHOD_VARIANT
            or config.get("claim_scope") != "development"
            or config.get("method", {}).get("paper_faithful_b0") is not False
            or config.get("safety", {}).get("llm_api_called") is not False
            or config.get("safety", {}).get("network_allowed") is not False
            or config.get("safety", {}).get("active_registry_modified") is not False
        ):
            raise Estg150B0DevelopmentError("B4 config identity or safety changed")
        prereg_path, prereg = _verify_preregistration(config_path, config)
        layer_e = _check_spec(ROOT, config["inputs"]["human_correction_layer_e"], "Layer E")
        membership = _check_spec(ROOT, config["inputs"]["membership_hashes"], "membership")
        freeze_receipt = _check_spec(ROOT, config["inputs"]["annotation_freeze_receipt"], "S2.2 freeze receipt")
        parent_manifest_path = _check_spec(ROOT, config["inputs"]["v10a_parent_manifest"], "v10-A manifest")
        _check_spec(ROOT, config["inputs"]["v10a_parent_attempts"], "v10-A attempts")
        _check_spec(ROOT, config["inputs"]["v10a_parent_evaluation"], "v10-A evaluation")
        _check_spec(ROOT, config["inputs"]["v10a_parent_table8"], "v10-A Table-8 diagnostic")
        _check_spec(ROOT, config["inputs"]["b3a_negative_evidence"], "B3a negative evidence")
        _check_spec(ROOT, config["inputs"]["b3b_negative_evidence"], "B3b negative evidence")
        _check_spec(ROOT, config["method"]["s2_6_config"], "S2.6 classifier config")
        _check_spec(ROOT, config["method"]["constraint_lexicon_manifest"], "B4 lexicon manifest")
        evaluator_path = _check_spec(ROOT, config["evaluator"], "S2.10 evaluator v3")
        output_dir = (ROOT / config["output"]["directory"]).resolve()
        output_dir.relative_to((ROOT / "outputs/development").resolve())
        if output_dir.exists():
            raise Estg150B0DevelopmentError(f"refusing to overwrite: {output_dir}")

        gold, source_records = build_canonical_gold_records(layer_e, membership)
        evaluator_contract = load_evaluator_contract(evaluator_path)
        parent_attempts = _load_array(PARENT_ATTEMPTS)
        parent_report = load_object(PARENT_EVALUATION)
        parent_table8 = load_object(PARENT_TABLE8)
        parent_manifest = load_object(parent_manifest_path)
        (ROOT / ".tmp").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="s27_estg150_b0_enhanced_b4-", dir=ROOT / ".tmp") as raw_work:
            attempts, runtime = run_b0_batch_b4(
                ROOT,
                source_records,
                runtime_home=args.runtime_home,
                work_dir=Path(raw_work),
                device=args.device,
            )
            report = _evaluate(gold, attempts, contract=evaluator_contract, dataset_id=config["dataset_id"])
            table8 = sun_table8_any_overlap_diagnostic(gold, attempts)
            gate_report = evaluate_promotion_gates(
                report=report,
                attempts=attempts,
                runtime=runtime,
                table8=table8,
                parent_report=parent_report,
                parent_attempts=parent_attempts,
                parent_table8=parent_table8,
                parent_runtime=parent_manifest["runtime"],
                gates=config["promotion_gates"],
            )
            staging = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
            if staging.exists():
                raise Estg150B0DevelopmentError(f"staging path already exists: {staging}")
            staging.mkdir()
            try:
                attempts_path = staging / "b0_attempts.json"
                evaluation_path = staging / "evaluation_all150.json"
                table8_path = staging / "sun_table8_any_overlap_diagnostic.json"
                gate_path = staging / "promotion_gate_report.json"
                _write_json(attempts_path, attempts)
                _write_json(evaluation_path, report)
                _write_json(table8_path, table8)
                _write_json(gate_path, gate_report)
                manifest = {
                    "schema_version": "estg150_b0_enhanced_b4_manifest@1.0.0",
                    "run_id": config["run_id"],
                    "task_id": config["task_id"],
                    "status": "succeeded_development_not_formal",
                    "method_id": METHOD_ID,
                    "method_variant": METHOD_VARIANT,
                    "paper_faithful_b0": False,
                    "dataset_id": config["dataset_id"],
                    "claim_scope": "development",
                    "is_formal_performance_result": False,
                    "parent_run": "s27_estg150_b0_enhanced_v10a",
                    "negative_evidence_only": ["B3a", "B3b"],
                    "preregistration": {
                        "path": str(prereg_path.relative_to(ROOT)).replace("\\", "/"),
                        "sha256": sha256_file(prereg_path),
                        "created_at_utc": prereg["created_at_utc"],
                    },
                    "input_binding": {
                        "layer_e_sha256": sha256_file(layer_e),
                        "membership_hashes_sha256": sha256_file(membership),
                        "freeze_receipt_sha256": sha256_file(freeze_receipt),
                        "canonical_gold_membership_sha256": membership_sha256(gold),
                        "canonical_gold_copy_persisted": False,
                        "config_sha256": sha256_file(config_path),
                    },
                    "tracks": {
                        "all150": summarize_evaluation(report),
                        "sun_table8_any_overlap_diagnostic": table8["overall"],
                    },
                    "runtime": runtime,
                    "promotion": {
                        "promote": gate_report["promote"],
                        "decision": gate_report["decision"],
                        "failed_gates": gate_report["failed_gates"],
                        "active_registry_modified": False,
                    },
                    "artifacts": {
                        "attempts": {"path": attempts_path.name, "sha256": sha256_file(attempts_path)},
                        "evaluation_all150": {"path": evaluation_path.name, "sha256": sha256_file(evaluation_path)},
                        "sun_table8_any_overlap_diagnostic": {"path": table8_path.name, "sha256": sha256_file(table8_path)},
                        "promotion_gate_report": {"path": gate_path.name, "sha256": sha256_file(gate_path)},
                    },
                    "route_boundaries": config["route_boundaries"],
                    "safety": {
                        **config["safety"],
                        "row_level_development_predictions_persisted": True,
                        "network_called": False,
                        "llm_call_count": 0,
                        "estimated_cost_usd": 0.0,
                    },
                }
                _write_json(staging / "manifest.json", manifest)
                staging.rename(output_dir)
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                raise
        print(json.dumps({"run_id": config["run_id"], "output_dir": str(output_dir), "promotion": manifest["promotion"], "constraint": table8["per_field"]["constraint"], "overall": table8["overall"], "new_markers": runtime["lexicon_b4"], "llm_calls": 0, "network_calls": 0, "formal": False}, ensure_ascii=False, sort_keys=True))
        return 0
    except (Estg150B0DevelopmentError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"EStG-150 B4 development run failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

