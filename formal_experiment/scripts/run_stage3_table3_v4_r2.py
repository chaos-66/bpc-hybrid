# -*- coding: utf-8 -*-
"""R2 offline runner for the scoped Table 3 matrix.

The real D1 predictions are reused; no LLM/API call is made.  This runner
imports the frozen R1 runner as an implementation module, swaps in the strict
R2 temporal projection v3, augments every order signal with a non-scoring
failure diagnostic, and then rewrites the R2 output/manifest version labels
after the frozen R1 writer has persisted the computed outputs.

Only code/config within ``formal_experiment/`` is touched.  No reference,
Gold, control, target rule/type, or current-case mutation is read by the
inference path.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.sun_stage3.order_failure_diagnostics_v1 import (  # noqa: E402
    build_sun_order_diagnostic,
    build_winter_order_diagnostic,
)
from bpc_hybrid.sun_stage3 import temporal_projection_v3  # noqa: E402

R2_CONFIG = ROOT / "configs/stage3_table3_v4_execution_r2.json"
R2_OUT_DIR = ROOT / "outputs/development/stage3_table3_v4_r2"


def _load_r1_runner() -> Any:
    path = ROOT / "scripts/run_stage3_table3_v4_r1.py"
    spec = importlib.util.spec_from_file_location("stage3_table3_v4_r1_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load R1 runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _augment_sun_payload(payload: Mapping[str, Any], rule_records: Mapping[str, Any],
                         model: Any, scorer: Any) -> None:
    for rule_id, record in (rule_records or {}).items():
        signals = (payload.get("signals_by_rule") or {}).get(rule_id)
        if not isinstance(signals, Mapping):
            continue
        signal = signals.get("out_of_order")
        if not isinstance(signal, dict):
            continue
        diagnostic = build_sun_order_diagnostic(record, signal, model, scorer)
        signal["order_diagnostic"] = _jsonable(diagnostic)
        if str(signal.get("status")) == "unknown" and int(signal.get("denominator") or 0) == 0:
            if signal.get("reason") is not None:
                signal.setdefault("raw_reason", signal.get("reason"))
            signal["reason"] = diagnostic["category"]


def _augment_winter_payload(payload: Mapping[str, Any]) -> None:
    for signals in (payload.get("signals_by_rule") or {}).values():
        if not isinstance(signals, Mapping):
            continue
        signal = signals.get("out_of_order")
        if not isinstance(signal, dict):
            continue
        signal["order_diagnostic"] = _jsonable(build_winter_order_diagnostic(signal))


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def _install_r2_projection(r1: Any) -> None:
    r1.CONFIG = R2_CONFIG
    r1.OUT_DIR = R2_OUT_DIR
    r1.SCHEMA_VERSION = "stage3_table3_v4_r2_predictions@1.0.0"
    r1.project_record_order_relations = temporal_projection_v3.project_record_order_relations

    original_sun = r1._sun_case_payload

    def sun_payload_r2(item: Mapping[str, Any], rule_records: Mapping[str, Any],
                       checker: Any, nlp: Any, contract: Any,
                       model_cache: dict[str, Any]) -> dict[str, Any]:
        payload = original_sun(item, rule_records, checker, nlp, contract, model_cache)
        path = str(item["bpmn_path"])
        model = model_cache[path]["model"]
        _augment_sun_payload(payload, rule_records, model, checker.scorer)
        return payload

    r1._sun_case_payload = sun_payload_r2

    original_winter = r1._winter_case_payload

    def winter_payload_r2(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = original_winter(*args, **kwargs)
        _augment_winter_payload(payload)
        return payload

    r1._winter_case_payload = winter_payload_r2


def _postprocess_outputs(out_dir: Path, r2_manifest: dict[str, Any]) -> dict[str, Any]:
    predictions_path = out_dir / "predictions.json"
    signals_path = out_dir / "signals_matrix.json"
    rule_records_path = out_dir / "rule_records.json"
    global_roles_path = out_dir / "global_role_candidates.json"

    predictions = json.loads(predictions_path.read_text(encoding="utf-8"))
    predictions["schema_version"] = "stage3_table3_v4_r2_predictions@1.0.0"
    predictions["dataset_id"] = "stage3_scoped_gdpr_v4_r2"
    _write_json(predictions_path, predictions)

    signals_doc = json.loads(signals_path.read_text(encoding="utf-8"))
    signals_doc["schema_version"] = "stage3_table3_v4_r2_signals@1.0.0"
    by_key: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    actual_case_ids: set[str] = set()
    actual_rule_ids: set[str] = set()
    for row in predictions.get("records") or []:
        actual_case_ids.add(str(row.get("case_id")))
        for rule_id, checks in (row.get("signals_by_rule") or {}).items():
            actual_rule_ids.add(str(rule_id))
            for check_type, signal in (checks or {}).items():
                by_key[(str(row.get("row_method_id")), str(row.get("case_id")),
                        str(rule_id), str(check_type))] = signal
    for flat in signals_doc.get("signals") or []:
        key = (str(flat.get("method")), str(flat.get("case_id")),
               str(flat.get("rule_id")), str(flat.get("check_type")))
        nested = by_key.get(key)
        if nested is not None:
            if isinstance(nested, Mapping) and "order_diagnostic" in nested:
                flat["order_diagnostic"] = nested["order_diagnostic"]
            if "raw_reason" in nested:
                flat["raw_reason"] = nested["raw_reason"]
    _write_json(signals_path, signals_doc)

    outputs = {
        "predictions": {"path": _rel(predictions_path),
                        "sha256": _sha_file(predictions_path)},
        "signals_matrix": {"path": _rel(signals_path),
                           "sha256": _sha_file(signals_path)},
        "rule_records": {"path": _rel(rule_records_path),
                         "sha256": _sha_file(rule_records_path)},
        "global_role_candidates": {"path": _rel(global_roles_path),
                                   "sha256": _sha_file(global_roles_path)},
    }
    code_paths = [
        Path(__file__),
        ROOT / "scripts/run_stage3_table3_v4_r1.py",
        ROOT / "src/bpc_hybrid/sun_stage3/temporal_projection_v1.py",
        ROOT / "src/bpc_hybrid/sun_stage3/temporal_projection_v2.py",
        ROOT / "src/bpc_hybrid/sun_stage3/temporal_projection_v3.py",
        ROOT / "src/bpc_hybrid/sun_stage3/order_failure_diagnostics_v1.py",
        ROOT / "src/bpc_hybrid/sun_stage3/no_gate_checker_v1.py",
        ROOT / "src/bpc_hybrid/sun_stage3/sun_scorer.py",
        ROOT / "src/bpc_hybrid/sun_stage3/gdpr_capsule_converter.py",
        ROOT / "src/bpc_hybrid/stage3_sun_style_checker.py",
        ROOT / "src/bpc_hybrid/winter_stage3/winter_model.py",
        ROOT / "src/bpc_hybrid/winter_stage3/winter_clause.py",
        ROOT / "src/bpc_hybrid/winter_stage3/winter_pair.py",
        ROOT / "src/bpc_hybrid/winter_stage3/winter_similarity.py",
        ROOT / "src/bpc_hybrid/winter_stage3/global_roles.py",
    ]
    r2_manifest = dict(r2_manifest)
    r2_manifest["schema_version"] = "stage3_table3_v4_r2_run@1.0.0"
    r2_manifest["run_id"] = "stage3_table3_v4_r2"
    r2_manifest["command"] = "python formal_experiment/scripts/run_stage3_table3_v4_r2.py"
    r2_manifest["outputs"] = outputs
    r2_manifest["code_sha256"] = {
        str(path.relative_to(ROOT)).replace("\\", "/"): _sha_file(path)
        for path in code_paths if path.is_file()
    }
    r2_manifest["actual_output_case_ids"] = sorted(actual_case_ids)
    r2_manifest["actual_output_rule_ids"] = sorted(actual_rule_ids)
    r2_manifest["method_projection_versions"] = {
        "sun": "sun_stage3_temporal_projection_v3@1.0.0",
        "ours": "sun_stage3_temporal_projection_v3@1.0.0",
    }
    r2_manifest["one_strict_projection_for_sun_and_ours"] = True
    r2_manifest["order_diagnostic_module"] = "src/bpc_hybrid/sun_stage3/order_failure_diagnostics_v1.py"
    r2_manifest["llm_api_calls"] = 0
    r2_manifest["network_calls"] = 0
    return r2_manifest


def run(*, out_dir: Path = R2_OUT_DIR, nlp_model: str = "en_core_web_sm",
        overwrite: bool = False) -> dict[str, Any]:
    r1 = _load_r1_runner()
    _install_r2_projection(r1)
    manifest = r1.run(out_dir=out_dir, nlp_model=nlp_model, overwrite=overwrite)
    manifest = _postprocess_outputs(out_dir, manifest)
    _write_json(out_dir / "run_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=R2_OUT_DIR)
    parser.add_argument("--nlp-model", default="en_core_web_sm")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    manifest = run(out_dir=args.out_dir, nlp_model=args.nlp_model, overwrite=args.overwrite)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

