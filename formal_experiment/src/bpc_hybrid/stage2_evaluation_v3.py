"""S2.10-E v3 evaluator with method-independent span alignment.

The v1.1 evaluator aligned clauses and entities by exact identifiers before
falling back to exact raw spans.  That contract is unsuitable when Gold and
methods create identifiers independently and when sentence parsers include a
trailing punctuation character that a human semantic clause omits.

Version 1.2 keeps exact sample membership and all failure denominators, but
aligns clauses by deterministic maximum-total character-span IoU with a fixed
0.5 majority-overlap threshold.  Entity IDs are treated as method-local:
strict metrics use exact raw-span matching, safe metrics use the frozen safe
normalization profile, and token metrics use maximum-total positive token IoU.
Exact clause segmentation remains a separate structural metric.

No threshold search, paper-score target, Gold mutation, network call, or model
call occurs in this module.
"""

from __future__ import annotations

import copy
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from bpc_hybrid import stage2_evaluation as v2
from bpc_hybrid.stage2_canonical import VALID_MODALITIES


CONTRACT_VERSION = "stage2_evaluator_contract@1.2.0"
REPORT_VERSION = "stage2_evaluation_report@1.2.0"
CLAUSE_ALIGNMENT_NAME = "maximum_total_character_span_iou"
ENTITY_ALIGNMENT_NAME = "metric_specific_method_local_ids_ignored"
CLAUSE_MINIMUM_IOU = 0.5
TEXT_FIELDS = v2.TEXT_FIELDS
FIELD_LABELS = v2.FIELD_LABELS
Stage2EvaluationError = v2.Stage2EvaluationError
membership_sha256 = v2.membership_sha256
sha256_file = v2.sha256_file
sha256_json = v2.sha256_json
build_style_review_template = v2.build_style_review_template
validate_style_review_document = v2.validate_style_review_document


def load_evaluator_contract(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage2EvaluationError(f"invalid v3 evaluator contract: {path}") from exc
    if not isinstance(value, dict):
        raise Stage2EvaluationError("v3 evaluator contract root must be an object")
    alignment = value.get("alignment", {})
    if (
        value.get("schema_version") != CONTRACT_VERSION
        or value.get("task_id") != "S2.10-E"
        or alignment.get("clause") != CLAUSE_ALIGNMENT_NAME
        or alignment.get("clause_minimum_iou") != CLAUSE_MINIMUM_IOU
        or alignment.get("entity") != ENTITY_ALIGNMENT_NAME
        or alignment.get("prediction_ids_are_method_local") is not True
        or alignment.get("paper_score_targeting_forbidden") is not True
    ):
        raise Stage2EvaluationError("v3 evaluator identity or alignment contract changed")
    profiles = value.get("normalization", {}).get("profiles", {})
    if profiles.get("strict") != [] or profiles.get("safe") != [
        "unicode_nfc",
        "lowercase",
        "whitespace_collapse",
        "trailing_punctuation_strip",
    ]:
        raise Stage2EvaluationError("v3 normalization profiles changed")
    if value.get("methods") != ["sun_rule_only", "sun_llm_fallback", "direct_llm"]:
        raise Stage2EvaluationError("v3 method set changed")
    return value


def _item_span(item: Mapping[str, Any]) -> Mapping[str, Any]:
    return item.get("clause_span", item)


def _stable_item_key(item: Mapping[str, Any]) -> tuple[Any, ...]:
    span = _item_span(item)
    return (
        int(span.get("start", -1)),
        int(span.get("end", -1)),
        str(span.get("text", "")),
        str(item.get("clause_id") or item.get("id") or ""),
    )


def _hungarian_max(weights: Sequence[Sequence[float]]) -> list[tuple[int, int]]:
    """Return a deterministic maximum-weight assignment for a square matrix."""
    size = len(weights)
    if size == 0:
        return []
    if any(len(row) != size for row in weights):
        raise Stage2EvaluationError("Hungarian matrix must be square")
    # Potentials implementation for min-cost assignment; negate weights to
    # maximize.  Strict '<' comparisons and ascending columns freeze ties.
    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)
    epsilon = 1e-15
    for row in range(1, size + 1):
        p[0] = row
        minv = [math.inf] * (size + 1)
        used = [False] * (size + 1)
        column = 0
        while True:
            used[column] = True
            active_row = p[column]
            delta = math.inf
            next_column = 0
            for candidate in range(1, size + 1):
                if used[candidate]:
                    continue
                reduced = -weights[active_row - 1][candidate - 1] - u[active_row] - v[candidate]
                if reduced < minv[candidate] - epsilon:
                    minv[candidate] = reduced
                    way[candidate] = column
                if (
                    minv[candidate] < delta - epsilon
                    or abs(minv[candidate] - delta) <= epsilon
                    and (next_column == 0 or candidate < next_column)
                ):
                    delta = minv[candidate]
                    next_column = candidate
            if next_column == 0 or not math.isfinite(delta):
                raise Stage2EvaluationError("Hungarian assignment failed")
            for candidate in range(size + 1):
                if used[candidate]:
                    u[p[candidate]] += delta
                    v[candidate] -= delta
                else:
                    minv[candidate] -= delta
            column = next_column
            if p[column] == 0:
                break
        while True:
            previous = way[column]
            p[column] = p[previous]
            column = previous
            if column == 0:
                break
    return sorted((p[column] - 1, column - 1) for column in range(1, size + 1))


def _maximum_weight_pairs(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
    *,
    score: Callable[[Mapping[str, Any], Mapping[str, Any]], float],
    minimum: float,
) -> tuple[list[tuple[int, int]], list[int], list[int], dict[tuple[int, int], float]]:
    """Globally align two item sets without using array position or IDs."""
    if not left or not right:
        return [], list(range(len(left))), list(range(len(right))), {}
    left_order = sorted(range(len(left)), key=lambda index: _stable_item_key(left[index]))
    right_order = sorted(range(len(right)), key=lambda index: _stable_item_key(right[index]))
    size = max(len(left_order), len(right_order))
    weights = [[0.0 for _ in range(size)] for _ in range(size)]
    observed: dict[tuple[int, int], float] = {}
    for stable_left, original_left in enumerate(left_order):
        for stable_right, original_right in enumerate(right_order):
            value = float(score(left[original_left], right[original_right]))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise Stage2EvaluationError("alignment score must be a finite rate")
            observed[(original_left, original_right)] = value
            if value + 1e-15 >= minimum:
                weights[stable_left][stable_right] = value
    pairs: list[tuple[int, int]] = []
    for stable_left, stable_right in _hungarian_max(weights):
        if stable_left >= len(left_order) or stable_right >= len(right_order):
            continue
        original_left = left_order[stable_left]
        original_right = right_order[stable_right]
        if observed[(original_left, original_right)] + 1e-15 >= minimum:
            pairs.append((original_left, original_right))
    pairs.sort()
    used_left = {left_index for left_index, _ in pairs}
    used_right = {right_index for _, right_index in pairs}
    return (
        pairs,
        sorted(set(range(len(left))) - used_left),
        sorted(set(range(len(right))) - used_right),
        observed,
    )


def clause_iou_pairs(
    gold: Sequence[Mapping[str, Any]],
    predicted: Sequence[Mapping[str, Any]],
    *,
    minimum_iou: float = CLAUSE_MINIMUM_IOU,
) -> tuple[list[tuple[int, int]], list[int], list[int], dict[tuple[int, int], float]]:
    return _maximum_weight_pairs(
        gold,
        predicted,
        score=lambda left, right: v2._char_iou(_item_span(left), _item_span(right)),
        minimum=minimum_iou,
    )


def _exact_span_pairs(
    gold: Sequence[Mapping[str, Any]], predicted: Sequence[Mapping[str, Any]]
) -> list[tuple[int, int]]:
    return _maximum_weight_pairs(
        gold,
        predicted,
        score=lambda left, right: float(
            v2._span_key(_item_span(left)) == v2._span_key(_item_span(right))
        ),
        minimum=1.0,
    )[0]


def _safe_pairs(
    gold: Sequence[Mapping[str, Any]],
    predicted: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> list[tuple[int, int]]:
    return _maximum_weight_pairs(
        gold,
        predicted,
        score=lambda left, right: float(
            v2.normalize_span_text(str(left["text"]), profile="safe", contract=contract)
            == v2.normalize_span_text(str(right["text"]), profile="safe", contract=contract)
        ),
        minimum=1.0,
    )[0]


def _token_pairs(
    gold: Sequence[Mapping[str, Any]], predicted: Sequence[Mapping[str, Any]]
) -> tuple[list[tuple[int, int]], dict[tuple[int, int], float]]:
    pairs, _, _, observed = _maximum_weight_pairs(
        gold,
        predicted,
        score=v2._token_iou,
        minimum=1e-15,
    )
    return pairs, observed


def _pair_score_sum(
    pairs: Sequence[tuple[int, int]],
    scores: Mapping[tuple[int, int], float],
) -> float:
    return sum(scores[pair] for pair in pairs)


def _map_edges_for_sample(
    gold_record: Mapping[str, Any],
    pred_record: Mapping[str, Any] | None,
    clause_pairs: Sequence[tuple[int, int]],
    extra_pred: Sequence[int],
) -> tuple[set[tuple[Any, ...]], set[tuple[Any, ...]], set[tuple[Any, ...]], set[tuple[Any, ...]]]:
    gold_actor_action: set[tuple[Any, ...]] = set()
    pred_actor_action: set[tuple[Any, ...]] = set()
    gold_order: set[tuple[Any, ...]] = set()
    pred_order: set[tuple[Any, ...]] = set()
    gold_clauses = gold_record["clauses"]
    pred_clauses = pred_record["clauses"] if pred_record else []
    for clause in gold_clauses:
        key = (gold_record["sample_id"], clause["clause_id"])
        gold_actor_action.update(
            (key, edge["actor_id"], edge["action_id"])
            for edge in clause["actor_action_map"]
        )
        gold_order.update(
            (key, edge["before_action_id"], edge["after_action_id"])
            for edge in clause["order_relations"]
        )
    for gold_index, pred_index in clause_pairs:
        gold_clause = gold_clauses[gold_index]
        pred_clause = pred_clauses[pred_index]
        key = (gold_record["sample_id"], gold_clause["clause_id"])
        actor_pairs = _exact_span_pairs(gold_clause["actors"], pred_clause["actors"])
        action_pairs = _exact_span_pairs(gold_clause["actions"], pred_clause["actions"])
        actor_map = {
            pred_clause["actors"][pred_item]["id"]: gold_clause["actors"][gold_item]["id"]
            for gold_item, pred_item in actor_pairs
        }
        action_map = {
            pred_clause["actions"][pred_item]["id"]: gold_clause["actions"][gold_item]["id"]
            for gold_item, pred_item in action_pairs
        }
        for edge_index, edge in enumerate(pred_clause["actor_action_map"]):
            mapped_actor = actor_map.get(edge["actor_id"]) if edge["actor_id"] is not None else None
            mapped_action = action_map.get(edge["action_id"])
            if (edge["actor_id"] is not None and mapped_actor is None) or mapped_action is None:
                pred_actor_action.add(("unaligned", gold_record["sample_id"], pred_index, edge_index))
            else:
                pred_actor_action.add((key, mapped_actor, mapped_action))
        for edge_index, edge in enumerate(pred_clause["order_relations"]):
            before = action_map.get(edge["before_action_id"])
            after = action_map.get(edge["after_action_id"])
            if before is None or after is None:
                pred_order.add(("unaligned", gold_record["sample_id"], pred_index, edge_index))
            else:
                pred_order.add((key, before, after))
    for pred_index in extra_pred:
        for edge_index, _ in enumerate(pred_clauses[pred_index]["actor_action_map"]):
            pred_actor_action.add(("extra_clause", gold_record["sample_id"], pred_index, edge_index))
        for edge_index, _ in enumerate(pred_clauses[pred_index]["order_relations"]):
            pred_order.add(("extra_clause", gold_record["sample_id"], pred_index, edge_index))
    return gold_actor_action, pred_actor_action, gold_order, pred_order


def evaluate_stage2(
    gold_records: Sequence[Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    *,
    contract: Mapping[str, Any],
    dataset_id: str,
    method_id: str,
    expected_membership_sha256: str,
    claim_scope: str = "synthetic_contract",
    formal_ready: bool = False,
) -> dict[str, Any]:
    if contract.get("schema_version") != CONTRACT_VERSION:
        raise Stage2EvaluationError("unrecognized v3 evaluator contract")
    if claim_scope not in contract.get("safety", {}).get("allowed_claim_scopes", []):
        raise Stage2EvaluationError(f"claim scope is not allowed: {claim_scope}")
    if claim_scope == "formal" and not formal_ready:
        raise Stage2EvaluationError("formal evaluation requires the external final-readiness gate")
    if method_id not in contract.get("methods", []):
        raise Stage2EvaluationError(f"unknown method_id: {method_id}")
    gold_by_id = v2._validate_gold(gold_records)
    actual_membership_sha = membership_sha256(list(gold_by_id.values()))
    if actual_membership_sha != expected_membership_sha256:
        raise Stage2EvaluationError("Gold membership SHA-256 mismatch")
    attempts_by_id, runtime_errors, cost = v2._validate_attempts(
        attempts, gold_by_id, method_id=method_id
    )

    field_counts = {
        field: {"gold": 0.0, "predicted": 0.0, "strict_tp": 0.0, "safe_tp": 0.0, "token_tp": 0.0}
        for field in TEXT_FIELDS
    }
    macro_token_samples: dict[str, list[dict[str, float]]] = {field: [] for field in TEXT_FIELDS}
    modality_counts = {
        label: {"tp": 0.0, "fp": 0.0, "fn": 0.0, "support": 0.0, "missing": 0.0, "extra": 0.0}
        for label in VALID_MODALITIES
    }
    confusion = {label: Counter() for label in VALID_MODALITIES}
    coverage_required = coverage_predicted = coverage_matched_presence = complete_records = 0
    valid_records = unsupported_records = 0
    segmentation_exact = total_gold_clauses = total_pred_clauses = aligned_clause_count = 0
    clause_iou_sum = 0.0
    all_gold_actor_action: set[tuple[Any, ...]] = set()
    all_pred_actor_action: set[tuple[Any, ...]] = set()
    all_gold_order: set[tuple[Any, ...]] = set()
    all_pred_order: set[tuple[Any, ...]] = set()

    for sample_id in sorted(gold_by_id):
        gold = gold_by_id[sample_id]
        attempt = attempts_by_id[sample_id]
        pred = attempt["record_for_scoring"]
        if pred is not None:
            valid_records += 1
            unsupported_records += bool(pred.get("unsupported_or_ambiguous"))
        gold_clauses = gold["clauses"]
        pred_clauses = pred["clauses"] if pred else []
        clause_pairs, missing_gold, extra_pred, clause_scores = clause_iou_pairs(
            gold_clauses,
            pred_clauses,
            minimum_iou=float(contract["alignment"]["clause_minimum_iou"]),
        )
        exact_pairs = _exact_span_pairs(gold_clauses, pred_clauses)
        segmentation_exact += len(exact_pairs)
        aligned_clause_count += len(clause_pairs)
        clause_iou_sum += _pair_score_sum(clause_pairs, clause_scores)
        total_gold_clauses += len(gold_clauses)
        total_pred_clauses += len(pred_clauses)
        pair_by_gold = dict(clause_pairs)
        sample_required = len(gold_clauses)
        sample_predicted = len(pred_clauses)
        sample_presence = len(clause_pairs)
        per_sample_token = {
            field: {"gold": 0.0, "predicted": 0.0, "tp": 0.0}
            for field in TEXT_FIELDS
        }

        for gold_index, gold_clause in enumerate(gold_clauses):
            gold_label = gold_clause["modality"]["label"]
            modality_counts[gold_label]["support"] += 1
            pred_index = pair_by_gold.get(gold_index)
            pred_clause = pred_clauses[pred_index] if pred_index is not None else None
            if pred_clause is None:
                modality_counts[gold_label]["fn"] += 1
                modality_counts[gold_label]["missing"] += 1
            else:
                pred_label = pred_clause["modality"]["label"]
                confusion[gold_label][pred_label] += 1
                if pred_label == gold_label:
                    modality_counts[gold_label]["tp"] += 1
                else:
                    modality_counts[gold_label]["fn"] += 1
                    modality_counts[pred_label]["fp"] += 1
            for field in TEXT_FIELDS:
                gold_items = gold_clause[field]
                pred_items = pred_clause[field] if pred_clause is not None else []
                strict_pairs = _exact_span_pairs(gold_items, pred_items)
                safe_pairs = _safe_pairs(gold_items, pred_items, contract)
                token_pairs, token_scores = _token_pairs(gold_items, pred_items)
                token_tp = _pair_score_sum(token_pairs, token_scores)
                field_counts[field]["gold"] += len(gold_items)
                field_counts[field]["predicted"] += len(pred_items)
                field_counts[field]["strict_tp"] += len(strict_pairs)
                field_counts[field]["safe_tp"] += len(safe_pairs)
                field_counts[field]["token_tp"] += token_tp
                sample_required += len(gold_items)
                sample_predicted += len(pred_items)
                sample_presence += len(token_pairs)
                per_sample_token[field]["gold"] += len(gold_items)
                per_sample_token[field]["predicted"] += len(pred_items)
                per_sample_token[field]["tp"] += token_tp

        for pred_index in extra_pred:
            pred_clause = pred_clauses[pred_index]
            pred_label = pred_clause["modality"]["label"]
            modality_counts[pred_label]["fp"] += 1
            modality_counts[pred_label]["extra"] += 1
            for field in TEXT_FIELDS:
                count = len(pred_clause[field])
                field_counts[field]["predicted"] += count
                sample_predicted += count
                per_sample_token[field]["predicted"] += count
        del missing_gold
        coverage_required += sample_required
        coverage_predicted += sample_predicted
        coverage_matched_presence += sample_presence
        complete_records += int(sample_presence == sample_required)
        for field, values in per_sample_token.items():
            if values["gold"] or values["predicted"]:
                macro_token_samples[field].append(
                    v2._prf(values["tp"], values["predicted"] - values["tp"], values["gold"] - values["tp"])
                )
        gaa, paa, go, po = _map_edges_for_sample(gold, pred, clause_pairs, extra_pred)
        all_gold_actor_action.update(gaa)
        all_pred_actor_action.update(paa)
        all_gold_order.update(go)
        all_pred_order.update(po)

    per_field: dict[str, Any] = {}
    for field, values in field_counts.items():
        gold_count = values["gold"]
        pred_count = values["predicted"]
        strict = v2._prf(values["strict_tp"], pred_count - values["strict_tp"], gold_count - values["strict_tp"])
        safe = v2._prf(values["safe_tp"], pred_count - values["safe_tp"], gold_count - values["safe_tp"])
        token_micro = v2._prf(values["token_tp"], pred_count - values["token_tp"], gold_count - values["token_tp"])
        samples = macro_token_samples[field]
        token_macro = {
            "precision": sum((item["precision"] or 0.0) for item in samples) / len(samples) if samples else 0.0,
            "recall": sum(item["recall"] for item in samples) / len(samples) if samples else 0.0,
            "f1": sum(item["f1"] for item in samples) / len(samples) if samples else 0.0,
            "evaluated_sample_count": len(samples),
        }
        per_field[FIELD_LABELS[field]] = {
            "gold_count": int(gold_count),
            "predicted_count": int(pred_count),
            "strict_exact": strict,
            "safe_normalized": safe,
            "normalized_f1_lift": safe["f1"] - strict["f1"],
            "token_overlap_micro": token_micro,
            "token_overlap_macro": token_macro,
        }

    modality = v2._modality_report(modality_counts, confusion)
    modality["micro"] = v2._prf(
        sum(modality_counts[label]["tp"] for label in VALID_MODALITIES),
        sum(modality_counts[label]["fp"] for label in VALID_MODALITIES),
        sum(modality_counts[label]["fn"] for label in VALID_MODALITIES),
    )
    actor_action = v2._edge_metrics(all_gold_actor_action, all_pred_actor_action)
    order_relation = v2._edge_metrics(all_gold_order, all_pred_order)
    requests = len(gold_by_id)
    api_errors = sum(item["request_status"] == "api_error" for item in attempts_by_id.values())
    recovered_api_errors = sum(
        item.get("recovered_runtime_error_category") is not None
        for item in attempts_by_id.values()
    )
    invalid_records = requests - valid_records - api_errors
    errors = Counter(runtime_errors)
    errors["modality_false_negative"] = int(
        sum(modality_counts[label]["fn"] for label in VALID_MODALITIES)
    )
    for field, metrics in per_field.items():
        errors[f"{field}_strict_false_negative"] = int(round(metrics["strict_exact"]["fn"]))
        errors[f"{field}_strict_false_positive"] = int(round(metrics["strict_exact"]["fp"]))
    errors["actor_action_edge_false_negative"] = int(actor_action["fn"])
    errors["actor_action_edge_false_positive"] = int(actor_action["fp"])
    errors["order_relation_edge_false_negative"] = int(order_relation["fn"])
    errors["order_relation_edge_false_positive"] = int(order_relation["fp"])
    alignment_precision = v2._safe_rate(aligned_clause_count, total_pred_clauses)
    alignment_recall = v2._safe_rate(aligned_clause_count, total_gold_clauses)
    alignment_f1 = v2._prf(
        aligned_clause_count,
        total_pred_clauses - aligned_clause_count,
        total_gold_clauses - aligned_clause_count,
    )["f1"]
    return {
        "schema_version": REPORT_VERSION,
        "task_id": "S2.10-E",
        "dataset_id": dataset_id,
        "method_id": method_id,
        "claim_scope": claim_scope,
        "is_formal_performance_result": claim_scope == "formal",
        "contract": {
            "schema_version": contract["schema_version"],
            "normalization_rule_set_version": contract["normalization"]["rule_set_version"],
            "clause_alignment": contract["alignment"]["clause"],
            "clause_alignment_minimum_iou": contract["alignment"]["clause_minimum_iou"],
            "entity_alignment": contract["alignment"]["entity"],
        },
        "membership": {
            "sample_count": requests,
            "payload_sha256": actual_membership_sha,
            "gold_attempt_ids_exact_match": True,
        },
        "primary_metrics": {"modality": modality, "fields": per_field},
        "semantic_coverage": {
            "gold_required_count": coverage_required,
            "predicted_count": coverage_predicted,
            "matched_presence_count": coverage_matched_presence,
            "gold_required_presence_recall": v2._safe_rate(coverage_matched_presence, coverage_required),
            "predicted_field_precision": v2._safe_rate(coverage_matched_presence, coverage_predicted),
            "hallucinated_field_rate": 1 - v2._safe_rate(coverage_matched_presence, coverage_predicted) if coverage_predicted else 0.0,
            "complete_record_rate": complete_records / requests,
            "schema_valid_rate": valid_records / requests,
            "unsupported_or_ambiguous_rate": unsupported_records / requests,
            "invalid_record_rate": invalid_records / requests,
            "api_error_rate": api_errors / requests,
            "recovered_api_error_rate": recovered_api_errors / requests,
            "any_api_error_rate": (api_errors + recovered_api_errors) / requests,
            "invalid_or_api_error_rate": (invalid_records + api_errors) / requests,
        },
        "structural_encoding": {
            "actor_action_edges": actor_action,
            "order_relation_edges": order_relation,
            "clause_segmentation": {
                "gold_count": total_gold_clauses,
                "predicted_count": total_pred_clauses,
                "exact_match_count": segmentation_exact,
                "exact_precision": v2._safe_rate(segmentation_exact, total_pred_clauses),
                "exact_recall": v2._safe_rate(segmentation_exact, total_gold_clauses),
                "exact_f1": v2._prf(
                    segmentation_exact,
                    total_pred_clauses - segmentation_exact,
                    total_gold_clauses - segmentation_exact,
                )["f1"],
                "aligned_match_count": aligned_clause_count,
                "alignment_precision": alignment_precision,
                "alignment_recall": alignment_recall,
                "alignment_f1": alignment_f1,
                "minimum_iou": contract["alignment"]["clause_minimum_iou"],
                "mean_gold_clause_span_iou": v2._safe_rate(clause_iou_sum, total_gold_clauses),
                "mean_matched_clause_span_iou": v2._safe_rate(clause_iou_sum, aligned_clause_count),
            },
            "schema_valid_rate": valid_records / requests,
        },
        "error_accounting": {
            "categories_are_nonexclusive": True,
            "counts": dict(sorted((key, int(value)) for key, value in errors.items())),
        },
        "cost_accounting": {
            "request_count": int(cost["request_count"]),
            "llm_call_count": int(cost["llm_call_count"]),
            "prompt_tokens": int(cost["prompt_tokens"]),
            "completion_tokens": int(cost["completion_tokens"]),
            "total_tokens": int(cost["total_tokens"]),
            "estimated_cost_usd": cost["estimated_cost_usd"],
            "latency_ms_total": cost["latency_ms"],
            "latency_ms_mean_per_request": cost["latency_ms"] / requests,
        },
        "safety": {
            "gold_modified": False,
            "network_called_by_evaluator": False,
            "llm_called_by_evaluator": False,
            "row_level_predictions_persisted_in_report": False,
            "paper_score_targeting_used": False,
        },
    }


def _is_rate(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def validate_evaluation_report(report: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_root = {
        "schema_version", "task_id", "dataset_id", "method_id", "claim_scope",
        "is_formal_performance_result", "contract", "membership", "primary_metrics",
        "semantic_coverage", "structural_encoding", "error_accounting",
        "cost_accounting", "safety",
    }
    if set(report) != expected_root:
        errors.append("report root keys changed")
    if report.get("schema_version") != REPORT_VERSION or report.get("task_id") != "S2.10-E":
        errors.append("report identity changed")
    scope = report.get("claim_scope")
    if scope not in {"synthetic_contract", "development", "formal"}:
        errors.append("invalid claim_scope")
    if report.get("is_formal_performance_result") is not (scope == "formal"):
        errors.append("formal-result flag disagrees with claim_scope")
    contract = report.get("contract", {})
    if contract != {
        "schema_version": CONTRACT_VERSION,
        "normalization_rule_set_version": "safe-legal-v1",
        "clause_alignment": CLAUSE_ALIGNMENT_NAME,
        "clause_alignment_minimum_iou": CLAUSE_MINIMUM_IOU,
        "entity_alignment": ENTITY_ALIGNMENT_NAME,
    }:
        errors.append("report contract binding changed")
    membership = report.get("membership", {})
    if (
        not isinstance(membership, Mapping)
        or not isinstance(membership.get("sample_count"), int)
        or membership.get("sample_count", 0) < 1
        or re.fullmatch(r"[0-9a-f]{64}", str(membership.get("payload_sha256", ""))) is None
        or membership.get("gold_attempt_ids_exact_match") is not True
    ):
        errors.append("membership is invalid")
    primary = report.get("primary_metrics", {})
    modality = primary.get("modality", {}) if isinstance(primary, Mapping) else {}
    if modality.get("labels") != list(VALID_MODALITIES) or not _is_rate(modality.get("macro_f1")):
        errors.append("modality metrics are invalid")
    modality_micro = modality.get("micro", {}) if isinstance(modality, Mapping) else {}
    if not all(_is_rate(modality_micro.get(key)) for key in ("precision", "recall", "f1")):
        errors.append("modality micro metrics are invalid")
    fields = primary.get("fields", {}) if isinstance(primary, Mapping) else {}
    if not isinstance(fields, Mapping) or set(fields) != set(FIELD_LABELS.values()):
        errors.append("field metric keys changed")
    else:
        for field, metric in fields.items():
            for name in ("strict_exact", "safe_normalized", "token_overlap_micro"):
                part = metric.get(name, {}) if isinstance(metric, Mapping) else {}
                if not all(_is_rate(part.get(key)) for key in ("precision", "recall", "f1")):
                    errors.append(f"invalid {field}.{name}")
            strict_f1 = metric.get("strict_exact", {}).get("f1", math.nan)
            safe_f1 = metric.get("safe_normalized", {}).get("f1", math.nan)
            if safe_f1 + 1e-12 < strict_f1:
                errors.append(f"safe normalization is not a superset for {field}")
    coverage = report.get("semantic_coverage", {})
    for key in (
        "gold_required_presence_recall", "predicted_field_precision", "hallucinated_field_rate",
        "complete_record_rate", "schema_valid_rate", "unsupported_or_ambiguous_rate",
        "invalid_record_rate", "api_error_rate", "recovered_api_error_rate",
        "any_api_error_rate", "invalid_or_api_error_rate",
    ):
        if not isinstance(coverage, Mapping) or not _is_rate(coverage.get(key)):
            errors.append(f"invalid coverage rate: {key}")
    structural = report.get("structural_encoding", {})
    segmentation = structural.get("clause_segmentation", {}) if isinstance(structural, Mapping) else {}
    for key in (
        "exact_precision", "exact_recall", "exact_f1", "alignment_precision",
        "alignment_recall", "alignment_f1", "minimum_iou",
        "mean_gold_clause_span_iou", "mean_matched_clause_span_iou",
    ):
        if not _is_rate(segmentation.get(key)):
            errors.append(f"invalid segmentation rate: {key}")
    if segmentation.get("minimum_iou") != CLAUSE_MINIMUM_IOU:
        errors.append("segmentation threshold changed")
    safety = report.get("safety", {})
    if safety != {
        "gold_modified": False,
        "network_called_by_evaluator": False,
        "llm_called_by_evaluator": False,
        "row_level_predictions_persisted_in_report": False,
        "paper_score_targeting_used": False,
    }:
        errors.append("report safety boundary changed")
    cost = report.get("cost_accounting", {})
    if cost.get("request_count") != membership.get("sample_count"):
        errors.append("request count differs from membership")
    if cost.get("total_tokens") != cost.get("prompt_tokens", 0) + cost.get("completion_tokens", 0):
        errors.append("token totals disagree")
    return errors
