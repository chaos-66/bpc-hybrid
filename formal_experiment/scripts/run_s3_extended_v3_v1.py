# -*- coding: utf-8 -*-
"""S3.9-EXT v3 arm: the four extended violation types with v3 action localization.

One new method arm on the **frozen** 40-variant / 40-control extension panel:

* the panel, the rule source, the four formulas, the ``gamma_ext`` decision rule
  and the frozen evaluators are reused unchanged;
* the only replacement is the action localization - ``EvidenceChecksV3.
  action_match`` (``src/bpc_hybrid/s3_extended_v3_adapter.py``) instead of the
  label-similarity argmax of ``ExtendedViolationScorer._best_action``;
* the already stored Winter-style / Sun-style / BM25 / TF-IDF reference
  predictions are **reused read-only** (hash checked against the
  ``s3_formula_repair_v2`` manifest) and are never re-run or rewritten.

Predictions are written to disk before any label is read; the labels
(``expected_violation``) enter only the evaluators.  Zero API calls.

Metric views, reported separately and never merged:

* A - the 40 mutated variants: four-class P/R/F1, macro-F1, exact-type hits,
  wrong types, unobservable (a positive ``unknown`` counts as a miss);
* B - the 40 compliant controls: false positives, explicitly compliant answers,
  unobservable (a control ``unknown`` is NOT a correct rejection);
* C - the 40 pairs: both sides correct;
* D - the merged 80 objects: five classes including ``none``, labelled as such
  and never presented as A.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import run_s3_extended_violation_panel_v2 as panel_runner  # noqa: E402
from bpc_hybrid.s3_action_matching_v3 import EvidenceChecksV3  # noqa: E402
from bpc_hybrid.s3_extended_unified import unified_rows  # noqa: E402
from bpc_hybrid.s3_extended_v3_adapter import (  # noqa: E402
    ADAPTER_ID, ADAPTER_LOCALIZATION, DECISION_MAPPED, DECISION_NOT_SATISFIED,
    DECISION_UNDETERMINED, V3ExtendedScorer, classify_v3_decision,
)
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes  # noqa: E402
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES, NONE_LABEL, ConstraintSurface, condition_candidates,
    constraint_candidates, evaluate_extended, evaluate_paired, exception_candidates,
)
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402
from reevaluate_s3_extended_unified_v1 import confusion_matrix  # noqa: E402

RUN_ID = "s3_extended_v3_v1"
METHOD_ID = "v3_extended_action_structure"
METHOD_DISPLAY = "v3 four-type extension (structured action localization)"
ARM_SOURCE = "reference"
FROZEN_RUN_ID = "s3_formula_repair_v2"
FROZEN_EVIDENCE = ROOT / "outputs/evidence" / FROZEN_RUN_ID
FROZEN_REPORT = ROOT / "outputs/reports" / f"{FROZEN_RUN_ID}.json"
FROZEN_MANIFEST = FROZEN_EVIDENCE / "manifest.json"
FROZEN_METHODS = ("winter", "sun", "bm25", "tfidf_svd")
# the action localization of the v3 arm is v3; the recorded action gamma is the
# frozen sun-style value of the same panel (provenance only, not a gate)
GATE_METHOD = "sun"

OUT_DIR = ROOT / "outputs/development" / RUN_ID
PREDICTIONS_FILE = OUT_DIR / "predictions.jsonl"
METRICS_FILE = OUT_DIR / "metrics.json"
DIAGNOSTICS_FILE = OUT_DIR / "diagnostics.json"
MANIFEST_FILE = OUT_DIR / "manifest.json"
OUT_FILES = ("predictions.jsonl", "metrics.json", "diagnostics.json", "manifest.json")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                            for r in rows), encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def frozen_prediction_path(method: str) -> Path:
    return FROZEN_EVIDENCE / "extended_four" / ARM_SOURCE / method / "predictions.jsonl"


def frozen_paths() -> list[Path]:
    paths = [
        panel_runner.PANEL, panel_runner.EXTENSION_CONFIG, panel_runner.INFERENCE_PACK,
        panel_runner.STRUCTURAL_CONTRACT, panel_runner.SUN_CONFIG,
        panel_runner.WINTER_CONFIG, panel_runner.BM25_CONFIG, panel_runner.TFIDF_CONFIG,
        FROZEN_REPORT, FROZEN_MANIFEST,
        ROOT / "src/bpc_hybrid/stage3_extended_violations.py",
        ROOT / "src/bpc_hybrid/s3_extended_unified.py",
        ROOT / "src/bpc_hybrid/s3_action_matching_v3.py",
        ROOT / "src/bpc_hybrid/s3_action_matching_v2.py",
        ROOT / "src/bpc_hybrid/s3_evidence_checks_v1.py",
        ROOT / "src/bpc_hybrid/winter_stage3/winter_similarity.py",
        ROOT / "src/bpc_hybrid/sun_stage3/sun_model.py",
    ]
    paths += [frozen_prediction_path(method) for method in FROZEN_METHODS]
    paths += sorted((ROOT / "data/input/stage1_stage3/gdpr7").glob("*.bpmn"))
    for variant in read_json(panel_runner.PANEL)["variants"]:
        for side in ("control", "variant"):
            paths.append(ROOT / variant[f"{side}_bpmn"])
    return paths


def hash_map(paths: list[Path]) -> dict[str, str]:
    return {str(p.relative_to(ROOT)): sha256_file(p) for p in paths}


# ---------------------------------------------------------------------------
# one side of one instance: v3 localization -> four type checks
# ---------------------------------------------------------------------------


def score_side(sentence: dict, bpmn_path: Path, process_id: str, v3, sim_text: str,
               gamma_action: float, gamma_ext: float, nlp, contract) -> dict:
    source_path = str(bpmn_path.relative_to(ROOT))
    raw_bytes = bpmn_path.read_bytes()
    record = parse_bpmn_bytes(raw_bytes, source_path=source_path, contract=contract)
    model = SunProcessModel(process_id, record, nlp)
    xml_root = ET.fromstring(raw_bytes)
    scorer = V3ExtendedScorer(v3, sim_text, gamma_action, gamma_ext)

    localization = scorer.localize(sentence.get("action") or "", model)
    # ONE localized activity feeds both the score gate and the evidence surfaces
    mapped_id = localization["matched_activity_id"]
    condition_surface = condition_candidates(record, xml_root, mapped_id)
    constraint_surface = constraint_candidates(record, xml_root, mapped_id)
    exception_surface = exception_candidates(record, xml_root, mapped_id)

    results = {
        "prohibited_action_present": scorer.prohibited_action(sentence, model),
        "required_condition_not_enforced": scorer.required_condition(
            sentence, model, condition_surface),
        "constraint_violated": scorer.constraint_violated(
            sentence, model, constraint_surface),
        "exception_not_handled": scorer.exception_not_handled(
            sentence, model, exception_surface),
    }
    scores = {t: (results[t].get("score") if results[t].get("observable") else None)
              for t in EXTENDED_TYPES}
    observability = {t: {"observable": bool(results[t].get("observable", False)),
                         "reason": results[t].get("reason")}
                     for t in EXTENDED_TYPES}
    clean = {t: {"score": scores[t], "observable": observability[t]["observable"],
                 "reason": observability[t]["reason"],
                 "exact_contradiction": results[t].get("exact_contradiction")}
             for t in EXTENDED_TYPES}
    surfaces = {
        "required_condition_not_enforced": condition_surface,
        "constraint_violated": constraint_surface,
        "exception_not_handled": exception_surface,
    }
    evidence_binding = {}
    for t in EXTENDED_TYPES:
        surface = surfaces.get(t)
        evidence_binding[t] = {
            "matched_activity_id": results[t].get("matched_activity_id"),
            "surface_activity_id": (surface.activity_id
                                    if isinstance(surface, ConstraintSurface) else None),
            "candidate_count": len(surface) if surface is not None else None,
            "consumed_candidate": results[t].get("best_candidate"),
            "consumed_score": scores[t],
            "consumed_similarity": results[t].get("max_sim"),
            "same_activity_as_localization": (
                results[t].get("matched_activity_id") in (None, mapped_id)
                and (not isinstance(surface, ConstraintSurface)
                     or surface.activity_id in (None, mapped_id))),
        }
    return {
        "scores": scores,
        "scores_detail": {t: {k: v for k, v in results[t].items() if k != "score"}
                          for t in EXTENDED_TYPES},
        "observability": observability,
        "clean_scores": clean,
        "localization": localization,
        "evidence_binding": evidence_binding,
        "matched_activity_id": mapped_id,
    }


def build_row(variant: dict, sentence: dict, v3, sim_text: str, gamma_action: float,
              gamma_ext: float, nlp, contract) -> dict:
    pid = variant["process_id"]
    vid = variant["variant_id"]
    variant_side = score_side(sentence, ROOT / variant["variant_bpmn"], pid, v3, sim_text,
                              gamma_action, gamma_ext, nlp, contract)
    control_side = score_side(sentence, ROOT / variant["control_bpmn"], pid, v3, sim_text,
                              gamma_action, gamma_ext, nlp, contract)
    return {
        "schema_version": "stage3_extended_prediction@1.0.0",
        "method_id": METHOD_ID,
        "method_display_name": METHOD_DISPLAY,
        "run_id": f"{RUN_ID}_{METHOD_ID}",
        "task": "violation",
        "item_id": vid,
        "process_id": pid,
        "rule_id": variant["rule_id"],
        # kept for the frozen evaluators' self-check only; never an input of the
        # localization or of any type decision
        "expected_violation": variant["expected_violation"],
        "check_type": variant["expected_violation"],
        "predicted_violation_type": None,
        "scores": variant_side["scores"],
        "scores_detail": variant_side["scores_detail"],
        "observability": variant_side["observability"],
        "control_scores": control_side["clean_scores"],
        "action_localization": {
            "adapter": ADAPTER_ID,
            "localization": ADAPTER_LOCALIZATION,
            "variant": variant_side["localization"],
            "control": control_side["localization"],
        },
        "evidence_binding": {
            "variant": variant_side["evidence_binding"],
            "control": control_side["evidence_binding"],
        },
        "matched_activity": {
            "variant": variant_side["matched_activity_id"],
            "control": control_side["matched_activity_id"],
        },
        "thresholds": {
            "gamma_ext": gamma_ext,
            "action_mapping_gamma_recorded": gamma_action,
            "action_gate": "v3_localization_decision",
            "v3_method_id": getattr(v3, "method_id", None),
            "v3_thresholds": {"tau": v3.tau, "gamma": v3.gamma, "theta": v3.theta},
        },
        "threshold": gamma_ext,
        "action_mapping_gamma": gamma_action,
        "gamma_ext": gamma_ext,
        "panel": "synthetic_controlled_error_extension_v2",
        "gold_visible": False,
        "source_hashes": {
            "variant": vid,
            "source_bpmn_sha256": variant["source_bpmn_sha256"],
            "variant_bpmn_sha256": variant["variant_bpmn_sha256"],
            "control_bpmn_sha256": variant["control_bpmn_sha256"],
        },
        "method_provenance": (
            f"{METHOD_DISPLAY} gamma_ext={gamma_ext} action_localization=v3 "
            f"({ADAPTER_ID}); the four frozen extension formulas, the frozen "
            "gamma_ext decision rule and the frozen evaluators are unchanged "
            "(synthetic panel v2; development-only arm)"),
    }


# ---------------------------------------------------------------------------
# evaluation views (labels enter only here, after the predictions are on disk)
# ---------------------------------------------------------------------------


def variant_only_view(rows: list[dict], gold: dict, panel: dict, gamma_ext: float) -> dict:
    return evaluate_extended(rows, gold)


def control_view(paired: dict) -> dict:
    """Control-side view: an abstention is never counted as a rejection.

    The false positives are the CONTROL objects predicted as one of the four
    types (``per_type[t]["fp"]`` counts both sides, so it must not be used
    here); an explicitly compliant answer is a control object predicted
    ``none``; the rest are abstentions.
    """
    total = paired["control_objects"]
    false_positives = len(paired["cases"]["control_false_positive"])
    unobservable = paired["unobservable"]["control"]
    explicitly_compliant = total - false_positives - unobservable
    if not (0 <= explicitly_compliant <= total):
        raise RuntimeError("control identities do not add up to the control objects")
    if round(false_positives / total, 4) != paired["control_false_positive_rate"]:
        raise RuntimeError("control false-positive count and rate disagree")
    unobservable_by_reason = Counter()
    for case in paired["cases"]["control_unobservable"]:
        for reason in case["reasons"]:
            unobservable_by_reason[reason] += 1
    return {
        "objects": total,
        "false_positives": false_positives,
        "false_positive_rate": paired["control_false_positive_rate"],
        "explicitly_compliant": explicitly_compliant,
        "unobservable": unobservable,
        "unobservable_by_reason": dict(sorted(unobservable_by_reason.items())),
        "identity": "explicitly_compliant + false_positives + unobservable == objects",
        "policy": ("a control unknown is an abstention, not a correct rejection; an "
                   "explicitly compliant answer is `none`; false positives count only "
                   "control objects"),
    }


def paired_view(paired: dict) -> dict:
    return {
        "pairs": paired["variant_objects"],
        "both_sides_correct": round(paired["paired_accuracy"] * paired["variant_objects"]),
        "paired_accuracy": paired["paired_accuracy"],
        "variant_exact_type_accuracy": paired["variant_exact_type_accuracy"],
        "policy": paired["denominator_policy"],
    }


def merged_view(paired: dict) -> dict:
    labels = [NONE_LABEL] + list(EXTENDED_TYPES)
    return {
        "label": "D_merged_80_objects (40 variants + 40 controls)",
        "classes": labels,
        "denominator": paired["total_objects"],
        "five_class_accuracy": paired["five_class_accuracy"],
        "macro_f1_five_classes": paired["macro_f1_five_classes"],
        "macro_f1_four_violation_types": paired["macro_f1_four_violation_types"],
        "per_class": {label: paired["per_type"][label] for label in labels},
        "warning": ("this merged view is NOT the variant-only table A: it mixes 40 "
                    "violation objects with 40 compliant objects"),
    }


def frozen_reference_view(method: str, report: dict) -> dict:
    """Summary-only view of one frozen arm (no stored case lists are copied)."""
    block = report["extended_four_types"][ARM_SOURCE][method]
    ev, pa = block["variant_evaluation"], block["paired_evaluation"]
    return {
        "source": f"{FROZEN_REPORT.relative_to(ROOT).as_posix()} (read-only, not re-run)",
        "method": method,
        "A_variant_only_40": {k: ev[k] for k in
                              ("support", "per_type", "macro_f1", "micro_f1", "detected",
                               "missed", "wrong_type", "unobservable", "denominator")},
        "B_control_40": control_view(pa),
        "C_paired_40": paired_view(pa),
        "D_merged_80": merged_view(pa),
        "confusion_matrix": block.get("confusion_matrix"),
    }


def transition_view(old_rows: list[dict], new_rows: list[dict]) -> dict:
    """Sun-style -> v3 per-item transitions on the variant side."""
    old_by_id = {row["item_id"]: row for row in old_rows}
    new_by_id = {row["item_id"]: row for row in new_rows}

    def category(row: dict) -> str:
        raw = row.get("unified_predicted_raw")
        if raw is None:
            return "unknown"
        if raw == NONE_LABEL:
            return "compliant_observable"
        return raw

    buckets = {"unknown_to_correct": [], "unknown_to_wrong": [],
               "correct_to_wrong_or_unknown": [], "still_unknown": [],
               "unchanged_correct": [], "other": []}
    for row in sorted(new_rows, key=lambda r: r["item_id"]):
        vid = row["item_id"]
        old, expected = old_by_id[vid], row["expected_violation"]
        old_cat, new_cat = category(old), category(row)
        record = {
            "item_id": vid, "expected": expected, "process_id": row["process_id"],
            "rule_id": row["rule_id"],
            "old_predicted": old.get("unified_predicted_raw"),
            "new_predicted": row.get("unified_predicted_raw"),
            "old_expected_type_observable": old["observability"][expected]["observable"],
            "new_expected_type_observable": row["observability"][expected]["observable"],
            "old_expected_type_reason": old["observability"][expected]["reason"],
            "new_expected_type_reason": row["observability"][expected]["reason"],
            "old_scores": old.get("scores"), "new_scores": row.get("scores"),
            "v3_decision": row["action_localization"]["variant"]["decision"],
            "v3_match_tier": row["action_localization"]["variant"]["match_tier"],
            "v3_reason": row["action_localization"]["variant"]["reason"],
        }
        if old_cat == "unknown" and new_cat == expected:
            buckets["unknown_to_correct"].append(record)
        elif old_cat == "unknown" and new_cat not in ("unknown", expected):
            buckets["unknown_to_wrong"].append(record)
        elif old_cat == expected and new_cat not in (expected,):
            buckets["correct_to_wrong_or_unknown"].append(record)
        elif old_cat == "unknown" and new_cat == "unknown":
            buckets["still_unknown"].append(record)
        elif old_cat == expected and new_cat == expected:
            buckets["unchanged_correct"].append(record)
        else:
            buckets["other"].append(record)
    return {
        "old_arm": "sun (frozen s3_formula_repair_v2 reference predictions)",
        "new_arm": METHOD_ID,
        "counts": {key: len(value) for key, value in buckets.items()},
        "items": buckets,
    }


def per_type_view(rows: list[dict], old_rows: list[dict], old_view: dict,
                  new_view: dict) -> dict:
    """Per-type old/new metrics plus the unobservable reasons of this arm."""
    reasons = {t: Counter() for t in EXTENDED_TYPES}
    for row in rows:
        for t in EXTENDED_TYPES:
            if not row["observability"][t]["observable"]:
                reasons[t][row["observability"][t]["reason"] or "unspecified"] += 1
    by_id = {row["item_id"]: row for row in old_rows}
    out = {}
    for t in EXTENDED_TYPES:
        old_type, new_type = old_view["per_type"][t], new_view["per_type"][t]
        changed = sorted(
            row["item_id"] for row in rows
            if by_id[row["item_id"]]["unified_predicted_raw"] != row["unified_predicted_raw"])
        out[t] = {
            "support": new_type["support"],
            "old": {"precision": old_type["precision"], "recall": old_type["recall"],
                    "f1": old_type["f1"]},
            "new": {"precision": new_type["precision"], "recall": new_type["recall"],
                    "f1": new_type["f1"]},
            # gold-type basis: of the 10 variants whose expected type is t, how many
            # could not be judged (these are the A-table abstentions)
            "gold_type_unobservable_old": old_view["denominator"]["per_type_unobservable"][t],
            "gold_type_unobservable_new": new_view["denominator"]["per_type_unobservable"][t],
            # type basis: every instance of type t over the 40 rows, by reason
            "type_unobservable_by_reason_all_instances": dict(sorted(reasons[t].items())),
            "items_with_changed_prediction": changed,
            "denominator_note": ("gold_type_* counts the 10 gold-t variants; "
                                 "type_unobservable_by_reason_all_instances counts all 40 "
                                 "rows of this type"),
        }
    return out


# ---------------------------------------------------------------------------
# run / verify
# ---------------------------------------------------------------------------


def build_all() -> dict:
    import spacy
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    panel = read_json(panel_runner.PANEL)
    gamma_ext = float(panel["config"]["gamma_ext"])
    sun_config = read_json(panel_runner.SUN_CONFIG)
    tau = float(sun_config["method"]["thresholds"]["tau"])
    gamma = float(sun_config["method"]["thresholds"]["gamma"])
    theta = float(sun_config["method"]["thresholds"]["theta"])
    gamma_action = panel_runner._gamma_for(GATE_METHOD)
    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    v3 = EvidenceChecksV3(sim, tau, gamma, theta, nlp)
    contract = load_stage1_contract(panel_runner.STRUCTURAL_CONTRACT)
    rule_texts = panel_runner._rule_texts()

    rows: list[dict] = []
    for variant in panel["variants"]:
        sentence = panel_runner._locked_sentence(variant, rule_texts[variant["rule_id"]], nlp)
        rows.append(build_row(variant, sentence, v3, sim.text_pair, gamma_action,
                              gamma_ext, nlp, contract))
    # phase boundary: the unified decision (no label involved) is applied and the
    # predictions are on disk BEFORE any label is read
    rows = unified_rows(rows, gamma_ext)
    write_rows(PREDICTIONS_FILE, rows)

    gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}
    variant_view = variant_only_view(rows, gold, panel, gamma_ext)
    paired = evaluate_paired(rows, panel, gamma_ext)
    cm = confusion_matrix(rows, gold, gamma_ext, panel)
    old_sun = read_jsonl(frozen_prediction_path("sun"))
    transitions = transition_view(old_sun, rows)
    old_sun_view = variant_only_view(old_sun, gold, panel, gamma_ext)
    report = read_json(FROZEN_REPORT)

    metrics = {
        "schema_version": "s3_extended_v3_metrics@1.0.0",
        "run_id": RUN_ID,
        "generated_utc": started,
        "scope": "development_only",
        "arm": {
            "method_id": METHOD_ID, "method_display_name": METHOD_DISPLAY,
            "new_arm": True, "adapter": ADAPTER_ID,
            "action_localization": ADAPTER_LOCALIZATION,
            "source": ARM_SOURCE,
            "theta_tau_gamma": {"tau": tau, "gamma": gamma, "theta": theta},
            "action_mapping_gamma_recorded": gamma_action,
            "gamma_ext": gamma_ext,
            "action_gate": "v3_localization_decision",
        },
        "prediction_scope": ("40 panel variants; each row carries the mutated variant "
                             "side and its paired compliant control side = 80 "
                             "evaluation objects"),
        "A_variant_only_40": variant_view,
        "B_control_40": control_view(paired),
        "C_paired_40": paired_view(paired),
        "D_merged_80": merged_view(paired),
        "confusion_matrix": cm,
        "comparison_same_panel": {
            method: frozen_reference_view(method, report) for method in FROZEN_METHODS},
        "old_sun_recount_from_stored_predictions": {
            "A_variant_only_40": {k: old_sun_view[k] for k in
                                  ("macro_f1", "micro_f1", "detected", "missed",
                                   "wrong_type", "unobservable", "per_type")},
            "note": "recounted offline from the stored sun-style rows; must equal the "
                    "frozen report values (asserted by the run)",
        },
        "sun_to_v3": transitions,
        "per_type_change": per_type_view(rows, old_sun, old_sun_view, variant_view),
        "frozen_asset_reference": {
            "report": {"path": FROZEN_REPORT.relative_to(ROOT).as_posix(),
                       "sha256": sha256_file(FROZEN_REPORT)},
            "manifest": {"path": FROZEN_MANIFEST.relative_to(ROOT).as_posix(),
                         "sha256": sha256_file(FROZEN_MANIFEST)},
            "report_values_untouched": True,
        },
        "safety": {"api_calls": 0, "gold_read_for_evaluation_only": True,
                   "predictions_written_before_labels": True,
                   "thresholds_changed": False, "existing_predictions_rerun": False},
    }
    metrics["comparison_same_panel"][METHOD_ID] = {
        "source": "this run", "method": METHOD_ID,
        "A_variant_only_40": variant_view, "B_control_40": control_view(paired),
        "C_paired_40": paired_view(paired), "D_merged_80": merged_view(paired),
        "confusion_matrix": cm,
    }
    frozen_old = metrics["comparison_same_panel"]["sun"]["A_variant_only_40"]
    assert frozen_old["macro_f1"] == old_sun_view["macro_f1"], (
        "the stored sun-style rows no longer reproduce the frozen report; the old arm "
        "must not be re-bound silently")

    diagnostics = build_diagnostics(rows, panel, gamma_ext, gamma_action)
    write_json(METRICS_FILE, metrics)
    write_json(DIAGNOSTICS_FILE, diagnostics)
    return {"rows": rows, "metrics": metrics, "diagnostics": diagnostics,
            "panel": panel, "runtime_seconds": round(time.time() - t0, 3),
            "started_utc": started}


def build_diagnostics(rows: list[dict], panel: dict, gamma_ext: float,
                      gamma_action: float) -> dict:
    per_instance = []
    gate_only_by_v3 = 0
    v3_verdict_vs_frozen = Counter()
    for row in rows:
        loc = row["action_localization"]["variant"]
        detail = row["scores_detail"]
        gate_note = {
            t: {"reason": detail[t].get("reason"),
                "v3_decision": detail[t].get("v3_decision"),
                "v3_match_tier": detail[t].get("v3_match_tier"),
                "score_source": detail[t].get("score_source")}
            for t in EXTENDED_TYPES}
        if loc["decision"] == DECISION_MAPPED and loc["winner_similarity"] < gamma_action:
            gate_only_by_v3 += 1
        if loc["decision"] != DECISION_MAPPED:
            v3_verdict_vs_frozen[loc["decision"]] += 1
        per_instance.append({
            "item_id": row["item_id"], "process_id": row["process_id"],
            "rule_id": row["rule_id"], "expected_violation": row["expected_violation"],
            "method_id": row["method_id"], "run_id": row["run_id"],
            "thresholds": row["thresholds"],
            "action_localization": loc,
            "control_action_localization": row["action_localization"]["control"],
            "matched_activity": row["matched_activity"],
            "scores": row["scores"], "observability": row["observability"],
            "control_scores": row["control_scores"],
            "score_detail": {t: {k: v for k, v in detail[t].items()
                                 if k not in ("v3_tier_reason",)} for t in EXTENDED_TYPES},
            "evidence_binding": row["evidence_binding"],
            "gate_notes": gate_note,
            "final_prediction": row["unified_predicted_raw"],
            "final_prediction_kind": ("unknown" if row["unified_predicted_raw"] is None else
                                      "observable_compliant"
                                      if row["unified_predicted_raw"] == NONE_LABEL else
                                      "violation_type"),
        })
    unobservable = Counter()
    for row in rows:
        for t in EXTENDED_TYPES:
            if not row["observability"][t]["observable"]:
                unobservable[row["observability"][t]["reason"] or "unspecified"] += 1
    decisions = {row["action_localization"][side]["decision"] for row in rows
                 for side in ("variant", "control")}
    unexpected = sorted(decisions - {DECISION_MAPPED, DECISION_UNDETERMINED,
                                     DECISION_NOT_SATISFIED})
    if unexpected:
        raise RuntimeError(f"unexpected v3 localization decisions: {unexpected}")
    return {
        "schema_version": "s3_extended_v3_diagnostics@1.0.0",
        "run_id": RUN_ID,
        "instances": per_instance,
        "counts": {
            "instances": len(rows),
            "evaluation_objects": 2 * len(rows),
            "variant_unobservable_by_reason": dict(sorted(unobservable.items())),
            "v3_decision_counts": dict(sorted(Counter(
                row["action_localization"]["variant"]["decision"] for row in rows).items())),
            "v3_decision_counts_control": dict(sorted(Counter(
                row["action_localization"]["control"]["decision"] for row in rows).items())),
            "matched_with_similarity_below_recorded_gamma": gate_only_by_v3,
            "non_mapped_localizations": dict(sorted(v3_verdict_vs_frozen.items())),
        },
        "notes": [
            "the only replaced component is the action localization; the four frozen "
            "formulas, the frozen gamma_ext decision rule and the frozen evaluators are "
            "unchanged",
            "an undetermined or unsatisfied v3 localization keeps the type unobservable; "
            "v3 booleans are never written as 1.0/0.0 scores",
            "for prohibited_action_present the reported score is a real similarity: the "
            "v3-selected candidate when v3 matched, otherwise the best candidate "
            "similarity; the frozen decision rule then applies gamma_ext unchanged",
        ],
    }


def verify_outputs() -> dict:
    manifest = read_json(MANIFEST_FILE)
    mismatched = []
    for section in ("inputs", "implementation"):
        for rel, digest in manifest[section].items():
            if sha256_file(ROOT / rel) != digest:
                mismatched.append(f"{section}:{rel}")
    for key, entry in manifest["results"].items():
        if sha256_file(ROOT / entry["path"]) != entry["sha256"]:
            mismatched.append(f"results:{key}")
    if mismatched:
        raise RuntimeError("hash mismatch: " + ", ".join(sorted(set(mismatched))))
    if sorted(p.name for p in OUT_DIR.iterdir()) != sorted(OUT_FILES):
        raise RuntimeError("the run directory must hold exactly its four files")
    rows = read_jsonl(PREDICTIONS_FILE)
    if len(rows) != 40:
        raise RuntimeError("expected 40 panel rows (80 evaluation objects)")
    panel = read_json(panel_runner.PANEL)
    gamma_ext = float(panel["config"]["gamma_ext"])
    gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}
    metrics = read_json(METRICS_FILE)
    recomputed = variant_only_view(rows, gold, panel, gamma_ext)
    if recomputed != metrics["A_variant_only_40"]:
        raise RuntimeError("the variant-only view is not reproducible from the stored rows")
    paired = evaluate_paired(rows, panel, gamma_ext)
    if merged_view(paired) != metrics["D_merged_80"]:
        raise RuntimeError("the merged view is not reproducible from the stored rows")
    if metrics["arm"]["method_id"] != METHOD_ID:
        raise RuntimeError("the run must expose its own named method arm")
    for method, entry in manifest["reused_frozen_artifacts"].items():
        if entry["rerun"] is not False or entry["rewritten"] is not False:
            raise RuntimeError(f"the frozen {method} arm must stay read-only")
        if sha256_file(ROOT / entry["path"]) != entry["sha256"]:
            raise RuntimeError(f"frozen {method} predictions changed")
    return {"rows": rows, "metrics": metrics, "manifest": manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        verify_outputs()
        print("S3 EXTENDED V3 ARM VERIFIED")
        return 0
    if OUT_DIR.exists() and any(OUT_DIR.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing run directory: {OUT_DIR}")
    paths = frozen_paths()
    before = hash_map(paths)
    built = build_all()
    after = hash_map(paths)
    if before != after:
        raise RuntimeError("a frozen input or implementation file changed during the run")
    rows = built["rows"]
    manifest = {
        "schema_version": "s3_extended_v3_manifest@1.0.0",
        "run_id": RUN_ID,
        "method_id": METHOD_ID,
        "started_utc": built["started_utc"],
        "runtime_seconds": built["runtime_seconds"],
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                              text=True).strip(),
        "command": f"python {Path(__file__).relative_to(ROOT)}",
        "arm": built["metrics"]["arm"],
        "inputs": before,
        "implementation": {
            str(Path(__file__).relative_to(ROOT)): sha256_file(Path(__file__)),
            "src/bpc_hybrid/s3_extended_v3_adapter.py":
                sha256_file(ROOT / "src/bpc_hybrid/s3_extended_v3_adapter.py"),
            "tests/test_s3_extended_v3_v1.py":
                sha256_file(ROOT / "tests/test_s3_extended_v3_v1.py"),
        },
        "reused_frozen_artifacts": {
            method: {"path": frozen_prediction_path(method).relative_to(ROOT).as_posix(),
                     "sha256": sha256_file(frozen_prediction_path(method)),
                     "rerun": False, "rewritten": False}
            for method in FROZEN_METHODS},
        "results": {
            "predictions": {"path": PREDICTIONS_FILE.relative_to(ROOT).as_posix(),
                            "sha256": sha256_file(PREDICTIONS_FILE), "rows": len(rows),
                            "evaluation_objects": 2 * len(rows)},
            "metrics": {"path": METRICS_FILE.relative_to(ROOT).as_posix(),
                        "sha256": sha256_file(METRICS_FILE)},
            "diagnostics": {"path": DIAGNOSTICS_FILE.relative_to(ROOT).as_posix(),
                            "sha256": sha256_file(DIAGNOSTICS_FILE)},
        },
        "safety": {
            "api_calls": 0, "llm_api_calls": 0, "gold_modified": False,
            "thresholds_changed": False, "frozen_arms_rerun": False,
            "existing_results_rewritten": False, "panel_modified": False,
            "bpmn_modified": False, "v3_checker_modified": False,
            "sun_scorer_modified": False, "winter_modified": False,
        },
    }
    write_json(MANIFEST_FILE, manifest)
    verify_outputs()
    print(json.dumps({
        "run_id": RUN_ID, "method_id": METHOD_ID, "rows": len(rows),
        "evaluation_objects": 2 * len(rows),
        "variant_macro_f1": built["metrics"]["A_variant_only_40"]["macro_f1"],
        "control_false_positive_rate": built["metrics"]["B_control_40"]["false_positive_rate"],
        "paired_accuracy": built["metrics"]["C_paired_40"]["paired_accuracy"],
        "unobservable_variant": built["metrics"]["A_variant_only_40"]["unobservable"],
        "llm_api_calls": 0,
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
