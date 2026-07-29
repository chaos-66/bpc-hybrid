"""Run the sole preregistered EStG-150 B5 development candidate."""

from __future__ import annotations

import argparse
import hashlib
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
from bpc_hybrid.estg150_b0_development_b5 import (  # noqa: E402
    METHOD_ID,
    METHOD_VARIANT,
    run_b0_batch_b5,
    validate_b5_registry,
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


DEFAULT_CONFIG = ROOT / "configs/models/estg150_b0_enhanced_s27_b5.json"


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _load_array(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise Estg150B0DevelopmentError(f"expected JSON object array: {path}")
    return value


def _check_spec(spec: Mapping[str, Any], label: str) -> Path:
    path = ROOT / str(spec.get("path"))
    if not path.is_file() or sha256_file(path) != spec.get("sha256"):
        raise Estg150B0DevelopmentError(f"{label} is missing or hash-mismatched")
    return path


def _verify_preregistration(
    config_path: Path, config: Mapping[str, Any]
) -> tuple[Path, dict[str, Any]]:
    prereg_rel = config.get("method", {}).get("preregistration", {}).get("path")
    if not isinstance(prereg_rel, str):
        raise Estg150B0DevelopmentError("B5 config is missing preregistration path")
    prereg_path = ROOT / prereg_rel
    prereg = load_object(prereg_path)
    if (
        prereg.get("schema_version") != "b0_enhanced_b5_preregistration@1.0.0"
        or prereg.get("status") != "preregistered_frozen_before_single_all150"
        or prereg.get("run_id") != "s27_estg150_b0_enhanced_b5"
        or prereg.get("method_variant") != METHOD_VARIANT
        or prereg.get("single_all150_run_max") != 1
    ):
        raise Estg150B0DevelopmentError("B5 preregistration identity/status changed")
    config_binding = prereg.get("config") or {}
    if (
        config_binding.get("path") != str(config_path.relative_to(ROOT)).replace("\\", "/")
        or config_binding.get("sha256") != sha256_file(config_path)
        or config_binding.get("bytes") != config_path.stat().st_size
    ):
        raise Estg150B0DevelopmentError("B5 config is not frozen by preregistration")
    for group_name in (
        "new_code_bindings",
        "resource_bindings",
        "fixed_parent_bindings",
        "synthetic_gate_bindings",
    ):
        group = prereg.get(group_name)
        if not isinstance(group, Mapping) or not group:
            raise Estg150B0DevelopmentError(f"B5 preregistration lacks {group_name}")
        for name, metadata in group.items():
            if not isinstance(metadata, Mapping):
                raise Estg150B0DevelopmentError(f"invalid B5 binding: {group_name}.{name}")
            path = ROOT / str(metadata.get("path"))
            if (
                not path.is_file()
                or sha256_file(path) != metadata.get("sha256")
                or path.stat().st_size != metadata.get("bytes")
            ):
                raise Estg150B0DevelopmentError(
                    f"B5 preregistration binding drifted: {group_name}.{name}"
                )
    if prereg.get("exact_command") != (
        "python formal_experiment/scripts/run_estg150_b0_enhanced_b5_development.py "
        "--config formal_experiment/configs/models/estg150_b0_enhanced_s27_b5.json "
        "--runtime-home D:\\environment\\stanford-corenlp-4.5.10 --device cpu"
    ):
        raise Estg150B0DevelopmentError("B5 exact preregistered command drifted")
    gate_bytes = json.dumps(
        config.get("promotion_gates"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if (
        prereg.get("promotion_gates") != config.get("promotion_gates")
        or prereg.get("promotion_gates_sha256")
        != hashlib.sha256(gate_bytes).hexdigest()
    ):
        raise Estg150B0DevelopmentError("B5 preregistered promotion gates drifted")
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
        raise Estg150B0DevelopmentError("B5 evaluation report invalid: " + "; ".join(errors))
    return report


def _check(name: str, passed: bool, actual: Any, expected: Any) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "actual": actual, "expected": expected}


def _indexed_clauses(
    attempts: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    for attempt in attempts:
        sample_id = str(attempt["sample_id"])
        for clause in attempt["record"].get("clauses") or []:
            key = (sample_id, str(clause["clause_id"]))
            if key in indexed:
                raise Estg150B0DevelopmentError(f"duplicate clause identity: {key}")
            indexed[key] = clause
    return indexed


def _parent_route_diff(
    attempts: Sequence[Mapping[str, Any]],
    parent_attempts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    candidate = _indexed_clauses(attempts)
    parent = _indexed_clauses(parent_attempts)
    common = sorted(set(candidate) & set(parent))
    return {
        "same_clause_keys": set(candidate) == set(parent),
        "candidate_clause_count": len(candidate),
        "parent_clause_count": len(parent),
        "clause_span_mismatches": sum(
            candidate[key].get("clause_span") != parent[key].get("clause_span")
            for key in common
        ),
        "alignment_mismatches": sum(
            candidate[key].get("alignment") != parent[key].get("alignment")
            for key in common
        ),
        "modality_mismatches": sum(
            candidate[key].get("modality") != parent[key].get("modality")
            for key in common
        ),
    }


def _selected_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: metrics[key]
        for key in ("tp", "fp", "fn", "precision", "recall", "f1")
        if key in metrics
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
    """Evaluate the frozen A-F gate family without changing any threshold."""
    groups: dict[str, list[dict[str, Any]]] = {name: [] for name in "ABCDEF"}
    authenticity = gates["A_authenticity"]
    proof = runtime["registry_proof"]
    consumer = runtime["actor_action_b5"]
    groups["A"].extend(
        [
            _check("A01_pattern_count_29", runtime["pattern_count"] == authenticity["pattern_count"], runtime["pattern_count"], authenticity["pattern_count"]),
            _check("A02_pattern_strings_order_exact_v3", proof["pattern_strings_exact_parent"] is True and proof["pattern_order_exact_parent"] is True, {"strings": proof["pattern_strings_exact_parent"], "order": proof["pattern_order_exact_parent"]}, True),
            _check("A03_accepted_surgery_positive", runtime["surgery_accepted"] >= authenticity["accepted_surgery_min"], runtime["surgery_accepted"], f">= {authenticity['accepted_surgery_min']}"),
            _check("A04_terminal_tree_removal_zero", runtime["terminal_tree_removal_count"] <= authenticity["terminal_tree_removal_max"], runtime["terminal_tree_removal_count"], authenticity["terminal_tree_removal_max"]),
            _check("A05_post_surgery_action_matches_positive", runtime["post_surgery_action_matches"] >= authenticity["post_surgery_action_matches_min"], runtime["post_surgery_action_matches"], f">= {authenticity['post_surgery_action_matches_min']}"),
            _check("A06_post_surgery_actor_matches_positive", runtime["post_surgery_actor_matches"] >= authenticity["post_surgery_actor_matches_min"], runtime["post_surgery_actor_matches"], f">= {authenticity['post_surgery_actor_matches_min']}"),
            _check("A07_final_tregex_action_spans_positive", consumer["final_tregex_action_spans"] >= authenticity["final_tregex_action_spans_min"], consumer["final_tregex_action_spans"], f">= {authenticity['final_tregex_action_spans_min']}"),
            _check("A08_final_tregex_actor_spans_positive", consumer["final_tregex_actor_spans"] >= authenticity["final_tregex_actor_spans_min"], consumer["final_tregex_actor_spans"], f">= {authenticity['final_tregex_actor_spans_min']}"),
            _check("A09_dependency_candidate_zero", consumer["dependency_candidate_span_count"] <= authenticity["dependency_candidate_span_count_max"], consumer["dependency_candidate_span_count"], 0),
            _check("A10_dependency_fallback_zero", consumer["dependency_fallback_count"] <= authenticity["dependency_fallback_count_max"], consumer["dependency_fallback_count"], 0),
            _check("A11_source_slice_failures_zero", runtime["source_slice_failures"] + consumer["source_slice_failures"] <= authenticity["source_slice_failures_max"], runtime["source_slice_failures"] + consumer["source_slice_failures"], 0),
            _check("A12_placeholder_zero", runtime["placeholder_classifier_count"] <= authenticity["placeholder_classifier_count_max"], runtime["placeholder_classifier_count"], 0),
        ]
    )

    actor = table8["per_field"]["actor"]
    action = table8["per_field"]["action"]
    parent_actor = parent_table8["per_field"]["actor"]
    parent_action = parent_table8["per_field"]["action"]
    actor_action = gates["B_actor_action"]
    combined = {
        key: actor[key] + action[key] for key in ("tp", "fp", "fn")
    }
    combined_parent = {
        key: parent_actor[key] + parent_action[key] for key in ("tp", "fp", "fn")
    }
    improvement_options = {
        "actor_f1_gain": actor["f1"] - parent_actor["f1"],
        "action_f1_gain": action["f1"] - parent_action["f1"],
        "combined_fp_reduction": combined_parent["fp"] - combined["fp"],
    }
    groups["B"].extend(
        [
            _check("B01_combined_tp", combined["tp"] >= actor_action["combined_tp_min"], combined["tp"], f">= {actor_action['combined_tp_min']}"),
            _check("B02_combined_fp", combined["fp"] <= actor_action["combined_fp_max"], combined["fp"], f"<= {actor_action['combined_fp_max']}"),
            _check("B03_combined_fn", combined["fn"] <= actor_action["combined_fn_max"], combined["fn"], f"<= {actor_action['combined_fn_max']}"),
            _check("B04_actor_f1", actor["f1"] >= actor_action["actor_f1_min"], actor["f1"], f">= {actor_action['actor_f1_min']}"),
            _check("B05_action_f1", action["f1"] >= actor_action["action_f1_min"], action["f1"], f">= {actor_action['action_f1_min']}"),
            _check("B06_actor_action_mean_f1", (actor["f1"] + action["f1"]) / 2 >= actor_action["mean_f1_min"], (actor["f1"] + action["f1"]) / 2, f">= {actor_action['mean_f1_min']}"),
            _check("B07_at_least_one_material_improvement", improvement_options["actor_f1_gain"] >= actor_action["actor_f1_improvement_min"] or improvement_options["action_f1_gain"] >= actor_action["action_f1_improvement_min"] or improvement_options["combined_fp_reduction"] >= actor_action["combined_fp_reduction_min"], improvement_options, {"actor_f1_gain": f">= {actor_action['actor_f1_improvement_min']}", "action_f1_gain": f">= {actor_action['action_f1_improvement_min']}", "combined_fp_reduction": f">= {actor_action['combined_fp_reduction_min']}"}),
        ]
    )

    overall = table8["overall"]
    overall_gate = gates["C_overall"]
    for metric in ("tp", "fp", "fn", "precision", "recall", "f1"):
        suffix = "max" if metric in {"fp", "fn"} else "min"
        threshold = overall_gate[f"{metric}_{suffix}"]
        passed = overall[metric] <= threshold if suffix == "max" else overall[metric] >= threshold
        groups["C"].append(
            _check(f"C_{metric}", passed, overall[metric], f"{'<=' if suffix == 'max' else '>='} {threshold}")
        )

    context_gate = gates["D_context"]
    context_deltas: dict[str, float] = {}
    for field in ("condition", "constraint", "exception"):
        drop = parent_table8["per_field"][field]["f1"] - table8["per_field"][field]["f1"]
        context_deltas[field] = drop
        threshold = context_gate[f"{field}_f1_drop_max"]
        groups["D"].append(
            _check(f"D_{field}_f1_drop", drop <= threshold, drop, f"<= {threshold}")
        )

    route_diff = _parent_route_diff(attempts, parent_attempts)
    summary = summarize_evaluation(report)
    parent_summary = summarize_evaluation(parent_report)
    segmentation = summary["clause_segmentation"]
    coverage = summary["semantic_coverage"]
    edges = report["structural_encoding"]["actor_action_edges"]
    full_gate = gates["E_full_regression"]
    call_count = int(report["cost_accounting"]["llm_call_count"])
    groups["E"].extend(
        [
            _check("E01_clause_identity_exact_parent", route_diff["same_clause_keys"] and route_diff["clause_span_mismatches"] == 0 and route_diff["alignment_mismatches"] == 0, route_diff, "exact v10-A"),
            _check("E02_modality_predictions_exact_parent", route_diff["modality_mismatches"] == 0, route_diff["modality_mismatches"], 0),
            _check("E03_modality_route_counts_exact_parent", runtime["modality_route_counts"] == parent_runtime["modality_route_counts"], runtime["modality_route_counts"], parent_runtime["modality_route_counts"]),
            _check("E04_predicted_clauses", segmentation["predicted_count"] == full_gate["predicted_clause_count"], segmentation["predicted_count"], full_gate["predicted_clause_count"]),
            _check("E05_aligned_clauses", segmentation["aligned_match_count"] == full_gate["aligned_clause_count"], segmentation["aligned_match_count"], full_gate["aligned_clause_count"]),
            _check("E06_alignment_f1_exact", segmentation["alignment_f1"] == full_gate["alignment_f1"], segmentation["alignment_f1"], full_gate["alignment_f1"]),
            _check("E07_exact_segmentation_f1_exact", segmentation["exact_f1"] == full_gate["exact_segmentation_f1"], segmentation["exact_f1"], full_gate["exact_segmentation_f1"]),
            _check("E08_presence_recall", coverage["gold_required_presence_recall"] >= full_gate["presence_recall_min"], coverage["gold_required_presence_recall"], f">= {full_gate['presence_recall_min']}"),
            _check("E09_complete_record_rate", coverage["complete_record_rate"] >= full_gate["complete_record_rate_min"], coverage["complete_record_rate"], f">= {full_gate['complete_record_rate_min']}"),
            _check("E10_hallucinated_field_rate", coverage["hallucinated_field_rate"] <= full_gate["hallucinated_field_rate_max"], coverage["hallucinated_field_rate"], f"<= {full_gate['hallucinated_field_rate_max']}"),
            _check("E11_edge_fp", edges["fp"] <= full_gate["edge_fp_max"], edges["fp"], f"<= {full_gate['edge_fp_max']}"),
            _check("E12_schema_valid_rate", coverage["schema_valid_rate"] == full_gate["schema_valid_rate"], coverage["schema_valid_rate"], full_gate["schema_valid_rate"]),
            _check("E13_no_llm_api_network", call_count == 0, {"llm_calls": call_count, "api_error_rate": coverage["api_error_rate"], "network_calls": 0}, {"llm_calls": 0, "api_error_rate": 0.0, "network_calls": 0}),
            _check("E14_segmentation_metrics_exact_parent", segmentation == parent_summary["clause_segmentation"], segmentation, parent_summary["clause_segmentation"]),
        ]
    )

    fields = report["primary_metrics"]["fields"]
    parent_fields = parent_report["primary_metrics"]["fields"]
    evaluator_gate = gates["F_main_evaluator"]
    actor_token_drop = (
        parent_fields["actor"]["token_overlap_micro"]["f1"]
        - fields["actor"]["token_overlap_micro"]["f1"]
    )
    action_token_drop = (
        parent_fields["action"]["token_overlap_micro"]["f1"]
        - fields["action"]["token_overlap_micro"]["f1"]
    )
    groups["F"].extend(
        [
            _check("F01_actor_token_f1_drop", actor_token_drop <= evaluator_gate["actor_token_f1_drop_max"], actor_token_drop, f"<= {evaluator_gate['actor_token_f1_drop_max']}"),
            _check("F02_action_token_f1_drop", action_token_drop <= evaluator_gate["action_token_f1_drop_max"], action_token_drop, f"<= {evaluator_gate['action_token_f1_drop_max']}"),
            _check("F03_complete_record_rate", coverage["complete_record_rate"] >= evaluator_gate["complete_record_rate_min"], coverage["complete_record_rate"], f">= {evaluator_gate['complete_record_rate_min']}"),
            _check("F04_schema_valid_rate", coverage["schema_valid_rate"] == evaluator_gate["schema_valid_rate"], coverage["schema_valid_rate"], evaluator_gate["schema_valid_rate"]),
        ]
    )

    gate_pass = {name: all(check["pass"] for check in checks) for name, checks in groups.items()}
    failed = [check["name"] for checks in groups.values() for check in checks if not check["pass"]]
    return {
        "schema_version": "b5_promotion_gate_report@1.0.0",
        "promotion_recommended": not failed,
        "decision": "promotion_recommended_user_review_required" if not failed else "valid_negative_development_candidate",
        "parent_remains": "s27_estg150_b0_enhanced_v10a",
        "active_registry_modified": False,
        "gate_family_pass": gate_pass,
        "checks_by_family": groups,
        "failed_gates": failed,
        "actor_action_combined": {"candidate": combined, "parent": combined_parent},
        "actor_action_improvement_options": improvement_options,
        "context_f1_drop": context_deltas,
        "main_evaluator_actor_action": {
            field: {
                "strict_exact": fields[field]["strict_exact"],
                "safe_normalized": fields[field]["safe_normalized"],
                "token_overlap_micro": fields[field]["token_overlap_micro"],
                "token_overlap_macro": fields[field]["token_overlap_macro"],
            }
            for field in ("actor", "action")
        },
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
            config.get("run_id") != "s27_estg150_b0_enhanced_b5"
            or config.get("method", {}).get("method_variant") != METHOD_VARIANT
            or config.get("claim_scope") != "development"
            or config.get("method", {}).get("paper_faithful_b0") is not False
            or config.get("safety", {}).get("llm_api_called") is not False
            or config.get("safety", {}).get("network_allowed") is not False
            or config.get("safety", {}).get("b4_lexicon_loaded") is not False
            or config.get("safety", {}).get("active_registry_modified") is not False
            or config.get("safety", {}).get("b6_bert_started") is not False
        ):
            raise Estg150B0DevelopmentError("B5 config identity or safety changed")
        prereg_path, prereg = _verify_preregistration(config_path, config)
        layer_e = _check_spec(config["inputs"]["human_correction_layer_e"], "Layer E")
        membership = _check_spec(config["inputs"]["membership_hashes"], "membership")
        freeze_receipt = _check_spec(config["inputs"]["annotation_freeze_receipt"], "S2.2 freeze receipt")
        parent_manifest_path = _check_spec(config["inputs"]["v10a_parent_manifest"], "v10-A manifest")
        parent_attempts_path = _check_spec(config["inputs"]["v10a_parent_attempts"], "v10-A attempts")
        parent_evaluation_path = _check_spec(config["inputs"]["v10a_parent_evaluation"], "v10-A evaluation")
        parent_table8_path = _check_spec(config["inputs"]["v10a_parent_table8"], "v10-A Table8")
        _check_spec(config["inputs"]["b4_negative_manifest"], "B4 negative manifest")
        _check_spec(config["method"]["s2_6_config"], "S2.6 classifier config")
        _check_spec(config["method"]["v3_parent_tregex"], "v3 Tregex registry")
        _check_spec(config["method"]["b5_operation_registry"], "B5 operation registry")
        _check_spec(config["method"]["v2_lexicon_manifest"], "v2 lexicon manifest")
        _check_spec(config["method"]["fixed_scope_resolver"], "v10 scope resolver")
        _check_spec(config["method"]["unchanged_production_multi_bridge"], "production Multi bridge")
        _check_spec(config["method"]["active_registry_read_only"], "active registry")
        _check_spec(config["synthetic_gate"]["fixture"], "B5 synthetic fixture")
        evaluator_path = _check_spec(config["evaluator"], "S2.10 evaluator v3")
        registry_proof = validate_b5_registry(ROOT)
        output_dir = (ROOT / config["output"]["directory"]).resolve()
        output_dir.relative_to((ROOT / "outputs/development").resolve())
        if output_dir.exists():
            raise Estg150B0DevelopmentError(f"refusing to overwrite: {output_dir}")

        gold, source_records = build_canonical_gold_records(layer_e, membership)
        evaluator_contract = load_evaluator_contract(evaluator_path)
        parent_attempts = _load_array(parent_attempts_path)
        parent_report = load_object(parent_evaluation_path)
        parent_table8 = load_object(parent_table8_path)
        parent_manifest = load_object(parent_manifest_path)
        (ROOT / ".tmp").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="s27_estg150_b0_enhanced_b5-", dir=ROOT / ".tmp"
        ) as raw_work:
            attempts, runtime = run_b0_batch_b5(
                ROOT,
                source_records,
                runtime_home=args.runtime_home,
                work_dir=Path(raw_work),
                device=args.device,
            )
            report = _evaluate(
                gold,
                attempts,
                contract=evaluator_contract,
                dataset_id=config["dataset_id"],
            )
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
                    "schema_version": "estg150_b0_enhanced_b5_manifest@1.0.0",
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
                    "b4_inheritance": "none_valid_negative_only",
                    "hypothesis": config["method"]["hypothesis_boundary"],
                    "attribution": {
                        "context_spans_emitted_pre_surgery": True,
                        "direct_target": "prevent_context_pollution_of_post_surgery_action_actor",
                        "primary_metrics": ["actor", "action", "overall_precision"],
                        "constraint_metric_role": "side_effect_observation_only",
                    },
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
                    "registry_proof": registry_proof,
                    "tracks": {
                        "all150": summarize_evaluation(report),
                        "sun_table8_any_overlap_diagnostic": table8,
                        "main_evaluator_actor_action": gate_report[
                            "main_evaluator_actor_action"
                        ],
                    },
                    "runtime": runtime,
                    "promotion": {
                        "promotion_recommended": gate_report["promotion_recommended"],
                        "decision": gate_report["decision"],
                        "gate_family_pass": gate_report["gate_family_pass"],
                        "failed_gates": gate_report["failed_gates"],
                        "parent_remains": "s27_estg150_b0_enhanced_v10a",
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
        print(
            json.dumps(
                {
                    "run_id": config["run_id"],
                    "output_dir": str(output_dir),
                    "promotion": manifest["promotion"],
                    "actor": table8["per_field"]["actor"],
                    "action": table8["per_field"]["action"],
                    "overall": table8["overall"],
                    "bridge": {
                        key: runtime[key]
                        for key in (
                            "raw_match_count",
                            "surgery_attempted",
                            "surgery_accepted",
                            "surgery_rejected",
                            "post_surgery_action_matches",
                            "post_surgery_actor_matches",
                        )
                    },
                    "llm_calls": 0,
                    "network_calls": 0,
                    "formal": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (Estg150B0DevelopmentError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"EStG-150 B5 development run failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
