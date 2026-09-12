# -*- coding: utf-8 -*-
"""Run the SIM card case (S3.9-EXT-REAL-CASE): groups A / B / C plus repair controls.

Zero LLM/API.  Predictions are written before the development reference
judgments are read; the reference judgments never enter the rule side.

Usage (from ``formal_experiment/``):
    python scripts/run_sim_case_c1_v1.py [--overwrite] [--check] [--replay]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from bpc_hybrid import sim_case_c1 as core  # noqa: E402
from bpc_hybrid.sim_case_c1_transforms import (  # noqa: E402
    flatten_collaboration, repair_variant, repair_variant_r8_task_scoped_legacy,
)

RUN_DIR = ROOT / "outputs" / "development" / "sim_case_c1" / "run_v1"
LOCAL_MODELS = ROOT / "outputs" / "development" / "sim_case_c1" / "models"
REPORT_JSON = ROOT / "outputs" / "reports" / "sim_case_c1_results.json"
REPORT_MD = ROOT / "outputs" / "reports" / "sim_case_c1_results.md"

LENS_MAP = {  # declared comparison mapping (comparison stage only, never fed to detection)
    "r8": {"primary": "constraint_violated", "secondary": ["required_condition_not_enforced"]},
    "r9": {"primary": "missing_action", "secondary": []},
    "r10": {"primary": "incorrect_actor", "secondary": []},
    "r11": {"primary": "out_of_order", "secondary": ["required_condition_not_enforced"]},
    "r13": {"primary": "required_condition_not_enforced", "secondary": ["constraint_violated"]},
}
GAMMA_EXT = 0.5
LABEL_FALLBACK_GAMMA = 0.4  # REPAIR-V2 arm C configuration
BASELINE_CAPSULE = ROOT / "outputs" / "development" / "sim_case_c1" / "stage2_baseline_v1" / "capsule.json"


def _load_baseline_capsule() -> tuple[Path, dict]:
    if not BASELINE_CAPSULE.exists():
        raise SystemExit(
            "group A baseline capsule missing: run "
            "`python scripts/run_sim_case_stage2_baseline_v1.py --overwrite` first")
    return BASELINE_CAPSULE, json.loads(BASELINE_CAPSULE.read_text(encoding="utf-8"))


def stage2_group_a_baseline(rule_id: str, rule_text: str, baseline: dict) -> dict:
    """Group A Stage 2 = the project's locked non-LLM baseline capsule row."""
    import sys as _sys

    _sys.path.insert(0, str(ROOT / "src"))
    from bpc_hybrid.gdpr_s2_s3_projection import project_external_sentence

    sample_id = f"sim_{rule_id}_v2"
    row = next((r for r in baseline.get("records", []) if r.get("sample_id") == sample_id), None)
    if row is None:
        return {"ok": False, "error": "baseline_row_missing", "sentence": None}
    projected = project_external_sentence(row, rule_text, sample_id)
    if not projected.get("ok"):
        return {"ok": False, "error": projected.get("error"), "sentence": None,
                "diagnostics": projected.get("diagnostics")}
    return {"ok": True, "error": None, "sentence": projected["sentence"],
            "diagnostics": projected.get("diagnostics"),
            "source": "sun_rule_only_b0_v10a"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write(path: Path, text: str, overwrite: bool) -> dict:
    if path.exists() and not overwrite:
        raise SystemExit(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return {"path": str(path.relative_to(core.REPO)).replace("\\", "/"),
            "sha256": _sha(text), "bytes": len(text.encode("utf-8"))}


def _load_nlp():
    import spacy
    return spacy.load("en_core_web_sm")


def _sun_thresholds() -> dict:
    config = core.load_json(core.SUN_CONFIG)
    thresholds = config["method"]["thresholds"]
    return {"tau": float(thresholds["tau"]), "gamma": float(thresholds["gamma"]),
            "theta": float(thresholds["theta"])}


def _parse_flattened(payload: bytes, label: str, contract_config: Path,
                     already_flattened: bool = False) -> dict:
    """Parse a model view with the frozen Stage 1 contract.

    ``already_flattened`` must be True for repair variants, which are produced
    FROM the flattened original: flattening twice would re-wrap lanes and add a
    second, unintended adaptation step.
    """
    import xml.etree.ElementTree as ET

    from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes, validate_process_record

    if already_flattened:
        flattened, info = payload, {"transform": "already_flattened", "reason": "repair input"}
    else:
        flattened, info = flatten_collaboration(payload)
    contract = load_stage1_contract(contract_config)
    record = parse_bpmn_bytes(flattened, source_path=f"{label}.bpmn", contract=contract)
    validation = validate_process_record(record)
    if not getattr(validation, "valid", False):
        raise SystemExit(f"{label}: stage1 record invalid: {validation}")
    return {
        "label": label,
        "record": record,
        "xml_root": ET.fromstring(flattened),
        "flattened_xml": flattened,
        "flatten_info": info,
        "evidence": {
            "flattened_xml_sha256": core.sha256_bytes(flattened),
            "process_record_sha256": _sha(json.dumps(record, sort_keys=True, ensure_ascii=False)),
            "activities": len(record.get("activities", [])),
            "gateways": len(record.get("gateways", [])),
            "events": len(record.get("events", [])),
            "flows": len(record.get("sequence_flows", [])),
            "lanes": [lane.get("name") for lane in record.get("lanes", [])],
        },
    }


def _group_rows(scorers: dict, sentence: dict, model, stage1: dict, rule: dict) -> dict:
    three = core.run_three_types(scorers["sun"], rule, model)
    rows = {"three_types": three}
    return rows


def _extended_rows(scorers: dict, sentence: dict, model, stage1: dict, rule: dict) -> dict:
    activity_id, activity_sim, activity_name = core.best_activity_for(sentence, model, scorers["sim"])
    rows, surfaces, raw = core.run_extended_types(scorers["ext"], sentence, model, stage1["record"],
                                                  stage1["xml_root"], activity_id)
    gate = scorers["gate"](raw, GAMMA_EXT)
    return {"extended": rows, "surfaces": surfaces, "gate": gate,
            "mapped_activity": {"id": activity_id, "name": activity_name, "similarity": activity_sim}}


def _rule_side(rule_id: str, rule_text: str, group: str, context: dict) -> dict:
    if group == "A":
        outcome = stage2_group_a_baseline(rule_id, rule_text, context["baseline"])
    else:
        outcome = core.stage2_group_b(rule_id, rule_text, context["predictions"])
    if not outcome.get("ok"):
        return {"ok": False, "error": outcome.get("error"), "sentence": None, "rule": None}
    sentence = core.apply_role_binding(outcome["sentence"])
    sentence["rule_id"] = rule_id
    if not sentence.get("sentence_text"):
        sentence["sentence_text"] = rule_text
    rule = core.build_rule_record(sentence)
    return {"ok": True, "error": None, "sentence": sentence, "rule": rule,
            "stage2_meta": {k: v for k, v in outcome.items() if k not in ("sentence",)}}


def _compare_records(rule_a: dict, rule_b: dict, chain: dict | None = None) -> dict:
    fields = ["modality", "actions", "actors", "actor_action_pairs", "order_relations",
              "condition", "constraint", "exception"]
    diff = {f: {"A": rule_a.get(f), "B": rule_b.get(f)}
            for f in fields if rule_a.get(f) != rule_b.get(f)}
    adaptation_loss = []
    if chain:
        for group in ("A", "B"):
            flows = ((chain.get("groups") or {}).get(group) or {}).get("field_flow") or {}
            for field, flow in flows.items():
                verdict = flow.get("verdict")
                if verdict in ("partially_carried_by_declared_policy", "lost_in_adaptation"):
                    adaptation_loss.append({
                        "group": group,
                        "field": field,
                        "verdict": verdict,
                        "raw_count": flow.get("raw_count"),
                        "projected_count": flow.get("projected_candidate_count"),
                        "adapted_count": flow.get("adapted_record_count"),
                    })
    has_diff = bool(diff)
    if has_diff and adaptation_loss:
        attribution = "extraction_with_adaptation_loss"
    elif adaptation_loss:
        attribution = "adaptation_loss_without_a_to_b_value_change"
    elif has_diff:
        attribution = "extraction"
    else:
        attribution = "none"
    return {
        "changed_fields": sorted(diff),
        "detail": diff,
        "difference_attribution": "extraction" if has_diff else "none",
        "attribution": attribution,
        "adaptation_loss": adaptation_loss,
        "note_zh": (
            "changed_fields 的 A→B 直接差异来自两次抽取；adaptation_loss 另行记录"
            "每个组内原始抽取→投影→规则记录的截断/丢失，不能笼统说差异全部来自抽取。"
        ),
    }


def _sanitise_attribution(attribution: dict) -> dict:
    clean = {}
    for rule_id, block in attribution.items():
        if not block:
            clean[rule_id] = block
            continue
        detail = {}
        for field, values in (block.get("detail") or {}).items():
            detail[field] = {side: _fragment(value) for side, value in values.items()}
        clean[rule_id] = {
            "changed_fields": block.get("changed_fields", []),
            "difference_attribution": block.get("difference_attribution"),
            "attribution": block.get("attribution"),
            "adaptation_loss": block.get("adaptation_loss", []),
            "detail_fragments": detail,
            "note_zh": block.get("note_zh"),
        }
    return clean


def _fragment(value) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    text = " ".join(text.split())
    return f"{text[:30]}…(sha256 {_sha(text)[:12]})" if len(text) > 30 else text


def _redact_for_report(value):
    """Keep short labels/scores, fragment long rule-side text.

    The local capsule retains the complete evidence.  Committable reports must
    not contain restricted requirement text, so long strings are replaced by a
    30-character fragment plus a hash.  This changes presentation only, never
    the detector output or the capsule evidence.
    """
    if isinstance(value, dict):
        return {key: _redact_for_report(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_for_report(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_for_report(item) for item in value]
    if isinstance(value, str) and len(value) > 30:
        return _fragment(value)
    return value


def _id_of(model, name: str) -> str | None:
    return next((a["id"] for a in model.actions if (a.get("name") or "") == name), None)


def _lane_of_record(record: dict, node_id: str) -> str | None:
    for lane in record.get("lanes", []):
        if node_id in (lane.get("flow_node_refs") or []):
            return lane.get("name")
    return None


def verify_repair(repair_id: str, repaired: dict, model) -> dict:
    """Independent structural verification of a repaired model.

    This function does not ask the detector.  For r8 it distinguishes the
    valid process-level event-subprocess timeout from the rejected
    task-scoped precursor and records whether the frozen Stage-1
    representation can carry the relevant semantics into detection.
    """
    import xml.etree.ElementTree as ET

    root = ET.fromstring(repaired["flattened_xml"])
    tag = lambda e: e.tag.split("}")[1]  # noqa: E731
    process = next((e for e in root if tag(e) == "process"), None)
    evidence: dict = {}

    if repair_id in ("r8_timeout_termination", "r8_timeout_termination_task_scoped_legacy"):
        if process is None:
            return {"fix_expressed": False, "reason": "process_element_missing"}
        if repair_id == "r8_timeout_termination":
            sub = next((e for e in process if tag(e) == "subProcess"
                        and (e.get("triggeredByEvent") or "").lower() == "true"), None)
            start_event = next((e for e in (list(sub) if sub is not None else []) if tag(e) == "startEvent"), None)
            timer_def = next((e for e in (list(start_event) if start_event is not None else []) if tag(e) == "timerEventDefinition"), None)
            duration = next((e for e in (list(timer_def) if timer_def is not None else []) if tag(e) == "timeDuration"), None)
            end_event = next((e for e in (list(sub) if sub is not None else []) if tag(e) == "endEvent"), None)
            terminate_def = next((e for e in (list(end_event) if end_event is not None else []) if tag(e) == "terminateEventDefinition"), None)
            duration_text = (duration.text or "").strip() if duration is not None else None
            inner_flows = [e for e in (list(sub) if sub is not None else []) if tag(e) == "sequenceFlow"]
            timer_to_end = any(
                f.get("sourceRef") == (start_event.get("id") if start_event is not None else None)
                and f.get("targetRef") == (end_event.get("id") if end_event is not None else None)
                for f in inner_flows
            )
            stage1_activity_ids = {a["id"] for a in repaired["record"].get("activities", [])}
            stage1_event_ids = {e["id"] for e in repaired["record"].get("events", [])}
            timer_surface_visible = False
            try:
                from bpc_hybrid.stage3_extended_violations import constraint_candidates
                surface = [str(item) for item in constraint_candidates(repaired["record"], root, None)]
                timer_surface_visible = any("P30D" in item or "30" in item or "day" in item.lower()
                                            for item in surface)
                surface_fragment = [item for item in surface if "P30D" in item or "30" in item][:5]
            except Exception as exc:  # verification must not fail because a diagnostic import changed
                surface_fragment = []
                timer_surface_visible = bool(duration_text)
                evidence["constraint_surface_error"] = type(exc).__name__
            mechanism_valid = all([
                sub is not None,
                start_event is not None,
                timer_def is not None,
                bool(duration_text),
                end_event is not None,
                terminate_def is not None,
                timer_to_end,
                (start_event.get("isInterrupting") if start_event is not None else None) != "false",
            ])
            evidence = {
                "repair_id": repair_id,
                "mechanism": "process_level_event_subprocess_timer_terminate",
                "event_subprocess": sub is not None,
                "event_subprocess_is_process_child": sub in list(process),
                "timer_start_event": start_event is not None,
                "timer_definition": timer_def is not None,
                "timer_duration": duration_text,
                "timer_starts_with_process_scope": bool(sub is not None and timer_def is not None),
                "interrupting": (start_event.get("isInterrupting") if start_event is not None else None),
                "terminate_end_event": end_event is not None,
                "terminate_definition": terminate_def is not None,
                "timer_to_terminate_flow": timer_to_end,
                "scope": "process_instance",
                "scope_matches_rule_semantics": mechanism_valid,
                "no_task_attachment": not any(
                    tag(e) == "boundaryEvent" and e.get("attachedToRef") for e in process
                ),
                "stage1_record_representation": {
                    "subprocess_activity_present": (sub.get("id") if sub is not None else None) in stage1_activity_ids,
                    "timer_start_event_in_record": (start_event.get("id") if start_event is not None else None) in stage1_event_ids,
                    "terminate_end_event_in_record": (end_event.get("id") if end_event is not None else None) in stage1_event_ids,
                    "stage1_subprocess_handling": "opaque_activity_no_internal_flattening",
                },
                "detector_surface": {
                    "timer_text_visible_in_constraint_candidates": timer_surface_visible,
                    "surface_fragment": surface_fragment,
                    "scope_and_termination_link_visible_as_structured_fields": False,
                },
                "semantics_entered_detection_surface": timer_surface_visible,
                "semantics_entered_detection_chain": False,
                "excluded_from_effective_repair_denominator": True,
                "exclusion_reason_zh": (
                    "过程级事件子流程在冻结 Stage 1 中是 opaque activity；计时器/终止定义及"
                    "其流程级作用域没有进入结构化 Process Record，因此不能把修复后检测结果"
                    "解释为方法能力。"
                ),
                "fix_expressed": mechanism_valid,
                "repair_semantics_valid": mechanism_valid,
            }
        else:
            anchor = next((e for e in process.iter()
                           if tag(e) == "task" and (e.get("name") or "") == "Send SIM card"), None)
            boundary = next((e for e in process if tag(e) == "boundaryEvent"
                             and e.get("attachedToRef") == (anchor.get("id") if anchor is not None else None)), None)
            timer = next((e for e in (list(boundary) if boundary is not None else []) if tag(e) == "timerEventDefinition"), None)
            target_id = boundary.get("id") if boundary is not None else None
            termination = any(
                f.get("sourceRef") == target_id and f.get("targetRef") and any(
                    e.get("id") == f.get("targetRef") and tag(e) == "endEvent" for e in process
                )
                for f in process if tag(f) == "sequenceFlow"
            )
            evidence = {
                "repair_id": repair_id,
                "mechanism": "task_scoped_boundary_timer_legacy",
                "attached_to": "Send SIM card" if anchor is not None else None,
                "boundary_event": boundary is not None,
                "timer_definition": timer is not None,
                "has_termination_path": termination,
                "scope": "task_scoped_timeout",
                "scope_matches_rule_semantics": False,
                "fix_expressed": False,
                "repair_semantics_valid": False,
                "semantics_entered_detection_chain": True,
                "excluded_from_effective_repair_denominator": True,
                "exclusion_reason_zh": (
                    "旧修复件只在 Send SIM card 任务上挂计时器，不能表达整个入网流程超过 30 天即终止；"
                    "保留为部分/无效对照。"
                ),
            }
        return evidence

    if repair_id == "r9_add_verification":
        target = _id_of(model, "Verify correctness of customer personal data")
        before = _id_of(model, "Request personal data")
        after = _id_of(model, "Sign contract")
        evidence = {
            "activity_present": target is not None,
            "reachable_from_request_personal_data": bool(target and before and model.is_reachable(before, target)),
            "reaches_sign_contract": bool(target and after and model.is_reachable(target, after)),
        }
        evidence["fix_expressed"] = all(evidence.values())
    elif repair_id == "r10_activation_owner":
        activity = _id_of(model, "Activate SIM card")
        lane = _lane_of_record(repaired["record"], activity) if activity else None
        evidence = {"activity": "Activate SIM card", "lane": lane, "expected_lane": "Phone company"}
        evidence["fix_expressed"] = lane == "Phone company"
    elif repair_id == "r11_consent_before_retrieval":
        consent = _id_of(model, "Ask for consent")
        retrieval = _id_of(model, "Request personal data")
        evidence = {
            "consent_reaches_retrieval": bool(consent and retrieval and model.is_reachable(consent, retrieval)),
            "retrieval_reaches_consent": bool(consent and retrieval and model.is_reachable(retrieval, consent)),
        }
        evidence["fix_expressed"] = evidence["consent_reaches_retrieval"] and not evidence["retrieval_reaches_consent"]
    elif repair_id == "r13_threshold_50":
        labels = [f.get("name") for f in root.iter() if tag(f) == "sequenceFlow" and f.get("name")]
        evidence = {
            "labels": labels,
            "old_label_present": "Debt < 100" in labels,
            "new_label_present": "Debt <= 50" in labels,
            "semantic_note_zh": "Debt <= 50 排除超过 50 的客户，且不单独证明其他入网条件满足。",
        }
        evidence["fix_expressed"] = evidence["new_label_present"] and not evidence["old_label_present"]
    else:
        return {"fix_expressed": False, "repair_semantics_valid": False, "reason": "unknown repair"}

    evidence.setdefault("scope", "rule_element_scope")
    evidence.setdefault("scope_matches_rule_semantics", True)
    evidence["repair_semantics_valid"] = bool(evidence.get("fix_expressed"))
    evidence["semantics_entered_detection_chain"] = True
    evidence["excluded_from_effective_repair_denominator"] = False
    return evidence


FIELD_TRACE_FIELDS = ("actions", "actors", "conditions", "constraints",
                     "exceptions", "order_relations")
FIELD_SINGULAR = {"actions": "action", "actors": "actor", "conditions": "condition",
                  "constraints": "constraint", "exceptions": "exception",
                  "order_relations": "order_relations"}
RULE_CONSUMER = {"actions": "action", "actors": "actor", "conditions": "condition",
                 "constraints": "constraint", "exceptions": "exception",
                 "order_relations": "order_relations"}


def _clauses(row: dict | None) -> list[dict]:
    return list(((row or {}).get("record") or {}).get("clauses") or [])


def _raw_field_spans(clause: dict, field: str) -> list:
    entry = clause.get(field)
    if isinstance(entry, dict) and isinstance(entry.get("spans"), list):
        return list(entry["spans"])
    if isinstance(entry, list):
        return list(entry)
    singular = FIELD_SINGULAR[field]
    value = clause.get(singular)
    return list(value) if isinstance(value, list) else []


def _span_text_local(span) -> str | None:
    if isinstance(span, dict):
        text = span.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    if isinstance(span, str) and span.strip():
        return span.strip()
    return None


def _raw_field_inventory(row: dict | None) -> dict:
    clauses = _clauses(row)
    counts = {field: 0 for field in FIELD_TRACE_FIELDS}
    texts = {field: [] for field in FIELD_TRACE_FIELDS}
    invalid = {field: 0 for field in FIELD_TRACE_FIELDS}
    for clause in clauses:
        for field in FIELD_TRACE_FIELDS:
            for span in _raw_field_spans(clause, field):
                counts[field] += 1
                text = _span_text_local(span)
                if text:
                    texts[field].append(text)
                else:
                    invalid[field] += 1
    actor_action_map = []
    for clause in clauses:
        for entry in clause.get("actor_action_map") or []:
            if isinstance(entry, dict):
                actor_action_map.append({
                    "actor_id": entry.get("actor_id"),
                    "action_id": entry.get("action_id"),
                })
            else:
                actor_action_map.append({"raw": repr(entry)})
    return {
        "clause_count": len(clauses),
        "raw_counts": counts,
        "valid_span_counts": {field: len(texts[field]) for field in FIELD_TRACE_FIELDS},
        "invalid_span_counts": invalid,
        "texts": texts,
        "actor_action_map": actor_action_map,
        "actor_action_map_count": len(actor_action_map),
    }


def _projected_field_inventory(sentence: dict | None) -> dict:
    diagnostics = (sentence or {}).get("diagnostics") or {}
    field_texts = diagnostics.get("span_field_texts") or {}
    return {
        "field_texts": {field: list(field_texts.get(RULE_CONSUMER[field]) or []) for field in FIELD_TRACE_FIELDS},
        "counts": {field: len(field_texts.get(RULE_CONSUMER[field]) or []) for field in FIELD_TRACE_FIELDS},
        "actor_action_map": list(diagnostics.get("actor_action_map") or []),
        "projection_value_policy": diagnostics.get("projection_value_policy"),
    }


def _rule_field_inventory(rule: dict | None) -> dict:
    rule = rule or {}
    return {
        "actions": list(rule.get("actions") or []),
        "actors": list(rule.get("actors") or []),
        "conditions": [rule["condition"]] if rule.get("condition") else [],
        "constraints": [rule["constraint"]] if rule.get("constraint") else [],
        "exceptions": [rule["exception"]] if rule.get("exception") else [],
        "order_relations": list(rule.get("order_relations") or []),
        "actor_action_pairs": list(rule.get("actor_action_pairs") or []),
        "selection_metadata": dict(rule.get("selection_metadata") or {}),
    }


def _field_verdict(field: str, raw_count: int, projected_count: int,
                   adapted_count: int) -> str:
    if field == "order_relations":
        if raw_count == 0 and adapted_count > 0:
            return "derived_by_declared_policy"
        if raw_count == 0 and projected_count == 0 and adapted_count == 0:
            return "not_extracted"
    if raw_count == 0 and projected_count == 0 and adapted_count == 0:
        return "not_extracted"
    if raw_count > 0 and projected_count == 0:
        return "lost_in_adaptation"
    if projected_count > adapted_count or raw_count > adapted_count:
        return "partially_carried_by_declared_policy"
    if adapted_count > 0:
        return "full_carry"
    return "not_extracted"


def _pair_verdict(raw_count: int, projected_valid: int, projected_invalid: int,
                  adapted_count: int) -> str:
    if raw_count == 0 and projected_valid == 0 and adapted_count == 0:
        return "not_extracted"
    if raw_count > 0 and projected_valid == 0 and projected_invalid > 0 and adapted_count == 0:
        return "invalid_in_raw_no_valid_pair"
    if raw_count > 0 and projected_valid == 0 and adapted_count == 0:
        return "lost_in_adaptation"
    if projected_valid > adapted_count or raw_count > adapted_count:
        return "partially_carried_by_declared_policy"
    if adapted_count > 0:
        return "full_carry"
    return "not_extracted"


def _consumption_status(field: str, group: str, projected_count: int,
                        adapted_count: int, consumed_count: int) -> str:
    consumer_expected = field in ("actions", "actors", "order_relations") or group == "C"
    if not consumer_expected:
        return "not_used_by_group_pipeline"
    if adapted_count == 0:
        return "no_value_to_consume"
    if projected_count > consumed_count:
        return "partially_consumed_relative_to_projected"
    if consumed_count >= adapted_count:
        return "fully_consumed"
    if consumed_count > 0:
        return "partially_consumed"
    return "not_consumed"


def _value_change_trace(field: str, raw_values: list, projected_values: list,
                        adapted_values: list, metadata: dict) -> list[dict]:
    """Show concrete value changes, so count equality cannot hide a fallback."""
    changes: list[dict] = []
    selection = (metadata or {}).get("field_selection_policy") or {}
    role_originals: set[str] = set()
    if field == "actors":
        for item in (metadata or {}).get("role_binding_trace") or []:
            original = item.get("actor_original")
            final = item.get("actor_final")
            if original:
                role_originals.add(original)
            if original != final:
                changes.append({
                    "field": field,
                    "direction": "raw_or_projected_to_adapted",
                    "original": original,
                    "final": final,
                    "source": item.get("bound_from"),
                    "binding_applied": item.get("binding_applied"),
                    "selection_policy": selection.get(field),
                    "reason": "declared_role_binding",
                })
    for value in projected_values:
        if field == "actors" and value in role_originals:
            continue
        if value not in adapted_values:
            changes.append({
                "field": field,
                "direction": "projected_to_adapted",
                "original": value,
                "final": None,
                "source": None,
                "binding_applied": False,
                "selection_policy": selection.get(field),
                "reason": "not_selected_or_not_consumed",
            })
    if not (field == "actors" and role_originals):
        for value in adapted_values:
            if value not in projected_values and value not in raw_values:
                changes.append({
                    "field": field,
                    "direction": "adapted_value_not_in_projected_raw",
                    "original": None,
                    "final": value,
                    "source": None,
                    "binding_applied": False,
                    "selection_policy": selection.get(field),
                    "reason": "binding_or_declared_derivation",
                })
    return changes


def build_chain(rule_id: str, rule_text: str, sides: dict, raw_by_group: dict) -> dict:
    """Rule text -> raw extraction -> projection -> adapted rule record -> detector input.

    Counts and verdicts are kept separately.  A field is not ``full_carry``
    merely because some value survived: moving from 2 raw actions to 1 adapted
    action is explicitly ``partially_carried_by_declared_policy``.
    """
    chain = {"rule_id": rule_id, "version": "v2", "rule_text_sha256": _sha(rule_text),
             "rule_text_length": len(rule_text), "groups": {}}
    for group in ("A", "B", "C"):
        side = sides.get(group) or {}
        if not side.get("ok"):
            chain["groups"][group] = {"ok": False, "error": side.get("error")}
            continue
        sentence = side.get("sentence") or {}
        rule = side.get("rule") or {}
        raw = _raw_field_inventory(raw_by_group.get(group))
        projected = _projected_field_inventory(sentence)
        adapted = _rule_field_inventory(rule)
        field_flow = {}
        for field in FIELD_TRACE_FIELDS:
            raw_values = list(raw["texts"].get(field, []))
            projected_values = list(projected["field_texts"].get(field, []))
            adapted_values = list(adapted.get(field) or [])
            raw_count = int(raw["valid_span_counts"].get(field, 0))
            projected_count = int(projected["counts"].get(field, 0))
            adapted_count = len(adapted_values)
            consumer_expected = field in ("actions", "actors", "order_relations") or group == "C"
            consumed_count = adapted_count if consumer_expected else 0
            if field == "actors":
                bound_originals = {
                    item.get("actor_original")
                    for item in ((adapted.get("selection_metadata") or {}).get("role_binding_trace") or [])
                    if item.get("actor_original")
                }
                unconsumed = [value for value in projected_values if value not in bound_originals]
            else:
                unconsumed = [value for value in projected_values if value not in adapted_values]
            field_flow[field] = {
                "raw_count": raw_count,
                "raw_invalid_count": int(raw["invalid_span_counts"].get(field, 0)),
                "projected_candidate_count": projected_count,
                "adapted_record_count": adapted_count,
                "detector_consumed_count": consumed_count,
                "consumer_expected": consumer_expected,
                "consumption_status": _consumption_status(field, group, projected_count,
                                                                            adapted_count, consumed_count),
                "verdict": _field_verdict(field, raw_count, projected_count, adapted_count),
                "selection_policy": (adapted.get("selection_metadata", {}).get("field_selection_policy") or {}).get(field),
                "unconsumed_candidates": unconsumed,
                "raw_values": raw_values,
                "projected_values": projected_values,
                "adapted_values": adapted_values,
                "value_changes": _value_change_trace(
                    field, raw_values, projected_values, adapted_values,
                    adapted.get("selection_metadata") or {},
                ),
            }
        raw_pair_values = list(raw.get("actor_action_map") or [])
        projected_pair_values = list(projected.get("actor_action_map") or [])
        adapted_pair_values = list(adapted.get("actor_action_pairs") or [])
        pair_value_changes = []
        for pair in adapted_pair_values:
            original = pair.get("actor_original")
            final = pair.get("actor")
            if original != final:
                pair_value_changes.append({
                    "direction": "explicit_pair_actor_binding",
                    "actor_original": original,
                    "actor_final": final,
                    "bound_from": pair.get("actor_bound_from"),
                    "binding_applied": pair.get("binding_applied"),
                    "action": pair.get("action"),
                    "actor_id": pair.get("actor_id"),
                    "action_id": pair.get("action_id"),
                    "reason": "declared_role_binding",
                })
        pair_flow = {
            "raw_count": int(raw.get("actor_action_map_count", 0)),
            "projected_count": sum(1 for entry in projected_pair_values if entry.get("valid")),
            "projected_valid_count": sum(1 for entry in projected_pair_values if entry.get("valid")),
            "projected_invalid_count": sum(1 for entry in projected_pair_values if not entry.get("valid")),
            "adapted_count": len(adapted_pair_values),
            "verdict": _pair_verdict(
                int(raw.get("actor_action_map_count", 0)),
                sum(1 for entry in projected_pair_values if entry.get("valid")),
                sum(1 for entry in projected_pair_values if not entry.get("valid")),
                len(adapted_pair_values)),
            "invalid_links": [entry for entry in projected_pair_values if not entry.get("valid")],
            "raw_values": raw_pair_values,
            "projected_values": projected_pair_values,
            "adapted_values": adapted_pair_values,
            "value_changes": pair_value_changes,
        }
        chain["groups"][group] = {
            "ok": True,
            "raw_extraction": raw,
            "projected_record": {
                "counts": projected["counts"],
                "field_texts": projected["field_texts"],
                "actor_action_map": projected["actor_action_map"],
                "projection_value_policy": projected["projection_value_policy"],
            },
            "adapted_record": rule,
            "field_flow": field_flow,
            "actor_action_pair_flow": pair_flow,
            "process_binding": {
                "mapped_activity": side.get("mapped_activity"),
                "surfaces": side.get("surfaces"),
                "candidate_activity_id": (side.get("surfaces") or {}).get("activity_id"),
            },
            "checks": side.get("checks"),
            "gate": side.get("gate"),
        }
    return chain


def _stage1_process_facts(stage1: dict) -> dict:
    record = stage1.get("record") or {}
    xml_root = stage1.get("xml_root")
    tag = lambda e: e.tag.split("}")[1]  # noqa: E731
    lane_name = {lane.get("id"): lane.get("name") for lane in record.get("lanes", [])}
    activities = []
    for act in record.get("activities", []):
        activities.append({
            "id": act.get("id"),
            "name": act.get("name"),
            "lanes": [lane_name.get(lid, lid) for lid in act.get("lane_ids", [])],
        })
    flows = []
    for flow in record.get("sequence_flows", []):
        flows.append({
            "id": flow.get("id"), "name": flow.get("name"),
            "source_ref": flow.get("source_ref"), "target_ref": flow.get("target_ref"),
            "condition_expression": flow.get("condition_expression"),
        })
    xml_counts = {
        "timer_event_definitions": 0,
        "time_durations": 0,
        "boundary_events": 0,
        "terminate_event_definitions": 0,
        "event_subprocesses": 0,
    }
    if xml_root is not None:
        for elem in xml_root.iter():
            local = tag(elem)
            if local == "timerEventDefinition":
                xml_counts["timer_event_definitions"] += 1
            elif local == "timeDuration":
                xml_counts["time_durations"] += 1
            elif local == "boundaryEvent":
                xml_counts["boundary_events"] += 1
            elif local == "terminateEventDefinition":
                xml_counts["terminate_event_definitions"] += 1
            elif local == "subProcess" and (elem.get("triggeredByEvent") or "").lower() == "true":
                xml_counts["event_subprocesses"] += 1
    return {
        "activities": activities,
        "events": [{"id": e.get("id"), "name": e.get("name"), "type": e.get("type")}
                   for e in record.get("events", [])],
        "gateways": [{"id": g.get("id"), "name": g.get("name"), "type": g.get("type")}
                     for g in record.get("gateways", [])],
        "sequence_flows": flows,
        "flow_labels": [flow["name"] for flow in flows if flow.get("name")],
        "xml_counts": xml_counts,
        "condition_expressions": len([f for f in flows if f.get("condition_expression")]),
    }


def _check_row(rule_id: str, group: str, check: str, result: dict,
               inherited_from: str | None = None, added_by: str | None = None) -> dict:
    row = {
        "rule_id": rule_id, "group": group, "check": check,
        "status": result.get("status"),
        "machine_status": result.get("machine_status", result.get("status")),
        "evaluation_status": result.get("evaluation_status", result.get("status")),
        "status_source": result.get("status_source"),
        "evaluation_reason": result.get("evaluation_reason"),
        "score": result.get("score"),
        "denominator": result.get("denominator"),
        "reason": result.get("reason"),
        "observable": result.get("observable"),
        "comparison_performed": result.get("comparison_performed"),
    }
    if inherited_from:
        row["inherited_from"] = inherited_from
    if added_by:
        row["added_by"] = added_by
    return row


def _alarm_compact(name: str, result: dict | None) -> dict:
    result = result or {}
    return {
        "check": name,
        "status": result.get("status"),
        "machine_status": result.get("machine_status", result.get("status")),
        "evaluation_status": result.get("evaluation_status", result.get("status")),
        "score": result.get("score"),
        "reason": result.get("reason"),
        "best_candidate": result.get("best_candidate"),
        "max_sim": result.get("max_sim"),
        "details": result.get("details") or [],
        "process_actor_candidates": result.get("process_actor_candidates") or [],
        "matched_process_action_ids": result.get("matched_process_action_ids") or [],
        "matched_action_owner_evidence": result.get("matched_action_owner_evidence") or [],
        "primary_action_match": result.get("primary_action_match"),
        "primary_action_owner_evidence": result.get("primary_action_owner_evidence") or [],
        "exact_contradiction": result.get("exact_contradiction"),
        "action_resolution": result.get("action_resolution"),
        "resolved_activity_label": result.get("resolved_activity_label"),
        "unresolved_reason": result.get("unresolved_reason"),
    }


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(token in lowered for token in tokens)


def _actor_tokens(text: str) -> set[str]:
    stop = {"the", "a", "an"}
    return {token for token in re.findall(r"[a-z]+", (text or "").lower()) if token not in stop}


def _owner_matches(required: str, owner: str) -> bool:
    return bool(_actor_tokens(required) & _actor_tokens(owner))


def _process_activity_rows(process_facts: dict) -> list[dict]:
    return [
        {"id": item.get("id"), "name": item.get("name"),
         "lanes": list(item.get("lanes") or [])}
        for item in (process_facts.get("activities") or [])
    ]


def _process_name_map(process_facts: dict) -> dict:
    result = {}
    for key in ("activities", "events", "gateways"):
        for item in process_facts.get(key) or []:
            result[item.get("id")] = item.get("name") or item.get("id")
    return result


def _meaningful_tokens(text: str) -> set[str]:
    stop = {"the", "a", "an", "of", "for", "and", "to", "in", "on", "with"}
    return {token for token in re.findall(r"[a-z]+", (text or "").lower())
            if token not in stop and len(token) > 2}


def _alarm_model_side_text(alarm: dict) -> list[tuple[str, str]]:
    """Collect only model-side evidence fields, never rule-action JSON keys."""
    fields: list[tuple[str, str]] = []
    for key in ("best_candidate", "resolved_activity_label"):
        value = alarm.get(key)
        if isinstance(value, str) and value.strip():
            fields.append((key, value.strip()))
    for key in ("details", "matched_action_owner_evidence",
                "primary_action_owner_evidence", "process_actor_candidates"):
        values = alarm.get(key) or []
        for item in values:
            if isinstance(item, dict):
                for subkey in ("best_model_action", "label", "activity_label",
                               "resolved_activity_label"):
                    value = item.get(subkey)
                    if isinstance(value, str) and value.strip():
                        fields.append((key + "." + subkey, value.strip()))
                for owner in item.get("owners") or []:
                    if isinstance(owner, str) and owner.strip():
                        fields.append((key + ".owners", owner.strip()))
            elif isinstance(item, str) and item.strip():
                fields.append((key, item.strip()))
    return fields


def _assess_alarm_correspondence(rule_id: str, group: str, side: dict,
                                 process_facts: dict, reference_item: dict) -> dict:
    """Separate raw machine alarms from evidence-checked reference correspondence.

    The function reads detector rows and process facts after scoring.  It never
    feeds reference judgments back into extraction, rule records, or scoring.
    Each fixed rule has an explicit evidence requirement; matching a type name
    is not sufficient.
    """
    checks = side.get("checks") or {}
    rule = side.get("rule") or {}
    alarms = [_alarm_compact(name, result) for name, result in checks.items()
              if result.get("status") == core.STATUS_VIOLATION]
    activity_rows = _process_activity_rows(process_facts)
    activity_by_id = {row["id"]: row for row in activity_rows}
    activity_names = [row["name"] for row in activity_rows if row.get("name")]
    name_by_id = _process_name_map(process_facts)
    reference_summary = (reference_item.get("semantic_issue") or {}).get("summary_zh") or ""
    matched: list[str] = []
    chain: list[str] = []
    details: dict = {}

    if rule_id == "r8":
        process_xml = (process_facts.get("xml_counts") or {})
        scope_sources = []
        if process_xml.get("event_subprocesses"):
            scope_sources.append("xml_counts.event_subprocesses")
        if process_xml.get("timer_event_definitions"):
            scope_sources.append("xml_counts.timer_event_definitions")
        if process_xml.get("terminate_event_definitions"):
            scope_sources.append("xml_counts.terminate_event_definitions")
        alarm_assessments = []
        for alarm in alarms:
            model_fields = _alarm_model_side_text(alarm)
            time_hits = [(source, value) for source, value in model_fields
                         if re.search(r"\b30\s*days?\b|p30d", value, re.IGNORECASE)]
            term_hits = [(source, value) for source, value in model_fields
                         if re.search(r"\b(?:terminate|terminated|termination)\b", value, re.IGNORECASE)]
            scope_hits = [(source, value) for source, value in model_fields
                          if re.search(r"\b(?:process|scope|instance)\b", value, re.IGNORECASE)]
            all_hits = bool(time_hits and term_hits and scope_sources)
            alarm_assessments.append({
                "check": alarm["check"],
                "time_evidence_sources": [{"source": s, "value": v} for s, v in time_hits],
                "termination_evidence_sources": [{"source": s, "value": v} for s, v in term_hits],
                "process_scope_sources": scope_sources,
                "same_alarm_model_scope_mentions": [{"source": s, "value": v} for s, v in scope_hits],
                "corresponds": all_hits,
            })
            if all_hits:
                matched.append(alarm["check"])
                chain.append(
                    "{}: model-side time evidence {}, termination evidence {}, "
                    "process-scope facts {}. This alarm has evidence for the fixed r8 issue.".format(
                        alarm["check"], time_hits, term_hits, scope_sources)
                )
            else:
                chain.append(
                    "{}: machine alarm retained, but no model-side alarm value supplies "
                    "an actual 30-day bound or terminate label; process-scope fields are {}. "
                    "Reference correspondence remains unverified.".format(
                        alarm["check"], scope_sources or "absent")
                )
        if not matched:
            chain.append(
                "r8 requires time, termination, and process-scope evidence from explicit sources; "
                "keyword co-occurrence in the alarm object is not used."
            )
        details = {
            "expected_evidence": ["model_side_30_day_bound", "model_side_terminate_behavior",
                                  "process_level_timer_or_event_subprocess_scope",
                                  "terminate_end_scope"],
            "process_scope_sources": scope_sources,
            "alarm_assessments": alarm_assessments,
        }

    elif rule_id == "r9":
        alarm = next((a for a in alarms if a["check"] == "missing_action"), None)
        extracted_actions = list(rule.get("actions") or [])
        details_items = (alarm or {}).get("details") or []
        first = details_items[0] if details_items else {}
        sign_contract = next((row for row in activity_rows
                              if "sign contract" in (row.get("name") or "").lower()), None)
        expected = (((reference_item.get("semantic_issue") or {}).get("evidence") or {})
                    .get("expected_activity"))
        verify_like_activities = [
            row.get("name") for row in activity_rows
            if any(trigger in (row.get("name") or "").lower()
                   for trigger in ("verify", "verif", "correctness"))
        ]
        evidence_ok = bool(
            extracted_actions
            and alarm is not None
            and first.get("rule_action") in extracted_actions
            and first.get("missing") is True
            and first.get("best_model_action") is not None
            and first.get("similarity") is not None
            and sign_contract is not None
            and not verify_like_activities
        )
        if evidence_ok:
            matched.append("missing_action")
            chain.append(
                "Extracted verification action is checked by missing_action; best process "
                "candidate is {} at similarity {}, and the original activity inventory has "
                "no verify/correctness activity. Sign contract ({}) is only the positional "
                "anchor, not the missing action.".format(
                    first.get("best_model_action"), first.get("similarity"),
                    sign_contract.get("id") if sign_contract else None)
            )
        else:
            chain.append(
                "r9 correspondence needs an extracted action, a missing_action alarm with "
                "a concrete best candidate/similarity, and an activity inventory lacking "
                "verify/correctness semantics; Sign contract is only an anchor."
            )
        details = {
            "expected_activity_reference": expected,
            "extracted_actions": extracted_actions,
            "alarm_rule_action": first.get("rule_action"),
            "alarm_best_model_action": first.get("best_model_action"),
            "alarm_similarity": first.get("similarity"),
            "alarm_missing": first.get("missing"),
            "sign_contract_anchor": sign_contract,
            "verify_like_process_activities": verify_like_activities,
            "process_activity_inventory": activity_names,
        }

    elif rule_id == "r10":
        alarm = next((a for a in alarms if a["check"] == "incorrect_actor"), None)
        required_actor = (rule.get("actors") or [""])[0]
        primary_match = (alarm or {}).get("primary_action_match") or {}
        primary_owner_evidence = (alarm or {}).get("primary_action_owner_evidence") or []
        primary_owner_rows = []
        for evidence in primary_owner_evidence:
            activity_id = evidence.get("activity_id")
            primary_owner_rows.append({
                "activity_id": activity_id,
                "activity_name": name_by_id.get(activity_id, activity_id),
                "owners": list(evidence.get("owners") or []),
            })
        candidate_rows = []
        for evidence in (alarm or {}).get("matched_action_owner_evidence") or []:
            activity_id = evidence.get("activity_id")
            candidate_rows.append({
                "activity_id": activity_id,
                "activity_name": name_by_id.get(activity_id, activity_id),
                "owners": list(evidence.get("owners") or []),
            })
        primary_action_name = primary_match.get("best_model_action")
        primary_owners = []
        for row in primary_owner_rows:
            primary_owners.extend(row.get("owners") or [])
        evidence_ok = bool(
            alarm is not None
            and primary_action_name == "Activate SIM card"
            and primary_owner_rows
            and any(owner.lower() == "customer" for owner in primary_owners)
            and not any(_owner_matches(required_actor, owner) for owner in primary_owners)
        )
        if evidence_ok:
            matched.append("incorrect_actor")
            chain.append(
                "Rule action maps to {} ({}); its concrete owner evidence is {}; required "
                "actor is {}. This is the fixed r10 actor-mismatch evidence. Other matched "
                "candidates are listed separately and are not attributed to Customer.".format(
                    primary_action_name,
                    primary_owner_rows[0].get("activity_id") if primary_owner_rows else None,
                    primary_owners, required_actor)
            )
        else:
            chain.append(
                "r10 correspondence needs the rule action to bind to Activate SIM card, "
                "with concrete owner Customer and a required actor that is not an owner. "
                "A union of all matched candidates is not used."
            )
        details = {
            "required_actor": required_actor,
            "primary_action_match": primary_match,
            "primary_action_owner_rows": primary_owner_rows,
            "all_matched_candidate_rows": candidate_rows,
            "detector_evidence": (alarm or {}).get("details") or [],
        }

    elif rule_id == "r11":
        oo = checks.get("out_of_order") or {}
        missing_alarm = next((a for a in alarms if a["check"] == "missing_action"), None)
        consent = next((row for row in activity_rows
                        if "consent" in (row.get("name") or "").lower()), None)
        retrieval = next((row for row in activity_rows
                          if "request personal data" in (row.get("name") or "").lower()), None)
        oo_details = oo.get("details") or []
        mapped_details = [item for item in oo_details if item.get("mapped")]
        order_evidence_ok = bool(
            oo.get("status") == core.STATUS_VIOLATION
            and mapped_details
            and any(item.get("satisfied") is False for item in mapped_details)
        )
        if order_evidence_ok:
            consent_mapped = any(
                "consent" in ((item.get("before_activity") or "") + " " +
                              (item.get("after_activity") or "")).lower()
                for item in mapped_details
            )
            retrieval_mapped = any(
                "request personal data" in ((item.get("before_activity") or "") + " " +
                                           (item.get("after_activity") or "")).lower()
                for item in mapped_details
            )
            order_evidence_ok = bool(consent_mapped and retrieval_mapped)
        if order_evidence_ok:
            matched.append("out_of_order")
            chain.append(
                "out_of_order has mapped consent/retrieval endpoints and a violated "
                "forward/backward relation; this is direct order evidence for r11."
            )
        else:
            chain.append(
                "r11 correspondence requires a positive out_of_order alarm whose mapped "
                "endpoints include consent and request personal data. The present missing_action "
                "alarm is retained as a machine alarm but cannot substitute for the order issue; "
                "consent activity present={}, retrieval activity present={}.".format(
                    bool(consent), bool(retrieval))
            )
        details = {
            "consent_activity": consent,
            "retrieval_activity": retrieval,
            "out_of_order_status": oo.get("status"),
            "out_of_order_mapped_details": mapped_details,
            "missing_action_alarm_present": missing_alarm is not None,
            "missing_action_cannot_substitute_order": True,
        }

    elif rule_id == "r13":
        condition_alarm = next((a for a in alarms
                               if a["check"] == "required_condition_not_enforced"), None)
        constraint_alarm = next((a for a in alarms
                                 if a["check"] == "constraint_violated"), None)
        actor_text = (rule.get("actors") or [""])[0]
        model_labels = [flow.get("name") for flow in (process_facts.get("sequence_flows") or [])
                        if flow.get("name")]
        threshold_alarm_evidence = []
        for alarm in (condition_alarm, constraint_alarm):
            if not alarm:
                continue
            blob = " ".join(str(alarm.get(key) or "") for key in
                            ("best_candidate", "reason", "max_sim")) + " " + \
                   " ".join(str(item) for item in (alarm.get("details") or []))
            if "debt" in blob.lower() and ("50" in blob or "100" in blob):
                threshold_alarm_evidence.append({"check": alarm["check"], "evidence": blob})
        field_attribution = {
            "actor_text_contains_50": bool(re.search(r"\b50\b", actor_text or "")),
            "condition_value": rule.get("condition"),
            "constraint_value": rule.get("constraint"),
            "condition_empty": not bool(rule.get("condition")),
            "constraint_empty": not bool(rule.get("constraint")),
            "model_debt_labels": [label for label in model_labels if "debt" in label.lower()],
            "note": ("The 50 EUR threshold appears in the actor field; condition/constraint "
                     "are empty in this rule record, so no comparison is fabricated."),
        }
        if threshold_alarm_evidence:
            matched.append("required_condition_not_enforced")
            chain.append(
                "A condition/constraint alarm contains actual debt-threshold evidence {}; "
                "it is treated as reference-corresponding.".format(threshold_alarm_evidence)
            )
        else:
            other = [a["check"] for a in alarms]
            chain.append(
                "No condition/constraint alarm contains both the 50 EUR threshold and the "
                "model Debt < 100 label. Actor threshold text is recorded as a field-attribution "
                "gap, not copied into condition/constraint. Other alarms are {}.".format(other)
            )
        details = {
            "condition_alarm": condition_alarm,
            "constraint_alarm": constraint_alarm,
            "threshold_alarm_evidence": threshold_alarm_evidence,
            "field_attribution": field_attribution,
        }

    else:
        chain.append("Unknown rule; no correspondence rule was applied.")
        details = {"reason": "unknown_rule"}

    if matched:
        judgment = "found_with_reference_evidence"
    elif alarms:
        judgment = "machine_alarm_but_reference_correspondence_unverified"
    else:
        judgment = "no_positive_machine_alarm"
    return {
        "reference_issue_present": reference_item.get("dev_reference_judgment", {}).get("judgment")
        in ("issue_present", "issue_present_with_premise"),
        "reference_issue_summary_zh": reference_summary,
        "machine_alarms": alarms,
        "machine_alarm_count": len(alarms),
        "matched_alarm_checks": sorted(set(matched)),
        "found_corresponding_problem": bool(matched),
        "correspondence_judgment": judgment,
        "evidence_chain_zh": chain,
        "assessment_details": details,
        "evaluation_scope_note_zh": (
            "开发案例评价：只根据本规则声明所需的动作绑定、流程事实、时间/终止/门槛证据"
            "逐项判断；类型名相同或 status=violation 本身不构成证据。机器状态不改写。"
        ),
    }


def _repair_evidence(result: dict | None) -> dict:
    result = result or {}
    return {
        "status": result.get("status"),
        "machine_status": result.get("machine_status", result.get("status")),
        "score": result.get("score"),
        "reason": result.get("reason") or result.get("evaluation_reason") or result.get("machine_reason"),
        "denominator": result.get("denominator"),
        "details": result.get("details") or [],
        "matched_action_owner_evidence": result.get("matched_action_owner_evidence") or [],
        "matched_process_action_ids": result.get("matched_process_action_ids") or [],
        "best_candidate": result.get("best_candidate"),
        "max_sim": result.get("max_sim"),
        "observable": result.get("observable"),
    }


def run(overwrite: bool, check_only: bool) -> dict:
    nlp = _load_nlp()
    thresholds = _sun_thresholds()
    curated = core.load_json(core.CURATED)
    requirements = core.load_requirements()
    predictions = core.load_predictions(1)
    repair_specs = core.load_json(core.REPAIR_SPECS)

    from bpc_hybrid.s3_action_matching_v3 import EvidenceChecksV3  # noqa: E402
    from bpc_hybrid.s3_extended_v3_repair_v2 import (  # noqa: E402
        RepairedExtendedScorerV2, aggregate_with_comparison_gate,
    )
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

    sim = WinterSimilarity(nlp)
    scorers = {"sim": sim, "sun": SunScorer(sim, thresholds["tau"], thresholds["gamma"],
                                            thresholds["theta"], nlp=nlp)}

    original = core.BPMN.read_bytes()
    stage1 = _parse_flattened(original, "sim_original", core.STAGE1_CONTRACT)
    model = core.build_model(stage1, nlp)
    v3 = EvidenceChecksV3(sim, thresholds["tau"], thresholds["gamma"], thresholds["theta"], nlp)
    scorers["ext"] = RepairedExtendedScorerV2(v3, sim.text_pair, LABEL_FALLBACK_GAMMA, GAMMA_EXT)
    scorers["gate"] = aggregate_with_comparison_gate
    baseline_path, baseline = _load_baseline_capsule()
    process_facts = _stage1_process_facts(stage1)

    plan = {
        "schema_version": "sim_case_c1_plan@1.0.0",
        "run_id": "sim_case_c1_run_v1",
        "claim_scope": "development_case_study_not_formal_gold",
        "written_before_scoring": True,
        "main_denominator": [f"{rid}/v2" for rid in core.MAIN_RULES],
        "background_items": core.BACKGROUND_RULES,
        "groups": {
            "A": "project non-LLM baseline sun_rule_only / B0 v10a (CoreNLP + Tregex + locked "
                 "BERT-TextCNN) + frozen Sun-style three-type detection",
            "B": "existing real-LLM predictions (repeat-01) + SAME three-type detection as A",
            "C": "SAME stage2 and three-type rows as B + the project's accepted four-type "
                 "repair (REPAIR-V2 arm C: v3 localization + comparison gate)",
        },
        "components": {
            "A.stage2": {"entry_point": "bpc_hybrid.estg150_b0_development_v10.run_b0_batch_v10",
                         "profile": "PROFILE_V10A",
                         "capsule": str(baseline_path.relative_to(core.REPO)).replace("\\", "/"),
                         "runner": "scripts/run_sim_case_stage2_baseline_v1.py",
                         "language_boundary": "English sentences through the German-contract classifier slot"},
            "A.stage3": {"three_types": "bpc_hybrid.sun_stage3.sun_scorer.SunScorer (Def5-7)",
                         "four_types": "not run"},
            "B.stage2": {"source": "outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-01",
                         "projection": "bpc_hybrid.gdpr_s2_s3_projection.project_external_sentence"},
            "B.stage3": {"three_types": "identical code and thresholds to A", "four_types": "not run"},
            "C.stage2": {"source": "identical to B (same row objects)"},
            "C.stage3": {"three_types": "identical rows reused from B",
                         "four_types": "bpc_hybrid.s3_extended_v3_repair_v2.RepairedExtendedScorerV2 "
                                       "(v3=EvidenceChecksV3 gamma 0.8, label fallback 0.4, gamma_ext 0.5) "
                                       "+ aggregate_with_comparison_gate"},
            "similarity_backend": {"class": "bpc_hybrid.winter_stage3.winter_similarity.WinterSimilarity",
                                   "nlp": "en_core_web_sm",
                                   "behaviour": "Doc.similarity over context-sensitive tensors (spaCy warns W007: "
                                                "the model ships no static word vectors); it is NOT a string "
                                                "similarity and NOT a static-embedding similarity"},
        },
        "declared_policy": core.ADAPTATION_POLICY,
        "thresholds": {**thresholds, "gamma_ext": GAMMA_EXT,
                       "label_fallback_gamma": LABEL_FALLBACK_GAMMA,
                       "source": "configs/sun_stage3_development_v1.json + REPAIR-V2 arm C configuration"},
        "lens_map": LENS_MAP,
        "evaluation_policy": {
            "status_semantics": (
                "empty_rule_action is an extraction failure; evaluation status is undetermined and "
                "the raw formula status is retained separately as machine_status=not_applicable"
            ),
            "reference_correspondence": (
                "type equality plus status=violation is not sufficient; only alarms with action-bound, "
                "process-fact, temporal or termination evidence count as corresponding to the reference issue"
            ),
            "adaptation_trace": "raw_extraction_count -> projected_candidate_count -> adapted_record_count -> detector_consumed_count",
        },
        "inputs": {
            "bpmn": core.artifact(core.BPMN),
            "requirements": core.artifact(core.REQUIREMENTS),
            "step_3_baseline": core.artifact(core.STEP3),
            "curated_reference_judgments": core.artifact(core.CURATED),
            "repair_specs": core.artifact(core.REPAIR_SPECS),
            "predictions_repeat01": predictions["artifact"],
            "stage1_contract": core.artifact(core.STAGE1_CONTRACT),
            "sun_config": core.artifact(core.SUN_CONFIG),
            "stage2_baseline_capsule": core.artifact(baseline_path),
        },
        "stage1_public_record": stage1["evidence"],
        "implementation_hashes": {
            "core": _sha(Path(core.__file__).read_text(encoding="utf-8")),
            "transforms": _sha((ROOT / "src" / "bpc_hybrid" / "sim_case_c1_transforms.py")
                               .read_text(encoding="utf-8")),
            "runner": _sha(Path(__file__).read_text(encoding="utf-8")),
        },
        "prediction_isolation": {
            "reference_judgments_read_after_predictions": True,
            "external_deviations_not_in_detection_input": True,
            "step_3_baseline_read_only_for_comparison": True,
        },
    }

    rows: list[dict] = []
    rule_records: dict[str, dict] = {}
    for rule_id in core.MAIN_RULES:
        rule_text = requirements[(rule_id, 2)]
        sides = {group: _rule_side(rule_id, rule_text, group,
                                   {"nlp": nlp, "predictions": predictions, "baseline": baseline})
                 for group in ("A", "B")}
        entry = {"rule_id": rule_id, "version": "v2", "rule_text_sha256": _sha(rule_text),
                 "rule_text_length": len(rule_text), "sides": {}}
        for group, side in sides.items():
            if not side["ok"]:
                rows.append({"rule_id": rule_id, "group": group, "check": "*",
                             "status": core.STATUS_UNDETERMINED,
                             "machine_status": core.STATUS_UNDETERMINED,
                             "reason": side["error"]})
                entry["sides"][group] = {"ok": False, "error": side["error"]}
                continue
            rule_rows = _group_rows(scorers, side["sentence"], model, stage1, side["rule"])
            entry["sides"][group] = {
                "ok": True,
                "sentence": {k: v for k, v in side["sentence"].items() if k != "sentence_text"},
                "rule": side["rule"],
                "checks": rule_rows["three_types"],
                "stage2_meta": side["stage2_meta"],
            }
            for check, result in rule_rows["three_types"].items():
                rows.append(_check_row(rule_id, group, check, result))
        side_b = sides["B"]
        if side_b["ok"]:
            ext = _extended_rows(scorers, side_b["sentence"], model, stage1, side_b["rule"])
            entry["sides"]["C"] = {
                "ok": True,
                "sentence": entry["sides"]["B"]["sentence"],
                "rule": side_b["rule"],
                "checks": {**entry["sides"]["B"]["checks"], **ext["extended"]},
                "surfaces": ext["surfaces"], "mapped_activity": ext["mapped_activity"],
                "gate": ext["gate"],
                "reuses_group_b": ["stage2", "three_type_rows"],
            }
            for check, result in entry["sides"]["B"]["checks"].items():
                rows.append(_check_row(rule_id, "C", check, result, inherited_from="B"))
            for check, result in ext["extended"].items():
                rows.append(_check_row(rule_id, "C", check, result,
                                       added_by="four_extended_types"))
        else:
            entry["sides"]["C"] = {"ok": False, "error": side_b.get("error")}
        raw_by_group = {
            "A": next((r for r in baseline.get("records", [])
                       if r.get("sample_id") == f"sim_{rule_id}_v2"), {}),
            "B": predictions["rows"].get(f"SIM_card_scenario/{rule_id}/v2", {}),
            "C": predictions["rows"].get(f"SIM_card_scenario/{rule_id}/v2", {}),
        }
        entry["chain"] = build_chain(rule_id, rule_text,
                                     {g: entry["sides"].get(g) or {} for g in ("A", "B", "C")},
                                     raw_by_group)
        entry["a_to_b"] = (_compare_records(entry["sides"]["A"]["rule"], entry["sides"]["B"]["rule"],
                                            entry["chain"])
                           if entry["sides"]["A"].get("ok") and entry["sides"]["B"].get("ok") else None)
        rule_records[rule_id] = entry

    # Verify the required B/C three-type reuse invariant before the comparison
    # stage reads any reference judgment.
    for rule_id in core.MAIN_RULES:
        sides = rule_records[rule_id]["sides"]
        if sides.get("B", {}).get("ok") and sides.get("C", {}).get("ok"):
            for check in ("missing_action", "incorrect_actor", "out_of_order"):
                if sides["B"]["checks"][check] != sides["C"]["checks"][check]:
                    raise AssertionError(f"B/C three-type reuse changed for {rule_id}/{check}")

    # ---- reference judgments are read only now, after all predictions/scoring --
    reference = {item["rule_id"]: item for item in curated["items"]}
    comparison = []
    reference_assessment_summary = {
        group: {"reference_problems": 5, "found_with_reference_evidence": 0,
                "machine_alarm_but_reference_correspondence_unverified": 0,
                "no_positive_machine_alarm": 0}
        for group in ("A", "B", "C")
    }
    for rule_id in core.MAIN_RULES:
        item = reference[rule_id]
        lenses = LENS_MAP[rule_id]
        per_group = {}
        for group in ("A", "B", "C"):
            side = rule_records[rule_id]["sides"].get(group) or {}
            checks = side.get("checks") or {}
            lens_results = {}
            for lens in [lenses["primary"], *lenses["secondary"]]:
                if lens in checks:
                    lens_results[lens] = {
                        "status": checks[lens]["status"],
                        "machine_status": checks[lens].get("machine_status", checks[lens]["status"]),
                        "score": checks[lens].get("score"),
                        "reason": checks[lens].get("reason"),
                    }
            assessment = _assess_alarm_correspondence(rule_id, group, side, process_facts, item)
            type_status_found = any(r["status"] == core.STATUS_VIOLATION for r in lens_results.values())
            per_group[group] = {
                "covered_lenses": sorted(lens_results),
                "lens_results": lens_results,
                "type_and_status_only_match": type_status_found and lenses["primary"] in {
                    k for k, v in lens_results.items() if v["status"] == core.STATUS_VIOLATION},
                "found_corresponding_problem": assessment["found_corresponding_problem"],
                "correspondence_judgment": assessment["correspondence_judgment"],
                "matched_alarm_checks": assessment["matched_alarm_checks"],
                "machine_alarms": assessment["machine_alarms"],
                "machine_alarm_count": assessment["machine_alarm_count"],
                "evidence_chain_zh": assessment["evidence_chain_zh"],
                "assessment_details": assessment.get("assessment_details") or {},
                "all_lenses_undetermined": (not lens_results) or all(
                    r["status"] in (core.STATUS_UNDETERMINED, core.STATUS_NOT_APPLICABLE)
                    for r in lens_results.values()),
            }
            category = assessment["correspondence_judgment"]
            if category in reference_assessment_summary[group]:
                reference_assessment_summary[group][category] += 1
        primary = per_group["C"]
        reference_present = item["dev_reference_judgment"]["judgment"] in (
            "issue_present", "issue_present_with_premise")
        if primary["found_corresponding_problem"]:
            miss_kind = None
        elif primary["correspondence_judgment"] == "machine_alarm_but_reference_correspondence_unverified":
            miss_kind = "alarm_without_verified_reference_correspondence"
        elif primary["all_lenses_undetermined"]:
            miss_kind = "undetermined"
        else:
            miss_kind = "wrong_or_unaligned_judgment"
        comparison.append({
            "rule_id": rule_id,
            "reference_judgment": item["dev_reference_judgment"]["judgment"],
            "reference_sources": item["dev_reference_judgment"]["sources"],
            "premise_zh": item["dev_reference_judgment"].get("premise_zh"),
            "semantic_issue_zh": item["semantic_issue"]["summary_zh"],
            "primary_lens": lenses["primary"],
            "secondary_lenses": lenses["secondary"],
            "groups": per_group,
            "consistency": {
                "reference_issue_present": reference_present,
                "group_C_found": primary["found_corresponding_problem"],
                "group_C_undetermined": primary["all_lenses_undetermined"],
                "group_C_judgment": primary["correspondence_judgment"],
                "type_and_status_only_match": primary["type_and_status_only_match"],
                "miss_kind": miss_kind,
            },
        })

    # ---- repair controls ----------------------------------------------------
    repairs = []
    for spec in repair_specs["repairs"]:
        repaired_payload, detail = repair_variant(stage1["flattened_xml"], spec["repair_id"])
        repaired = _parse_flattened(repaired_payload, f"repair_{spec['repair_id']}", core.STAGE1_CONTRACT,
                                    already_flattened=True)
        repaired_model = core.build_model(repaired, nlp)
        rule_text = requirements[(spec["rule_id"], 2)]
        row = {"repair_id": spec["repair_id"], "rule_id": spec["rule_id"], "lens": spec["lens"],
               "operations": detail["operations"], "semantic_zh": detail["semantic_zh"],
               "model_evidence": repaired["evidence"],
               "independent_verification": verify_repair(spec["repair_id"], repaired, repaired_model),
               "before": None, "after": None}
        side = rule_records[spec["rule_id"]]["sides"].get("B") or {}
        side_c_original = rule_records[spec["rule_id"]]["sides"].get("C") or side
        rule_element_available = False
        exclusion_reason = None
        if side.get("ok"):
            sentence = dict(side["sentence"])
            sentence["sentence_text"] = rule_text
            rule = side["rule"]
            lens = spec["lens"]
            if lens in ("missing_action", "incorrect_actor", "out_of_order"):
                after_checks = core.run_three_types(scorers["sun"], rule, repaired_model)
            else:
                after_checks = _extended_rows(scorers, sentence, repaired_model, repaired, rule)["extended"]
            after = after_checks.get(lens)
            before = (side_c_original.get("checks") or {}).get(lens)
            before_group_b = (side.get("checks") or {}).get(lens)
            field_for_lens = {
                "missing_action": "actions", "incorrect_actor": "actors",
                "out_of_order": "order_relations", "prohibited_action_present": "action",
                "required_condition_not_enforced": "condition",
                "constraint_violated": "constraint", "exception_not_handled": "exception",
            }.get(lens)
            if field_for_lens in ("action", "condition", "constraint", "exception"):
                rule_element_available = bool(rule.get(field_for_lens))
            else:
                rule_element_available = bool(rule.get(field_for_lens or ""))
            if not rule_element_available:
                exclusion_reason = f"empty_rule_{field_for_lens}"
            iv = row["independent_verification"]
            effective = (bool(iv.get("repair_semantics_valid"))
                         and bool(iv.get("semantics_entered_detection_chain"))
                         and rule_element_available
                         and after is not None)
            if not bool(iv.get("repair_semantics_valid")):
                exclusion_reason = exclusion_reason or "repair_semantics_invalid"
            elif not bool(iv.get("semantics_entered_detection_chain")):
                exclusion_reason = exclusion_reason or "repair_semantics_not_carried_by_stage1"
            row.update({
                "rule_element_available": rule_element_available,
                "effective_repair_control": effective,
                "in_effective_repair_denominator": effective,
                "effective_control_exclusion_reason": exclusion_reason,
                "before": {"group": "C_original", **_repair_evidence(before)},
                "after": {"group": "C_repaired", **_repair_evidence(after)},
                "problem_removed": bool(
                    (before or {}).get("status") == core.STATUS_VIOLATION
                    and (after or {}).get("status") == core.STATUS_SATISFIED
                ),
            })
            row["group_B"] = {"group": "B_original", **_repair_evidence(before_group_b)}
            row["group_C"] = dict(row["after"])
        else:
            row.update({"rule_element_available": False,
                        "effective_repair_control": False,
                        "in_effective_repair_denominator": False,
                        "effective_control_exclusion_reason": "rule_side_unavailable"})
        if spec["repair_id"] == "r8_timeout_termination":
            legacy_payload, legacy_detail = repair_variant_r8_task_scoped_legacy(stage1["flattened_xml"])
            legacy = _parse_flattened(legacy_payload, "repair_r8_timeout_termination_task_scoped_legacy",
                                      core.STAGE1_CONTRACT, already_flattened=True)
            legacy_model = core.build_model(legacy, nlp)
            legacy_iv = verify_repair("r8_timeout_termination_task_scoped_legacy", legacy, legacy_model)
            legacy_after = None
            legacy_side = rule_records[spec["rule_id"]]["sides"].get("B") or {}
            if legacy_side.get("ok"):
                legacy_sentence = dict(legacy_side["sentence"])
                legacy_sentence["sentence_text"] = rule_text
                legacy_after_checks = _extended_rows(scorers, legacy_sentence, legacy_model,
                                                     legacy, legacy_side["rule"])["extended"]
                legacy_after = legacy_after_checks.get(spec["lens"])
            row["legacy_partial_control"] = {
                "repair_id": "r8_timeout_termination_task_scoped_legacy",
                "operations": legacy_detail["operations"],
                "semantic_zh": legacy_detail["semantic_zh"],
                "model_evidence": legacy["evidence"],
                "independent_verification": legacy_iv,
                "before": {"group": "C_original", **_repair_evidence((side_c_original.get("checks") or {}).get(spec["lens"]))},
                "after": {"group": "C", **_repair_evidence(legacy_after)},
                "control_status": "partial_or_invalid_scope",
                "in_effective_repair_denominator": False,
            }
        repairs.append(row)

    repair_control_summary = {
        "main_repairs": len(repairs),
        "effective_repair_controls": sum(1 for r in repairs if r.get("effective_repair_control")),
        "excluded_from_effective_denominator": sum(1 for r in repairs
                                                   if not r.get("effective_repair_control")),
        "excluded_reasons": {r["repair_id"]: r.get("effective_control_exclusion_reason")
                             for r in repairs if not r.get("effective_repair_control")},
    }

    summary = {}
    for group in ("A", "B", "C"):
        status_counts: dict[str, int] = {}
        machine_counts: dict[str, int] = {}
        for row in rows:
            if row["group"] != group:
                continue
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
            machine = row.get("machine_status")
            if machine:
                machine_counts[machine] = machine_counts.get(machine, 0) + 1
        summary[group] = {
            "checks": sum(1 for r in rows if r["group"] == group),
            "status_counts": status_counts,
            "machine_status_counts": machine_counts,
        }

    capsule = {
        "schema_version": "sim_case_c1_run@1.0.0",
        "run_id": plan["run_id"],
        "claim_scope": plan["claim_scope"],
        "plan": plan,
        "process_facts": process_facts,
        "rows": rows,
        "rules": rule_records,
        "comparison": comparison,
        "repairs": repairs,
        "summary": summary,
        "reference_assessment_summary": reference_assessment_summary,
        "repair_control_summary": repair_control_summary,
        "stage_attribution": {
            "a_to_b": {rid: rule_records[rid]["a_to_b"] for rid in core.MAIN_RULES},
            "b_to_c": "group C adds exactly the four extended checks on the SAME rule side as B; "
                      "three-type rows are reused byte-identically (reuses_group_b)",
        },
    }

    if check_only:
        return {"status": "CHECK_OK", "summary": summary,
                "reference_assessment_summary": reference_assessment_summary,
                "repair_control_summary": repair_control_summary,
                "comparison": [{c["rule_id"]: c["consistency"]} for c in comparison],
                "repairs": [{r["repair_id"]: r.get("effective_repair_control")} for r in repairs]}

    outputs = {
        "plan": _write(RUN_DIR / "plan.json", json.dumps(plan, ensure_ascii=False, indent=1) + "\n", overwrite),
        "capsule": _write(RUN_DIR / "capsule.json", json.dumps(capsule, ensure_ascii=False, indent=1) + "\n", overwrite),
        "rows": _write(RUN_DIR / "rows.jsonl",
                       "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), overwrite),
        "report_json": _write(REPORT_JSON, json.dumps(
            {"schema_version": capsule["schema_version"], "run_id": plan["run_id"],
             "claim_scope": plan["claim_scope"], "groups": plan["groups"],
             "thresholds": plan["thresholds"], "declared_policy": plan["declared_policy"],
             "stage1": plan["stage1_public_record"], "inputs": plan["inputs"],
             "summary": summary, "reference_assessment_summary": reference_assessment_summary,
             "repair_control_summary": repair_control_summary,
             "process_facts_summary": {k: process_facts[k] for k in
                                       ("xml_counts", "condition_expressions", "flow_labels")},
             "comparison": _redact_for_report(comparison),
             "repairs": _redact_for_report(repairs),
             "stage_attribution": {
                 "a_to_b": _sanitise_attribution(capsule["stage_attribution"]["a_to_b"]),
                 "b_to_c": capsule["stage_attribution"]["b_to_c"],
             },
             "boundaries": [
                 "development case study; not formal Gold, not the authors' original experiment, not an enterprise validation",
                 "single case: counts and per-item results only; no seven-type aggregate F1",
                 "five prediction repeats are stability evidence, not 25 independent samples",
                 "the Barrientos artifact is read in place; no restricted text is committed",
             ]}, ensure_ascii=False, indent=1) + "\n", overwrite),
    }
    outputs["report_md"] = _write(REPORT_MD, render_md(capsule), overwrite)
    manifest = {
        "schema_version": "sim_case_c1_run_manifest@1.0.0",
        "run_id": plan["run_id"], "inputs": plan["inputs"],
        "implementation_hashes": plan["implementation_hashes"],
        "outputs": outputs, "api_calls": 0, "network": False,
    }
    _write(RUN_DIR / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", overwrite)
    (LOCAL_MODELS).mkdir(parents=True, exist_ok=True)
    (LOCAL_MODELS / "sim_original_flattened.bpmn").write_bytes(stage1["flattened_xml"])
    return {"status": "BUILT", "outputs": {k: v["path"] for k, v in outputs.items()},
            "summary": summary, "reference_assessment_summary": reference_assessment_summary,
            "repair_control_summary": repair_control_summary}


def _cell_status(result: dict | None) -> str:
    if not result:
        return "—"
    status = result.get("status")
    score = result.get("score")
    extra = f" ({score})" if score is not None else ""
    if result.get("status_source") == "extraction" and result.get("evaluation_reason"):
        extra += f"; raw_machine={result.get('machine_status')}; {result.get('evaluation_reason')}"
    return f"{status}{extra}"


def _flow_cell(flow: dict | None) -> str:
    if not flow:
        return "—"
    return (f"{flow.get('verdict')} "
            f"[raw={flow.get('raw_count')}→proj={flow.get('projected_candidate_count')}→"
            f"adapted={flow.get('adapted_record_count')}→consumed={flow.get('detector_consumed_count')}; "
            f"{flow.get('consumption_status')}]")


def _alarm_summary(alarms: list[dict]) -> str:
    if not alarms:
        return "无 positive alarm"
    parts = []
    for alarm in alarms:
        reason = alarm.get("reason") or ""
        best = alarm.get("best_candidate")
        max_sim = alarm.get("max_sim")
        extra = f" best={best!r} max_sim={max_sim}" if best is not None or max_sim is not None else ""
        parts.append(f"{alarm['check']}={alarm.get('machine_status')}/{alarm.get('score')}{extra} {reason}")
    return "；".join(parts)


def render_md(capsule: dict) -> str:
    plant = capsule["plan"]
    lines = [
        "# SIM 卡入网案例：A/B/C 三组开发性检测结果（同一 capsule）",
        "",
        f"- run: `{capsule['run_id']}`；口径：**{capsule['claim_scope']}**（非正式 Gold，非作者原始实验复现，非企业验证）。",
        f"- 主评价单位：{', '.join(plant['main_denominator'])}（5 条 v2 规则）；背景条目：{', '.join(plant['background_items'])}。",
        f"- 阈值：tau={plant['thresholds']['tau']}, gamma={plant['thresholds']['gamma']}, "
        f"theta={plant['thresholds']['theta']}, gamma_ext={plant['thresholds']['gamma_ext']}, "
        f"label_fallback={plant['thresholds']['label_fallback_gamma']}。",
        f"- 公共 Stage 1 记录：{plant['stage1_public_record']['process_record_sha256'][:16]}…；"
        f"扁平化 XML {plant['stage1_public_record']['flattened_xml_sha256'][:16]}…；"
        f"lanes={plant['stage1_public_record']['lanes']}。",
        f"- 角色绑定（打分前声明）：{json.dumps(plant['declared_policy']['role_binding'], ensure_ascii=False)}。",
        "",
        "## 1. 组件对应",
        "",
        "| 组 | Stage 2 | Stage 3 三类 | Stage 3 四类 |",
        "|---|---|---|---|",
        "| A | 项目锁定非 LLM 基线 B0 v10a (`sun_rule_only_b0_v10a`) | 冻结 Sun 式 Def5–7 | 未运行 |",
        "| B | 已有真实 LLM 预测 `OURS-FULL/repeat-01`，经 `project_external_sentence` | 与 A 同一代码和阈值 | 未运行 |",
        "| C | 与 B 同一 Stage 2 行和适配记录 | 逐行复用 B | REPAIR-V2 C 实现：`RepairedExtendedScorerV2` + `aggregate_with_comparison_gate` |",
        "",
        "## 2. 五条规则的逐项实际输出",
        "",
        "> `status` 是修正抽取失败后的评价状态；`machine_status` 保留冻结公式在分母为 0 等情形下的原始机器状态。"
        "A 组 r9/r13 的 `empty_rule_action` 不再写成 `not_applicable`。",
        "",
        "| 规则 | 组 | missing_action | incorrect_actor | out_of_order | prohibited | condition | constraint | exception |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for rule_id in core.MAIN_RULES:
        entry = capsule["rules"][rule_id]
        for group in ("A", "B", "C"):
            checks = (entry["sides"].get(group) or {}).get("checks") or {}
            lines.append(
                f"| {rule_id}/v2 | {group} | {_cell_status(checks.get('missing_action'))} | "
                f"{_cell_status(checks.get('incorrect_actor'))} | {_cell_status(checks.get('out_of_order'))} | "
                f"{_cell_status(checks.get('prohibited_action_present'))} | "
                f"{_cell_status(checks.get('required_condition_not_enforced'))} | "
                f"{_cell_status(checks.get('constraint_violated'))} | "
                f"{_cell_status(checks.get('exception_not_handled'))} |"
            )
    lines += [
        "",
        "## 3. 机器报警与参考问题对应（评价栏与检测器输出分栏）",
        "",
        "> 只有同时具备动作绑定、流程事实、时间/终止语义等可核验证据的报警才计为对应检出；"
        "类型相同且 `status=violation` 本身不算证据。",
        "",
        "| 规则 | 组 | 机器报警（原始输出） | 对应判断 | 有证据对应的报警 | 评价证据链 |",
        "|---|---|---|---|---|---|",
    ]
    for item in capsule["comparison"]:
        rid = item["rule_id"]
        for group in ("A", "B", "C"):
            block = item["groups"][group]
            chain = " ".join(block.get("evidence_chain_zh") or [])
            lines.append(
                f"| {rid}/v2 | {group} | {_alarm_summary(block.get('machine_alarms') or [])} | "
                f"{block.get('correspondence_judgment')} | "
                f"{', '.join(block.get('matched_alarm_checks') or []) or '—'} | {chain} |"
            )
    lines += [
        "",
        "## 4. 信息传递与部分丢失（原始抽取→投影→规则记录→检测器消费）",
        "",
        "判定：`full_carry`=各层数量一致；`partially_carried_by_declared_policy`=出现多值截断；"
        "`lost_in_adaptation`=抽取/投影有值但规则记录丢失；`not_extracted`=原始即无；"
        "`derived_by_declared_policy`=顺序关系由事先声明的 temporal policy 派生。",
        "",
        "| 规则 | 组 | actions | actors | conditions | constraints | exceptions | order_relations | actor_action_pairs |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for rule_id in core.MAIN_RULES:
        groups = capsule["rules"][rule_id]["chain"]["groups"]
        for group in ("A", "B", "C"):
            flow = (groups.get(group) or {}).get("field_flow") or {}
            pair_flow = (groups.get(group) or {}).get("actor_action_pair_flow") or {}
            cells = [_flow_cell(flow.get(f)) for f in
                     ("actions", "actors", "conditions", "constraints", "exceptions", "order_relations")]
            pair = pair_flow.get("verdict", "—")
            lines.append(f"| {rule_id}/v2 | {group} | " + " | ".join(cells) + f" | {pair} |")
    value_rows = []
    for rule_id in core.MAIN_RULES:
        groups = capsule["rules"][rule_id]["chain"]["groups"]
        for group in ("A", "B", "C"):
            grp = groups.get(group) or {}
            for field, flow in (grp.get("field_flow") or {}).items():
                for change in flow.get("value_changes") or []:
                    value_rows.append(
                        f"| {rule_id}/v2 | {group} | {field} | "
                        f"{change.get('original')} | {change.get('final')} | "
                        f"{change.get('source') or change.get('bound_from') or '—'} | "
                        f"{change.get('reason') or '—'} |"
                    )
            pair_flow = grp.get("actor_action_pair_flow") or {}
            for change in pair_flow.get("value_changes") or []:
                value_rows.append(
                    f"| {rule_id}/v2 | {group} | actor_action_pairs | "
                    f"{change.get('actor_original')} | {change.get('actor_final')} | "
                    f"{change.get('bound_from') or '—'} | {change.get('reason') or '—'} |"
                )
    if value_rows:
        lines += [
            "",
            "### 4.1 值级变化与角色绑定（防止 1->1 计数掩盖回退）",
            "",
            "| 规则 | 组 | 字段/配对 | original | final | source | reason |",
            "|---|---|---|---|---|---|---|",
            *value_rows,
        ]
    lines += [
        "",
        "### 4.2 A→B 归因",
        "",
        "| 规则 | A→B changed_fields | 直接差异归因 | 组内适配损失 |",
        "|---|---|---|---|",
    ]
    for rid, block in capsule["stage_attribution"]["a_to_b"].items():
        block = block or {}
        losses = block.get("adaptation_loss") or []
        loss_text = "; ".join(
            f"{x['group']}/{x['field']}={x['verdict']} "
            f"({x['raw_count']}→{x['projected_count']}→{x['adapted_count']})"
            for x in losses
        ) or "无"
        lines.append(
            f"| {rid}/v2 | {', '.join(block.get('changed_fields', [])) or '无'} | "
            f"{block.get('difference_attribution')} | {loss_text} |"
        )
    lines += [
        "",
        "## 5. 修复对照：有效、部分/无效与可评价性",
        "",
        "> `effective_repair_control=true` 要求：修复语义独立成立、修复信息确实进入检测链、"
        "对应规则元素可用、修复后检查可执行。r8 的过程级事件子流程在冻结 Stage 1 中为 opaque activity，"
        "计时/终止作用域不能进入结构化检测链；旧任务级修复保留为部分/无效对照。",
        "",
        "| 修复 | 规则 | 视角 | 修复语义有效 | 进入检测链 | 有效分母 | 排除原因 | C_original | C_repaired | 问题移除 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in capsule["repairs"]:
        iv = row.get("independent_verification") or {}
        before = row.get("before") or {}
        after = row.get("after") or {}
        lines.append(
            f"| {row['repair_id']} | {row['rule_id']} | {row['lens']} | {iv.get('repair_semantics_valid')} | "
            f"{iv.get('semantics_entered_detection_chain')} | {row.get('in_effective_repair_denominator')} | "
            f"{row.get('effective_control_exclusion_reason') or '—'} | "
            f"{before.get('status')} ({before.get('score')}) | "
            f"{after.get('status')} ({after.get('score')}) | {row.get('problem_removed')} |"
        )
    lines += [
        "",
        "### 5.1 r8 旧任务级对照（保留但不进入有效分母）",
        "",
    ]
    r8 = next((r for r in capsule["repairs"] if r["repair_id"] == "r8_timeout_termination"), {})
    legacy = r8.get("legacy_partial_control") or {}
    if legacy:
        lines.append(
            f"- 旧件 `{legacy['repair_id']}`：`scope_matches_rule_semantics="
            f"{legacy['independent_verification'].get('scope_matches_rule_semantics')}`；"
            f"有效分母={legacy.get('in_effective_repair_denominator')}；C_original {legacy.get('before', {}).get('status')} "
            f"-> C_repaired {legacy.get('after', {}).get('status')}。"
        )
    lines += [
        "",
        "## 6. 计数（逐检测项，不是七类总 F1，也不混用规则数）",
        "",
        "| 组 | checks | violation | satisfied | undetermined | not_applicable | machine_status 计数 |",
        "|---|---|---|---|---|---|---|",
    ]
    for group, block in capsule["summary"].items():
        counts = block["status_counts"]
        machine = block.get("machine_status_counts") or {}
        lines.append(
            f"| {group} | {block['checks']} | {counts.get('violation', 0)} | "
            f"{counts.get('satisfied', 0)} | {counts.get('undetermined', 0)} | "
            f"{counts.get('not_applicable', 0)} | {json.dumps(machine, ensure_ascii=False)} |"
        )
    lines += [
        "",
        "### 6.1 参考问题对应计数",
        "",
        "| 组 | 参考问题数 | 有证据对应检出 | 有报警但对应未证实 | 无 positive alarm |",
        "|---|---|---|---|---|",
    ]
    for group, block in capsule["reference_assessment_summary"].items():
        lines.append(
            f"| {group} | {block['reference_problems']} | {block['found_with_reference_evidence']} | "
            f"{block['machine_alarm_but_reference_correspondence_unverified']} | "
            f"{block['no_positive_machine_alarm']} |"
        )
    lines += [
        "",
        "### 6.2 有效修复对照计数",
        "",
        f"- 主修复件：{capsule['repair_control_summary']['main_repairs']}。",
        f"- 有效修复对照分母：{capsule['repair_control_summary']['effective_repair_controls']}。",
        f"- 排除：{json.dumps(capsule['repair_control_summary']['excluded_reasons'], ensure_ascii=False)}。",
        "",
        "## 7. 边界",
        "",
        "- 这是开发性单案例结果，不是正式 Gold、不是独立人工准确率、不是作者原始实验复现。",
        "- 单案例只给逐条与逐检查计数，不合成七类总 F1。",
        "- B 组复用已有 repeat-01 预测；重复运行只作稳定性证据，不作为新增独立样本。",
        "- 原始 BPMN、需求、Gold、预测均未修改；参考判断只在评价阶段读取。",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--check", action="store_true", help="run in memory, write nothing")
    ap.add_argument("--replay", action="store_true", help="rerun from the stored plan and compare")
    args = ap.parse_args()
    result = run(overwrite=args.overwrite, check_only=args.check or args.replay)
    print(json.dumps(result, ensure_ascii=False, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
