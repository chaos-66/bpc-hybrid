# -*- coding: utf-8 -*-
"""Deterministic runner for revision ``s3_semantic_grounding_v1``.

It consumes the frozen 40-variant + 40-control development panel and the
frozen Stage-2 inference pack, scores every side with the deterministic
semantic-grounding scorer, writes a new development/evidence/report revision,
and never overwrites the historical ``s3_formula_repair_v2`` evidence.

Zero real LLM/API calls.  The strict LLM fallback is implemented in the module
and covered by offline tests, but this runner records it as
``IMPLEMENTED / NOT REAL-RUN`` and never constructs a real API transport.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import spacy  # noqa: E402

from bpc_hybrid.s3_semantic_grounding_v1 import (  # noqa: E402
    REVISION,
    VIOLATION_PRIORITY,
    SemanticGroundingScorer,
    build_llm_input,
)
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes  # noqa: E402
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES,
    NONE_LABEL,
    extract_six_element_sentences,
    sentence_matches_locked,
)
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
INFERENCE_PACK = ROOT / "data/development/human_review/stage3_gold_inference_v1.json"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
REVISION_CONFIG = ROOT / "configs/stage3_semantic_grounding_v1.json"
WINTER_CONFIG = ROOT / "configs/winter_stage3_development_v1.json"

HISTORICAL_MANIFEST = ROOT / "outputs/evidence/s3_formula_repair_v2/manifest.json"
HISTORICAL_REPORT = ROOT / "outputs/reports/s3_formula_repair_v2.json"
ORIGINAL_THREE_DIR = ROOT / "outputs/evidence/s3_formula_repair_v2/original_three"
SUN_SCORER = ROOT / "src/bpc_hybrid/sun_stage3/sun_scorer.py"

OUT_DIR = ROOT / "outputs/development/s3_semantic_grounding_v1"
EVIDENCE_DIR = ROOT / "outputs/evidence/s3_semantic_grounding_v1"
REPORT_JSON = ROOT / "outputs/reports/s3_semantic_grounding_v1.json"
REPORT_MD = ROOT / "outputs/reports/s3_semantic_grounding_v1.md"

RUN_ID = "s3_semantic_grounding_v1"
EVALUATOR_VERSION = "s3_semantic_grounding_evaluator@1.0.0"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                            for row in rows), encoding="utf-8", newline="\n")


def git_state() -> dict[str, Any]:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return {"commit": commit, "dirty": bool(dirty), "dirty_paths": dirty.splitlines()[:40]}
    except Exception:
        return {"commit": "unknown", "dirty": None, "dirty_paths": []}


def rule_texts() -> dict[str, str]:
    inference = read_json(INFERENCE_PACK)
    texts: dict[str, str] = {}
    for item in inference.get("matching_items", []) + inference.get("violation_items", []):
        texts.setdefault(item["rule_id"], item["rule_text"])
    return texts


def locked_sentence(variant: Mapping[str, Any], rule_text: str, nlp: Any) -> dict[str, Any]:
    sentences = extract_six_element_sentences(variant["rule_id"], rule_text, nlp)
    sentence = next((s for s in sentences
                     if s["sentence_idx"] == variant["rule_element"]["sentence_idx"]), None)
    if sentence is None:
        raise RuntimeError(f"{variant['variant_id']}: locked sentence not found")
    if not sentence_matches_locked(sentence, variant["rule_element"]):
        raise RuntimeError(f"{variant['variant_id']}: re-extraction mismatch")
    return sentence


def rule_sentence_view(sentence: Mapping[str, Any]) -> dict[str, Any]:
    """Only Rule-Record fields used by the scorer; no expected/mutation data."""
    return {
        "rule_id": sentence.get("rule_id"),
        "modality": sentence.get("modality"),
        "actor": sentence.get("actor"),
        "action": sentence.get("action"),
        "condition": sentence.get("condition"),
        "constraint": sentence.get("constraint"),
        "exception": sentence.get("exception"),
    }


def score_side(sentence_view: Mapping[str, Any], bpmn_path: Path, process_id: str,
               contract: Mapping[str, Any], scorer: SemanticGroundingScorer,
               nlp: Any) -> dict[str, Any]:
    payload = bpmn_path.read_bytes()
    record = parse_bpmn_bytes(payload, source_path="s3_semantic_grounding_panel.bpmn",
                              contract=contract)
    model = SunProcessModel(process_id, record, nlp)
    xml_root = ET.fromstring(payload)
    result = scorer.score(sentence_view, model, record, xml_root)
    result["input_hashes"] = {
        "bpmn_sha256": hashlib.sha256(payload).hexdigest(),
        "bpmn_bytes": len(payload),
    }
    return result


def fallback_summary(scored: Mapping[str, Any]) -> dict[str, Any]:
    checks = scored.get("checks") or {}
    eligible = sorted(
        check_name for check_name, check in checks.items()
        if check.get("status") in {"unknown", "ambiguous", "unresolved"}
    )
    return {
        "eligible": bool(eligible),
        "eligible_types": eligible,
        "triggered": False,
        "real_api_calls": 0,
        "resolved": False,
        "failed": False,
        "status": "IMPLEMENTED_NOT_REAL_RUN",
        "policy": "strict JSON validator + fail-closed unknown; no real API call in this revision",
    }


def build_prediction_row(variant: Mapping[str, Any], side: str, scored: Mapping[str, Any],
                         sentence_view: Mapping[str, Any]) -> dict[str, Any]:
    decision = scored["decision"]
    predicted = decision.get("predicted")
    checks = scored.get("checks") or {}
    return {
        "schema_version": "s3_semantic_grounding_prediction@1.0.0",
        "revision": REVISION,
        "item_id": variant["variant_id"],
        "side": side,
        "process_id": variant["process_id"],
        "rule_id": variant["rule_id"],
        "expected_violation": variant["expected_violation"],
        "predicted_violation_type": predicted,
        "prediction_rule": {
            "name": decision.get("decision"),
            "reason": decision.get("reason"),
            "pending_types": decision.get("pending_types", []),
            "violation_priority": list(VIOLATION_PRIORITY),
        },
        "scores": scored.get("scores"),
        "observability": scored.get("observability"),
        "checks": {
            check_name: {
                "status": check.get("status"),
                "observable": check.get("observable"),
                "violation": check.get("violation"),
                "reason": check.get("reason"),
                "score": check.get("score"),
            }
            for check_name, check in checks.items()
        },
        "check_details": {
            check_name: {
                key: value for key, value in check.items()
                if key not in {"score", "observable", "violation", "status", "reason"}
            }
            for check_name, check in checks.items()
        },
        "action_grounding": scored.get("action_grounding"),
        "llm_fallback": fallback_summary(scored),
        "llm_input_excerpt": build_llm_input(sentence_view, scored.get("action_grounding") or {},
                                             checks),
        "gold_visible_to_scorer": False,
        "prediction_input_fields": sorted(rule_sentence_view(sentence_view).keys()),
    }


def _p_r_f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def evaluate_variant_only(rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_type = {t: {"tp": 0, "fp": 0, "fn": 0} for t in EXTENDED_TYPES}
    unobservable_by_reason: dict[str, int] = {}
    for row in rows:
        gold = row["expected_violation"]
        pred = row["predicted_violation_type"]
        if pred == gold:
            per_type[gold]["tp"] += 1
        elif pred in EXTENDED_TYPES:
            per_type[gold]["fn"] += 1
            per_type[pred]["fp"] += 1
        else:
            per_type[gold]["fn"] += 1
            obs = row.get("observability", {}).get(gold, {})
            if obs.get("observable") is False:
                reason = obs.get("reason") or "unspecified"
                unobservable_by_reason[reason] = unobservable_by_reason.get(reason, 0) + 1
    per_type_results = {
        t: {"support": per_type[t]["tp"] + per_type[t]["fn"],
            **_p_r_f1(per_type[t]["tp"], per_type[t]["fp"], per_type[t]["fn"])}
        for t in EXTENDED_TYPES
    }
    total_tp = sum(per_type[t]["tp"] for t in EXTENDED_TYPES)
    total_fp = sum(per_type[t]["fp"] for t in EXTENDED_TYPES)
    total_fn = sum(per_type[t]["fn"] for t in EXTENDED_TYPES)
    micro = _p_r_f1(total_tp, total_fp, total_fn)
    exact = sum(1 for row in rows
                if row["predicted_violation_type"] == row["expected_violation"]) / len(rows)
    return {
        "support": len(rows),
        "per_type": per_type_results,
        "macro_f1_four_types": round(
            sum(per_type_results[t]["f1"] for t in EXTENDED_TYPES) / len(EXTENDED_TYPES), 4),
        "micro_f1": micro["f1"],
        "exact_type_accuracy": round(exact, 4),
        "unobservable": sum(unobservable_by_reason.values()),
        "unobservable_by_reason": unobservable_by_reason,
    }


def evaluate_per_type_checks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Binary multi-label evaluation of each structural check over all variants.

    This is the natural view for the four extension types: the control-flow
    mutation for one type is not required to erase valid evidence for another
    field in the same sentence, and several variants are byte-identical because
    their controls added different mechanisms on top of the same source model.
    """
    per_type = {t: {"tp": 0, "fp": 0, "fn": 0} for t in EXTENDED_TYPES}
    for row in rows:
        expected = row["expected_violation"]
        for check_name in EXTENDED_TYPES:
            detail = (row.get("checks") or {}).get(check_name) or {}
            detected = detail.get("violation") is True
            if expected == check_name and detected:
                per_type[check_name]["tp"] += 1
            elif expected == check_name:
                per_type[check_name]["fn"] += 1
            elif detected:
                per_type[check_name]["fp"] += 1
    per_type_results = {
        t: {"support": per_type[t]["tp"] + per_type[t]["fn"],
            **_p_r_f1(per_type[t]["tp"], per_type[t]["fp"], per_type[t]["fn"])}
        for t in EXTENDED_TYPES
    }
    return {
        "support": len(rows),
        "per_type": per_type_results,
        "macro_f1_four_types": round(
            sum(per_type_results[t]["f1"] for t in EXTENDED_TYPES)
            / len(EXTENDED_TYPES), 4),
        "note": ("each type is evaluated as an independent binary structural check on "
                 "the variant side; no final single-label priority is applied here"),
    }


def evaluate_target_field(variant_rows: list[dict[str, Any]],
                          control_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-type target-field diagnostic.

    For each expected type t it uses only ``checks[t]`` on the corresponding
    variant and control.  Controls in this panel are synthetic and only
    guarantee their own target field; the panel does not make them globally
    compliant across all four rule fields.  This diagnostic therefore isolates
    "did the method find the mutated target field" from cross-field findings.
    """
    per_type: dict[str, dict[str, Any]] = {}
    controls = {row["item_id"]: row for row in control_rows}
    for expected in EXTENDED_TYPES:
        tp = fn = unknown = 0
        control_violation = control_unknown = 0
        for variant in variant_rows:
            if variant["expected_violation"] != expected:
                continue
            check = (variant.get("checks") or {}).get(expected) or {}
            if check.get("violation") is True:
                tp += 1
            elif check.get("status") in {"unknown", "ambiguous"}:
                unknown += 1
                fn += 1
            else:
                fn += 1
            control = controls.get(variant["item_id"]) or {}
            control_check = (control.get("checks") or {}).get(expected) or {}
            if control_check.get("violation") is True:
                control_violation += 1
            elif control_check.get("status") in {"unknown", "ambiguous"}:
                control_unknown += 1
        precision = tp / (tp + control_violation) if (tp + control_violation) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        per_type[expected] = {
            "variant_support": tp + fn,
            "variant_detected": tp,
            "variant_not_detected": fn,
            "variant_unknown": unknown,
            "control_target_violation": control_violation,
            "control_target_unknown": control_unknown,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    return {
        "per_type": per_type,
        "macro_f1_four_types": round(
            sum(per_type[t]["f1"] for t in EXTENDED_TYPES) / len(EXTENDED_TYPES), 4),
        "control_target_false_positive_rate": round(
            sum(per_type[t]["control_target_violation"] for t in EXTENDED_TYPES)
            / len(control_rows), 4),
        "note": ("target-field-only diagnostic; controls are not globally compliant "
                 "for the other three rule fields, so this is reported separately "
                 "from the unified paired controls"),
    }


def identifiability_audit(panel: Mapping[str, Any]) -> dict[str, Any]:
    """Audit byte-identical variant inputs across expected types.

    The frozen panel adds one synthetic control mechanism per target type and
    removes it in the variant.  When two targets mutate different mechanisms of
    the same source model, their variants can be byte-identical.  A single-side
    deterministic method must then make the same prediction for both, so a
    single-label unified accuracy has a ceiling below one.  This block reports
    the collision without using expected labels during inference.
    """
    groups: dict[str, list[dict[str, str]]] = {}
    for variant in panel["variants"]:
        path = ROOT / variant["variant_bpmn"]
        digest = sha256_file(path)
        groups.setdefault(digest, []).append({
            "item_id": variant["variant_id"],
            "expected_violation": variant["expected_violation"],
        })
    collisions = [
        {"variant_bpmn_sha256": digest, "variants": members}
        for digest, members in sorted(groups.items()) if len(members) > 1
    ]
    return {
        "audit_kind": "variant_input_identifiability",
        "collision_group_count": len(collisions),
        "variant_count_in_collisions": sum(len(item["variants"]) for item in collisions),
        "collision_groups": collisions,
        "implication": ("single-label unified accuracy is bounded below 1 by input "
                        "collisions; per-type binary checks and explicit abstention "
                        "are the valid reporting views"),
    }


def evaluate_paired(variant_rows: list[dict[str, Any]],
                    control_rows: list[dict[str, Any]]) -> dict[str, Any]:
    controls = {row["item_id"]: row for row in control_rows}
    labels = [NONE_LABEL] + list(EXTENDED_TYPES)
    per_class = {label: {"tp": 0, "fp": 0, "fn": 0} for label in labels}
    items: list[tuple[str, str | None]] = []
    paired_ok = 0
    control_fp = 0
    variant_unobservable = 0
    control_unobservable = 0
    unobservable_by_reason: dict[str, int] = {}
    for variant in variant_rows:
        control = controls[variant["item_id"]]
        expected = variant["expected_violation"]
        variant_pred = variant["predicted_violation_type"]
        control_pred = control["predicted_violation_type"]
        if control_pred in EXTENDED_TYPES:
            control_fp += 1
        if control_pred is None:
            control_unobservable += 1
            reason = "control_abstention"
            unobservable_by_reason[reason] = unobservable_by_reason.get(reason, 0) + 1
        if variant_pred is None:
            variant_unobservable += 1
            reason = variant.get("observability", {}).get(expected, {}).get("reason") or "unspecified"
            unobservable_by_reason[reason] = unobservable_by_reason.get(reason, 0) + 1
        items.append((NONE_LABEL, control_pred))
        items.append((expected, variant_pred))
        if control_pred == NONE_LABEL and variant_pred == expected:
            paired_ok += 1
    correct = 0
    for gold, pred in items:
        if pred == gold:
            correct += 1
            per_class[gold]["tp"] += 1
        else:
            per_class[gold]["fn"] += 1
            if pred in per_class:
                per_class[pred]["fp"] += 1
    per_class_results = {
        label: {"support": per_class[label]["tp"] + per_class[label]["fn"],
                **_p_r_f1(per_class[label]["tp"], per_class[label]["fp"],
                          per_class[label]["fn"])}
        for label in labels
    }
    return {
        "schema_version": "s3_semantic_grounding_paired_evaluator@1.0.0",
        "total_objects": len(items),
        "control_objects": len(control_rows),
        "variant_objects": len(variant_rows),
        "five_class_accuracy": round(correct / len(items), 4) if items else 0.0,
        "variant_exact_type_accuracy": round(
            sum(1 for variant in variant_rows
                if variant["predicted_violation_type"] == variant["expected_violation"])
            / len(variant_rows), 4),
        "control_false_positive_rate": round(control_fp / len(control_rows), 4),
        "paired_accuracy": round(paired_ok / len(variant_rows), 4),
        "per_class": per_class_results,
        "macro_f1_four_violation_types": round(
            sum(per_class_results[t]["f1"] for t in EXTENDED_TYPES) / len(EXTENDED_TYPES), 4),
        "macro_f1_five_classes": round(
            sum(per_class_results[label]["f1"] for label in labels) / len(labels), 4),
        "unobservable": {
            "total": variant_unobservable + control_unobservable,
            "variant": variant_unobservable,
            "control": control_unobservable,
            "by_reason": unobservable_by_reason,
        },
        "denominator_policy": ("all 80 objects stay in every denominator; None is an "
                               "abstention and counts as an error, never as a violation "
                               "or as explicit compliance"),
    }


def historical_baseline() -> dict[str, Any]:
    report = read_json(HISTORICAL_REPORT)
    ext = report["extended_four_types"]["reference"]["winter"]
    variant = ext["variant_evaluation"]
    paired = ext["paired_evaluation"]
    return {
        "source": HISTORICAL_REPORT.relative_to(ROOT).as_posix(),
        "arm": "reference/winter",
        "variant_evaluation": {
            "per_type": variant["per_type"],
            "macro_f1_four_types": variant["macro_f1"],
            "micro_f1": variant["micro_f1"],
            "exact_type_accuracy": variant["exact_type_accuracy"],
            "unobservable": variant["unobservable"],
            "unobservable_by_reason": variant["denominator"]["unobservable_by_reason"],
        },
        "paired_evaluation": {
            "five_class_accuracy": paired["five_class_accuracy"],
            "control_false_positive_rate": paired["control_false_positive_rate"],
            "paired_accuracy": paired["paired_accuracy"],
            "macro_f1_four_violation_types": paired["macro_f1_four_violation_types"],
            "macro_f1_five_classes": paired["macro_f1_five_classes"],
            "unobservable": paired["unobservable"],
        },
    }


def verify_original_three_unchanged() -> dict[str, Any]:
    manifest = read_json(HISTORICAL_MANIFEST)
    expected = {
        key: value for key, value in manifest.get("artifacts", {}).items()
        if key.replace("\\", "/").startswith("outputs/evidence/s3_formula_repair_v2/original_three")
    }
    checked = {}
    for key, expected_sha in sorted(expected.items()):
        path = ROOT / key.replace("\\", "/")
        actual = sha256_file(path)
        checked[path.relative_to(ROOT).as_posix()] = {
            "expected_sha256": expected_sha,
            "actual_sha256": actual,
            "match": actual == expected_sha,
        }
    scorer_expected = None
    for key, value in manifest.get("implementation_hashes", {}).items():
        if key.replace("\\", "/") == "src/bpc_hybrid/sun_stage3/sun_scorer.py":
            scorer_expected = value
            break
    hash_mode = manifest.get("implementation_hash_mode", "raw_bytes")
    scorer_raw = sha256_file(SUN_SCORER)
    scorer_canonical = hashlib.sha256(
        SUN_SCORER.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    scorer_actual = scorer_canonical if hash_mode == "canonical_lf_utf8_text" else scorer_raw
    result = {
        "historical_manifest": HISTORICAL_MANIFEST.relative_to(ROOT).as_posix(),
        "original_three_artifacts": checked,
        "original_three_all_match": bool(checked) and all(
            item["match"] for item in checked.values()),
        "sun_scorer": {
            "path": SUN_SCORER.relative_to(ROOT).as_posix(),
            "historical_hash_mode": hash_mode,
            "expected_sha256": scorer_expected,
            "actual_sha256": scorer_actual,
            "raw_sha256": scorer_raw,
            "canonical_lf_sha256": scorer_canonical,
            "match": scorer_expected == scorer_actual,
        },
    }
    if not result["original_three_all_match"] or not result["sun_scorer"]["match"]:
        raise RuntimeError("frozen original-three evidence or Sun scorer changed")
    return result


def run(*, overwrite: bool = False) -> dict[str, Any]:
    if OUT_DIR.exists() or EVIDENCE_DIR.exists() or REPORT_JSON.exists() or REPORT_MD.exists():
        if not overwrite:
            raise RuntimeError("refusing to overwrite existing s3_semantic_grounding_v1 outputs")
    config = read_json(REVISION_CONFIG)
    panel = read_json(PANEL)
    inference = read_json(INFERENCE_PACK)
    texts = rule_texts()
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    regression = verify_original_three_unchanged()
    thresholds = config["thresholds"]
    gamma_ext = float(thresholds["gamma_ext"])
    gamma = float(thresholds["action_similarity_gamma"])

    nlp = spacy.load("en_core_web_sm")
    similarity = WinterSimilarity(nlp)
    scorer = SemanticGroundingScorer(similarity.text_pair, gamma=gamma,
                                     gamma_ext=gamma_ext, config=config)

    variant_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    runtime_by_item: dict[str, float] = {}
    fallback_eligible = 0
    for variant in panel["variants"]:
        sentence = locked_sentence(variant, texts[variant["rule_id"]], nlp)
        view = rule_sentence_view(sentence)
        start = time.time()
        variant_scored = score_side(view, ROOT / variant["variant_bpmn"],
                                    variant["process_id"], contract, scorer, nlp)
        control_scored = score_side(view, ROOT / variant["control_bpmn"],
                                    variant["process_id"], contract, scorer, nlp)
        runtime_by_item[variant["variant_id"]] = round(time.time() - start, 4)
        variant_row = build_prediction_row(variant, "variant", variant_scored, view)
        control_row = build_prediction_row(variant, "control", control_scored, view)
        variant_rows.append(variant_row)
        control_rows.append(control_row)
        fallback_eligible += int(bool(variant_row["llm_fallback"]["eligible"])
                                 or bool(control_row["llm_fallback"]["eligible"]))

    variant_eval = evaluate_variant_only(variant_rows)
    per_type_eval = evaluate_per_type_checks(variant_rows)
    target_field_eval = evaluate_target_field(variant_rows, control_rows)
    paired_eval = evaluate_paired(variant_rows, control_rows)
    identifiability = identifiability_audit(panel)
    baseline = historical_baseline()
    metrics = {
        "schema_version": "s3_semantic_grounding_metrics@1.0.0",
        "run_id": RUN_ID,
        "scope": "development_only_synthetic_controlled_panel",
        "variant_evaluation": variant_eval,
        "per_type_check_evaluation": per_type_eval,
        "target_field_diagnostic": target_field_eval,
        "paired_evaluation": paired_eval,
        "identifiability_audit": identifiability,
        "fallback": {
            "real_api_calls": 0,
            "status": "IMPLEMENTED_NOT_REAL_RUN",
            "eligible_objects": fallback_eligible,
            "triggered_objects": 0,
            "resolved_objects": 0,
            "failed_objects": 0,
            "note": ("The fallback schema/validator/mock plumbing is implemented and tested "
                     "offline. No real API authorization was present for this revision, so "
                     "no fallback call was made and no LLM-improved metric is reported."),
        },
        "baseline_comparison": {
            "baseline": baseline,
            "delta_variant_macro_f1_four_types": round(
                variant_eval["macro_f1_four_types"]
                - baseline["variant_evaluation"]["macro_f1_four_types"], 4),
            "delta_variant_exact_type_accuracy": round(
                variant_eval["exact_type_accuracy"]
                - baseline["variant_evaluation"]["exact_type_accuracy"], 4),
            "delta_paired_macro_f1_five_classes": round(
                paired_eval["macro_f1_five_classes"]
                - baseline["paired_evaluation"]["macro_f1_five_classes"], 4),
            "delta_control_false_positive_rate": round(
                paired_eval["control_false_positive_rate"]
                - baseline["paired_evaluation"]["control_false_positive_rate"], 4),
            "delta_paired_accuracy": round(
                paired_eval["paired_accuracy"]
                - baseline["paired_evaluation"]["paired_accuracy"], 4),
        },
    }

    implementation_files = [
        Path(__file__),
        ROOT / "src/bpc_hybrid/s3_semantic_grounding_v1.py",
        REVISION_CONFIG,
        ROOT / "tests/test_s3_semantic_grounding_v1.py",
    ]
    input_files = [
        PANEL, INFERENCE_PACK, STRUCTURAL_CONTRACT, WINTER_CONFIG,
        HISTORICAL_MANIFEST, HISTORICAL_REPORT,
    ]
    manifest = {
        "schema_version": "s3_semantic_grounding_manifest@1.0.0",
        "run_id": RUN_ID,
        "revision": REVISION,
        "scope": "development_only",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git": git_state(),
        "evaluator_version": EVALUATOR_VERSION,
        "sample_count": {"variants": len(variant_rows), "controls": len(control_rows),
                         "objects": len(variant_rows) + len(control_rows)},
        "inputs": {path.relative_to(ROOT).as_posix(): sha256_file(path)
                   for path in input_files},
        "implementation_hashes": {path.relative_to(ROOT).as_posix(): sha256_file(path)
                                  for path in implementation_files},
        "config_sha256": sha256_file(REVISION_CONFIG),
        "panel_sha256": sha256_file(PANEL),
        "thresholds": {
            "gamma_ext": gamma_ext,
            "action_similarity_gamma": gamma,
            "action_top_k_similarity": thresholds["action_top_k_similarity"],
            "action_top_k_lexical": thresholds["action_top_k_lexical"],
        },
        "frozen_original_three_regression": regression,
        "llm_fallback": {
            "status": "IMPLEMENTED_NOT_REAL_RUN",
            "real_api_calls": 0,
            "network_calls": 0,
            "provider": "none",
            "schema_version": config["llm_fallback"]["schema_version"],
            "strict_json_validator": True,
            "fail_closed": True,
        },
        "safety": {
            "human_gold_read": False,
            "human_gold_modified": False,
            "panel_modified": False,
            "original_three_modified": False,
            "existing_s3_formula_repair_v2_overwritten": False,
            "real_api_calls": 0,
            "network_calls": 0,
            "development_only_not_formal_oracle": True,
            "prediction_metadata_blind": True,
        },
        "metrics_file": (OUT_DIR / "metrics.json").relative_to(ROOT).as_posix(),
        "predictions_file": (OUT_DIR / "predictions.jsonl").relative_to(ROOT).as_posix(),
        "evidence_metrics_file": (EVIDENCE_DIR / "metrics.json").relative_to(ROOT).as_posix(),
        "evidence_predictions_file": (EVIDENCE_DIR / "predictions.jsonl").relative_to(ROOT).as_posix(),
        "artifact_hashes_file": (EVIDENCE_DIR / "artifact_hashes.json").relative_to(ROOT).as_posix(),
    }

    if OUT_DIR.exists() and not overwrite:
        raise RuntimeError("run dir already exists")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_rows(OUT_DIR / "predictions.jsonl", variant_rows + control_rows)
    write_json(OUT_DIR / "metrics.json", metrics)
    write_json(OUT_DIR / "manifest.json", manifest)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    write_json(EVIDENCE_DIR / "manifest.json", manifest)
    write_json(EVIDENCE_DIR / "metrics.json", metrics)
    write_rows(EVIDENCE_DIR / "predictions.jsonl", variant_rows + control_rows)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    if REPORT_JSON.exists() and not overwrite:
        raise RuntimeError("report already exists")
    write_json(REPORT_JSON, {
        "schema_version": "s3_semantic_grounding_report@1.0.0",
        "revision": REVISION,
        "scope": "development_only",
        "generated_utc": manifest["generated_utc"],
        "status": "VERIFIED_DEVELOPMENT_RESULT",
        "baseline_comparison": metrics["baseline_comparison"],
        "variant_evaluation": metrics["variant_evaluation"],
        "per_type_check_evaluation": metrics["per_type_check_evaluation"],
        "target_field_diagnostic": metrics["target_field_diagnostic"],
        "paired_evaluation": metrics["paired_evaluation"],
        "identifiability_audit": metrics["identifiability_audit"],
        "fallback": metrics["fallback"],
        "manifest": manifest,
        "safety": manifest["safety"],
        "claim_boundary": (
            "Development-only synthetic controlled-panel result. Not the formal "
            "Oracle, not human Gold, and not a claim about Winter/Sun native "
            "capability for the four new types. The LLM fallback was not real-run. "
            "The panel has byte-identical variant inputs across expected types, so "
            "the unified single-label metric is bounded by input non-identifiability; "
            "the per-type binary-check evaluation is the valid type-level view."
        ),
    })
    REPORT_MD.write_text(render_markdown(metrics), encoding="utf-8", newline="\n")
    artifact_paths = [
        OUT_DIR / "predictions.jsonl", OUT_DIR / "metrics.json", OUT_DIR / "manifest.json",
        EVIDENCE_DIR / "predictions.jsonl", EVIDENCE_DIR / "metrics.json",
        EVIDENCE_DIR / "manifest.json", REPORT_JSON, REPORT_MD,
    ]
    write_json(EVIDENCE_DIR / "artifact_hashes.json", {
        "schema_version": "s3_semantic_grounding_artifact_hashes@1.0.0",
        "run_id": RUN_ID,
        "scope": "development_only",
        "artifacts": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in artifact_paths
        },
    })
    return {"metrics": metrics, "manifest": manifest, "report_json": str(REPORT_JSON)}


def render_markdown(metrics: Mapping[str, Any]) -> str:
    variant = metrics["variant_evaluation"]
    binary = metrics["per_type_check_evaluation"]
    target = metrics["target_field_diagnostic"]
    paired = metrics["paired_evaluation"]
    baseline = metrics["baseline_comparison"]["baseline"]
    lines = [
        "# s3_semantic_grounding_v1 (development-only)",
        "",
        "Deterministic-first Stage 3 semantic-grounding repair over the frozen "
        "40-variant + 40-control development panel.  Zero real API calls.",
        "",
        "## Per-type binary structural checks (40 variants)",
        "",
        "| Type | P | R | F1 |",
        "|---|---|---|---|",
    ]
    for t in EXTENDED_TYPES:
        row = binary["per_type"][t]
        lines.append(f"| {t} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} |")
    lines += [
        "",
        f"- Binary per-type Macro-F1: **{binary['macro_f1_four_types']:.4f}**",
        "",
        "## Unified variant decision (fixed structural-specificity priority)",
        "",
        "| Type | P | R | F1 |",
        "|---|---|---|---|",
    ]
    for t in EXTENDED_TYPES:
        row = variant["per_type"][t]
        lines.append(f"| {t} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} |")
    lines += [
        "",
        f"- Unified 4-type Macro-F1: **{variant['macro_f1_four_types']:.4f}**",
        f"- Micro-F1: **{variant['micro_f1']:.4f}**",
        f"- Exact type accuracy: **{variant['exact_type_accuracy']:.4f}**",
        f"- Unobservable: **{variant['unobservable']}**",
        "",
        "## Target-field diagnostic (each pair scored only on its mutated field)",
        "",
        "| Type | P | R | F1 | Variant detected | Control target violations |",
        "|---|---|---|---|---|---|",
    ]
    for t in EXTENDED_TYPES:
        row = target["per_type"][t]
        lines.append(
            f"| {t} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} | "
            f"{row['variant_detected']}/{row['variant_support']} | "
            f"{row['control_target_violation']} |"
        )
    lines += [
        "",
        f"- Target-field 4-type Macro-F1: **{target['macro_f1_four_types']:.4f}**",
        f"- Control target-field FP rate: **{target['control_target_false_positive_rate']:.4f}**",
        "",
        "## Paired 80-object evaluation (unified single-label)",
        "",
        f"- 5-class accuracy: **{paired['five_class_accuracy']:.4f}**",
        f"- Variant exact accuracy: **{paired['variant_exact_type_accuracy']:.4f}**",
        f"- Control any-type false-positive rate: **{paired['control_false_positive_rate']:.4f}**",
        f"- Paired accuracy: **{paired['paired_accuracy']:.4f}**",
        f"- 4-type Macro-F1: **{paired['macro_f1_four_violation_types']:.4f}**",
        f"- 5-class Macro-F1: **{paired['macro_f1_five_classes']:.4f}**",
        f"- Unobservable total: **{paired['unobservable']['total']}**",
        "",
        "## Input-identifiability audit",
        "",
        f"- Byte-identical variant-input collision groups: **{metrics['identifiability_audit']['collision_group_count']}** "
        f"covering **{metrics['identifiability_audit']['variant_count_in_collisions']}** variants.",
        "- A single-side method must make identical predictions inside a collision group; the unified "
        "single-label metrics are therefore structurally bounded. The per-type and target-field views are "
        "the valid type-level evidence.",
        "",
        "## Baseline comparison (historical reference/winter)",
        "",
        f"- Historical unified variant Macro-F1: {baseline['variant_evaluation']['macro_f1_four_types']:.4f}",
        f"- Historical paired 5-class Macro-F1: {baseline['paired_evaluation']['macro_f1_five_classes']:.4f}",
        f"- Historical paired accuracy: {baseline['paired_evaluation']['paired_accuracy']:.4f}",
        f"- Delta unified variant Macro-F1: {metrics['baseline_comparison']['delta_variant_macro_f1_four_types']:+.4f}",
        f"- Delta paired 5-class Macro-F1: {metrics['baseline_comparison']['delta_paired_macro_f1_five_classes']:+.4f}",
        f"- Delta paired accuracy: {metrics['baseline_comparison']['delta_paired_accuracy']:+.4f}",
        "",
        "## LLM semantic-grounding fallback",
        "",
        f"- Status: **{metrics['fallback']['status']}**",
        f"- Real API calls: **{metrics['fallback']['real_api_calls']}**",
        f"- Fallback-eligible objects (deterministic ambiguity): **{metrics['fallback']['eligible_objects']}**",
        f"- {metrics['fallback']['note']}",
        "",
        "## Claim boundary",
        "",
        "Development-only synthetic controlled panel; not formal Oracle and not human Gold. "
        "The four types are project extensions, not native Winter/Sun capabilities. "
        "The fallback is implemented and offline-validated but was not real-run.",
        "",
    ]
    return "\n".join(lines)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true",
                        help="allow replacing existing s3_semantic_grounding_v1 outputs")
    args = parser.parse_args()
    result = run(overwrite=args.overwrite)
    metrics = result["metrics"]
    print(json.dumps({
        "revision": REVISION,
        "variant_macro_f1_four_types": metrics["variant_evaluation"]["macro_f1_four_types"],
        "variant_exact_type_accuracy": metrics["variant_evaluation"]["exact_type_accuracy"],
        "paired_macro_f1_five_classes": metrics["paired_evaluation"]["macro_f1_five_classes"],
        "control_false_positive_rate": metrics["paired_evaluation"]["control_false_positive_rate"],
        "paired_accuracy": metrics["paired_evaluation"]["paired_accuracy"],
        "llm_fallback": metrics["fallback"]["status"],
        "real_api_calls": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
