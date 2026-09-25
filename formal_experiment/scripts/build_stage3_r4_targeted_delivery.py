# -*- coding: utf-8 -*-
"""Build the R4 targeted central delivery report.

This is a post-inference, post-evaluation analysis.  It reads the saved R4
predictions/report, the historical M1 report/predictions, the frozen reference
labels, and the R4 mechanism check.  It does not call an LLM/API, does not
re-run Stage 2, and does not change any prediction or threshold.
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

M1_REPORT = ROOT / "outputs/reports/stage3_table3_r3_m1.json"
M1_PRED = ROOT / "outputs/development/stage3_table3_r3_m1/predictions.json"
M1_RULE_RECORDS = ROOT / "outputs/development/stage3_table3_r3_m1/rule_records.json"
R4_REPORT = ROOT / "outputs/reports/stage3_table3_r4_targeted_v1_eval.json"
R4_PRED = ROOT / "outputs/development/stage3_table3_r4_targeted_v1/predictions.json"
R4_RULE_RECORDS = ROOT / "outputs/development/stage3_table3_r4_targeted_v1/rule_records.json"
R4_MANIFEST = ROOT / "outputs/development/stage3_table3_r4_targeted_v1/run_manifest.json"
SIDECAR_INDEX = ROOT / "outputs/development/stage3_table3_r3_p2_sidecars/index.json"
REFERENCE = ROOT / "data/development/stage3_reconstruction_v4/construction_reference.json"
MECHANISM = ROOT / "outputs/reports/stage3_table3_r4_targeted_mechanism_v1.json"
D1_PRED = ROOT / "data/predictions/stage3_v4_d1_frozen_v1/predictions.json"
OUT_JSON = ROOT / "outputs/reports/stage3_table3_r4_targeted_v1.json"
FINAL_MANIFEST = ROOT / "outputs/reports/stage3_table3_r4_targeted_v1.manifest.json"
OUT_MD = ROOT / "outputs/reports/stage3_table3_r4_targeted_v1.md"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")
METRIC_FIELDS = ("tp", "fp", "fn", "tn", "precision", "recall", "f1",
                 "observable_coverage", "unknown_positive", "unknown_negative",
                 "not_applicable_cells", "cells", "predicted_positive")


def _load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _sha_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rel(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return Path(path).resolve().as_posix()


def _metric_subset(block: Mapping[str, Any] | None) -> dict[str, Any]:
    block = block or {}
    return {field: block.get(field) for field in METRIC_FIELDS}


def _method_metrics(report: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for method in ("sun", "ours", "winter"):
        block = ((report.get("methods") or {}).get(method) or {})
        out[method] = {
            "method_status": block.get("method_status"),
            "overall": _metric_subset(block.get("overall")),
            "per_type": {check: _metric_subset((block.get("per_type") or {}).get(check))
                         for check in TYPES},
        }
    return out


def _evidence_index(report: Mapping[str, Any]) -> dict[tuple[str, str, str, str], Mapping[str, Any]]:
    out: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    for row in report.get("evidence") or []:
        out[(str(row.get("method")), str(row.get("case_id")),
             str(row.get("rule_id")), str(row.get("check_type")))] = row
    return out


def _mapping_rows(pred_doc: Mapping[str, Any], method: str, case_id: str,
                  rule_id: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
    for row in pred_doc.get("records") or []:
        if str(row.get("row_method_id")) != method or str(row.get("case_id")) != case_id:
            continue
        rows = list((row.get("method_evidence") or {}).get("mapping_table") or [])
        if rule_id is not None:
            rows = [r for r in rows if str(r.get("rule_id")) == str(rule_id)]
        if kind is not None:
            rows = [r for r in rows if str(r.get("kind")) == kind]
        return rows
    return []


def _candidate_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    candidates = list(row.get("candidates") or [])
    selected = next((c for c in candidates if c.get("selected")), None)
    return {
        "rule_original_text": row.get("rule_original_text"),
        "rule_action_surface": row.get("rule_action_surface"),
        "rule_business_object_surface": row.get("rule_business_object_surface"),
        "rule_legacy_match_source_text": row.get("rule_legacy_match_source_text"),
        "rule_legacy_matching_text": row.get("rule_legacy_matching_text"),
        "r4_action_match_source_text": row.get("r4_action_match_source_text"),
        "r4_action_matching_text": row.get("r4_action_matching_text"),
        "rule_parse_status": row.get("rule_parse_status"),
        "candidate_count": len(candidates),
        "selected_node_id": selected.get("node_id") if selected else None,
        "selected_similarity": selected.get("similarity") if selected else None,
        "selected_action_match_text": selected.get("candidate_action_match_text") if selected else None,
        "candidates": [{
            "node_id": c.get("node_id"),
            "node_type": c.get("node_type"),
            "original_label": c.get("original_label"),
            "candidate_action_surface": c.get("candidate_action_surface"),
            "candidate_legacy_match_source_text": c.get("candidate_legacy_match_source_text"),
            "candidate_action_match_text": c.get("candidate_action_match_text"),
            "candidate_matching_text": c.get("candidate_matching_text"),
            "similarity": c.get("similarity"),
            "tied": c.get("tied"),
            "selected": c.get("selected"),
            "reason": c.get("reason"),
        } for c in candidates],
    }


def _signal_summary(pred_doc: Mapping[str, Any], method: str, case_id: str,
                    rule_id: str, check_type: str) -> dict[str, Any] | None:
    for row in pred_doc.get("records") or []:
        if str(row.get("row_method_id")) != method or str(row.get("case_id")) != case_id:
            continue
        signal = (((row.get("signals_by_rule") or {}).get(rule_id) or {})
                  .get(check_type) or {})
        if not signal:
            return None
        return {
            "status": signal.get("status"),
            "raw_score": signal.get("raw_score"),
            "denominator": signal.get("denominator"),
            "observable": signal.get("observable"),
            "reason": signal.get("reason"),
            "r4_order_diagnostic": signal.get("r4_order_diagnostic"),
            "evidence": signal.get("evidence"),
        }
    return None


def _rule_record(rule_records_doc: Mapping[str, Any], method: str,
                 rule_id: str) -> Mapping[str, Any]:
    return (((rule_records_doc.get(method) or {}).get("records") or {}).get(rule_id) or {})


def _sidecar_by_case() -> dict[str, Any]:
    idx = _load_json(SIDECAR_INDEX)
    out: dict[str, Any] = {}
    for row in idx.get("cases") or []:
        out[str(row["case_id"])] = _load_json(ROOT / str(row["sidecar_path"]))
    return out


def _decision_changes(m1_report: Mapping[str, Any], r4_report: Mapping[str, Any],
                      m1_pred: Mapping[str, Any], r4_pred: Mapping[str, Any],
                      m1_rules: Mapping[str, Any], r4_rules: Mapping[str, Any],
                      reference: Mapping[str, Any]) -> list[dict[str, Any]]:
    a = _evidence_index(m1_report)
    b = _evidence_index(r4_report)
    ref_states = {(str(c["case_id"]), str(c["rule_id"])): c.get("reference_states") or {}
                  for c in reference.get("cases") or []}
    rows: list[dict[str, Any]] = []
    for key in sorted(set(a) | set(b)):
        old = a.get(key) or {}
        new = b.get(key) or {}
        if (old.get("predicted_status") == new.get("predicted_status")
                and old.get("classification") == new.get("classification")):
            continue
        method, case_id, rule_id, check_type = key
        mapping_kind = "order_endpoint" if check_type == "out_of_order" else "action"
        old_map = [_candidate_summary(r) for r in _mapping_rows(m1_pred, method, case_id, rule_id, mapping_kind)]
        new_map = [_candidate_summary(r) for r in _mapping_rows(r4_pred, method, case_id, rule_id, mapping_kind)]
        rows.append({
            "method": method,
            "case_id": case_id,
            "rule_id": rule_id,
            "check_type": check_type,
            "reference": (ref_states.get((case_id, rule_id)) or {}).get(check_type),
            "m1_status": old.get("predicted_status"),
            "r4_status": new.get("predicted_status"),
            "m1_classification": old.get("classification"),
            "r4_classification": new.get("classification"),
            "m1_signal": _signal_summary(m1_pred, method, case_id, rule_id, check_type),
            "r4_signal": _signal_summary(r4_pred, method, case_id, rule_id, check_type),
            "m1_mapping_evidence": old_map,
            "r4_mapping_evidence": new_map,
            "m1_rule_record": _rule_record(m1_rules, method, rule_id),
            "r4_rule_record": _rule_record(r4_rules, method, rule_id),
        })
    return rows


def _article18_chain(m1_pred: Mapping[str, Any], r4_pred: Mapping[str, Any],
                     m1_rules: Mapping[str, Any], r4_rules: Mapping[str, Any],
                     sidecars: Mapping[str, Any]) -> dict[str, Any]:
    cases = {
        "correct_order_control": "case_89c44a45c04d",
        "reverse_order_mutation": "case_8cbb7ad90a6d",
    }
    out: dict[str, Any] = {
        "rule_id": "article18p3",
        "note": "Original endpoint -> P2 field -> actual action comparison text -> selected node -> gamma -> reachability -> final state.",
        "cases": {},
    }
    for case_label, case_id in cases.items():
        case_out: dict[str, Any] = {"case_id": case_id, "methods": {}}
        for method in ("sun", "ours"):
            m1_signal = _signal_summary(m1_pred, method, case_id, "article18p3", "out_of_order")
            r4_signal = _signal_summary(r4_pred, method, case_id, "article18p3", "out_of_order")
            old_rows = [_candidate_summary(r) for r in _mapping_rows(
                m1_pred, method, case_id, "article18p3", "order_endpoint")]
            new_rows = [_candidate_summary(r) for r in _mapping_rows(
                r4_pred, method, case_id, "article18p3", "order_endpoint")]
            new_rule = _rule_record(r4_rules, method, "article18p3")
            old_rule = _rule_record(m1_rules, method, "article18p3")
            sidecar = sidecars.get(case_id) or {}
            endpoints: list[dict[str, Any]] = []
            for index, relation in enumerate(new_rule.get("order_relations") or []):
                view = (new_rule.get("order_relation_views") or [])[index] if index < len(new_rule.get("order_relation_views") or []) else {}
                for side, pos in (("before", 0), ("after", 1)):
                    endpoint_text = str(relation[pos]) if isinstance(relation, (list, tuple)) and len(relation) > pos else None
                    view_row = (view or {}).get(side) or {}
                    new_map = new_rows[pos] if pos < len(new_rows) else {}
                    old_map = old_rows[pos] if pos < len(old_rows) else {}
                    detail = None
                    for row in (r4_signal or {}).get("evidence", {}).get("details") or []:
                        if isinstance(row, dict) and side in ("before", "after"):
                            key = f"{side}_activity"
                            if key in row:
                                detail = row
                                break
                    endpoints.append({
                        "side": side,
                        "original_endpoint_text": endpoint_text,
                        "p2_fields": {
                            "action_surface": view_row.get("action_surface"),
                            "business_object_surface": view_row.get("business_object_surface"),
                            "legacy_match_source_text": view_row.get("match_source_text"),
                            "parse_status": view_row.get("parse_status"),
                            "parse_error": view_row.get("parse_error"),
                        },
                        "m1_actual_action_comparison": {
                            "rule_text": old_map.get("rule_action_surface") or old_map.get("rule_legacy_match_source_text"),
                            "rule_legacy_match_source_text": old_map.get("rule_legacy_match_source_text"),
                            "selected_node_id": old_map.get("selected_node_id"),
                            "selected_similarity": old_map.get("selected_similarity"),
                            "candidates": old_map.get("candidates"),
                        },
                        "r4_actual_action_comparison": {
                            "rule_action_surface": new_map.get("rule_action_surface"),
                            "r4_action_match_source_text": new_map.get("r4_action_match_source_text"),
                            "r4_action_matching_text": new_map.get("r4_action_matching_text"),
                            "selected_node_id": new_map.get("selected_node_id"),
                            "selected_similarity": new_map.get("selected_similarity"),
                            "candidates": new_map.get("candidates"),
                        },
                        "selected_model_node": (r4_signal or {}).get("evidence", {}).get("details", [{}])[0] if False else None,
                        "reachability": {
                            "before_activity": (detail or {}).get("before_activity"),
                            "after_activity": (detail or {}).get("after_activity"),
                            "forward_reachable": (detail or {}).get("forward_reachable"),
                            "backward_reachable": (detail or {}).get("backward_reachable"),
                            "satisfied": (detail or {}).get("satisfied"),
                        },
                    })
            case_out["methods"][method] = {
                "m1_final": m1_signal,
                "r4_final": r4_signal,
                "gamma": 0.8,
                "theta": 0.8,
                "m1_rule_relations": old_rule.get("order_relations"),
                "r4_rule_relations": new_rule.get("order_relations"),
                "r4_rule_relation_views": new_rule.get("order_relation_views"),
                "sidecar_reachable": sidecar.get("reachable"),
                "endpoints": endpoints,
            }
        out["cases"][case_label] = case_out
    return out


def _m1_scorer():
    import spacy
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    return SunScorer(sim, 0.8, 0.8, 0.8, nlp=nlp), sim


def _m1_actor_fp_rows(m1_pred: Mapping[str, Any], reference: Mapping[str, Any]) -> list[dict[str, Any]]:
    scorer, sim = _m1_scorer()
    case_rule = {str(c["case_id"]): str(c["rule_id"]) for c in reference.get("cases") or []}
    rows: list[dict[str, Any]] = []
    pred_by = {(str(r.get("row_method_id")), str(r.get("case_id"))): r for r in m1_pred.get("records") or []}
    for case in reference.get("cases") or []:
        if str((case.get("reference_states") or {}).get("incorrect_actor")) != "satisfied":
            continue
        case_id = str(case["case_id"])
        rule_id = case_rule[case_id]
        row = pred_by.get(("sun", case_id)) or {}
        signal = (((row.get("signals_by_rule") or {}).get(rule_id) or {}).get("incorrect_actor") or {})
        if signal.get("status") != "violated":
            continue
        details = (signal.get("evidence") or {}).get("details") or []
        candidates = (signal.get("evidence") or {}).get("process_actor_candidates") or []
        for detail_row in details:
            actor = str(detail_row.get("rule_actor"))
            scored: list[dict[str, Any]] = []
            for cand in candidates:
                compare_text = cand.get("matching_text") or cand.get("text")
                score = float(sim.text_pair(scorer._lemma(actor), scorer._lemma(str(compare_text))))
                scored.append({
                    "kind": cand.get("kind"),
                    "candidate_original_text": cand.get("text"),
                    "candidate_actual_comparison_text": compare_text,
                    "candidate_actual_comparison_lemma": scorer._lemma(str(compare_text)),
                    "node_id": cand.get("node_id"),
                    "rule_actor_similarity_raw": score,
                    "rule_actor_similarity": round(score, 4),
                    "violates_theta": bool(score < scorer.theta),
                })
            minimum = min((float(c["rule_actor_similarity_raw"]) for c in scored), default=0.0)
            min_candidates = [c for c in scored if float(c["rule_actor_similarity_raw"]) == minimum]
            rows.append({
                "case_id": case_id,
                "rule_id": rule_id,
                "method": "sun",
                "rule_actor_original_text": actor,
                "rule_actor_matching_text": scorer._lemma(actor),
                "theta": scorer.theta,
                "m1_min_process_actor_similarity": round(minimum, 4),
                "minimum_candidate_kind": min_candidates[0]["kind"] if min_candidates else None,
                "minimum_candidates": min_candidates,
                "all_candidates": scored,
                "business_object_candidate_present": any(c.get("kind") == "business_object" for c in scored),
                "reason_class": ("role_name_surface_mismatch"
                                 if min_candidates and min_candidates[0]["kind"] != "business_object"
                                 else "business_object_candidate_minimum"
                                 if min_candidates else "no_candidate"),
                "action_mapping_note": "Candidate set is action-bound; list includes model action nodes and business objects from those nodes.",
            })
    return rows


def _r4_actor_fp_rows(r4_pred: Mapping[str, Any], reference: Mapping[str, Any]) -> list[dict[str, Any]]:
    case_rule = {str(c["case_id"]): str(c["rule_id"]) for c in reference.get("cases") or []}
    rows: list[dict[str, Any]] = []
    pred_by = {(str(r.get("row_method_id")), str(r.get("case_id"))): r for r in r4_pred.get("records") or []}
    for method in ("sun", "ours"):
        for case in reference.get("cases") or []:
            if str((case.get("reference_states") or {}).get("incorrect_actor")) != "satisfied":
                continue
            case_id = str(case["case_id"])
            rule_id = case_rule[case_id]
            row = pred_by.get((method, case_id)) or {}
            signal = (((row.get("signals_by_rule") or {}).get(rule_id) or {}).get("incorrect_actor") or {})
            if signal.get("status") != "violated":
                continue
            details = (signal.get("evidence") or {}).get("details") or []
            for detail_row in details:
                rows.append({
                    "method": method,
                    "case_id": case_id,
                    "rule_id": rule_id,
                    "rule_actor_original_text": detail_row.get("rule_actor_original_text"),
                    "rule_actor_matching_text": detail_row.get("rule_actor_matching_text"),
                    "theta": detail_row.get("theta"),
                    "gamma": detail_row.get("gamma"),
                    "min_process_actor_similarity": detail_row.get("min_process_actor_similarity"),
                    "minimum_candidate_kind": (detail_row.get("minimum_candidates") or [{}])[0].get("kind"),
                    "minimum_candidates": detail_row.get("minimum_candidates"),
                    "all_candidates": detail_row.get("process_actor_candidates"),
                    "reason_class": ("role_name_surface_mismatch"
                                     if (detail_row.get("minimum_candidates") or [{}])[0].get("kind") != "business_object"
                                     else "business_object_candidate_minimum"),
                })
    return rows


def _counterfactual_summary(pred_doc: Mapping[str, Any], method: str,
                            m1_mode: bool = False) -> dict[str, Any]:
    changed: list[dict[str, Any]] = []
    total = 0
    excluded_empty = 0
    biz_min = 0
    actual_satisfied = 0
    scorer = None
    sim = None
    if m1_mode:
        scorer, sim = _m1_scorer()
    for row in pred_doc.get("records") or []:
        if str(row.get("row_method_id")) != method:
            continue
        for rule_id, signals in (row.get("signals_by_rule") or {}).items():
            signal = (signals or {}).get("incorrect_actor") or {}
            details = (signal.get("evidence") or {}).get("details") or []
            if not details:
                continue
            total += 1
            cf_items = []
            for detail_row in details:
                if m1_mode:
                    # M1 details do not carry candidate scores; only a single actor is saved per signal in practice.
                    candidates = (signal.get("evidence") or {}).get("process_actor_candidates") or []
                    actor = str(detail_row.get("rule_actor"))
                    kept = []
                    for cand in candidates:
                        if cand.get("kind") == "business_object":
                            continue
                        compare_text = cand.get("matching_text") or cand.get("text")
                        kept.append(float(sim.text_pair(scorer._lemma(actor), scorer._lemma(str(compare_text)))))
                    if not kept:
                        cf_items.append("unknown")
                        excluded_empty += 1
                    else:
                        cf_items.append("violated" if min(kept) < scorer.theta else "satisfied")
                else:
                    candidates = detail_row.get("process_actor_candidates") or []
                    kept = [c for c in candidates if c.get("kind") != "business_object"]
                    if not kept:
                        cf_items.append("unknown")
                        excluded_empty += 1
                    else:
                        cf_items.append("violated" if min(float(c["rule_actor_similarity_raw"]) for c in kept) < 0.8 else "satisfied")
                    if candidates and min(
                        (float(c.get("rule_actor_similarity_raw", 9.9)) for c in candidates),
                        default=9.9,
                    ) < 0.8:
                        min_cands = [c for c in candidates if c.get("rule_actor_similarity_raw") == min(
                            float(x.get("rule_actor_similarity_raw", 9.9)) for x in candidates)]
                        if min_cands and min_cands[0].get("kind") == "business_object":
                            biz_min += 1
            if any(x == "unknown" for x in cf_items):
                cf = "unknown"
            else:
                cf = "violated" if any(x == "violated" for x in cf_items) else "satisfied"
            actual = signal.get("status")
            if actual == "satisfied":
                actual_satisfied += 1
            if actual != cf:
                changed.append({"case_id": row.get("case_id"), "rule_id": rule_id,
                                "actual": actual, "counterfactual_excluding_business_object": cf})
    return {
        "method": method,
        "source": "M1" if m1_mode else "R4",
        "observable_actor_signals": total,
        "actual_satisfied_signals": actual_satisfied,
        "changed_signals": len(changed),
        "changed_to_unknown": sum(1 for x in changed if x["counterfactual_excluding_business_object"] == "unknown"),
        "changed_to_satisfied": sum(1 for x in changed if x["counterfactual_excluding_business_object"] == "satisfied"),
        "changed_to_violated": sum(1 for x in changed if x["counterfactual_excluding_business_object"] == "violated"),
        "business_object_was_minimum_count": biz_min,
        "remaining_candidate_empty_count": excluded_empty,
        "changed_rows": changed,
        "policy": ("diagnostic_counterfactual; same saved action mappings and actor scores; "
                   "business_object candidates removed; empty remaining C is recorded unknown, never satisfied"),
    }


def _definition6_check() -> dict[str, Any]:
    import spacy
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    scorer = SunScorer(sim, 0.8, 0.8, 0.8, nlp=nlp)
    actor = "the controller"
    actor_candidate = "the controller"
    business_object_candidate = "finance record"
    actor_score = float(sim.text_pair(scorer._lemma(actor), scorer._lemma(actor_candidate)))
    business_object_score = float(sim.text_pair(scorer._lemma(actor), scorer._lemma(business_object_candidate)))
    return {
        "paper_location": "references/papers/extracted/sun_2024_full_text.txt:549-559 (Definition 6)",
        "paper_literal_formula_line": 555,
        "paper_prose_line": 557,
        "paper_prose_quote": "C contains the actors in the process model that perform the same action as in the rule record",
        "implementation_paths": [
            "src/bpc_hybrid/sun_stage3/r3_sun_scorer.py::R3SunScorer.incorrect_actor (c_candidates construction)",
            "src/bpc_hybrid/sun_stage3/r4_action_surface_scorer.py::R4ActionSurfaceScorer.incorrect_actor (preserves R3 C scope)",
        ],
        "variable_mapping": {
            "R_{r,m,gamma}": "matched rule actors in r_set/matched_pairs",
            "D_{r,m}": "best action match from rule action to a model action",
            "f_r": "rule actor_action_pairs",
            "f_m": "model.action_actor_names / model.actor_sources",
            "bs_obj(A_m union E_m)": "model.business_objects bound to the matched model action",
            "C_{r,m,gamma}": "current implementation union of action-bound model actors and action-bound business objects",
        },
        "finding": ("The current implementation matches the literal extracted formula (which includes "
                    "bs_obj in the C union) but conflicts with the prose reading that C contains actors only. "
                    "This ambiguity was not silently changed in R4."),
        "minimal_discriminating_example": {
            "model": {"node_id": "N1", "action_surface": "Inform",
                      "actor_surface": "the controller", "business_object_surface": "finance record"},
            "rule": {"action_surface": "inform", "actor_original_text": "the controller"},
            "actor_candidate_score_raw": actor_score,
            "business_object_candidate_score_raw": business_object_score,
            "theta": 0.8,
            "literal_C_union_outcome": "violated (business-object minimum below theta)",
            "prose_actor_only_C_outcome": "satisfied (actor candidate score above theta)",
        },
    }


def _order_unknown_diagnostics(r4_report: Mapping[str, Any], r4_pred: Mapping[str, Any]) -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {}
    raw_reason_counts: dict[str, dict[str, int]] = {}
    examples: list[dict[str, Any]] = []
    for row in r4_pred.get("records") or []:
        method = str(row.get("row_method_id"))
        if method not in ("sun", "ours", "winter"):
            continue
        counts.setdefault(method, {})
        raw_reason_counts.setdefault(method, {})
        for rule_id, signals in (row.get("signals_by_rule") or {}).items():
            signal = (signals or {}).get("out_of_order") or {}
            diag = signal.get("r4_order_diagnostic") or {}
            category = str(diag.get("category") or signal.get("reason") or "unknown")
            counts[method][category] = counts[method].get(category, 0) + 1
            raw = str(signal.get("reason") or "None")
            raw_reason_counts[method][raw] = raw_reason_counts[method].get(raw, 0) + 1
            if (raw == "no_rule_order_endpoints" and category != "no_rule_order_relation"
                    and len(examples) < 4):
                examples.append({
                    "method": method, "case_id": row.get("case_id"), "rule_id": rule_id,
                    "raw_reason": raw, "precise_diagnostic_category": category,
                    "diagnostic": diag,
                    "order_relations": _rule_record(_load_json(R4_RULE_RECORDS), method, str(rule_id)).get("order_relations"),
                })
    return {
        "category_counts": counts,
        "raw_reason_counts": raw_reason_counts,
        "precision_field": "signal.r4_order_diagnostic.category (aliased as order_diagnostic for evaluator diagnostics)",
        "raw_reason_retained": True,
        "does_not_change_denominator_or_score": True,
        "examples_where_raw_reason_is_generic": examples,
    }


def _raw_d1_actor_evidence() -> dict[str, Any]:
    raw_path = ROOT / "data/predictions/stage3_v4_d1_frozen_v1/raw_responses/01_gdpr_article13p3_s001.json"
    raw14_path = ROOT / "data/predictions/stage3_v4_d1_frozen_v1/raw_responses/02_gdpr_article14p4_s001.json"
    d1 = _load_json(D1_PRED)
    out: dict[str, Any] = {}
    for rule_id, path in (("article13p3", raw_path), ("article14p4", raw14_path)):
        raw_doc = _load_json(path)
        body = json.loads(base64.b64decode(raw_doc["raw_response_body_base64"]).decode("utf-8"))
        content = json.loads(body["choices"][0]["message"]["content"])
        record = d1["records"][0]["record"] if rule_id == "article13p3" else d1["records"][1]["record"]
        out[rule_id] = {
            "raw_response_path": _rel(path),
            "raw_response_content_sha256": raw_doc.get("decode", {}).get("response_content_sha256"),
            "raw_response_contains_actor_the_controller": "the controller" in json.dumps(content).lower(),
            "raw_actor_texts": [a.get("text") for clause in content.get("clauses", []) for a in clause.get("actors", [])],
            "raw_actor_action_map": [m for clause in content.get("clauses", []) for m in clause.get("actor_action_map", [])],
            "canonical_record_actors": [a.get("text") for clause in record.get("clauses", []) for a in clause.get("actors", [])],
            "canonical_record_actor_action_map": [m for clause in record.get("clauses", []) for m in clause.get("actor_action_map", [])],
            "canonicalization_effect": "actor and actor-action association absent in the stored canonical record",
        }
    return out


def _stage2_residual_loss(r4_rules: Mapping[str, Any], r4_pred: Mapping[str, Any]) -> dict[str, Any]:
    d1 = _raw_d1_actor_evidence()
    method_records = r4_rules.get("ours", {}).get("records") or {}
    mapping = {str(r.get("rule_id")): r for r in _mapping_rows(r4_pred, "ours", "case_fd4b197b953b", "article13p3") + _mapping_rows(r4_pred, "ours", "case_44fc51ad7da0", "article14p4")}
    out: dict[str, Any] = {
        "scope": "Frozen Stage2 residual errors retained, not repaired by R4.",
        "ours_actor_loss": d1,
        "ours_rule_record_after_canonicalization": {
            rule_id: {
                "actors": (method_records.get(rule_id) or {}).get("actors"),
                "actor_action_pairs": (method_records.get(rule_id) or {}).get("actor_action_pairs"),
                "actions": (method_records.get(rule_id) or {}).get("actions"),
            } for rule_id in ("article13p3", "article14p4")
        },
        "ours_fragmented_action_views": {
            rule_id: [{
                "original_text": str(a),
                "action_surface": getattr(a, "action_surface", None),
                "business_object_surface": getattr(a, "business_object_surface", None),
            } for a in ((method_records.get(rule_id) or {}).get("actions") or [])]
            for rule_id in ("article13p3", "article14p4")
        },
        "order_edges_present_r4": {
            method: {
                rule_id: len((_rule_record(r4_rules, method, rule_id)).get("order_relations") or [])
                for rule_id in ("article18p3", "article35p1", "article36p1")
            } for method in ("sun", "ours")
        },
        "actual_metric_effects": {},
    }
    # Flatten action views from the saved predictions (the rule_records JSON serializes views as strings).
    out["ours_fragmented_action_views_from_predictions"] = {}
    for rule_id in ("article13p3", "article14p4"):
        rows = _mapping_rows(r4_pred, "ours", "case_fd4b197b953b" if rule_id == "article13p3" else "case_44fc51ad7da0", rule_id, "action")
        out["ours_fragmented_action_views_from_predictions"][rule_id] = [{
            "original_text": r.get("rule_original_text"),
            "action_surface": r.get("rule_action_surface"),
            "business_object_surface": r.get("rule_business_object_surface"),
            "r4_matching_text": r.get("r4_action_matching_text"),
        } for r in rows]
    # Effects.
    for method in ("sun", "ours"):
        actor_unknown = 0
        for row in r4_pred.get("records") or []:
            if str(row.get("row_method_id")) != method:
                continue
            for rule_id, signals in (row.get("signals_by_rule") or {}).items():
                if str(rule_id) not in ("article13p3", "article14p4", "article18p3", "article35p1", "article36p1"):
                    continue
                if (signals.get("incorrect_actor") or {}).get("status") == "unknown":
                    actor_unknown += 1
        out["actual_metric_effects"][method] = {"incorrect_actor_unknown_cells_in_five_rules": actor_unknown}
    return out


def _ranking_analysis(m1_metrics: Mapping[str, Any], r4_metrics: Mapping[str, Any]) -> dict[str, Any]:
    def f1(methods: Mapping[str, Any], method: str) -> Any:
        return (methods.get(method) or {}).get("overall", {}).get("f1")
    actual = {
        "m1": {m: f1(m1_metrics, m) for m in ("sun", "ours", "winter")},
        "r4": {m: f1(r4_metrics, m) for m in ("sun", "ours", "winter")},
    }
    return {
        "expected_order_was_not_an_acceptance_condition": True,
        "actual_overall_f1": actual,
        "supports_ours_gt_sun_gt_winter": False,
        "explanation": (
            "R4 F1 order is " +
            " > ".join(f"{m}={actual['r4'][m]:.4f}" if actual['r4'][m] is not None else f"{m}=null"
                       for m in sorted(actual["r4"], key=lambda x: (actual["r4"][x] is None, -(actual["r4"][x] or -1))))
            + ". The Ours-vs-Sun gap is not a threshold-tuning issue: per-type counts show "
              "Sun missing_action TP=3 FP=6 FN=2, Ours TP=2 FP=3 FN=3; Sun actor TP=4 FP=8 FN=1, "
              "Ours actor TP=3 FP=6 FN=2; order is identical (TP=1 FP=0 FN=4). Winter stays high "
              "because its actor TP=4 FP=0 FN=1, while Sun/Ours continue to lose actor cells to "
              "the the/Controller surface mismatch and frozen Stage2 losses."
        ),
        "gap_components": {
            "ours_vs_sun": {
                "overall_tp_delta_ours_minus_sun": int(r4_metrics["ours"]["overall"]["tp"]) - int(r4_metrics["sun"]["overall"]["tp"]),
                "overall_fp_delta_ours_minus_sun": int(r4_metrics["ours"]["overall"]["fp"]) - int(r4_metrics["sun"]["overall"]["fp"]),
                "overall_fn_delta_ours_minus_sun": int(r4_metrics["ours"]["overall"]["fn"]) - int(r4_metrics["sun"]["overall"]["fn"]),
                "missing_action_tp_delta": int(r4_metrics["ours"]["per_type"]["missing_action"]["tp"]) - int(r4_metrics["sun"]["per_type"]["missing_action"]["tp"]),
                "incorrect_actor_tp_delta": int(r4_metrics["ours"]["per_type"]["incorrect_actor"]["tp"]) - int(r4_metrics["sun"]["per_type"]["incorrect_actor"]["tp"]),
                "out_of_order_tp_delta": int(r4_metrics["ours"]["per_type"]["out_of_order"]["tp"]) - int(r4_metrics["sun"]["per_type"]["out_of_order"]["tp"]),
            },
            "winter_vs_others": {
                "winter_actor_tp_fp_fn": [r4_metrics["winter"]["per_type"]["incorrect_actor"][k] for k in ("tp", "fp", "fn")],
                "winter_order_all_unknown": r4_metrics["winter"]["per_type"]["out_of_order"]["unknown_positive"] == 5 and r4_metrics["winter"]["per_type"]["out_of_order"]["unknown_negative"] == 10,
            },
        },
    }


def _attribution() -> dict[str, Any]:
    return {
        "A_interface_or_implementation": [
            "R3 action comparison used action_surface + business_object_surface; R4 uses action_surface only on both sides.",
            "R3 mechanism-check entry point returned 0 regardless of failure; R4 check returns non-zero on contract/probe failure with an explicit self-test failure fixture.",
            "R3 backend selection normalized unknown values to sm; R4 entry point requires an explicit allowed --backend and records the actual loaded backend.",
            "R3 order-unknown reporting collapsed many causes into no_rule_order_endpoints; R4 keeps the raw reason and adds a precise diagnostic category without changing scores/denominators.",
        ],
        "B_frozen_stage2_real_prediction_errors": [
            "Ours D1 article13p3/article14p4 raw response contains 'the controller' and actor-action maps, but the stored canonical record has actors=[] and actor_action_map=[]; R4 cannot repair that.",
            "Ours article13p3 action is fragmented into two predicted actions; article14p4 is a single long action; neither is repaired.",
            "Frozen rule/order extraction still has missing order relations for some rules; R4 only evaluates the saved relations.",
        ],
        "C_method_or_representation_limits": [
            "action_surface-only cannot distinguish 'Archive the parcel' from 'Archive the invoice'; the mechanism fixtures retain this limitation and also test the correct-object-absent case.",
            "The existing actor normalizer leaves 'the controller'/'The controller' vs 'Controller' at raw similarity about 0.4272, below theta=0.8; R4 deliberately does not add a synonym/role normalization.",
            "Winter natively does not support before/prior-to relations; its out_of_order cells remain unknown and are reused from R2.",
            "Definition 6 C-scope has a literal-formula/prose ambiguity around business objects; R4 preserves the frozen union and reports a minimal discriminating example.",
        ],
        "D_evidence_gaps": [
            "No unresolved evidence gap remains for the changed R4 cells: action mappings, candidate IDs, raw scores, gamma/theta, and order diagnostics are saved.",
            "The evaluation remains development/retrospective because the same data have been reused for multiple diagnostics; it is not independent test or formal Table-3 acceptance.",
        ],
    }


def _conclusions() -> dict[str, Any]:
    return {
        "fixed_implementation_or_interface": [
            "Sun/Ours action comparisons now use action_surface on both sides across Definitions 4, 5, 6 internal action gating, and 7.",
            "article18p3 order endpoints now map (before: informed/inform; after: lifted/lift), and correct/reverse model order is distinguished by reachability.",
            "Mechanism check now separates implementation-contract checks, behaviour probes, and known-limitation reproductions, and exits non-zero on failure.",
            "Backend selection is explicit and validated before scoring.",
            "Order-unknown diagnostics separate no edge, projection rejection (including multiple predicates), endpoint parse failure, missing model action field, below-gamma, other mapping/reachability, and Winter native unsupported.",
        ],
        "remaining_frozen_upstream_errors": [
            "Ours article13p3/article14p4 actor and actor-action association loss after D1 canonicalization.",
            "Ours article13p3 fragmented action.",
            "Missing order relations in the frozen rule extraction for some rules.",
        ],
        "method_limitations": [
            "Action-surface-only cannot reject same-verb/different-object candidates.",
            "Role strings such as 'the controller' and 'Controller' remain below theta without a normalization rule; R4 does not add one.",
            "Some rule actions are below gamma against all model action surfaces; R4 retains unknown rather than inventing actions.",
            "Winter native order checking remains unsupported for before/prior-to semantics.",
        ],
        "supported_by_current_data": [
            "R4 increased Sun order coverage from 0.64 to 0.70 and produced TP=1 for out_of_order while keeping FP=0.",
            "R4 increased Ours order coverage from 0.52 to 0.64 and produced TP=1 for out_of_order while keeping FP=0.",
            "The mechanism check passes implementation contracts and behaviour probes in the synthetic development fixtures.",
        ],
        "not_supported_by_current_data": [
            "Ours > Sun > Winter is not supported by the R4 overall F1 values.",
            "R4 does not make Sun/Ours actor detection generally correct; actor F1 remains 0.4706 for Sun and 0.4286 for Ours.",
            "R4 does not recover missing Stage2 actor/action information and should not be described as doing so.",
        ],
    }


def build(validation_json: Path | None = None) -> dict[str, Any]:
    m1_report = _load_json(M1_REPORT)
    r4_report = _load_json(R4_REPORT)
    m1_pred = _load_json(M1_PRED)
    r4_pred = _load_json(R4_PRED)
    m1_rules = _load_json(M1_RULE_RECORDS)
    r4_rules = _load_json(R4_RULE_RECORDS)
    r4_manifest = _load_json(R4_MANIFEST)
    reference = _load_json(REFERENCE)
    sidecars = _sidecar_by_case()
    mechanism = _load_json(MECHANISM) if MECHANISM.is_file() else {}
    validation = _load_json(validation_json) if validation_json and Path(validation_json).is_file() else {}

    m1_metrics = _method_metrics(m1_report)
    r4_metrics = _method_metrics(r4_report)
    report = {
        "schema_version": "stage3_table3_r4_targeted_delivery@1.0.0",
        "task_id": "S3-TABLE3-R4-TARGETED-FIX",
        "status": "development_retrospective_not_independent_test_complete",
        "development_status": "development_retrospective_not_independent_test",
        "scope_boundary": {
            "new_stage3_methods_run": ["sun", "ours"],
            "winter": "reused_from_r2_not_rerun",
            "data_changed": False,
            "labels_changed": False,
            "thresholds_changed": False,
            "denominators_changed": False,
            "api_calls": 0,
            "env_read": False,
        },
        "methods": {
            "m1": m1_metrics,
            "r4": r4_metrics,
        },
        "metric_deltas_m1_to_r4": {
            method: {
                "overall": {
                    field: (r4_metrics[method]["overall"].get(field) - m1_metrics[method]["overall"].get(field)
                            if isinstance(r4_metrics[method]["overall"].get(field), (int, float))
                            and isinstance(m1_metrics[method]["overall"].get(field), (int, float)) else None)
                    for field in ("tp", "fp", "fn", "tn", "precision", "recall", "f1",
                                  "observable_coverage", "unknown_positive", "unknown_negative")
                }
            } for method in ("sun", "ours", "winter")
        },
        "decision_changes": _decision_changes(m1_report, r4_report, m1_pred, r4_pred,
                                              m1_rules, r4_rules, reference),
        "article18p3_chain": _article18_chain(m1_pred, r4_pred, m1_rules, r4_rules, sidecars),
        "actor_evidence": {
            "m1_sun_false_positives": _m1_actor_fp_rows(m1_pred, reference),
            "r4_false_positives": _r4_actor_fp_rows(r4_pred, reference),
            "surface_equivalent_role_diagnostic": {
                "rule_actor_examples": ["the controller", "The controller"],
                "model_candidate_examples": ["Controller"],
                "m1_raw_similarity": 0.4271531105041504,
                "r4_raw_similarity": 0.4271531105041504,
                "theta": 0.8,
                "difference": "article + capitalization; frozen parser/lemma has no role normalization",
                "effect": "the candidate remains below theta and drives the observed actor false positives",
            },
            "counterfactual_diagnostic": {
                "source": "diagnostic_counterfactual",
                "exclude_business_object_candidates": True,
                "m1": {
                    "sun": _counterfactual_summary(m1_pred, "sun", m1_mode=True),
                    "ours": _counterfactual_summary(m1_pred, "ours", m1_mode=True),
                },
                "r4": {
                    "sun": _counterfactual_summary(r4_pred, "sun", m1_mode=False),
                    "ours": _counterfactual_summary(r4_pred, "ours", m1_mode=False),
                },
                "not_mixed_into_main_metrics": True,
            },
            "definition6_C_scope_check": _definition6_check(),
        },
        "order_unknown_diagnostics": _order_unknown_diagnostics(r4_report, r4_pred),
        "frozen_stage2_residual_loss": _stage2_residual_loss(r4_rules, r4_pred),
        "ranking_analysis": _ranking_analysis(m1_metrics, r4_metrics),
        "attribution": _attribution(),
        "conclusions": _conclusions(),
        "mechanism_check": {
            "path": _rel(MECHANISM),
            "status": mechanism.get("status"),
            "summary": mechanism.get("summary"),
            "implementation_contract_checks": mechanism.get("implementation_contract_checks"),
            "behaviour_probes": mechanism.get("behavior_probes"),
            "known_limitation_reproductions": mechanism.get("known_limitation_reproductions"),
            "capability_acceptance_note": mechanism.get("capability_acceptance_note"),
        },
        "validation": validation,
        "run_manifest": {
            "path": _rel(R4_MANIFEST),
            "sha256": _sha_file(R4_MANIFEST),
            "run_id": r4_manifest.get("run_id"),
            "git": r4_manifest.get("git"),
            "outputs": r4_manifest.get("outputs"),
            "inputs": r4_manifest.get("inputs"),
            "action_match_policy": (r4_manifest.get("r4_action_matching") or {}).get("policy"),
            "order_diagnostic_policy": r4_manifest.get("order_diagnostic_policy"),
            "post_run_metadata_repair": r4_manifest.get("post_run_metadata_repair"),
        },
        "report_source_hashes": {
            "m1_report": _sha_file(M1_REPORT),
            "r4_eval_report": _sha_file(R4_REPORT),
            "r4_predictions": _sha_file(R4_PRED),
            "r4_rule_records": _sha_file(R4_RULE_RECORDS),
            "reference": _sha_file(REFERENCE),
        },
    }
    _write_json(OUT_JSON, report)
    _write_markdown(OUT_MD, report)
    _write_final_manifest(report)
    return report


def _write_final_manifest(report: Mapping[str, Any]) -> None:
    r4 = ((report.get("methods") or {}).get("r4") or {})
    manifest = {
        "schema_version": "stage3_table3_r4_targeted_delivery_manifest@1.0.0",
        "status": report.get("status"),
        "task_id": report.get("task_id"),
        "development_status": report.get("development_status"),
        "inputs": {
            "eval_report": {"path": _rel(R4_REPORT), "sha256": _sha_file(R4_REPORT)},
            "run_manifest": {"path": _rel(R4_MANIFEST), "sha256": _sha_file(R4_MANIFEST)},
            "r4_predictions": {"path": _rel(R4_PRED), "sha256": _sha_file(R4_PRED)},
            "reference": {"path": _rel(REFERENCE), "sha256": _sha_file(REFERENCE)},
        },
        "outputs": {
            "json": {"path": _rel(OUT_JSON), "sha256": _sha_file(OUT_JSON)},
            "markdown": {"path": _rel(OUT_MD), "sha256": _sha_file(OUT_MD)},
        },
        "counts": {
            method: {
                "tp": (r4.get(method) or {}).get("overall", {}).get("tp"),
                "fp": (r4.get(method) or {}).get("overall", {}).get("fp"),
                "fn": (r4.get(method) or {}).get("overall", {}).get("fn"),
                "tn": (r4.get(method) or {}).get("overall", {}).get("tn"),
                "unknown_positive": (r4.get(method) or {}).get("overall", {}).get("unknown_positive"),
                "unknown_negative": (r4.get(method) or {}).get("overall", {}).get("unknown_negative"),
                "not_applicable_cells": (r4.get(method) or {}).get("overall", {}).get("not_applicable_cells"),
            } for method in ("sun", "ours", "winter")
        },
        "backend": "sm",
        "action_match_policy": "r4_action_surface_only_frozen_lemma",
        "gold_read_by_analysis": True,
        "gold_read_by_inference": False,
        "no_prediction_modification": True,
        "boundary": "development_retrospective_not_independent_test",
    }
    _write_json(FINAL_MANIFEST, manifest)


def _fmt(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _write_markdown(path: Path, report: Mapping[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Stage 3 Table 3 R4 Targeted Fix Delivery")
    lines.append("")
    lines.append(f"- status: `{report.get('status')}`")
    lines.append("- development/retrospective; not independent test or formal Table-3 acceptance.")
    lines.append("- API calls: 0; Winter reused from R2, not rerun.")
    lines.append("")
    lines.append("## M1 vs R4 metrics")
    lines.append("")
    lines.append("| Config | Method | TP | FP | FN | TN | P | R | F1 | Coverage | Unknown+ | Unknown- | N/A |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for config in ("m1", "r4"):
        for method in ("sun", "ours", "winter"):
            m = report["methods"][config][method]["overall"]
            lines.append("| " + " | ".join([
                config, method, _fmt(m.get("tp")), _fmt(m.get("fp")), _fmt(m.get("fn")),
                _fmt(m.get("tn")), _fmt(m.get("precision")), _fmt(m.get("recall")),
                _fmt(m.get("f1")), _fmt(m.get("observable_coverage")),
                _fmt(m.get("unknown_positive")), _fmt(m.get("unknown_negative")),
                _fmt(m.get("not_applicable_cells")),
            ]) + " |")
    lines.append("")
    lines.append("## Per-type R4 counts")
    lines.append("")
    lines.append("| Method | Type | TP | FP | FN | TN | Unknown+ | Unknown- | N/A | P | R | F1 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for method in ("sun", "ours", "winter"):
        for check_type in TYPES:
            c = report["methods"]["r4"][method]["per_type"][check_type]
            lines.append("| " + " | ".join([
                method, check_type, _fmt(c.get("tp")), _fmt(c.get("fp")), _fmt(c.get("fn")),
                _fmt(c.get("tn")), _fmt(c.get("unknown_positive")), _fmt(c.get("unknown_negative")),
                _fmt(c.get("not_applicable_cells")), _fmt(c.get("precision")),
                _fmt(c.get("recall")), _fmt(c.get("f1")),
            ]) + " |")
    lines.append("")
    lines.append("## Decision changes M1 -> R4")
    lines.append("")
    lines.append("| Method | Case | Rule | Type | Ref | M1 | R4 | New raw reason / diagnostic |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in report.get("decision_changes") or []:
        new = row.get("r4_signal") or {}
        diag = (new.get("r4_order_diagnostic") or {}).get("category")
        reason = new.get("reason")
        lines.append("| " + " | ".join([
            str(row.get("method")), str(row.get("case_id")), str(row.get("rule_id")),
            str(row.get("check_type")), str(row.get("reference")), str(row.get("m1_status")),
            str(row.get("r4_status")), str(diag or reason),
        ]) + " |")
    lines.append("")
    lines.append("## article18p3 chain")
    lines.append("")
    for case_label, case in (report.get("article18p3_chain") or {}).get("cases", {}).items():
        lines.append(f"### {case_label} (`{case.get('case_id')}`)")
        lines.append("")
        for method, data in (case.get("methods") or {}).items():
            lines.append(f"- {method}: M1={_fmt((data.get('m1_final') or {}).get('status'))}, "
                         f"R4={_fmt((data.get('r4_final') or {}).get('status'))}, "
                         f"gamma={data.get('gamma')}, theta={data.get('theta')}")
            for ep in data.get("endpoints") or []:
                lines.append(f"  - {ep.get('side')}: original `{ep.get('original_endpoint_text')}`; "
                             f"action_surface `{(ep.get('p2_fields') or {}).get('action_surface')}`; "
                             f"R4 selected `{(ep.get('r4_actual_action_comparison') or {}).get('selected_node_id')}` "
                             f"score `{_fmt((ep.get('r4_actual_action_comparison') or {}).get('selected_similarity'))}`; "
                             f"M1 selected `{(ep.get('m1_actual_action_comparison') or {}).get('selected_node_id')}` "
                             f"score `{_fmt((ep.get('m1_actual_action_comparison') or {}).get('selected_similarity'))}`")
        lines.append("")
    lines.append("## Actor evidence and diagnostic counterfactual")
    lines.append("")
    lines.append(f"- M1 Sun actor false-positive rows: {len(report['actor_evidence']['m1_sun_false_positives'])}")
    lines.append(f"- R4 actor false-positive rows: {len(report['actor_evidence']['r4_false_positives'])}")
    for source, methods in (report["actor_evidence"]["counterfactual_diagnostic"].items()):
        if source in ("source",):
            continue
        if isinstance(methods, Mapping):
            for method, summary in methods.items():
                if isinstance(summary, Mapping):
                    lines.append(f"- {source}/{method}: observable={summary.get('observable_actor_signals')}, "
                                 f"changed={summary.get('changed_signals')}, "
                                 f"business_object_was_minimum={summary.get('business_object_was_minimum_count')}, "
                                 f"empty_remaining_C={summary.get('remaining_candidate_empty_count')}")
    lines.append("")
    lines.append("## Frozen Stage2 residual loss")
    lines.append("")
    for rule_id, row in (report["frozen_stage2_residual_loss"].get("ours_actor_loss") or {}).items():
        lines.append(f"- {rule_id}: raw contains actor=`{row.get('raw_response_contains_actor_the_controller')}`, "
                     f"canonical actors=`{row.get('canonical_record_actors')}`, "
                     f"canonical actor-action map=`{row.get('canonical_record_actor_action_map')}`")
    lines.append("")
    lines.append("## Ranking analysis")
    lines.append("")
    lines.append(f"- supports Ours > Sun > Winter: `{report['ranking_analysis']['supports_ours_gt_sun_gt_winter']}`")
    lines.append(f"- actual overall F1: `{report['ranking_analysis']['actual_overall_f1']}`")
    lines.append(f"- {report['ranking_analysis']['explanation']}")
    lines.append("")
    lines.append("## Classification")
    lines.append("")
    for section, rows in (report.get("attribution") or {}).items():
        lines.append(f"### {section}")
        for row in rows:
            lines.append(f"- {row}")
    lines.append("")
    lines.append("## Conclusions")
    lines.append("")
    for section, rows in (report.get("conclusions") or {}).items():
        lines.append(f"### {section}")
        for row in rows:
            lines.append(f"- {row}")
    lines.append("")
    lines.append("## Validation")
    lines.append("")
    validation = report.get("validation") or {}
    if validation.get("commands"):
        for cmd in validation["commands"]:
            lines.append(f"- `{cmd.get('command')}` -> exit `{cmd.get('exit_code')}`: {cmd.get('summary')}")
    else:
        lines.append("- See final handoff for focused validation commands and results; no full-suite authorization.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-json", type=Path, default=None)
    args = parser.parse_args(argv)
    build(validation_json=args.validation_json)
    print(json.dumps({
        "json": _rel(OUT_JSON),
        "markdown": _rel(OUT_MD),
        "decision_changes": len(_load_json(OUT_JSON).get("decision_changes") or []),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
