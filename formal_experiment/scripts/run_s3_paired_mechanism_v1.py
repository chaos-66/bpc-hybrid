# -*- coding: utf-8 -*-
"""S3 paired controlled mechanism experiment (development, synthetic, zero API).

Question: under a controlled condition where the local requirement is already
explicit and its action text is literally the BPMN activity label, can a Stage 3
checker tell a *satisfied local requirement* (original process) from a *single
targeted error* (frozen controlled-error variant), for each of the three check
types?

Design (fixed before any checker ran):

* 30 frozen variants from
  ``data/development/stage3_synth/synthetic_controlled_error_extension_v1.json``
  (10 missing_action / 10 incorrect_actor / 10 out_of_order), bound to the frozen
  GDPR-7 corpus.  Each variant is paired with the *original* process it was
  mutated from, so the experiment has 30 pairs == 60 local check instances.  The
  instances come from the same frozen source corpus (6 of the 7 processes are
  actually mutated); they are NOT 60 independent processes.
* Per pair, a "local synthetic requirement" is derived from ORIGINAL structure
  plus frozen target metadata only, written and locked *before* inference:
    1. missing_action  -> the original target activity label is the required action;
    2. incorrect_actor -> required action as above, required actor = the activity's
       explicit named lane, else its pool; a conflict or ambiguity is reported and
       the contract is left unresolved (never guessed);
    3. out_of_order    -> the two activities named in the frozen mutation record,
       in the direction that holds in the ORIGINAL process; both endpoints use the
       real original labels, and the variant is verified to break that relation.
  These are local synthetic specifications defined by the original process.  They
  are NOT human GDPR legal rules, NOT legal Gold and NOT legal-rule extraction.
* Two checkers, identical inputs, identical configuration, identical evaluator:
    A. ``sun_2024``           - the frozen Sun reconstruction (``SunScorer``);
    B. ``evidence_checks_v1`` - the committed development checker (``EvidenceChecks``).
* Every checker computes all three signals per (requirement, process model) and the
  evaluator reads the pre-specified target signal.  This is a *designated-type local
  check*, not free three-way classification and not discovery of unknown types.
* Frozen Sun can return a numeric ``0`` together with an empty denominator; the
  read-only adapter turns exactly that combination into ``unknown``, records the raw
  return value and the fixed conversion reason.  Unknown is never a correct
  satisfaction: a positive (variant) unknown counts as a miss, a control (original)
  unknown is not counted as a correct rejection.

Only the requirement block is handed to the checkers.  Mutation type, expected
violation, original/variant identity and mutation prose never enter prediction.

Zero LLM/API calls; no network; no human Gold is read or modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

RUN_ID = "s3_paired_mechanism_v1"
SCHEMA = "s3_paired_mechanism@1.0.0"
OUT_DIR = ROOT / "outputs/development" / RUN_ID

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v1.json"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
SUN_CONFIG = ROOT / "configs/sun_stage3_development_v1.json"

CHECK_TYPES = ("missing_action", "incorrect_actor", "out_of_order")
CHECKERS = ("sun_2024_frozen", "evidence_checks_v1")

CONTRACTS_FILE = OUT_DIR / "contracts_locked.json"
PREDICTIONS_FILE = OUT_DIR / "predictions.jsonl"
METRICS_FILE = OUT_DIR / "metrics.json"
MANIFEST_FILE = OUT_DIR / "manifest.json"
REPORT_FILE = OUT_DIR / "REPORT.md"

# Fixed, label-independent normalisation contract (locked before inference).
NORMALISATION = {
    "rule": "a checker result is a violation only from an explicit positive signal "
            "with a non-empty denominator; an empty denominator or an explicitly "
            "unobservable result is unknown, never 'satisfied'",
    "sun_zero_score_empty_denominator": "numeric score 0.0 with denominator 0 "
                                        "-> unknown (raw score retained)",
    "evidence_native_status": "EvidenceChecks already returns "
                              "satisfied/violation/unknown; its status is used as-is",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode("utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git(args: list[str]) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout.strip()


# ---------------------------------------------------------------------------
# Phase 1 - contract construction (no checker, no NLP, no label)
# ---------------------------------------------------------------------------


def _named_lanes_owning(record: dict, activity_id: str) -> list[str]:
    names = []
    for lane in record.get("lanes", []):
        if activity_id in lane.get("flow_node_refs", []) and (lane.get("name") or "").strip():
            names.append(lane["name"].strip())
    return list(dict.fromkeys(names))


def _pool_names(record: dict) -> list[str]:
    return list(dict.fromkeys((p.get("name") or "").strip() for p in record.get("pools", [])
                              if (p.get("name") or "").strip()))


def resolve_required_actor(record: dict, activity_id: str) -> dict:
    """Explicit named lane first; otherwise the pool. Conflicts are reported."""
    lanes = _named_lanes_owning(record, activity_id)
    if len(lanes) == 1:
        return {"owner": lanes[0], "policy": "explicit_named_lane", "candidates": lanes,
                "status": "resolved"}
    if len(lanes) > 1:
        return {"owner": None, "policy": "explicit_named_lane", "candidates": lanes,
                "status": "conflicting_lanes"}
    pools = _pool_names(record)
    if len(pools) == 1:
        return {"owner": pools[0], "policy": "containing_pool", "candidates": pools,
                "status": "resolved"}
    if not pools:
        return {"owner": None, "policy": "containing_pool", "candidates": [],
                "status": "no_actor_label"}
    return {"owner": None, "policy": "containing_pool", "candidates": pools,
            "status": "ambiguous_pools"}


def _activity_names(record: dict) -> dict[str, str]:
    return {a["id"]: a["name"] for a in record.get("activities", [])}


def _owner_label_set(record: dict, activity_id: str) -> list[str]:
    """Structural owner label set (lanes union pools); used only for the
    checker-independent 'did the mutation change ownership' check."""
    owners = _named_lanes_owning(record, activity_id)
    owners += _pool_names(record)
    return sorted(dict.fromkeys(owners))


def build_contracts(panel: dict, records: dict[str, dict],
                    reachability: dict[str, dict[str, set[str]]]) -> dict:
    contracts: list[dict] = []
    for variant in sorted(panel["variants"], key=lambda v: (v["mutation_type"], v["variant_id"])):
        vid = variant["variant_id"]
        check = variant["mutation_type"]
        rec_o = records[variant["source_bpmn"]]
        rec_v = records[variant["variant_bpmn"]]
        names_o, names_v = _activity_names(rec_o), _activity_names(rec_v)
        tid = variant["target_activity_id"]
        target_name = names_o.get(tid)
        contract = {
            "contract_id": f"{vid}",
            "variant_id": vid,
            "check_type": check,
            "process_id": variant["process_id"],
            "rule_id": variant["rule_id"],
            "source_bpmn": variant["source_bpmn"],
            "source_bpmn_sha256": sha256_file(ROOT / variant["source_bpmn"]),
            "variant_bpmn": variant["variant_bpmn"],
            "variant_bpmn_sha256": sha256_file(ROOT / variant["variant_bpmn"]),
            "target_activity_id": tid,
            "target_activity_name": target_name,
            "requirement": None,
            "evaluation": None,
            "binding_evidence": {},
            "validation": [],
            "status": "invalid",
            "reason": None,
        }
        if not target_name or not target_name.strip():
            contract["reason"] = "target_activity_missing_or_unnamed_in_original"
            contracts.append(contract)
            continue
        if check == "missing_action":
            _contract_missing_action(contract, variant, rec_o, rec_v, tid, target_name, names_v)
        elif check == "incorrect_actor":
            _contract_incorrect_actor(contract, rec_o, rec_v, tid, target_name, names_o, names_v)
        elif check == "out_of_order":
            _contract_out_of_order(contract, variant, rec_o, rec_v, tid,
                                   names_o, names_v, reachability)
        else:  # pragma: no cover - frozen panel has exactly three types
            contract["reason"] = f"unsupported_check_type:{check}"
        contracts.append(contract)

    valid = [c for c in contracts if c["status"] == "valid"]
    per_type = {}
    for check in CHECK_TYPES:
        group = [c for c in contracts if c["check_type"] == check]
        per_type[check] = {
            "fixed_variants": len(group),
            "valid_contracts": sum(c["status"] == "valid" for c in group),
            "unresolved": sum(c["status"] != "valid" for c in group),
        }
    summary = {
        "schema_version": "s3_paired_mechanism_contracts@1.0.0",
        "run_id": RUN_ID,
        "panel_id": panel["panel_id"],
        "panel_sha256": sha256_file(PANEL),
        "locked_before_inference": True,
        "lock_statement": (
            "Contracts were derived from ORIGINAL process structure and frozen target "
            "metadata only, written and hashed before any checker ran. No checker "
            "output, prediction, mutation prose or expected label entered derivation."
        ),
        "requirement_derivation": {
            "missing_action": "required action = original target activity label (verbatim)",
            "incorrect_actor": "required action as above; required actor = explicit named "
                               "lane owning the activity in the original, else the "
                               "containing pool; conflicts/ambiguity -> unresolved",
            "out_of_order": "the two activities named in the frozen mutation record, in the "
                            "direction that holds in the ORIGINAL; endpoints use the real "
                            "original labels; the variant is verified to break the relation",
        },
        "source_corpus": {
            "bpmn_dir": panel["originals"]["bpmn_dir"],
            "bpmn_file_count": panel["originals"]["bpmn_file_count"],
            "processes_mutated": sorted({v["process_id"] for v in panel["variants"]}),
            "processes_mutated_count": len({v["process_id"] for v in panel["variants"]}),
            "note": "the frozen corpus holds 7 GDPR-7 processes; 6 of them are mutated by "
                    "the 30 variants, so the 60 check instances are not 60 independent "
                    "processes",
        },
        "normalisation": NORMALISATION,
        "counts": {
            "fixed_variants": len(contracts),
            "valid_contracts": len(valid),
            "unresolved": len(contracts) - len(valid),
            "pairs": len(valid),
            "control_instances": len(valid),
            "variant_instances": len(valid),
            "total_check_instances": 2 * len(valid),
        },
        "per_type": per_type,
        "unresolved": [
            {"contract_id": c["contract_id"], "check_type": c["check_type"], "reason": c["reason"]}
            for c in contracts if c["status"] != "valid"
        ],
        "contracts": contracts,
    }
    return summary


def _contract_missing_action(contract, variant, rec_o, rec_v, tid, target_name, names_v) -> None:
    duplicates = [aid for aid, name in names_v.items() if name == target_name]
    removed = tid not in names_v
    contract["requirement"] = {
        "actions": [target_name], "actors": [], "actor_action_pairs": [], "order_relations": [],
    }
    contract["evaluation"] = {"target_check": "missing_action",
                              "expected_original": "satisfied",
                              "expected_variant": "violation"}
    contract["binding_evidence"] = {
        "target_activity_present_in_original": True,
        "target_activity_removed_in_variant": removed,
        "same_name_activity_ids_in_variant": duplicates,
        "variant_validation_status": variant["validation_checks"]["status"],
    }
    contract["validation"] = [
        {"check": "target_named_in_original", "ok": bool(target_name.strip())},
        {"check": "target_activity_absent_in_variant", "ok": removed},
        {"check": "no_same_name_activity_left_in_variant", "ok": not duplicates},
    ]
    if removed and not duplicates:
        contract["status"] = "valid"
    else:
        contract["reason"] = ("target_activity_not_removed_in_variant" if not removed
                              else "same_name_activity_still_present_in_variant")


def _contract_incorrect_actor(contract, rec_o, rec_v, tid, target_name, names_o, names_v) -> None:
    resolved = resolve_required_actor(rec_o, tid)
    owners_o = _owner_label_set(rec_o, tid)
    owners_v = _owner_label_set(rec_v, tid) if tid in names_v else []
    effective = owners_o != owners_v
    contract["requirement"] = {
        "actions": [target_name],
        "actors": [resolved["owner"]] if resolved["owner"] else [],
        "actor_action_pairs": ([{"actor": resolved["owner"], "action": target_name}]
                               if resolved["owner"] else []),
        "order_relations": [],
    }
    contract["evaluation"] = {"target_check": "incorrect_actor",
                              "expected_original": "satisfied",
                              "expected_variant": "violation"}
    contract["binding_evidence"] = {
        "actor_resolution_policy": resolved["policy"],
        "actor_resolution_status": resolved["status"],
        "actor_candidates": resolved["candidates"],
        "required_actor": resolved["owner"],
        "owner_label_set_original": owners_o,
        "owner_label_set_variant": owners_v,
        "ownership_changed_by_variant": effective,
        "target_activity_present_in_variant": tid in names_v,
    }
    contract["validation"] = [
        {"check": "target_activity_present_in_variant", "ok": tid in names_v},
        {"check": "required_actor_resolved_uniquely", "ok": resolved["status"] == "resolved"},
        {"check": "ownership_changed_by_variant", "ok": effective},
    ]
    if resolved["status"] != "resolved":
        contract["reason"] = f"actor_not_uniquely_resolved:{resolved['status']}"
    elif tid not in names_v:
        contract["reason"] = "target_activity_missing_in_variant"
    elif not effective:
        contract["reason"] = "variant_does_not_change_ownership"
    else:
        contract["status"] = "valid"


def _contract_out_of_order(contract, variant, rec_o, rec_v, tid,
                           names_o, names_v, reachability) -> None:
    pair = list(variant["mutation_config"]["diff"]["pair"])
    pid = variant["process_id"]
    reach_o = reachability[variant["source_bpmn"]]
    reach_v = reachability[variant["variant_bpmn"]]
    a, b = pair
    name_a, name_b = names_o.get(a), names_o.get(b)
    fwd_o, bwd_o = b in reach_o.get(a, set()), a in reach_o.get(b, set())
    fwd_v, bwd_v = b in reach_v.get(a, set()), a in reach_v.get(b, set())
    names_stable = (names_v.get(a) == name_a and names_v.get(b) == name_b
                    and name_a and name_b)
    unique_direction = fwd_o and not bwd_o
    broken = not (fwd_v and not bwd_v)
    if unique_direction:
        before, after = name_a, name_b
        before_id, after_id = a, b
    elif bwd_o and not fwd_o:
        before, after = name_b, name_a
        before_id, after_id = b, a
    else:
        before = after = None
        before_id = after_id = None
    contract["requirement"] = {
        "actions": [], "actors": [], "actor_action_pairs": [],
        "order_relations": [[before, after]] if before else [],
    }
    contract["evaluation"] = {"target_check": "out_of_order",
                              "expected_original": "satisfied",
                              "expected_variant": "violation"}
    contract["binding_evidence"] = {
        "pair_ids": pair,
        "pair_names_original": [name_a, name_b],
        "original_forward_reachable_a_to_b": fwd_o,
        "original_backward_reachable_b_to_a": bwd_o,
        "variant_forward_reachable_a_to_b": fwd_v,
        "variant_backward_reachable_b_to_a": bwd_v,
        "direction_unique_in_original": unique_direction or (bwd_o and not fwd_o),
        "relation_broken_in_variant": broken,
        "names_stable_across_pair": bool(names_stable),
        "required_before_id": before_id,
        "required_after_id": after_id,
        "described_pair_before": before,
        "described_pair_after": after,
    }
    contract["validation"] = [
        {"check": "both_endpoints_named_in_original", "ok": bool(name_a and name_b)},
        {"check": "direction_unique_in_original", "ok": bool(unique_direction or (bwd_o and not fwd_o))},
        {"check": "endpoint_names_unchanged_in_variant", "ok": bool(names_stable)},
        {"check": "relation_broken_in_variant", "ok": broken},
    ]
    if not (name_a and name_b):
        contract["reason"] = "order_endpoint_unnamed_in_original"
    elif not (unique_direction or (bwd_o and not fwd_o)):
        contract["reason"] = "order_direction_not_unique_in_original"
    elif not names_stable:
        contract["reason"] = "order_endpoint_names_changed_in_variant"
    elif not broken:
        contract["reason"] = "variant_does_not_break_the_relation"
    else:
        contract["status"] = "valid"


# ---------------------------------------------------------------------------
# Phase 2 - inference (requirement + process model only)
# ---------------------------------------------------------------------------


def requirement_block(contract: dict) -> dict:
    """The only thing a checker may see besides the process model."""
    return contract["requirement"]


def run_signals(scorer, requirement: dict, model) -> dict:
    """Compute all three signals from the requirement and the process model."""
    actions = list(requirement["actions"])
    actors = list(requirement["actors"])
    pairs = list(requirement["actor_action_pairs"])
    relations = [tuple(x) for x in requirement["order_relations"]]
    return {
        "missing_action": scorer.missing_action(actions, model),
        "incorrect_actor": scorer.incorrect_actor(actions, actors, model, pairs),
        "out_of_order": scorer.out_of_order(relations, actions, model),
    }


def normalize_sun(check_type: str, raw: dict) -> dict:
    """Fixed, label-free conversion of a frozen-Sun result to a tri-state."""
    denominator = int(raw.get("denominator") or 0)
    score = raw.get("score")
    if raw.get("observable") is False:
        return {"status": "unknown", "reason": raw.get("reason") or "reported_unobservable",
                "raw_score": score, "denominator": denominator,
                "conversion": "explicitly_unobservable"}
    if score is None:
        return {"status": "unknown", "reason": raw.get("reason") or "score_none",
                "raw_score": None, "denominator": denominator,
                "conversion": "score_is_none"}
    if denominator == 0:
        return {"status": "unknown", "reason": "zero_score_with_empty_denominator",
                "raw_score": score, "denominator": 0,
                "conversion": "sun_zero_score_empty_denominator"}
    return {"status": "violation" if score > 0 else "satisfied", "reason": None,
            "raw_score": score, "denominator": denominator, "conversion": "none"}


def normalize_evidence(check_type: str, raw: dict) -> dict:
    """EvidenceChecks already returns a tri-state; keep it, guard the denominator."""
    status = raw.get("status")
    denominator = int(raw.get("denominator") or 0)
    if status not in {"satisfied", "violation", "unknown"}:
        return {"status": "unknown", "reason": "unrecognised_checker_status",
                "raw_score": raw.get("score"), "denominator": denominator,
                "conversion": "unrecognised_status"}
    if status == "satisfied" and denominator == 0:
        return {"status": "unknown", "reason": "satisfied_with_empty_denominator",
                "raw_score": raw.get("score"), "denominator": 0,
                "conversion": "empty_denominator_guard"}
    return {"status": status, "reason": raw.get("reason"),
            "raw_score": raw.get("score"), "denominator": denominator,
            "conversion": "none"}


NORMALIZERS = {"sun_2024_frozen": normalize_sun, "evidence_checks_v1": normalize_evidence}


def build_predictions(contracts_doc: dict, models: dict[str, Any],
                      scorers: dict[str, Any]) -> list[dict]:
    rows: list[dict] = []
    for contract in contracts_doc["contracts"]:
        requirement = requirement_block(contract)
        if contract["status"] != "valid":
            continue
        requirement_sha = canonical_sha256(requirement)
        for side, bpmn_key in (("original", contract["source_bpmn"]),
                               ("variant", contract["variant_bpmn"])):
            model = models[bpmn_key]
            for checker in CHECKERS:
                raw = run_signals(scorers[checker], requirement, model)
                rows.append({
                    "schema_version": "s3_paired_mechanism_prediction@1.0.0",
                    "run_id": RUN_ID,
                    "item_id": f"{contract['contract_id']}::{side}",
                    "pair_id": contract["contract_id"],
                    "variant_id": contract["variant_id"],
                    "side": side,
                    "checker": checker,
                    "target_check": contract["check_type"],
                    "process_id": contract["process_id"],
                    "model_bpmn": bpmn_key,
                    "model_bpmn_sha256": sha256_file(ROOT / bpmn_key),
                    "requirement_sha256": requirement_sha,
                    "shared_binding": {
                        "thresholds": scorers["config"]["thresholds"],
                        "nlp_model": scorers["config"]["nlp_model"],
                        "nlp_version": scorers["config"]["nlp_version"],
                        "similarity_backend": "winter_stage3.winter_similarity.WinterSimilarity",
                        "stage1_structural_contract": "configs/stage1_structural_s11_s14.json",
                    },
                    "raw": raw,
                    "signals": {check: NORMALIZERS[checker](check, raw[check]) for check in CHECK_TYPES},
                })
    return rows


# ---------------------------------------------------------------------------
# Phase 3 - evaluation (recomputable from stored rows only)
# ---------------------------------------------------------------------------


def evaluate(predictions: list[dict], contracts_doc: dict) -> dict:
    valid = {c["contract_id"]: c for c in contracts_doc["contracts"] if c["status"] == "valid"}
    result: dict[str, Any] = {
        "schema_version": "s3_paired_mechanism_metrics@1.0.0",
        "run_id": RUN_ID,
        "denominator_policy": {
            "positive": "variant side of a valid contract; expected violation",
            "control": "original side of a valid contract; expected satisfied",
            "tp": "positive judged violation",
            "fn": "positive not judged violation (satisfied or unknown; positive unknown counts as a miss)",
            "fp": "control judged violation (false alarm)",
            "tn": "control judged satisfied",
            "control_unknown": "not counted as tn and not counted as fp",
            "precision": "tp/(tp+fp)",
            "recall": "tp/(tp+fn) == tp/valid_positive_instances",
            "control_satisfied_rate": "tn/valid_control_instances",
            "paired_success": "control satisfied AND positive violation for the same pair",
        },
        "checkers": {},
    }
    for checker in CHECKERS:
        per_type: dict[str, Any] = {}
        for check in CHECK_TYPES:
            rows = [p for p in predictions
                    if p["checker"] == checker and p["target_check"] == check
                    and p["pair_id"] in valid]
            positive = {p["pair_id"]: p for p in rows if p["side"] == "variant"}
            control = {p["pair_id"]: p for p in rows if p["side"] == "original"}
            tp = sum(p["signals"][check]["status"] == "violation" for p in positive.values())
            fp = sum(p["signals"][check]["status"] == "violation" for p in control.values())
            tn = sum(p["signals"][check]["status"] == "satisfied" for p in control.values())
            fn = len(positive) - tp
            pos_unknown = sum(p["signals"][check]["status"] == "unknown" for p in positive.values())
            ctl_unknown = sum(p["signals"][check]["status"] == "unknown" for p in control.values())
            paired = sum(control[k]["signals"][check]["status"] == "satisfied"
                         and positive[k]["signals"][check]["status"] == "violation"
                         for k in positive if k in control)
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            per_type[check] = {
                "valid_pairs": len(positive),
                "control_instances": len(control),
                "variant_instances": len(positive),
                "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                "positive_unknown": pos_unknown,
                "control_unknown": ctl_unknown,
                "precision": precision, "recall": recall,
                "f1": (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0,
                "control_satisfied": tn,
                "control_satisfied_rate": (tn / len(control)) if control else 0.0,
                "paired_success": paired,
                "paired_success_rate": (paired / len(positive)) if positive else 0.0,
                "per_pair": {k: {"control": control[k]["signals"][check]["status"],
                                 "variant": positive[k]["signals"][check]["status"]}
                             for k in sorted(positive) if k in control},
            }
        macro = sum(per_type[c]["f1"] for c in CHECK_TYPES) / len(CHECK_TYPES)
        total_unknown = sum(per_type[c]["positive_unknown"] + per_type[c]["control_unknown"]
                            for c in CHECK_TYPES)
        result["checkers"][checker] = {
            "per_type": per_type,
            "macro_f1": macro,
            "total_unknown": total_unknown,
            "valid_contracts": len(valid),
            "valid_contract_coverage": len(valid) / contracts_doc["counts"]["fixed_variants"],
            "paired_success_total": sum(per_type[c]["paired_success"] for c in CHECK_TYPES),
            "control_satisfied_total": sum(per_type[c]["control_satisfied"] for c in CHECK_TYPES),
        }
    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def select_cases(contracts_doc: dict) -> list[dict]:
    """Fixed rule: per check type, the first valid contract by sorted variant_id."""
    cases = []
    for check in CHECK_TYPES:
        candidates = sorted((c for c in contracts_doc["contracts"]
                             if c["check_type"] == check and c["status"] == "valid"),
                            key=lambda c: c["variant_id"])
        if candidates:
            cases.append(candidates[0])
    return cases


def build_report(contracts_doc: dict, predictions: list[dict], metrics: dict,
                 panel: dict) -> str:
    variants = {v["variant_id"]: v for v in panel["variants"]}
    lines = [
        "# Stage 3 三类检查的成对受控机制实验（development / synthetic）",
        "",
        "本报告是开发阶段的受控机制实验，不是正式 GDPR Oracle，不是人工规则与自动规则的优劣比较，"
        "也没有评价法条与流程图之间的语义映射难度。",
        "",
        "## 1. 实验问题",
        "",
        "在目标要求已经明确、动作名称直接取自 BPMN 标签的受控条件下，检查器能否区分"
        "“原图局部要求满足”与“单一目标错误”？",
        "",
        "## 2. 设计",
        "",
        f"- 固定面板：{contracts_doc['counts']['fixed_variants']} 个冻结变体"
        "（missing_action 10 / incorrect_actor 10 / out_of_order 10），未重新选样、未删除失败项。",
        f"- 有效契约：{contracts_doc['counts']['valid_contracts']}；未解决：{contracts_doc['counts']['unresolved']}；"
        f"有效配对：{contracts_doc['counts']['pairs']}；检查实例：{contracts_doc['counts']['total_check_instances']}"
        "（每条有效契约 = 1 个原图对照 + 1 个错误变体）。",
        f"- 来源流程：冻结 GDPR-7 语料 {contracts_doc['source_corpus']['bpmn_file_count']} 个流程，"
        f"其中 {contracts_doc['source_corpus']['processes_mutated_count']} 个被实际变异"
        "；这些实例不是 60 个独立流程。",
        "- 两个检查器：`sun_2024_frozen`（冻结 Sun 重建）与 `evidence_checks_v1`（已提交开发检查器），"
        "使用完全相同的局部合成要求、原图／变体、Stage 1 解析、NLP 模型、tau/gamma/theta 与评价口径。",
        "- 局部合成规范由原图结构与冻结目标元数据确定，在推断前生成并锁定；动作名称直接取自原图，"
        "因此本实验基本排除了法条与流程图之间的语义映射难度，只验证检查机制。",
        "",
        "## 3. 指标口径",
        "",
        "- 正例 = 有效契约的变体侧（预期违规）；对照 = 有效契约的原图侧（预期满足）。",
        "- 正例 unknown 计入漏检（FN）；对照 unknown 不计为正确拒报（TN），也不计为误报（FP）。",
        "- 冻结 Sun 的“数值 0 + 分母 0”由只读适配层转为 unknown，并保留原始返回值。",
        "- 全部数字由 `predictions.jsonl` 的逐项状态重算，不做手工汇总。",
        "",
        "## 4. 结果",
        "",
    ]
    for checker in CHECKERS:
        block = metrics["checkers"][checker]
        lines += [f"### 4.{CHECKERS.index(checker) + 1} `{checker}`", "",
                  "| 检查类型 | 有效对 | TP | FP | FN | TN | 正例unknown | 对照unknown | "
                  "Precision | Recall | F1 | 对照满足/有效对照 | 成对成功/有效对 |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
        for check in CHECK_TYPES:
            m = block["per_type"][check]
            lines.append(
                f"| {check} | {m['valid_pairs']} | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} | "
                f"{m['positive_unknown']} | {m['control_unknown']} | {m['precision']:.4f} | "
                f"{m['recall']:.4f} | {m['f1']:.4f} | "
                f"{m['control_satisfied']}/{m['control_instances']} | "
                f"{m['paired_success']}/{m['valid_pairs']} |")
        lines += ["",
                  f"- macro-F1 = {block['macro_f1']:.4f}；总 unknown = {block['total_unknown']}；"
                  f"有效契约覆盖 = {block['valid_contracts']}/{contracts_doc['counts']['fixed_variants']}"
                  f"（{block['valid_contract_coverage']:.4f}）。", ""]
    lines += ["## 5. 案例（固定规则：每类按 variant_id 排序取第一个契约有效者）", ""]
    for case in select_cases(contracts_doc):
        check = case["check_type"]
        variant = variants[case["variant_id"]]
        lines += [f"### 5.{CHECK_TYPES.index(check) + 1} `{case['variant_id']}`（{check}）", "",
                  f"- 原图局部要求：{_requirement_text(case)}",
                  f"- 变体改动：{_mutation_text(variant)}"]
        for checker in CHECKERS:
            row_c = _row(predictions, case["contract_id"], "original", checker)
            row_v = _row(predictions, case["contract_id"], "variant", checker)
            lines.append(
                f"- `{checker}`：原图 → {row_c['signals'][check]['status']}"
                f"（{_reason(row_c['signals'][check])}）；变体 → {row_v['signals'][check]['status']}"
                f"（{_reason(row_v['signals'][check])}）")
        lines += [f"- 解释：{_case_note(predictions, case)}", ""]
    lines += ["## 6. 边界与未解决项", "",
              "- 局部合成规范由原图定义，不是人工 GDPR 法律规则、不是法律 Gold、不是法条抽取结果。",
              "- 对照“满足”只表示本次指定的局部合成要求满足，不表示整个流程合法。",
              "- 动作名称直接取自原图，本实验未评价真实法条到流程的语义映射难度。",
              "- 旧 33 条人工标签的检查范围问题仍未解决，本实验不替代也不修改该评价面。",
              "- 零 LLM/API 调用；未修改人工 Gold、旧标签、原图、冻结变体、旧预测与旧报告。", ""]
    return "\n".join(lines) + "\n"


def _requirement_text(case: dict) -> str:
    req = case["requirement"]
    if case["check_type"] == "missing_action":
        return f"必须执行的动作 = “{req['actions'][0]}”"
    if case["check_type"] == "incorrect_actor":
        return f"动作 “{req['actions'][0]}” 的执行者必须是 “{req['actors'][0]}”"
    return f"“{req['order_relations'][0][0]}” 必须早于 “{req['order_relations'][0][1]}”"


def _mutation_text(variant: dict) -> str:
    diff = variant["mutation_config"]["diff"]
    kind = variant["mutation_type"]
    if kind == "missing_action":
        return (f"从流程中删除活动 {diff['removed_activity_name']!r}"
                f"（{diff['removed_activity_id']}）并用 bypass 边接通前后节点")
    if kind == "incorrect_actor":
        return (f"为目标活动注入 lane {diff['injected_lane_name']!r}"
                f"（{diff['target_lane_id']}），只改该活动归属")
    return (f"反转 {diff['pair']} 这对活动的先后关系（原路径 {diff['path_nodes']}）")


def _reason(signal: dict) -> str:
    return signal.get("reason") or "—"


def _row(predictions: list[dict], pair_id: str, side: str, checker: str) -> dict:
    for row in predictions:
        if row["pair_id"] == pair_id and row["side"] == side and row["checker"] == checker:
            return row
    raise KeyError(f"missing row {pair_id}/{side}/{checker}")


def _case_note(predictions: list[dict], case: dict) -> str:
    check = case["check_type"]
    states = []
    for checker in CHECKERS:
        c = _row(predictions, case["contract_id"], "original", checker)["signals"][check]["status"]
        v = _row(predictions, case["contract_id"], "variant", checker)["signals"][check]["status"]
        states.append((checker, c, v))
    both = all(c == "satisfied" and v == "violation" for _, c, v in states)
    if both:
        return "两个检查器都在原图上判为满足、在变体上判为违规，指定类型的局部机制成立。"
    return ("两个检查器在该对照上未同时给出“原图满足 + 变体违规”："
            + "；".join(f"{n} 原图={c} 变体={v}" for n, c, v in states) + "。")


# ---------------------------------------------------------------------------
# Manifest / verification
# ---------------------------------------------------------------------------


def file_binding(rel: str) -> dict:
    path = ROOT / rel
    raw = path.read_bytes()
    filtered = subprocess.run(["git", "hash-object", f"--path={rel}", str(path)],
                              cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    plain = subprocess.run(["git", "hash-object", "--no-filters", str(path)],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    return {
        "bytes": len(raw),
        "crlf_pairs": raw.count(b"\r\n"),
        "sha256_raw_working_tree": sha256_bytes(raw),
        "git_blob_sha1_raw": plain,
        "git_blob_sha1_after_clean_filter": filtered,
        "raw_bytes_equal_committed_bytes": plain == filtered,
    }


def implementation_paths() -> list[str]:
    return [
        "src/bpc_hybrid/s3_evidence_checks_v1.py",
        "src/bpc_hybrid/sun_stage3/sun_scorer.py",
        "src/bpc_hybrid/sun_stage3/sun_model.py",
        "src/bpc_hybrid/winter_stage3/winter_similarity.py",
        "src/bpc_hybrid/stage1_process.py",
        "scripts/run_s3_paired_mechanism_v1.py",
        "tests/test_s3_paired_mechanism_v1.py",
    ]


def build_manifest(contracts_doc: dict, predictions: list[dict], metrics: dict,
                   started: str, runtime: float) -> dict:
    panel = read_json(PANEL)
    inputs = [PANEL.relative_to(ROOT).as_posix(),
              STRUCTURAL_CONTRACT.relative_to(ROOT).as_posix(),
              SUN_CONFIG.relative_to(ROOT).as_posix()]
    inputs += sorted({v["source_bpmn"] for v in panel["variants"]})
    inputs += sorted({v["variant_bpmn"] for v in panel["variants"]})
    return {
        "schema_version": "s3_paired_mechanism_manifest@1.0.0",
        "run_id": RUN_ID,
        "started_utc": started,
        "runtime_seconds": round(runtime, 3),
        "git_commit_before_checkpoint": git(["rev-parse", "HEAD"]),
        "declarations": {
            "development_only": True, "synthetic": True, "human_gold": False,
            "formal_oracle": False, "semantic_mapping_evaluated": False,
            "new_llm_api_calls": 0,
        },
        "hash_conventions": {
            "sha256_raw_working_tree": "SHA-256 over the raw bytes on disk; this is the "
                                       "binding used by --check / --replay",
            "git_blob_sha1_raw": "git hash-object --no-filters (SHA-1 of the raw bytes)",
            "git_blob_sha1_after_clean_filter": "git hash-object --path=<rel> (SHA-1 after "
                                                "the repository's clean filter, i.e. the "
                                                "content that would be committed)",
            "raw_bytes_equal_committed_bytes": "true means the working-tree bytes survive "
                                               "checkout unchanged, so the raw SHA-256 stays "
                                               "valid after commit",
            "scope": "this run pins only its own new artifacts to text eol=lf; no frozen "
                     "source file and no directory-wide attribute was changed",
        },
        "inputs": {p: file_binding(p) for p in inputs},
        "variants": {v["variant_id"]: {
            "source_bpmn": v["source_bpmn"],
            "source_bpmn_sha256_recorded": v["source_bpmn_sha256"],
            "source_bpmn_sha256_now": sha256_file(ROOT / v["source_bpmn"]),
            "variant_bpmn": v["variant_bpmn"],
            "variant_bpmn_sha256_recorded": v["variant_bpmn_sha256"],
            "variant_bpmn_sha256_now": sha256_file(ROOT / v["variant_bpmn"]),
        } for v in panel["variants"]},
        "contracts": {"path": CONTRACTS_FILE.relative_to(ROOT).as_posix(),
                      "sha256": sha256_file(CONTRACTS_FILE),
                      "valid": contracts_doc["counts"]["valid_contracts"],
                      "unresolved": contracts_doc["counts"]["unresolved"]},
        "configuration": {
            "checkers": list(CHECKERS),
            "thresholds": {k: float(read_json(SUN_CONFIG)["method"]["thresholds"][k])
                           for k in ("tau", "gamma", "theta")},
            "threshold_keys": ["tau", "gamma", "theta"],
            "threshold_source": "configs/sun_stage3_development_v1.json",
            "nlp_model": "en_core_web_sm",
            "similarity_backend": "winter_stage3.winter_similarity.WinterSimilarity",
            "normalisation": NORMALISATION,
        },
        "implementation": {p: file_binding(p) for p in implementation_paths()},
        "results": {
            "predictions": {"path": PREDICTIONS_FILE.relative_to(ROOT).as_posix(),
                            "sha256": sha256_file(PREDICTIONS_FILE), "rows": len(predictions)},
            "metrics": {"path": METRICS_FILE.relative_to(ROOT).as_posix(),
                        "sha256": sha256_file(METRICS_FILE)},
            "report": {"path": REPORT_FILE.relative_to(ROOT).as_posix(),
                       "sha256": sha256_file(REPORT_FILE)},
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "safety": {
            "gold_read": False, "gold_modified": False, "old_results_modified": False,
            "frozen_variants_modified": False, "original_bpmn_modified": False,
            "network_calls": 0, "llm_api_calls": 0, "thresholds_changed": False,
            "checkers_modified": False,
        },
    }


def verify_manifest() -> dict:
    manifest = read_json(MANIFEST_FILE)
    missing = []
    for section in ("inputs", "implementation"):
        for rel, recorded in manifest[section].items():
            if sha256_file(ROOT / rel) != recorded["sha256_raw_working_tree"]:
                missing.append(f"{section}:{rel}")
    for key in ("predictions", "metrics", "report"):
        entry = manifest["results"][key]
        if sha256_file(ROOT / entry["path"]) != entry["sha256"]:
            missing.append(f"results:{key}")
    if sha256_file(CONTRACTS_FILE) != manifest["contracts"]["sha256"]:
        missing.append("contracts")
    if missing:
        raise RuntimeError("hash mismatch: " + ", ".join(sorted(set(missing))))
    contracts_doc = read_json(CONTRACTS_FILE)
    metrics = read_json(METRICS_FILE)
    rows = [json.loads(line) for line in PREDICTIONS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 2 * 2 * contracts_doc["counts"]["valid_contracts"]:
        raise RuntimeError("prediction row count does not match 2 sides x 2 checkers x valid pairs")
    recomputed = evaluate(rows, contracts_doc)
    if json.loads(json.dumps(recomputed, sort_keys=True)) != json.loads(json.dumps(metrics, sort_keys=True)):
        raise RuntimeError("metrics are not reproducible from the stored predictions")
    if metrics["checkers"]["sun_2024_frozen"]["valid_contracts"] != contracts_doc["counts"]["valid_contracts"]:
        raise RuntimeError("valid-contract coverage mismatch")
    return {"contracts": contracts_doc, "predictions": rows, "metrics": metrics}


def replay_payload(contracts_doc: dict) -> dict:
    """Recompute contracts and predictions from first principles."""
    panel = read_json(PANEL)
    records, reachability, models, scorers = prepare(panel)
    rebuilt_contracts = build_contracts(panel, records, reachability)
    rebuilt_rows = build_predictions(rebuilt_contracts, models, scorers)
    return {
        "contracts": json.loads(json.dumps(rebuilt_contracts, sort_keys=True)),
        "predictions": json.loads(json.dumps(rebuilt_rows, sort_keys=True)),
        "stored_contracts": json.loads(json.dumps(contracts_doc, sort_keys=True)),
        "stored_predictions": json.loads(json.dumps(
            [json.loads(line) for line in PREDICTIONS_FILE.read_text(encoding="utf-8").splitlines()
             if line.strip()], sort_keys=True)),
    }


# ---------------------------------------------------------------------------
# Preparation / CLI
# ---------------------------------------------------------------------------


def prepare(panel: dict):
    from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file
    from bpc_hybrid.sun_stage3.sun_model import SunProcessModel

    import spacy
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity

    structural = load_stage1_contract(STRUCTURAL_CONTRACT)
    nlp = spacy.load("en_core_web_sm")
    records: dict[str, dict] = {}
    reachability: dict[str, dict[str, set[str]]] = {}
    models: dict[str, Any] = {}
    for rel in sorted({v["source_bpmn"] for v in panel["variants"]} |
                      {v["variant_bpmn"] for v in panel["variants"]}):
        record = parse_bpmn_file(ROOT / rel, contract=structural)
        records[rel] = record
        reach: dict[str, set[str]] = {}
        for pair in record.get("control_flow", {}).get("reachable_pairs", []):
            reach.setdefault(pair["source_ref"], set()).add(pair["target_ref"])
        reachability[rel] = reach
        models[rel] = SunProcessModel(Path(rel).stem, record, nlp)
    config = read_json(SUN_CONFIG)
    thresholds = {k: float(config["method"]["thresholds"][k]) for k in ("tau", "gamma", "theta")}
    sim = WinterSimilarity(nlp)
    from bpc_hybrid.s3_evidence_checks_v1 import EvidenceChecks
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
    scorers = {
        "sun_2024_frozen": SunScorer(sim, thresholds["tau"], thresholds["gamma"],
                                     thresholds["theta"], nlp=nlp),
        "evidence_checks_v1": EvidenceChecks(sim, thresholds["tau"], thresholds["gamma"],
                                             thresholds["theta"], nlp=nlp),
        "config": {"thresholds": thresholds, "nlp_model": "en_core_web_sm",
                   "nlp_version": nlp.meta.get("version")},
    }
    return records, reachability, models, scorers


def write_outputs(contracts_doc: dict, predictions: list[dict], metrics: dict,
                  panel: dict, started: str, runtime: float) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CONTRACTS_FILE.write_bytes((json.dumps(contracts_doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    with PREDICTIONS_FILE.open("w", encoding="utf-8", newline="\n") as handle:
        for row in predictions:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    METRICS_FILE.write_bytes((json.dumps(metrics, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    REPORT_FILE.write_bytes(build_report(contracts_doc, predictions, metrics, panel).encode("utf-8"))
    MANIFEST_FILE.write_bytes((json.dumps(build_manifest(contracts_doc, predictions, metrics,
                                                         started, runtime),
                                          ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify stored artifacts and their bindings (no inference)")
    parser.add_argument("--replay", action="store_true",
                        help="recompute contracts and predictions and compare with the stored run")
    args = parser.parse_args()

    if args.check or args.replay:
        verified = verify_manifest()
        if args.replay:
            payload = replay_payload(verified["contracts"])
            if payload["contracts"] != payload["stored_contracts"]:
                raise RuntimeError("contract replay mismatch")
            if payload["predictions"] != payload["stored_predictions"]:
                raise RuntimeError("prediction replay mismatch")
        print("S3 PAIRED MECHANISM VERIFIED")
        return 0

    if OUT_DIR.exists() and any(OUT_DIR.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing run directory: {OUT_DIR}")
    started = datetime.now(timezone.utc).isoformat()
    import time
    t0 = time.time()
    panel = read_json(PANEL)
    records, reachability, models, scorers = prepare(panel)
    contracts_doc = build_contracts(panel, records, reachability)
    predictions = build_predictions(contracts_doc, models, scorers)
    metrics = evaluate(predictions, contracts_doc)
    write_outputs(contracts_doc, predictions, metrics, panel, started, time.time() - t0)
    verify_manifest()
    print(json.dumps({
        "run_id": RUN_ID,
        "valid_contracts": contracts_doc["counts"]["valid_contracts"],
        "unresolved": contracts_doc["counts"]["unresolved"],
        "check_instances": contracts_doc["counts"]["total_check_instances"],
        "macro_f1": {k: round(v["macro_f1"], 4) for k, v in metrics["checkers"].items()},
        "llm_api_calls": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
