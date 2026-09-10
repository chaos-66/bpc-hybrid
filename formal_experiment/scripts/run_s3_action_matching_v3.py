# -*- coding: utf-8 -*-
"""S3 action-representation v3 measurement on the frozen paired mechanism panel.

Comparison columns, all on the identical frozen contracts:

* ``sun_2024_frozen``  - reused verified predictions (previous round)
* ``evidence_checks_v2_action_matching`` - reused verified predictions
* ``evidence_checks_v3_action_structure`` - 56 newly generated predictions

Only the action representation and the candidate matching changed.  The frozen
contracts, the original/variant BPMNs, the Stage 1 parsing, the NLP model, the
similarity backend, the thresholds, the executor check, the order check, the
unknown aggregation and the metric code path are reused unchanged.

Reused columns are referenced by path and SHA-256 after binding verification and
are never re-run.  The two remaining missing_action unknowns stay in the main
denominator: no contract, no expected label and no sample is changed.

Zero LLM/API calls; no human Gold, legacy label, BPMN, frozen variant, old
prediction or old report is modified.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

RUN_ID = "s3_action_matching_v3"

V1_DIR = ROOT / "outputs/development/s3_paired_mechanism_v1"
V2_DIR = ROOT / "outputs/development/s3_action_matching_v2"
CONTRACTS_FILE = V1_DIR / "contracts_locked.json"
V1_MANIFEST = V1_DIR / "manifest.json"
V2_MANIFEST = V2_DIR / "manifest.json"
SOURCE_PREDICTIONS = V1_DIR / "predictions.jsonl"          # sun + v1 columns
V2_PREDICTIONS = V2_DIR / "predictions.jsonl"              # v2 column
V2_METRICS = V2_DIR / "metrics.json"

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v1.json"
SUN_CONFIG = ROOT / "configs/sun_stage3_development_v1.json"

OUT_DIR = ROOT / "outputs/development" / RUN_ID
PREDICTIONS_FILE = OUT_DIR / "predictions.jsonl"
METRICS_FILE = OUT_DIR / "metrics.json"
DIAGNOSTICS_FILE = OUT_DIR / "diagnostics.json"
MANIFEST_FILE = OUT_DIR / "manifest.json"

SUN_METHOD = "sun_2024_frozen"
V2_METHOD = "evidence_checks_v2_action_matching"
V3_METHOD = "evidence_checks_v3_action_structure"
METHODS = (SUN_METHOD, V2_METHOD, V3_METHOD)
CHECK_TYPES = ("missing_action", "incorrect_actor", "out_of_order")
EXPECTED_STATUS = {"original": "satisfied", "variant": "violation"}

# The two remaining unknowns and the four independently reproduced causes.
FOCUS_ITEMS = ("syn_missing_action_04::variant", "syn_missing_action_06::variant")

COUNTER_EXAMPLES = (
    {"name": "nested_action_substitution",
     "requirement": 'Add the right to read a file',
     "candidates": ['Add the right to delete a file'],
     "expected_mapped": False,
     "expected_reasons": ["nested_action_substituted"]},
    {"name": "relation_containment_undetermined",
     "requirement": "Stop running the pump using coolant",
     "candidates": ["Stop using coolant"],
     "expected_mapped": False,
     "expected_reasons": ["nested_action_component_containment",
                          "required_object_content_absent"]},
    {"name": "unrelated_candidate_does_not_veto",
     "requirement": "Inspect package",
     "candidates": ["Examine package", "Inspect furniture"],
     "expected_mapped": True,
     "expected_reasons": []},
    {"name": "role_swap_detected",
     "requirement": "Transfer money from Alice to Bob",
     "candidates": ["Transfer money from Bob to Alice"],
     "expected_mapped": False,
     "expected_reasons": ["role_content_difference"]},
    {"name": "lexical_variation_not_a_conflict",
     "requirement": "Inspect package",
     "candidates": ["Examine package"],
     "expected_mapped": True,
     "expected_reasons": []},
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


V2RUN = load_module("action_matching_v2_runner", SCRIPTS / "run_s3_action_matching_v2.py")
V1 = V2RUN.V1
sha256_file = V2RUN.sha256_file
read_json = V2RUN.read_json
read_jsonl = V2RUN.read_jsonl
git = V2RUN.git


# ---------------------------------------------------------------------------
# Context, predictions
# ---------------------------------------------------------------------------


def prepare_context() -> dict:
    """Same models, backend and NLP objects as the reused columns."""
    from bpc_hybrid.s3_action_matching_v3 import EvidenceChecksV3

    panel = read_json(PANEL)
    records, reachability, models, scorers = V1.prepare(panel)
    base = scorers["evidence_checks_v1"]
    v3 = EvidenceChecksV3(base.sim, base.tau, base.gamma, base.theta, nlp=base.nlp)
    return {
        "panel": panel, "records": records, "reachability": reachability,
        "models": models, "v3": v3,
        "shared_binding": {
            "thresholds": {"tau": float(base.tau), "gamma": float(base.gamma),
                           "theta": float(base.theta)},
            "nlp_model": "en_core_web_sm",
            "nlp_version": base.nlp.meta.get("version"),
            "similarity_backend": "winter_stage3.winter_similarity.WinterSimilarity",
            "stage1_structural_contract": "configs/stage1_structural_s11_s14.json",
            "shared_backend_object_with_reused_columns": True,
            "shared_nlp_object_with_reused_columns": True,
        },
    }


def build_v3_predictions(context: dict, contracts_doc: dict) -> list[dict]:
    rows: list[dict] = []
    scorer = context["v3"]
    for contract in contracts_doc["contracts"]:
        if contract["status"] != "valid":
            continue
        requirement = contract["requirement"]
        requirement_sha = V1.canonical_sha256(requirement)
        for side, key in (("original", "source_bpmn"), ("variant", "variant_bpmn")):
            bpmn = contract[key]
            raw = V1.run_signals(scorer, requirement, context["models"][bpmn])
            rows.append({
                "schema_version": "s3_action_matching_v3_prediction@1.0.0",
                "run_id": RUN_ID,
                "item_id": f"{contract['contract_id']}::{side}",
                "pair_id": contract["contract_id"],
                "variant_id": contract["variant_id"],
                "side": side,
                "checker": V3_METHOD,
                "method_scope": "action representation and candidate matching only",
                "target_check": contract["check_type"],
                "process_id": contract["process_id"],
                "model_bpmn": bpmn,
                "model_bpmn_sha256": sha256_file(ROOT / bpmn),
                "requirement_sha256": requirement_sha,
                "shared_binding": context["shared_binding"],
                "raw": raw,
                "signals": {check: V1.normalize_evidence(check, raw[check])
                            for check in CHECK_TYPES},
            })
    return rows


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def build_metrics(contracts_doc: dict, v3_rows: list[dict]) -> dict:
    v1_manifest = read_json(V1_MANIFEST)
    v2_manifest = read_json(V2_MANIFEST)
    v1_rows = read_jsonl(SOURCE_PREDICTIONS)
    v2_rows = read_jsonl(V2_PREDICTIONS)
    v2_metrics = read_json(V2_METRICS)

    sources: dict[str, Any] = {}
    methods: dict[str, Any] = {}
    faithfulness: dict[str, bool] = {}

    sun_rows = [row for row in v1_rows if row["checker"] == SUN_METHOD]
    v1_rows_only = [row for row in v1_rows if row["checker"] == "evidence_checks_v1"]
    methods[SUN_METHOD] = V2RUN.metrics_for_method(sun_rows, contracts_doc)
    faithfulness[SUN_METHOD] = json.dumps(methods[SUN_METHOD], sort_keys=True) == json.dumps(
        v2_metrics["methods"][SUN_METHOD], sort_keys=True)
    sources[SUN_METHOD] = {
        "mode": "reused_verified_predictions",
        "path": SOURCE_PREDICTIONS.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(SOURCE_PREDICTIONS),
        "manifest": V1_MANIFEST.relative_to(ROOT).as_posix(),
        "manifest_sha256": sha256_file(V1_MANIFEST),
        "manifest_recorded_sha256": v1_manifest["results"]["predictions"]["sha256"],
        "item_count": len(sun_rows),
        "items": reused_items(sun_rows),
    }
    methods[V2_METHOD] = V2RUN.metrics_for_method(v2_rows, contracts_doc)
    faithfulness[V2_METHOD] = json.dumps(methods[V2_METHOD], sort_keys=True) == json.dumps(
        v2_metrics["methods"][V2_METHOD], sort_keys=True)
    sources[V2_METHOD] = {
        "mode": "reused_verified_predictions",
        "path": V2_PREDICTIONS.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(V2_PREDICTIONS),
        "manifest": V2_MANIFEST.relative_to(ROOT).as_posix(),
        "manifest_sha256": sha256_file(V2_MANIFEST),
        "manifest_recorded_sha256": v2_manifest["results"]["predictions"]["sha256"],
        "item_count": len(v2_rows),
        "items": reused_items(v2_rows),
    }
    methods[V3_METHOD] = V2RUN.metrics_for_method(v3_rows, contracts_doc)
    sources[V3_METHOD] = {
        "mode": "newly_generated",
        "path": PREDICTIONS_FILE.relative_to(ROOT).as_posix(),
        "item_count": len(v3_rows),
    }
    return {
        "schema_version": "s3_action_matching_v3_metrics@1.0.0",
        "run_id": RUN_ID,
        "denominator_policy": v2_metrics["denominator_policy"],
        "denominator_policy_source": {
            "path": V2_METRICS.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(V2_METRICS),
            "note": "inherited unchanged; the evaluator code path is not modified",
        },
        "methods": methods,
        "macro_f1": {method: methods[method]["macro_f1"] for method in METHODS},
        "total_unknown": {method: methods[method]["total_unknown"] for method in METHODS},
        "valid_contract_coverage": {
            "fixed_variants": contracts_doc["counts"]["fixed_variants"],
            "valid_contracts": contracts_doc["counts"]["valid_contracts"],
            "unresolved": contracts_doc["counts"]["unresolved"],
        },
        "sources": sources,
        "shared_evaluator_adapter": {
            "description": "every column is scored through the frozen evaluator by "
                           "canonicalising the in-memory method label; stored rows keep their "
                           "true method id and no metric formula is reimplemented",
            "canonical_alias": V2RUN.CANONICAL_ALIAS,
            "faithfulness_check_against_stored_metrics": faithfulness,
        },
        "v1_column_reference": {
            "method": "evidence_checks_v1",
            "path": SOURCE_PREDICTIONS.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(SOURCE_PREDICTIONS),
            "note": "the v1 column is not a comparison column this round; its per-item statuses "
                    "are used for the v2-to-v3 change audit only",
            "items": reused_items(v1_rows_only),
        },
    }


def reused_items(rows: list[dict]) -> list[dict]:
    """Per-item statuses of a reused column; the evidence stays in the source file."""
    items = []
    for row in sorted(rows, key=lambda r: (r["pair_id"], r["side"])):
        items.append({
            "item_id": row["item_id"], "pair_id": row["pair_id"], "side": row["side"],
            "checker": row["checker"], "target_check": row["target_check"],
            "status": row["signals"][row["target_check"]]["status"],
            "reason": row["signals"][row["target_check"]]["reason"],
            "signals": {check: row["signals"][check]["status"] for check in CHECK_TYPES},
        })
    return items


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def status_of(row: dict) -> str:
    return row["signals"][row["target_check"]]["status"]


def expected_of(row: dict) -> str:
    return EXPECTED_STATUS[row["side"]]


def is_correct(row: dict) -> bool:
    return status_of(row) == expected_of(row)


def match_records(raw: dict, check: str) -> list[dict]:
    if check == "out_of_order":
        records = []
        for detail in raw.get("details", []):
            for key in ("before", "after"):
                if isinstance(detail.get(key), dict):
                    records.append(detail[key])
        return records
    return [detail["match"] for detail in raw.get("details", [])
            if isinstance(detail.get("match"), dict)]


def match_reason_codes(record: dict) -> list[str]:
    """Decision-level codes of a match record, including its candidates' evidence."""
    codes = {reason["code"] for reason in record.get("reasons", [])}
    for candidate in [record.get("best"), *record.get("candidates", [])]:
        if isinstance(candidate, dict):
            for reason in candidate.get("reasons", []) or []:
                codes.add(reason["code"])
    return sorted(codes)


def build_diagnostics(context: dict, contracts_doc: dict, v2_rows: list[dict],
                      v3_rows: list[dict]) -> dict:
    from bpc_hybrid.s3_action_matching_v3 import match_policy

    v2_index = {(row["pair_id"], row["side"]): row for row in v2_rows}
    v3_index = {(row["pair_id"], row["side"]): row for row in v3_rows}
    changes, new_errors, fixed_errors = [], [], []
    for key in sorted(v2_index):
        old, new = v2_index[key], v3_index[key]
        old_status, new_status = status_of(old), status_of(new)
        check = new["target_check"]
        records = match_records(new["raw"][check], check)
        tiers = sorted({record.get("match_tier") for record in records if record.get("match_tier")})
        reasons = sorted({code for record in records for code in match_reason_codes(record)})
        entry = {
            "item_id": new["item_id"], "pair_id": key[0], "side": key[1],
            "check_type": check, "expected": expected_of(new),
            "v2_status": old_status, "v3_status": new_status,
            "v3_match_tiers": tiers, "v3_reason_codes": reasons,
            "v3_tier_reasons": sorted({record.get("tier_reason") for record in records
                                       if record.get("tier_reason")}),
            "change": ("unchanged" if old_status == new_status else
                       "corrected" if is_correct(new) else
                       "regressed" if is_correct(old) else
                       "changed_but_still_incorrect"),
        }
        changes.append(entry)
        if is_correct(old) and not is_correct(new):
            new_errors.append(entry)
        if not is_correct(old) and is_correct(new):
            fixed_errors.append(entry)

    focus = []
    for item_id in FOCUS_ITEMS:
        pair_id, side = item_id.split("::")
        row = v3_index[(pair_id, side)]
        check = row["target_check"]
        contract = next(c for c in contracts_doc["contracts"] if c["contract_id"] == pair_id)
        old = v2_index[(pair_id, side)]
        records = match_records(row["raw"][check], check)
        best = next((record for record in records if record.get("best")), records[0] if records else {})
        candidates = best.get("candidates", [])
        checked_ids = sorted({best.get("best", {}).get("activity_id"),
                              *[candidate["activity_id"] for candidate in candidates]} - {None})
        focus.append({
            "item_id": item_id,
            "check_type": check,
            "contract_requirement": contract["requirement"],
            "target_activity_name": contract["target_activity_name"],
            "target_activity_id": contract["target_activity_id"],
            "v2_status": status_of(old),
            "v3_status": status_of(row),
            "v3_tier": sorted({record.get("match_tier") for record in records
                               if record.get("match_tier")}),
            "v3_tier_reason": sorted({record.get("tier_reason") for record in records
                                      if record.get("tier_reason")}),
            "v3_reason_codes": sorted({code for record in records
                                       for code in match_reason_codes(record)}),
            "checked_activity_ids": checked_ids,
            "candidate_evidence": [
                {"activity_id": candidate["activity_id"], "label": candidate["label"],
                 "predicate_agrees": candidate["predicate_agrees"],
                 "verdict": candidate["verdict"],
                 "raw_similarity": round(candidate["raw_similarity"], 4),
                 "reason_codes": [reason["code"] for reason in candidate["reasons"]]}
                for candidate in candidates],
        })

    return {
        "schema_version": "s3_action_matching_v3_diagnostics@1.0.0",
        "run_id": RUN_ID,
        "method": {"id": V3_METHOD, "scope": "action representation and candidate matching only"},
        "representation_policy": match_policy(),
        "policy_frozen_before_panel_run": True,
        "definitions": {
            "correct_positive": "variant side judged violation",
            "correct_control": "original side judged satisfied",
            "new_errors": "v2 correct and v3 not correct",
            "fixed_errors": "v2 not correct and v3 correct",
        },
        "change_summary": dict(Counter(entry["change"] for entry in changes)),
        "v2_to_v3_item_changes": changes,
        "new_errors": new_errors,
        "fixed_errors": fixed_errors,
        "focus_items": focus,
        "counter_examples": run_counter_examples(context),
        "contract_interpretation": contract_interpretation(),
        "reference": "per-candidate evidence lives once in predictions.jsonl; this file refers "
                     "to items by item_id and repeats only decision-level codes",
    }


def run_counter_examples(context: dict) -> list[dict]:
    """Evaluate the fixed independent counter-examples with the same checker."""
    from types import SimpleNamespace
    scorer = context["v3"]
    results = []
    for case in COUNTER_EXAMPLES:
        activities = [{"id": f"x{i}", "name": name}
                      for i, name in enumerate(case["candidates"])]
        model = SimpleNamespace(actions=activities, record={"lanes": []},
                                action_actor_names={a["id"]: ["Clerk"] for a in activities},
                                business_objects=[], actors=["Clerk"],
                                is_reachable=lambda source, target: False)
        match = scorer.action_match(case["requirement"], model)
        codes = sorted({reason["code"] for reason in match.get("best", {}).get("reasons", [])})
        results.append({
            "name": case["name"], "requirement": case["requirement"],
            "candidates": case["candidates"], "mapped": match["mapped"],
            "match_tier": match.get("match_tier"), "reason": match["reason"],
            "reason_codes": codes,
            "expected_mapped": case["expected_mapped"],
            "expected_reasons": case["expected_reasons"],
            "as_expected": (match["mapped"] == case["expected_mapped"]
                            and set(case["expected_reasons"]) <= set(codes)),
        })
    return results


def contract_interpretation() -> dict:
    """Which missing_action definition the frozen panel actually encodes."""
    contracts = read_json(CONTRACTS_FILE)
    panel = read_json(PANEL)
    variant = next(v for v in panel["variants"] if v["variant_id"] == "syn_missing_action_06")
    return {
        "question": "does the frozen panel require the specified structured activity to be "
                    "present (A), or the absence of any activity achieving an equivalent "
                    "business effect (B)?",
        "evidence": {
            "contracts_locked.requirement_derivation.missing_action":
                contracts["requirement_derivation"]["missing_action"],
            "panel_mutation_type": variant["mutation_type"],
            "panel_expected_violation": variant["expected_violation"],
            "panel_removed_activity_id": variant["mutation_config"]["diff"]["removed_activity_id"],
            "panel_removed_activity_name": variant["mutation_config"]["diff"]["removed_activity_name"],
        },
        "finding": "the frozen contract defines the requirement as the original activity's own "
                   "label and records the expectation from the removal of that activity, i.e. "
                   "definition A; equivalence of business effect (B) is not defined anywhere in "
                   "the frozen panel, contract or evaluator",
        "decision": "definition not switched; the panel, the requirement and the denominator stay "
                    "unchanged, and the undecidable item stays unknown and counts as a miss",
        "minimum_question_for_coordinator":
            "should syn_missing_action_06::variant be judged under definition A (the specified "
            "scoped action is absent) or under definition B (a broader activity with an "
            "equivalent effect may satisfy it)?",
    }


# ---------------------------------------------------------------------------
# Manifest and verification
# ---------------------------------------------------------------------------


def input_paths() -> list[str]:
    panel = read_json(PANEL)
    paths = [PANEL.relative_to(ROOT).as_posix(),
             "configs/stage1_structural_s11_s14.json",
             SUN_CONFIG.relative_to(ROOT).as_posix()]
    paths += sorted({v["source_bpmn"] for v in panel["variants"]})
    paths += sorted({v["variant_bpmn"] for v in panel["variants"]})
    return paths


def implementation_paths() -> list[str]:
    return [
        "src/bpc_hybrid/s3_action_matching_v3.py",
        "src/bpc_hybrid/s3_action_matching_v2.py",
        "src/bpc_hybrid/s3_evidence_checks_v1.py",
        "src/bpc_hybrid/sun_stage3/sun_scorer.py",
        "src/bpc_hybrid/sun_stage3/sun_model.py",
        "src/bpc_hybrid/winter_stage3/winter_similarity.py",
        "src/bpc_hybrid/stage1_process.py",
        "scripts/run_s3_action_matching_v3.py",
        "scripts/run_s3_action_matching_v2.py",
        "scripts/run_s3_paired_mechanism_v1.py",
        "tests/test_s3_action_matching_v3.py",
    ]


def build_manifest(metrics: dict, diagnostics: dict, started: str, runtime: float) -> dict:
    return {
        "schema_version": "s3_action_matching_v3_manifest@1.0.0",
        "run_id": RUN_ID,
        "started_utc": started,
        "runtime_seconds": round(runtime, 3),
        "git_commit_before_checkpoint": git(["rev-parse", "HEAD"]),
        "declarations": {
            "development_only": True, "synthetic": True, "human_gold": False,
            "formal_oracle": False, "semantic_mapping_evaluated": False,
            "modification_scope": "action representation and candidate matching only",
            "new_llm_api_calls": 0,
            "frozen_panel_reused_not_reselected": True,
            "denominator_unchanged": True,
            "measurement_set_note": "the panel is a fixed development regression surface; this "
                                    "is not an independent generalisation result and not a "
                                    "formal legal-rule Stage 3 experiment",
        },
        "hash_conventions": {
            "artifacts": "UTF-8, LF; written with an explicit newline so committed bytes equal "
                         "working-tree bytes",
            "sha256_raw_working_tree": "SHA-256 over the raw bytes on disk; the binding used by "
                                       "--check / --replay",
            "scope": "only this run's new files are pinned to text eol=lf; no frozen source file "
                     "and no directory-wide attribute is changed",
        },
        "inputs": {path: V1.file_binding(path) for path in input_paths()},
        "contracts": {
            "path": CONTRACTS_FILE.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(CONTRACTS_FILE),
            "mode": "reused_frozen_contracts_not_regenerated",
            "fixed_variants": read_json(CONTRACTS_FILE)["counts"]["fixed_variants"],
            "valid_contracts": read_json(CONTRACTS_FILE)["counts"]["valid_contracts"],
            "unresolved": read_json(CONTRACTS_FILE)["counts"]["unresolved"],
        },
        "source_predictions": {
            "sun_2024_frozen": {"path": SOURCE_PREDICTIONS.relative_to(ROOT).as_posix(),
                                "sha256": sha256_file(SOURCE_PREDICTIONS),
                                "mode": "reused_verified_predictions"},
            "evidence_checks_v2_action_matching": {
                "path": V2_PREDICTIONS.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(V2_PREDICTIONS),
                "manifest": V2_MANIFEST.relative_to(ROOT).as_posix(),
                "manifest_sha256": sha256_file(V2_MANIFEST),
                "mode": "reused_verified_predictions"},
        },
        "configuration": {
            "thresholds": {k: float(read_json(SUN_CONFIG)["method"]["thresholds"][k])
                           for k in ("tau", "gamma", "theta")},
            "threshold_source": SUN_CONFIG.relative_to(ROOT).as_posix(),
            "similarity_backend": "winter_stage3.winter_similarity.WinterSimilarity",
            "nlp_model": "en_core_web_sm",
            "denominator_policy": "inherited from the previous round (see metrics.json)",
            "shared_evaluator_adapter": metrics["shared_evaluator_adapter"],
        },
        "implementation": {path: V1.file_binding(path) for path in implementation_paths()},
        "results": {
            "predictions": {"path": PREDICTIONS_FILE.relative_to(ROOT).as_posix(),
                            "sha256": sha256_file(PREDICTIONS_FILE),
                            "rows": len(read_jsonl(PREDICTIONS_FILE))},
            "metrics": {"path": METRICS_FILE.relative_to(ROOT).as_posix(),
                        "sha256": sha256_file(METRICS_FILE)},
            "diagnostics": {"path": DIAGNOSTICS_FILE.relative_to(ROOT).as_posix(),
                            "sha256": sha256_file(DIAGNOSTICS_FILE)},
        },
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "safety": {
            "sun_scorer_modified": False, "evidence_checks_v1_modified": False,
            "action_matching_v2_modified": False, "executor_check_modified": False,
            "order_check_modified": False, "unknown_aggregation_modified": False,
            "metric_logic_modified": False, "thresholds_changed": False,
            "similarity_backend_changed": False, "nlp_model_changed": False,
            "contract_changed": False, "expected_labels_changed": False,
            "gold_read": False, "gold_modified": False, "legacy_labels_modified": False,
            "original_bpmn_modified": False, "frozen_variants_modified": False,
            "old_predictions_modified": False, "old_reports_modified": False,
            "network_calls": 0, "llm_api_calls": 0,
        },
    }


def verify_manifest() -> dict:
    manifest = read_json(MANIFEST_FILE)
    mismatched = []
    for section in ("inputs", "implementation"):
        for rel, binding in manifest[section].items():
            if sha256_file(ROOT / rel) != binding["sha256_raw_working_tree"]:
                mismatched.append(f"{section}:{rel}")
    if sha256_file(CONTRACTS_FILE) != manifest["contracts"]["sha256"]:
        mismatched.append("contracts")
    for key, entry in manifest["source_predictions"].items():
        if sha256_file(ROOT / entry["path"]) != entry["sha256"]:
            mismatched.append(f"source:{key}")
    for key in ("predictions", "metrics", "diagnostics"):
        entry = manifest["results"][key]
        if sha256_file(ROOT / entry["path"]) != entry["sha256"]:
            mismatched.append(f"results:{key}")
    if mismatched:
        raise RuntimeError("hash mismatch: " + ", ".join(sorted(set(mismatched))))

    contracts = read_json(CONTRACTS_FILE)
    predictions = read_jsonl(PREDICTIONS_FILE)
    metrics = read_json(METRICS_FILE)
    diagnostics = read_json(DIAGNOSTICS_FILE)
    if len(predictions) != 2 * contracts["counts"]["valid_contracts"]:
        raise RuntimeError("v3 prediction count must be 2 x valid contracts")
    if {row["checker"] for row in predictions} != {V3_METHOD}:
        raise RuntimeError("v3 predictions must carry the v3 method id only")
    if not all(metrics["shared_evaluator_adapter"]
               ["faithfulness_check_against_stored_metrics"].values()):
        raise RuntimeError("the shared evaluator adapter does not reproduce the stored metrics")
    recomputed = build_metrics(contracts, predictions)
    if json.loads(json.dumps(recomputed, sort_keys=True)) != json.loads(
            json.dumps(metrics, sort_keys=True)):
        raise RuntimeError("metrics are not reproducible from the stored predictions")
    return {"contracts": contracts, "predictions": predictions, "metrics": metrics,
            "diagnostics": diagnostics}


def replay_payload() -> dict:
    contracts = read_json(CONTRACTS_FILE)
    context = prepare_context()
    rows = build_v3_predictions(context, contracts)
    v2_rows = read_jsonl(V2_PREDICTIONS)
    as_json = lambda value: json.loads(json.dumps(value, sort_keys=True))  # noqa: E731
    return {
        "predictions": as_json(rows),
        "stored_predictions": as_json(read_jsonl(PREDICTIONS_FILE)),
        "metrics": as_json(build_metrics(contracts, rows)),
        "stored_metrics": as_json(read_json(METRICS_FILE)),
        "diagnostics": as_json(build_diagnostics(context, contracts, v2_rows, rows)),
        "stored_diagnostics": as_json(read_json(DIAGNOSTICS_FILE)),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def write_outputs(rows: list[dict], metrics: dict, diagnostics: dict,
                  started: str, runtime: float) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with PREDICTIONS_FILE.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    METRICS_FILE.write_bytes((json.dumps(metrics, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    DIAGNOSTICS_FILE.write_bytes((json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    MANIFEST_FILE.write_bytes((json.dumps(build_manifest(metrics, diagnostics, started, runtime),
                                          ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()

    if args.check or args.replay:
        verify_manifest()
        if args.replay:
            payload = replay_payload()
            for key in ("predictions", "metrics", "diagnostics"):
                if payload[key] != payload[f"stored_{key}"]:
                    raise RuntimeError(f"{key} replay mismatch")
        print("S3 ACTION MATCHING V3 VERIFIED")
        return 0

    if OUT_DIR.exists() and any(OUT_DIR.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing run directory: {OUT_DIR}")
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    contracts = read_json(CONTRACTS_FILE)
    context = prepare_context()
    rows = build_v3_predictions(context, contracts)
    v2_rows = read_jsonl(V2_PREDICTIONS)
    metrics = build_metrics(contracts, rows)
    diagnostics = build_diagnostics(context, contracts, v2_rows, rows)
    write_outputs(rows, metrics, diagnostics, started, time.time() - t0)
    verify_manifest()
    print(json.dumps({
        "run_id": RUN_ID,
        "rows": len(rows),
        "valid_contracts": contracts["counts"]["valid_contracts"],
        "macro_f1": metrics["macro_f1"],
        "total_unknown": metrics["total_unknown"],
        "change_summary": diagnostics["change_summary"],
        "counter_examples_ok": all(case["as_expected"] for case in diagnostics["counter_examples"]),
        "focus_status": {item["item_id"]: item["v3_status"] for item in diagnostics["focus_items"]},
        "llm_api_calls": 0,
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
