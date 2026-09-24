# -*- coding: utf-8 -*-
"""Independent R1 evaluator for the scoped Table 3 benchmark.

The evaluator first verifies output hashes, unique keys, row/signal
completeness, and manifest bindings.  Only after those checks pass does it
read ``construction_reference.json``.  It never modifies predictions,
algorithms, thresholds, or the reference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONFIG = ROOT / "configs/stage3_table3_v4_execution_r1.json"
OUT_DIR = ROOT / "outputs/development/stage3_table3_v4_r1"
REFERENCE = ROOT / "data/development/stage3_reconstruction_v4/construction_reference.json"
REPORT_JSON = ROOT / "outputs/reports/stage3_table3_v4_r1.json"
REPORT_MD = ROOT / "outputs/reports/stage3_table3_v4_r1.md"
REPORT_MANIFEST = ROOT / "outputs/reports/stage3_table3_v4_r1.manifest.json"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")
METHOD_ORDER = ("sun", "ours", "winter")


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _verify_output_hashes(*, run_manifest: Mapping[str, Any], out_dir: Path,
                          predictions_path: Path, signals_path: Path) -> None:
    """Verify all saved outputs against the inference manifest before labels."""
    outputs = run_manifest.get("outputs")
    if not isinstance(outputs, Mapping):
        raise RuntimeError("run manifest has no output hash binding")
    expected = {
        "predictions": predictions_path,
        "signals_matrix": signals_path,
        "rule_records": out_dir / "rule_records.json",
        "global_role_candidates": out_dir / "global_role_candidates.json",
    }
    for name, path in expected.items():
        if not path.is_file():
            raise RuntimeError(f"bound output missing: {name}: {path}")
        rec = outputs.get(name)
        if not isinstance(rec, Mapping):
            raise RuntimeError(f"run manifest did not bind output: {name}")
        actual = _sha_file(path)
        if rec.get("sha256") != actual:
            raise RuntimeError(f"output hash mismatch for {name}: {actual} != {rec.get('sha256')}")
        if str(rec.get("path") or "").replace("\\", "/") != _rel(path):
            raise RuntimeError(f"output path drift for {name}: {rec.get('path')} != {_rel(path)}")
    config_rec = ((run_manifest.get("inputs") or {}).get("execution_config") or {})
    if config_rec.get("sha256") != _sha_file(CONFIG):
        raise RuntimeError("execution config hash drift in run manifest")
    input_rec = ((run_manifest.get("inputs") or {}).get("inference_view") or {})
    if input_rec.get("sha256") != _sha_file(ROOT / "data/development/stage3_reconstruction_v4/inference_view.json"):
        raise RuntimeError("inference-view hash drift in run manifest")


def _validate_prediction_structure(*, rows: list[Mapping[str, Any]], signals_doc: Mapping[str, Any],
                                   cfg: Mapping[str, Any]) -> None:
    """Validate unique keys, completeness, and flattened/nested consistency.

    This runs before the evaluator reads the reference.  A duplicate key would
    otherwise silently overwrite a prior dictionary entry.
    """
    rule_ids = [str(r) for r in (cfg.get("scope") or {}).get("rule_ids") or []]
    if len(rule_ids) != 5 or len(set(rule_ids)) != 5:
        raise RuntimeError("execution config does not freeze five unique rule IDs")
    expected_case_count = int((cfg.get("scope") or {}).get("case_count") or 0)
    if expected_case_count != 20:
        raise RuntimeError("execution config case_count drift")
    expected_row_count = 3 * expected_case_count
    if len(rows) != expected_row_count:
        raise RuntimeError(f"expected {expected_row_count} prediction rows, got {len(rows)}")

    by_method_case: dict[tuple[str, str], Mapping[str, Any]] = {}
    case_ids: set[str] = set()
    method_case_ids: dict[str, set[str]] = {m: set() for m in METHOD_ORDER}
    nested_keys: set[tuple[str, str, str, str]] = set()
    for row in rows:
        method = str(row.get("row_method_id"))
        case_id = str(row.get("case_id"))
        if method not in METHOD_ORDER:
            raise RuntimeError(f"unknown method row: {method}")
        key = (method, case_id)
        if key in by_method_case:
            raise RuntimeError(f"duplicate prediction row: {method}/{case_id}")
        by_method_case[key] = row
        case_ids.add(case_id)
        method_case_ids[method].add(case_id)
        signals_by_rule = row.get("signals_by_rule")
        if not isinstance(signals_by_rule, Mapping) or set(signals_by_rule) != set(rule_ids):
            raise RuntimeError(f"rule-key drift for {method}/{case_id}: {sorted((signals_by_rule or {}).keys())}")
        for rid in rule_ids:
            checks = signals_by_rule[rid]
            if not isinstance(checks, Mapping) or set(checks) != set(TYPES):
                raise RuntimeError(f"check-type drift for {method}/{case_id}/{rid}: {sorted((checks or {}).keys())}")
            for check_type in TYPES:
                signal = checks[check_type]
                if not isinstance(signal, Mapping):
                    raise RuntimeError(f"signal not an object: {method}/{case_id}/{rid}/{check_type}")
                status = signal.get("status")
                if status not in ("violated", "satisfied", "unknown"):
                    raise RuntimeError(f"invalid signal status: {method}/{case_id}/{rid}/{check_type}={status!r}")
                flat_key = (method, case_id, rid, check_type)
                if flat_key in nested_keys:
                    raise RuntimeError(f"duplicate signal key: {flat_key}")
                nested_keys.add(flat_key)
    if len(case_ids) != expected_case_count:
        raise RuntimeError(f"expected {expected_case_count} cases, got {len(case_ids)}")
    for method in METHOD_ORDER:
        if len(method_case_ids[method]) != expected_case_count:
            raise RuntimeError(f"{method} does not cover exactly {expected_case_count} cases")
        if method_case_ids[method] != case_ids:
            raise RuntimeError(f"{method} case population differs from other methods")

    signals = signals_doc.get("signals") or []
    if int(signals_doc.get("count", -1)) != len(signals) or len(signals) != 900:
        raise RuntimeError(f"signal matrix count drift: count={signals_doc.get('count')}, len={len(signals)}")
    flat_keys: set[tuple[str, str, str, str]] = set()
    for flat in signals:
        key = (str(flat.get("method")), str(flat.get("case_id")),
               str(flat.get("rule_id")), str(flat.get("check_type")))
        if key in flat_keys:
            raise RuntimeError(f"duplicate flattened signal key: {key}")
        if key not in nested_keys:
            raise RuntimeError(f"flattened signal not present in nested rows: {key}")
        flat_keys.add(key)
        nested = by_method_case[(key[0], key[1])]["signals_by_rule"][key[2]][key[3]]
        for field in ("status", "raw_score", "denominator", "observable", "reason"):
            if flat.get(field) != nested.get(field):
                raise RuntimeError(f"flattened/nested mismatch for {key}/{field}")
    if flat_keys != nested_keys:
        raise RuntimeError("flattened signal matrix does not match nested rows")


def _empty_counts() -> dict[str, int]:
    return {
        "tp": 0, "fp": 0, "fn": 0, "tn": 0,
        "unknown_positive": 0, "unknown_negative": 0,
        "positive_cells": 0, "negative_cells": 0,
        "not_applicable_cells": 0, "cells": 0,
    }


def _finalize(counts: Mapping[str, int]) -> dict[str, Any]:
    out = dict(counts)
    tp, fp, fn, tn = out["tp"], out["fp"], out["fn"], out["tn"]
    unknown = out["unknown_positive"] + out["unknown_negative"]
    out["unknown_total"] = unknown
    out["predicted_positive"] = tp + fp
    out["precision"] = (None if (tp + fp) == 0 else tp / (tp + fp))
    out["recall"] = tp / (tp + fn) if (tp + fn) else None
    denom_f1 = 2 * tp + fp + fn
    out["f1"] = (2 * tp / denom_f1) if denom_f1 else None
    # R1 coverage: unobservable cells are both positive and negative
    # unknowns, not only positive unknowns.
    observable = out["cells"] - out["unknown_positive"] - out["unknown_negative"]
    out["observable_coverage"] = (observable / out["cells"]) if out["cells"] else None
    out["unknown_rate"] = (unknown / out["cells"]) if out["cells"] else None
    out["positive_unknown_rate"] = (out["unknown_positive"] / out["positive_cells"]) if out["positive_cells"] else None
    out["negative_unknown_rate"] = (out["unknown_negative"] / out["negative_cells"]) if out["negative_cells"] else None
    return out


def _classify(reference: str, predicted: str) -> str:
    if reference == "violated":
        if predicted == "violated":
            return "tp"
        if predicted == "satisfied":
            return "fn"
        return "unknown_positive"
    if reference == "satisfied":
        if predicted == "violated":
            return "fp"
        if predicted == "satisfied":
            return "tn"
        return "unknown_negative"
    raise ValueError(f"unsupported reference state: {reference}")


def _fmt(value: Any, decimals: int = 4) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    return str(value)


def evaluate(*, out_dir: Path = OUT_DIR, report_json: Path = REPORT_JSON,
             report_md: Path = REPORT_MD, report_manifest: Path = REPORT_MANIFEST) -> dict[str, Any]:
    cfg = _load_json(CONFIG)
    manifest_path = out_dir / "run_manifest.json"
    predictions_path = out_dir / "predictions.json"
    signals_path = out_dir / "signals_matrix.json"
    run_manifest = _load_json(manifest_path)
    predictions_doc = _load_json(predictions_path)
    signals_doc = _load_json(signals_path)
    if run_manifest.get("construction_reference_read_by_runner") is not False:
        raise RuntimeError("runner manifest does not declare reference-blind inference")
    if predictions_doc.get("construction_reference_read") is not False:
        raise RuntimeError("prediction document does not declare reference blindness")
    rows = predictions_doc.get("records") or []
    # R1-A hard gate: verify saved output hashes, unique keys, nested/flat
    # consistency, and manifest binding BEFORE opening the reference.
    _verify_output_hashes(
        run_manifest=run_manifest,
        out_dir=out_dir,
        predictions_path=predictions_path,
        signals_path=signals_path,
    )
    _validate_prediction_structure(rows=list(rows), signals_doc=signals_doc, cfg=cfg)
    prediction_sha = _sha_file(predictions_path)
    signals_sha = _sha_file(signals_path)

    precheck = cfg.get("reference_precheck") or {}
    expected_reference_sha = str(precheck.get("expected_sha256") or "")
    if not expected_reference_sha or _sha_file(REFERENCE) != expected_reference_sha:
        raise RuntimeError("construction reference SHA does not match R1 precheck binding")
    reference = _load_json(REFERENCE)
    if reference.get("is_gold") is not False or reference.get("human_adjudicated") is not False:
        raise RuntimeError("reference identity boundary drift")
    cases = reference.get("cases") or []
    if len(cases) != int((cfg.get("scope") or {}).get("case_count") or 0):
        raise RuntimeError("reference case count does not match execution config")

    # Index predictions.
    by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in rows:
        method = str(row.get("row_method_id"))
        case_id = str(row.get("case_id"))
        by_key[(method, case_id)] = row

    method_statuses: dict[str, str] = {}
    for row in rows:
        method_statuses.setdefault(str(row.get("row_method_id")), str(row.get("method_status")))

    evidence: list[dict[str, Any]] = []
    per_method: dict[str, dict[str, Any]] = {}
    for method in METHOD_ORDER:
        per_type = {check_type: _empty_counts() for check_type in TYPES}
        overall = _empty_counts()
        for case in cases:
            case_id = str(case["case_id"])
            rule_id = str(case.get("rule_id") or case.get("family_id"))
            ref_states = case.get("reference_states") or {}
            prediction_row = by_key.get((method, case_id))
            if prediction_row is None:
                raise RuntimeError(f"missing prediction row for {method}/{case_id}")
            signals_by_rule = prediction_row.get("signals_by_rule") or {}
            signals = signals_by_rule.get(rule_id) or {}
            for check_type in TYPES:
                ref = str(ref_states.get(check_type))
                if ref not in ("violated", "satisfied", "not_applicable"):
                    raise RuntimeError(f"invalid reference state {ref!r} for {case_id}/{check_type}")
                if ref == "not_applicable":
                    for counts in (per_type[check_type], overall):
                        counts["not_applicable_cells"] += 1
                    evidence.append({
                        "method": method, "case_id": case_id, "rule_id": rule_id,
                        "check_type": check_type, "reference": ref,
                        "predicted_status": None, "classification": "excluded_not_applicable",
                        "raw_score": None, "denominator": None, "observable": None, "reason": None,
                    })
                    continue
                signal = signals.get(check_type) or {}
                predicted = str(signal.get("status") or "unknown")
                if predicted not in ("violated", "satisfied", "unknown"):
                    predicted = "unknown"
                classification = _classify(ref, predicted)
                counts = per_type[check_type]
                counts["cells"] += 1
                overall["cells"] += 1
                if ref == "violated":
                    counts["positive_cells"] += 1
                    overall["positive_cells"] += 1
                else:
                    counts["negative_cells"] += 1
                    overall["negative_cells"] += 1
                counts[classification] += 1
                overall[classification] += 1
                if classification == "unknown_positive":
                    counts["fn"] += 1
                    overall["fn"] += 1
                evidence.append({
                    "method": method, "case_id": case_id, "rule_id": rule_id,
                    "check_type": check_type, "reference": ref,
                    "predicted_status": predicted, "classification": classification,
                    "raw_score": signal.get("raw_score"),
                    "denominator": signal.get("denominator"),
                    "observable": signal.get("observable"),
                    "reason": signal.get("reason"),
                })
        method_status = method_statuses.get(method, "unknown")
        per_method[method] = {
            "method_status": method_status,
            "per_type": {k: _finalize(v) for k, v in per_type.items()},
            "overall": _finalize(overall),
        }
        # R1-A: a method that was not actually run (blocked / not_run) must
        # not publish zero as if it were a measured performance.  Keep the
        # all-unknown arithmetic separately as a diagnostic, while main
        # precision/recall/F1 remain null.
        if not method_status.startswith("available"):
            for metric in [per_method[method]["overall"], *per_method[method]["per_type"].values()]:
                metric["diagnostic_all_unknown_arithmetic"] = {
                    "precision": metric.get("precision"),
                    "recall": metric.get("recall"),
                    "f1": metric.get("f1"),
                }
                metric["precision"] = None
                metric["recall"] = None
                metric["f1"] = None

    # Contract assertions and diagnostics.
    diagnostics: dict[str, Any] = {"methods": {}, "flags": []}
    for method in METHOD_ORDER:
        method_diag: dict[str, Any] = {}
        for check_type in TYPES:
            c = per_method[method]["per_type"][check_type]
            if c["tp"] + c["fn"] != 5:
                raise RuntimeError(f"{method}/{check_type}: TP+FN != 5")
            if c["fp"] + c["tn"] + c["unknown_negative"] != c["negative_cells"]:
                raise RuntimeError(f"{method}/{check_type}: negative denominator mismatch")
            if c["cells"] + c["not_applicable_cells"] != 20:
                raise RuntimeError(f"{method}/{check_type}: cell total mismatch")
            if c["f1"] is not None and (c["f1"] == 0.0 or c["f1"] == 1.0):
                diagnostics["flags"].append(f"{method}/{check_type}: extreme_f1={c['f1']}")
        overall = per_method[method]["overall"]
        if overall["tp"] + overall["fn"] != 15:
            raise RuntimeError(f"{method}: overall TP+FN != 15")
        if overall["fp"] + overall["tn"] + overall["unknown_negative"] != 35:
            raise RuntimeError(f"{method}: overall negative denominator != 35")
        if overall["cells"] != 50:
            raise RuntimeError(f"{method}: overall evaluable cells != 50")
        if overall["not_applicable_cells"] != 10:
            raise RuntimeError(f"{method}: overall not_applicable cells != 10")
        if overall["f1"] is not None and (overall["f1"] == 0.0 or overall["f1"] == 1.0):
            diagnostics["flags"].append(f"{method}: overall_extreme_f1={overall['f1']}")
        if method_statuses.get(method, "").startswith("blocked"):
            diagnostics["flags"].append(f"{method}: blocked_status={method_statuses.get(method)}")
        # Constant prediction and denominator diagnostics from evidence rows.
        for check_type in TYPES:
            ev = [e for e in evidence if e["method"] == method and e["check_type"] == check_type
                  and e["classification"] != "excluded_not_applicable"]
            statuses = {e["predicted_status"] for e in ev}
            if len(statuses) == 1:
                diagnostics["flags"].append(f"{method}/{check_type}: constant_prediction={next(iter(statuses))}")
            denom = [e.get("denominator") for e in ev if e.get("denominator") is not None]
            if denom and all((d or 0) == 0 for d in denom):
                diagnostics["flags"].append(f"{method}/{check_type}: all_denominators_zero")
        method_diag["prediction_row_status"] = method_statuses.get(method)
        method_diag["overall"] = overall
        method_diag["per_type"] = per_method[method]["per_type"]
        diagnostics["methods"][method] = method_diag

    diagnostics["reference_leakage_check"] = {
        "runner_declared_no_reference": run_manifest.get("construction_reference_read_by_runner") is False,
        "prediction_declared_no_reference": predictions_doc.get("construction_reference_read") is False,
        "all_prediction_rows_declare_no_reference": all(
            all((row.get("inference_inputs") or {}).get(key) is False
                for key in ("case_gold_read", "target_rule_id_read", "target_violation_type_read",
                            "control_reference_read", "construction_reference_read"))
            for row in rows
        ),
    }
    # Extra diagnostics: distinguish mechanical mapping gaps from real
    # capability failures.  These counts are descriptive only.
    order_unknown_reasons: dict[str, int] = {}
    order_unmapped_reasons: dict[str, int] = {}
    actor_unknown_reasons: dict[str, int] = {}
    missing_unknown_reasons: dict[str, int] = {}
    endpoint_same_activity = 0
    order_denominator_zero_cells = 0
    empty_process_cases: list[str] = []
    invisible_executor_cases: list[str] = []
    for row in rows:
        evidence_method = row.get("method_evidence") or {}
        if "process_activities" in evidence_method and not evidence_method.get("process_activities"):
            empty_process_cases.append(f"{row.get('row_method_id')}:{row.get('case_id')}")
        if "visible_executors" in evidence_method and not evidence_method.get("visible_executors"):
            invisible_executor_cases.append(f"{row.get('row_method_id')}:{row.get('case_id')}")
        for rid, sigs in (row.get("signals_by_rule") or {}).items():
            order_signal = (sigs or {}).get("out_of_order") or {}
            if order_signal.get("status") == "unknown":
                reason = str(order_signal.get("reason") or "unknown")
                order_unknown_reasons[reason] = order_unknown_reasons.get(reason, 0) + 1
            if (order_signal.get("denominator") or 0) == 0:
                order_denominator_zero_cells += 1
            for detail in ((order_signal.get("evidence") or {}).get("details") or []):
                if detail.get("mapped") is False:
                    reason = str(detail.get("reason") or "unmapped")
                    order_unmapped_reasons[reason] = order_unmapped_reasons.get(reason, 0) + 1
                elif detail.get("mapped") is True and detail.get("before_activity") == detail.get("after_activity"):
                    endpoint_same_activity += 1
            for check_type, signal in (sigs or {}).items():
                if (signal or {}).get("status") != "unknown":
                    continue
                reason = str((signal or {}).get("reason") or "unknown")
                if check_type == "incorrect_actor":
                    actor_unknown_reasons[reason] = actor_unknown_reasons.get(reason, 0) + 1
                elif check_type == "missing_action":
                    missing_unknown_reasons[reason] = missing_unknown_reasons.get(reason, 0) + 1
    projection_counts: dict[str, Any] = {}
    rule_records_path = out_dir / "rule_records.json"
    if rule_records_path.is_file():
        rule_records_doc = _load_json(rule_records_path)
        for method_key, block in (rule_records_doc or {}).items():
            recs = (block or {}).get("records") or {}
            projection_counts[method_key] = {
                str(rid): len((rec or {}).get("order_relations") or [])
                for rid, rec in recs.items()
            }
    diagnostics["unknown_cause_counts"] = {
        "order_unknown_reasons": order_unknown_reasons,
        "order_unmapped_detail_reasons": order_unmapped_reasons,
        "actor_unknown_reasons": actor_unknown_reasons,
        "missing_action_unknown_reasons": missing_unknown_reasons,
        "order_denominator_zero_cells": order_denominator_zero_cells,
        "order_endpoint_same_activity": endpoint_same_activity,
    }
    diagnostics["structural_checks"] = {
        "empty_process_cases": empty_process_cases,
        "invisible_executor_cases": invisible_executor_cases,
        "order_relation_counts_per_method_rule": projection_counts,
        "no_prediction_modification": True,
    }

    diagnostics["acceptance"] = (
        "needs_method_review"
        if diagnostics["flags"] else "diagnostic_complete_pending_method_review"
    )
    diagnostics["boundary"] = {
        "reference_is_gold": reference.get("is_gold"),
        "human_adjudicated": reference.get("human_adjudicated"),
        "claim": "Given applicable-scope checking only; not full GDPR end-to-end F1 and not MAP.",
    }

    def summary_cell(metric: Mapping[str, Any], field: str) -> Any:
        return metric.get(field)

    report = {
        "schema_version": "stage3_table3_v4_r1_report@1.0.0",
        "status": diagnostics["acceptance"],
        "reference_boundary": {
            "reference_is_gold": False,
            "human_adjudicated": False,
            "name": "AI construction reference",
            "claim": "Given applicable-scope checking only; not full GDPR end-to-end F1 and not MAP.",
        },
        "coverage_formula": "(cells - unknown_positive - unknown_negative) / cells",
        "source_hashes": {
            "execution_config": _sha_file(CONFIG),
            "run_manifest": _sha_file(manifest_path),
            "predictions": prediction_sha,
            "signals_matrix": signals_sha,
            "rule_records": _sha_file(out_dir / "rule_records.json"),
            "global_role_candidates": _sha_file(out_dir / "global_role_candidates.json"),
            "construction_reference": _sha_file(REFERENCE),
        },
        "summary": {
            method: {
                "missing_action_f1": per_method[method]["per_type"]["missing_action"]["f1"],
                "incorrect_actor_f1": per_method[method]["per_type"]["incorrect_actor"]["f1"],
                "out_of_order_f1": per_method[method]["per_type"]["out_of_order"]["f1"],
                "overall_precision": per_method[method]["overall"]["precision"],
                "overall_recall": per_method[method]["overall"]["recall"],
                "overall_f1": per_method[method]["overall"]["f1"],
                "coverage": per_method[method]["overall"]["observable_coverage"],
                "run_status": method_statuses.get(method),
            } for method in METHOD_ORDER
        },
        "methods": per_method,
        "evidence": evidence,
        "diagnostics": diagnostics,
    }
    _write_json(report_json, report)

    # Markdown.
    lines: list[str] = []
    lines.append("# Stage 3 Table 3 R1 (scoped GDPR checking)")
    lines.append("")
    lines.append("Reference is AI-constructed (`is_gold=false`, `human_adjudicated=false`). "
                 "Metrics are given applicable-scope checking, not full GDPR end-to-end F1.")
    lines.append("")
    lines.append("Coverage = `(cells - unknown_positive - unknown_negative) / cells`; "
                 "positive unknowns remain FN, negative unknowns are not TN.")
    lines.append("")
    lines.append("## Primary comparison")
    lines.append("")
    lines.append("| Method | Missing-F1 | Actor-F1 | Order-F1 | Overall-P | Overall-R | Overall-F1 | Coverage | Status |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for method in METHOD_ORDER:
        s = report["summary"][method]
        lines.append("| " + " | ".join([
            method,
            _fmt(s["missing_action_f1"]),
            _fmt(s["incorrect_actor_f1"]),
            _fmt(s["out_of_order_f1"]),
            _fmt(s["overall_precision"]),
            _fmt(s["overall_recall"]),
            _fmt(s["overall_f1"]),
            _fmt(s["coverage"]),
            str(s["run_status"]),
        ]) + " |")
    lines.append("")
    lines.append("## Per-type counts and unknown")
    lines.append("")
    lines.append("| Method | Type | TP | FP | FN | TN | Unknown-positive | Unknown-negative | N/A | P | R | F1 | Coverage |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for method in METHOD_ORDER:
        for check_type in TYPES:
            c = per_method[method]["per_type"][check_type]
            lines.append("| " + " | ".join([
                method, check_type,
                str(c["tp"]), str(c["fp"]), str(c["fn"]), str(c["tn"]),
                str(c["unknown_positive"]), str(c["unknown_negative"]),
                str(c["not_applicable_cells"]),
                _fmt(c["precision"]), _fmt(c["recall"]), _fmt(c["f1"]),
                _fmt(c["observable_coverage"]),
            ]) + " |")
        c = per_method[method]["overall"]
        lines.append("| " + " | ".join([
            method, "OVERALL",
            str(c["tp"]), str(c["fp"]), str(c["fn"]), str(c["tn"]),
            str(c["unknown_positive"]), str(c["unknown_negative"]),
            str(c["not_applicable_cells"]),
            _fmt(c["precision"]), _fmt(c["recall"]), _fmt(c["f1"]),
            _fmt(c["observable_coverage"]),
        ]) + " |")
    lines.append("")
    lines.append("## Method status")
    lines.append("")
    for method in METHOD_ORDER:
        lines.append(f"- {method}: {method_statuses.get(method)}; overall F1={_fmt(per_method[method]['overall']['f1'])}")
    lines.append("")
    lines.append("## Diagnostics")
    lines.append("")
    lines.append(f"- acceptance: `{diagnostics['acceptance']}`")
    for flag in diagnostics["flags"]:
        lines.append(f"- flag: `{flag}`")
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    manifest = {
        "schema_version": "stage3_table3_v4_r1_report_manifest@1.0.0",
        "status": report["status"],
        "inputs": report["source_hashes"],
        "outputs": {
            "json": {"path": _rel(report_json),
                     "sha256": _sha_file(report_json)},
            "markdown": {"path": _rel(report_md),
                         "sha256": _sha_file(report_md)},
        },
        "counts": {
            method: {
                "overall_cells": per_method[method]["overall"]["cells"],
                "not_applicable_cells": per_method[method]["overall"]["not_applicable_cells"],
                "tp": per_method[method]["overall"]["tp"],
                "fp": per_method[method]["overall"]["fp"],
                "fn": per_method[method]["overall"]["fn"],
                "tn": per_method[method]["overall"]["tn"],
                "unknown_positive": per_method[method]["overall"]["unknown_positive"],
                "unknown_negative": per_method[method]["overall"]["unknown_negative"],
            } for method in METHOD_ORDER
        },
        "acceptance": report["status"],
        "gold_read": False,
        "no_prediction_modification": True,
    }
    _write_json(report_manifest, manifest)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--report-json", type=Path, default=REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    parser.add_argument("--report-manifest", type=Path, default=REPORT_MANIFEST)
    args = parser.parse_args()
    report = evaluate(out_dir=args.out_dir, report_json=args.report_json,
                      report_md=args.report_md, report_manifest=args.report_manifest)
    print(json.dumps({
        "status": report["status"],
        "acceptance": report["diagnostics"]["acceptance"],
        "flags": report["diagnostics"]["flags"],
        "outputs": {
            "json": str(REPORT_JSON.relative_to(ROOT)).replace("\\", "/"),
            "markdown": str(REPORT_MD.relative_to(ROOT)).replace("\\", "/"),
            "manifest": str(REPORT_MANIFEST.relative_to(ROOT)).replace("\\", "/"),
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())