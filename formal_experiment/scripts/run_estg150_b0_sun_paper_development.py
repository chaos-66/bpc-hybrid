"""Run the Sun Section 4.2.2 paper-spec B0 reconstruction on frozen EStG-150."""

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
    load_object,
    sha256_file,
)
from bpc_hybrid.estg150_b0_sun_paper import (  # noqa: E402
    METHOD_ID,
    METHOD_VARIANT,
    run_b0_batch_sun_paper,
)
from bpc_hybrid.stage2_evaluation_v3 import membership_sha256  # noqa: E402
from bpc_hybrid.stage2_sun_table8_compatible import (  # noqa: E402
    evaluate_sun_table8_literal_overlap,
)


DEFAULT_CONFIG = ROOT / "configs/models/estg150_b0_sun_paper_s27_v1.json"


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _check_spec(root: Path, spec: dict[str, Any], label: str) -> Path:
    path = (root / spec["path"]).resolve()
    if not path.is_file() or sha256_file(path) != spec["sha256"]:
        raise Estg150B0DevelopmentError(f"{label} is missing or hash-mismatched")
    return path


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
            config.get("schema_version") != "estg150_b0_sun_paper_development@1.0.0"
            or config.get("task_id") != "S2.7-B0-SUN-PAPER-DEV"
            or config.get("claim_scope") != "development"
            or config.get("method", {}).get("method_variant") != METHOD_VARIANT
            or config.get("method", {}).get("paper_faithful_reconstruction") is not True
            or config.get("method", {}).get("exact_original_reproduction") is not False
            or config.get("safety", {}).get("llm_api_called") is not False
        ):
            raise Estg150B0DevelopmentError("Sun paper development config identity changed")

        inputs = config["inputs"]
        layer_e = _check_spec(ROOT, inputs["human_correction_layer_e"], "Layer E")
        membership = _check_spec(ROOT, inputs["membership_hashes"], "membership hashes")
        freeze_receipt = _check_spec(
            ROOT, inputs["annotation_freeze_receipt"], "S2.2 freeze receipt"
        )
        method = config["method"]
        _check_spec(ROOT, method["s2_6_config"], "S2.6 classifier binding")
        pattern_registry = _check_spec(ROOT, method["pattern_registry"], "paper rule registry")
        bridge = _check_spec(ROOT, method["bridge"], "paper Java bridge")
        for field, spec in method["marker_parameter"]["category_files"].items():
            _check_spec(ROOT, spec, f"{field} marker parameter")
        evaluator_path = _check_spec(ROOT, config["evaluator"], "Sun literal evaluator")
        literature_path = _check_spec(ROOT, config["literature_source"], "Sun primary source")
        evaluator = load_object(evaluator_path)
        if (
            evaluator.get("evaluator_id") != "sun_table8_literal_overlap_v2"
            or evaluator.get("evaluation_unit") != "statement"
            or evaluator.get("clause_alignment_required") is not False
            or evaluator.get("assignment") != "none_independent_overlap_coverage"
        ):
            raise Estg150B0DevelopmentError("Sun literal evaluator identity changed")

        output_dir = (
            args.output_dir.resolve()
            if args.output_dir
            else (ROOT / config["output"]["directory"]).resolve()
        )
        try:
            output_dir.relative_to((ROOT / "outputs/development").resolve())
        except ValueError as exc:
            raise Estg150B0DevelopmentError(
                "Sun paper development output must remain under outputs/development"
            ) from exc
        if output_dir.exists():
            raise Estg150B0DevelopmentError(f"refusing to overwrite: {output_dir}")

        gold, source_records = build_canonical_gold_records(layer_e, membership)
        ROOT.joinpath(".tmp").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=f"{config['run_id']}-", dir=ROOT / ".tmp"
        ) as raw_work:
            attempts, runtime = run_b0_batch_sun_paper(
                ROOT,
                source_records,
                runtime_home=args.runtime_home,
                work_dir=Path(raw_work),
                s26_config_rel=method["s2_6_config"]["path"],
                registry_rel=method["pattern_registry"]["path"],
                marker_specs=method["marker_parameter"]["category_files"],
                device=args.device,
            )
        metrics = evaluate_sun_table8_literal_overlap(
            gold,
            attempts,
            dataset_id=config["dataset_id"],
            method_id=f"{METHOD_ID}:{METHOD_VARIANT}",
        )

        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
        if staging.exists():
            raise Estg150B0DevelopmentError(f"staging path already exists: {staging}")
        staging.mkdir()
        try:
            attempts_path = staging / "b0_attempts.json"
            metrics_path = staging / "metrics.json"
            _write_json(attempts_path, attempts)
            _write_json(metrics_path, metrics)
            manifest = {
                "schema_version": "estg150_b0_sun_paper_development_manifest@1.0.0",
                "run_id": config["run_id"],
                "task_id": config["task_id"],
                "status": "succeeded_development_not_formal",
                "dataset_id": config["dataset_id"],
                "method_id": METHOD_ID,
                "method_variant": METHOD_VARIANT,
                "paper_faithful_reconstruction": True,
                "exact_original_reproduction": False,
                "is_formal_performance_result": False,
                "claim_scope": "development_sun_table8_literal_overlap_view",
                "input_binding": {
                    "layer_e_sha256": sha256_file(layer_e),
                    "membership_hashes_sha256": sha256_file(membership),
                    "freeze_receipt_sha256": sha256_file(freeze_receipt),
                    "canonical_gold_membership_sha256": membership_sha256(gold),
                    "config_sha256": sha256_file(config_path),
                    "literature_source_sha256": sha256_file(literature_path),
                    "pattern_registry_sha256": sha256_file(pattern_registry),
                    "bridge_sha256": sha256_file(bridge),
                    "evaluator_sha256": sha256_file(evaluator_path),
                },
                "method_alignment": {
                    "source_location": config["literature_source"]["method_location"],
                    "evaluation_location": config["literature_source"]["evaluation_location"],
                    "published_rule_order": method["extraction_order"],
                    "dependency_gated_actor": True,
                    "real_tsurgeon_context_removal": True,
                    "all_remaining_vp_action_extraction": True,
                    "same_field_any_nonempty_overlap_evaluation": True,
                    "excluded_project_extensions": method["excluded_project_extensions"],
                    "marker_parameter_is_original": False,
                    "unavailable_original_assets": config["reproduction_boundary"]["unavailable_original_assets"],
                },
                "runtime": runtime,
                "metrics": metrics,
                "artifacts": {
                    "attempts": {"path": "b0_attempts.json", "sha256": sha256_file(attempts_path)},
                    "metrics": {"path": "metrics.json", "sha256": sha256_file(metrics_path)},
                },
                "safety": {
                    **config["safety"],
                    "gold_read_only": True,
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
                    "per_field": metrics["per_field"],
                    "overall": metrics["overall"],
                    "llm_calls": 0,
                    "formal": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (Estg150B0DevelopmentError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"Sun paper B0 development run failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
