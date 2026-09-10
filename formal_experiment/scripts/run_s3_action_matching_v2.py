# -*- coding: utf-8 -*-
"""S3 action-matching v2 measurement on the frozen paired mechanism panel.

Only the action matcher changes.  This runner reuses, unchanged:

* the frozen paired contracts (``s3_paired_mechanism_v1/contracts_locked.json``);
* the v1 parsing/models (``run_s3_paired_mechanism_v1.prepare``);
* the v1 signal driver (``run_signals``) and the v1 evidence-to-tristate
  adapter (``normalize_evidence``);
* the v1 metric code path (``evaluate``) through a small explicit adapter,
  documented below, whose faithfulness is checked against the stored v1 metrics
  for both reused methods.

Comparison columns:

* ``sun_2024_frozen``                  - reused verified predictions
* ``evidence_checks_v1``               - reused verified predictions
* ``evidence_checks_v2_action_matching`` - 56 newly generated predictions

Nothing else is re-run and no source prediction is rewritten.  The v2 checker
receives the *same* requirement block, the *same* parsed process models, the
*same* similarity backend object, the *same* NLP object and the *same* frozen
thresholds as v1; only ``action_match`` differs.

Denominator policy is inherited verbatim from the previous round: a positive
(variant) unknown counts as a miss, a control (original) unknown is neither a
correct rejection nor a false alarm.

Zero LLM/API calls; no human Gold, legacy label, BPMN, frozen variant, old
prediction or old report is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

RUN_ID = "s3_action_matching_v2"
SCHEMA = "s3_action_matching_v2@1.0.0"

V1_DIR = ROOT / "outputs/development/s3_paired_mechanism_v1"
CONTRACTS_FILE = V1_DIR / "contracts_locked.json"
V1_PREDICTIONS_FILE = V1_DIR / "predictions.jsonl"
V1_METRICS_FILE = V1_DIR / "metrics.json"
V1_MANIFEST_FILE = V1_DIR / "manifest.json"
V1_RUNNER = ROOT / "scripts/run_s3_paired_mechanism_v1.py"

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v1.json"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
SUN_CONFIG = ROOT / "configs/sun_stage3_development_v1.json"

OUT_DIR = ROOT / "outputs/development" / RUN_ID
PREDICTIONS_FILE = OUT_DIR / "predictions.jsonl"
METRICS_FILE = OUT_DIR / "metrics.json"
DIAGNOSTICS_FILE = OUT_DIR / "diagnostics.json"
MANIFEST_FILE = OUT_DIR / "manifest.json"

V2_METHOD = "evidence_checks_v2_action_matching"
REUSED_METHODS = ("sun_2024_frozen", "evidence_checks_v1")
METHODS = REUSED_METHODS + (V2_METHOD,)
CHECK_TYPES = ("missing_action", "incorrect_actor", "out_of_order")

# In-memory canonicalisation for the frozen metric function only.  ``evaluate``
# in the previous round iterates a fixed method-name tuple, so each method is
# scored through the same code path by handing it one method's rows under a
# canonical in-memory label; stored rows keep their true method id and no
# prediction identity is rewritten.  Faithfulness is checked against the stored
# previous-round metrics for both reused methods.
CANONICAL_ALIAS = "evidence_checks_v1"

EXPECTED_STATUS = {"original": "satisfied", "variant": "violation"}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def git(args: list[str]) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout.strip()


def load_v1_runner():
    spec = importlib.util.spec_from_file_location("paired_mechanism_v1_runner", V1_RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["paired_mechanism_v1_runner"] = module
    spec.loader.exec_module(module)
    return module


V1 = load_v1_runner()


# ---------------------------------------------------------------------------
# Context and predictions
# ---------------------------------------------------------------------------


def prepare_context() -> dict:
    """Reuse the v1 parsing/models; build the v2 scorer on the same objects."""
    from bpc_hybrid.s3_action_matching_v2 import EvidenceChecksV2

    panel = read_json(PANEL)
    records, reachability, models, scorers = V1.prepare(panel)
    base = scorers["evidence_checks_v1"]
    v2 = EvidenceChecksV2(base.sim, base.tau, base.gamma, base.theta, nlp=base.nlp)
    return {
        "panel": panel,
        "records": records,
        "reachability": reachability,
        "models": models,
        "v2": v2,
        "shared_binding": {
            "thresholds": {"tau": float(base.tau), "gamma": float(base.gamma),
                           "theta": float(base.theta)},
            "nlp_model": "en_core_web_sm",
            "nlp_version": base.nlp.meta.get("version"),
            "similarity_backend": "winter_stage3.winter_similarity.WinterSimilarity",
            "stage1_structural_contract": "configs/stage1_structural_s11_s14.json",
            "shared_backend_object_with_v1": True,
            "shared_nlp_object_with_v1": True,
        },
    }


def build_v2_predictions(context: dict, contracts_doc: dict) -> list[dict]:
    """56 new rows: 28 valid contracts x 2 sides x 1 method.

    The only checker input is the contract's requirement block plus the parsed
    process model.  Evaluation metadata, mutation prose and the frozen target id
    never enter this path.
    """
    rows: list[dict] = []
    scorer = context["v2"]
    for contract in contracts_doc["contracts"]:
        if contract["status"] != "valid":
            continue
        requirement = contract["requirement"]
        requirement_sha = V1.canonical_sha256(requirement)
        for side, key in (("original", "source_bpmn"), ("variant", "variant_bpmn")):
            bpmn = contract[key]
            model = context["models"][bpmn]
            raw = V1.run_signals(scorer, requirement, model)
            rows.append({
                "schema_version": "s3_action_matching_v2_prediction@1.0.0",
                "run_id": RUN_ID,
                "item_id": f"{contract['contract_id']}::{side}",
                "pair_id": contract["contract_id"],
                "variant_id": contract["variant_id"],
                "side": side,
                "checker": V2_METHOD,
                "method_scope": "action matching only",
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
# Metrics through the shared evaluator
# ---------------------------------------------------------------------------


def metrics_for_method(rows: list[dict], contracts_doc: dict) -> dict:
    """Score one method through the previous round's evaluator (unchanged)."""
    canonical = [{**row, "checker": CANONICAL_ALIAS} for row in rows]
    doc = {"counts": contracts_doc["counts"], "contracts": contracts_doc["contracts"]}
    return V1.evaluate(canonical, doc)["checkers"][CANONICAL_ALIAS]


def build_metrics(contracts_doc: dict, v2_rows: list[dict]) -> dict:
    v1_stored = read_json(V1_METRICS_FILE)
    reused_rows = [row for row in read_jsonl(V1_PREDICTIONS_FILE)
                   if row["checker"] in REUSED_METHODS]
    methods: dict[str, Any] = {}
    faithfulness: dict[str, bool] = {}
    for method in REUSED_METHODS:
        rows = [row for row in reused_rows if row["checker"] == method]
        block = metrics_for_method(rows, contracts_doc)
        methods[method] = block
        faithfulness[method] = json.loads(json.dumps(block, sort_keys=True)) == json.loads(
            json.dumps(v1_stored["checkers"][method], sort_keys=True))
    methods[V2_METHOD] = metrics_for_method(v2_rows, contracts_doc)

    result = {
        "schema_version": "s3_action_matching_v2_metrics@1.0.0",
        "run_id": RUN_ID,
        "denominator_policy": v1_stored["denominator_policy"],
        "denominator_policy_source": {
            "path": V1_METRICS_FILE.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(V1_METRICS_FILE),
            "note": "inherited verbatim; the evaluator code path is unchanged",
        },
        "methods": methods,
        "macro_f1": {method: methods[method]["macro_f1"] for method in METHODS},
        "total_unknown": {method: methods[method]["total_unknown"] for method in METHODS},
        "sources": {
            "sun_2024_frozen": {
                "mode": "reused_verified_predictions",
                "path": V1_PREDICTIONS_FILE.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(V1_PREDICTIONS_FILE),
                "item_count": 56,
            },
            "evidence_checks_v1": {
                "mode": "reused_verified_predictions",
                "path": V1_PREDICTIONS_FILE.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(V1_PREDICTIONS_FILE),
                "item_count": 56,
            },
            V2_METHOD: {
                "mode": "newly_generated",
                "path": PREDICTIONS_FILE.relative_to(ROOT).as_posix(),
                "item_count": len(v2_rows),
            },
        },
        "shared_evaluator_adapter": {
            "description": "each method's rows are scored through the previous round's "
                           "evaluate() by canonicalising the in-memory method label; stored "
                           "rows keep their true method id and no metric formula is reimplemented",
            "canonical_alias": CANONICAL_ALIAS,
            "faithfulness_check_against_stored_v1_metrics": faithfulness,
        },
    }
    for method in REUSED_METHODS:
        result["sources"][method]["items"] = reused_items(reused_rows, method)
    return result


def reused_items(rows: list[dict], method: str) -> list[dict]:
    """Reused per-item statuses only.

    The reused candidate evidence stays in the referenced previous-round file
    (``sources[method].path`` plus ``sha256``); this file never duplicates it.
    """
    items = []
    for row in sorted((r for r in rows if r["checker"] == method),
                      key=lambda r: (r["pair_id"], r["side"])):
        items.append({
            "item_id": row["item_id"],
            "pair_id": row["pair_id"],
            "side": row["side"],
            "checker": method,
            "target_check": row["target_check"],
            "status": status_of(row),
            "reason": row["signals"][row["target_check"]]["reason"],
            "signals": {check: row["signals"][check]["status"] for check in CHECK_TYPES},
        })
    return items


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def status_of(row: dict) -> str:
    return row["signals"][row["target_check"]]["status"]


def match_records(raw: dict, check: str) -> list[dict]:
    """Every per-requirement match record inside a raw check result.

    ``missing_action``/``incorrect_actor`` carry one match per required action,
    ``out_of_order`` one per order endpoint.  Each record exposes the match tier,
    the raw similarity, the object evidence and the accept/reject decision.
    """
    if check == "out_of_order":
        records = []
        for detail in raw.get("details", []):
            for key in ("before", "after"):
                if isinstance(detail.get(key), dict):
                    records.append(detail[key])
        return records
    return [detail["match"] for detail in raw.get("details", [])
            if isinstance(detail.get("match"), dict)]


def tiers_of(raw: dict, check: str) -> list[str]:
    return sorted({record.get("match_tier") for record in match_records(raw, check)
                   if record.get("match_tier")})


def tier_reasons_of(raw: dict, check: str) -> list[str]:
    return sorted({record.get("tier_reason") for record in match_records(raw, check)
                   if record.get("tier_reason")})


def expected_of(row: dict) -> str:
    return EXPECTED_STATUS[row["side"]]


def is_correct(row: dict) -> bool:
    return status_of(row) == expected_of(row)


def build_diagnostics(contracts_doc: dict, v1_rows: list[dict], v2_rows: list[dict]) -> dict:
    from bpc_hybrid.s3_action_matching_v2 import match_policy

    v1_index = {(r["pair_id"], r["side"]): r for r in v1_rows if r["checker"] == "evidence_checks_v1"}
    v2_index = {(r["pair_id"], r["side"]): r for r in v2_rows}
    changes = []
    transitions = Counter()
    corrections = []
    regressions = []
    residual: dict[str, list[str]] = {}
    tiers_counter = Counter()
    for key in sorted(v1_index):
        old, new = v1_index[key], v2_index[key]
        old_status, new_status = status_of(old), status_of(new)
        expected = expected_of(old)
        raw = new["raw"][new["target_check"]]
        tiers = tiers_of(raw, new["target_check"])
        tier_reasons = tier_reasons_of(raw, new["target_check"])
        for tier in tiers:
            tiers_counter[f"{new['target_check']}:{tier}"] += 1
        if old_status == new_status:
            change = "unchanged"
        elif is_correct(new):
            change = "corrected"
        elif is_correct(old):
            change = "regressed"
        else:
            change = "changed_but_still_incorrect"
        changes.append({
            "item_id": new["item_id"],
            "pair_id": key[0],
            "side": key[1],
            "check_type": new["target_check"],
            "expected": expected,
            "v1_status": old_status,
            "v2_status": new_status,
            "change": change,
            "v2_match_tiers": tiers,
            "v2_tier_reasons": tier_reasons,
            "v1_reason": old["signals"][old["target_check"]]["reason"],
            "v2_reason": new["signals"][new["target_check"]]["reason"],
        })
        if old_status == "unknown":
            if is_correct(new):
                transitions["v1_unknown_now_correct"] += 1
            elif new_status == "unknown":
                transitions["v1_unknown_still_unknown"] += 1
            else:
                transitions["v1_unknown_now_wrong"] += 1
        if new["side"] == "variant" and old_status == "satisfied":
            if new_status == "violation":
                corrections.append(new["item_id"])
            else:
                residual.setdefault("positive_target_absent_but_still_not_flagged",
                                    []).append(new["item_id"])
        if is_correct(old) and not is_correct(new):
            regressions.append(new["item_id"])
        if not is_correct(new):
            reason = _residual_cause(new, tiers)
            residual.setdefault(reason, []).append(new["item_id"])
    for key in ("v1_unknown_now_correct", "v1_unknown_now_wrong", "v1_unknown_still_unknown"):
        transitions.setdefault(key, 0)
    transitions["v1_unknown_total"] = (transitions["v1_unknown_now_correct"]
                                       + transitions["v1_unknown_now_wrong"]
                                       + transitions["v1_unknown_still_unknown"])
    return {
        "schema_version": "s3_action_matching_v2_diagnostics@1.0.0",
        "run_id": RUN_ID,
        "method": {"id": V2_METHOD, "scope": "action matching only"},
        "matching_policy": match_policy(),
        "policy_frozen_before_panel_scoring": True,
        "definitions": {
            "correct_positive": "variant side judged violation",
            "correct_control": "original side judged satisfied",
            "v1_unknown_transitions": "of the 19 v1 unknown items, how v2 judges them now",
            "match_tier": "decision tier per requirement/endpoint, recorded in predictions.jsonl",
        },
        "v1_v2_item_changes": changes,
        "change_summary": dict(Counter(entry["change"] for entry in changes)),
        "unknown_transitions": dict(transitions),
        "missed_positive_corrections": {
            "v1_satisfied_on_positive_now_violation": corrections,
            "v1_satisfied_on_positive_still_not_flagged": residual.get(
                "positive_target_absent_but_still_not_flagged", []),
        },
        "regressions": regressions,
        "residual_failures_grouped_by_cause": {k: v for k, v in sorted(residual.items())},
        "v2_match_tier_counts": dict(sorted(tiers_counter.items())),
        "reference": "per-item candidate evidence lives once in predictions.jsonl; this file "
                     "refers to items by item_id only",
    }


def _residual_cause(row: dict, tiers: list[str]) -> str:
    status = status_of(row)
    tier_set = set(tiers)
    if row["side"] == "variant" and status == "satisfied":
        if "exact_label" in tier_set:
            return "variant_target_still_present_as_exact_label"
        return "variant_positive_not_detected_by_matching_tier"
    if row["side"] == "original" and status == "violation":
        return "control_flagged_as_violation_by_matching_tier"
    if status == "unknown":
        if "partial_object_overlap" in tier_set:
            return "under_determined_partial_object_overlap"
        if "exact_label_tie" in tier_set:
            return "under_determined_identical_labels"
        if "frozen_similarity_tie" in tier_set:
            return "under_determined_equal_similarity"
        if "predicate_object_agreement_tie" in tier_set:
            return "under_determined_equivalent_candidates"
        if "similarity_below_gamma" in tier_set:
            return "no_candidate_above_gamma"
        return "unknown_with_tiers:" + ",".join(sorted(tier_set))
    return "incorrect_with_tiers:" + ",".join(sorted(tier_set))


# ---------------------------------------------------------------------------
# Manifest and verification
# ---------------------------------------------------------------------------


def input_paths() -> list[str]:
    panel = read_json(PANEL)
    paths = [PANEL.relative_to(ROOT).as_posix(),
             STRUCTURAL_CONTRACT.relative_to(ROOT).as_posix(),
             SUN_CONFIG.relative_to(ROOT).as_posix()]
    paths += sorted({v["source_bpmn"] for v in panel["variants"]})
    paths += sorted({v["variant_bpmn"] for v in panel["variants"]})
    return paths


def implementation_paths() -> list[str]:
    return [
        "src/bpc_hybrid/s3_action_matching_v2.py",
        "src/bpc_hybrid/s3_evidence_checks_v1.py",
        "src/bpc_hybrid/sun_stage3/sun_scorer.py",
        "src/bpc_hybrid/sun_stage3/sun_model.py",
        "src/bpc_hybrid/winter_stage3/winter_similarity.py",
        "src/bpc_hybrid/stage1_process.py",
        "scripts/run_s3_action_matching_v2.py",
        "scripts/run_s3_paired_mechanism_v1.py",
        "tests/test_s3_action_matching_v2.py",
    ]


def build_manifest(metrics: dict, diagnostics: dict, started: str, runtime: float) -> dict:
    return {
        "schema_version": "s3_action_matching_v2_manifest@1.0.0",
        "run_id": RUN_ID,
        "started_utc": started,
        "runtime_seconds": round(runtime, 3),
        "git_commit_before_checkpoint": git(["rev-parse", "HEAD"]),
        "declarations": {
            "development_only": True,
            "synthetic": True,
            "human_gold": False,
            "formal_oracle": False,
            "modification_scope": "action matching only",
            "semantic_mapping_evaluated": False,
            "new_llm_api_calls": 0,
            "frozen_panel_reused_not_reselected": True,
            "measurement_set_note": "the panel was used to locate the defect, so these numbers "
                                    "are a fixed-development-set regression result, not an "
                                    "independent generalisation result",
        },
        "hash_conventions": {
            "artifacts": "UTF-8, LF; written with an explicit newline so the committed bytes "
                         "equal the working-tree bytes",
            "sha256_raw_working_tree": "SHA-256 over the raw bytes on disk; the binding used by "
                                       "--check / --replay",
            "git_blob_sha1_raw": "git hash-object --no-filters",
            "git_blob_sha1_after_clean_filter": "git hash-object --path=<rel> (content that "
                                                "would be committed)",
            "raw_bytes_equal_committed_bytes": "true means the raw hash stays valid after checkout",
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
            "unresolved_contract_ids": [entry["contract_id"]
                                        for entry in read_json(CONTRACTS_FILE)["unresolved"]],
        },
        "source_predictions": {
            "path": V1_PREDICTIONS_FILE.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(V1_PREDICTIONS_FILE),
            "manifest": V1_MANIFEST_FILE.relative_to(ROOT).as_posix(),
            "manifest_sha256": sha256_file(V1_MANIFEST_FILE),
            "mode": "reused_verified_predictions",
            "methods_reused": list(REUSED_METHODS),
        },
        "configuration": {
            "thresholds": {k: float(read_json(SUN_CONFIG)["method"]["thresholds"][k])
                           for k in ("tau", "gamma", "theta")},
            "threshold_source": "configs/sun_stage3_development_v1.json",
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
            "sun_scorer_modified": False,
            "evidence_checks_v1_modified": False,
            "executor_check_modified": False,
            "order_check_modified": False,
            "unknown_aggregation_modified": False,
            "metric_logic_modified": False,
            "thresholds_changed": False,
            "similarity_backend_changed": False,
            "nlp_model_changed": False,
            "gold_read": False,
            "gold_modified": False,
            "legacy_labels_modified": False,
            "original_bpmn_modified": False,
            "frozen_variants_modified": False,
            "old_predictions_modified": False,
            "old_reports_modified": False,
            "network_calls": 0,
            "llm_api_calls": 0,
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
    if sha256_file(V1_PREDICTIONS_FILE) != manifest["source_predictions"]["sha256"]:
        mismatched.append("source_predictions")
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
        raise RuntimeError("v2 prediction count must be 2 x valid contracts")
    if {row["checker"] for row in predictions} != {V2_METHOD}:
        raise RuntimeError("v2 predictions must carry the v2 method id only")
    if not all(metrics["shared_evaluator_adapter"]
               ["faithfulness_check_against_stored_v1_metrics"].values()):
        raise RuntimeError("shared evaluator adapter does not reproduce the stored v1 metrics")
    recomputed = build_metrics(contracts, predictions)
    if json.loads(json.dumps(recomputed, sort_keys=True)) != json.loads(
            json.dumps(metrics, sort_keys=True)):
        raise RuntimeError("metrics are not reproducible from the stored predictions")
    return {"contracts": contracts, "predictions": predictions, "metrics": metrics,
            "diagnostics": diagnostics}


def replay_payload() -> dict:
    """Recompute v2 predictions, metrics and diagnostics from first principles."""
    contracts = read_json(CONTRACTS_FILE)
    context = prepare_context()
    rows = build_v2_predictions(context, contracts)
    v1_rows = read_jsonl(V1_PREDICTIONS_FILE)
    metrics = build_metrics(contracts, rows)
    diagnostics = build_diagnostics(contracts, v1_rows, rows)
    as_json = lambda value: json.loads(json.dumps(value, sort_keys=True))  # noqa: E731
    return {
        "predictions": as_json(rows),
        "stored_predictions": as_json(read_jsonl(PREDICTIONS_FILE)),
        "metrics": as_json(metrics),
        "stored_metrics": as_json(read_json(METRICS_FILE)),
        "diagnostics": as_json(diagnostics),
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
        verified = verify_manifest()
        if args.replay:
            payload = replay_payload()
            for key in ("predictions", "metrics", "diagnostics"):
                if payload[key] != payload[f"stored_{key}"]:
                    raise RuntimeError(f"{key} replay mismatch")
        print("S3 ACTION MATCHING V2 VERIFIED")
        return 0

    if OUT_DIR.exists() and any(OUT_DIR.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing run directory: {OUT_DIR}")
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    contracts = read_json(CONTRACTS_FILE)
    context = prepare_context()
    rows = build_v2_predictions(context, contracts)
    v1_rows = read_jsonl(V1_PREDICTIONS_FILE)
    metrics = build_metrics(contracts, rows)
    diagnostics = build_diagnostics(contracts, v1_rows, rows)
    write_outputs(rows, metrics, diagnostics, started, time.time() - t0)
    verify_manifest()
    print(json.dumps({
        "run_id": RUN_ID,
        "rows": len(rows),
        "valid_contracts": contracts["counts"]["valid_contracts"],
        "unresolved": contracts["counts"]["unresolved"],
        "macro_f1": metrics["macro_f1"],
        "total_unknown": metrics["total_unknown"],
        "change_summary": diagnostics["change_summary"],
        "unknown_transitions": diagnostics["unknown_transitions"],
        "llm_api_calls": 0,
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
