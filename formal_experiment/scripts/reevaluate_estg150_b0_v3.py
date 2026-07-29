"""Re-evaluate immutable EStG-150 B0 attempts with the S2.10-E v1.2 evaluator.

This command does not rerun CoreNLP, BERT, an LLM, or any network operation.
It reads the exact v1 B0 attempts, rebuilds the read-only canonical Gold view,
and writes a new development-only aggregate report while preserving v1.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    Estg150B0DevelopmentError,
    build_canonical_gold_records,
    load_jsonl,
    load_object,
    sha256_file,
    summarize_evaluation,
)
from bpc_hybrid.stage2_evaluation_v3 import (  # noqa: E402
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    validate_evaluation_report,
)


SOURCE_CONFIG = ROOT / "configs/models/estg150_b0_development_s27.json"
SOURCE_RUN_DIR = ROOT / "outputs/development/s27_estg150_b0_development_v1"
SOURCE_MANIFEST = SOURCE_RUN_DIR / "manifest.json"
SOURCE_ATTEMPTS = SOURCE_RUN_DIR / "b0_attempts.json"
V3_CONTRACT = ROOT / "configs/stage2_evaluator_s210_v3.json"
V3_REPORT_SCHEMA = ROOT / "configs/schemas/stage2_evaluation_report_v3.schema.json"
V3_IMPLEMENTATION = ROOT / "src/bpc_hybrid/stage2_evaluation_v3.py"
V3_VERIFIER = ROOT / "scripts/verify_stage2_evaluator_s210_v3.py"
V3_RECEIPT = ROOT / "outputs/reports/s210_stage2_evaluator_contract_synthetic_v3.manifest.json"
REEVALUATOR = ROOT / "scripts/reevaluate_estg150_b0_v3.py"
DEFAULT_OUTPUT = ROOT / "outputs/development/s27_estg150_b0_v3_evaluation_v1"
EXPECTED_SOURCE_MANIFEST_SHA256 = "7ab968a5da3fb482e8135977cc323828c8c682db0379bd95c1dacabdc6af8746"
EXPECTED_ATTEMPTS_SHA256 = "0ab15cdaeba1cfc3e1e9f702586152521e6532ca2fc21e6192fb887ef8cb4278"


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _check_v3_receipt() -> dict[str, Any]:
    receipt = load_object(V3_RECEIPT)
    if (
        receipt.get("schema_version") != "s210_evaluator_verification_manifest@1.2.0"
        or receipt.get("status") != "succeeded_candidate_for_future_development"
        or receipt.get("safety", {}).get("paper_score_targeting_used") is not False
        or receipt.get("safety", {}).get("threshold_search_used") is not False
    ):
        raise Estg150B0DevelopmentError("S2.10-E v3 exact receipt identity changed")
    expected_paths = {
        "contract": V3_CONTRACT,
        "report_schema": V3_REPORT_SCHEMA,
        "implementation": V3_IMPLEMENTATION,
        "verifier": V3_VERIFIER,
    }
    for name, path in expected_paths.items():
        artifact = receipt.get("artifacts", {}).get(name, {})
        if artifact.get("path") != path.relative_to(ROOT).as_posix():
            raise Estg150B0DevelopmentError(f"v3 receipt path changed: {name}")
        if artifact.get("sha256") != sha256_file(path):
            raise Estg150B0DevelopmentError(f"v3 receipt hash mismatch: {name}")
    return receipt


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
        method_id="sun_rule_only",
        expected_membership_sha256=membership_sha256(gold),
        claim_scope="development",
        formal_ready=False,
    )
    errors = validate_evaluation_report(report)
    if errors:
        raise Estg150B0DevelopmentError("v3 report invalid: " + "; ".join(errors))
    return report


def _summary(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = summarize_evaluation(report)
    summary["modality_micro"] = {
        key: report["primary_metrics"]["modality"]["micro"][key]
        for key in ("precision", "recall", "f1")
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        output_dir = args.output_dir.resolve()
        try:
            output_dir.relative_to((ROOT / "outputs/development").resolve())
        except ValueError as exc:
            raise Estg150B0DevelopmentError(
                "v3 development output must remain under outputs/development"
            ) from exc
        if output_dir.exists():
            raise Estg150B0DevelopmentError(f"refusing to overwrite: {output_dir}")
        if sha256_file(SOURCE_MANIFEST) != EXPECTED_SOURCE_MANIFEST_SHA256:
            raise Estg150B0DevelopmentError("source B0 development manifest changed")
        if sha256_file(SOURCE_ATTEMPTS) != EXPECTED_ATTEMPTS_SHA256:
            raise Estg150B0DevelopmentError("source B0 attempts changed")
        source_manifest = load_object(SOURCE_MANIFEST)
        if source_manifest.get("artifacts", {}).get("attempts", {}).get("sha256") != EXPECTED_ATTEMPTS_SHA256:
            raise Estg150B0DevelopmentError("source manifest no longer binds the B0 attempts")
        receipt = _check_v3_receipt()
        config = load_object(SOURCE_CONFIG)
        layer_e = ROOT / config["inputs"]["human_correction_layer_e"]["path"]
        membership_path = ROOT / config["inputs"]["membership_hashes"]["path"]
        independence_path = ROOT / config["inputs"]["independence_audit"]["path"]
        for label, path, expected in (
            ("Layer E", layer_e, config["inputs"]["human_correction_layer_e"]["sha256"]),
            ("membership", membership_path, config["inputs"]["membership_hashes"]["sha256"]),
            ("independence", independence_path, config["inputs"]["independence_audit"]["sha256"]),
        ):
            if sha256_file(path) != expected:
                raise Estg150B0DevelopmentError(f"{label} input hash changed")

        gold, _ = build_canonical_gold_records(layer_e, membership_path)
        attempts = json.loads(SOURCE_ATTEMPTS.read_text(encoding="utf-8"))
        if not isinstance(attempts, list):
            raise Estg150B0DevelopmentError("B0 attempts root must be an array")
        contract = load_evaluator_contract(V3_CONTRACT)
        report_all = _evaluate(
            gold,
            attempts,
            contract=contract,
            dataset_id=config["dataset_id"],
        )

        independent_ids = {
            row["sample_id"]
            for row in load_jsonl(independence_path)
            if row.get("classification") == "独立"
        }
        if len(independent_ids) != 82:
            raise Estg150B0DevelopmentError(
                f"independent sensitivity membership must be 82, got {len(independent_ids)}"
            )
        gold_by_id = {row["sample_id"]: row for row in gold}
        attempts_by_id = {row["sample_id"]: row for row in attempts}
        ordered_independent = [
            row["sample_id"] for row in gold if row["sample_id"] in independent_ids
        ]
        report_independent = _evaluate(
            [gold_by_id[sample_id] for sample_id in ordered_independent],
            [attempts_by_id[sample_id] for sample_id in ordered_independent],
            contract=contract,
            dataset_id=config["dataset_id"] + "_independent82_sensitivity",
        )

        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
        if staging.exists():
            raise Estg150B0DevelopmentError(f"staging path exists: {staging}")
        staging.mkdir()
        try:
            all_path = staging / "evaluation_all150.json"
            independent_path = staging / "evaluation_independent82.json"
            _write_json(all_path, report_all)
            _write_json(independent_path, report_independent)
            manifest = {
                "schema_version": "estg150_b0_v3_reevaluation_manifest@1.0.0",
                "task_id": "S2.7-B0-DEV-REEVAL",
                "run_id": "s27_estg150_b0_v3_evaluation_v1",
                "status": "succeeded_development_not_formal",
                "method_id": "sun_rule_only",
                "dataset_id": config["dataset_id"],
                "claim_scope": "development",
                "is_formal_performance_result": False,
                "models_rerun": False,
                "supersedes_result_interpretation_of": source_manifest["run_id"],
                "prior_run_preserved_as_provenance": True,
                "input_binding": {
                    "source_run_manifest": {
                        "path": SOURCE_MANIFEST.relative_to(ROOT).as_posix(),
                        "sha256": sha256_file(SOURCE_MANIFEST),
                    },
                    "immutable_b0_attempts": {
                        "path": SOURCE_ATTEMPTS.relative_to(ROOT).as_posix(),
                        "sha256": sha256_file(SOURCE_ATTEMPTS),
                    },
                    "layer_e_sha256": sha256_file(layer_e),
                    "canonical_gold_membership_sha256": membership_sha256(gold),
                    "v3_contract_sha256": sha256_file(V3_CONTRACT),
                    "v3_report_schema_sha256": sha256_file(V3_REPORT_SCHEMA),
                    "v3_implementation_sha256": sha256_file(V3_IMPLEMENTATION),
                    "v3_verification_receipt": {
                        "path": V3_RECEIPT.relative_to(ROOT).as_posix(),
                        "sha256": sha256_file(V3_RECEIPT),
                        "report_payload_sha256": receipt["verification"]["report_payload_sha256"],
                    },
                    "reevaluator_sha256": sha256_file(REEVALUATOR),
                },
                "tracks": {
                    "all150": _summary(report_all),
                    "independent82_sensitivity": _summary(report_independent),
                },
                "artifacts": {
                    "evaluation_all150": {
                        "path": "evaluation_all150.json",
                        "sha256": sha256_file(all_path),
                    },
                    "evaluation_independent82": {
                        "path": "evaluation_independent82.json",
                        "sha256": sha256_file(independent_path),
                    },
                },
                "literature_comparison": {
                    "sun_locally_recorded_stage3_reference": {
                        "precision": 0.77,
                        "recall": 0.83,
                        "f1": 0.80,
                    },
                    "current_result_stage": "Stage 2 six-element extraction plus modality",
                    "reference_result_stage": "Stage 3 violation checking",
                    "datasets_and_gold_membership_identical": False,
                    "direct_numeric_comparison_valid": False,
                    "within_10_percentage_points_requirement_evaluated": False,
                    "difference_over_10_percentage_points_policy": "diagnostic_alert_only",
                    "acceptance_or_threshold_tuning_based_on_paper_score": False,
                },
                "interpretation": (
                    "The v1 exact-ID/exact-span evaluator materially undercounted B0 because method-local IDs "
                    "and near-identical clause boundaries could not align. V3 corrects that measurement defect. "
                    "Remaining errors are method/data errors and must not be hidden by evaluator tuning."
                ),
                "safety": {
                    "gold_read_only": True,
                    "source_attempts_read_only": True,
                    "formal_predictions_or_results_written": False,
                    "paper_score_targeting_used": False,
                    "threshold_search_used": False,
                    "llm_api_called": False,
                    "llm_call_count": 0,
                    "network_called": False,
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
                    "run_id": manifest["run_id"],
                    "output_dir": str(output_dir),
                    "all150_modality_micro": manifest["tracks"]["all150"]["modality_micro"],
                    "all150_modality_macro_f1": manifest["tracks"]["all150"]["modality_macro_f1"],
                    "all150_clause_alignment": {
                        key: manifest["tracks"]["all150"]["clause_segmentation"][key]
                        for key in ("alignment_precision", "alignment_recall", "alignment_f1")
                    },
                    "llm_calls": 0,
                    "formal": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (Estg150B0DevelopmentError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"EStG-150 B0 v3 re-evaluation failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
