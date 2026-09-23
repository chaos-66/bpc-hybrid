# -*- coding: utf-8 -*-
"""Automatic rule-to-process grounding for the Stage 3 paired benchmark.

The module is intentionally independent from Binding Gold.  It consumes only:
- the Direct-LLM Stage-2 Rule Record (plus the frozen Stage-2 sentence input
  needed to recover the character spans that the Rule Record carries), and
- a BPMN Process Record.

For each benchmark pair the runner uses the pair's CONTROL BPMN as the
reference process.  It never reads the benchmark grounding block, target
activity id, expected lane, order pair, mutation manifest, or gold label.
Predictions are persisted before any evaluator is allowed to read a binding
reference.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterable, Mapping, Sequence

from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file
from bpc_hybrid.s3_semantic_grounding_v1 import (
    ACTION_STATUS_RESOLVED,
    ACTION_STATUS_AMBIGUOUS,
    ACTION_STATUS_UNRESOLVED,
    fold_whitespace,
    ground_action,
    normalize_text,
    token_coverage,
    token_jaccard,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DIRECT_PREDICTIONS = (
    ROOT / "data/predictions/gdpr7_direct_llm_v1/predictions.json"
)
DEFAULT_STAGE2_INPUT = ROOT / "data/input/gdpr7_stage2_input_v1.json"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"

SCHEMA_VERSION = "stage3_automatic_grounding_predictions@1.0.0"
METHOD_ID = "automatic_rule_process_grounding_v1"
ALLOWED_BENCHMARK_ITEM_KEYS = (
    "item_id", "pair_id", "role", "bpmn_path", "rule_id", "process_id",
)
FORBIDDEN_INFERENCE_FIELDS = (
    "grounding", "gold_violation_type", "target_violation_type",
    "structural_observation", "bpmn_sha256",
)
RULE_RE = re.compile(r"^gdpr_(?P<rule>.+?)_s\d+$")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rule_id_from_sample_id(sample_id: str) -> str | None:
    match = RULE_RE.match(str(sample_id or ""))
    return match.group("rule") if match else None


def project_benchmark_items(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return only the inference-visible item keys.

    This is the programmatic boundary that keeps mutation answers and binding
    declarations out of the grounding/detector path.
    """
    projected: list[dict[str, Any]] = []
    for raw in doc.get("items") or []:
        item = {key: raw.get(key) for key in ALLOWED_BENCHMARK_ITEM_KEYS}
        if item.get("item_id") and item.get("pair_id") and item.get("bpmn_path"):
            projected.append(item)
    return projected


def load_stage2_sentence_index(path: Path = DEFAULT_STAGE2_INPUT
                               ) -> dict[str, str]:
    doc = _load_json(path)
    out: dict[str, str] = {}
    for rule in doc.get("rules") or []:
        for sentence in rule.get("sentences") or []:
            sample_id = str(sentence.get("sample_id") or "")
            text = str(sentence.get("approved_text_en") or "")
            if sample_id:
                out[sample_id] = text
    return out


def _slice(text: str, span: Mapping[str, Any] | None) -> str:
    if not isinstance(span, Mapping):
        return ""
    start = span.get("start")
    end = span.get("end")
    if not isinstance(start, int) or not isinstance(end, int):
        return ""
    if start < 0 or end < start or end > len(text):
        return ""
    return text[start:end]


def load_direct_llm_rule_index(
    predictions_path: Path = DEFAULT_DIRECT_PREDICTIONS,
    sentence_path: Path = DEFAULT_STAGE2_INPUT,
) -> dict[str, list[dict[str, Any]]]:
    """Build a rich, read-only Direct-LLM Rule Record index.

    The published Rule Record stores character spans, not the sentence text.
    The frozen Stage-2 sentence input is therefore part of the record's
    denotation; no Gold Rule Record is read here.
    """
    predictions = _load_json(predictions_path)
    sentence_by_id = load_stage2_sentence_index(sentence_path)
    out: dict[str, list[dict[str, Any]]] = {}

    for row in predictions.get("records") or []:
        if str(row.get("request_status") or "") not in ("ok", "completed", ""):
            continue
        sample_id = str(row.get("sample_id") or "")
        rule_id = _rule_id_from_sample_id(sample_id)
        if not rule_id:
            continue
        record = row.get("record") or {}
        sentence_text = sentence_by_id.get(sample_id, "")
        clauses = record.get("clauses") or []
        clause_actions: list[dict[str, Any]] = []
        clause_actors: list[dict[str, Any]] = []
        clause_order_relations: list[dict[str, Any]] = []

        for clause_index, clause in enumerate(clauses, start=1):
            clause_id = str(clause.get("clause_id") or
                            f"{sample_id}_c{clause_index:02d}")
            clause_span = clause.get("clause_span") or {}
            clause_text = _slice(sentence_text, clause_span) or sentence_text
            modality = str((clause.get("modality") or {}).get("label") or "")
            actions: list[dict[str, Any]] = []
            actors: list[dict[str, Any]] = []
            action_by_local: dict[str, dict[str, Any]] = {}

            for action_index, action in enumerate(clause.get("actions") or [],
                                                  start=1):
                local_id = str(action.get("id") or f"p{action_index:02d}")
                action_text = _slice(sentence_text, action)
                if not action_text.strip():
                    continue
                item = {
                    "rule_action_id": (
                        f"{sample_id}.c{clause_index}.action.{local_id}"
                    ),
                    "local_id": local_id,
                    "text": fold_whitespace(action_text),
                    "sample_id": sample_id,
                    "rule_id": rule_id,
                    "clause_id": clause_id,
                    "clause_text": fold_whitespace(clause_text),
                    "modality": modality,
                    "actor_ids": [],
                    "actor_texts": [],
                }
                actions.append(item)
                action_by_local[local_id] = item

            for actor_index, actor in enumerate(clause.get("actors") or [],
                                                start=1):
                local_id = str(actor.get("id") or f"a{actor_index:02d}")
                actor_text = _slice(sentence_text, actor)
                if not actor_text.strip():
                    continue
                item = {
                    "rule_actor_id": (
                        f"{sample_id}.c{clause_index}.actor.{local_id}"
                    ),
                    "local_id": local_id,
                    "text": fold_whitespace(actor_text),
                    "sample_id": sample_id,
                    "rule_id": rule_id,
                    "clause_id": clause_id,
                }
                actors.append(item)

            local_actor_map: dict[str, list[str]] = {}
            for pair in clause.get("actor_action_map") or []:
                if not isinstance(pair, Mapping):
                    continue
                actor_local = str(pair.get("actor_id") or "")
                action_local = str(pair.get("action_id") or "")
                if actor_local and action_local:
                    local_actor_map.setdefault(actor_local, []).append(action_local)
            for actor in actors:
                linked_locals = local_actor_map.get(actor["local_id"], [])
                for action_local in linked_locals:
                    action = action_by_local.get(action_local)
                    if action is None:
                        continue
                    if actor["rule_actor_id"] not in action["actor_ids"]:
                        action["actor_ids"].append(actor["rule_actor_id"])
                        action["actor_texts"].append(actor["text"])

            for relation in clause.get("order_relations") or []:
                if not isinstance(relation, Mapping):
                    continue
                before_local = (
                    relation.get("before_action_id")
                    or relation.get("source_action_id")
                    or relation.get("source")
                )
                after_local = (
                    relation.get("after_action_id")
                    or relation.get("target_action_id")
                    or relation.get("target")
                )
                before_action = action_by_local.get(str(before_local or ""))
                after_action = action_by_local.get(str(after_local or ""))
                if not before_action or not after_action:
                    continue
                clause_order_relations.append({
                    "relation_type": str(relation.get("relation")
                                         or relation.get("type") or "before"),
                    "before_rule_action_id": before_action["rule_action_id"],
                    "after_rule_action_id": after_action["rule_action_id"],
                    "source": "direct_llm_rule_record.order_relations",
                })

            clause_actions.extend(actions)
            clause_actors.extend(actors)
            clause_order_relations = clause_order_relations

        if not clause_actions:
            continue
        out.setdefault(rule_id, []).append({
            "sample_id": sample_id,
            "rule_id": rule_id,
            "sentence_text": fold_whitespace(sentence_text),
            "actions": clause_actions,
            "actors": [actor for clause in clauses
                       for actor in clause_actors
                       if actor["sample_id"] == sample_id],
            "order_relations": [
                rel for rel in clause_order_relations
            ],
        })
    return out


def flatten_rule_actions(rule_records: Sequence[Mapping[str, Any]]
                         ) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in rule_records:
        out.extend(record.get("actions") or [])
    return out


def flatten_rule_actors(rule_records: Sequence[Mapping[str, Any]]
                        ) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in rule_records:
        for actor in record.get("actors") or []:
            actor_id = str(actor.get("rule_actor_id") or "")
            if actor_id and actor_id not in seen:
                seen.add(actor_id)
                out.append(actor)
    return out


class TextSimilarity:
    """Cached spaCy-vector similarity with a deterministic lexical fallback."""

    def __init__(self, nlp: Any) -> None:
        self.nlp = nlp
        self._cache: dict[tuple[str, str], float] = {}

    def __call__(self, left: Any, right: Any) -> float:
        left_text = fold_whitespace(left)
        right_text = fold_whitespace(right)
        key = (left_text, right_text)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        score = 0.0
        try:
            doc_left = self.nlp(left_text)
            doc_right = self.nlp(right_text)
            if (getattr(doc_left, "vector_norm", 0.0)
                    and getattr(doc_right, "vector_norm", 0.0)):
                score = float(doc_left.similarity(doc_right))
            elif left_text and right_text:
                score = token_jaccard(left_text, right_text)
        except Exception:
            score = token_jaccard(left_text, right_text) if (
                left_text and right_text) else 0.0
        score = max(0.0, min(1.0, float(score)))
        self._cache[key] = score
        return score


def _activity_lane(record: Mapping[str, Any], activity_id: str) -> str | None:
    for activity in record.get("activities") or []:
        if str(activity.get("id")) == str(activity_id):
            lanes = activity.get("lane_ids") or []
            return str(lanes[0]) if lanes else None
    return None


def _activity_name(record: Mapping[str, Any], activity_id: str) -> str:
    for activity in record.get("activities") or []:
        if str(activity.get("id")) == str(activity_id):
            return str(activity.get("name") or "")
    return ""


def _resource_options(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for lane in record.get("lanes") or []:
        options.append({
            "resource_id": str(lane.get("id") or ""),
            "resource_name": str(lane.get("name") or ""),
            "resource_type": "lane",
        })
    for pool in record.get("pools") or []:
        options.append({
            "resource_id": str(pool.get("id") or ""),
            "resource_name": str(pool.get("name") or ""),
            "resource_type": "pool",
        })
    return options


def _best_action_candidate(ground: Mapping[str, Any],
                           rows: Sequence[Mapping[str, Any]]
                           ) -> Mapping[str, Any] | None:
    if not rows:
        return None
    return sorted(
        rows,
        key=lambda row: (
            -float(row.get("lexical_coverage") or 0.0),
            -float(row.get("similarity") or 0.0),
            str(row.get("activity_id") or ""),
        ),
    )[0]


def ground_reference_process(
    *,
    pair_id: str,
    process_id: str,
    rule_id: str,
    control_bpmn_path: str,
    rule_records: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
    nlp: Any,
) -> dict[str, Any]:
    """Ground one rule record against one reference (control) BPMN."""
    process_path = ROOT / control_bpmn_path
    record = parse_bpmn_file(process_path, contract=contract)
    model = SimpleNamespace(actions=record.get("activities") or [])
    sim = TextSimilarity(nlp)

    actions: list[dict[str, Any]] = []
    detector_ids: set[str] = set()
    detector_scores: dict[str, float] = {}
    for action in flatten_rule_actions(rule_records):
        ground = ground_action(
            action.get("text") or "",
            model,
            record,
            sim,
            gamma=0.40,
            top_k_similarity=5,
            top_k_lexical=5,
        )
        rows = list(ground.get("candidates") or [])
        best = _best_action_candidate(ground, rows)
        predicted_activity_id = (
            ground.get("activity_id")
            or (best.get("activity_id") if best else None)
        )
        candidate_ids = list(ground.get("candidate_activity_ids") or [])
        strong_ids = list(ground.get("strong_activity_ids") or [])
        for activity_id in candidate_ids:
            detector_ids.add(str(activity_id))
        if predicted_activity_id:
            detector_ids.add(str(predicted_activity_id))
        for row in rows:
            activity_id = str(row.get("activity_id") or "")
            if not activity_id:
                continue
            score = max(
                float(row.get("lexical_coverage") or 0.0),
                float(row.get("similarity") or 0.0),
            )
            detector_scores[activity_id] = max(
                detector_scores.get(activity_id, 0.0), score
            )
        actions.append({
            "rule_action_id": action.get("rule_action_id"),
            "rule_action_text": action.get("text"),
            "sample_id": action.get("sample_id"),
            "clause_id": action.get("clause_id"),
            "modality": action.get("modality"),
            "actor_ids": list(action.get("actor_ids") or []),
            "status": ground.get("status"),
            "reason": ground.get("reason"),
            "predicted_activity_id": predicted_activity_id,
            "candidate_activity_ids": candidate_ids,
            "strong_activity_ids": strong_ids,
            "best_activity_id": best.get("activity_id") if best else None,
            "best_similarity": best.get("similarity") if best else None,
            "best_lexical_coverage": best.get("lexical_coverage") if best else None,
        })

    detector_activity_ids = sorted(detector_ids)
    activity_lane_map = {
        activity_id: _activity_lane(record, activity_id)
        for activity_id in detector_activity_ids
    }
    activity_name_map = {
        activity_id: _activity_name(record, activity_id)
        for activity_id in detector_activity_ids
    }

    # Actor grounding is resource matching plus structural owner evidence.
    resources = _resource_options(record)
    actor_predictions: list[dict[str, Any]] = []
    action_by_id = {
        str(a.get("rule_action_id")): a for a in actions
    }
    for actor in flatten_rule_actors(rule_records):
        actor_text = str(actor.get("text") or "")
        ranked_resources: list[dict[str, Any]] = []
        for resource in resources:
            name = str(resource.get("resource_name") or "")
            if not name.strip():
                continue
            semantic = sim(actor_text, name)
            lexical = max(token_coverage(actor_text, name),
                          token_jaccard(actor_text, name))
            ranked_resources.append({
                **resource,
                "semantic_similarity": round(semantic, 6),
                "lexical_score": round(lexical, 6),
                "combined_score": round(max(semantic, lexical), 6),
            })
        ranked_resources.sort(
            key=lambda row: (-row["combined_score"],
                             row["resource_type"],
                             row["resource_id"])
        )
        predicted_resource = (
            ranked_resources[0] if ranked_resources
            and ranked_resources[0]["combined_score"] >= 0.35 else None
        )
        associated_activity_ids: set[str] = set()
        for action in actions:
            if str(actor.get("rule_actor_id")) in (
                    action.get("actor_ids") or []
            ):
                associated_activity_ids.update(
                    str(x) for x in action.get("candidate_activity_ids") or []
                )
                if action.get("predicted_activity_id"):
                    associated_activity_ids.add(
                        str(action["predicted_activity_id"])
                    )
        actor_predictions.append({
            "rule_actor_id": actor.get("rule_actor_id"),
            "rule_actor_text": actor_text,
            "predicted_resource": predicted_resource,
            "candidate_activity_ids": sorted(associated_activity_ids),
        })

    order_predictions: list[dict[str, Any]] = []
    for record_item in rule_records:
        for relation in record_item.get("order_relations") or []:
            before_id = str(relation.get("before_rule_action_id") or "")
            after_id = str(relation.get("after_rule_action_id") or "")
            before_action = action_by_id.get(before_id) or {}
            after_action = action_by_id.get(after_id) or {}
            order_predictions.append({
                "before_rule_action_id": before_id,
                "after_rule_action_id": after_id,
                "before_activity_ids": (
                    before_action.get("candidate_activity_ids") or []
                ),
                "after_activity_ids": (
                    after_action.get("candidate_activity_ids") or []
                ),
                "before_predicted_activity_id": (
                    before_action.get("predicted_activity_id")
                ),
                "after_predicted_activity_id": (
                    after_action.get("predicted_activity_id")
                ),
                "relation_type": relation.get("relation_type") or "before",
                "source": relation.get("source")
                or "direct_llm_rule_record.order_relations",
            })

    return {
        "pair_id": pair_id,
        "process_id": process_id,
        "rule_id": rule_id,
        "reference_role": "control",
        "reference_bpmn_path": control_bpmn_path,
        "reference_bpmn_sha256": _sha256(process_path),
        "actions": actions,
        "detector_activity_ids": detector_activity_ids,
        "detector_activity_scores": detector_scores,
        "activity_lane_map": activity_lane_map,
        "activity_name_map": activity_name_map,
        "actor_predictions": actor_predictions,
        "order_predictions": order_predictions,
        "unobservable_reasons": (
            ["no_rule_actions"] if not actions else []
        ),
    }


def build_all_grounding_predictions(
    *,
    benchmark_path: Path,
    direct_predictions_path: Path = DEFAULT_DIRECT_PREDICTIONS,
    sentence_input_path: Path = DEFAULT_STAGE2_INPUT,
    nlp: Any,
    contract_path: Path = STRUCTURAL_CONTRACT,
) -> dict[str, Any]:
    benchmark = _load_json(benchmark_path)
    items = project_benchmark_items(benchmark)
    contract = load_stage1_contract(contract_path)
    rule_index = load_direct_llm_rule_index(
        direct_predictions_path, sentence_input_path
    )
    controls: dict[str, dict[str, Any]] = {}
    for item in items:
        if item.get("role") == "control":
            controls[str(item["pair_id"])] = item

    rows: list[dict[str, Any]] = []
    for pair_id, control in sorted(controls.items()):
        rule_id = str(control.get("rule_id") or "")
        rows.append(ground_reference_process(
            pair_id=pair_id,
            process_id=str(control.get("process_id") or ""),
            rule_id=rule_id,
            control_bpmn_path=str(control.get("bpmn_path") or ""),
            rule_records=rule_index.get(rule_id, []),
            contract=contract,
            nlp=nlp,
        ))

    return {
        "schema_version": SCHEMA_VERSION,
        "method_id": METHOD_ID,
        "benchmark_id": benchmark.get("benchmark_id"),
        "benchmark_sha256": _sha256(benchmark_path),
        "direct_predictions_path": str(
            direct_predictions_path.relative_to(ROOT)
        ).replace("\\", "/"),
        "direct_predictions_sha256": _sha256(direct_predictions_path),
        "stage2_input_path": str(
            sentence_input_path.relative_to(ROOT)
        ).replace("\\", "/"),
        "stage2_input_sha256": _sha256(sentence_input_path),
        "inference_inputs": [
            "Direct-LLM Rule Record + frozen Stage-2 sentence spans",
            "reference (control) BPMN Process Record",
        ],
        "forbidden_inputs_not_read": list(FORBIDDEN_INFERENCE_FIELDS)
        + ["binding_reference", "mutation_manifest", "gold_label"],
        "gold_read": False,
        "binding_reference_read": False,
        "network_calls": 0,
        "llm_api_calls": 0,
        "rows": rows,
    }


__all__ = [
    "ALLOWED_BENCHMARK_ITEM_KEYS",
    "FORBIDDEN_INFERENCE_FIELDS",
    "ROOT",
    "TextSimilarity",
    "build_all_grounding_predictions",
    "flatten_rule_actions",
    "flatten_rule_actors",
    "ground_reference_process",
    "load_direct_llm_rule_index",
    "load_stage2_sentence_index",
    "project_benchmark_items",
]
