# -*- coding: utf-8 -*-
"""S3.9-EXT wiring repair run: arm W (wiring only) and arm H (scoped evidence).

Two pre-declared arms, one run each over the frozen 40-variant / 40-control panel
= 160 new object predictions.  A/B/C and every older arm are read-only inputs.

W  the measured arm C behaviour with ONE ``resolve_action()`` result feeding the
   candidate surfaces, the checks, the numeric gate and the recorded fields;
H  W plus sourced evidence, evidence scoped to the target activity, and the four
   outcomes ``satisfied / violated / unknown / not_applicable``.

Inference isolation: the scoring call receives only the frozen rule sentence
fields (``modality``, ``action``, ``condition``, ``constraint``, ``exception``)
and the single side's process model.  ``expected_violation``, ``mutation_type``,
``mutation_config``, ``target_activity_id`` and the panel's ``rule_element`` are
read only in the evaluation phase, after ``predictions.jsonl`` is on disk, and
never reach a scorer.  Zero API, zero LLM.
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
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import run_s3_extended_violation_panel_v2 as pr  # noqa: E402
from bpc_hybrid.s3_action_matching_v3 import EvidenceChecksV3  # noqa: E402
from bpc_hybrid.s3_extended_evidence_scope_v1 import (  # noqa: E402
    EVIDENCE_SCOPE_ID, RULE_FIELD_FOR_TYPE, ScopedEvidenceScorer, VERDICT_VIOLATED,
    WIRING_REPAIR_ID, WiringOnlyScorer, aggregate_scope_verdicts, repair_policy,
)
from bpc_hybrid.s3_extended_prediction_accounting_v1 import (  # noqa: E402
    POLICIES as LEGACY_POLICIES, classification, evaluate_instances,
)
from bpc_hybrid.s3_extended_v3_repair_v2 import (  # noqa: E402
    aggregate_with_comparison_gate,
)
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes  # noqa: E402
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES, NONE_LABEL, condition_candidates, constraint_candidates,
    exception_candidates,
)
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

RUN_ID = "s3_extended_evidence_scope_v1"
OUT_DIR = ROOT / "outputs/development" / RUN_ID
PLAN_FILE = OUT_DIR / "plan.json"
PREDICTIONS_FILE = OUT_DIR / "predictions.jsonl"
METRICS_FILE = OUT_DIR / "metrics.json"
DIAGNOSTICS_FILE = OUT_DIR / "diagnostics.json"
MANIFEST_FILE = OUT_DIR / "manifest.json"
OUT_FILES = ("plan.json", "predictions.jsonl", "metrics.json", "diagnostics.json",
             "manifest.json")

GAMMA_EXT = 0.5
V3_INTERNAL_GAMMA = 0.8
TAU = 0.8
THETA = 0.8
LABEL_FALLBACK_GAMMA = 0.4

ARMS = {
    "W_action_resolution_wiring": {
        "label": "arm C behaviour with one action resolution (wiring repair only)",
        "scorer": "WiringOnlyScorer",
        "thresholds": {"v3_internal_gamma": V3_INTERNAL_GAMMA, "tau": TAU,
                       "theta": THETA, "label_fallback_gamma": LABEL_FALLBACK_GAMMA,
                       "gamma_ext": GAMMA_EXT},
        "policy": "unified_five_class_decision_v1+comparison_gate",
    },
    "H_scoped_evidence_and_verdicts": {
        "label": "wiring repair plus sourced, scoped evidence and four-outcome verdicts",
        "scorer": "ScopedEvidenceScorer",
        "thresholds": {"v3_internal_gamma": V3_INTERNAL_GAMMA, "tau": TAU,
                       "theta": THETA, "label_fallback_gamma": LABEL_FALLBACK_GAMMA,
                       "gamma_ext": GAMMA_EXT},
        "policy": "scope_verdict_aggregation_v1",
    },
}

# policies the shared evaluator must accept for this batch, on top of the legacy ones
ARM_POLICIES = {arm: cfg["policy"] for arm, cfg in ARMS.items()}
ALL_POLICIES = {**LEGACY_POLICIES, **ARM_POLICIES}

REFERENCE_CELLS = {
    "arm_C_previous": {
        "path": "outputs/development/s3_extended_repair_v2_v1/predictions.jsonl",
        "arm": "C_v3_no_forced_resolution"},
    "arm_B_previous": {
        "path": "outputs/development/s3_extended_repair_v2_v1/predictions.jsonl",
        "arm": "B_original_path_normalized"},
    "arm_A_previous": {
        "path": "outputs/development/s3_extended_repair_v2_v1/predictions.jsonl",
        "arm": "A_v3_internal_0_4"},
    "winter_frozen": {
        "path": "outputs/evidence/s3_formula_repair_v2/extended_four/reference/winter/"
                "predictions.jsonl", "arm": None},
}
ACCOUNTING_DIR = ROOT / "outputs/development/s3_extended_prediction_accounting_v1"

FINDINGS = {
    "R1": {
        "confirmed": True,
        "statement": ("the runner built the candidate surfaces from "
                      "localize().matched_activity_id while the checks called "
                      "resolve_action() internally; whenever v3 did not localize the "
                      "first was None and the second fell back to the label argmax"),
        "measurement": ("read-only replay of arm C's own scorer over the 80 "
                        "side-instances: 45 side-instances (19 variant + 26 control) "
                        "built their surfaces with None while the checks consumed an "
                        "activity"),
        "not_claimed": ("the stored binding field surface_activity_id is only populated "
                        "for the constraint surface, so the 14+14 records are check "
                        "reference counts, not 28 independent processes; and arm B has "
                        "no matched_activity_id field by construction, which is not a "
                        "binding error"),
    },
    "R2": {
        "confirmed": True,
        "statement": ("condition, constraint and exception candidates were collected "
                      "graph-wide; passing the activity id added no candidate"),
        "measurement": ("on syn_v2_required_condition_01 the activity id added 0 of "
                        "25 constraint candidates and 0 of 3 exception candidates; the "
                        "condition candidate list is empty for that model"),
        "not_claimed": "the strict numeric comparison inside ConstraintSurface.bound_texts was already activity-bound",
    },
    "R3": {
        "confirmed": True,
        "statement": ("_missing_evidence answered with 1 - max_similarity and treated an "
                      "empty candidate list as unknown, so 'contradicted', 'confirmed "
                      "absent in a complete scope', 'cannot be expressed' and 'insufficient "
                      "scope' were not separated"),
        "measurement": "arm H implements the four outcomes and reports applicability and evidence_status separately",
        "not_claimed": "the four outcomes are a code-level distinction, not new legal semantics",
    },
    "R4": {
        "confirmed": True,
        "scope": "upstream rule extraction and panel generation, NOT a scoring bug",
        "instances": {
            "syn_v2_required_condition_05": {
                "frozen_rule_action": "have the obligation to erase personal data without "
                                      "undue delay where one of the following grounds applies",
                "frozen_rule_condition": "where one of the following grounds applies",
                "observation": ("the generator attached the condition to the activity its "
                                "own mutation_config names as target_activity_id; the "
                                "rule action itself speaks about erasing personal data"),
                "status": "recorded as an input problem; target_activity_id is generator "
                          "metadata and was NOT used as an answer key anywhere",
            },
            "syn_v2_exception_not_handled_04": {
                "frozen_rule_element": {"modality": "prohibition", "action": "apply",
                                        "exception": "shall not apply if the decision is "
                                                     "necessary for entering into"},
                "observation": ("the frozen six-element extractor reads 'Paragraph 1 shall "
                                "not apply ...' as a prohibition on the action 'apply' and "
                                "also as an exception; the batch does not revise frozen "
                                "extraction"),
                "status": "recorded as an upstream parsing problem",
            },
        },
    },
    "R5": {
        "confirmed": True,
        "scope": "evaluation contract",
        "statement": ("the generator adds evidence for the target field only, so the "
                      "controls are not proof that every other element holds; alarming on "
                      "a control is therefore not a confirmed legal false positive"),
        "measurement": "reported as a separate contract-diagnosis category; no case is "
                       "removed, relabelled or excluded",
    },
    "R6": {
        "confirmed": True,
        "statement": ("the diagnostic comparison_strings looked the sentence up by "
                      "violation-type name, so condition / constraint / exception were "
                      "recorded as empty strings"),
        "measurement": ("arm W and arm H record rule_field_consumed from the "
                        "element-to-field mapping and rule_text_consumed from the field "
                        "the check actually used; a test asserts they are equal"),
        "not_claimed": "this is a diagnostics repair and changes no prediction",
    },
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
        ROOT / "src/bpc_hybrid/s3_extended_evidence_scope_v1.py",
        ROOT / "src/bpc_hybrid/s3_extended_v3_repair_v2.py",
        ROOT / "src/bpc_hybrid/s3_extended_v3_repair.py",
        ROOT / "src/bpc_hybrid/s3_extended_v3_adapter.py",
        ROOT / "src/bpc_hybrid/s3_action_matching_v3.py",
        ROOT / "src/bpc_hybrid/s3_action_matching_v2.py",
        ROOT / "src/bpc_hybrid/s3_evidence_checks_v1.py",
        ROOT / "src/bpc_hybrid/stage3_extended_violations.py",
        ROOT / "src/bpc_hybrid/s3_extended_prediction_accounting_v1.py",
        ROOT / "src/bpc_hybrid/winter_stage3/winter_similarity.py",
        ROOT / "src/bpc_hybrid/sun_stage3/sun_model.py",
    ]


def input_paths() -> list[Path]:
    paths = [pr.PANEL, pr.EXTENSION_CONFIG, pr.INFERENCE_PACK, pr.STRUCTURAL_CONTRACT,
             pr.SUN_CONFIG]
    paths += sorted((ROOT / "data/input/stage1_stage3/gdpr7").glob("*.bpmn"))
    for variant in read_json(pr.PANEL)["variants"]:
        for side in ("control", "variant"):
            paths.append(ROOT / variant[f"{side}_bpmn"])
    paths += [ROOT / entry["path"] for entry in REFERENCE_CELLS.values()]
    paths += sorted(ACCOUNTING_DIR.glob("*.json*"))
    return paths


def build_plan() -> dict:
    return {
        "schema_version": "s3_extended_evidence_scope_plan@1.0.0",
        "run_id": RUN_ID,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": repair_policy()["scope_statement"],
        "panel": {"path": pr.PANEL.relative_to(ROOT).as_posix(),
                  "sha256": sha256_file(pr.PANEL),
                  "variants": 40, "controls": 40, "objects": 80,
                  "gamma_ext": GAMMA_EXT},
        "arms": ARMS,
        "arm_count": len(ARMS),
        "runs_per_arm": 1,
        "total_new_object_predictions": 2 * 80,
        "actual_inference_runs": {
            "count": 2,
            "reason": ("inference run 1 failed before writing predictions (the row "
                       "representation omitted the label field a view still read); "
                       "inference run 2 succeeded; a later change to the offline "
                       "--replay guard changed the runner bytes and the hash-bound plan "
                       "was regenerated, so inference was re-run once to keep the "
                       "artifact, the plan and the manifest consistent.  Predicted "
                       "labels were identical in runs 2 and 3"),
            "plan_written_before_inference": True,
        },
        "arm_difference": ("H uses the same rule input, action resolution rule and "
                           "thresholds as W; H adds sourced evidence, evidence scoping "
                           "and the four-outcome verdict contract with its own "
                           "aggregation"),
        "evaluation_views": {
            "A_historical_five_class": ("the original five-class labels (four violation "
                                        "types + none), reported as development "
                                        "regression against the old synthetic labels; "
                                        "NOT a human-confirmed legal false-positive rate"),
            "pairing_definition": ("paired success counts a pair only when BOTH the "
                                   "variant carries the expected type AND the control is "
                                   "answered with explicit compliance 'none'.  A control "
                                   "abstention is never a correct rejection, and a "
                                   "variant-side true positive does not by itself make "
                                   "the pair successful; this is why the paired count is "
                                   "far below the variant correct count"),
            "B_target_field_diagnostic": ("the target field is read only after inference "
                                          "and each method's stored four-type results are "
                                          "consulted for that one check; a mechanism "
                                          "diagnostic, not a new headline table; the "
                                          "controls only guarantee the target field"),
        },
        "inference_isolation": [
            "the scorer receives only the frozen rule sentence fields and the single "
            "side's process model",
            "expected_violation, mutation_type, mutation_config, target_activity_id and "
            "rule_element are read only after predictions.jsonl is written",
            "no file name, syn_ prefix, item id, variant/control identity or the other "
            "side's BPMN reaches the scorer",
        ],
        "findings": FINDINGS,
        "implementation": {str(p.relative_to(ROOT)): sha256_file(p)
                           for p in implementation_paths()},
        "inputs": {str(p.relative_to(ROOT)): sha256_file(p) for p in input_paths()},
    }


# ------------------------------------------------------------------- inference


def rule_sentence_view(sentence: dict) -> dict:
    """Only the fields a check may see; no panel or expected-answer metadata."""
    return {
        "modality": sentence.get("modality"),
        "action": sentence.get("action"),
        "condition": sentence.get("condition"),
        "constraint": sentence.get("constraint"),
        "exception": sentence.get("exception"),
    }


def build_scorer(arm: str, v3, sim_text, resolution):
    if arm == "W_action_resolution_wiring":
        return WiringOnlyScorer(v3, sim_text, LABEL_FALLBACK_GAMMA, GAMMA_EXT,
                                resolution=resolution)
    return ScopedEvidenceScorer(v3, sim_text, LABEL_FALLBACK_GAMMA, GAMMA_EXT,
                                resolution=resolution)


def score_side(arm: str, sentence: dict, bpmn_path: Path, process_id: str, v3,
               sim_text: str, contract, nlp) -> dict:
    raw_bytes = bpmn_path.read_bytes()
    record = parse_bpmn_bytes(raw_bytes, source_path="panel.bpmn", contract=contract)
    model = SunProcessModel(process_id, record, nlp)
    xml_root = ET.fromstring(raw_bytes)

    # ONE action resolution, computed before anything consumes it
    probe = build_scorer(arm, v3, sim_text, None)
    resolution = probe.resolve_action(rule_sentence_view(sentence).get("action") or "",
                                      model)
    scorer = build_scorer(arm, v3, sim_text, resolution)

    condition_surface = condition_candidates(record, xml_root,
                                             resolution["resolved_activity_id"])
    constraint_surface = constraint_candidates(record, xml_root,
                                               resolution["resolved_activity_id"])
    exception_surface = exception_candidates(record, xml_root,
                                             resolution["resolved_activity_id"])

    if arm == "H_scoped_evidence_and_verdicts":
        results = {
            "prohibited_action_present": scorer.prohibited_action(sentence, model),
            "required_condition_not_enforced": scorer.condition_check(
                sentence, model, record, xml_root),
            "constraint_violated": scorer.constraint_check(sentence, model, record,
                                                           xml_root),
            "exception_not_handled": scorer.exception_check(sentence, model, record,
                                                            xml_root),
        }
    else:
        results = {
            "prohibited_action_present": scorer.prohibited_action(sentence, model),
            "required_condition_not_enforced": scorer.required_condition(
                sentence, model, condition_surface),
            "constraint_violated": scorer.constraint_violated(
                sentence, model, constraint_surface),
            "exception_not_handled": scorer.exception_not_handled(
                sentence, model, exception_surface),
        }

    checks = {}
    for t in EXTENDED_TYPES:
        entry = {k: v for k, v in results[t].items() if k != "evidence_scope"}
        if t != "prohibited_action_present" and "evidence_scope" in results[t]:
            scope = results[t]["evidence_scope"]
            entry["evidence_sources"] = {
                "scope_statement": scope["scope_statement"],
                "scope_enumerable": scope["scope_enumerable"],
                "target_activity_id": scope["target_activity_id"],
                "bound": [dict(e) for e in scope["bound"]],
                "unbound": [dict(e) for e in scope["unbound"]],
                "surfaces": scope["surfaces"],
            }
        checks[t] = entry

    scores = {t: (results[t].get("score") if results[t].get("observable") else None)
              for t in EXTENDED_TYPES}
    return {
        "checks": checks,
        "scores": scores,
        "observability": {t: {"observable": bool(results[t].get("observable", False)),
                              "reason": results[t].get("reason")}
                          for t in EXTENDED_TYPES},
        "scores_detail": {t: {k: v for k, v in results[t].items()
                              if k not in ("score", "evidence_scope")}
                          for t in EXTENDED_TYPES},
        "action_resolution": resolution,
        "candidate_surfaces": {
            "required_condition_not_enforced": list(condition_surface),
            "constraint_violated": list(constraint_surface),
            "exception_not_handled": list(exception_surface),
        },
        "comparison_strings": {
            t: {"rule_field": RULE_FIELD_FOR_TYPE[t],
                "rule_text_consumed": checks[t].get("rule_text_consumed"),
                "consumed_candidate": checks[t].get("best_candidate"),
                "surface_activity_id": getattr(
                    {"required_condition_not_enforced": condition_surface,
                     "constraint_violated": constraint_surface,
                     "exception_not_handled": exception_surface}.get(t), "activity_id",
                    None)}
            for t in EXTENDED_TYPES},
    }


def final_label_for(arm: str, side: dict, gamma_ext: float):
    scores = {
        t: {
            **side["scores_detail"][t],
            "score": side["scores"][t],
            "observable": side["observability"][t]["observable"],
        }
        for t in EXTENDED_TYPES
    }
    if arm == "H_scoped_evidence_and_verdicts":
        return aggregate_scope_verdicts(scores, gamma_ext)
    return aggregate_with_comparison_gate(scores, gamma_ext)


def build_rows(panel: dict, rule_texts: dict, v3, sim_text, contract, nlp) -> list[dict]:
    rows = []
    for variant in panel["variants"]:
        pid = variant["process_id"]
        for side in ("variant", "control"):
            sentence = pr._locked_sentence(variant, rule_texts[variant["rule_id"]], nlp)
            view = rule_sentence_view(sentence)
            per_arm = {}
            for arm in ARMS:
                scored = score_side(arm, view, ROOT / variant[f"{side}_bpmn"], pid, v3,
                                    sim_text, contract, nlp)
                decision = final_label_for(arm, scored, GAMMA_EXT)
                per_arm[arm] = {
                    "arm": arm,
                    "item_id": variant["variant_id"],
                    "side": side,
                    "decision_policy": ARM_POLICIES[arm],
                    "gamma_ext": GAMMA_EXT,
                    "final_label": decision["predicted"],
                    "final_unknown": decision["predicted"] is None,
                    "per_type_decisions": decision["per_type"],
                    "action_resolution": scored["action_resolution"],
                    "candidate_surfaces": scored["candidate_surfaces"],
                    "checks": scored["checks"],
                    "scores": scored["scores"],
                    "observability": scored["observability"],
                    "comparison_strings": scored["comparison_strings"],
                    "thresholds": ARMS[arm]["thresholds"],
                    "rule_sentence_fields": view,
                    "gold_visible": False,
                }
                if arm == "H_scoped_evidence_and_verdicts":
                    per_arm[arm]["decision_detail"] = {
                        "required_evidence_checks": decision["required_evidence_checks"],
                        "pending_required_checks": decision["pending_required_checks"],
                        "policy": decision["policy"],
                    }
            rows.append(per_arm)
    return rows


def flatten(rows_by_object: list[dict]) -> list[dict]:
    return [row[arm] for row in rows_by_object for arm in ARMS]


# ------------------------------------------------------------------ evaluation


def historical_view(rows: list[dict], panel: dict) -> dict:
    """View A: the original five-class labels, through the shared accounting functions."""
    expected = {(r["arm"], v["variant_id"]): v["expected_violation"]
                for r in rows for v in panel["variants"]}
    decisions = []
    for row in rows:
        decisions.append({
            "arm": row["arm"], "item_id": row["item_id"], "side": row["side"],
            "source_row": 1, "decision_policy": row["decision_policy"],
            "gamma_ext": row["gamma_ext"], "predicted": row["final_label"],
            "per_type_decisions": row["per_type_decisions"],
            "final_unknown": row["final_label"] is None,
            "expected": (expected[row["arm"], row["item_id"]]
                         if row["side"] == "variant" else NONE_LABEL),
        })
    result = {}
    for arm in ARMS:
        arm_records = [d for d in decisions if d["arm"] == arm]
        groups = {}
        for record in arm_records:
            groups.setdefault(record["item_id"], {})[record["side"]] = record
        variants = [groups[i]["variant"] for i in sorted(groups)]
        controls = [groups[i]["control"] for i in sorted(groups)]
        counts = {"correct_type": 0, "wrong_type": 0, "explicit_compliance": 0,
                  "final_unknown": 0}
        for record in variants:
            p = record["predicted"]
            counts["correct_type" if p == record["expected"] else
                   "final_unknown" if p is None else
                   "explicit_compliance" if p == NONE_LABEL else "wrong_type"] += 1
        control_counts = {"false_positives": 0, "explicit_compliance": 0,
                          "final_unknown": 0}
        for record in controls:
            p = record["predicted"]
            control_counts["final_unknown" if p is None else
                           "explicit_compliance" if p == NONE_LABEL else
                           "false_positives"] += 1
        per_pair = [{"item_id": record["item_id"],
                     "expected": record["expected"],
                     "variant_correct": record["predicted"] == record["expected"],
                     "control_correct": groups[record["item_id"]]["control"]["predicted"]
                     == NONE_LABEL}
                    for record in variants]
        paired = sum(p["variant_correct"] and p["control_correct"] for p in per_pair)
        merged = classification(list(groups[i][s] for i in groups
                                     for s in ("variant", "control")),
                                (NONE_LABEL,) + tuple(EXTENDED_TYPES))
        style = classification(variants, tuple(EXTENDED_TYPES))
        if paired > min(counts["correct_type"], control_counts["explicit_compliance"]):
            raise RuntimeError("paired success exceeds a side's correct count")
        if abs(merged["accuracy"]
               - (counts["correct_type"] + control_counts["explicit_compliance"]) / 80) \
                > 1e-12:
            raise RuntimeError("merged accuracy contradicts the side counts")
        result[arm] = {
            "decision_policy": ARM_POLICIES[arm],
            "A_variant_40": {
                "objects": 40, **counts,
                "target_type_unknown": sum(
                    groups[i]["variant"]["per_type_decisions"][groups[i]["variant"]["expected"]]
                    is None for i in groups),
                **style,
            },
            "B_control_40": {"objects": 40, **control_counts},
            "C_paired_40": {"pairs": 40, "both_sides_correct": paired,
                            "paired_accuracy": paired / 40, "per_pair": per_pair},
            "D_merged_80": {"objects": 80,
                            "correct": counts["correct_type"]
                            + control_counts["explicit_compliance"], **merged},
        }
    return result


def target_field_view(rows: list[dict], panel: dict) -> dict:
    """View B: read the target field only now and inspect each arm's stored checks."""
    targets = {v["variant_id"]: v["expected_violation"] for v in panel["variants"]}
    by_arm: dict[str, dict] = {arm: {} for arm in ARMS}
    for row in rows:
        by_arm[row["arm"]][(row["item_id"], row["side"])] = row
    out = {}
    for arm, cells in by_arm.items():
        per_type = {t: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for t in EXTENDED_TYPES}
        control_unknown = {t: 0 for t in EXTENDED_TYPES}
        pairs = []
        for item, target in sorted(targets.items()):
            variant = cells[(item, "variant")]
            control = cells[(item, "control")]
            decision = variant["per_type_decisions"].get(target)
            if decision is True:
                per_type[target]["tp"] += 1
            elif decision is False:
                per_type[target]["fp"] += 1
            else:
                per_type[target]["fn"] += 1
            for t in EXTENDED_TYPES:
                if cells[(item, "control")]["per_type_decisions"].get(t) is None:
                    control_unknown[t] += 1
            control_ok = control["per_type_decisions"].get(target) is False
            pairs.append({"item_id": item, "target": target,
                          "variant_target_decision": decision,
                          "control_target_decision":
                              control["per_type_decisions"].get(target),
                          "both_sides_ok": decision is True and control_ok})
        for t in EXTENDED_TYPES:
            per_type[t]["tn"] = sum(
                1 for item, target in targets.items()
                if target != t
                and cells[(item, "variant")]["per_type_decisions"].get(t) is False)
        for t, c in per_type.items():
            support = c["tp"] + c["fn"]
            c["support"] = support
            c["precision"] = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
            c["recall"] = c["tp"] / support if support else 0.0
            c["f1"] = (2 * c["tp"] / (2 * c["tp"] + c["fp"] + c["fn"])
                       if 2 * c["tp"] + c["fp"] + c["fn"] else 0.0)
        out[arm] = {
            "note": ("each method's own stored per-type decision for the target type; "
                     "the controls only guarantee the target field"),
            "per_type": per_type,
            "control_unknown_by_type": control_unknown,
            "paired_target_ok": sum(1 for p in pairs if p["both_sides_ok"]),
            "per_pair": pairs,
        }
    for name, entry in REFERENCE_CELLS.items():
        path = ROOT / entry["path"]
        if not path.is_file():
            out[name] = {"available": False, "reason": "stored cell missing"}
            continue
        stored = read_jsonl(path)
        if entry["arm"]:
            stored = [r for r in stored if r["arm"] == entry["arm"]]
        if not stored or "scores_detail" not in stored[0]:
            out[name] = {"available": False,
                         "reason": "the stored cell does not carry native per-type "
                                   "detail; not recomputed to avoid passing it off as "
                                   "a stored result"}
            continue
        cells = {}
        for row in stored:
            cells[(row["item_id"], "variant")] = row
        per_type = {t: {"tp": 0, "fp": 0, "fn": 0} for t in EXTENDED_TYPES}
        for item, target in targets.items():
            row = cells.get((item, "variant"))
            if row is None:
                continue
            obs = row["observability"][target]["observable"]
            decision = (row["predicted_violation_type"] == target) if obs else None
            if decision is True:
                per_type[target]["tp"] += 1
            elif decision is False:
                per_type[target]["fp"] += 1
            else:
                per_type[target]["fn"] += 1
        out[name] = {"available": True, "source": entry["path"],
                     "arm": entry["arm"], "per_type": per_type}
    return out


def contract_diagnosis(rows: list[dict], panel: dict) -> list[dict]:
    """Read-only: what each problem instance actually is, without relabelling it."""
    variants = {v["variant_id"]: v for v in panel["variants"]}
    by_key = {(r["arm"], r["item_id"], r["side"]): r for r in rows}
    diagnosis = []
    for item, variant in sorted(variants.items()):
        element = variant["rule_element"]
        condition = element.get("condition")
        mutation = variant.get("mutation_config") or {}
        control = by_key[("H_scoped_evidence_and_verdicts", item, "control")]
        entries = []
        if condition:
            entries.append({
                "category": "target_evidence_construction",
                "detail": ("the generator adds the condition to the activity its own "
                           "mutation_config names; this is the panel's construction "
                           "choice, not a legal answer key"),
            })
        if element.get("modality") == "prohibition" and element.get("exception"):
            entries.append({
                "category": "semantic_target_binding_uncertain",
                "detail": ("the frozen extractor reads one sentence as both a prohibition "
                           "on the action and an exception; the batch does not revise "
                           "frozen extraction"),
            })
        if not any(e["category"] == "target_evidence_construction" for e in entries):
            entries.append({
                "category": "whole_rule_control_unverified",
                "detail": ("the control only carries evidence for the target field; the "
                           "other three checks were not constructed to be satisfied, so "
                           "a control alarm is not a confirmed legal false positive"),
            })
        diagnosis.append({
            "item_id": item,
            "rule_id": variant["rule_id"],
            "mutation_hash": hashlib.sha256(
                json.dumps(mutation, sort_keys=True).encode("utf-8")).hexdigest()[:16],
            "categories": [e["category"] for e in entries],
            "entries": entries,
            "arm_H_control_final_label": control["final_label"],
        })
    return diagnosis


# ----------------------------------------------------------------------- driver


def build_all() -> dict:
    import spacy
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    panel = read_json(pr.PANEL)
    if float(panel["config"]["gamma_ext"]) != GAMMA_EXT:
        raise RuntimeError("panel gamma_ext changed")
    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    v3 = EvidenceChecksV3(sim, TAU, V3_INTERNAL_GAMMA, THETA, nlp)
    if v3.gamma != V3_INTERNAL_GAMMA:
        raise RuntimeError("the v3 instance does not carry the declared gamma")
    contract = load_stage1_contract(pr.STRUCTURAL_CONTRACT)
    rule_texts = pr._rule_texts()

    write_json(PLAN_FILE, build_plan())

    rows_by_object = build_rows(panel, rule_texts, v3, sim.text_pair, contract, nlp)
    rows = flatten(rows_by_object)
    if len(rows) != 160:
        raise RuntimeError(f"expected 160 object predictions, got {len(rows)}")
    # phase boundary: every prediction is on disk before any label is read
    write_rows(PREDICTIONS_FILE, rows)

    historical = historical_view(rows, panel)
    target = target_field_view(rows, panel)
    write_json(METRICS_FILE, {
        "schema_version": "s3_extended_evidence_scope_metrics@1.0.0",
        "run_id": RUN_ID, "generated_utc": started, "scope": repair_policy()["scope_statement"],
        "arms": {arm: {**historical[arm], "label": ARMS[arm]["label"],
                       "thresholds": ARMS[arm]["thresholds"]}
                 for arm in ARMS},
        "target_field_diagnostic": target,
        "legacy_reference": legacy_reference_view(),
    })
    write_json(DIAGNOSTICS_FILE, {
        "schema_version": "s3_extended_evidence_scope_diagnostics@1.0.0",
        "run_id": RUN_ID,
        "findings": FINDINGS,
        "policy_notes": {"scope": repair_policy()["scope_statement"],
                         "arm_policies": ARM_POLICIES,
                         "diagnostics_repair_does_not_affect_predictions": True},
        "contract_diagnosis": contract_diagnosis(rows, panel),
        "comparison_strings_check": comparison_strings_check(rows),
    })
    return {"rows": rows, "runtime_seconds": round(time.time() - t0, 3),
            "started_utc": started}


def legacy_reference_view() -> dict:
    """Re-run the shared accounting over the stored A/B/C final decisions.

    ``final_predictions.jsonl`` is already the materialized decision table of the
    accounting batch, so it goes straight into the shared evaluator; the numbers
    must equal the stored ``metrics.json`` of that batch.  Nothing is re-decided
    and no label is re-associated here.
    """
    decisions = read_jsonl(ACCOUNTING_DIR / "final_predictions.jsonl")
    return evaluate_instances(decisions)


def comparison_strings_check(rows: list[dict]) -> dict:
    """Assert the recorded rule text is the text the check consumed."""
    checked, mismatches = 0, []
    for row in rows:
        for t, entry in row["comparison_strings"].items():
            field = RULE_FIELD_FOR_TYPE[t]
            consumed = row["rule_sentence_fields"].get(field) or ""
            if (entry["rule_text_consumed"] or "") != consumed.strip():
                mismatches.append({"arm": row["arm"], "item_id": row["item_id"],
                                   "side": row["side"], "type": t})
            checked += 1
    if mismatches:
        raise RuntimeError(f"diagnostic rule text mismatch: {mismatches[:5]}")
    return {"checked": checked, "mismatches": 0,
            "note": "rule_text_consumed equals the sentence field the check used"}


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
    if len(rows) != 160:
        raise RuntimeError(f"expected 160 rows, got {len(rows)}")
    for arm, cfg in ARMS.items():
        arm_rows = [r for r in rows if r["arm"] == arm]
        if len(arm_rows) != 80:
            raise RuntimeError(f"{arm}: expected 80 rows")
        if {r["decision_policy"] for r in arm_rows} != {cfg["policy"]}:
            raise RuntimeError(f"{arm}: policy mismatch")
    return {"rows": rows, "plan": plan, "metrics": read_json(METRICS_FILE),
            "diagnostics": read_json(DIAGNOSTICS_FILE)}


def replay_metrics() -> dict:
    """Recompute the metric views from the stored rows only (no inference)."""
    rows = read_jsonl(PREDICTIONS_FILE)
    panel = read_json(pr.PANEL)
    return {"historical": historical_view(rows, panel),
            "target_field": target_field_view(rows, panel)}


def write_manifest(built: dict) -> None:
    manifest = {
        "schema_version": "s3_extended_evidence_scope_manifest@1.0.0",
        "run_id": RUN_ID,
        "started_utc": built["started_utc"],
        "runtime_seconds": built["runtime_seconds"],
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                              text=True).strip(),
        "command": f"python {Path(__file__).relative_to(ROOT)}",
        "arms": ARMS,
        "arm_count": len(ARMS),
        "runs_per_arm": 1,
        "new_object_predictions": 160,
        "plan": {"path": PLAN_FILE.relative_to(ROOT).as_posix(),
                 "sha256": sha256_file(PLAN_FILE)},
        "inputs": {str(p.relative_to(ROOT)): sha256_file(p) for p in input_paths()},
        "implementation": {str(p.relative_to(ROOT)): sha256_file(p)
                           for p in implementation_paths()},
        "reference_cells_read_only": {
            name: {**entry, "sha256": sha256_file(ROOT / entry["path"]), "rerun": False}
            for name, entry in REFERENCE_CELLS.items()},
        "results": {
            "predictions": {"path": PREDICTIONS_FILE.relative_to(ROOT).as_posix(),
                            "sha256": sha256_file(PREDICTIONS_FILE), "rows": 160,
                            "evaluation_objects": 160},
            "metrics": {"path": METRICS_FILE.relative_to(ROOT).as_posix(),
                        "sha256": sha256_file(METRICS_FILE)},
            "diagnostics": {"path": DIAGNOSTICS_FILE.relative_to(ROOT).as_posix(),
                            "sha256": sha256_file(DIAGNOSTICS_FILE)},
        },
        "safety": {"api_calls": 0, "llm_api_calls": 0, "gold_modified": False,
                   "panel_modified": False, "bpmn_modified": False,
                   "thresholds_searched": False, "existing_results_rewritten": False,
                   "old_manifests_rebound": False, "other_agents_started": False},
    }
    write_json(MANIFEST_FILE, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--replay", action="store_true",
                        help="recompute the metric views from stored rows only")
    args = parser.parse_args()
    if args.check:
        verify_outputs()
        print(f"{RUN_ID} VERIFIED")
        return 0
    if args.plan_only:
        write_json(PLAN_FILE, build_plan())
        print(json.dumps({"plan": str(PLAN_FILE.relative_to(ROOT)), "arms": list(ARMS),
                          "runs_per_arm": 1}, ensure_ascii=False))
        return 0
    if args.replay:
        recomputed = replay_metrics()
        stored = read_json(METRICS_FILE)
        for arm in ARMS:
            for key in ("decision_policy", "A_variant_40", "B_control_40",
                        "C_paired_40", "D_merged_80"):
                if recomputed["historical"][arm][key] != stored["arms"][arm][key]:
                    raise RuntimeError(f"{arm}: stored {key} is not reproducible")
            if recomputed["target_field"][arm] != \
                    stored["target_field_diagnostic"][arm]:
                raise RuntimeError(f"{arm}: the stored target view is not reproducible")
        print(json.dumps({"replay": "ok", "arms": list(ARMS),
                          "predictions_rewritten": False,
                          "note": "metric views recomputed from stored rows only"},
                         ensure_ascii=False))
        return 0
    if PREDICTIONS_FILE.exists():
        raise FileExistsError(f"refusing to overwrite an existing run: {PREDICTIONS_FILE}")
    before = {str(p.relative_to(ROOT)): sha256_file(p) for p in input_paths()}
    built = build_all()
    after = {str(p.relative_to(ROOT)): sha256_file(p) for p in input_paths()}
    if before != after:
        raise RuntimeError("a frozen input or reference cell changed during the run")
    write_manifest(built)
    verify_outputs()
    metrics = read_json(METRICS_FILE)
    summary = {}
    for arm in ARMS:
        block = metrics["arms"][arm]
        a, b = block["A_variant_40"], block["B_control_40"]
        summary[arm] = {
            "variant": {k: a[k] for k in ("correct_type", "wrong_type",
                                          "explicit_compliance", "final_unknown",
                                          "target_type_unknown")},
            "macro_f1": round(a["macro_f1"], 4),
            "control": {k: b[k] for k in ("false_positives", "explicit_compliance",
                                          "final_unknown")},
            "paired": block["C_paired_40"]["both_sides_correct"],
        }
    print(json.dumps({"run_id": RUN_ID, "objects": 160, "arms": summary},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
