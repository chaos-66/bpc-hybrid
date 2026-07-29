"""Run the single preregistered EStG-150 B2a2 development evaluation."""

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
from bpc_hybrid.estg150_b0_development_b2a2 import (  # noqa: E402
    METHOD_ID,
    METHOD_VARIANT,
    run_b0_batch_b2a2,
    sun_table8_any_overlap_diagnostic,
)
from bpc_hybrid.stage2_evaluation_v3 import (  # noqa: E402
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    validate_evaluation_report,
)


DEFAULT_CONFIG = ROOT / "configs/models/estg150_b0_enhanced_s27_b2a2.json"
V10_ATTEMPTS = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json"
V10_EVALUATION = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/evaluation_all150.json"
V10_TABLE8 = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/sun_table8_any_overlap_diagnostic.json"


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
    path = root / str(spec["path"])
    if not path.is_file() or sha256_file(path) != spec.get("sha256"):
        raise Estg150B0DevelopmentError(f"{label} is missing or hash-mismatched")
    return path


def _verify_preregistration(config_path: Path, config: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    prereg_rel = config.get("method", {}).get("preregistration", {}).get("path")
    if not isinstance(prereg_rel, str):
        raise Estg150B0DevelopmentError("B2a2 config is missing preregistration path")
    prereg_path = ROOT / prereg_rel
    prereg = load_object(prereg_path)
    if (
        prereg.get("schema_version") != "b0_enhanced_b2a2_preregistration@1.0.0"
        or prereg.get("status") != "preregistered_frozen_before_single_all150"
        or prereg.get("run_id") != "s27_estg150_b0_enhanced_b2a2"
        or prereg.get("single_all150_run_max") != 1
    ):
        raise Estg150B0DevelopmentError("B2a2 preregistration identity/status changed")
    config_binding = prereg.get("config") or {}
    if (
        config_binding.get("path") != str(config_path.relative_to(ROOT)).replace("\\", "/")
        or config_binding.get("sha256") != sha256_file(config_path)
    ):
        raise Estg150B0DevelopmentError("B2a2 config is not frozen by preregistration")
    for group in ("module_bindings", "resource_bindings"):
        bindings = prereg.get(group)
        if not isinstance(bindings, Mapping) or not bindings:
            raise Estg150B0DevelopmentError(f"B2a2 preregistration lacks {group}")
        for name, meta in bindings.items():
            if not isinstance(meta, Mapping):
                raise Estg150B0DevelopmentError(f"invalid preregistration binding: {name}")
            path = ROOT / str(meta.get("path"))
            if (
                not path.is_file()
                or sha256_file(path) != meta.get("sha256")
                or path.stat().st_size != meta.get("bytes")
            ):
                raise Estg150B0DevelopmentError(f"preregistration binding drifted: {name}")
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
        raise Estg150B0DevelopmentError(
            "B2a2 evaluation report invalid: " + "; ".join(errors)
        )
    return report


def _fallback_keys(attempts: Sequence[Mapping[str, Any]]) -> set[tuple[str, str]]:
    return {
        (str(attempt["sample_id"]), str(clause["clause_id"]))
        for attempt in attempts
        for clause in attempt["record"].get("clauses") or []
        if clause.get("modality", {}).get("route") == "record_level_classifier_fallback"
    }


def _check(name: str, passed: bool, actual: Any, expected: Any) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "actual": actual, "expected": expected}


def evaluate_promotion_gates(
    *,
    report: Mapping[str, Any],
    attempts: Sequence[Mapping[str, Any]],
    runtime: Mapping[str, Any],
    table8: Mapping[str, Any],
    parent_report: Mapping[str, Any],
    parent_attempts: Sequence[Mapping[str, Any]],
    parent_table8: Mapping[str, Any],
    gates: Mapping[str, Any],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    current_fallback = _fallback_keys(attempts)
    parent_fallback = _fallback_keys(parent_attempts)
    new_fallback = current_fallback - parent_fallback
    contradictory = sum(
        "reject_loose_definition_record_even_if_def"
        in str(clause.get("modality", {}).get("diagnostic", {}).get("b2a2_rule", ""))
        for attempt in attempts
        for clause in attempt["record"].get("clauses") or []
    )
    checks.extend(
        [
            _check(
                "A1_record_level_classifier_fallback_count",
                len(current_fallback) <= int(gates["record_level_classifier_fallback_max"]),
                len(current_fallback),
                f"<= {gates['record_level_classifier_fallback_max']}",
            ),
            _check(
                "A2_fallback_set_is_v10a_subset",
                current_fallback <= parent_fallback,
                {"current": len(current_fallback), "outside_parent": len(new_fallback)},
                "current subset of v10-A",
            ),
            _check(
                "A3_supported_new_record_fallback_count",
                int(runtime.get("supported_record_fallback_count", -1))
                <= int(gates["supported_new_record_fallback_max"]),
                int(runtime.get("supported_record_fallback_count", -1)),
                gates["supported_new_record_fallback_max"],
            ),
            _check(
                "A4_placeholder_classifier_count",
                int(runtime.get("placeholder_classifier_count", -1))
                == int(gates["placeholder_classifier_count"]),
                int(runtime.get("placeholder_classifier_count", -1)),
                gates["placeholder_classifier_count"],
            ),
            _check(
                "A5_contradictory_record_fallback_path_count",
                contradictory <= int(gates["contradictory_record_fallback_path_max"]),
                contradictory,
                gates["contradictory_record_fallback_path_max"],
            ),
        ]
    )

    modality = report["primary_metrics"]["modality"]
    definition = modality["per_class"]["definition"]
    definition_gates = gates["definition"]
    for suffix, metric, op in (
        ("tp", "tp", lambda actual, expected: actual >= expected),
        ("fp", "fp", lambda actual, expected: actual <= expected),
        ("fn", "fn", lambda actual, expected: actual <= expected),
        ("precision", "precision", lambda actual, expected: actual >= expected),
        ("recall", "recall", lambda actual, expected: actual >= expected),
        ("f1", "f1", lambda actual, expected: actual >= expected),
    ):
        gate_key = suffix + ("_min" if suffix in {"tp", "precision", "recall", "f1"} else "_max")
        actual = float(definition[metric])
        expected = float(definition_gates[gate_key])
        checks.append(_check(f"B_definition_{suffix}", op(actual, expected), actual, expected))

    micro = modality["micro"]
    overall_gates = gates["overall_modality"]
    for suffix, metric in (("tp", "tp"), ("precision", "precision"), ("recall", "recall"), ("f1", "f1")):
        actual = float(micro[metric])
        expected = float(overall_gates[f"{suffix}_min"])
        checks.append(_check(f"C_overall_{suffix}", actual >= expected, actual, expected))

    max_drop = float(gates["other_class_f1_drop_max"])
    parent_per_class = parent_report["primary_metrics"]["modality"]["per_class"]
    for label in ("obligation", "permission", "prohibition"):
        parent_f1 = float(parent_per_class[label]["f1"])
        current_f1 = float(modality["per_class"][label]["f1"])
        drop = parent_f1 - current_f1
        checks.append(
            _check(
                f"D_{label}_f1_drop",
                drop <= max_drop,
                {"parent": parent_f1, "current": current_f1, "drop": drop},
                f"<= {max_drop}",
            )
        )

    structural = report["structural_encoding"]
    parent_structural = parent_report["structural_encoding"]
    segmentation = structural["clause_segmentation"]
    locked = gates["locked_to_v10a"]
    checks.extend(
        [
            _check(
                "E1_predicted_clause_count",
                segmentation["predicted_count"] == locked["predicted_clauses"],
                segmentation["predicted_count"],
                locked["predicted_clauses"],
            ),
            _check(
                "E2_aligned_clause_count",
                segmentation["aligned_match_count"] == locked["aligned_clauses"],
                segmentation["aligned_match_count"],
                locked["aligned_clauses"],
            ),
            _check(
                "E3_alignment_f1_equal_v10a",
                segmentation["alignment_f1"]
                == parent_structural["clause_segmentation"]["alignment_f1"],
                segmentation["alignment_f1"],
                parent_structural["clause_segmentation"]["alignment_f1"],
            ),
            _check(
                "E4_exact_segmentation_f1_equal_v10a",
                segmentation["exact_f1"]
                == parent_structural["clause_segmentation"]["exact_f1"],
                segmentation["exact_f1"],
                parent_structural["clause_segmentation"]["exact_f1"],
            ),
            _check(
                "E5_table8_all_fields_and_overall_equal_v10a",
                table8 == parent_table8,
                table8,
                "exact v10-A Table8 diagnostic object",
            ),
            _check(
                "E6_primary_field_metrics_equal_v10a",
                report["primary_metrics"]["fields"]
                == parent_report["primary_metrics"]["fields"],
                report["primary_metrics"]["fields"],
                "exact v10-A field metrics",
            ),
        ]
    )
    coverage = report["semantic_coverage"]
    parent_coverage = parent_report["semantic_coverage"]
    for name in (
        "gold_required_presence_recall",
        "complete_record_rate",
        "hallucinated_field_rate",
    ):
        checks.append(
            _check(
                f"E7_{name}_equal_v10a",
                coverage[name] == parent_coverage[name],
                coverage[name],
                parent_coverage[name],
            )
        )
    checks.extend(
        [
            _check(
                "E8_actor_action_edges_equal_v10a",
                structural["actor_action_edges"] == parent_structural["actor_action_edges"],
                structural["actor_action_edges"],
                parent_structural["actor_action_edges"],
            ),
            _check(
                "E9_schema_valid_rate",
                structural["schema_valid_rate"] == float(locked["schema_valid_rate"]),
                structural["schema_valid_rate"],
                locked["schema_valid_rate"],
            ),
        ]
    )
    failed = [check["name"] for check in checks if not check["pass"]]
    return {
        "schema_version": "b2a2_promotion_gate_report@1.0.0",
        "promote": not failed,
        "decision": "promotion_eligible_user_decision_required" if not failed else "not_promoted_negative_evidence",
        "checks": checks,
        "failed_gates": failed,
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
            config.get("run_id") != "s27_estg150_b0_enhanced_b2a2"
            or config.get("method", {}).get("method_id") != METHOD_VARIANT
            or config.get("method", {}).get("method_variant") != METHOD_VARIANT
            or config.get("claim_scope") != "development"
            or config.get("method", {}).get("paper_faithful_b0") is not False
            or config.get("safety", {}).get("llm_api_called") is not False
            or config.get("safety", {}).get("independent82_read_or_used") is not False
        ):
            raise Estg150B0DevelopmentError("B2a2 config identity or safety changed")
        prereg_path, prereg = _verify_preregistration(config_path, config)
        layer_e = _check_spec(ROOT, config["inputs"]["human_correction_layer_e"], "Layer E")
        membership = _check_spec(ROOT, config["inputs"]["membership_hashes"], "membership")
        freeze_receipt = _check_spec(
            ROOT, config["inputs"]["annotation_freeze_receipt"], "S2.2 freeze receipt"
        )
        _check_spec(ROOT, config["inputs"]["v10a_parent_manifest"], "v10-A manifest")
        _check_spec(ROOT, config["inputs"]["b2a_negative_manifest"], "B2a manifest")
        _check_spec(ROOT, config["inputs"]["route_diagnostic"], "B2a2 route diagnostic")
        _check_spec(ROOT, config["method"]["s2_6_config"], "S2.6 classifier config")
        evaluator_path = _check_spec(ROOT, config["evaluator"], "S2.10 evaluator v3")
        output_dir = (ROOT / config["output"]["directory"]).resolve()
        output_dir.relative_to((ROOT / "outputs/development").resolve())
        if output_dir.exists():
            raise Estg150B0DevelopmentError(f"refusing to overwrite: {output_dir}")

        gold, source_records = build_canonical_gold_records(layer_e, membership)
        evaluator_contract = load_evaluator_contract(evaluator_path)
        parent_attempts = _load_array(V10_ATTEMPTS)
        parent_report = load_object(V10_EVALUATION)
        parent_table8 = load_object(V10_TABLE8)
        (ROOT / ".tmp").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="s27_estg150_b0_enhanced_b2a2-", dir=ROOT / ".tmp"
        ) as raw_work:
            attempts, runtime = run_b0_batch_b2a2(
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
                    "schema_version": "estg150_b0_enhanced_b2a2_manifest@1.0.0",
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
                    "negative_evidence_run": "s27_estg150_b0_enhanced_b2a",
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
                        "evaluation_all150": {
                            "path": evaluation_path.name,
                            "sha256": sha256_file(evaluation_path),
                        },
                        "sun_table8_any_overlap_diagnostic": {
                            "path": table8_path.name,
                            "sha256": sha256_file(table8_path),
                        },
                        "promotion_gate_report": {
                            "path": gate_path.name,
                            "sha256": sha256_file(gate_path),
                        },
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
                    "route_counts": runtime["modality_route_counts"],
                    "all150": manifest["tracks"]["all150"],
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
        print(f"EStG-150 B2a2 development run failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
