"""Run the frozen v2-versus-v3 marker-only paired B0 comparison."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping


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
from bpc_hybrid.marker_lexicon_v3_pair import (  # noqa: E402
    FIELD_ORDER,
    MarkerLexiconPairError,
    build_paired_comparison,
)
from bpc_hybrid.stage2_evaluation_v3 import membership_sha256  # noqa: E402
from bpc_hybrid.stage2_sun_table8_compatible import (  # noqa: E402
    evaluate_sun_table8_literal_overlap,
)


DEFAULT_CONFIG = ROOT / "configs/models/estg150_b0_marker_lexicon_v3_paired_v1.json"
RUNTIME_FIELDS = ("actor", "condition", "constraint", "exception")


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _check_spec(root: Path, spec: Mapping[str, Any], label: str) -> Path:
    path = (root / str(spec.get("path", ""))).resolve()
    expected = spec.get("sha256")
    if not path.is_file() or not isinstance(expected, str) or sha256_file(path) != expected:
        raise Estg150B0DevelopmentError(f"{label} is missing or hash-mismatched")
    return path


def _validate_config(config: Mapping[str, Any]) -> None:
    if (
        config.get("schema_version") != "estg150_b0_marker_lexicon_paired@1.0.0"
        or config.get("task_id") != "S2.7-B0-MARKER-LEXICON-V3-PAIR"
        or config.get("claim_scope") != "development"
        or config.get("safety", {}).get("llm_api_called") is not False
        or config.get("safety", {}).get("network_allowed") is not False
    ):
        raise Estg150B0DevelopmentError("paired config identity changed")
    protocol = config.get("paired_protocol", {})
    if (
        protocol.get("sole_variable") != "method.marker_parameter.category_files"
        or tuple(protocol.get("zero_regression_fields", ())) != FIELD_ORDER
        or tuple(protocol.get("zero_regression_metrics", ())) != ("precision", "recall")
        or tuple(protocol.get("strict_improvement_targets", ()))
        != ("condition.precision", "constraint.recall")
    ):
        raise Estg150B0DevelopmentError("paired gate was changed")


def _validate_freeze(root: Path, config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    freeze = config["candidate_freeze"]
    _check_spec(root, freeze["source_snapshot"], "candidate source snapshot")
    manifest_path = _check_spec(root, freeze["manifest"], "candidate manifest")
    _check_spec(root, freeze["provenance_report"], "candidate provenance report")
    manifest = load_object(manifest_path)
    if (
        manifest.get("candidate_status") != "frozen_pre_evaluation"
        or manifest.get("lexicon_id") != freeze.get("lexicon_id")
        or manifest.get("combined_payload_sha256")
        != freeze.get("combined_payload_sha256")
    ):
        raise Estg150B0DevelopmentError("candidate freeze identity changed")
    category_files = freeze.get("category_files")
    if not isinstance(category_files, Mapping) or set(category_files) != {
        "modality",
        "actor",
        "action",
        "condition",
        "constraint",
        "exception",
    }:
        raise Estg150B0DevelopmentError("candidate must bind all six category artifacts")
    for field, spec in category_files.items():
        _check_spec(root, spec, f"candidate {field} category")
        manifest_spec = manifest["category_files"].get(field)
        if (
            not isinstance(manifest_spec, Mapping)
            or manifest_spec.get("sha256") != spec.get("sha256")
            or manifest_spec.get("entry_count") != spec.get("entry_count")
            or bool(spec.get("runtime_bound")) != (field in RUNTIME_FIELDS)
        ):
            raise Estg150B0DevelopmentError(f"candidate {field} freeze mismatch")
    return {field: dict(category_files[field]) for field in RUNTIME_FIELDS}


def _validate_baseline(
    root: Path, config: Mapping[str, Any]
) -> tuple[dict[str, Any], Path]:
    baseline_path = _check_spec(root, config["baseline_config"], "baseline config")
    baseline = load_object(baseline_path)
    method = baseline.get("method", {})
    if (
        baseline.get("schema_version") != "estg150_b0_sun_paper_development@1.0.0"
        or baseline.get("dataset_id") != config.get("dataset_id")
        or method.get("method_variant") != METHOD_VARIANT
        or method.get("paper_faithful_reconstruction") is not True
        or method.get("exact_original_reproduction") is not False
        or method.get("marker_parameter", {}).get("id") != "public_marker_lexicon_en_v2"
    ):
        raise Estg150B0DevelopmentError("baseline config identity changed")
    return baseline, baseline_path


def _artifact_record(path: Path) -> dict[str, Any]:
    return {"path": path.name, "sha256": sha256_file(path)}


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
        _validate_config(config)
        baseline, baseline_config_path = _validate_baseline(ROOT, config)
        candidate_markers = _validate_freeze(ROOT, config)

        method = baseline["method"]
        inputs = baseline["inputs"]
        layer_e = _check_spec(ROOT, inputs["human_correction_layer_e"], "Layer E")
        membership = _check_spec(ROOT, inputs["membership_hashes"], "membership hashes")
        freeze_receipt = _check_spec(
            ROOT, inputs["annotation_freeze_receipt"], "S2.2 freeze receipt"
        )
        s26_config = _check_spec(ROOT, method["s2_6_config"], "S2.6 classifier")
        pattern_registry = _check_spec(ROOT, method["pattern_registry"], "pattern registry")
        bridge = _check_spec(ROOT, method["bridge"], "Java bridge")
        evaluator_path = _check_spec(ROOT, baseline["evaluator"], "literal evaluator")
        literature_path = _check_spec(ROOT, baseline["literature_source"], "Sun paper")
        baseline_markers = method["marker_parameter"]["category_files"]
        if set(baseline_markers) != set(RUNTIME_FIELDS):
            raise Estg150B0DevelopmentError("baseline marker binding changed")
        for field, spec in baseline_markers.items():
            _check_spec(ROOT, spec, f"baseline {field} marker")

        output_dir = (
            args.output_dir.resolve()
            if args.output_dir
            else (ROOT / config["output"]["directory"]).resolve()
        )
        try:
            output_dir.relative_to((ROOT / "outputs/development").resolve())
        except ValueError as exc:
            raise Estg150B0DevelopmentError(
                "paired output must remain under outputs/development"
            ) from exc
        if output_dir.exists():
            raise Estg150B0DevelopmentError(f"refusing to overwrite: {output_dir}")

        gold, source_records = build_canonical_gold_records(layer_e, membership)
        (ROOT / ".tmp").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=f"{config['run_id']}-", dir=ROOT / ".tmp"
        ) as raw_work:
            work = Path(raw_work)
            baseline_attempts, baseline_runtime = run_b0_batch_sun_paper(
                ROOT,
                source_records,
                runtime_home=args.runtime_home,
                work_dir=work / "baseline",
                s26_config_rel=method["s2_6_config"]["path"],
                registry_rel=method["pattern_registry"]["path"],
                marker_specs=baseline_markers,
                device=args.device,
            )
            candidate_attempts, candidate_runtime = run_b0_batch_sun_paper(
                ROOT,
                source_records,
                runtime_home=args.runtime_home,
                work_dir=work / "candidate",
                s26_config_rel=method["s2_6_config"]["path"],
                registry_rel=method["pattern_registry"]["path"],
                marker_specs=candidate_markers,
                device=args.device,
            )
        evaluation_method = f"{METHOD_ID}:{METHOD_VARIANT}"
        baseline_metrics = evaluate_sun_table8_literal_overlap(
            gold,
            baseline_attempts,
            dataset_id=config["dataset_id"],
            method_id=evaluation_method,
        )
        candidate_metrics = evaluate_sun_table8_literal_overlap(
            gold,
            candidate_attempts,
            dataset_id=config["dataset_id"],
            method_id=evaluation_method,
        )
        comparison = build_paired_comparison(baseline_metrics, candidate_metrics)

        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
        if staging.exists():
            raise Estg150B0DevelopmentError(f"staging path already exists: {staging}")
        staging.mkdir()
        try:
            paths = {
                "baseline_attempts": staging / "baseline_attempts.json",
                "candidate_attempts": staging / "candidate_attempts.json",
                "baseline_metrics": staging / "baseline_metrics.json",
                "candidate_metrics": staging / "candidate_metrics.json",
                "comparison": staging / "comparison.json",
            }
            _write_json(paths["baseline_attempts"], baseline_attempts)
            _write_json(paths["candidate_attempts"], candidate_attempts)
            _write_json(paths["baseline_metrics"], baseline_metrics)
            _write_json(paths["candidate_metrics"], candidate_metrics)
            _write_json(paths["comparison"], comparison)
            manifest = {
                "schema_version": "estg150_b0_marker_lexicon_paired_manifest@1.0.0",
                "run_id": config["run_id"],
                "task_id": config["task_id"],
                "status": "succeeded_development_not_formal",
                "dataset_id": config["dataset_id"],
                "claim_scope": "development_paired_marker_parameter_comparison",
                "sole_variable": "marker_parameter_category_files",
                "input_binding": {
                    "config_sha256": sha256_file(config_path),
                    "baseline_config_sha256": sha256_file(baseline_config_path),
                    "layer_e_sha256": sha256_file(layer_e),
                    "membership_hashes_sha256": sha256_file(membership),
                    "freeze_receipt_sha256": sha256_file(freeze_receipt),
                    "canonical_gold_membership_sha256": membership_sha256(gold),
                    "literature_source_sha256": sha256_file(literature_path),
                    "s2_6_config_sha256": sha256_file(s26_config),
                    "pattern_registry_sha256": sha256_file(pattern_registry),
                    "bridge_sha256": sha256_file(bridge),
                    "evaluator_sha256": sha256_file(evaluator_path),
                    "candidate_source_sha256": config["candidate_freeze"]["source_snapshot"]["sha256"],
                    "candidate_manifest_sha256": config["candidate_freeze"]["manifest"]["sha256"],
                    "candidate_provenance_report_sha256": config["candidate_freeze"]["provenance_report"]["sha256"],
                },
                "pair_binding": {
                    "baseline_marker_id": "public_marker_lexicon_en_v2",
                    "candidate_marker_id": "public_marker_lexicon_en_v3",
                    "baseline_marker_sha256": baseline_runtime[
                        "marker_parameter_sha256"
                    ],
                    "candidate_marker_sha256": candidate_runtime[
                        "marker_parameter_sha256"
                    ],
                    "shared_b0_function": "run_b0_batch_sun_paper",
                    "shared_evaluator": "evaluate_sun_table8_literal_overlap",
                    "shared_gold_object": True,
                    "shared_source_records_object": True,
                    "shared_device": args.device,
                    "non_marker_method_components_identical": True,
                },
                "runtime": {
                    "baseline": baseline_runtime,
                    "candidate": candidate_runtime,
                },
                "gate": comparison["gate"],
                "artifacts": {
                    key: _artifact_record(path) for key, path in paths.items()
                },
                "safety": {
                    **config["safety"],
                    "gold_read_only": True,
                    "network_called": False,
                    "llm_call_count": 0,
                    "estimated_cost_usd": 0.0,
                    "created_no_overwrite": True,
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
                    "decision": comparison["gate"]["decision"],
                    "regressions": comparison["gate"]["regressions"],
                    "target_improvements": comparison["gate"]["target_improvements"],
                    "per_field": comparison["per_field"],
                    "llm_calls": 0,
                    "formal": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (
        Estg150B0DevelopmentError,
        MarkerLexiconPairError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"marker lexicon paired run failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
