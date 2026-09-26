# -*- coding: utf-8 -*-
"""Run the frozen Stage 3-v2 development calibration and export reports.

This is the only calibration run for the revision.  The threshold grid is read
from ``configs/stage3_v2_development_v1.json`` before any metric is computed.
The script never reads a test case into the calibration evaluation and never
runs the legacy test replay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import spacy  # noqa: E402
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file  # noqa: E402
from bpc_hybrid.stage3_v2.action_order_projection_v2 import (  # noqa: E402
    MAIN_ORDER_TYPE,
    EXTENDED_ORDER_TYPE,
    UNSUPPORTED_ORDER_TYPE,
    SharedActionOrderProjectionV2,
    projection_freeze_manifest,
)
from bpc_hybrid.stage3_v2.checker_v2 import TYPES, SharedStage3CheckerV2  # noqa: E402
from bpc_hybrid.stage3_v2.evaluation_v2 import (  # noqa: E402
    DevelopmentEvaluationError,
    calibration_tie_break_key,
    combined_objective,
    evaluate_dev_method,
)
from bpc_hybrid.stage3_v2.rule_record_converter_v2 import canonical_to_rule_record_v2  # noqa: E402
from bpc_hybrid.stage3_v2.semantic_matcher_v2 import (  # noqa: E402
    SPACY_MD,
    SPACY_SM,
    SharedSemanticMatcherV2,
    inventory_backends,
    selected_backend_manifest,
)

CONFIG_PATH = ROOT / "configs/stage3_v2_development_v1.json"
DEV_MANIFEST = ROOT / "data/development/stage3_v2/reference_dev_v1.json"
ORDER_SCOPE = ROOT / "outputs/reports/stage3_v2_order_scope_manifest_v1.json"
BENCHMARK = ROOT / "data/development/stage3_table3_r5_benchmark_v2"
SOURCE_REQUIREMENTS = BENCHMARK / "source_requirements.json"
INFERENCE_VIEW = BENCHMARK / "inference/inference_view.json"
SPLIT_MANIFEST = BENCHMARK / "split_manifest.json"
STAGE1_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
SUN_PRED = ROOT / "data/predictions/stage3_table3_r5_sun_rule_only_v1/predictions.json"
OURS_PRED = ROOT / "data/predictions/stage3_table3_r5_ours_stage2_formal_v1/predictions.json"
BENCHMARK_MANIFEST = BENCHMARK / "manifest.json"
GOLD_PACKET = ROOT / "outputs/reports/stage3_table3_r5_gold_adjudication_packet_v1.json"
HISTORICAL_RESULT = ROOT / "outputs/reports/stage3_table3_formal_results_v1.json"

OUT_DIR = ROOT / "outputs/development/stage3_v2"
REPORTS = ROOT / "outputs/reports"
SEM_BACKEND_FREEZE = REPORTS / "stage3_v2_semantic_backend_freeze_v1.json"
ORDER_PROJECTION_FREEZE = REPORTS / "stage3_v2_order_projection_freeze_v1.json"
DEV_REPORT_JSON = REPORTS / "stage3_v2_development_report_v1.json"
DEV_REPORT_MD = REPORTS / "stage3_v2_development_report_v1.md"
DEV_GRID_JSON = OUT_DIR / "dev_calibration_grid_v1.json"
DEV_SIGNALS_JSON = OUT_DIR / "selected_dev_signals_v1.json"

TAU = 0.8


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _format(value: Any, digits: int = 4) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def build_case_index() -> dict[str, dict[str, Any]]:
    view = load_json(INFERENCE_VIEW)
    return {str(item["case_id"]): dict(item) for item in view["items"]}


def load_development_inputs() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str], dict[str, dict[str, Any]], dict[str, str]]:
    config = load_json(CONFIG_PATH)
    dev = load_json(DEV_MANIFEST)
    cases = list(dev["cases"])
    if any(str(case.get("split")) != "development" for case in cases):
        raise DevelopmentEvaluationError("development manifest contains non-development cases")
    source_doc = load_json(SOURCE_REQUIREMENTS)
    sources = {str(row["requirement_id"]): row for row in source_doc["requirements"]}
    source_texts = {rid: str(row["excerpt_text"]) for rid, row in sources.items()}
    case_index = build_case_index()
    order_scope_doc = load_json(ORDER_SCOPE)
    order_scope = {
        rid: str(row.get("order_type") or "")
        for rid, row in order_scope_doc["requirements"].items()
    }
    return config, cases, source_texts, case_index, order_scope


def build_converted_records(case_index: Mapping[str, Mapping[str, Any]],
                            sources: Mapping[str, Mapping[str, Any]],
                            source_texts: Mapping[str, str],
                            nlp: Any,
                            development_requirement_ids: Sequence[str]
                            ) -> dict[str, dict[str, dict[str, Any]]]:
    projection = SharedActionOrderProjectionV2()
    sun_doc = load_json(SUN_PRED)
    ours_doc = load_json(OURS_PRED)
    sun_by_id = {str(row["requirement_id"]): row for row in sun_doc["records"]}
    ours_by_id = {str(row["requirement_id"]): row for row in ours_doc["records"]}
    output: dict[str, dict[str, dict[str, Any]]] = {"sun": {}, "ours": {}}
    for requirement_id in sorted(set(development_requirement_ids)):
        if requirement_id not in source_texts:
            raise DevelopmentEvaluationError(f"missing source text for {requirement_id}")
        source_text = source_texts[requirement_id]
        output["sun"][requirement_id] = canonical_to_rule_record_v2(
            sun_by_id[requirement_id].get("record"), source_text, requirement_id, nlp,
            projection=projection,
        )
        output["ours"][requirement_id] = canonical_to_rule_record_v2(
            ours_by_id[requirement_id].get("record"), source_text, requirement_id, nlp,
            projection=projection,
        )
    return output


def build_process_models(case_index: Mapping[str, Mapping[str, Any]], nlp: Any) -> dict[str, Any]:
    contract = load_stage1_contract(STAGE1_CONTRACT)
    from bpc_hybrid.sun_stage3.sun_model import SunProcessModel
    models: dict[str, Any] = {}
    for case_id, item in sorted(case_index.items()):
        bpmn_path = BENCHMARK / str(item["bpmn_path"])
        record = parse_bpmn_file(bpmn_path, contract=contract)
        models[case_id] = SunProcessModel(str(item["process_id"]), record, nlp)
    return models


def evaluate_grid(backend_name: str,
                  cases: Sequence[Mapping[str, Any]],
                  converted: Mapping[str, Mapping[str, Mapping[str, Any]]],
                  models: Mapping[str, Any],
                  order_scope: Mapping[str, str],
                  gamma_grid: Sequence[float],
                  theta_grid: Sequence[float],
                  *,
                  verbose: bool = True
                  ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Mapping[str, Any]]], SharedSemanticMatcherV2]:
    matcher = SharedSemanticMatcherV2.for_backend(backend_name)
    nlp = matcher.backend.nlp
    checker = SharedStage3CheckerV2(matcher, nlp, tau=TAU,
                                    gamma=float(gamma_grid[0]), theta=float(theta_grid[0]))
    results: list[dict[str, Any]] = []
    selected_signals: dict[str, dict[str, Mapping[str, Any]]] = {"sun": {}, "ours": {}}
    best_key: tuple[Any, ...] | None = None
    best_point: dict[str, Any] | None = None
    started = time.perf_counter()
    for gamma in gamma_grid:
        for theta in theta_grid:
            checker.set_thresholds(gamma=float(gamma), theta=float(theta))
            signals_by_method: dict[str, dict[tuple[str, str, str], Mapping[str, Any]]] = {"sun": {}, "ours": {}}
            for case in cases:
                case_id = str(case["case_id"])
                requirement_id = str(case["requirement_id"])
                model = models[case_id]
                for method in ("sun", "ours"):
                    record = converted[method][requirement_id]
                    checked = checker.check_rule_record(record, model)
                    for check_type in TYPES:
                        signals_by_method[method][(method, case_id, check_type)] = checked[check_type]
            method_results = {
                method: evaluate_dev_method(method, cases, signals_by_method[method], order_scope)
                for method in ("sun", "ours")
            }
            objective = combined_objective(method_results)
            tie_key = calibration_tie_break_key("combined", method_results, gamma=float(gamma), theta=float(theta))
            row = {
                "backend": backend_name,
                "gamma": float(gamma),
                "theta": float(theta),
                "objective": objective,
                "tie_break_key": list(tie_key),
                "sun": method_results["sun"],
                "ours": method_results["ours"],
            }
            results.append(row)
            if best_key is None or tuple(tie_key) > best_key:
                best_key = tuple(tie_key)
                best_point = row
                selected_signals = signals_by_method
        if verbose:
            print(f"[{backend_name}] gamma={gamma:.2f} points_done={len(results)}", flush=True)
    if best_point is None:
        raise DevelopmentEvaluationError("empty threshold grid")
    return results, selected_signals, matcher


def diagnostic_mapping(matcher: SharedSemanticMatcherV2,
                       nlp: Any,
                       cases: Sequence[Mapping[str, Any]],
                       converted: Mapping[str, Mapping[str, Mapping[str, Any]]],
                       models: Mapping[str, Any],
                       gamma: float,
                       theta: float,
                       order_scope: Mapping[str, str]
                       ) -> dict[str, Any]:
    checker = SharedStage3CheckerV2(matcher, nlp, tau=TAU, gamma=gamma, theta=theta)
    out: dict[str, Any] = {}
    for method in ("sun", "ours"):
        action_total = action_success = 0
        actor_observable = actor_total = 0
        missing_fp = 0
        missing_fp_categories: Counter = Counter()
        missing_signals_observable = 0
        for case in cases:
            case_id = str(case["case_id"])
            requirement_id = str(case["requirement_id"])
            record = converted[method][requirement_id]
            model = models[case_id]
            checked = checker.check_rule_record(record, model)
            missing_raw = checked["raw"]["missing_action"]
            for detail in missing_raw.get("details") or []:
                action_total += 1
                if not detail.get("missing"):
                    action_success += 1
            actor_signal = checked["incorrect_actor"]
            actor_total += 1
            if bool(actor_signal.get("observable")):
                actor_observable += 1
            missing_signal = checked["missing_action"]
            if bool(missing_signal.get("observable")):
                missing_signals_observable += 1
            expected = str((case.get("reference_states") or {}).get("missing_action") or "")
            status = str(missing_signal.get("status") or "unknown")
            if expected == "satisfied" and status == "violated":
                missing_fp += 1
                details = missing_raw.get("details") or []
                missing_flags = [bool(item.get("missing")) for item in details]
                if missing_flags and all(missing_flags):
                    missing_fp_categories["mandatory_primary_action_not_detected_below_gamma"] += 1
                elif any(missing_flags):
                    missing_fp_categories["mandatory_action_detected_but_extra_rule_action_below_gamma"] += 1
                else:
                    missing_fp_categories["other_missing_action_false_positive"] += 1
            # Actor action mapping below gamma diagnostic
        out[method] = {
            "action_mapping_total_rule_actions": action_total,
            "action_mapping_success_above_gamma": action_success,
            "action_mapping_success_rate": (action_success / action_total) if action_total else None,
            "actor_observable_cells": actor_observable,
            "actor_scored_cells": actor_total,
            "actor_observability_rate": (actor_observable / actor_total) if actor_total else None,
            "missing_false_positive_cells": missing_fp,
            "missing_false_positive_categories": dict(missing_fp_categories),
            "missing_observable_cells": missing_signals_observable,
        }
    return out


def order_case_rows(backend_name: str,
                    cases: Sequence[Mapping[str, Any]],
                    converted: Mapping[str, Mapping[str, Mapping[str, Any]]],
                    models: Mapping[str, Any],
                    nlp: Any,
                    gamma: float,
                    theta: float,
                    order_scope_doc: Mapping[str, Any]
                    ) -> list[dict[str, Any]]:
    matcher = SharedSemanticMatcherV2.for_backend(backend_name)
    checker = SharedStage3CheckerV2(matcher, nlp, tau=TAU, gamma=gamma, theta=theta)
    rows: list[dict[str, Any]] = []
    requirement_scope = order_scope_doc["requirements"]
    for case in sorted(cases, key=lambda item: str(item["case_id"])):
        requirement_id = str(case["requirement_id"])
        scope = requirement_scope.get(requirement_id) or {}
        if str(scope.get("order_type") or "") != MAIN_ORDER_TYPE:
            continue
        # The main metric scores only cells whose expected order state is
        # violated/satisfied; in this benchmark those are the out_of_order
        # mutation and the compliant baseline control.
        expected_order = str((case.get("reference_states") or {}).get("out_of_order") or "")
        if str(case.get("variant")) not in ("baseline", "out_of_order"):
            continue
        if expected_order not in ("violated", "satisfied"):
            continue
        case_id = str(case["case_id"])
        model = models[case_id]
        row: dict[str, Any] = {
            "case_id": case_id,
            "requirement_id": requirement_id,
            "citation": scope.get("citation"),
            "source_relation": scope.get("order_evidence"),
            "gold_out_of_order": (case.get("reference_states") or {}).get("out_of_order"),
            "methods": {},
        }
        for method in ("sun", "ours"):
            record = converted[method][requirement_id]
            checked = checker.check_rule_record(record, model)
            signal = checked["out_of_order"]
            edges = []
            for before_text, after_text in record.get("order_relations") or []:
                _, before_score = checker.scorer._best_action_match(before_text, model)
                _, after_score = checker.scorer._best_action_match(after_text, model)
                edges.append({
                    "before_text": before_text,
                    "after_text": after_text,
                    "before_best_similarity": before_score,
                    "after_best_similarity": after_score,
                })
            row["methods"][method] = {
                "converted_order_relations": list(record.get("order_relations") or []),
                "projection_status": (record.get("conversion_audit") or {}).get("order_projection", {}).get("status"),
                "edges": edges,
                "edge_generated": bool(edges),
                "signal_status": signal.get("status"),
                "signal_raw_score": signal.get("raw_score"),
                "signal_denominator": signal.get("denominator"),
                "signal_observable": signal.get("observable"),
                "signal_reason": signal.get("reason"),
            }
        rows.append(row)
    return rows


def build_report(config: Mapping[str, Any],
                 backend_rows: Mapping[str, list[dict[str, Any]]],
                 selected_backend: str,
                 selected_gamma: float,
                 selected_theta: float,
                 selected_method_results: Mapping[str, Mapping[str, Any]],
                 selected_signals: Mapping[str, Mapping[str, Mapping[str, Any]]],
                 diagnostics: Mapping[str, Mapping[str, Mapping[str, Any]]],
                 order_rows: Sequence[Mapping[str, Any]],
                 inventory: Sequence[Mapping[str, Any]],
                 dev_manifest: Mapping[str, Any],
                 order_scope_doc: Mapping[str, Any],
                 runtime: Mapping[str, Any]
                 ) -> dict[str, Any]:
    selected_row = next(row for row in backend_rows[selected_backend]
                        if float(row["gamma"]) == float(selected_gamma)
                        and float(row["theta"]) == float(selected_theta))
    type_b = [rid for rid, row in order_scope_doc["requirements"].items()
              if row.get("order_type") == EXTENDED_ORDER_TYPE]
    type_c = [rid for rid, row in order_scope_doc["requirements"].items()
              if row.get("order_type") == UNSUPPORTED_ORDER_TYPE]
    integrity = {
        "gold_modified": False,
        "benchmark_modified": False,
        "ours_stage2_prediction_modified": False,
        "sun_stage2_prediction_modified": False,
        "historical_v1_result_modified": False,
        "real_api_calls": 0,
        "network_calls": 0,
        "benchmark_manifest_sha256": sha_file(BENCHMARK_MANIFEST),
        "gold_packet_sha256": sha_file(GOLD_PACKET) if GOLD_PACKET.exists() else None,
        "historical_v1_result_sha256": sha_file(HISTORICAL_RESULT) if HISTORICAL_RESULT.exists() else None,
        "sun_stage2_predictions_sha256": sha_file(SUN_PRED),
        "ours_stage2_predictions_sha256": sha_file(OURS_PRED),
        "development_manifest_sha256": sha_file(DEV_MANIFEST),
        "order_scope_manifest_sha256": sha_file(ORDER_SCOPE),
    }
    return {
        "schema_version": "stage3_v2_development_report@1.0.0",
        "status": "DEVELOPMENT_COMPLETE_BACKEND_AND_ORDER_FROZEN",
        "winter_mainline_status": "ARCHIVED_EXTERNAL_BASELINE",
        "stage3_v1_status": "PRESERVED_HISTORICAL_FROZEN_RUN",
        "test_quarantine": {
            "legacy_test_seen": False,
            "legacy_test_used_for_calibration": False,
            "legacy_test_replay_performed": False,
        },
        "selected": {
            "backend": selected_backend,
            "gamma": selected_gamma,
            "theta": selected_theta,
            "tau": TAU,
            "objective": selected_row["objective"],
            "tie_break_key": selected_row["tie_break_key"],
            "preferred_sentence_embedding_backend": "sentence-transformers/all-mpnet-base-v2",
            "preferred_backend_download_required": next(
                (bool(row.get("download_required")) for row in inventory
                 if row.get("short_name") == "sentence_transformers_all_mpnet_base_v2"),
                True,
            ),
        },
        "inventory": list(inventory),
        "calibration": {
            "objective": config["calibration"]["objective"],
            "tie_breakers": config["calibration"]["tie_breakers"],
            "grid": {
                "gamma": config["thresholds"]["gamma_grid"],
                "theta": config["thresholds"]["theta_grid"],
            },
            "backend_best_points": {
                backend: {
                    "gamma": min((row for row in rows), key=lambda r: -float(r["objective"]))["gamma"] if False else None,
                }
                for backend, rows in {}
            },
            "grid_result_rows": sum(len(rows) for rows in backend_rows.values()),
        },
        "dev_result": {
            "sun": selected_method_results["sun"],
            "ours": selected_method_results["ours"],
            "macro_f1_sun": selected_method_results["sun"]["macro_f1"],
            "macro_f1_ours": selected_method_results["ours"]["macro_f1"],
            "micro_f1_sun": selected_method_results["sun"]["micro_f1"],
            "micro_f1_ours": selected_method_results["ours"]["micro_f1"],
        },
        "old_vs_new_semantic_mapping": diagnostics,
        "order_type_a_rows": list(order_rows),
        "order_type_b_preserved": type_b,
        "order_type_c_unsupported_not_scored": type_c,
        "action_scope_audit": {
            "extra_action_false_positive_count": sum(
                int(method_diag["missing_false_positive_categories"].get(
                    "mandatory_action_detected_but_extra_rule_action_below_gamma", 0))
                for backend_diag in diagnostics.values()
                for method_diag in backend_diag.values()
            ),
            "action_scope_proposal": "NONE",
            "implementation_allowed": False,
        },
        "integrity": integrity,
        "runtime": dict(runtime),
        "development_case_count": len(dev_manifest.get("cases") or []),
    }


def format_md(report: Mapping[str, Any]) -> str:
    lines = [
        "# Stage 3-v2 Development Report v1",
        "",
        f"- status: `{report['status']}`",
        f"- winter mainline: `{report['winter_mainline_status']}`",
        f"- Stage3-v1: `{report['stage3_v1_status']}`",
        f"- selected backend: `{report['selected']['backend']}`",
        f"- selected gamma/theta/tau: `{report['selected']['gamma']}` / `{report['selected']['theta']}` / `{report['selected']['tau']}`",
        f"- legacy test used for calibration: `{report['test_quarantine']['legacy_test_used_for_calibration']}`",
        "",
        "## Selected Dev Table3-v2",
        "",
        "| Method | Missing F1 | Actor F1 | TYPE-A Order F1 | Macro-F1 | Micro-F1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method in ("sun", "ours"):
        m = report["dev_result"][method]
        lines.append(
            f"| {method.capitalize()} | {_format(m['per_type']['missing_action']['f1'])} | "
            f"{_format(m['per_type']['incorrect_actor']['f1'])} | "
            f"{_format(m['per_type']['out_of_order']['f1'])} | "
            f"{_format(m['macro_f1'])} | {_format(m['micro_f1'])} |"
        )
    lines.extend([
        "",
        "## Old vs New Semantic Mapping Diagnostics",
        "",
        "| Backend | Method | Action mapping success | Actor observable | Missing FP |",
        "|---|---|---:|---:|---:|",
    ])
    for backend, methods in report["old_vs_new_semantic_mapping"].items():
        for method, diag in methods.items():
            lines.append(
                f"| {backend} | {method} | "
                f"{diag['action_mapping_success_above_gamma']}/{diag['action_mapping_total_rule_actions']} "
                f"({_format(diag['action_mapping_success_rate'])}) | "
                f"{diag['actor_observable_cells']}/{diag['actor_scored_cells']} | "
                f"{diag['missing_false_positive_cells']} |"
            )
    lines.extend([
        "",
        "## TYPE A Order Cases (dev)",
        "",
        "| Case | Method | Edge generated | Edge endpoints | Order signal |",
        "|---|---|---|---|---|",
    ])
    for row in report["order_type_a_rows"]:
        for method in ("sun", "ours"):
            m = row["methods"][method]
            endpoints = " ; ".join(
                f"{e['before_text']} -> {e['after_text']}" for e in m["edges"]
            ) or ""
            lines.append(
                f"| {row['case_id']} | {method} | {m['edge_generated']} | {endpoints} | "
                f"{m['signal_status']} |"
            )
    lines.extend([
        "",
        "## Integrity",
        "",
        f"- Gold modified: `{report['integrity']['gold_modified']}`",
        f"- Benchmark modified: `{report['integrity']['benchmark_modified']}`",
        f"- Ours Stage2 modified: `{report['integrity']['ours_stage2_prediction_modified']}`",
        f"- Sun Stage2 modified: `{report['integrity']['sun_stage2_prediction_modified']}`",
        f"- Historical v1 result modified: `{report['integrity']['historical_v1_result_modified']}`",
        f"- Real API calls: `{report['integrity']['real_api_calls']}`",
        "",
        "## Readiness",
        "",
        f"- STAGE3_V2_BACKEND_SELECTED = `{report['selected']['backend']}`",
        f"- STAGE3_V2_GAMMA_FROZEN = `{report['selected']['gamma']}`",
        f"- STAGE3_V2_THETA_FROZEN = `{report['selected']['theta']}`",
        "- STAGE3_V2_TYPE_A_ORDER_SCOPE_FROZEN = `true`",
        "- ACTION_SCOPE_CHANGE_IMPLEMENTED = `false`",
        "- LEGACY_TEST_DIAGNOSTIC_COMPLETE = `false`",
        "- FINAL_UNSEEN_HOLDOUT_CREATED = `false`",
        "- FINAL_TABLE3_V2_RUN = `false`",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    config, cases, source_texts, case_index, order_scope = load_development_inputs()
    for case in cases:
        case.update(case_index[str(case["case_id"])])
    dev_requirement_ids = sorted({str(case["requirement_id"]) for case in cases})
    dev_case_ids = sorted({str(case["case_id"]) for case in cases})
    dev_case_index = {case_id: case_index[case_id] for case_id in dev_case_ids}

    backend_rows: dict[str, list[dict[str, Any]]] = {}
    backend_matchers: dict[str, SharedSemanticMatcherV2] = {}
    backend_sources: dict[str, tuple[Any, Any, Any, Any]] = {}
    for backend_name in (SPACY_MD, SPACY_SM):
        # Build the backend once for conversion / process parsing.
        matcher = SharedSemanticMatcherV2.for_backend(backend_name)
        nlp = matcher.backend.nlp
        converted = build_converted_records(
            dev_case_index,
            {rid: {"excerpt_text": text} for rid, text in source_texts.items()},
            source_texts, nlp, dev_requirement_ids,
        )
        models = build_process_models(dev_case_index, nlp)
        rows, selected_signals, _ = evaluate_grid(
            backend_name, cases, converted, models, order_scope,
            config["thresholds"]["gamma_grid"], config["thresholds"]["theta_grid"],
            verbose=args.verbose,
        )
        backend_rows[backend_name] = rows
        backend_matchers[backend_name] = matcher
        backend_sources[backend_name] = (converted, models, selected_signals, nlp)
        print(f"[{backend_name}] grid completed: {len(rows)} points")

    # Persist the raw calibration surface before report assembly so a later
    # presentation bug cannot force a re-run of the single frozen sweep.
    write_json(DEV_GRID_JSON, {
        "schema_version": "stage3_v2_dev_calibration_grid@1.0.0",
        "grid_frozen_before_metrics": True,
        "config_sha256": sha_file(CONFIG_PATH),
        "development_manifest_sha256": sha_file(DEV_MANIFEST),
        "backends": backend_rows,
    })

    # Backend selection uses the same method-neutral tie-break tuple as
    # threshold selection.
    backend_best: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {}
    for backend_name, rows in backend_rows.items():
        best = max(rows, key=lambda row: tuple(row["tie_break_key"]))
        backend_best[backend_name] = (tuple(best["tie_break_key"]), best)
    selected_backend = max(backend_best, key=lambda name: backend_best[name][0])
    selected_row = backend_best[selected_backend][1]
    selected_gamma = float(selected_row["gamma"])
    selected_theta = float(selected_row["theta"])

    # Reconstruct selected backend signals at the selected point for export.
    converted, models, selected_signals, nlp = backend_sources[selected_backend]
    checker = SharedStage3CheckerV2(backend_matchers[selected_backend], nlp,
                                   tau=TAU, gamma=selected_gamma, theta=selected_theta)
    export_signals: dict[str, dict[str, Mapping[str, Any]]] = {}
    for case in cases:
        case_id = str(case["case_id"])
        requirement_id = str(case["requirement_id"])
        model = models[case_id]
        for method in ("sun", "ours"):
            checked = checker.check_rule_record(converted[method][requirement_id], model)
            for check_type in TYPES:
                export_signals.setdefault(method, {}).setdefault(case_id, {})[check_type] = checked[check_type]

    selected_method_results = {
        "sun": selected_row["sun"],
        "ours": selected_row["ours"],
    }
    diagnostics: dict[str, dict[str, Any]] = {}
    for backend_name in (SPACY_SM, SPACY_MD):
        if backend_name not in backend_matchers:
            continue
        backend_diag = diagnostic_mapping(
            backend_matchers[backend_name], backend_sources[backend_name][3],
            cases, backend_sources[backend_name][0], backend_sources[backend_name][1],
            float(backend_best[backend_name][1]["gamma"]),
            float(backend_best[backend_name][1]["theta"]),
            order_scope,
        )
        diagnostics[backend_name] = backend_diag

    order_scope_doc = load_json(ORDER_SCOPE)
    order_rows = order_case_rows(
        selected_backend, cases, converted, models, nlp, selected_gamma, selected_theta,
        order_scope_doc,
    )
    inventory = inventory_backends()
    runtime = {
        "python": sys.version,
        "spacy": getattr(spacy, "__version__", None),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "selected_backend_identity": backend_matchers[selected_backend].identity(),
        "matcher_stats": backend_matchers[selected_backend].stats(),
    }
    report = build_report(
        config, backend_rows, selected_backend, selected_gamma, selected_theta,
        selected_method_results, selected_signals, diagnostics, order_rows, inventory,
        load_json(DEV_MANIFEST), order_scope_doc, runtime,
    )
    write_json(DEV_GRID_JSON, {
        "schema_version": "stage3_v2_dev_calibration_grid@1.0.0",
        "grid_frozen_before_metrics": True,
        "config_sha256": sha_file(CONFIG_PATH),
        "development_manifest_sha256": sha_file(DEV_MANIFEST),
        "backends": backend_rows,
    })
    write_json(DEV_SIGNALS_JSON, {
        "schema_version": "stage3_v2_selected_dev_signals@1.0.0",
        "selected_backend": selected_backend,
        "gamma": selected_gamma,
        "theta": selected_theta,
        "signals": export_signals,
    })
    write_json(DEV_REPORT_JSON, report)
    DEV_REPORT_MD.write_text(format_md(report), encoding="utf-8", newline="\n")

    # Freeze manifests are written only after calibration and selection.
    semantic_freeze = selected_backend_manifest(
        backend_matchers[selected_backend],
        gamma=selected_gamma,
        theta=selected_theta,
        calibration_grid={
            "gamma": config["thresholds"]["gamma_grid"],
            "theta": config["thresholds"]["theta_grid"],
            "tau": TAU,
        },
        calibration_objective={
            "name": config["calibration"]["objective"],
            "tie_breakers": config["calibration"]["tie_breakers"],
        },
        development_family_ids=sorted({str(case["source_family_id"]) for case in cases}),
        test_quarantine_statement=(
            "Legacy test split is quarantined; no test case or test metric was read "
            "or used for backend/threshold selection. A single legacy diagnostic replay "
            "is allowed only after this freeze and must be labelled LEGACY_SEEN_TEST_DIAGNOSTIC."
        ),
    )
    semantic_freeze["candidate_inventory"] = inventory
    semantic_freeze["preferred_sentence_embedding_backend"] = "sentence-transformers/all-mpnet-base-v2"
    semantic_freeze["preferred_backend_download_required"] = next(
        (bool(row.get("download_required")) for row in inventory
         if row.get("short_name") == "sentence_transformers_all_mpnet_base_v2"),
        True,
    )
    semantic_freeze["preferred_backend_status_note"] = (
        "Preferred sentence-transformer backend was not present in the local cache and was not "
        "downloaded. The frozen selection is a locally available shared spaCy fallback selected "
        "by the pre-registered method-neutral development objective. A future revision may "
        "replace it with the preferred backend without changing Stage 1/2 or Gold."
    )
    semantic_freeze["selected_grid_point"] = {
        "gamma": selected_gamma,
        "theta": selected_theta,
        "tau": TAU,
        "objective": selected_row["objective"],
        "tie_break_key": selected_row["tie_break_key"],
    }
    semantic_freeze["development_evidence"] = {
        "sun": selected_method_results["sun"],
        "ours": selected_method_results["ours"],
    }
    write_json(SEM_BACKEND_FREEZE, semantic_freeze)

    order_freeze = projection_freeze_manifest(
        projection=SharedActionOrderProjectionV2(),
        order_scope_manifest_sha256=sha_file(ORDER_SCOPE),
        development_type_a_cases=[
            str(row["case_id"]) for row in order_rows
        ],
    )
    order_freeze["selected_backend"] = selected_backend
    order_freeze["development_order_rows"] = list(order_rows)
    write_json(ORDER_PROJECTION_FREEZE, order_freeze)
    print("Selected backend:", selected_backend)
    print("Selected gamma/theta:", selected_gamma, selected_theta)
    print("Wrote", rel(DEV_REPORT_JSON), rel(DEV_REPORT_MD), rel(SEM_BACKEND_FREEZE), rel(ORDER_PROJECTION_FREEZE))


if __name__ == "__main__":
    main()
