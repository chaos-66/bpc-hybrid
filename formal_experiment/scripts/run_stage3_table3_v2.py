# -*- coding: utf-8 -*-
"""Run the repaired Stage-3 Table 3 controlled comparison (v2).

Zero API, zero network.  Reuses only persisted Stage-2 predictions and frozen
Stage-3 modules.  Predictions are persisted with all three detector signals
before the separate evaluator reads benchmark labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for candidate in (SRC,):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
)
from bpc_hybrid.stage3_table3_v2 import (  # noqa: E402
    ALLOWED_INFERENCE_ITEM_KEYS,
    METHODS,
    SCHEMA_VERSION,
    TYPES,
    build_converted_rule_records,
    load_json,
    load_regulation_text_index,
    normalize_sun_signal,
    project_inference_items,
    sha256_file,
    violated_types,
    winter_signals,
)

DEFAULT_VIEW = (
    ROOT / "data/development/stage3_synth"
    / "stage3_paired_benchmark_inference_view_v2.json"
)
DEFAULT_TEXT_VIEW = (
    ROOT / "data/development/stage3_synth"
    / "stage3_regulation_text_view_v2.json"
)
DEFAULT_STAGE2_INPUT = ROOT / "data/input/gdpr7_stage2_input_v1.json"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
SUN_CONFIG = ROOT / "configs/sun_stage3_development_v1.json"
WINTER_CONFIG = ROOT / "configs/winter_stage3_development_v1.json"
WINTER_LEXICON_DIR = (
    ROOT.parent / "references" / "winter_2020_model_check"
    / "model_check" / "input" / "files"
)
OUT_DIR = ROOT / "outputs/development/stage3_table3_v2"
PREDICTIONS_JSONL = OUT_DIR / "predictions.jsonl"
RUN_MANIFEST = OUT_DIR / "run_manifest.json"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _load_lexicon(name: str) -> list[str]:
    return [
        word.strip()
        for word in (WINTER_LEXICON_DIR / name).read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
        if word.strip()
    ]


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _code_hash(paths: list[Path]) -> dict[str, str]:
    return {
        path.resolve().relative_to(ROOT.resolve()).as_posix(): sha256_file(path)
        for path in paths if path.is_file()
    }


def _check_outputs(out_dir: Path, overwrite: bool) -> None:
    if out_dir.exists() and any(out_dir.iterdir()) and not overwrite:
        raise SystemExit(
            f"refusing to overwrite existing output directory {out_dir}; "
            "pass --overwrite only for a deliberate rerun"
        )


def run(
    *,
    view_path: Path = DEFAULT_VIEW,
    text_view_path: Path = DEFAULT_TEXT_VIEW,
    stage2_input_path: Path = DEFAULT_STAGE2_INPUT,
    out_dir: Path = OUT_DIR,
    nlp_model: str = "en_core_web_sm",
    overwrite: bool = False,
) -> dict[str, Any]:
    _check_outputs(out_dir, overwrite)
    view = load_json(view_path)
    if view.get("safety", {}).get("gold_labels_present") is not False:
        raise ValueError("inference view is not declared gold-blind")
    if view.get("safety", {}).get("pair_role_present") is not False:
        raise ValueError("inference view must not contain pair role")
    items = project_inference_items(view)
    if len(items) != len(view.get("items") or []):
        raise ValueError("some inference items were dropped by projection")

    regulation_texts = load_regulation_text_index(text_view_path)
    missing_rules = sorted({str(i["rule_id"]) for i in items}
                           - set(regulation_texts))
    if missing_rules:
        raise ValueError(f"missing regulation text for rules: {missing_rules}")

    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    sun_cfg = load_json(SUN_CONFIG)
    winter_cfg = load_json(WINTER_CONFIG)
    thresholds = sun_cfg["method"]["thresholds"]

    import spacy  # type: ignore

    nlp = spacy.load(nlp_model)

    from bpc_hybrid.sun_stage3.sun_model import SunProcessModel
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
    from bpc_hybrid.winter_stage3.winter_clause import (
        parse_regulation_paragraph,
    )
    from bpc_hybrid.winter_stage3.winter_model import (
        REACHABILITY_CORRECTED,
        parse_bpmn_file_winter,
    )
    from bpc_hybrid.winter_stage3.winter_pair import WinterPair
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity

    sim = WinterSimilarity(nlp)
    # One frozen scorer instance, one frozen threshold triple, both methods.
    scorer = SunScorer(
        sim,
        float(thresholds["tau"]),
        float(thresholds["gamma"]),
        float(thresholds["theta"]),
        nlp=nlp,
    )

    rule_records_by_method: dict[str, dict[str, dict[str, Any]]] = {}
    converter_summaries: dict[str, Any] = {}
    method_rule_ids = sorted({str(item["rule_id"]) for item in items})
    for method_id, method in METHODS.items():
        if method["predictions_path"] is None:
            continue
        records, summary = build_converted_rule_records(
            predictions_path=ROOT / str(method["predictions_path"]),
            sentence_input_path=stage2_input_path,
            expected_schema=str(method["expected_schema"]),
            rule_ids=method_rule_ids,
        )
        rule_records_by_method[method_id] = records
        converter_summaries[method_id] = summary

    signalwords = set(_load_lexicon("signalwords.txt"))
    sequencemarkers = set(_load_lexicon("sequencemarkers.txt"))
    stopwords = set(_load_lexicon("stopwords.txt"))

    bpmn_record_cache: dict[str, dict[str, Any]] = {}
    sun_model_cache: dict[str, Any] = {}
    winter_model_cache: dict[str, Any] = {}
    paragraph_cache: dict[str, Any] = {}

    def bpmn_record(path: str) -> dict[str, Any]:
        if path not in bpmn_record_cache:
            bpmn_record_cache[path] = parse_bpmn_file(
                ROOT / path, contract=contract)
        return bpmn_record_cache[path]

    def sun_model(path: str, process_id: str) -> Any:
        if path not in sun_model_cache:
            sun_model_cache[path] = SunProcessModel(
                process_id, bpmn_record(path), nlp)
        return sun_model_cache[path]

    def winter_model(path: str) -> Any:
        if path not in winter_model_cache:
            winter_model_cache[path] = parse_bpmn_file_winter(
                ROOT / path, nlp, stopwords,
                reachability_mode=REACHABILITY_CORRECTED)
        return winter_model_cache[path]

    def winter_paragraph(rule_id: str) -> Any:
        if rule_id not in paragraph_cache:
            paragraph_cache[rule_id] = parse_regulation_paragraph(
                rule_id,
                regulation_texts[rule_id],
                nlp,
                stopwords,
                signalwords,
                sequencemarkers,
                only_constraints=True,
            )
        return paragraph_cache[rule_id]

    prediction_rows: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda row: str(row["item_id"])):
        item_id = str(item["item_id"])
        pair_id = str(item["pair_id"])
        rule_id = str(item["rule_id"])
        process_id = str(item["process_id"])
        bpmn_path = str(item["bpmn_path"])

        for method_id, method in METHODS.items():
            if method_id == "winter_2020_native_wrapper":
                model = winter_model(bpmn_path)
                paragraph = winter_paragraph(rule_id)
                resources = {
                    str(process.participant).lower()
                    for process in model.processes
                    if str(process.participant or "").strip()
                }
                pair = WinterPair(
                    nlp,
                    sim,
                    model,
                    paragraph,
                    resources,
                    float(winter_cfg["method"]["gamma"]),
                    float(winter_cfg["method"]["delta"]),
                )
                signals = winter_signals(
                    pair=pair,
                    model=model,
                    paragraph=paragraph,
                    resource_set=resources,
                )
                extra = {
                    "winter_config_version": winter_cfg.get("config_version"),
                    "reachability_mode": REACHABILITY_CORRECTED,
                    "resource_set": sorted(resources),
                }
            else:
                record = rule_records_by_method[method_id].get(rule_id) or {}
                if record.get("failed"):
                    signals = {
                        t: {
                            "status": "unknown",
                            "raw_score": None,
                            "denominator": 0,
                            "observable": False,
                            "reason": "stage2_rule_record_failed",
                            "evidence": {
                                "failure_reasons": record.get(
                                    "failure_reasons") or []
                            },
                        }
                        for t in TYPES
                    }
                else:
                    model = sun_model(bpmn_path, process_id)
                    missing = scorer.missing_action(
                        record.get("actions") or [], model)
                    actor = scorer.incorrect_actor(
                        record.get("actions") or [],
                        record.get("actors") or [],
                        model,
                        record.get("actor_action_pairs") or [],
                    )
                    order = scorer.out_of_order(
                        record.get("order_relations") or [],
                        record.get("actions") or [],
                        model,
                    )
                    signals = {
                        "missing_action": normalize_sun_signal(
                            "missing_action", missing),
                        "incorrect_actor": normalize_sun_signal(
                            "incorrect_actor", actor),
                        "out_of_order": normalize_sun_signal(
                            "out_of_order", order),
                    }
                extra = {
                    "rule_record_failed": bool(record.get("failed")),
                    "rule_action_count": len(record.get("actions") or []),
                    "rule_actor_count": len(record.get("actors") or []),
                }
            prediction_rows.append({
                "schema_version": SCHEMA_VERSION,
                "method_id": method_id,
                "method_label": method["label"],
                "paper_label": method["paper_label"],
                "item_id": item_id,
                "pair_id": pair_id,
                "rule_id": rule_id,
                "process_id": process_id,
                "bpmn_path": bpmn_path,
                "signals": signals,
                "violated_types": violated_types(signals),
                "inference_inputs": {
                    "current_bpmn_only": True,
                    "rule_text_or_rule_predictions_only": True,
                    "pair_role_read": False,
                    "target_violation_type_read": False,
                    "gold_read": False,
                    "binding_reference_read": False,
                },
                "method_evidence": extra,
            })

    # Persist unsorted-but-deterministic rows before the evaluator can read
    # benchmark labels or eligibility.
    predictions_path = out_dir / "predictions.jsonl"
    _write_jsonl(predictions_path, prediction_rows)

    rule_record_paths: dict[str, str] = {}
    for method_id, records in rule_records_by_method.items():
        path = out_dir / f"rule_records_{method_id}.json"
        _write_json(path, {
            "method_id": method_id,
            "converter_summary": converter_summaries[method_id],
            "records": records,
        })
        rule_record_paths[method_id] = _display_path(path)

    manifest_path = out_dir / "run_manifest.json"
    method_manifest: dict[str, Any] = {}
    for method_id, method in METHODS.items():
        method_manifest[method_id] = {
            **method,
            "rule_records_path": rule_record_paths.get(method_id),
            "rule_records_sha256": (
                sha256_file(ROOT / rule_record_paths[method_id])
                if method_id in rule_record_paths else None),
        }
    manifest = {
        "schema_version": "stage3_table3_v2_run@1.0.0",
        "status": "complete",
        "run_id": "stage3_table3_v2_controlled_comparison",
        "scope": "development paired synthetic panel; target-check evaluation",
        "inference_boundary": {
            "allowed_item_keys": list(ALLOWED_INFERENCE_ITEM_KEYS),
            "current_bpmn_only": True,
            "method_rule_predictions_or_regulation_text_only": True,
            "pair_role_read": False,
            "target_violation_type_read": False,
            "gold_violation_type_read": False,
            "target_activity_id_read": False,
            "expected_lane_read": False,
            "mutation_description_read": False,
            "binding_reference_read": False,
            "benchmark_labels_read_by_runner": False,
        },
        "inputs": {
            "inference_view": {
                "path": _display_path(view_path),
                "sha256": sha256_file(view_path),
            },
            "regulation_text_view": {
                "path": _display_path(text_view_path),
                "sha256": sha256_file(text_view_path),
            },
            "stage2_input": {
                "path": _display_path(stage2_input_path),
                "sha256": sha256_file(stage2_input_path),
            },
            "stage2_predictions": {
                method_id: (
                    {
                        "path": method["predictions_path"],
                        "sha256": sha256_file(ROOT / method["predictions_path"]),
                    }
                    if method["predictions_path"] else None
                )
                for method_id, method in METHODS.items()
            },
        },
        "configuration": {
            "similarity_backend": {
                "package": "spacy",
                "model": nlp_model,
            },
            "sun_frozen_thresholds": {
                key: float(thresholds[key])
                for key in ("tau", "gamma", "theta")
            },
            "sun_scorer": "bpc_hybrid.sun_stage3.sun_scorer.SunScorer",
            "converter": "bpc_hybrid.sun_stage3.gdpr_capsule_converter",
            "winter_config": {
                "path": _display_path(WINTER_CONFIG),
                "sha256": sha256_file(WINTER_CONFIG),
                "gamma": winter_cfg["method"]["gamma"],
                "delta": winter_cfg["method"]["delta"],
                "reachability_mode": REACHABILITY_CORRECTED,
            },
            "one_scorer_instance_for_sun_and_ours": True,
            "same_thresholds_for_sun_and_ours": True,
        },
        "methods": method_manifest,
        "counts": {
            "items": len(items),
            "methods": len(METHODS),
            "prediction_rows": len(prediction_rows),
        },
        "outputs": {
            "predictions_jsonl": {
                "path": _display_path(predictions_path),
                "sha256": sha256_file(predictions_path),
            },
            "run_manifest": _display_path(manifest_path),
        },
        "code_sha256": _code_hash([
            ROOT / "scripts/run_stage3_table3_v2.py",
            ROOT / "scripts/evaluate_stage3_table3_v2.py",
            ROOT / "scripts/build_stage3_table3_inputs_v2.py",
            ROOT / "tests/test_stage3_table3_v2.py",
            SRC / "bpc_hybrid/stage3_table3_v2.py",
            SRC / "bpc_hybrid/stage1_process.py",
            SRC / "bpc_hybrid/sun_stage3/gdpr_capsule_converter.py",
            SRC / "bpc_hybrid/sun_stage3/sun_scorer.py",
            SRC / "bpc_hybrid/sun_stage3/sun_model.py",
            SRC / "bpc_hybrid/winter_stage3/winter_clause.py",
            SRC / "bpc_hybrid/winter_stage3/winter_model.py",
            SRC / "bpc_hybrid/winter_stage3/winter_pair.py",
            SRC / "bpc_hybrid/winter_stage3/winter_similarity.py",
        ]),
        "llm_api_calls": 0,
        "network_calls": 0,
        "existing_predictions_reused": True,
        "reused_existing_llm_predictions": True,
        "gold_read_by_runner": False,
        "binding_reference_read_by_runner": False,
        "target_violation_type_read_by_runner": False,
        "pair_role_used_by_inference": False,
        "winter_native_implementation_differences": [
            "re-implemented Winter wrapper, not imported from references/",
            "corrected reachability mode is used (prototype literal bug disclosed in config)",
            "resource_cost is explicitly unknown when the BPMN has no non-empty participant/resource labels",
            "only target-free regulation text and the current BPMN are read",
        ],
    }
    _write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--view", type=Path, default=DEFAULT_VIEW)
    parser.add_argument("--text-view", type=Path, default=DEFAULT_TEXT_VIEW)
    parser.add_argument("--stage2-input", type=Path, default=DEFAULT_STAGE2_INPUT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--nlp-model", default="en_core_web_sm")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    manifest = run(
        view_path=args.view,
        text_view_path=args.text_view,
        stage2_input_path=args.stage2_input,
        out_dir=args.out_dir,
        nlp_model=args.nlp_model,
        overwrite=args.overwrite,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())