# -*- coding: utf-8 -*-
"""S3.9-EXT-REAL-CASE core: SIM card scenario, groups A / B / C (development only).

Fixed design (declared before any scoring; see the task spec v5):

* **One public Stage 1 record.** The SIM BPMN is parsed once with the frozen
  Stage 1 contract; all three groups consume that same Process Record. The raw
  XML root used by the extended candidate surfaces is parsed from the SAME bytes
  and its hash is recorded.
* **Group A** - non-LLM Stage 2: the project's deterministic six-element
  adapter (`extract_six_element_sentences`) over the version-2 rule text,
  plus the frozen Sun-style three-type detection.
* **Group B** - Stage 2 replaced by the existing real-LLM predictions
  (`OURS-FULL` repeat-01 primary), projected with `project_external_sentence`;
  the three-type detection is the SAME code and thresholds as A.
* **Group C** - same Stage 2 and same three-type results as B, plus the four
  extended types.

Adaptation policies are declared in :data:`ADAPTATION_POLICY` and applied
identically to every group.  Reference judgments (the development reading of
what is wrong in the process) live in the curated data file and are NEVER read
on the prediction path; they are only used afterwards for the comparison table.

Zero LLM/API, no network, deterministic.  `references/` is read in place.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
REF = REPO / "references" / "barrientos_2026"

BPMN = REF / "artifact_input" / "process_models" / "SIM_card_scenario" / "SIM_card_scenario.bpmn"
REQUIREMENTS = REF / "artifact_input" / "requirements" / "SIM_card_scenario" / "SIM_card_scenario.json"
STEP3 = REF / "evaluation" / "ground_truth" / "step_3_baseline.json"
CURATED = ROOT / "data" / "development" / "sim_case_c1" / "case_items_v2.json"
PRED_DIR = ROOT / "outputs" / "development" / "barrientos_ablation_suite_v2" / "OURS-FULL"
STAGE1_CONTRACT = ROOT / "configs" / "stage1_structural_s11_s14.json"
SUN_CONFIG = ROOT / "configs" / "sun_stage3_development_v1.json"
REPAIR_SPECS = ROOT / "data" / "development" / "sim_case_c1" / "repair_specs_v1.json"

MAIN_RULES = ["r8", "r9", "r10", "r11", "r13"]
BACKGROUND_RULES = ["r12"]
EXTENDED = ("prohibited_action_present", "required_condition_not_enforced",
            "constraint_violated", "exception_not_handled")

ADAPTATION_POLICY = {
    "name": "sim_case_c1_public_adaptation_v1",
    "declared_before_scoring": True,
    "role_binding": {"Data Controller": "Phone company", "Data Subject": "Customer"},
    "primary_sentence": "longest_sentence_text_v1",
    "span_projection": {
        "name": "first_valid_span_per_field_v1_with_diagnostics",
        "action_actor_pairing": "explicit_prediction_actor_action_map_only_v1",
        "action_obligation_policy": (
            "只有预测显式 actor_action_map 中的 action 进入 rule.actions；未配对动作候选保留在"
            "selection_metadata/unconsumed_candidates 中，但不自动视为独立义务。"
        ),
        "single_value_scorers": ["condition", "constraint", "exception"],
        "note_zh": (
            "投影保留所有有效候选文本用于追踪；检测器若只消费单项，则在 chain 中记录"
            "projected→adapted→consumed 的数量变化和选择政策，不标成全部保留。"
        ),
    },
    "order_relation_derivation": {
        "name": "temporal_marker_from_condition_v2",
        "rule_zh": (
            "当抽取出的 condition 以 before/after 时间标记开头时，按该标记在主动作与条件内动作之间生成一条顺序关系："
            "'Before X, Y' -> (Y, X)；'After X, Y' -> (X, Y)。端点取逗号前的条件片段；"
            "没有逗号时取整个条件片段（两种写法语义相同）。非时间标记的条件（if / when 等）不生成顺序关系，"
            "所以条件触发不会被当成顺序断言。该 policy 对 A/B 两组统一施加，不读取任何外部答案或偏离标签"
        ),
        "applies_to_groups": ["A", "B", "C"],
        "comma_handling": "comma_optional_v2",
        "fix_note_zh": (
            "v1 的正则要求条件片段里必须有逗号，而本案例的抽取结果（如 After receiving the customer's personal "
            "information）没有逗号，导致 r9/r11 在三组里都报 no_mapped_rule_order_endpoints。v2 允许无逗号。"
        ),
    },
    "forbidden": [
        "不得按结果新增角色绑定、动作同义词或规则 ID 特判",
        "不得用外部偏差标签或参考判断回填规则记录",
    ],
}

STATUS_VIOLATION = "violation"
STATUS_SATISFIED = "satisfied"
STATUS_UNDETERMINED = "undetermined"
STATUS_NOT_APPLICABLE = "not_applicable"

STAGE_SOURCES = ("rule_not_applicable", "extraction", "adaptation", "process_expressiveness",
                 "detection", "unattributed")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {"path": str(path.relative_to(REPO)).replace("\\", "/"),
            "sha256": sha256_bytes(payload), "bytes": len(payload)}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_requirements() -> dict[tuple[str, int], str]:
    return {(e["ID"], int(e["version"])): (e.get("text") or "") for e in load_json(REQUIREMENTS)}


# ---------------------------------------------------------------------------
# Stage 1 (single public record)
# ---------------------------------------------------------------------------

def build_stage1(contract_config: Path) -> dict[str, Any]:
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file, validate_process_record

    contract = load_stage1_contract(contract_config)
    payload = BPMN.read_bytes()
    record = parse_bpmn_file(BPMN, contract=contract)
    validation = validate_process_record(record)
    if not getattr(validation, "valid", False):
        raise SystemExit(f"stage1 record invalid: {validation}")
    xml_root = ET.fromstring(payload)
    return {
        "record": record,
        "xml_root": xml_root,
        "evidence": {
            "bpmn": artifact(BPMN),
            "stage1_contract": artifact(contract_config),
            "process_record_sha256": sha256_bytes(
                json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")),
            "process_id": record.get("process_id"),
            "activities": len(record.get("activities", [])),
            "gateways": len(record.get("gateways", [])),
            "events": len(record.get("events", [])),
            "flows": len(record.get("sequence_flows", [])),
            "reachable_pairs": len(record.get("control_flow", {}).get("reachable_pairs", [])),
            "xml_root_source": "same bytes as the parsed BPMN (single parse, single hash)",
        },
    }


def build_model(stage1: dict[str, Any], nlp) -> Any:
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from bpc_hybrid.sun_stage3.sun_model import SunProcessModel
    return SunProcessModel(stage1["record"]["process_id"], stage1["record"], nlp)


# ---------------------------------------------------------------------------
# Stage 2 (A: deterministic adapter; B/C: existing real-LLM predictions)
# ---------------------------------------------------------------------------

def stage2_group_a(rule_id: str, rule_text: str, nlp) -> dict[str, Any]:
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from bpc_hybrid.stage3_extended_violations import extract_six_element_sentences

    sentences = extract_six_element_sentences(rule_id, rule_text, nlp)
    if not sentences:
        return {"ok": False, "error": "adapter_returned_no_sentence", "sentence": None}
    primary = max(sentences, key=lambda s: len(s.get("sentence_text") or ""))
    return {"ok": True, "error": None, "sentence": dict(primary),
            "sentence_count": len(sentences)}


def load_predictions(repeat: int) -> dict[str, Any]:
    path = PRED_DIR / f"repeat-{repeat:02d}" / "canonical_predictions.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    sim = {r["sample_id"]: r for r in rows if str(r.get("sample_id", "")).startswith("SIM_card_scenario/")}
    return {"artifact": artifact(path), "rows": sim}


def stage2_group_b(rule_id: str, rule_text: str, predictions: dict[str, Any]) -> dict[str, Any]:
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from bpc_hybrid.gdpr_s2_s3_projection import project_external_sentence

    sample_id = f"SIM_card_scenario/{rule_id}/v2"
    pred = predictions["rows"].get(sample_id)
    if pred is None:
        return {"ok": False, "error": "prediction_row_missing", "sentence": None}
    projected = project_external_sentence(pred, rule_text, sample_id)
    if not projected.get("ok"):
        return {"ok": False, "error": projected.get("error"), "sentence": None,
                "diagnostics": projected.get("diagnostics")}
    return {"ok": True, "error": None, "sentence": projected["sentence"],
            "diagnostics": projected.get("diagnostics")}


def apply_role_binding(sentence: dict[str, Any]) -> dict[str, Any]:
    """Apply the declared scenario role binding to the actor text."""
    bound = dict(sentence)
    actor = (sentence.get("actor") or "")
    for source, target in ADAPTATION_POLICY["role_binding"].items():
        if source.lower() in actor.lower():
            bound["actor"] = target
            bound["actor_bound_from"] = source
            break
    return bound


_ORDER_AFTER = re.compile(r"^\s*after\s+(?P<clause>.+)$", re.IGNORECASE | re.DOTALL)
_ORDER_BEFORE = re.compile(r"^\s*before\s+(?P<clause>.+)$", re.IGNORECASE | re.DOTALL)


def _split_marker_clause(clause: str) -> str:
    """Take the temporal clause, with or without a comma separator.

    Extractions may look like "After receiving the customer's personal
    information" (no comma) or "After receiving the data, the controller shall
    notify" (comma).  Both are the same temporal marker; the endpoint is what
    precedes the comma, or the whole remainder when no comma is present.
    """
    head = re.split(r",", clause, maxsplit=1)[0]
    return head.strip(" .;")


def derive_order_relations(sentence: dict[str, Any]) -> list[tuple[str, str]]:
    """Declared, group-independent template policy (see ADAPTATION_POLICY).

    Applies to comma and comma-less temporal conditions alike; conditions whose
    marker is not a temporal precedence marker (e.g. "if", "when") yield no
    relation, so a conditional trigger is never turned into an order claim.
    """
    condition = (sentence.get("condition") or "").strip()
    action = (sentence.get("action") or "").strip()
    if not condition or not action:
        return []
    match = _ORDER_AFTER.match(condition)
    if match:
        before = _split_marker_clause(match.group("clause"))
        return [(before, action)] if before else []
    match = _ORDER_BEFORE.match(condition)
    if match:
        after = _split_marker_clause(match.group("clause"))
        return [(action, after)] if after else []
    return []


def _dedup_texts(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values or []:
        text = (value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _projected_candidates(sentence: dict[str, Any], field: str) -> list[str]:
    diagnostics = sentence.get("diagnostics") or {}
    return _dedup_texts((diagnostics.get("span_field_texts") or {}).get(field) or [])


def _explicit_actor_action_pairs(sentence: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Return only links explicitly predicted by Stage 2.

    The case wrapper must not turn a co-occurring actor and action into a pair.
    Invalid links (for example a null actor id) are preserved as diagnostics
    and never repaired by role heuristics.
    """
    diagnostics = sentence.get("diagnostics") or {}
    valid: list[dict[str, str]] = []
    invalid: list[dict[str, Any]] = []
    for entry in diagnostics.get("actor_action_map") or []:
        actor = (entry.get("actor_text") or "").strip()
        action = (entry.get("action_text") or "").strip()
        if entry.get("valid") and actor and action:
            valid.append({"actor": actor, "action": action})
        else:
            invalid.append({
                "actor_id": entry.get("actor_id") or entry.get("raw_actor_id"),
                "action_id": entry.get("action_id") or entry.get("raw_action_id"),
                "reason": entry.get("reason") or "invalid_actor_action_link",
                "actor_text": actor or None,
                "action_text": action or None,
            })
    return valid, invalid


def build_rule_record(sentence: dict[str, Any]) -> dict[str, Any]:
    diagnostic_fields = {
        field: _projected_candidates(sentence, field)
        for field in ("actor", "action", "condition", "constraint", "exception")
    }
    explicit_pairs, invalid_pairs = _explicit_actor_action_pairs(sentence)

    if explicit_pairs:
        actions = _dedup_texts([pair["action"] for pair in explicit_pairs])
        actors = _dedup_texts([pair["actor"] for pair in explicit_pairs])
        actor_action_pairs: list[dict[str, str]] = list(explicit_pairs)
        action_policy = "explicit_actor_action_map_v1"
        actor_policy = "explicit_actor_action_map_v1"
    else:
        # No explicit map was supplied (or its actor was null).  Keep the
        # single projected action for the action-existence check, but do not
        # manufacture an actor-action pair.  The frozen Def6 then abstains with
        # missing_rule_actor_action_map instead of inventing ownership.
        projected_action = (sentence.get("action") or "").strip()
        projected_actor = (sentence.get("actor") or "").strip()
        actions = [projected_action] if projected_action else []
        actors = [projected_actor] if projected_actor else []
        actor_action_pairs = []
        action_policy = "projected_single_action_no_explicit_map_v1"
        actor_policy = "projected_single_actor_no_explicit_map_v1"

    condition = (sentence.get("condition") or "").strip() or None
    constraint = (sentence.get("constraint") or "").strip() or None
    exception = (sentence.get("exception") or "").strip() or None
    order_relations = derive_order_relations(sentence)
    consumed_by_diagnostic_field = {
        "actor": actors,
        "action": actions,
        "condition": [condition] if condition else [],
        "constraint": [constraint] if constraint else [],
        "exception": [exception] if exception else [],
    }
    unconsumed = {
        field: [text for text in diagnostic_fields.get(field, [])
                if text not in consumed_by_diagnostic_field.get(field, [])]
        for field in diagnostic_fields
    }
    metadata = {
        "candidate_fields": diagnostic_fields,
        "field_selection_policy": {
            "actions": action_policy,
            "actors": actor_policy,
            "condition": "first_valid_span_v1_single_value_extended_scorer",
            "constraint": "first_valid_span_v1_single_value_extended_scorer",
            "exception": "first_valid_span_v1_single_value_extended_scorer",
            "order_relations": ADAPTATION_POLICY["order_relation_derivation"]["name"],
        },
        "unconsumed_candidates": unconsumed,
        "invalid_actor_action_links": invalid_pairs,
        "explicit_actor_action_pair_count": len(explicit_pairs),
        "actor_action_pair_source": "prediction_actor_action_map" if explicit_pairs else "none_no_fabrication",
    }
    return {
        "rule_id": sentence.get("rule_id"),
        "modality": sentence.get("modality"),
        "actions": actions,
        "actors": actors,
        "actor_action_pairs": actor_action_pairs,
        "order_relations": order_relations,
        "condition": condition,
        "constraint": constraint,
        "exception": exception,
        "sentence_text": sentence.get("sentence_text"),
        "selection_metadata": metadata,
    }


def _status_from_score(score: float | None, denominator: int) -> str:
    if denominator == 0:
        return STATUS_NOT_APPLICABLE
    if score is None:
        return STATUS_UNDETERMINED
    return STATUS_VIOLATION if score > 0 else STATUS_SATISFIED


def _owner_evidence(model: Any, activity_ids: list[str]) -> list[dict[str, Any]]:
    owners_by_id = getattr(model, "action_actor_names", {}) or {}
    result = []
    for activity_id in activity_ids or []:
        owners = list(owners_by_id.get(activity_id, []) or [])
        result.append({"activity_id": activity_id, "owners": owners})
    return result


def run_three_types(scorer, rule: dict[str, Any], model: Any) -> dict[str, Any]:
    ma = scorer.missing_action(rule["actions"], model)
    ia = scorer.incorrect_actor(rule["actions"], rule["actors"], model, rule.get("actor_action_pairs"))
    oo = scorer.out_of_order(rule["order_relations"], rule["actions"], model)

    ma_machine_status = _status_from_score(ma["score"], ma["denominator"])
    if ma["denominator"] == 0:
        ma_status = STATUS_UNDETERMINED
        ma_source = "extraction"
        ma_eval_reason = "empty_rule_action_rule_element_not_extracted"
    else:
        ma_status = ma_machine_status
        ma_source = "detector"
        ma_eval_reason = None

    ia_observable = bool(ia.get("observable"))
    if ia_observable:
        ia_machine_status = _status_from_score(ia.get("score"), ia.get("denominator") or 0)
        ia_status = ia_machine_status
        ia_source = "detector"
        ia_eval_reason = None
    else:
        ia_machine_status = STATUS_UNDETERMINED
        ia_status = STATUS_UNDETERMINED
        ia_source = "detector_abstention"
        ia_eval_reason = ia.get("reason") or "detector_unobservable"

    if oo["denominator"] == 0:
        oo_machine_status = STATUS_UNDETERMINED
        oo_status = STATUS_UNDETERMINED
        oo_source = "extraction_or_mapping"
        oo_eval_reason = "no_mapped_rule_order_endpoints"
    else:
        oo_machine_status = _status_from_score(oo["score"], oo["denominator"])
        oo_status = oo_machine_status
        oo_source = "detector"
        oo_eval_reason = None

    matched_ids = list(ia.get("matched_process_action_ids") or [])
    primary_action = (rule.get("actions") or [None])[0]
    primary_action_match = None
    primary_action_owner_evidence = []
    if primary_action:
        best_name, best_score = scorer._best_action_match(primary_action, model)
        primary_action_match = {"rule_action": primary_action, "best_model_action": best_name,
                                "similarity": round(best_score, 6) if best_score is not None else None}
        best_id = next((act["id"] for act in model.actions
                        if act.get("name") == best_name), None)
        if best_id:
            primary_action_owner_evidence = _owner_evidence(model, [best_id])
    rows = {
        "missing_action": {
            "status": ma_status,
            "machine_status": ma_machine_status,
            "evaluation_status": ma_status,
            "status_source": ma_source,
            "evaluation_reason": ma_eval_reason,
            "machine_reason": "empty_rule_action" if ma["denominator"] == 0 else None,
            "observable": ma["denominator"] > 0,
            "score": ma["score"], "denominator": ma["denominator"],
            "details": ma["details"],
            "reason": None if ma["denominator"] else "empty_rule_action",
        },
        "incorrect_actor": {
            "status": ia_status,
            "machine_status": ia_machine_status,
            "evaluation_status": ia_status,
            "status_source": ia_source,
            "evaluation_reason": ia_eval_reason,
            "machine_reason": ia.get("reason"),
            "observable": ia_observable,
            "score": ia.get("score"), "denominator": ia.get("denominator"),
            "details": ia.get("details", []),
            "process_actor_candidates": ia.get("process_actor_candidates", []),
            "matched_process_action_ids": matched_ids,
            "matched_action_owner_evidence": _owner_evidence(model, matched_ids),
            "primary_action_match": primary_action_match,
            "primary_action_owner_evidence": primary_action_owner_evidence,
            "actor_scope_policy": ia.get("actor_scope_policy"),
        },
        "out_of_order": {
            "status": oo_status,
            "machine_status": oo_machine_status,
            "evaluation_status": oo_status,
            "status_source": oo_source,
            "evaluation_reason": oo_eval_reason,
            "machine_reason": None if oo["denominator"] else "no_mapped_rule_order_endpoints",
            "observable": oo["denominator"] > 0,
            "score": oo["score"], "denominator": oo["denominator"],
            "details": oo["details"],
            "reason": None if oo["denominator"] else "no_mapped_rule_order_endpoints",
        },
    }
    return rows


def run_extended_types(scorer, sentence: dict[str, Any], model: Any, record: dict[str, Any],
                       xml_root: Any, activity_id: str | None) -> dict[str, Any]:
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from bpc_hybrid.stage3_extended_violations import (
        condition_candidates, constraint_candidates, exception_candidates,
    )

    cond = condition_candidates(record, xml_root, activity_id)
    cons = constraint_candidates(record, xml_root, activity_id)
    exc = exception_candidates(record, xml_root, activity_id)

    raw = {
        "prohibited_action_present": scorer.prohibited_action(sentence, model),
        "required_condition_not_enforced": scorer.required_condition(sentence, model, cond),
        "constraint_violated": scorer.constraint_violated(sentence, model, cons),
        "exception_not_handled": scorer.exception_not_handled(sentence, model, exc),
    }
    rows = {}
    for name, result in raw.items():
        if not result.get("observable"):
            status, reason = STATUS_UNDETERMINED, result.get("reason")
        elif result.get("violation"):
            status, reason = STATUS_VIOLATION, result.get("reason")
        else:
            status, reason = STATUS_SATISFIED, result.get("reason")
        rows[name] = {
            "status": status,
            "machine_status": status,
            "evaluation_status": status,
            "status_source": "detector" if result.get("observable") else "detector_abstention",
            "evaluation_reason": None if result.get("observable") else reason,
            "score": result.get("score"), "reason": reason,
            "observable": bool(result.get("observable")),
            "abstention_kind": result.get("abstention_kind"),
            "candidate_count": {"required_condition_not_enforced": len(cond),
                                "constraint_violated": len(cons),
                                "exception_not_handled": len(exc)}.get(name),
            "best_candidate": result.get("best_candidate"),
            "max_sim": result.get("max_sim"),
            "gamma_ext": scorer.gamma_ext,
            "comparison_performed": bool(result.get("comparison_performed")),
            "exact_contradiction": result.get("exact_contradiction"),
            "matched_activity_id": result.get("matched_activity_id"),
            "action_max_sim": result.get("action_max_sim"),
            "action_resolution": result.get("action_resolution"),
            "resolved_by": result.get("resolved_by"),
            "resolved_activity_label": result.get("resolved_activity_label"),
            "unresolved_reason": result.get("unresolved_reason"),
            "raw_winner_label": result.get("raw_winner_label"),
            "raw_winner_similarity": result.get("raw_winner_similarity"),
        }
    return rows, {"condition_candidates": list(map(str, cond)),
                  "constraint_candidates": list(map(str, cons)),
                  "exception_candidates": list(map(str, exc)),
                  "activity_id": activity_id}, raw


def best_activity_for(sentence: dict[str, Any], model: Any, sim) -> tuple[str | None, float | None, str | None]:
    action = (sentence.get("action") or "").strip()
    if not action:
        return None, None, None
    best_name, best_score = None, -1.0
    for act in model.actions:
        name = (act.get("name") or "").strip()
        if not name:
            continue
        score = sim.text_pair(action, name)
        if score > best_score:
            best_name, best_score = name, score
    best_id = next((a["id"] for a in model.actions if a.get("name") == best_name), None)
    return best_id, round(best_score, 6), best_name
