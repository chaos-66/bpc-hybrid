"""Run the isolated Sun B0 mini regression pipeline; never runs all 150 rows."""

from __future__ import annotations

import argparse
import json
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
)
from bpc_hybrid.estg150_b0_sun_paper import (  # noqa: E402
    load_marker_parameter,
)
from bpc_hybrid.estg150_b0_sun_paper_v2 import (  # noqa: E402
    BRIDGE_CLASS,
    METHOD_VARIANT,
    run_b0_batch_sun_semantics_v2,
    write_semantics_v2_rule_plan,
)
from bpc_hybrid.stage2_sun_table8_compatible import (  # noqa: E402
    evaluate_sun_table8_literal_overlap,
)


DEFAULT_CONFIG = ROOT / "configs/models/estg150_b0_sun_mini_pipeline_v2.json"


def _write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _check_spec(spec: Mapping[str, Any], label: str) -> Path:
    path = (ROOT / str(spec.get("path", ""))).resolve()
    expected = spec.get("sha256")
    if not path.is_file() or not isinstance(expected, str) or sha256_file(path) != expected:
        raise Estg150B0DevelopmentError(f"{label} is missing or hash-mismatched")
    return path


def _filter_by_ids(rows: Sequence[Mapping[str, Any]], ids: Sequence[str]) -> list[dict[str, Any]]:
    by_id = {str(row["sample_id"]): dict(row) for row in rows}
    missing = [sample_id for sample_id in ids if sample_id not in by_id]
    if missing:
        raise Estg150B0DevelopmentError(f"mini panel IDs missing: {missing}")
    return [by_id[sample_id] for sample_id in ids]


def _field_prediction_counts(attempts: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    result = {
        "modality": 0,
        "actor": 0,
        "action": 0,
        "condition": 0,
        "constraint": 0,
        "exception": 0,
    }
    for attempt in attempts:
        record = attempt["record"]
        for clause in record["clauses"]:
            result["modality"] += len(clause["modality"].get("evidence", []))
            for singular, plural in (
                ("actor", "actors"),
                ("action", "actions"),
                ("condition", "conditions"),
                ("constraint", "constraints"),
                ("exception", "exceptions"),
            ):
                result[singular] += len(clause.get(plural, []))
    return result


def _overlap_duplicate_count(attempts: Sequence[Mapping[str, Any]], field: str) -> int:
    plural = {
        "actor": "actors",
        "action": "actions",
        "condition": "conditions",
        "constraint": "constraints",
        "exception": "exceptions",
    }[field]
    count = 0
    for attempt in attempts:
        for clause in attempt["record"]["clauses"]:
            spans = clause.get(plural, [])
            for index, left in enumerate(spans):
                if any(
                    index != other
                    and int(left["start"]) < int(right["end"])
                    and int(right["start"]) < int(left["end"])
                    for other, right in enumerate(spans)
                ):
                    count += 1
    return count


def _metric_view(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "per_field": {
            field: {
                key: values[key]
                for key in (
                    "extracted",
                    "ground_truth",
                    "matched_predictions",
                    "matched_ground_truth",
                    "precision",
                    "recall",
                    "f1",
                )
            }
            for field, values in metrics["per_field"].items()
        },
        "overall": metrics["overall"],
    }


def _metric_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in before["per_field"]:
        result[field] = {
            key: after["per_field"][field][key] - before["per_field"][field][key]
            for key in ("extracted", "precision", "recall", "f1")
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--runtime-home", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    try:
        config_path = args.config.resolve()
        config = load_object(config_path)
        if (
            config.get("schema_version") != "estg150_b0_sun_mini_pipeline@1.0.0"
            or config.get("task_id") != "S2.7-B0-SUN-MINI-V2"
            or config.get("claim_scope") != "diagnostic_only_not_performance"
            or config.get("method", {}).get("method_variant") != METHOD_VARIANT
            or config.get("method", {}).get("full_150_run_enabled") is not False
            or config.get("safety", {}).get("llm_api_called") is not False
        ):
            raise Estg150B0DevelopmentError("mini-pipeline config identity changed")

        inputs = config["inputs"]
        layer_e = _check_spec(inputs["human_correction_layer_e"], "Layer E")
        membership = _check_spec(inputs["membership_hashes"], "membership hashes")
        freeze_receipt = _check_spec(
            inputs["annotation_freeze_receipt"], "annotation freeze receipt"
        )
        v1_attempts_path = _check_spec(
            inputs["v1_development_attempts"], "v1 development attempts"
        )
        _check_spec(inputs["v1_development_manifest"], "v1 development manifest")
        method = config["method"]
        _check_spec(method["s2_6_config"], "S2.6 classifier binding")
        registry_path = _check_spec(method["pattern_registry"], "v2 rule registry")
        bridge_path = _check_spec(method["bridge"], "v2 bridge")
        for field, spec in method["marker_parameter"]["category_files"].items():
            _check_spec(spec, f"{field} marker parameter")
        _check_spec(config["evaluator"], "Sun literal evaluator")

        panel_ids = list(config["panel"]["sample_ids"])
        if len(panel_ids) != len(set(panel_ids)) or len(panel_ids) >= 150:
            raise Estg150B0DevelopmentError("mini panel must be unique and smaller than 150")
        gold, source_records = build_canonical_gold_records(layer_e, membership)
        panel_gold = _filter_by_ids(gold, panel_ids)
        panel_sources = _filter_by_ids(source_records, panel_ids)
        v1_attempts_payload = json.loads(v1_attempts_path.read_text(encoding="utf-8"))
        if not isinstance(v1_attempts_payload, list):
            raise Estg150B0DevelopmentError("v1 development attempts must be a list")
        v1_attempts = _filter_by_ids(v1_attempts_payload, panel_ids)

        registry = load_object(registry_path)
        markers, _ = load_marker_parameter(
            ROOT, method["marker_parameter"]["category_files"]
        )
        ROOT.joinpath(".tmp").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="sun-mini-plan-", dir=ROOT / ".tmp") as raw:
            plan_path = Path(raw) / "plan.tsv"
            write_semantics_v2_rule_plan(registry, markers, plan_path)
            plan_lines = plan_path.read_text(encoding="utf-8").splitlines()
        actor_lines = [line for line in plan_lines if line.startswith("actor\t")]
        method_contract = (
            bool(actor_lines)
            and all("NP=actor < (__ < " in line for line in actor_lines)
            and all("NP=actor <<" not in line for line in actor_lines)
            and registry["execution_semantics"]["context_capture_tree"]
            == "independent_fresh_copy_of_original_tree_per_field"
        )
        if not method_contract:
            raise Estg150B0DevelopmentError("Sun method-contract gate failed")

        with tempfile.TemporaryDirectory(prefix="sun-mini-run-", dir=ROOT / ".tmp") as raw:
            v2_attempts, runtime = run_b0_batch_sun_semantics_v2(
                ROOT,
                panel_sources,
                runtime_home=args.runtime_home,
                work_dir=Path(raw),
                s26_config_rel=method["s2_6_config"]["path"],
                registry_rel=method["pattern_registry"]["path"],
                marker_specs=method["marker_parameter"]["category_files"],
                device=args.device,
            )

        v1_metrics = evaluate_sun_table8_literal_overlap(
            panel_gold,
            v1_attempts,
            dataset_id=f"{config['dataset_id']}:mini-regression-panel",
            method_id="sun_rule_only:b0_sun_paper_spec_v1",
        )
        v2_metrics = evaluate_sun_table8_literal_overlap(
            panel_gold,
            v2_attempts,
            dataset_id=f"{config['dataset_id']}:mini-regression-panel",
            method_id=f"sun_rule_only:{METHOD_VARIANT}",
        )
        field_counts = _field_prediction_counts(v2_attempts)
        required_fields = set(config["panel"]["required_fields"])
        gates = {
            "method_contract": method_contract,
            "panel_membership": [row["sample_id"] for row in panel_sources] == panel_ids,
            "all_attempts_valid": all(
                attempt.get("request_status") == "ok"
                and attempt.get("record", {}).get("validation", {}).get("schema_valid") is True
                and attempt.get("record", {}).get("validation", {}).get("cross_field_valid") is True
                for attempt in v2_attempts
            ),
            "six_field_surface_present": required_fields == set(field_counts)
            and all(field_counts[field] > 0 for field in required_fields),
            "independent_context_runtime": runtime.get("bridge_class") == BRIDGE_CLASS,
            "no_llm": all(
                attempt.get("runtime", {}).get("llm_call_performed") is False
                for attempt in v2_attempts
            ),
            "full_150_not_run": len(v2_attempts) == len(panel_ids) < 150,
        }
        regression_gates = {
            field: {
                "precision_not_lower": (
                    v2_metrics["per_field"][field]["precision"]
                    >= v1_metrics["per_field"][field]["precision"]
                ),
                "recall_not_lower": (
                    v2_metrics["per_field"][field]["recall"]
                    >= v1_metrics["per_field"][field]["recall"]
                ),
            }
            for field in config["panel"]["required_fields"]
        }
        structural_passed = all(gates.values())
        regression_passed = all(
            check
            for field_gates in regression_gates.values()
            for check in field_gates.values()
        )
        regressed_fields = [
            field
            for field, field_gates in regression_gates.items()
            if not all(field_gates.values())
        ]

        report = {
            "schema_version": "sun_b0_mini_pipeline_manifest@1.0.0",
            "run_id": config["run_id"],
            "task_id": config["task_id"],
            "status": (
                "passed_diagnostic_only"
                if structural_passed and regression_passed
                else "blocked_field_regression"
            ),
            "claim_scope": config["claim_scope"],
            "is_formal_performance_result": False,
            "full_150_run_performed": False,
            "panel": {
                "sample_ids": panel_ids,
                "sample_count": len(panel_ids),
                "selection_role": config["panel"]["selection_role"],
                "metric_threshold_used_as_gate": True,
                "metric_regression_tolerance": config["panel"][
                    "metric_regression_tolerance"
                ],
            },
            "gates": gates,
            "regression_gates": regression_gates,
            "regressed_fields": regressed_fields,
            "bindings": {
                "config_sha256": sha256_file(config_path),
                "layer_e_sha256": sha256_file(layer_e),
                "membership_sha256": sha256_file(membership),
                "freeze_receipt_sha256": sha256_file(freeze_receipt),
                "registry_sha256": sha256_file(registry_path),
                "bridge_sha256": sha256_file(bridge_path),
                "implementation_sha256": sha256_file(
                    ROOT / "src/bpc_hybrid/estg150_b0_sun_paper_v2.py"
                ),
            },
            "runtime": runtime,
            "field_prediction_counts": field_counts,
            "overlap_duplicate_counts": {
                "actor_v1": _overlap_duplicate_count(v1_attempts, "actor"),
                "actor_v2": _overlap_duplicate_count(v2_attempts, "actor"),
                "exception_v1": _overlap_duplicate_count(v1_attempts, "exception"),
                "exception_v2": _overlap_duplicate_count(v2_attempts, "exception"),
            },
            "diagnostic_metrics": {
                "v1": _metric_view(v1_metrics),
                "v2": _metric_view(v2_metrics),
                "v2_minus_v1": _metric_delta(v1_metrics, v2_metrics),
            },
            "safety": {
                **config["safety"],
                "gold_read_only": True,
                "llm_call_count": 0,
                "row_level_predictions_persisted": False,
            },
        }
        if args.write_manifest:
            output_path = (ROOT / config["output"]["manifest"]).resolve()
            try:
                output_path.relative_to((ROOT / "outputs/reports").resolve())
            except ValueError as exc:
                raise Estg150B0DevelopmentError(
                    "mini manifest must remain under outputs/reports"
                ) from exc
            _write_json_exclusive(output_path, report)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if structural_passed and regression_passed else 2
    except (
        Estg150B0DevelopmentError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"Sun B0 mini pipeline failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
