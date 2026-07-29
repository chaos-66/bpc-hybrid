"""Run EStG-150 B0 enhanced development evaluation (versioned, non-formal).

Uses clause-level German modality routing, enhanced phrase patterns, multi-match
bridge, and the frozen S2.10-E v3 evaluator. Does not overwrite v1 outputs,
does not call LLM/API, and does not publish formal Gold.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

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
from bpc_hybrid.estg150_b0_development_b2a import (  # noqa: E402
    METHOD_ID,
    METHOD_VARIANT,
    run_b0_batch_b2a,
    sun_table8_any_overlap_diagnostic,
)
from bpc_hybrid.stage2_evaluation_v3 import (  # noqa: E402
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    validate_evaluation_report,
)

DEFAULT_CONFIG = ROOT / "configs/models/estg150_b0_enhanced_s27_b2a.json"


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _check_spec(root: Path, spec: dict[str, Any], label: str) -> Path:
    path = root / spec["path"]
    if not path.is_file() or sha256_file(path) != spec["sha256"]:
        raise Estg150B0DevelopmentError(f"{label} is missing or hash-mismatched")
    return path


def _evaluate(
    gold: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    *,
    contract: dict[str, Any],
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
            "development evaluation report invalid: " + "; ".join(errors)
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--runtime-home", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    try:
        config_path = args.config.resolve()
        config = load_object(config_path)
        if (
            config.get("schema_version") != "estg150_b0_enhanced_development@1.0.0"
            or config.get("task_id") != "S2.7-B0-ENHANCED-DEV"
            or config.get("claim_scope") != "development"
            or config.get("method", {}).get("method_id") not in {METHOD_VARIANT, "b0_enhanced_b2a", "b0_enhanced_b2a"}
            or config.get("safety", {}).get("llm_api_called") is not False
        ):
            raise Estg150B0DevelopmentError("enhanced development config identity or safety changed")
        inputs = config["inputs"]
        layer_e = _check_spec(ROOT, inputs["human_correction_layer_e"], "Layer E")
        membership = _check_spec(ROOT, inputs["membership_hashes"], "membership hashes")
        freeze_receipt = _check_spec(
            ROOT, inputs["annotation_freeze_receipt"], "S2.2 freeze receipt"
        )
        independence_path = _check_spec(
            ROOT, inputs["independence_audit"], "independence audit"
        )
        _check_spec(ROOT, config["method"]["s2_6_config"], "S2.6 config")
        evaluator_path = _check_spec(ROOT, config["evaluator"], "S2.10 evaluator v3")

        prereg_spec = config.get("method", {}).get("preregistration")
        if not isinstance(prereg_spec, dict):
            raise Estg150B0DevelopmentError("B2a config missing method.preregistration")
        prereg_path = _check_spec(ROOT, prereg_spec, "B2a preregistration")
        prereg = load_object(prereg_path)
        for rel, meta in (prereg.get("module_bindings") or {}).items():
            actual = sha256_file(ROOT / rel)
            if actual != meta.get("sha256"):
                raise Estg150B0DevelopmentError(f"prereg module hash mismatch: {rel}")
        for _k, meta in (prereg.get("resource_bindings") or {}).items():
            if isinstance(meta, dict) and "path" in meta:
                if sha256_file(ROOT / meta["path"]) != meta.get("sha256"):
                    raise Estg150B0DevelopmentError(f"prereg resource hash mismatch: {meta['path']}")

        output_dir = (
            args.output_dir.resolve()
            if args.output_dir
            else (ROOT / config["output"]["directory"]).resolve()
        )
        try:
            output_dir.relative_to((ROOT / "outputs/development").resolve())
        except ValueError as exc:
            raise Estg150B0DevelopmentError(
                "B0 enhanced development output must remain under outputs/development"
            ) from exc
        if output_dir.exists():
            raise Estg150B0DevelopmentError(f"refusing to overwrite: {output_dir}")

        gold, source_records = build_canonical_gold_records(layer_e, membership)
        independence_rows = load_jsonl(independence_path)
        independent_ids = {
            row["sample_id"] for row in independence_rows if row.get("classification") == "独立"
        }
        if len(independent_ids) != 82:
            raise Estg150B0DevelopmentError(
                f"independent sensitivity membership must be 82, got {len(independent_ids)}"
            )
        evaluator_contract = load_evaluator_contract(evaluator_path)
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        ROOT.joinpath(".tmp").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=f"{config['run_id']}-", dir=ROOT / ".tmp"
        ) as raw_work:
            work_dir = Path(raw_work)
            attempts, runtime = run_b0_batch_b2a(
                ROOT,
                source_records,
                runtime_home=args.runtime_home,
                work_dir=work_dir,
                device=args.device,
            )
            report_all = _evaluate(
                gold,
                attempts,
                contract=evaluator_contract,
                dataset_id=config["dataset_id"],
            )
            gold_by_id = {row["sample_id"]: row for row in gold}
            attempts_by_id = {row["sample_id"]: row for row in attempts}
            ordered_independent = [
                row["sample_id"] for row in gold if row["sample_id"] in independent_ids
            ]
            report_independent = _evaluate(
                [gold_by_id[sample_id] for sample_id in ordered_independent],
                [attempts_by_id[sample_id] for sample_id in ordered_independent],
                contract=evaluator_contract,
                dataset_id=config["dataset_id"] + "_independent82_sensitivity",
            )
            diagnostic = sun_table8_any_overlap_diagnostic(gold, attempts)

            staging = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
            if staging.exists():
                raise Estg150B0DevelopmentError(f"staging path already exists: {staging}")
            staging.mkdir()
            try:
                attempts_path = staging / "b0_attempts.json"
                all_path = staging / "evaluation_all150.json"
                independent_path = staging / "evaluation_independent82.json"
                diag_path = staging / "sun_table8_any_overlap_diagnostic.json"
                _write_json(attempts_path, attempts)
                _write_json(all_path, report_all)
                _write_json(independent_path, report_independent)
                _write_json(diag_path, diagnostic)
                manifest = {
                    "schema_version": "estg150_b0_enhanced_development_manifest@1.0.0",
                    "run_id": config["run_id"],
                    "task_id": config["task_id"],
                    "status": "succeeded_development_not_formal",
                    "method_id": METHOD_ID,
                    "method_variant": config.get("method", {}).get("method_variant", METHOD_VARIANT),
                    "paper_faithful_b0": False,
                    "dataset_id": config["dataset_id"],
                    "claim_scope": "development",
                    "is_formal_performance_result": False,
                    "prior_v1_preserved": True,
                    "input_binding": {
                        "layer_e_sha256": sha256_file(layer_e),
                        "membership_hashes_sha256": sha256_file(membership),
                        "freeze_receipt_sha256": sha256_file(freeze_receipt),
                        "canonical_gold_membership_sha256": membership_sha256(gold),
                        "canonical_gold_copy_persisted": False,
                        "config_sha256": sha256_file(config_path),
                    },
                    "tracks": {
                        "all150": summarize_evaluation(report_all),
                        "independent82_sensitivity": summarize_evaluation(report_independent),
                        "sun_table8_any_overlap_diagnostic": diagnostic["overall"],
                    },
                    "runtime": runtime,
                    "artifacts": {
                        "attempts": {
                            "path": "b0_attempts.json",
                            "sha256": sha256_file(attempts_path),
                        },
                        "evaluation_all150": {
                            "path": "evaluation_all150.json",
                            "sha256": sha256_file(all_path),
                        },
                        "evaluation_independent82": {
                            "path": "evaluation_independent82.json",
                            "sha256": sha256_file(independent_path),
                        },
                        "sun_table8_any_overlap_diagnostic": {
                            "path": "sun_table8_any_overlap_diagnostic.json",
                            "sha256": sha256_file(diag_path),
                        },
                    },
                    "route_boundaries": config["route_boundaries"],
                    "safety": {
                        **config["safety"],
                        "gold_read_only": True,
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
                    "method_id": METHOD_ID,
                    "method_variant": str(config.get("method", {}).get("method_variant", METHOD_VARIANT)),
                    "all150": manifest["tracks"]["all150"],
                    "independent82_sensitivity": manifest["tracks"]["independent82_sensitivity"],
                    "sun_table8_any_overlap_diagnostic": diagnostic["overall"],
                    "llm_calls": 0,
                    "formal": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (Estg150B0DevelopmentError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"EStG-150 B0 enhanced development run failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
