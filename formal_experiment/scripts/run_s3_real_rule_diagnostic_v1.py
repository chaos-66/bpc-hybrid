# -*- coding: utf-8 -*-
"""S3.7 real-rule diagnostic: frozen Sun vs the current v3 checker on the 7 BPMNs.

What this runner actually does, in this order:

1. converts the **confirmed human Gold Rule Records** (74 sentences / 92 clauses,
   obligation modality only, per the frozen policy) mechanically into checker
   records with the existing converter, and applies the existing runtime
   projection of the three confirmed temporal sentences;
2. builds the 7 original BPMN process models once (no synthetic variant is
   loaded);
3. runs **both** checkers - the frozen Sun reconstruction and the current
   ``EvidenceChecksV3`` - on every one of the 33 pre-existing inference items,
   for that item's pre-specified ``check_type`` only, and writes
   ``predictions.jsonl`` (66 rows) plus the de-duplicated
   ``mapping_evidence.jsonl`` **before any label is read**;
4. only afterwards reads the old violation Gold and the user's acknowledged
   local opinion, and produces the 33-item scope review and the summary.

Boundaries: this is a development diagnostic on real legal-rule input.  It is not
a formal S3.7 Oracle promotion, not a Gold publication, and it does not change
the legacy labels, the contracts, the Gold or the checkers.  Old label
TP/FP/FN/F1 are reported only inside ``legacy_label_diagnostic`` with
``scope_unresolved=true`` and ``performance_claim_ready=false``.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

RUN_ID = "s3_real_rule_diagnostic_v1"

BPMN_DIR = ROOT / "data/input/stage1_stage3/gdpr7"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
SUN_CONFIG = ROOT / "configs/sun_stage3_development_v1.json"
HUMAN_CAPSULE = ROOT / "data/predictions/gdpr7_human_rule_record_v1/predictions.json"
GOLD_RULE_RECORDS = ROOT / "data/gold/stage3/gdpr7_gold_rule_records_v1.json"
STAGE2_INPUT = ROOT / "data/input/gdpr7_stage2_input_v1.json"
INFERENCE_PACK = ROOT / "data/development/human_review/stage3_gold_inference_v1.json"
VIOLATION_GOLD = ROOT / "data/gold/stage3/stage3_violation_gold_v1.json"
CASE_ACK = ROOT / "data/development/human_review/gdpr7_human_confirmed_v1/case_acknowledgement.json"
PAIRED_RUNNER = ROOT / "scripts/run_s3_paired_mechanism_v1.py"   # tri-state adapters

OUT_DIR = ROOT / "outputs/development" / RUN_ID
PREDICTIONS_FILE = OUT_DIR / "predictions.jsonl"
MAPPING_FILE = OUT_DIR / "mapping_evidence.jsonl"
SCOPE_FILE = OUT_DIR / "scope_review.json"
SUMMARY_FILE = OUT_DIR / "summary.json"
MANIFEST_FILE = OUT_DIR / "manifest.json"

SUN_METHOD = "sun_2024_frozen"
V3_METHOD = "evidence_checks_v3_action_structure"
METHODS = (SUN_METHOD, V3_METHOD)
CHECK_TYPES = ("missing_action", "incorrect_actor", "out_of_order")
INCLUDE_MODALITIES = ("obligation",)

MAPPING_CLASSES = (
    "mapped_unique",                       # 1 clear activity correspondence
    "expression_differs_unresolved",       # 2 different wording, no reliable correspondence
    "multiple_candidates_insufficient",    # 3 several candidates, evidence insufficient
    "structure_parse_insufficient",        # 4 nested action / object / role parsing insufficient
    "order_endpoint_not_an_activity",      # 5 order endpoint is an event/state, not an activity
    "rule_lacks_required_information",     # 6 rule lacks actor or order information
    "needs_condition_or_context",          # 7 needs conditions/context not present/consumed
    "evidence_supports_judgment",          # 8 current judgment is supported by the recorded evidence
)

QUESTION_GROUPS = {
    "G1_target_binding": {
        "question": "每一项检查的目标是哪个 clause/规范条目与哪个具体活动？",
        "why": "33 项只携带 rule_id（整条法条），没有目标句/规范片段/活动绑定，机器无法唯一确定检查对象",
    },
    "G2_original_or_variant": {
        "question": "每一项应在原图还是某个变体上检查？",
        "why": "33 项均未标注 original/variant，也未给出变体文件路径",
    },
    "G3_missing_cited_article": {
        "question": "证据引用的 Article 12 / Article 19 是否补齐为输入？",
        "why": "v018/v021/v030 的证据引用 Article 12、v033 引用 Article 19，而当前输入只有 article6/7/15/16/17/20/22/33/34",
    },
    "G4_confirmed_local_conflict": {
        "question": "v001/v002 的检查范围是否覆盖 Article 33 通知活动？",
        "why": "用户已确认的局部读图意见认为该通知活动存在且执行者正确，与这两项的旧正标签存在范围冲突",
    },
    "G5_no_negative_control": {
        "question": "是否为该表补齐合规/负例对照，或明确只作正例诊断？",
        "why": "33 项全部是正标签，没有合规对照，无法据此评估误报",
    },
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PAIRED = load_module("paired_mechanism_v1_runner", PAIRED_RUNNER)
normalize_sun = PAIRED.normalize_sun
normalize_evidence = PAIRED.normalize_evidence

from bpc_hybrid.s3_action_matching_v3 import EvidenceChecksV3  # noqa: E402
from bpc_hybrid.s3_evidence_checks_v1 import project_confirmed_temporal_notes  # noqa: E402
from bpc_hybrid.stage1_process import load_stage1_contract  # noqa: E402
from bpc_hybrid.sun_stage3.gdpr_capsule_converter import (  # noqa: E402
    build_rule_records, sentence_texts_by_sample,
)
from bpc_hybrid.sun_stage3.sun_model import build_sun_models  # noqa: E402
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def git(args: list[str]) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout.strip()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Phase 1 - inference (no label is read in this phase)
# ---------------------------------------------------------------------------


def build_rule_inputs() -> dict:
    capsule = read_json(HUMAN_CAPSULE)
    input_doc = read_json(STAGE2_INPUT)
    gold_rules = read_json(GOLD_RULE_RECORDS)
    inference = read_json(INFERENCE_PACK)
    texts = sentence_texts_by_sample(input_doc)
    rule_ids = sorted({item["rule_id"] for item in inference["violation_items"]})
    records, summary = build_rule_records(capsule, texts, rule_ids, INCLUDE_MODALITIES)
    projected, temporal = project_confirmed_temporal_notes(records, gold_rules)
    return {
        "capsule": capsule, "input_doc": input_doc, "gold_rules": gold_rules,
        "inference": inference, "texts": texts, "rule_ids": rule_ids,
        "records": projected, "conversion_summary": summary, "temporal": temporal,
    }


def build_scorers() -> dict:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    config = read_json(SUN_CONFIG)
    thresholds = {key: float(config["method"]["thresholds"][key])
                  for key in ("tau", "gamma", "theta")}
    sim = WinterSimilarity(nlp)
    return {
        "nlp": nlp, "sim": sim, "thresholds": thresholds,
        SUN_METHOD: SunScorer(sim, thresholds["tau"], thresholds["gamma"],
                              thresholds["theta"], nlp=nlp),
        V3_METHOD: EvidenceChecksV3(sim, thresholds["tau"], thresholds["gamma"],
                                    thresholds["theta"], nlp=nlp),
        "models": build_sun_models(BPMN_DIR, STRUCTURAL_CONTRACT, nlp),
    }


def run_designated_check(scorer, check_type: str, record: dict, model):
    if record.get("failed"):
        return scorer._result([], "external_rule_record_failure")
    if check_type == "incorrect_actor":
        return scorer.incorrect_actor(record["actions"], record["actors"], model,
                                      record.get("actor_action_pairs"))
    if check_type == "out_of_order":
        return scorer.out_of_order(record["order_relations"], record["actions"], model)
    return scorer.missing_action(record["actions"], model)


def normalize(method: str, check_type: str, raw: dict) -> dict:
    if method == SUN_METHOD:
        return normalize_sun(check_type, raw)
    return normalize_evidence(check_type, raw)


def match_records(raw: dict, check_type: str) -> list[dict]:
    """Per-requirement match records of a check result (v3 shape)."""
    if check_type == "out_of_order":
        records = []
        for detail in raw.get("details", []):
            for key in ("before", "after"):
                if isinstance(detail.get(key), dict):
                    records.append(detail[key])
        return records
    return [detail["match"] for detail in raw.get("details", [])
            if isinstance(detail.get("match"), dict)]


def build_predictions(rule_inputs: dict, scorers: dict) -> tuple[list[dict], dict]:
    """Run both checkers on all 33 items: 33 x 2 = 66 prediction rows.

    Evidence is de-duplicated across items and methods, so a rule requirement that
    several items share is stored once and only referenced by id.
    """
    items = sorted(rule_inputs["inference"]["violation_items"], key=lambda x: x["item_id"])
    records = rule_inputs["records"]
    models = scorers["models"]
    evidence: dict[str, dict] = {}
    rows: list[dict] = []

    def add_evidence(key: dict, payload: dict) -> str:
        eid = hashlib.sha1(json.dumps(key, sort_keys=True, ensure_ascii=False)
                           .encode("utf-8")).hexdigest()[:16]
        entry = evidence.get(eid)
        if entry is None:
            evidence[eid] = {"evidence_id": eid, **key, **payload}
        else:
            for rule_id in key.get("rule_ids", []):
                if rule_id not in entry["rule_ids"]:
                    entry["rule_ids"].append(rule_id)
        return eid

    for item in items:
        rule_id = item["rule_id"]
        process_id = item["process_id"]
        check_type = item["check_type"]
        record = records[rule_id]
        model = models[process_id]
        common = {
            "schema_version": "s3_real_rule_diagnostic_prediction@1.0.0",
            "run_id": RUN_ID,
            "item_id": item["item_id"],
            "process_id": process_id,
            "rule_id": rule_id,
            "check_type": check_type,
            "rule_record": {
                "actions": len(record["actions"]),
                "actors": len(record["actors"]),
                "actor_action_pairs": len(record.get("actor_action_pairs") or []),
                "order_relations": len(record["order_relations"]),
                "failed": bool(record.get("failed")),
                "failure_reasons": list(record.get("failure_reasons") or []),
                "modality": record.get("modality"),
            },
            "rule_requirement_sha256": canonical_sha256({
                "actions": record["actions"], "actors": record["actors"],
                "pairs": record.get("actor_action_pairs") or [],
                "orders": [list(x) for x in record["order_relations"]]}),
            "model_bpmn": (BPMN_DIR / f"{process_id}.bpmn").relative_to(ROOT).as_posix(),
            "model_bpmn_sha256": sha256_file(BPMN_DIR / f"{process_id}.bpmn"),
            "shared_binding": {
                "thresholds": scorers["thresholds"],
                "nlp_model": "en_core_web_sm",
                "similarity_backend": "winter_stage3.winter_similarity.WinterSimilarity",
                "rule_source": HUMAN_CAPSULE.relative_to(ROOT).as_posix(),
                "include_modalities": list(INCLUDE_MODALITIES),
                "task": "designated_check_type_only",
            },
        }
        for method in METHODS:
            raw = run_designated_check(scorers[method], check_type, record, model)
            state = normalize(method, check_type, raw)
            evidence_ids: list[str] = []
            if check_type == "out_of_order":
                for before, after in record["order_relations"]:
                    for position, text in (("before", before), ("after", after)):
                        evidence_ids.append(add_evidence(
                            {"method": method, "kind": f"order_{position}",
                             "process_id": process_id, "requirement_text": text,
                             "rule_ids": [rule_id]},
                            {"source": find_source_span(rule_inputs, rule_id, text),
                             "mapping": endpoint_mapping(method, raw, text, model),
                             "capability_notes": [
                                 "order endpoints are matched against the model's action list, "
                                 "which contains both activities and events"]}))
            else:
                for text in record["actions"]:
                    evidence_ids.append(add_evidence(
                        {"method": method, "kind": "action", "process_id": process_id,
                         "requirement_text": text, "rule_ids": [rule_id]},
                        {"source": find_source_span(rule_inputs, rule_id, text),
                         "representation": representation_of(method, scorers, text),
                         "mapping": action_mapping(method, raw, text, model)}))
                if check_type == "incorrect_actor":
                    for pair in (record.get("actor_action_pairs") or []):
                        linked = ""
                        if pair["action"] in record["actions"] and evidence_ids:
                            linked = evidence_ids[record["actions"].index(pair["action"])]
                        evidence_ids.append(add_evidence(
                            {"method": method, "kind": "actor", "process_id": process_id,
                             "requirement_text": pair["actor"], "rule_ids": [rule_id]},
                            {"source": find_source_span(rule_inputs, rule_id, pair["actor"]),
                             "linked_action": pair["action"],
                             "action_evidence_id": linked,
                             "mapping": actor_mapping(method, raw, pair, model)}))
            rows.append({
                **common,
                "method": method,
                "method_scope": "designated check type only; shared rule record and process model",
                "status": state["status"],
                "score": state.get("raw_score"),
                "denominator": state.get("denominator"),
                "reason": state.get("reason"),
                "conversion": state.get("conversion"),
                "evidence_ids": evidence_ids,
            })
    return rows, evidence


def find_source_span(rule_inputs: dict, rule_id: str, text: str) -> dict:
    """Locate the confirmed clause/span a requirement text came from."""
    for record in rule_inputs["gold_rules"]["records"]:
        if record["rule_id"] != rule_id:
            continue
        for clause in record["clauses"]:
            for collection, kind in (("actions", "action"), ("actors", "actor")):
                for span in clause.get(collection) or []:
                    if span.get("text") == text:
                        return {"resolved": True, "kind": kind, "sample_id": record["sample_id"],
                                "clause_id": clause["clause_id"], "clause_item_id": clause["item_id"],
                                "modality": clause["modality"]["label"],
                                "span": {"start": span["start"], "end": span["end"]},
                                "sentence_span": record.get("char_span")}
    return {"resolved": False, "reason": "requirement text is not a confirmed clause span verbatim"}


def representation_of(method: str, scorers: dict, text: str) -> dict:
    if method == V3_METHOD:
        structure = scorers[V3_METHOD]._structure(text)
        return {"kind": "structured_action_record",
                "predicate": structure["predicate"],
                "objects": sorted(structure["objects"]),
                "nested": structure["nested"],
                "roles": structure["roles"],
                "numerals": sorted(structure["numerals"]),
                "negated": structure["negated"],
                "unparsed_content": structure["unparsed_content"],
                "has_verb_predicate": structure.get("has_verb_predicate")}
    return {"kind": "lemma_string", "value": scorers[SUN_METHOD]._lemma(text)}


def activity_kind(model, activity_id: str) -> str:
    for action in model.actions:
        if action["id"] == activity_id:
            return action.get("kind", "activity")
    return "unknown"


def action_mapping(method: str, raw: dict, text: str, model) -> dict:
    if method == V3_METHOD:
        for match in match_records(raw, "missing_action"):
            if match.get("required", {}).get("text") == text:
                return {
                    "mapped": bool(match.get("mapped")),
                    "match_tier": match.get("match_tier"),
                    "tier_reason": match.get("tier_reason"),
                    "reason_codes": sorted({reason["code"] for reason in
                                            (match.get("best") or {}).get("reasons", [])}),
                    "candidates": [
                        {"activity_id": candidate["activity_id"], "label": candidate["label"],
                         "kind": activity_kind(model, candidate["activity_id"]),
                         "verdict": candidate["verdict"],
                         "raw_similarity": round(candidate["raw_similarity"], 4),
                         "reason_codes": [reason["code"] for reason in candidate["reasons"]]}
                        for candidate in match.get("candidates", [])],
                }
    for detail in raw.get("details", []):
        if detail.get("rule_action") == text:
            return {"mapped": not detail.get("missing", True),
                    "best_model_action": detail.get("best_model_action"),
                    "similarity": detail.get("similarity"),
                    "match_tier": "frozen_similarity_only",
                    "candidates": [], "reason_codes": []}
    return {"mapped": None, "note": "requirement not present in this check result"}


def actor_mapping(method: str, raw: dict, pair: dict, model) -> dict:
    owners = {}
    if method == V3_METHOD:
        for detail in raw.get("details", []):
            if not isinstance(detail.get("pair"), dict):
                continue
            if detail["pair"].get("actor") != pair["actor"]:
                continue
            match = detail.get("match") or {}
            best = match.get("best") or {}
            activity_id = best.get("activity_id")
            if activity_id:
                owners[activity_id] = {
                    "label": best.get("label"),
                    "kind": activity_kind(model, activity_id),
                    "executors": (match.get("best") or {}).get("executors")
                    or model.action_actor_names.get(activity_id, []),
                }
            return {"mapped": bool(match.get("mapped")), "match_tier": match.get("match_tier"),
                    "reason": detail.get("reason"), "violated": detail.get("violated"),
                    "required_actor": pair["actor"], "matched_activity_executors": owners,
                    "process_actor_candidates": detail.get("executors")}
    for detail in raw.get("details", []):
        if detail.get("rule_actor") == pair["actor"]:
            return {"mapped": True, "match_tier": "frozen_def6_action_bound",
                    "required_actor": pair["actor"],
                    "min_process_actor_similarity": detail.get("min_process_actor_similarity"),
                    "violated": detail.get("violated"),
                    "process_actor_candidates": raw.get("process_actor_candidates"),
                    "matched_process_action_ids": raw.get("matched_process_action_ids")}
    return {"mapped": None, "note": "actor not present in this check result",
            "required_actor": pair["actor"]}


def endpoint_mapping(method: str, raw: dict, text: str, model) -> dict:
    if method == V3_METHOD:
        for match in match_records(raw, "out_of_order"):
            candidate_text = (match.get("required") or {}).get("text")
            if candidate_text != text:
                continue
            best = match.get("best") or {}
            if best:
                return {"mapped": bool(match.get("mapped")), "match_tier": match.get("match_tier"),
                        "tier_reason": match.get("tier_reason"),
                        "activity_id": best.get("activity_id"), "label": best.get("label"),
                        "kind": activity_kind(model, best.get("activity_id") or ""),
                        "raw_similarity": round(best.get("raw_similarity") or 0.0, 4)}
            return {"mapped": bool(match.get("mapped")), "match_tier": match.get("match_tier"),
                    "tier_reason": match.get("tier_reason"), "activity_id": None, "label": None}
    for detail in raw.get("details", []):
        constraint = detail.get("constraint")
        if not constraint or text not in constraint:
            continue
        return {"mapped": bool(detail.get("mapped")), "match_tier": "frozen_similarity_only",
                "before_activity": detail.get("before_activity"),
                "after_activity": detail.get("after_activity"),
                "forward_reachable": detail.get("forward_reachable"),
                "backward_reachable": detail.get("backward_reachable"),
                "reason": detail.get("reason")}
    return {"mapped": None, "note": "endpoint not present in this check result"}


# ---------------------------------------------------------------------------
# Phase 2 - post-prediction: labels, scope review, summary
# ---------------------------------------------------------------------------


def build_scope_review(rule_inputs: dict, predictions: list[dict]) -> dict:
    violation_gold = read_json(VIOLATION_GOLD)
    case_ack = read_json(CASE_ACK)
    gold_items = {item["item_id"]: item for item in violation_gold["items"]}
    inference_items = {item["item_id"]: item for item in rule_inputs["inference"]["violation_items"]}
    available_articles = set(rule_inputs["rule_ids"])
    pred_index: dict[str, dict] = defaultdict(dict)
    for row in predictions:
        pred_index[row["item_id"]][row["method"]] = row["evidence_ids"]

    clause_stats: dict[str, dict] = defaultdict(lambda: {"clauses": 0, "conditions": 0,
                                                         "constraints": 0, "exceptions": 0})
    for record in rule_inputs["gold_rules"]["records"]:
        stats = clause_stats[record["rule_id"]]
        for clause in record["clauses"]:
            stats["clauses"] += 1
            stats["conditions"] += bool(clause["conditions"])
            stats["constraints"] += bool(clause["constraints"])
            stats["exceptions"] += bool(clause["exceptions"])

    rows = []
    for item_id in sorted(gold_items):
        gold = gold_items[item_id]
        item = inference_items[item_id]
        rule_id, check_type = item["rule_id"], item["check_type"]
        cited = {int(value) for value in re.findall(r"\bArt(?:icle)?\s+(\d+)",
                                                    gold.get("decision_evidence") or "")}
        present = {int(value) for value in
                   (re.sub(r"\D", "", rule_id) or "0" for rule_id in available_articles)}
        missing = sorted(cited - present)
        record = rule_inputs["records"][rule_id]
        stats = clause_stats[rule_id]
        groups: list[str] = []
        if cited - present:
            groups.append("G3_missing_cited_article")
        groups.append("G1_target_binding")
        groups.append("G2_original_or_variant")
        if check_type == "incorrect_actor" and not record["actors"]:
            pass  # capability limit, not a scope question
        notification_conflict = bool(
            item["process_id"] == "gdpr_1_data_breach" and rule_id == "article33"
            and gold.get("decision_violation_type") in {"missing_action", "incorrect_actor"}
            and check_type in {"missing_action", "incorrect_actor"})
        if notification_conflict:
            groups.append("G4_confirmed_local_conflict")
        groups.append("G5_no_negative_control")

        proposals = []
        for record_row in rule_inputs["gold_rules"]["records"]:
            if record_row["rule_id"] != rule_id:
                continue
            for clause in record_row["clauses"][:3]:
                if clause["modality"]["label"] != "obligation":
                    continue
                action = (clause["actions"] or [{}])[0]
                proposals.append({
                    "machine_proposed": True, "human_confirmed": False,
                    "clause_id": clause["clause_id"], "sample_id": record_row["sample_id"],
                    "modality": clause["modality"]["label"],
                    "action_text": action.get("text"),
                    "action_span": {"start": action.get("start"), "end": action.get("end")},
                    "note": "candidate binding only; not approved, not Gold",
                })
            if len(proposals) >= 3:
                break

        rows.append({
            "item_id": item_id,
            "process_id": item["process_id"],
            "rule_id": rule_id,
            "check_type": check_type,
            "legacy": {
                "decision_violation_type": gold.get("decision_violation_type"),
                "decision_evidence": gold.get("decision_evidence"),
                "cited_articles": sorted(cited),
                "cited_articles_absent_from_current_input": missing,
            },
            "inference_scope": {
                "designated_check_type": check_type,
                "rule_actions_checked": len(record["actions"]),
                "rule_actors_checked": len(record["actors"]),
                "rule_order_relations_checked": len(record["order_relations"]),
                "condition_clauses_not_consumed": stats["conditions"],
                "constraint_clauses_not_consumed": stats["constraints"],
                "exception_clauses_not_consumed": stats["exceptions"],
                "modality_policy": "obligation only",
            },
            "target_binding": {
                "original_or_variant": "not_specified",
                "target_activity_bound": False,
                "target_clause_bound": False,
                "variant_bound": False,
                "evidence": "the pre-existing item carries only process_id/rule_id/check_type/rule_text",
            },
            "cited_article_present_in_current_input": not missing,
            "confirmed_opinion_scope_conflict": notification_conflict,
            "confirmed_opinion_source": (CASE_ACK.relative_to(ROOT).as_posix()
                                          if notification_conflict else None),
            "machine_proposed_bindings": proposals,
            "minimum_question_groups": groups,
            "evidence_refs": {
                "violation_gold": VIOLATION_GOLD.relative_to(ROOT).as_posix(),
                "inference_pack": INFERENCE_PACK.relative_to(ROOT).as_posix(),
                "human_rule_records": GOLD_RULE_RECORDS.relative_to(ROOT).as_posix(),
                "prediction_ids": {method: pred_index[item_id][method] for method in METHODS},
            },
        })

    group_index: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        for group in row["minimum_question_groups"]:
            group_index[group].append(row["item_id"])
    return {
        "schema_version": "s3_real_rule_diagnostic_scope_review@1.0.0",
        "run_id": RUN_ID,
        "item_count": len(rows),
        "negative_control_count": sum(row["legacy"]["decision_violation_type"] is None for row in rows),
        "all_items_are_positive_labels": all(row["legacy"]["decision_violation_type"] is not None
                                             for row in rows),
        "requires_human_scope_resolution": True,
        "may_relabel_gold_automatically": False,
        "performance_claim_ready": False,
        "confirmed_local_opinion": case_ack,
        "items": rows,
        "question_groups": [
            {"group_id": group_id, "items": sorted(items),
             "item_count": len(items), **QUESTION_GROUPS[group_id]}
            for group_id, items in sorted(group_index.items())],
        "note": "machine_proposed bindings are candidate bindings only: not approved, not "
                "reviewed, not adjudicated and not Gold",
    }


def mapping_coverage(predictions: list[dict], evidence: dict[str, dict],
                     rule_inputs: dict) -> dict:
    counts = {method: Counter() for method in METHODS}
    denominators = {method: {"actions": 0, "actors": 0, "order_endpoints": 0} for method in METHODS}
    for row in predictions:
        method = row["method"]
        record = rule_inputs["records"][row["rule_id"]]
        if row["check_type"] in {"missing_action", "incorrect_actor"}:
            denominators[method]["actions"] += len(record["actions"])
        if row["check_type"] == "incorrect_actor":
            denominators[method]["actors"] += len(record.get("actor_action_pairs") or [])
        if row["check_type"] == "out_of_order":
            denominators[method]["order_endpoints"] += 2 * len(record["order_relations"])
        for eid in row["evidence_ids"]:
            entry = evidence[eid]
            counts[method][classify_mapping(entry, row["check_type"])] += 1
    return {
        "definition": "each unit counts once per method; units are de-duplicated rule "
                      "requirements (one per method/action/process or actor/process or endpoint)",
        "classes": list(MAPPING_CLASSES),
        "denominators": {
            method: {"required_actions_checked": denominators[method]["actions"],
                     "required_actors_checked": denominators[method]["actors"],
                     "order_endpoints_checked": denominators[method]["order_endpoints"]}
            for method in METHODS},
        "counts": {method: {name: counts[method][name] for name in MAPPING_CLASSES}
                   for method in METHODS},
    }


def classify_mapping(entry: dict, check_type: str) -> str:
    mapping = entry.get("mapping") or {}
    if mapping.get("mapped") is None:
        return "rule_lacks_required_information"
    if entry.get("kind", "").startswith("order_"):
        if not mapping.get("mapped"):
            return "order_endpoint_not_an_activity"
        if mapping.get("kind") and mapping.get("kind") != "activity":
            return "order_endpoint_not_an_activity"
        return "evidence_supports_judgment"
    if check_type == "incorrect_actor":
        if mapping.get("mapped") is None:
            return "rule_lacks_required_information"
        if mapping.get("violated") is False:
            return "evidence_supports_judgment"
        if mapping.get("violated") is True:
            return "evidence_supports_judgment"
        return "expression_differs_unresolved"
    if mapping.get("mapped"):
        return "mapped_unique"
    codes = set(mapping.get("reason_codes") or [])
    if codes & {"requirement_content_not_parsed", "partial_object_overlap",
                "required_object_content_absent", "object_terms_possibly_equivalent"}:
        return "structure_parse_insufficient"
    if codes & {"exact_label_tie", "predicate_object_agreement_tie"}:
        return "multiple_candidates_insufficient"
    if mapping.get("match_tier") in {"structure_undetermined", "frozen_similarity_tie",
                                     "ambiguous_action_mapping"}:
        return "multiple_candidates_insufficient"
    if mapping.get("match_tier") == "structure_not_satisfied":
        return "expression_differs_unresolved"
    if mapping.get("best_model_action") is None:
        return "expression_differs_unresolved"
    return "expression_differs_unresolved"


def build_summary(rule_inputs: dict, predictions: list[dict], evidence: dict[str, dict],
                  scope: dict) -> dict:
    counts = {method: {check: Counter() for check in CHECK_TYPES} for method in METHODS}
    for row in predictions:
        counts[row["method"]][row["check_type"]][row["status"]] += 1

    by_item: dict[str, dict] = defaultdict(dict)
    for row in predictions:
        by_item[row["item_id"]][row["method"]] = row
    differences = []
    for item_id in sorted(by_item):
        sun = by_item[item_id][SUN_METHOD]
        v3 = by_item[item_id][V3_METHOD]
        if sun["status"] != v3["status"]:
            differences.append({
                "item_id": item_id, "check_type": sun["check_type"],
                "rule_id": sun["rule_id"], "process_id": sun["process_id"],
                "sun_status": sun["status"], "sun_reason": sun["reason"],
                "v3_status": v3["status"], "v3_reason": v3["reason"],
                "explanation": explain_difference(sun, v3),
            })

    coverage = mapping_coverage(predictions, evidence, rule_inputs)

    blockers = []
    no_actions = sorted({row["rule_id"] for row in predictions if row["rule_record"]["actions"] == 0})
    if no_actions:
        blockers.append({
            "blocker": "obligation_only_rules_without_actions",
            "rules": no_actions,
            "items": sorted({row["item_id"] for row in predictions if row["rule_id"] in no_actions}),
            "detail": "these articles carry no obligation clause, so the frozen obligation-only "
                      "policy leaves nothing to check for their items",
        })
    no_orders = sorted({row["item_id"] for row in predictions
                        if row["check_type"] == "out_of_order"
                        and row["rule_record"]["order_relations"] == 0})
    if no_orders:
        blockers.append({
            "blocker": "out_of_order_items_without_rule_order_information",
            "items": no_orders,
            "detail": "the rule record has no order relation and the confirmed temporal notes do "
                      "not cover these rules, so the order check has an empty denominator",
        })
    no_actors = sorted({row["item_id"] for row in predictions
                        if row["check_type"] == "incorrect_actor"
                        and not rule_inputs["records"][row["rule_id"]]["actors"]})
    if no_actors:
        blockers.append({
            "blocker": "incorrect_actor_items_without_rule_actor_information",
            "items": no_actors,
            "detail": "the rule record has no actor for these items, so the actor check cannot "
                      "be observed",
        })
    conditions = sorted({row["item_id"] for row in predictions
                         if clause_has_conditions(rule_inputs, row["rule_id"])})
    if conditions:
        blockers.append({
            "blocker": "conditions_constraints_exceptions_not_consumed",
            "items": conditions,
            "detail": "the confirmed clauses carry conditions/constraints/exceptions, and the "
                      "frozen converter and scorers do not consume them, so applicability is "
                      "not evaluated",
        })

    return {
        "schema_version": "s3_real_rule_diagnostic_summary@1.0.0",
        "run_id": RUN_ID,
        "claim_scope": "development_diagnostic_on_real_legal_rule_input",
        "performance_claim_ready": False,
        "formal_oracle_promotion": False,
        "inputs_used": {
            "human_rule_capsule": HUMAN_CAPSULE.relative_to(ROOT).as_posix(),
            "gold_rule_records": GOLD_RULE_RECORDS.relative_to(ROOT).as_posix(),
            "legal_text_input": STAGE2_INPUT.relative_to(ROOT).as_posix(),
            "inference_items": INFERENCE_PACK.relative_to(ROOT).as_posix(),
            "bpmn": [p.relative_to(ROOT).as_posix() for p in sorted(BPMN_DIR.glob("*.bpmn"))],
            "synthetic_variants_loaded": False,
        },
        "counts_per_method_and_check": {
            method: {check: dict(counts[method][check]) for check in CHECK_TYPES}
            for method in METHODS},
        "status_totals": {method: dict(Counter(row["status"] for row in predictions
                                               if row["method"] == method))
                          for method in METHODS},
        "mapping_coverage": coverage,
        "rule_conversion": {
            "include_modalities": list(INCLUDE_MODALITIES),
            "per_rule": {rule_id: {k: v for k, v in rule_inputs["conversion_summary"]
                                   ["per_rule"][rule_id].items()
                                   if k in {"clause_count", "included_clause_count",
                                            "excluded_modality_counts", "action_count",
                                            "actor_count", "order_relations_count",
                                            "order_relations_absent", "envelopes_failed"}}
                         for rule_id in rule_inputs["rule_ids"]},
            "temporal_projection": {
                "accepted": rule_inputs["temporal"]["accepted"],
                "rejected": rule_inputs["temporal"]["rejected"],
                "note": "the three confirmed sentence-level order statements are projected as "
                        "runtime order edges only; endpoints are not added as mandatory actions",
            },
        },
        "method_differences": differences,
        "scope_review": {
            "item_count": scope["item_count"],
            "clear_scope_items": [row["item_id"] for row in scope["items"]
                                  if not row["minimum_question_groups"]
                                  or row["minimum_question_groups"] == ["G5_no_negative_control"]],
            "items_with_missing_input_articles": [row["item_id"] for row in scope["items"]
                                                  if row["legacy"]
                                                  ["cited_articles_absent_from_current_input"]],
            "items_with_confirmed_opinion_conflict": [row["item_id"] for row in scope["items"]
                                                      if row["confirmed_opinion_scope_conflict"]],
            "items_requiring_human_clarification": sorted(
                {row["item_id"] for row in scope["items"] if row["minimum_question_groups"]}),
            "question_groups": scope["question_groups"],
        },
        "top_blockers": blockers[:3],
        "legacy_label_diagnostic": build_legacy_diagnostic(predictions),
        "capability_limits": [
            "the frozen converter consumes the obligation modality only; permission, prohibition "
            "and definition clauses are recorded but never checked",
            "the frozen converter does not consume conditions, constraints or exceptions, so "
            "applicability of a rule to a process is not evaluated",
            "the frozen scorer matches order endpoints against activities and events together and "
            "requires a rule-side order relation; structured order relations are absent for all "
            "nine articles and only the three confirmed temporal sentences are projected",
            "an IncorrectActor check needs an actor-action mapping; articles without actors cannot "
            "be observed",
        ],
        "separation_note": "prediction outputs are written before any label is read; the summary "
                           "is derived from the stored predictions and the rule structure only",
    }


def clause_has_conditions(rule_inputs: dict, rule_id: str) -> bool:
    for record in rule_inputs["gold_rules"]["records"]:
        if record["rule_id"] != rule_id:
            continue
        return any(clause["conditions"] or clause["constraints"] or clause["exceptions"]
                   for clause in record["clauses"])
    return False


def explain_difference(sun: dict, v3: dict) -> str:
    if v3["status"] == "unknown":
        return f"v3 keeps the requirement undetermined; recorded reason: {v3['reason']}"
    if sun["status"] == "unknown":
        return f"the frozen path is undetermined (reason: {sun['reason']}) while v3 gives " \
               f"{v3['status']} from its structured evidence"
    return f"the frozen similarity path gives {sun['status']} and the structured matcher gives " \
           f"{v3['status']}; see evidence ids for the candidate comparison"


def build_legacy_diagnostic(predictions: list[dict]) -> dict:
    violation_gold = read_json(VIOLATION_GOLD)
    labels = {item["item_id"]: item["decision_violation_type"]
              for item in violation_gold["items"]}
    per_method = {}
    for method in METHODS:
        per_type = {}
        for check in CHECK_TYPES:
            tp = fp = fn = tn = unknown = 0
            for row in predictions:
                if row["method"] != method or row["check_type"] != check:
                    continue
                gold = labels[row["item_id"]]
                status = row["status"]
                predicted = check if status == "violation" else None
                if status == "unknown":
                    unknown += 1
                tp += gold == check and predicted == check
                fp += gold != check and predicted == check
                fn += gold == check and predicted != check
                tn += gold is None and status == "satisfied"
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            per_type[check] = {"support": sum(1 for row in predictions
                                              if row["method"] == method
                                              and row["check_type"] == check),
                               "tp": tp, "fp": fp, "fn": fn, "tn": tn, "unknown": unknown,
                               "precision": precision, "recall": recall,
                               "f1": (2 * precision * recall / (precision + recall))
                               if (precision + recall) else 0.0}
        per_method[method] = {
            "per_type": per_type,
            "macro_f1": sum(per_type[check]["f1"] for check in CHECK_TYPES) / len(CHECK_TYPES),
            "items_retained": sum(1 for row in predictions if row["method"] == method),
        }
    return {
        "label": "legacy_label_diagnostic",
        "source": VIOLATION_GOLD.relative_to(ROOT).as_posix(),
        "scope_unresolved": True,
        "performance_claim_ready": False,
        "denominator_policy": "positive unknown counts as FN; every one of the 33 legacy items is "
                              "retained; no subset selection",
        "negative_control_count": sum(label is None for label in labels.values()),
        "methods": per_method,
        "note": "these numbers are a diagnostic against the legacy labels whose check scope is "
                "still unresolved; they are not the round's main result and must not be used to "
                "claim an improvement",
    }


SCOPE_CACHE: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Manifest, verification, CLI
# ---------------------------------------------------------------------------


def input_paths() -> list[str]:
    return [
        HUMAN_CAPSULE.relative_to(ROOT).as_posix(),
        GOLD_RULE_RECORDS.relative_to(ROOT).as_posix(),
        STAGE2_INPUT.relative_to(ROOT).as_posix(),
        INFERENCE_PACK.relative_to(ROOT).as_posix(),
        VIOLATION_GOLD.relative_to(ROOT).as_posix(),
        CASE_ACK.relative_to(ROOT).as_posix(),
        SUN_CONFIG.relative_to(ROOT).as_posix(),
        STRUCTURAL_CONTRACT.relative_to(ROOT).as_posix(),
    ] + [p.relative_to(ROOT).as_posix() for p in sorted(BPMN_DIR.glob("*.bpmn"))]


def implementation_paths() -> list[str]:
    return [
        "scripts/run_s3_real_rule_diagnostic_v1.py",
        "tests/test_s3_real_rule_diagnostic_v1.py",
        "src/bpc_hybrid/s3_action_matching_v3.py",
        "src/bpc_hybrid/s3_action_matching_v2.py",
        "src/bpc_hybrid/s3_evidence_checks_v1.py",
        "src/bpc_hybrid/sun_stage3/sun_scorer.py",
        "src/bpc_hybrid/sun_stage3/sun_model.py",
        "src/bpc_hybrid/sun_stage3/gdpr_capsule_converter.py",
        "src/bpc_hybrid/winter_stage3/winter_similarity.py",
        "src/bpc_hybrid/stage1_process.py",
        "scripts/run_s3_paired_mechanism_v1.py",
    ]


def file_binding(rel: str) -> dict:
    path = ROOT / rel
    raw = path.read_bytes()
    filtered = subprocess.run(["git", "hash-object", f"--path={rel}", str(path)], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip()
    plain = subprocess.run(["git", "hash-object", "--no-filters", str(path)], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    return {"bytes": len(raw), "crlf_pairs": raw.count(b"\r\n"),
            "sha256_raw_working_tree": hashlib.sha256(raw).hexdigest(),
            "git_blob_sha1_raw": plain, "git_blob_sha1_after_clean_filter": filtered,
            "raw_bytes_equal_committed_bytes": plain == filtered}


def build_manifest(predictions: list[dict], evidence: dict[str, dict], started: str,
                   runtime: float) -> dict:
    return {
        "schema_version": "s3_real_rule_diagnostic_manifest@1.0.0",
        "run_id": RUN_ID,
        "started_utc": started,
        "runtime_seconds": round(runtime, 3),
        "git_commit_before_checkpoint": git(["rev-parse", "HEAD"]),
        "declarations": {
            "development_only": True,
            "real_legal_rule_input": True,
            "synthetic_panel_used": False,
            "human_gold_rule_records_read": True,
            "human_gold_modified": False,
            "legacy_labels_modified": False,
            "contracts_modified": False,
            "formal_oracle_promotion": False,
            "gold_publication": False,
            "new_llm_api_calls": 0,
            "checkers_modified": False,
            "prediction_written_before_label_read": True,
        },
        "hash_conventions": {
            "artifacts": "UTF-8, LF; committed bytes equal working-tree bytes",
            "sha256_raw_working_tree": "SHA-256 over the raw bytes on disk; the binding used by "
                                       "--check / --replay",
            "scope": "only this run's new files are pinned to text eol=lf",
        },
        "inputs": {rel: file_binding(rel) for rel in input_paths()},
        "implementation": {rel: file_binding(rel) for rel in implementation_paths()},
        "run": {
            "methods": list(METHODS),
            "item_count": len({row["item_id"] for row in predictions}),
            "prediction_rows": len(predictions),
            "mapping_evidence_rows": len(evidence),
            "include_modalities": list(INCLUDE_MODALITIES),
            "command": "python formal_experiment/scripts/run_s3_real_rule_diagnostic_v1.py --replay",
        },
        "results": {
            "predictions": {"path": PREDICTIONS_FILE.relative_to(ROOT).as_posix(),
                            "sha256": sha256_file(PREDICTIONS_FILE), "rows": len(predictions)},
            "mapping_evidence": {"path": MAPPING_FILE.relative_to(ROOT).as_posix(),
                                 "sha256": sha256_file(MAPPING_FILE), "rows": len(evidence)},
            "scope_review": {"path": SCOPE_FILE.relative_to(ROOT).as_posix(),
                             "sha256": sha256_file(SCOPE_FILE)},
            "summary": {"path": SUMMARY_FILE.relative_to(ROOT).as_posix(),
                        "sha256": sha256_file(SUMMARY_FILE)},
        },
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "safety": {
            "gold_read": True, "gold_modified": False, "old_results_modified": False,
            "original_bpmn_modified": False, "frozen_scorer_modified": False,
            "v3_checker_modified": False, "thresholds_changed": False,
            "similarity_backend_changed": False, "nlp_model_changed": False,
            "network_calls": 0, "llm_api_calls": 0,
        },
    }


def verify_outputs() -> dict:
    manifest = read_json(MANIFEST_FILE)
    mismatched = []
    for section in ("inputs", "implementation"):
        for rel, binding in manifest[section].items():
            if sha256_file(ROOT / rel) != binding["sha256_raw_working_tree"]:
                mismatched.append(f"{section}:{rel}")
    for key, entry in manifest["results"].items():
        if sha256_file(ROOT / entry["path"]) != entry["sha256"]:
            mismatched.append(f"results:{key}")
    if mismatched:
        raise RuntimeError("hash mismatch: " + ", ".join(sorted(set(mismatched))))
    predictions = read_jsonl(PREDICTIONS_FILE)
    evidence_rows = read_jsonl(MAPPING_FILE)
    scope = read_json(SCOPE_FILE)
    summary = read_json(SUMMARY_FILE)
    if len(predictions) != 66:
        raise RuntimeError("expected 33 items x 2 methods = 66 prediction rows")
    if len({row["item_id"] for row in predictions}) != 33:
        raise RuntimeError("the 33 legacy item ids must be preserved")
    if {row["method"] for row in predictions} != set(METHODS):
        raise RuntimeError("both checkers must be present")
    if len(scope["items"]) != 33:
        raise RuntimeError("scope review must keep all 33 items")
    if summary["performance_claim_ready"] is not False:
        raise RuntimeError("the round is a diagnostic, never a performance claim")
    evidence_ids = {row["evidence_id"] for row in evidence_rows}
    for row in predictions:
        for eid in row["evidence_ids"]:
            if eid not in evidence_ids:
                raise RuntimeError(f"prediction references missing evidence {eid}")
    return {"predictions": predictions, "evidence": evidence_rows, "scope": scope,
            "summary": summary}


def write_predictions_and_evidence(predictions: list[dict], evidence: dict[str, dict]) -> None:
    """Phase 1 output: written before any label is read."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with PREDICTIONS_FILE.open("w", encoding="utf-8", newline="\n") as handle:
        for row in predictions:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with MAPPING_FILE.open("w", encoding="utf-8", newline="\n") as handle:
        for eid in sorted(evidence):
            handle.write(json.dumps(evidence[eid], ensure_ascii=False, sort_keys=True) + "\n")


def write_scope_summary_manifest(scope: dict, summary: dict, predictions: list[dict],
                                 evidence: dict[str, dict], started: str,
                                 runtime: float) -> None:
    """Phase 2 output: scope review, summary and manifest."""
    SCOPE_FILE.write_bytes((json.dumps(scope, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    SUMMARY_FILE.write_bytes((json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    MANIFEST_FILE.write_bytes((json.dumps(build_manifest(predictions, evidence, started, runtime),
                                          ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def replay_payload() -> dict:
    rule_inputs = build_rule_inputs()
    scorers = build_scorers()
    predictions, evidence = build_predictions(rule_inputs, scorers)
    scope = build_scope_review(rule_inputs, predictions)
    summary = build_summary(rule_inputs, predictions, evidence, scope)
    as_json = lambda value: json.loads(json.dumps(value, sort_keys=True))  # noqa: E731
    return {
        "predictions": as_json(predictions),
        "stored_predictions": as_json(read_jsonl(PREDICTIONS_FILE)),
        "evidence": as_json(sorted(evidence.values(), key=lambda x: x["evidence_id"])),
        "stored_evidence": as_json(read_jsonl(MAPPING_FILE)),
        "scope": as_json(scope),
        "stored_scope": as_json(read_json(SCOPE_FILE)),
        "summary": as_json(summary),
        "stored_summary": as_json(read_json(SUMMARY_FILE)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()

    if args.check or args.replay:
        verify_outputs()
        if args.replay:
            payload = replay_payload()
            for key in ("predictions", "evidence", "scope", "summary"):
                if payload[key] != payload[f"stored_{key}"]:
                    raise RuntimeError(f"{key} replay mismatch")
        print("S3 REAL RULE DIAGNOSTIC VERIFIED")
        return 0

    if OUT_DIR.exists() and any(OUT_DIR.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing run directory: {OUT_DIR}")
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    rule_inputs = build_rule_inputs()
    scorers = build_scorers()
    predictions, evidence = build_predictions(rule_inputs, scorers)
    # phase 1 boundary: predictions and mapping evidence are on disk before any label read
    write_predictions_and_evidence(predictions, evidence)
    scope = build_scope_review(rule_inputs, predictions)
    summary = build_summary(rule_inputs, predictions, evidence, scope)
    write_scope_summary_manifest(scope, summary, predictions, evidence, started, time.time() - t0)
    verify_outputs()
    print(json.dumps({
        "run_id": RUN_ID,
        "items": 33, "prediction_rows": len(predictions),
        "mapping_evidence_rows": len(evidence),
        "status_totals": summary["status_totals"],
        "method_differences": len(summary["method_differences"]),
        "scope": {k: len(v) for k, v in summary["scope_review"].items() if isinstance(v, list)},
        "llm_api_calls": 0,
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
