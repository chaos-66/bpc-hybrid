# -*- coding: utf-8 -*-
"""Build, publish, and replay SEP-C2 predecessor predictions/evaluations.

Each method is a separate builder.  Builders are Gold-blind by construction:
they receive the formal input records and never import or open ``data/gold``.
Evaluation is called only after predictions have been materialised in memory.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.sun_predecessors import common, evaluation
from bpc_hybrid.sun_predecessors.keyword import KeywordClassifier


EVIDENCE_ROOT_REL = "outputs/evidence/sep_c2_sun_predecessors_v1"
REPORTS_ROOT_REL = "outputs/reports"


def _artifact_path_prefix(method_id: str) -> str:
    return f"{EVIDENCE_ROOT_REL}/{method_id}"


def _report_basename(method_id: str) -> str:
    return f"sep_c2_sun_predecessor_{method_id}_v1"


def _source_binding(formal_root: Path, rel: str) -> dict[str, Any]:
    path = Path(formal_root) / rel
    return {
        "path": rel,
        "sha256": common.sha256_file(path),
        "byte_size": path.stat().st_size,
    }


def _rule_diagnostics(decisions: Sequence[Any], sample_ids: Sequence[str]) -> dict[str, Any]:
    matched_class = Counter(decision.matched_class for decision in decisions)
    labels = Counter(decision.label for decision in decisions)
    fallback = sum(1 for decision in decisions if decision.matched_rule is None)
    rows = [
        {
            "sample_id": sample_id,
            "predicted": decision.label,
            "matched_class": decision.matched_class,
            "matched_rule": decision.matched_rule,
            "matched_surface": decision.matched_surface,
        }
        for sample_id, decision in zip(sample_ids, decisions, strict=True)
    ]
    return {
        "schema_version": "sep_c2_sun_predecessor_cf_kw_diagnostics@1.0.0",
        "records": len(rows),
        "label_counts": dict(sorted(labels.items())),
        "matched_class_counts": dict(sorted(matched_class.items())),
        "fallback_count": fallback,
        "matched_decision_count": len(rows) - fallback,
        "rows": rows,
    }


def build_cf_kw(formal_root: Path) -> dict[str, Any]:
    formal_root = Path(formal_root)
    config_rel = "configs/sep_c2_sun_predecessors_v1/cf_kw_v1.json"
    config_path = formal_root / config_rel
    classifier = KeywordClassifier.from_path(config_path)
    spec = common.method_spec("cf_kw")
    records = evaluation.load_formal_input(formal_root)
    decisions = []
    attempts = []
    for row in records:
        text = row[spec.input_field]
        decision = classifier.classify(text)
        decisions.append(decision)
        attempts.append(
            evaluation.make_attempt(
                sample_id=row["sample_id"],
                source_text=text,
                label=decision.label,
                method_id=spec.method_id,
                evidence_text=decision.matched_surface or text,
            )
        )
    evaluated = evaluation.evaluate_attempts(formal_root, attempts)
    diagnostics = _rule_diagnostics(decisions, [row["sample_id"] for row in records])

    input_rel = evaluation.FORMAL_INPUT_REL
    gold_rel = evaluation.FORMAL_GOLD_REL
    manifest = {
        "schema_version": "sep_c2_sun_predecessor_method_manifest@1.0.0",
        "method_id": spec.method_id,
        "claim_scope": "development_zero_api_predecessor_method_comparison",
        "sun_source_and_role": spec.sun_role,
        "reproduction_class": spec.reproduction_class,
        "version_caveat": (
            "Built against the locally available earlier author manuscript; the final Springer version "
            "could not be checked in this offline environment. No exact-original claim is made."
        ),
        "formal_input_binding": _source_binding(formal_root, input_rel),
        "formal_gold_binding_read_only_for_evaluation": _source_binding(formal_root, gold_rel),
        "evaluator_binding": _source_binding(
            formal_root, "src/bpc_hybrid/formal_stage2_evaluation.py"
        ),
        "config_binding": _source_binding(formal_root, config_rel),
        "implementation_bindings": {
            rel: _source_binding(formal_root, rel)
            for rel in (
                "src/bpc_hybrid/sun_predecessors/common.py",
                "src/bpc_hybrid/sun_predecessors/evaluation.py",
                "src/bpc_hybrid/sun_predecessors/keyword.py",
                "src/bpc_hybrid/sun_predecessors/runner.py",
                "scripts/run_sep_c2_sun_predecessor_v1.py",
            )
        },
        "safety": {
            "new_llm_api_calls": 0,
            "new_network_calls": 0,
            "gold_read_by_prediction_code": False,
            "gold_used_for_evaluation": True,
            "post_result_tuning": False,
        },
    }
    evaluation_document = {
        "schema_version": "sep_c2_sun_predecessor_evaluation_file@1.0.0",
        "method_id": spec.method_id,
        "evaluation": evaluated,
    }
    prediction_document = {
        "schema_version": "sep_c2_sun_predecessor_predictions@1.0.0",
        "method_id": spec.method_id,
        "records": attempts,
    }
    config_snapshot = {
        "schema_version": "sep_c2_sun_predecessor_config@1.0.0",
        "method": {
            "method_id": spec.method_id,
            "sun_role": spec.sun_role,
            "reproduction_class": spec.reproduction_class,
            "input_field": spec.input_field,
            "input_language": spec.input_language,
            "training_data": spec.training_data,
            "notes": spec.notes,
        },
        "config_path": config_rel,
        "config_sha256": common.sha256_file(config_path),
    }
    artifacts = {
        f"{_artifact_path_prefix(spec.method_id)}/predictions.json": prediction_document,
        f"{_artifact_path_prefix(spec.method_id)}/evaluation.json": evaluation_document,
        f"{_artifact_path_prefix(spec.method_id)}/diagnostics.json": diagnostics,
        f"{_artifact_path_prefix(spec.method_id)}/config_snapshot.json": config_snapshot,
        f"{_artifact_path_prefix(spec.method_id)}/manifest.json": manifest,
    }
    report = {
        "schema_version": "sep_c2_sun_predecessor_report@1.0.0",
        "report_id": _report_basename(spec.method_id),
        "status": "completed_zero_api_predecessor_method_run",
        "method": config_snapshot["method"],
        "version_caveat": manifest["version_caveat"],
        "execution": {
            "formal_input": input_rel,
            "formal_input_sha256": manifest["formal_input_binding"]["sha256"],
            "input_field": spec.input_field,
            "input_language": spec.input_language,
            "records": len(records),
        },
        "training": {
            "required": False,
            "training_data": spec.training_data,
            "model_selection": "none",
        },
        "prediction": {
            "artifact_dir": _artifact_path_prefix(spec.method_id),
            "predicted_count": diagnostics["label_counts"],
            "fallback_count": diagnostics["fallback_count"],
        },
        "evaluation": evaluated,
        "safety": manifest["safety"],
    }
    return {
        "artifacts": artifacts,
        "report": report,
        "report_rel": f"{REPORTS_ROOT_REL}/{_report_basename(spec.method_id)}.json",
        "report_md_rel": f"{REPORTS_ROOT_REL}/{_report_basename(spec.method_id)}.md",
    }


def build_artifacts(method_id: str, formal_root: Path) -> dict[str, Any]:
    builders = {
        "cf_kw": build_cf_kw,
    }
    builder = builders.get(method_id)
    if builder is None:
        raise common.SunPredecessorError(
            f"method {method_id!r} is not implemented in this runner revision"
        )
    return builder(formal_root)


def render_markdown(report: Mapping[str, Any]) -> str:
    method = report["method"]
    evaluated = report["evaluation"]
    official = evaluated["official_evaluator"]
    lines = [
        f"# SEP-C2 Sun-predecessor run: {method['method_id']}",
        "",
        f"- status: **{report['status']}**",
        f"- Sun role: {method['sun_role']}",
        f"- reproduction class: {method['reproduction_class']}",
        f"- input field/language: `{report['execution']['input_field']}` / `{report['execution']['input_language']}`",
        f"- records scored: {evaluated['records_scored']} / {evaluated['records_expected']}",
        f"- missing / failed / unlabeled: {evaluated['records_missing']} / {evaluated['records_failed']} / {evaluated['unlabeled_predictions']}",
        f"- accuracy: {official['accuracy']:.4f}",
        f"- macro-F1: {official['macro_f1']:.4f}",
        "",
        "| class | precision | recall | F1 | gold support | predicted count |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    support = evaluated["gold_support"]
    predicted = evaluated["predicted_count"]
    for row in official["per_class"]:
        lines.append(
            f"| {row['class']} | {row['precision']:.4f} | {row['recall']:.4f} | "
            f"{row['f1']:.4f} | {support[row['class']]} | {predicted[row['class']]} |"
        )
    lines += [
        "",
        f"- version caveat: {report['version_caveat']}",
        f"- new LLM/API calls: {report['safety']['new_llm_api_calls']}",
        "",
    ]
    return "\n".join(lines)