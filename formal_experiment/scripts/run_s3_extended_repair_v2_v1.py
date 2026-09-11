# -*- coding: utf-8 -*-
"""S3.9-EXT limited repair run: three pre-specified arms on the frozen 80-instance panel.

The three arms answer the three causal questions of this batch and nothing else.
Their definitions are written to ``plan.json`` **before** any scoring, and each
arm records the parameters that were actually in force rather than the ones the
caller intended.

===========  =========================================================  ============  ===========  ==========
arm          matching path                                              v3 gamma      label gamma  gamma_ext
===========  =========================================================  ============  ===========  ==========
A            v3 structured match, **v3's own gamma really set to 0.4**   0.4           0.4          0.5
B            frozen original label argmax, v3 off, whitespace folded      -             0.4          0.5
C            v3 match + no forced resolution (successor repair)          0.8           0.4          0.5
===========  =========================================================  ============  ===========  ==========

Arm A fixes the execution error of ``run_s3_extended_v3_gamma04_v1.py``, which
built ``EvidenceChecksV3`` from the Sun config and therefore ran with gamma 0.8
while recording 0.4.  Arm C is deliberately a **two-level** configuration and is
reported as such.  Arm B isolates the whitespace factor with v3 switched off.

Offline only: zero API, zero LLM.  Predictions are written before any label is
read.  No threshold is searched, no path is chosen per sample, and every type is
computed for every instance before the unified decision runs.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import run_s3_extended_violation_panel_v2 as pr  # noqa: E402
from bpc_hybrid.s3_action_matching_v3 import EvidenceChecksV3  # noqa: E402
from bpc_hybrid.s3_extended_arm_report import arm_metrics  # noqa: E402
from bpc_hybrid.s3_extended_unified import unified_rows  # noqa: E402
from bpc_hybrid.s3_extended_v3_adapter import ADAPTER_ID, V3ExtendedScorer  # noqa: E402
from bpc_hybrid.s3_extended_v3_repair import REPAIR_ID  # noqa: E402
from bpc_hybrid.s3_extended_v3_repair_v2 import (  # noqa: E402
    NORMALIZER_ID, REPAIR_V2_ID, ArmAScorer, ConsistentRawScorer,
    RepairedExtendedScorerV2, aggregate_with_comparison_gate, fold_whitespace,
    repair_v2_policy,
)
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes  # noqa: E402
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES, NONE_LABEL, ConstraintSurface, ExtendedViolationScorer,
    condition_candidates, constraint_candidates, evaluate_extended, evaluate_paired,
    exception_candidates,
)
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

RUN_ID = "s3_extended_repair_v2_v1"
OUT_DIR = ROOT / "outputs/development" / RUN_ID
PLAN_FILE = OUT_DIR / "plan.json"
PREDICTIONS_FILE = OUT_DIR / "predictions.jsonl"
METRICS_FILE = OUT_DIR / "metrics.json"
DIAGNOSTICS_FILE = OUT_DIR / "diagnostics.json"
MANIFEST_FILE = OUT_DIR / "manifest.json"
OUT_FILES = ("plan.json", "predictions.jsonl", "metrics.json", "diagnostics.json",
             "manifest.json")

PANEL_GAMMA_EXT = 0.5

ARMS = {
    "A_v3_internal_0_4": {
        "label": "v3 structured match with v3's own gamma really set to 0.4",
        "matching_path": "v3_structured_action_match",
        "v3_internal_gamma": 0.4,
        "label_fallback_gamma": 0.4,
        "gamma_ext": PANEL_GAMMA_EXT,
        "scorer": "V3ExtendedScorer",
        "question": "how much do action localization, final predictions and control "
                    "false positives change when v3's own threshold really is 0.4?",
    },
    "B_original_path_normalized": {
        "label": "frozen original label argmax, v3 off, whitespace folded on both sides",
        "matching_path": "original_label_argmax",
        "v3_internal_gamma": None,
        "label_fallback_gamma": 0.4,
        "gamma_ext": PANEL_GAMMA_EXT,
        "scorer": "ConsistentRawScorer",
        "question": "does whitespace normalisation alone reproduce the two hits the "
                    "previous batch attributed to the new action resolution?",
    },
    "C_v3_no_forced_resolution": {
        "label": "v3 match + no forced resolution + comparison gate (two-level config)",
        "matching_path": "v3_structured_action_match_plus_successor_repair",
        "v3_internal_gamma": 0.8,
        "label_fallback_gamma": 0.4,
        "gamma_ext": PANEL_GAMMA_EXT,
        "scorer": "RepairedExtendedScorerV2",
        "question": "what does removing the forced resolution and the arbitrary "
                    "tie winner change, and does it cause regressions?",
    },
}

REFERENCE_CELLS = {
    "winter_frozen": {"path": "outputs/evidence/s3_formula_repair_v2/extended_four/"
                              "reference/winter/predictions.jsonl", "rerun": False},
    "sun_frozen": {"path": "outputs/evidence/s3_formula_repair_v2/extended_four/"
                            "reference/sun/predictions.jsonl", "rerun": False},
    "v3_08_existing": {"path": "outputs/development/s3_extended_v3_v1/predictions.jsonl",
                       "rerun": False},
    "v3_04_previous_repair": {
        "path": "outputs/development/s3_extended_v3_repair_v1/predictions.jsonl",
        "rerun": False},
    "v3_04_invalid_threshold_record": {
        "path": "outputs/development/s3_extended_v3_gamma04_v1/predictions.jsonl",
        "rerun": False,
        "status": "INVALID as a v3-gamma-0.4 experiment: the v3 instance was built with "
                  "gamma 0.8 from the Sun config; only the outer adapter gamma was 0.4"},
    "orig_04_rederived": {
        "path": "outputs/development/s3_extended_baseline_04_v1/predictions.jsonl",
        "rerun": False},
}

PREVIOUS_CLAIMS = {
    "withdrawn": [
        {"claim": "the action-mapping threshold is inert / explains zero failures in the "
                  "v3 path",
         "why": "the arm that was supposed to test it never changed v3's gamma: the "
                "EvidenceChecksV3 instance was constructed with gamma 0.8 from the Sun "
                "config while only the outer adapter received 0.4 (stored rows show "
                "action_mapping_gamma=0.4 next to v3_thresholds.gamma=0.8)",
         "replacement": "arm A of this batch sets v3's own gamma to 0.4 for real"},
        {"claim": "all 30 non-prohibited variant failures are caused by structural "
                  "rejection",
         "why": "26 of the 30 were the v3 similarity tier rejecting below its gamma, "
                "which was 0.8, not a structural verdict; at a real 0.4 the tier "
                "rejection count changes and must be recounted",
         "replacement": "arm A recounts the rejection reasons at a real 0.4"},
        {"claim": "control false positives squeezed two of the prohibited-action true "
                  "positives",
         "why": "false positives change precision, not recall: the prohibited type has "
                "TP 10 in every arm; the reported '17 vs 10' was same-type correct "
                "counts across all four types",
         "replacement": "per-type TP/FP/FN with precision and recall reported separately"},
        {"claim": "prediction is not None means a violation was detected",
         "why": "the unified five-class decision also emits the explicit compliance "
                "label 'none', which is a prediction but not a violation",
         "replacement": "four disjoint variant outcomes: correct type, wrong type, "
                        "explicit compliance, final unknown"},
        {"claim": "the repaired arm has no metric above the original path",
         "why": "contradicted by its own stored numbers (19 > 17 correct, 0.5233 > 0.4738 "
                "macro-F1); the correct statement is narrower - it does not beat the "
                "original path on any metric while keeping control false positives down",
         "replacement": "explicit per-metric comparison including control false positives"},
        {"claim": "the two extra hits are a contribution of the new action resolution / "
                  "structured matching",
         "why": "both extra hits came from the raw label fallback, and the compared "
                "label text differed only by a trailing newline "
                "(0.282807 -> 0.483290 and 0.266066 -> 0.466753, crossing 0.4)",
         "replacement": "arm B isolates the whitespace factor with v3 switched off"},
        {"claim": "target-type unobservability and the final unknown are the same count",
         "why": "a row can be unobservable for its gold type and still end as an explicit "
                "compliance or a wrong type, and the two are reported from different "
                "fields",
         "replacement": "target-type unobservability is counted separately from the four "
                        "disjoint variant outcomes"},
        {"claim": "the D1 scale defect is proved by 1.0000 vs 0.5040 crossing the 0.5 "
                  "threshold",
         "why": "both values are above 0.5, so that pair shows a scale difference but not "
                "a decision flip across the threshold",
         "replacement": "the discriminating pair is exception_not_handled_04: raw 0.5080 "
                        "at or above 0.5 versus lemmatised 0.5040 also at or above 0.5 "
                        "with the v3 arm not localizing at all; the decision flip is "
                        "carried by the fallback branch, not by the pair above"},
    ],
    "still_valid": [
        "arm B and the frozen Winter arm are the same matching path, so the whitespace "
        "factor can be read directly from their difference",
        "the frozen formulas, gamma_ext and the candidate surfaces are unchanged",
    ],
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                            for r in rows), encoding="utf-8", newline="\n")


def implementation_paths() -> list[Path]:
    return [
        Path(__file__),
        ROOT / "src/bpc_hybrid/s3_extended_v3_repair_v2.py",
        ROOT / "src/bpc_hybrid/s3_extended_v3_repair.py",
        ROOT / "src/bpc_hybrid/s3_extended_v3_adapter.py",
        ROOT / "src/bpc_hybrid/s3_action_matching_v3.py",
        ROOT / "src/bpc_hybrid/s3_action_matching_v2.py",
        ROOT / "src/bpc_hybrid/s3_evidence_checks_v1.py",
        ROOT / "src/bpc_hybrid/stage3_extended_violations.py",
        ROOT / "src/bpc_hybrid/s3_extended_unified.py",
        ROOT / "src/bpc_hybrid/s3_extended_arm_report.py",
        ROOT / "src/bpc_hybrid/winter_stage3/winter_similarity.py",
        ROOT / "src/bpc_hybrid/sun_stage3/sun_model.py",
    ]


def input_paths() -> list[Path]:
    paths = [pr.PANEL, pr.EXTENSION_CONFIG, pr.INFERENCE_PACK, pr.STRUCTURAL_CONTRACT,
             pr.WINTER_CONFIG, pr.SUN_CONFIG]
    paths += sorted((ROOT / "data/input/stage1_stage3/gdpr7").glob("*.bpmn"))
    for variant in read_json(pr.PANEL)["variants"]:
        for side in ("control", "variant"):
            paths.append(ROOT / variant[f"{side}_bpmn"])
    return paths


def build_plan() -> dict:
    """The pre-registered arm definitions; written before any scoring."""
    return {
        "schema_version": "s3_extended_repair_v2_plan@1.0.0",
        "run_id": RUN_ID,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": ("development_only synthetic four-type panel v2; 40 controlled variants "
                  "+ 40 synthetic compliant controls; NOT human Gold; NOT the formal "
                  "Oracle; zero API; zero LLM"),
        "panel": {"path": pr.PANEL.relative_to(ROOT).as_posix(),
                  "sha256": sha256_file(pr.PANEL),
                  "gamma_ext": PANEL_GAMMA_EXT},
        "arms": ARMS,
        "arm_count": 3,
        "runs_per_arm": 1,
        "reference_cells_read_only": REFERENCE_CELLS,
        "repair_policy": repair_v2_policy(),
        "previous_claims": PREVIOUS_CLAIMS,
        "pre_specified": [
            "no threshold is searched; 0.4 is Winter's frozen config value migrated "
            "unchanged and 0.8 is Sun's frozen config value",
            "no sample id, rule id, target activity id, mutation text or expected label "
            "enters any decision",
            "all four types are computed for every instance before the unified decision",
            "labels are read only after the predictions are on disk",
            "old predictions, metrics, manifests and their bound implementations are "
            "unchanged",
        ],
        "implementation": {str(p.relative_to(ROOT)): sha256_file(p)
                           for p in implementation_paths()},
        "inputs": {str(p.relative_to(ROOT)): sha256_file(p) for p in input_paths()},
    }


# --------------------------------------------------------------------------- arms


def build_scorer(arm: str, v3_04, v3_08, sim_text: str, contract):
    cfg = ARMS[arm]
    if arm == "A_v3_internal_0_4":
        return ArmAScorer(v3_04, sim_text, cfg["label_fallback_gamma"],
                          cfg["gamma_ext"]), "v3"
    if arm == "B_original_path_normalized":
        return ConsistentRawScorer(sim_text, sim_text, cfg["label_fallback_gamma"],
                                   cfg["gamma_ext"]), "raw"
    return RepairedExtendedScorerV2(v3_08, sim_text, cfg["label_fallback_gamma"],
                                    cfg["gamma_ext"]), "v3"


def score_side(arm: str, sentence: dict, bpmn_path: Path, process_id: str, v3_04, v3_08,
               sim_text: str, contract, nlp) -> dict:
    cfg = ARMS[arm]
    raw_bytes = bpmn_path.read_bytes()
    record = parse_bpmn_bytes(raw_bytes, source_path=str(bpmn_path.relative_to(ROOT)),
                              contract=contract)
    model = SunProcessModel(process_id, record, nlp)
    xml_root = ET.fromstring(raw_bytes)
    scorer, mode = build_scorer(arm, v3_04, v3_08, sim_text, contract)

    if mode == "v3":
        localization = scorer.localize(sentence.get("action") or "", model)
        mapped_id = localization["matched_activity_id"]
        resolution = localization
    else:
        evidence = scorer.folded_evidence(sentence.get("action") or "", model)
        mapped_id = evidence["winner_activity_id"]
        resolution = evidence

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
                 "comparison_performed": bool(results[t].get("comparison_performed")),
                 "abstention_kind": results[t].get("abstention_kind"),
                 "exact_contradiction": results[t].get("exact_contradiction")}
             for t in EXTENDED_TYPES}
    surfaces = {
        "required_condition_not_enforced": condition_surface,
        "constraint_violated": constraint_surface,
        "exception_not_handled": exception_surface,
    }
    binding = {}
    for t in EXTENDED_TYPES:
        surface = surfaces.get(t)
        observable = bool(results[t].get("observable", False))
        matched_id = results[t].get("matched_activity_id")
        if not observable:
            # the check produced no evidence, so there is nothing to attribute
            alignment = None
        elif t == "prohibited_action_present":
            # the presence check never needed one activity; it reports the activity
            # whose label it scored, which may differ from the action's own activity
            alignment = None
        else:
            alignment = (matched_id == mapped_id)
        binding[t] = {
            "matched_activity_id": matched_id,
            "surface_activity_id": (surface.activity_id
                                    if isinstance(surface, ConstraintSurface) else None),
            "candidate_count": len(surface) if surface is not None else None,
            "consumed_candidate": results[t].get("best_candidate"),
            # an unobservable check published no evidence, so it must not report a
            # consumed score either
            "consumed_score": scores[t] if observable else None,
            "consumed_similarity": (results[t].get("max_sim") if observable else None),
            "action_max_sim": (results[t].get("action_max_sim") if observable else None),
            "action_best_candidate": (results[t].get("action_best_candidate")
                                      if observable else None),
            "resolution_required": t != "prohibited_action_present",
            "same_activity_as_resolution": alignment,
            "localization_was_resolved": mapped_id is not None,
        }
    return {
        "scores": scores,
        "scores_detail": {t: {k: v for k, v in results[t].items() if k != "score"}
                          for t in EXTENDED_TYPES},
        "observability": observability,
        "clean_scores": clean,
        "action_resolution": resolution,
        "evidence_binding": binding,
        "matched_activity_id": mapped_id,
        "comparison_strings": (
            {t: {"rule_value": (sentence.get(t if t != "prohibited_action_present"
                                             else "action") or ""),
                 "consumed_candidate": results[t].get("best_candidate")}
             for t in EXTENDED_TYPES}),
    }


def build_rows(arm: str, panel: dict, rule_texts: dict, v3_04, v3_08, sim_text, contract,
               nlp) -> list[dict]:
    cfg = ARMS[arm]
    rows = []
    for variant in panel["variants"]:
        sentence = pr._locked_sentence(variant, rule_texts[variant["rule_id"]], nlp)
        pid = variant["process_id"]
        variant_side = score_side(arm, sentence, ROOT / variant["variant_bpmn"], pid,
                                  v3_04, v3_08, sim_text, contract, nlp)
        control_side = score_side(arm, sentence, ROOT / variant["control_bpmn"], pid,
                                  v3_04, v3_08, sim_text, contract, nlp)
        rows.append({
            "schema_version": "stage3_extended_prediction@1.0.0",
            "method_id": arm,
            "method_display_name": cfg["label"],
            "run_id": f"{RUN_ID}_{arm}",
            "task": "violation",
            "item_id": variant["variant_id"],
            "process_id": pid,
            "rule_id": variant["rule_id"],
            "expected_violation": variant["expected_violation"],
            "check_type": variant["expected_violation"],
            "predicted_violation_type": None,
            "scores": variant_side["scores"],
            "scores_detail": variant_side["scores_detail"],
            "observability": variant_side["observability"],
            "control_scores": control_side["clean_scores"],
            "action_localization": {"variant": variant_side["action_resolution"],
                                    "control": control_side["action_resolution"]},
            "comparison_strings": {"variant": variant_side["comparison_strings"],
                                   "control": control_side["comparison_strings"]},
            "evidence_binding": {"variant": variant_side["evidence_binding"],
                                 "control": control_side["evidence_binding"]},
            "matched_activity": {"variant": variant_side["matched_activity_id"],
                                 "control": control_side["matched_activity_id"]},
            "thresholds": {
                "gamma_ext": cfg["gamma_ext"],
                "v3_internal_gamma": cfg["v3_internal_gamma"],
                "v3_internal_tau": (v3_04.tau if cfg["v3_internal_gamma"] == 0.4
                                    else v3_08.tau) if cfg["v3_internal_gamma"] else None,
                "v3_internal_theta": (v3_04.theta if cfg["v3_internal_gamma"] == 0.4
                                      else v3_08.theta) if cfg["v3_internal_gamma"] else None,
                "label_fallback_gamma": cfg["label_fallback_gamma"],
                "matching_path": cfg["matching_path"],
                "scorer": cfg["scorer"],
                "configuration_levels": ("single_level" if cfg["v3_internal_gamma"]
                                         == cfg["label_fallback_gamma"]
                                         else "two_level"),
                "proxy_measure": ("score >= gamma_ext for the prohibition presence check; "
                                  "score > gamma_ext for the other three"),
            },
            "threshold": cfg["gamma_ext"],
            "gamma_ext": cfg["gamma_ext"],
            "panel": "synthetic_controlled_error_extension_v2",
            "gold_visible": False,
            "source_hashes": {
                "source_bpmn_sha256": variant["source_bpmn_sha256"],
                "variant_bpmn_sha256": variant["variant_bpmn_sha256"],
                "control_bpmn_sha256": variant["control_bpmn_sha256"],
            },
            "method_provenance": (
                f"{cfg['label']}; frozen panel/extractor/surfaces/formulas/gamma_ext and "
                f"the unified five-class decision are inherited (zero API)"),
        })
    return rows


def assert_thresholds_in_force(v3_04, v3_08) -> dict:
    """Fail before any scoring when a recorded gamma is not the one in force."""
    checks = {
        "A_v3_internal_0_4": {
            "declared_v3_gamma": ARMS["A_v3_internal_0_4"]["v3_internal_gamma"],
            "instance_v3_gamma": v3_04.gamma,
            "instance_tau": v3_04.tau,
            "instance_theta": v3_04.theta,
        },
        "C_v3_no_forced_resolution": {
            "declared_v3_gamma": ARMS["C_v3_no_forced_resolution"]["v3_internal_gamma"],
            "instance_v3_gamma": v3_08.gamma,
            "instance_tau": v3_08.tau,
            "instance_theta": v3_08.theta,
        },
    }
    for arm, entry in checks.items():
        if abs(entry["declared_v3_gamma"] - entry["instance_v3_gamma"]) > 1e-12:
            raise RuntimeError(
                f"{arm}: declared v3 gamma {entry['declared_v3_gamma']} but the "
                f"EvidenceChecksV3 instance carries {entry['instance_v3_gamma']}; "
                "refusing to score (this is exactly the defect of the previous batch)")
        if abs(entry["instance_tau"] - 0.8) > 1e-12 or abs(entry["instance_theta"] - 0.8) > 1e-12:
            raise RuntimeError(f"{arm}: tau/theta must stay at Sun's frozen 0.8")
    return checks


# ------------------------------------------------------------------- evaluations


def variant_partition(rows: list[dict], gold: dict) -> dict:
    """Four disjoint variant outcomes; target-type unobservability counted separately."""
    buckets = {"correct_type": [], "wrong_type": [], "explicit_compliance": [],
               "final_unknown": []}
    unobservable_gold_type = []
    for row in rows:
        item = row["item_id"]
        expected = gold[item]["expected_violation"]
        pred = row.get("unified_predicted_raw")
        if pred == expected:
            buckets["correct_type"].append(item)
        elif pred == NONE_LABEL:
            buckets["explicit_compliance"].append(item)
        elif pred is None:
            buckets["final_unknown"].append(item)
        else:
            buckets["wrong_type"].append(item)
        if row["observability"][expected]["observable"] is False:
            unobservable_gold_type.append(item)
    total = sum(len(v) for v in buckets.values())
    if total != len(rows):
        raise RuntimeError(f"variant partition does not cover the rows: {total}")
    return {
        "objects": len(rows),
        **{k: len(v) for k, v in buckets.items()},
        "identity": ("correct_type + wrong_type + explicit_compliance + final_unknown "
                     "== objects"),
        "items": buckets,
        "target_type_unobservable": len(unobservable_gold_type),
        "target_type_unobservable_items": unobservable_gold_type,
        "target_type_unobservable_is_separate": True,
        "note": ("'final_unknown' is the unified decision abstaining; "
                 "'target_type_unobservable' is a property of the gold type's check and "
                 "is NOT part of the four-way partition"),
    }


def control_partition(rows: list[dict]) -> dict:
    """Three disjoint control outcomes from the per-type control decisions.

    The aggregate answer ``none`` (explicit compliance) requires that at least one
    check actually compared the rule element against process evidence; a control
    whose every check abstained stays an abstention, never a correct rejection.
    The number of abstentions that the FRAGILE rule (``none`` whenever some type
    is observed) would have called explicitly compliant is reported separately.
    """
    fp_items, compliant_items, unknown_items = [], [], []
    fragile_rule_compliance = []
    for row in rows:
        per_type = {}
        evidence_comparisons = 0
        for t in EXTENDED_TYPES:
            cs = row["control_scores"][t]
            if t != "prohibited_action_present" and cs.get("comparison_performed"):
                evidence_comparisons += 1
            if not cs.get("observable"):
                per_type[t] = None
                continue
            score = cs.get("score")
            if t == "prohibited_action_present":
                per_type[t] = score is not None and score >= PANEL_GAMMA_EXT
            elif t == "constraint_violated":
                contradiction = bool((cs.get("exact_contradiction") or {})
                                     .get("contradiction"))
                per_type[t] = (score is not None and score > PANEL_GAMMA_EXT) or contradiction
            else:
                per_type[t] = score is not None and score > PANEL_GAMMA_EXT
        violated = [t for t in EXTENDED_TYPES if per_type.get(t) is True]
        any_observable = any(v is not None for v in per_type.values())
        if violated:
            fp_items.append({"item_id": row["item_id"], "predicted_type": violated[0]})
        elif any_observable and evidence_comparisons > 0:
            compliant_items.append(row["item_id"])
        else:
            unknown_items.append(row["item_id"])
            if any_observable:
                fragile_rule_compliance.append(row["item_id"])
    total = len(fp_items) + len(compliant_items) + len(unknown_items)
    if total != len(rows):
        raise RuntimeError(f"control partition does not cover the rows: {total}")
    return {
        "objects": len(rows),
        "false_positives": len(fp_items),
        "explicit_compliance": len(compliant_items),
        "final_unknown": len(unknown_items),
        "identity": "false_positives + explicit_compliance + final_unknown == objects",
        "false_positive_items": fp_items,
        "abstentions_the_fragile_rule_would_have_called_compliant":
            len(fragile_rule_compliance),
        "fragile_rule_items": fragile_rule_compliance,
        "note": ("a control false positive changes precision only; it never removes a "
                 "variant-side true positive.  'explicit compliance' means at least one "
                 "condition / constraint / exception check compared the rule element "
                 "against process evidence and none of the checks violated; a control "
                 "abstention is never a correct rejection"),
    }


def build_metrics(rows: list[dict], panel: dict, gold: dict, gamma_ext: float) -> dict:
    paired = evaluate_paired(rows, panel, gamma_ext)
    evaluation = evaluate_extended(rows, gold)
    labels = [NONE_LABEL] + list(EXTENDED_TYPES)
    return {
        "schema_version": "s3_extended_repair_v2_metrics@1.0.0",
        "A_variant_40": {
            "partition": variant_partition(rows, gold),
            "per_type": evaluation["per_type"],
            "macro_f1_four_types": evaluation["macro_f1"],
            "micro_f1": evaluation["micro_f1"],
        },
        "B_control_40": control_partition(rows),
        "C_paired_40": {
            "pairs": paired["variant_objects"],
            "both_sides_correct": round(paired["paired_accuracy"] * paired["variant_objects"]),
            "paired_accuracy": paired["paired_accuracy"],
        },
        "D_merged_80": {
            "label": "merged_80_objects (40 variants + 40 controls)",
            "denominator": paired["total_objects"],
            "five_class_accuracy": paired["five_class_accuracy"],
            "macro_f1_four_violation_types": paired["macro_f1_four_violation_types"],
            "macro_f1_five_classes": paired["macro_f1_five_classes"],
            "per_class": {label: paired["per_type"][label] for label in labels},
            "warning": "the merged view is NOT the A table: it mixes 40 violation objects "
                       "with 40 compliant objects",
        },
    }


def build_diagnostics(rows_by_arm: dict[str, list[dict]], plan: dict,
                      gold: dict, whitespace: dict) -> dict:
    """Parameter checks, per-arm difference lists against the read-only cells, corrections."""
    per_instance = {}
    for arm, rows in rows_by_arm.items():
        entries = []
        for row in rows:
            entries.append({
                "item_id": row["item_id"],
                "expected_violation": row["expected_violation"],
                "rule_id": row["rule_id"],
                "thresholds": row["thresholds"],
                "scores": row["scores"],
                "observability": row["observability"],
                "control_scores": row["control_scores"],
                "resolution": row["action_localization"]["variant"],
                "comparison_strings": row["comparison_strings"]["variant"],
                "evidence_binding": row["evidence_binding"]["variant"],
                "final_prediction": row.get("unified_predicted_raw"),
            })
        per_instance[arm] = entries

    reference = {}
    for name, entry in REFERENCE_CELLS.items():
        reference[name] = {r["item_id"]: r for r in read_jsonl(ROOT / entry["path"])}

    def decision(row):
        """The decision-relevant view, comparable across cells that store
        different amounts of provenance.

        ``resolution_detail`` is reported separately: the frozen reference cells
        do not store every resolution field, so a difference there is not a
        decision difference and must not be counted as one.
        """
        loc = (row.get("action_localization") or {}).get("variant") or {}
        return {
            "scores": row["scores"],
            "observability": {t: row["observability"][t]["observable"]
                              for t in EXTENDED_TYPES},
            "control": {t: {"score": row["control_scores"][t]["score"],
                            "observable": row["control_scores"][t]["observable"]}
                        for t in EXTENDED_TYPES},
            "prediction": row.get("unified_predicted_raw"),
        }

    def resolution_detail(row):
        """One shape for both stored reference formats.

        The frozen v3 cells store the adapter's localization record (``decision``,
        ``match_tier``, ``winner_*``); the repair arms store the resolution record
        (``v3_decision``, ``v3_match_tier``, ``raw_winner_*``).
        """
        loc = (row.get("action_localization") or {}).get("variant") or {}
        return {
            "decision": loc.get("decision", loc.get("v3_decision")),
            "tier": loc.get("match_tier", loc.get("v3_match_tier")),
            "resolved_by": loc.get("resolved_by"),
            "resolved_activity_id": loc.get("resolved_activity_id"),
            "winner_activity_id": loc.get("raw_winner_activity_id",
                                          loc.get("winner_activity_id")),
            "matched_activity_id": loc.get("matched_activity_id"),
        }

    detail_keys = ("decision", "tier", "resolved_by", "resolved_activity_id",
                   "winner_activity_id", "matched_activity_id")

    def diff_against(name: str, arm: str) -> dict:
        ref = reference[name]
        items = []
        identical = 0
        for row in rows_by_arm[arm]:
            other = ref.get(row["item_id"])
            if other is None:
                raise RuntimeError(f"{name}: missing reference row {row['item_id']}")
            left, right = decision(row), decision(other)
            if left == right:
                identical += 1
                continue
            changed = [k for k in left if left[k] != right[k]]
            items.append({
                "item_id": row["item_id"],
                "expected_violation": row["expected_violation"],
                "changed_decision_fields": changed,
                "arm": {k: left[k] for k in changed},
                "reference": {k: right[k] for k in changed},
                "arm_full": left,
                "reference_full": right,
                "reference_cell": name,
            })
        detail_only = []
        for row in rows_by_arm[arm]:
            other = ref[row["item_id"]]
            left, right = resolution_detail(row), resolution_detail(other)
            keys = [k for k in detail_keys
                    if left.get(k) != right.get(k) and right.get(k) is not None]
            if keys:
                detail_only.append({"item_id": row["item_id"], "changed": keys})
        return {"reference_cell": name, "decision_identical": identical,
                "decision_changed": len(items), "items": items,
                "resolution_detail_only_differences": detail_only,
                "detail_note": ("the frozen reference cells store fewer resolution "
                                "fields; a None on the reference side is not a "
                                "difference")}

    return {
        "schema_version": "s3_extended_repair_v2_diagnostics@1.0.0",
        "run_id": RUN_ID,
        "thresholds_in_force": plan.get("thresholds_in_force"),
        "arms": ARMS,
        "per_instance": per_instance,
        "differences_vs_reference_cells": {
            "A_vs_invalid_0_4_record": diff_against("v3_04_invalid_threshold_record",
                                                    "A_v3_internal_0_4"),
            "A_vs_v3_08": diff_against("v3_08_existing", "A_v3_internal_0_4"),
            "B_vs_winter_frozen": diff_against("winter_frozen",
                                               "B_original_path_normalized"),
            "C_vs_previous_repair": diff_against("v3_04_previous_repair",
                                                 "C_v3_no_forced_resolution"),
            "C_vs_winter_frozen": diff_against("winter_frozen",
                                               "C_v3_no_forced_resolution"),
        },
        "previous_claims": plan["previous_claims"],
        "whitespace_factor_evidence": whitespace,
        "argument_independence": {
            "separated": {
                "v3_internal_threshold": ("arm A changes only the gamma the "
                                          "EvidenceChecksV3 instance is built with "
                                          "(0.8 -> 0.4); tau, theta, backend, inputs and "
                                          "formulas are identical to the existing v3 arm"),
                "whitespace_normalisation_with_v3_off": (
                    "arm B is the frozen original path with one fold applied to both "
                    "sides of every comparison; no v3 component is used"),
            },
            "coupled": {
                "arm_C_vs_previous_repair": (
                    "arm C changes two things at once against the previous repair: the "
                    "whitespace is applied consistently instead of one-sided, and the "
                    "forced resolution / arbitrary tie winner is removed. The recorded "
                    "per-item differences name which of the two acted on each item, but "
                    "an item whose score changed AND whose resolution changed cannot be "
                    "attributed to one of them from this design alone"),
                "arm_A_vs_winter": (
                    "arm A differs from the frozen Winter-style arm in both the matching "
                    "path and the rejected-candidate handling, so it is not a "
                    "single-factor comparison against Winter"),
            },
            "not_claimed": [
                "no arm isolates v3's structured matching from v3's threshold",
                "no arm isolates the label fold from the threshold inside the v3 path",
            ],
        },
    }


whitespace_evidence: dict = {}


# --------------------------------------------------------------------------- main


def write_metrics(rows_by_arm: dict[str, list[dict]], panel: dict, gold: dict,
                  gamma_ext: float, started: str) -> dict:
    metrics = {arm: build_metrics(rows, panel, gold, gamma_ext)
               for arm, rows in rows_by_arm.items()}
    write_json(METRICS_FILE, {
        "schema_version": "s3_extended_repair_v2_metrics@1.0.0",
        "run_id": RUN_ID, "generated_utc": started, "scope": "development_only",
        "arms": {arm: {**metrics[arm], "label": ARMS[arm]["label"],
                       "thresholds": ARMS[arm]} for arm in ARMS},
    })
    return metrics


def rebuild_reports_from_stored_rows(whitespace: dict) -> dict:
    """Recompute metrics.json and diagnostics.json from the stored predictions.

    Used when only the reporting layer changed: no arm is re-run, and the
    predictions are never rewritten.  The stored conditions are restored exactly
    as they were (same panel, same per-arm mapping, same gamma_ext).
    """
    global whitespace_evidence
    whitespace_evidence = whitespace
    rows = read_jsonl(PREDICTIONS_FILE)
    rows_by_arm: dict[str, list[dict]] = {arm: [] for arm in ARMS}
    for row in rows:
        rows_by_arm[row["arm"]].append(row)
    if any(len(v) != 40 for v in rows_by_arm.values()):
        raise RuntimeError("stored predictions do not hold 40 rows per arm")
    panel = read_json(pr.PANEL)
    gamma_ext = float(panel["config"]["gamma_ext"])
    if abs(gamma_ext - PANEL_GAMMA_EXT) > 1e-12:
        raise RuntimeError("the frozen gamma_ext changed")
    gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}
    plan = read_json(PLAN_FILE)
    metrics = write_metrics(rows_by_arm, panel, gold, gamma_ext,
                            plan.get("created_utc", ""))
    write_json(DIAGNOSTICS_FILE, build_diagnostics(rows_by_arm, plan, gold, whitespace))
    return {"rows": rows_by_arm, "metrics": metrics, "plan": plan}


def apply_decision(arm: str, rows: list[dict], gamma_ext: float) -> list[dict]:
    """The unified five-class decision of one arm.

    Arms A and B use the frozen decision unchanged.  Arm C carries the one
    successor repair that touches the aggregate answer: ``none`` (explicit
    compliance) requires at least one performed comparison.
    """
    if arm != "C_v3_no_forced_resolution":
        return unified_rows(rows, gamma_ext)
    out = unified_rows(rows, gamma_ext)
    for row in out:
        side = {}
        for t in EXTENDED_TYPES:
            obs = row["observability"][t]
            detail = row["scores_detail"][t]
            side[t] = {
                "score": row["scores"][t],
                "observable": bool(obs.get("observable", False)),
                "reason": obs.get("reason"),
                "exact_contradiction": detail.get("exact_contradiction"),
                "comparison_performed": bool(detail.get("comparison_performed")),
            }
        decision = aggregate_with_comparison_gate(side, gamma_ext)
        raw = decision["predicted"]
        row["comparison_gate"] = {
            "evidence_comparisons_performed": decision["evidence_comparisons_performed"],
            "prohibition_comparison_performed":
                decision["prohibition_comparison_performed"],
            "any_type_observable": bool(
                any(v is not None for v in decision["per_type"].values())),
        }
        row["unified_predicted_raw"] = raw
        row["predicted_violation_type"] = (None if raw is None or raw == NONE_LABEL
                                           else raw)
        row["prediction_observable_compliant"] = bool(raw == NONE_LABEL)
        row["prediction_all_unobservable"] = bool(decision["all_unobservable"])
        row["prediction_rule"] = "unified_five_class_decision_v1+comparison_gate"
    return out


def build_all() -> dict:
    import spacy
    global whitespace_evidence
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    panel = read_json(pr.PANEL)
    gamma_ext = float(panel["config"]["gamma_ext"])
    sun = read_json(pr.SUN_CONFIG)["method"]["thresholds"]
    tau, theta = float(sun["tau"]), float(sun["theta"])
    winter_gamma = float(read_json(pr.WINTER_CONFIG)["method"]["gamma"])
    if abs(winter_gamma - 0.4) > 1e-12:
        raise RuntimeError("Winter's frozen gamma is no longer 0.4")

    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    v3_04 = EvidenceChecksV3(sim, tau, ARMS["A_v3_internal_0_4"]["v3_internal_gamma"],
                             theta, nlp)
    v3_08 = EvidenceChecksV3(sim, tau, ARMS["C_v3_no_forced_resolution"]["v3_internal_gamma"],
                             theta, nlp)
    thresholds = assert_thresholds_in_force(v3_04, v3_08)

    contract = load_stage1_contract(pr.STRUCTURAL_CONTRACT)
    rule_texts = pr._rule_texts()
    gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}

    whitespace = measure_whitespace(panel, rule_texts, sim, contract, nlp)
    whitespace_evidence = whitespace
    plan = build_plan()
    plan["thresholds_in_force"] = thresholds
    write_json(PLAN_FILE, plan)

    rows_by_arm = {}
    for arm in ARMS:
        rows = apply_decision(arm, build_rows(arm, panel, rule_texts, v3_04, v3_08,
                                              sim.text_pair, contract, nlp), gamma_ext)
        for row in rows:
            row["arm"] = arm
        rows_by_arm[arm] = rows
    # phase boundary: every arm's prediction is on disk before any label is read
    write_rows(PREDICTIONS_FILE, [r for arm in ARMS for r in rows_by_arm[arm]])
    metrics = write_metrics(rows_by_arm, panel, gold, gamma_ext, started)
    write_json(DIAGNOSTICS_FILE, build_diagnostics(rows_by_arm, plan, gold, whitespace))
    return {"rows": rows_by_arm, "metrics": metrics, "plan": plan,
            "runtime_seconds": round(time.time() - t0, 3), "started_utc": started,
            "thresholds": thresholds, "whitespace": whitespace}


def measure_whitespace(panel: dict, rule_texts: dict, sim, contract, nlp) -> dict:
    """The compared strings and scores with and without the whitespace fold."""
    out = {}
    for variant in panel["variants"]:
        sentence = pr._locked_sentence(variant, rule_texts[variant["rule_id"]], nlp)
        action = sentence.get("action") or ""
        folded_action = fold_whitespace(action)
        raw_bytes = (ROOT / variant["variant_bpmn"]).read_bytes()
        record = parse_bpmn_bytes(raw_bytes, source_path=variant["variant_bpmn"],
                                  contract=contract)
        model = SunProcessModel(variant["process_id"], record, nlp)
        rows = []
        for act in model.actions:
            name = act.get("name") or ""
            if not name.strip():
                continue
            folded = fold_whitespace(name)
            rows.append({
                "activity_id": act["id"], "label": name, "label_folded": folded,
                "score_raw_label": float(sim.text_pair(folded_action, name)),
                "score_folded_label": float(sim.text_pair(folded_action, folded)),
                "label_changed_by_fold": name != folded,
                "fold_removes_only_whitespace": name.split() == folded.split(),
            })
        rows.sort(key=lambda r: (-r["score_folded_label"], r["activity_id"]))
        best_raw = max(r["score_raw_label"] for r in rows) if rows else 0.0
        best_folded = max(r["score_folded_label"] for r in rows) if rows else 0.0
        out[variant["variant_id"]] = {
            "rule_action": action,
            "rule_action_folded": folded_action,
            "rule_action_changed_by_fold": action != folded_action,
            "best_score_raw_label": round(best_raw, 6),
            "best_score_folded_label": round(best_folded, 6),
            "crosses_label_gamma_raw": best_raw >= 0.4,
            "crosses_label_gamma_folded": best_folded >= 0.4,
            "candidates": rows[:5],
        }
    return out


def verify_outputs() -> dict:
    plan = read_json(PLAN_FILE)
    mismatched = [f"inputs:{rel}" for rel, digest in plan["inputs"].items()
                  if sha256_file(ROOT / rel) != digest]
    mismatched += [f"implementation:{rel}" for rel, digest in plan["implementation"].items()
                   if sha256_file(ROOT / rel) != digest]
    if mismatched:
        raise RuntimeError("hash mismatch: " + ", ".join(sorted(mismatched)))
    if sorted(p.name for p in OUT_DIR.iterdir()) != sorted(OUT_FILES):
        raise RuntimeError("the run directory must hold exactly its five files")
    rows = read_jsonl(PREDICTIONS_FILE)
    if len(rows) != 3 * 40:
        raise RuntimeError(f"expected 3 arms x 40 rows, got {len(rows)}")
    for arm in ARMS:
        arm_rows = [r for r in rows if r["arm"] == arm]
        if len(arm_rows) != 40:
            raise RuntimeError(f"{arm}: expected 40 rows")
        declared = ARMS[arm]
        for row in arm_rows:
            if abs(row["thresholds"]["gamma_ext"] - declared["gamma_ext"]) > 1e-12:
                raise RuntimeError(f"{arm}:{row['item_id']}: gamma_ext mismatch")
            if row["thresholds"]["v3_internal_gamma"] != declared["v3_internal_gamma"]:
                raise RuntimeError(f"{arm}:{row['item_id']}: v3 gamma mismatch")
            if row["thresholds"]["label_fallback_gamma"] != declared["label_fallback_gamma"]:
                raise RuntimeError(f"{arm}:{row['item_id']}: fallback gamma mismatch")
            for side in ("variant", "control"):
                binding = row["evidence_binding"][side]
                for t, entry in binding.items():
                    if entry["consumed_score"] is not None:
                        continue
                    if entry["consumed_candidate"] is not None:
                        raise RuntimeError(
                            f"{arm}:{row['item_id']}:{side}:{t}: a candidate is recorded "
                            "for a check that published no score")
    return {"rows": rows, "plan": plan, "metrics": read_json(METRICS_FILE)}


def write_manifest(built: dict) -> None:
    manifest = {
        "schema_version": "s3_extended_repair_v2_manifest@1.0.0",
        "run_id": RUN_ID,
        "started_utc": built["started_utc"],
        "runtime_seconds": built["runtime_seconds"],
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                              text=True).strip(),
        "command": f"python {Path(__file__).relative_to(ROOT)}",
        "arms": ARMS,
        "arm_count": len(ARMS),
        "runs_per_arm": 1,
        "plan": {"path": PLAN_FILE.relative_to(ROOT).as_posix(),
                 "sha256": sha256_file(PLAN_FILE)},
        "thresholds_in_force": built["thresholds"],
        "inputs": {str(p.relative_to(ROOT)): sha256_file(p) for p in input_paths()},
        "implementation": {str(p.relative_to(ROOT)): sha256_file(p)
                           for p in implementation_paths()},
        "reference_cells_read_only": {
            name: {**entry, "sha256": sha256_file(ROOT / entry["path"])}
            for name, entry in REFERENCE_CELLS.items()},
        "results": {
            "predictions": {"path": PREDICTIONS_FILE.relative_to(ROOT).as_posix(),
                            "sha256": sha256_file(PREDICTIONS_FILE),
                            "rows": 3 * 40, "evaluation_objects": 3 * 80},
            "metrics": {"path": METRICS_FILE.relative_to(ROOT).as_posix(),
                        "sha256": sha256_file(METRICS_FILE)},
            "diagnostics": {"path": DIAGNOSTICS_FILE.relative_to(ROOT).as_posix(),
                            "sha256": sha256_file(DIAGNOSTICS_FILE)},
        },
        "safety": {"api_calls": 0, "llm_api_calls": 0, "gold_modified": False,
                   "panel_modified": False, "bpmn_modified": False,
                   "thresholds_searched": False, "per_sample_path_choice": False,
                   "existing_results_rewritten": False, "old_manifests_rebound": False},
    }
    write_json(MANIFEST_FILE, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-only", action="store_true",
                        help="write plan.json (arm definitions and hashes) and stop")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--rebuild-reports", action="store_true",
                        help="recompute metrics.json and diagnostics.json from the "
                             "stored predictions only (no arm is re-run)")
    args = parser.parse_args()
    if args.check:
        verify_outputs()
        print(f"{RUN_ID} VERIFIED")
        return 0
    if args.rebuild_reports:
        stored = read_jsonl(PREDICTIONS_FILE)
        whitespace = (read_json(DIAGNOSTICS_FILE).get("whitespace_factor_evidence")
                      if DIAGNOSTICS_FILE.exists() else {})
        rebuilt = rebuild_reports_from_stored_rows(whitespace)
        del stored
        print(json.dumps({"rebuilt_from": str(PREDICTIONS_FILE.relative_to(ROOT)),
                          "arms": list(rebuilt["metrics"]),
                          "predictions_rewritten": False}, ensure_ascii=False))
        return 0
    if args.plan_only:
        plan = build_plan()
        write_json(PLAN_FILE, plan)
        print(json.dumps({"plan": str(PLAN_FILE.relative_to(ROOT)),
                          "arms": list(ARMS), "runs_per_arm": 1}, ensure_ascii=False))
        return 0
    if PREDICTIONS_FILE.exists():
        raise FileExistsError(f"refusing to overwrite an existing run: {PREDICTIONS_FILE}")
    before = {str(p.relative_to(ROOT)): sha256_file(p)
              for p in input_paths() + implementation_paths()
              + [ROOT / e["path"] for e in REFERENCE_CELLS.values()]}
    built = build_all()
    after = {str(p.relative_to(ROOT)): sha256_file(p)
             for p in input_paths() + implementation_paths()
             + [ROOT / e["path"] for e in REFERENCE_CELLS.values()]}
    if before != after:
        raise RuntimeError("a frozen input, implementation or reference cell changed")
    write_manifest(built)
    verify_outputs()
    summary = {}
    for arm, m in built["metrics"].items():
        summary[arm] = {
            "variant": {k: m["A_variant_40"]["partition"][k] for k in
                        ("correct_type", "wrong_type", "explicit_compliance",
                         "final_unknown", "target_type_unobservable")},
            "macro_f1": m["A_variant_40"]["macro_f1_four_types"],
            "control": {k: m["B_control_40"][k] for k in
                        ("false_positives", "explicit_compliance", "final_unknown")},
            "paired_both_sides_correct": m["C_paired_40"]["both_sides_correct"],
        }
    print(json.dumps({"run_id": RUN_ID, "arms": summary},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
