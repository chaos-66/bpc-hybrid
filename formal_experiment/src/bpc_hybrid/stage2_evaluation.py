"""Frozen S2.10 Stage 2 evaluator.

This module evaluates method-agnostic canonical Stage 2 records.  It is
deliberately separate from :mod:`bpc_hybrid.evaluator`, which is a retired
position-aligned prototype.  The contract implemented here is fail-closed:

* Gold and prediction attempts must have exactly the same ``sample_id`` set.
* Gold records must pass the canonical JSON-schema and cross-field validator.
* Terminal API errors remain in the denominator; recovered provider errors can
  retain a scorable fallback record while remaining visible in error rates.
  Invalid predictions are not scored as if their payload were usable.
* clauses and entities use one frozen hybrid alignment rule: exact id first,
  then exact raw span for still-unmatched items.
* strict, safe-normalized, token-overlap, modality, coverage, structural,
  error, and cost metrics are reported separately.

The evaluator performs no network or model calls and never mutates its inputs.
Synthetic contract verification is not a formal performance evaluation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from bpc_hybrid.stage2_canonical import VALID_MODALITIES, validate_canonical


CONTRACT_VERSION = "stage2_evaluator_contract@1.1.0"
REPORT_VERSION = "stage2_evaluation_report@1.1.0"
STYLE_REVIEW_VERSION = "style_equivalent_review@1.0.0"
TEXT_FIELDS = ("actors", "actions", "conditions", "constraints", "exceptions")
FIELD_LABELS = {
    "actors": "actor",
    "actions": "action",
    "conditions": "condition",
    "constraints": "constraint",
    "exceptions": "exception",
}
ATTEMPT_STATUSES = ("ok", "api_error")
STYLE_DECISIONS = (
    "full_alignment",
    "style_equivalent_alignment",
    "partial_misalignment",
)
_TRAILING_PUNCTUATION = re.compile(r"[\s\.,;:!?\u2018\u2019\u201c\u201d'\"]+$")
_WHITESPACE = re.compile(r"\s+")


class Stage2EvaluationError(ValueError):
    """Raised when S2.10 inputs or its frozen contract fail closed."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_evaluator_contract(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage2EvaluationError(f"invalid evaluator contract: {path}") from exc
    if not isinstance(value, dict):
        raise Stage2EvaluationError("evaluator contract root must be an object")
    if value.get("schema_version") != CONTRACT_VERSION:
        raise Stage2EvaluationError("evaluator contract version changed")
    if value.get("task_id") != "S2.10-E":
        raise Stage2EvaluationError("evaluator task identity changed")
    if value.get("alignment", {}).get("clause") != "hybrid_exact_id_then_exact_raw_span":
        raise Stage2EvaluationError("clause alignment must remain hybrid id then span")
    if value.get("alignment", {}).get("entity") != "hybrid_exact_id_then_exact_raw_span":
        raise Stage2EvaluationError("entity alignment must remain hybrid id then span")
    profiles = value.get("normalization", {}).get("profiles", {})
    if profiles.get("strict") != []:
        raise Stage2EvaluationError("strict normalization profile must be empty")
    expected_safe = ["unicode_nfc", "lowercase", "whitespace_collapse", "trailing_punctuation_strip"]
    if profiles.get("safe") != expected_safe:
        raise Stage2EvaluationError("safe normalization profile changed")
    if value.get("normalization", {}).get("rule_set_version") != "safe-legal-v1":
        raise Stage2EvaluationError("normalization rule-set version changed")
    recovered = value.get("attempt_envelope", {}).get("recovered_api_error_category", {})
    if (
        recovered.get("key") != "recovered_runtime_error_category"
        or recovered.get("nullable") is not True
        or recovered.get("terminal_api_error_rate_excludes_recovered_fallbacks") is not True
    ):
        raise Stage2EvaluationError("recovered API-error fallback contract changed")
    return value


def normalize_span_text(text: str, *, profile: str, contract: Mapping[str, Any]) -> str:
    """Apply the explicit strict or safe normalization profile."""
    profiles = contract.get("normalization", {}).get("profiles", {})
    rules = profiles.get(profile)
    if not isinstance(rules, list):
        raise Stage2EvaluationError(f"unknown normalization profile: {profile}")
    result = text
    for rule in rules:
        if rule == "unicode_nfc":
            result = unicodedata.normalize("NFC", result)
        elif rule == "lowercase":
            result = result.lower()
        elif rule == "whitespace_collapse":
            result = _WHITESPACE.sub(" ", result).strip()
        elif rule == "trailing_punctuation_strip":
            result = _TRAILING_PUNCTUATION.sub("", result)
        else:
            raise Stage2EvaluationError(f"unsupported normalization rule: {rule}")
    return result


def _span_key(span: Mapping[str, Any]) -> tuple[int, int, str]:
    return (int(span["start"]), int(span["end"]), str(span["text"]))


def _char_iou(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    start = max(int(left["start"]), int(right["start"]))
    end = min(int(left["end"]), int(right["end"]))
    intersection = max(0, end - start)
    union = max(int(left["end"]), int(right["end"])) - min(
        int(left["start"]), int(right["start"])
    )
    return intersection / union if union else 0.0


def _tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFC", text).lower()
    return set(re.findall(r"\w+", normalized, flags=re.UNICODE))


def _token_iou(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    a = _tokens(str(left["text"]))
    b = _tokens(str(right["text"]))
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _hybrid_pairs(
    gold: Sequence[Mapping[str, Any]],
    predicted: Sequence[Mapping[str, Any]],
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Pair by exact id, then exact raw span; never by array position."""
    pairs: list[tuple[int, int]] = []
    gold_left = set(range(len(gold)))
    pred_left = set(range(len(predicted)))

    pred_by_id: dict[str, list[int]] = {}
    for pi, item in enumerate(predicted):
        item_id = item.get("id") or item.get("clause_id")
        if isinstance(item_id, str):
            pred_by_id.setdefault(item_id, []).append(pi)
    for gi, item in enumerate(gold):
        item_id = item.get("id") or item.get("clause_id")
        candidates = pred_by_id.get(item_id, []) if isinstance(item_id, str) else []
        pi = next((candidate for candidate in candidates if candidate in pred_left), None)
        if pi is not None:
            pairs.append((gi, pi))
            gold_left.remove(gi)
            pred_left.remove(pi)

    for gi in sorted(gold_left):
        gspan = gold[gi].get("clause_span", gold[gi])
        match = next(
            (
                pi
                for pi in sorted(pred_left)
                if _span_key(predicted[pi].get("clause_span", predicted[pi]))
                == _span_key(gspan)
            ),
            None,
        )
        if match is not None:
            pairs.append((gi, match))
            pred_left.remove(match)
            gold_left.remove(gi)
    pairs.sort()
    return pairs, sorted(gold_left), sorted(pred_left)


def _pair_quality(
    gold: Sequence[Mapping[str, Any]],
    predicted: Sequence[Mapping[str, Any]],
    pairs: Sequence[tuple[int, int]],
    comparator: Callable[[Mapping[str, Any], Mapping[str, Any]], float],
) -> float:
    return sum(comparator(gold[gi], predicted[pi]) for gi, pi in pairs)


def _greedy_token_pairs(
    gold: Sequence[Mapping[str, Any]],
    predicted: Sequence[Mapping[str, Any]],
) -> list[tuple[int, int]]:
    """Id-first, then deterministic maximum-IoU pairing for soft token scores."""
    pairs, gold_left, pred_left = _hybrid_pairs(gold, predicted)
    # Hybrid exact-span fallback is already consumed.  Remaining positive-overlap
    # pairs are only for the token sensitivity metric, never for structural identity.
    candidates: list[tuple[float, int, int]] = []
    for gi in gold_left:
        for pi in pred_left:
            score = _token_iou(gold[gi], predicted[pi])
            if score > 0:
                candidates.append((-score, gi, pi))
    used_g = {gi for gi, _ in pairs}
    used_p = {pi for _, pi in pairs}
    for negative_score, gi, pi in sorted(candidates):
        del negative_score
        if gi not in used_g and pi not in used_p:
            pairs.append((gi, pi))
            used_g.add(gi)
            used_p.add(pi)
    return sorted(pairs)


def _prf(tp: float, fp: float, fn: float, *, na_precision: bool = False) -> dict[str, Any]:
    p_den = tp + fp
    r_den = tp + fn
    precision: float | None = tp / p_den if p_den else (None if na_precision else 0.0)
    recall = tp / r_den if r_den else 0.0
    numeric_precision = precision or 0.0
    f1 = (
        2 * numeric_precision * recall / (numeric_precision + recall)
        if numeric_precision + recall
        else 0.0
    )
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _safe_rate(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def membership_payload(gold_records: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    payload = [
        {
            "sample_id": str(record["sample_id"]),
            "source_id": str(record["source_id"]),
            "source_text_sha256": hashlib.sha256(
                str(record["source_text"]).encode("utf-8")
            ).hexdigest(),
        }
        for record in gold_records
    ]
    return sorted(payload, key=lambda item: item["sample_id"])


def membership_sha256(gold_records: Sequence[Mapping[str, Any]]) -> str:
    return sha256_json(membership_payload(gold_records))


def _validate_gold(gold_records: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    if not gold_records:
        raise Stage2EvaluationError("gold batch must not be empty")
    result: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(gold_records):
        if not isinstance(raw, Mapping):
            raise Stage2EvaluationError(f"gold[{index}] must be an object")
        record = copy.deepcopy(dict(raw))
        sample_id = record.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id:
            raise Stage2EvaluationError(f"gold[{index}] has no sample_id")
        if sample_id in result:
            raise Stage2EvaluationError(f"duplicate gold sample_id: {sample_id}")
        report = validate_canonical(record)
        if not report.schema_valid or not report.cross_field_valid:
            raise Stage2EvaluationError(
                f"gold {sample_id} is not canonical: {'; '.join(report.errors)}"
            )
        result[sample_id] = record
    return result


def _runtime_number(runtime: Mapping[str, Any], key: str) -> float:
    value = runtime.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Stage2EvaluationError(f"runtime.{key} must be numeric")
    if not math.isfinite(float(value)) or value < 0:
        raise Stage2EvaluationError(f"runtime.{key} must be finite and non-negative")
    return float(value)


def _validate_attempts(
    attempts: Sequence[Mapping[str, Any]],
    gold_by_id: Mapping[str, Mapping[str, Any]],
    *,
    method_id: str,
) -> tuple[dict[str, dict[str, Any]], Counter[str], dict[str, float]]:
    by_id: dict[str, dict[str, Any]] = {}
    errors: Counter[str] = Counter()
    cost = {
        "request_count": 0.0,
        "llm_call_count": 0.0,
        "prompt_tokens": 0.0,
        "completion_tokens": 0.0,
        "total_tokens": 0.0,
        "estimated_cost_usd": 0.0,
        "latency_ms": 0.0,
    }
    for index, raw in enumerate(attempts):
        if not isinstance(raw, Mapping):
            raise Stage2EvaluationError(f"attempts[{index}] must be an object")
        attempt = copy.deepcopy(dict(raw))
        sample_id = attempt.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id:
            raise Stage2EvaluationError(f"attempts[{index}] has no sample_id")
        if sample_id in by_id:
            raise Stage2EvaluationError(f"duplicate attempt sample_id: {sample_id}")
        status = attempt.get("request_status")
        if status not in ATTEMPT_STATUSES:
            raise Stage2EvaluationError(f"attempt {sample_id} has invalid request_status")
        runtime = attempt.get("runtime")
        if not isinstance(runtime, Mapping):
            raise Stage2EvaluationError(f"attempt {sample_id} has no runtime object")
        if runtime.get("llm_call_performed") not in (True, False):
            raise Stage2EvaluationError(
                f"attempt {sample_id} runtime.llm_call_performed must be boolean"
            )
        prompt = _runtime_number(runtime, "prompt_tokens")
        completion = _runtime_number(runtime, "completion_tokens")
        declared_total = _runtime_number(runtime, "total_tokens")
        if declared_total != prompt + completion:
            raise Stage2EvaluationError(f"attempt {sample_id} token totals disagree")
        cost["request_count"] += 1
        cost["llm_call_count"] += int(runtime["llm_call_performed"])
        cost["prompt_tokens"] += prompt
        cost["completion_tokens"] += completion
        cost["total_tokens"] += declared_total
        cost["estimated_cost_usd"] += _runtime_number(runtime, "estimated_cost_usd")
        cost["latency_ms"] += _runtime_number(runtime, "latency_ms")

        attempt["canonical_valid"] = False
        attempt["record_for_scoring"] = None
        recovered_category = attempt.get("recovered_runtime_error_category")
        if recovered_category is not None:
            if (
                status != "ok"
                or runtime.get("llm_call_performed") is not True
                or not isinstance(recovered_category, str)
                or not recovered_category.strip()
                or attempt.get("error_category") is not None
            ):
                raise Stage2EvaluationError(
                    f"attempt {sample_id} has an invalid recovered runtime error"
                )
            recovered_category = recovered_category.strip()
            attempt["recovered_runtime_error_category"] = recovered_category
            errors[f"recovered_api_error:{recovered_category}"] += 1
        if status == "api_error":
            if attempt.get("record") is not None:
                raise Stage2EvaluationError(f"API-error attempt {sample_id} must have record=null")
            category = attempt.get("error_category")
            if not isinstance(category, str) or not category:
                raise Stage2EvaluationError(f"API-error attempt {sample_id} needs error_category")
            errors[f"api_error:{category}"] += 1
        else:
            record = attempt.get("record")
            if not isinstance(record, Mapping):
                raise Stage2EvaluationError(f"ok attempt {sample_id} must contain record")
            record_copy = copy.deepcopy(dict(record))
            if record_copy.get("sample_id") != sample_id:
                raise Stage2EvaluationError(f"attempt/record sample_id mismatch: {sample_id}")
            validation = validate_canonical(record_copy)
            if not validation.schema_valid:
                errors["schema_invalid"] += 1
            elif not validation.cross_field_valid:
                errors["cross_field_invalid"] += 1
            else:
                gold = gold_by_id.get(sample_id)
                if gold is None:
                    raise Stage2EvaluationError(f"attempt sample_id not in gold: {sample_id}")
                if record_copy.get("source_id") != gold.get("source_id"):
                    raise Stage2EvaluationError(f"source_id mismatch for {sample_id}")
                if record_copy.get("source_text") != gold.get("source_text"):
                    raise Stage2EvaluationError(f"source_text mismatch for {sample_id}")
                if record_copy.get("method", {}).get("name") != method_id:
                    raise Stage2EvaluationError(f"method mismatch for {sample_id}")
                attempt["canonical_valid"] = True
                attempt["record_for_scoring"] = record_copy
        if recovered_category is not None and not attempt["canonical_valid"]:
            raise Stage2EvaluationError(
                f"attempt {sample_id} recovered runtime error requires a canonical-valid fallback record"
            )
        by_id[sample_id] = attempt

    if set(by_id) != set(gold_by_id):
        missing = sorted(set(gold_by_id) - set(by_id))
        extra = sorted(set(by_id) - set(gold_by_id))
        raise Stage2EvaluationError(
            f"attempt membership mismatch; missing={missing}, extra={extra}"
        )
    return by_id, errors, cost


def _modality_report(counts: Mapping[str, Mapping[str, float]], confusion: Mapping[str, Counter[str]]) -> dict[str, Any]:
    per_class: dict[str, Any] = {}
    for label in VALID_MODALITIES:
        values = counts[label]
        metric = _prf(values["tp"], values["fp"], values["fn"], na_precision=True)
        metric["support"] = int(values["support"])
        metric["precision_display"] = "N/A" if metric["precision"] is None else metric["precision"]
        per_class[label] = metric
    return {
        "unit": "clause",
        "labels": list(VALID_MODALITIES),
        "macro_f1": sum(per_class[label]["f1"] for label in VALID_MODALITIES) / 4,
        "per_class": per_class,
        "confusion_matrix": {
            gold: {pred: int(confusion[gold][pred]) for pred in VALID_MODALITIES}
            for gold in VALID_MODALITIES
        },
        "missing_prediction_by_gold_class": {
            label: int(counts[label]["missing"]) for label in VALID_MODALITIES
        },
        "extra_prediction_by_class": {
            label: int(counts[label]["extra"]) for label in VALID_MODALITIES
        },
    }


def _edge_metrics(gold_edges: set[tuple[Any, ...]], pred_edges: set[tuple[Any, ...]]) -> dict[str, Any]:
    tp = len(gold_edges & pred_edges)
    fp = len(pred_edges - gold_edges)
    fn = len(gold_edges - pred_edges)
    result = _prf(tp, fp, fn)
    union = len(gold_edges | pred_edges)
    result["jaccard_iou"] = tp / union if union else 1.0
    result["gold_count"] = len(gold_edges)
    result["predicted_count"] = len(pred_edges)
    return result


def _map_edges_for_sample(
    gold_record: Mapping[str, Any],
    pred_record: Mapping[str, Any] | None,
) -> tuple[set[tuple[Any, ...]], set[tuple[Any, ...]], set[tuple[Any, ...]], set[tuple[Any, ...]]]:
    gold_actor_action: set[tuple[Any, ...]] = set()
    pred_actor_action: set[tuple[Any, ...]] = set()
    gold_order: set[tuple[Any, ...]] = set()
    pred_order: set[tuple[Any, ...]] = set()
    gold_clauses = gold_record["clauses"]
    pred_clauses = pred_record["clauses"] if pred_record else []
    clause_pairs, _, extra_pred = _hybrid_pairs(gold_clauses, pred_clauses)

    for gi, gc in enumerate(gold_clauses):
        clause_key = (gold_record["sample_id"], gc["clause_id"])
        for edge in gc["actor_action_map"]:
            gold_actor_action.add((clause_key, edge["actor_id"], edge["action_id"]))
        for edge in gc["order_relations"]:
            gold_order.add((clause_key, edge["before_action_id"], edge["after_action_id"]))

    for gi, pi in clause_pairs:
        gc = gold_clauses[gi]
        pc = pred_clauses[pi]
        clause_key = (gold_record["sample_id"], gc["clause_id"])
        actor_pairs, _, _ = _hybrid_pairs(gc["actors"], pc["actors"])
        action_pairs, _, _ = _hybrid_pairs(gc["actions"], pc["actions"])
        actor_map = {pc["actors"][pi2]["id"]: gc["actors"][gi2]["id"] for gi2, pi2 in actor_pairs}
        action_map = {pc["actions"][pi2]["id"]: gc["actions"][gi2]["id"] for gi2, pi2 in action_pairs}
        for ei, edge in enumerate(pc["actor_action_map"]):
            actor_id = edge["actor_id"]
            mapped_actor: Any = None if actor_id is None else actor_map.get(actor_id)
            mapped_action = action_map.get(edge["action_id"])
            if (actor_id is not None and mapped_actor is None) or mapped_action is None:
                pred_actor_action.add(("unaligned", gold_record["sample_id"], pi, ei))
            else:
                pred_actor_action.add((clause_key, mapped_actor, mapped_action))
        for ei, edge in enumerate(pc["order_relations"]):
            before = action_map.get(edge["before_action_id"])
            after = action_map.get(edge["after_action_id"])
            if before is None or after is None:
                pred_order.add(("unaligned", gold_record["sample_id"], pi, ei))
            else:
                pred_order.add((clause_key, before, after))

    for pi in extra_pred:
        pc = pred_clauses[pi]
        for ei, _ in enumerate(pc["actor_action_map"]):
            pred_actor_action.add(("extra_clause", gold_record["sample_id"], pi, ei))
        for ei, _ in enumerate(pc["order_relations"]):
            pred_order.add(("extra_clause", gold_record["sample_id"], pi, ei))
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
    """Evaluate one exact-membership prediction batch against canonical Gold."""
    if contract.get("schema_version") != CONTRACT_VERSION:
        raise Stage2EvaluationError("unrecognized evaluator contract")
    allowed_scopes = contract.get("safety", {}).get("allowed_claim_scopes", [])
    if claim_scope not in allowed_scopes:
        raise Stage2EvaluationError(f"claim scope is not allowed: {claim_scope}")
    if claim_scope == "formal" and not formal_ready:
        raise Stage2EvaluationError("formal evaluation requires the external final-readiness gate")
    if not isinstance(dataset_id, str) or not dataset_id:
        raise Stage2EvaluationError("dataset_id must be non-empty")
    if method_id not in contract.get("methods", []):
        raise Stage2EvaluationError(f"unknown method_id: {method_id}")

    gold_by_id = _validate_gold(gold_records)
    actual_membership_sha = membership_sha256(list(gold_by_id.values()))
    if actual_membership_sha != expected_membership_sha256:
        raise Stage2EvaluationError("Gold membership SHA-256 mismatch")
    attempts_by_id, runtime_errors, cost = _validate_attempts(
        attempts, gold_by_id, method_id=method_id
    )

    field_counts: dict[str, dict[str, float]] = {
        field: {
            "gold": 0,
            "predicted": 0,
            "strict_tp": 0.0,
            "safe_tp": 0.0,
            "token_tp": 0.0,
        }
        for field in TEXT_FIELDS
    }
    macro_token_samples: dict[str, list[dict[str, float]]] = {field: [] for field in TEXT_FIELDS}
    modality_counts = {
        label: {"tp": 0.0, "fp": 0.0, "fn": 0.0, "support": 0.0, "missing": 0.0, "extra": 0.0}
        for label in VALID_MODALITIES
    }
    confusion = {label: Counter() for label in VALID_MODALITIES}
    coverage_required = 0
    coverage_predicted = 0
    coverage_matched_presence = 0
    complete_records = 0
    valid_records = 0
    unsupported_records = 0
    segmentation_exact = 0
    total_gold_clauses = 0
    total_pred_clauses = 0
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
        pairs, missing_gold_clauses, extra_pred_clauses = _hybrid_pairs(gold_clauses, pred_clauses)
        total_gold_clauses += len(gold_clauses)
        total_pred_clauses += len(pred_clauses)
        pair_by_gold = {gi: pi for gi, pi in pairs}
        segmentation_exact += sum(
            _span_key(gold_clauses[gi]["clause_span"])
            == _span_key(pred_clauses[pi]["clause_span"])
            for gi, pi in pairs
        )
        clause_iou_sum += sum(
            _char_iou(gold_clauses[gi]["clause_span"], pred_clauses[pi]["clause_span"])
            for gi, pi in pairs
        )

        sample_required = len(gold_clauses)
        sample_predicted = len(pred_clauses)
        sample_presence = len(pairs)
        per_sample_token = {
            field: {"gold": 0.0, "predicted": 0.0, "tp": 0.0}
            for field in TEXT_FIELDS
        }

        for gi, gc in enumerate(gold_clauses):
            gold_label = gc["modality"]["label"]
            modality_counts[gold_label]["support"] += 1
            pi = pair_by_gold.get(gi)
            if pi is None:
                modality_counts[gold_label]["fn"] += 1
                modality_counts[gold_label]["missing"] += 1
                pc = None
            else:
                pc = pred_clauses[pi]
                pred_label = pc["modality"]["label"]
                confusion[gold_label][pred_label] += 1
                if pred_label == gold_label:
                    modality_counts[gold_label]["tp"] += 1
                else:
                    modality_counts[gold_label]["fn"] += 1
                    modality_counts[pred_label]["fp"] += 1

            for field in TEXT_FIELDS:
                gold_items = gc[field]
                pred_items = pc[field] if pc is not None else []
                identity_pairs, _, _ = _hybrid_pairs(gold_items, pred_items)
                strict_tp = _pair_quality(
                    gold_items,
                    pred_items,
                    identity_pairs,
                    lambda left, right: float(_span_key(left) == _span_key(right)),
                )
                safe_tp = _pair_quality(
                    gold_items,
                    pred_items,
                    identity_pairs,
                    lambda left, right: float(
                        normalize_span_text(str(left["text"]), profile="safe", contract=contract)
                        == normalize_span_text(str(right["text"]), profile="safe", contract=contract)
                    ),
                )
                token_pairs = _greedy_token_pairs(gold_items, pred_items)
                token_tp = _pair_quality(gold_items, pred_items, token_pairs, _token_iou)
                field_counts[field]["gold"] += len(gold_items)
                field_counts[field]["predicted"] += len(pred_items)
                field_counts[field]["strict_tp"] += strict_tp
                field_counts[field]["safe_tp"] += safe_tp
                field_counts[field]["token_tp"] += token_tp
                sample_required += len(gold_items)
                sample_predicted += len(pred_items)
                sample_presence += len(identity_pairs)
                per_sample_token[field]["gold"] += len(gold_items)
                per_sample_token[field]["predicted"] += len(pred_items)
                per_sample_token[field]["tp"] += token_tp

        for pi in extra_pred_clauses:
            pc = pred_clauses[pi]
            pred_label = pc["modality"]["label"]
            modality_counts[pred_label]["fp"] += 1
            modality_counts[pred_label]["extra"] += 1
            for field in TEXT_FIELDS:
                count = len(pc[field])
                field_counts[field]["predicted"] += count
                sample_predicted += count
                per_sample_token[field]["predicted"] += count

        del missing_gold_clauses
        coverage_required += sample_required
        coverage_predicted += sample_predicted
        coverage_matched_presence += sample_presence
        complete_records += int(sample_presence == sample_required)
        for field in TEXT_FIELDS:
            values = per_sample_token[field]
            if values["gold"] or values["predicted"]:
                tp = values["tp"]
                macro_token_samples[field].append(
                    _prf(tp, values["predicted"] - tp, values["gold"] - tp)
                )

        gaa, paa, go, po = _map_edges_for_sample(gold, pred)
        all_gold_actor_action.update(gaa)
        all_pred_actor_action.update(paa)
        all_gold_order.update(go)
        all_pred_order.update(po)

    for label in VALID_MODALITIES:
        # Extra predictions and wrong-label predictions are already FPs.
        pass

    per_field: dict[str, Any] = {}
    for field, values in field_counts.items():
        gold_count = values["gold"]
        pred_count = values["predicted"]
        strict = _prf(values["strict_tp"], pred_count - values["strict_tp"], gold_count - values["strict_tp"])
        safe = _prf(values["safe_tp"], pred_count - values["safe_tp"], gold_count - values["safe_tp"])
        token_micro = _prf(values["token_tp"], pred_count - values["token_tp"], gold_count - values["token_tp"])
        sample_metrics = macro_token_samples[field]
        token_macro = {
            "precision": sum(item["precision"] or 0.0 for item in sample_metrics) / len(sample_metrics) if sample_metrics else 0.0,
            "recall": sum(item["recall"] for item in sample_metrics) / len(sample_metrics) if sample_metrics else 0.0,
            "f1": sum(item["f1"] for item in sample_metrics) / len(sample_metrics) if sample_metrics else 0.0,
            "evaluated_sample_count": len(sample_metrics),
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

    modality = _modality_report(modality_counts, confusion)
    actor_action = _edge_metrics(all_gold_actor_action, all_pred_actor_action)
    order_relation = _edge_metrics(all_gold_order, all_pred_order)
    invalid_records = len(gold_by_id) - valid_records - sum(
        attempt["request_status"] == "api_error" for attempt in attempts_by_id.values()
    )
    api_errors = sum(
        attempt["request_status"] == "api_error" for attempt in attempts_by_id.values()
    )
    recovered_api_errors = sum(
        attempt.get("recovered_runtime_error_category") is not None
        for attempt in attempts_by_id.values()
    )
    requests = len(gold_by_id)

    nonexclusive_errors = Counter(runtime_errors)
    nonexclusive_errors["modality_false_negative"] = int(
        sum(modality_counts[label]["fn"] for label in VALID_MODALITIES)
    )
    for field, metrics in per_field.items():
        nonexclusive_errors[f"{field}_strict_false_negative"] = int(round(metrics["strict_exact"]["fn"]))
        nonexclusive_errors[f"{field}_strict_false_positive"] = int(round(metrics["strict_exact"]["fp"]))
    nonexclusive_errors["actor_action_edge_false_negative"] = int(actor_action["fn"])
    nonexclusive_errors["actor_action_edge_false_positive"] = int(actor_action["fp"])
    nonexclusive_errors["order_relation_edge_false_negative"] = int(order_relation["fn"])
    nonexclusive_errors["order_relation_edge_false_positive"] = int(order_relation["fp"])

    report = {
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
            "entity_alignment": contract["alignment"]["entity"],
        },
        "membership": {
            "sample_count": requests,
            "payload_sha256": actual_membership_sha,
            "gold_attempt_ids_exact_match": True,
        },
        "primary_metrics": {
            "modality": modality,
            "fields": per_field,
        },
        "semantic_coverage": {
            "gold_required_count": coverage_required,
            "predicted_count": coverage_predicted,
            "matched_presence_count": coverage_matched_presence,
            "gold_required_presence_recall": _safe_rate(coverage_matched_presence, coverage_required),
            "predicted_field_precision": _safe_rate(coverage_matched_presence, coverage_predicted),
            "hallucinated_field_rate": 1 - _safe_rate(coverage_matched_presence, coverage_predicted) if coverage_predicted else 0.0,
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
                "exact_precision": _safe_rate(segmentation_exact, total_pred_clauses),
                "exact_recall": _safe_rate(segmentation_exact, total_gold_clauses),
                "exact_f1": _prf(
                    segmentation_exact,
                    total_pred_clauses - segmentation_exact,
                    total_gold_clauses - segmentation_exact,
                )["f1"],
                "mean_gold_clause_span_iou": _safe_rate(clause_iou_sum, total_gold_clauses),
            },
            "schema_valid_rate": valid_records / requests,
        },
        "error_accounting": {
            "categories_are_nonexclusive": True,
            "counts": dict(sorted((key, int(value)) for key, value in nonexclusive_errors.items())),
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
        },
    }
    return report


def build_style_review_template(
    candidates: Sequence[Mapping[str, Any]],
    *,
    dataset_id: str,
    method_id: str,
    sample_size: int,
    seed: str,
) -> dict[str, Any]:
    """Deterministically sample blank, human-only style-equivalence rows."""
    if sample_size < 1:
        raise Stage2EvaluationError("style review sample_size must be positive")
    required = {"sample_id", "clause_id", "field", "gold_text", "predicted_text"}
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for index, raw in enumerate(candidates):
        if not isinstance(raw, Mapping) or not required.issubset(raw):
            raise Stage2EvaluationError(f"style candidate {index} is incomplete")
        item = {key: str(raw[key]) for key in sorted(required)}
        identity = (
            item["sample_id"],
            item["clause_id"],
            item["field"],
            item["gold_text"],
            item["predicted_text"],
        )
        if identity in seen:
            raise Stage2EvaluationError("duplicate style review candidate")
        seen.add(identity)
        normalized.append(item)
    ranked = sorted(
        normalized,
        key=lambda item: (
            hashlib.sha256(seed.encode("utf-8") + b"\0" + canonical_json_bytes(item)).hexdigest(),
            item["sample_id"],
            item["field"],
        ),
    )
    selected = ranked[: min(sample_size, len(ranked))]
    return {
        "schema_version": STYLE_REVIEW_VERSION,
        "dataset_id": dataset_id,
        "method_id": method_id,
        "sampling": {
            "seed": seed,
            "requested": sample_size,
            "selected": len(selected),
            "candidate_payload_sha256": sha256_json(normalized),
        },
        "allowed_decisions": list(STYLE_DECISIONS),
        "human_only": True,
        "records": [
            {
                **item,
                "decision": None,
                "reviewer": None,
                "review_notes": None,
                "review_status": "awaiting_human_review",
            }
            for item in selected
        ],
    }


def _is_rate(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0 <= value <= 1
    )


def validate_evaluation_report(report: Mapping[str, Any]) -> list[str]:
    """Validate the aggregate report without requiring ``jsonschema``.

    The JSON Schema remains the publication-facing artifact.  This strict
    in-process validator makes the same essential invariants available in the
    project's stdlib-only audit environment.
    """
    errors: list[str] = []
    root_keys = {
        "schema_version",
        "task_id",
        "dataset_id",
        "method_id",
        "claim_scope",
        "is_formal_performance_result",
        "contract",
        "membership",
        "primary_metrics",
        "semantic_coverage",
        "structural_encoding",
        "error_accounting",
        "cost_accounting",
        "safety",
    }
    if set(report) != root_keys:
        errors.append("report root keys changed")
    if report.get("schema_version") != REPORT_VERSION or report.get("task_id") != "S2.10-E":
        errors.append("report identity changed")
    scope = report.get("claim_scope")
    if scope not in {"synthetic_contract", "development", "formal"}:
        errors.append("invalid claim_scope")
    if report.get("is_formal_performance_result") is not (scope == "formal"):
        errors.append("formal-result flag disagrees with claim_scope")
    membership = report.get("membership", {})
    if not isinstance(membership, Mapping):
        errors.append("membership must be an object")
    else:
        if not isinstance(membership.get("sample_count"), int) or membership.get("sample_count", 0) < 1:
            errors.append("membership sample_count is invalid")
        payload_sha = membership.get("payload_sha256")
        if not isinstance(payload_sha, str) or re.fullmatch(r"[0-9a-f]{64}", payload_sha) is None:
            errors.append("membership payload_sha256 is invalid")
        if membership.get("gold_attempt_ids_exact_match") is not True:
            errors.append("Gold/attempt membership is not exact")
    primary = report.get("primary_metrics", {})
    modality = primary.get("modality", {}) if isinstance(primary, Mapping) else {}
    if modality.get("labels") != list(VALID_MODALITIES) or modality.get("unit") != "clause":
        errors.append("modality labels or unit changed")
    if not _is_rate(modality.get("macro_f1")):
        errors.append("modality macro_f1 is not a rate")
    per_class = modality.get("per_class", {})
    if not isinstance(per_class, Mapping) or set(per_class) != set(VALID_MODALITIES):
        errors.append("modality per-class keys changed")
    else:
        for label, metric in per_class.items():
            if not isinstance(metric, Mapping) or not _is_rate(metric.get("recall")) or not _is_rate(metric.get("f1")):
                errors.append(f"invalid modality metric: {label}")
            precision = metric.get("precision") if isinstance(metric, Mapping) else None
            if precision is not None and not _is_rate(precision):
                errors.append(f"invalid modality precision: {label}")
    fields = primary.get("fields", {}) if isinstance(primary, Mapping) else {}
    if not isinstance(fields, Mapping) or set(fields) != set(FIELD_LABELS.values()):
        errors.append("field metric keys changed")
    else:
        for field, metric in fields.items():
            if not isinstance(metric, Mapping):
                errors.append(f"field metric is not an object: {field}")
                continue
            for name in ("strict_exact", "safe_normalized", "token_overlap_micro"):
                part = metric.get(name, {})
                if not isinstance(part, Mapping) or not all(
                    _is_rate(part.get(key)) for key in ("precision", "recall", "f1")
                ):
                    errors.append(f"invalid {field}.{name}")
            strict = metric.get("strict_exact", {}).get("f1", 0)
            safe = metric.get("safe_normalized", {}).get("f1", 0)
            if safe + 1e-12 < strict:
                errors.append(f"safe normalization is not a superset for {field}")
            if not math.isclose(metric.get("normalized_f1_lift", math.nan), safe - strict, abs_tol=1e-12):
                errors.append(f"normalized lift disagrees for {field}")
    coverage = report.get("semantic_coverage", {})
    if not isinstance(coverage, Mapping):
        errors.append("semantic_coverage must be an object")
    else:
        for key in (
            "gold_required_presence_recall",
            "predicted_field_precision",
            "hallucinated_field_rate",
            "complete_record_rate",
            "schema_valid_rate",
            "unsupported_or_ambiguous_rate",
            "invalid_record_rate",
            "api_error_rate",
            "recovered_api_error_rate",
            "any_api_error_rate",
            "invalid_or_api_error_rate",
        ):
            if not _is_rate(coverage.get(key)):
                errors.append(f"semantic coverage rate is invalid: {key}")
        if not math.isclose(
            coverage.get("hallucinated_field_rate", math.nan),
            1 - coverage.get("predicted_field_precision", math.nan)
            if coverage.get("predicted_count", 0)
            else 0.0,
            abs_tol=1e-12,
        ):
            errors.append("hallucination rate disagrees with predicted-field precision")
        if not math.isclose(
            coverage.get("any_api_error_rate", math.nan),
            coverage.get("api_error_rate", math.nan)
            + coverage.get("recovered_api_error_rate", math.nan),
            abs_tol=1e-12,
        ):
            errors.append("any API-error rate disagrees with terminal plus recovered rates")
    structural = report.get("structural_encoding", {})
    if not isinstance(structural, Mapping):
        errors.append("structural_encoding must be an object")
    else:
        for edge_name in ("actor_action_edges", "order_relation_edges"):
            edge = structural.get(edge_name, {})
            if not isinstance(edge, Mapping) or not all(
                _is_rate(edge.get(key)) for key in ("precision", "recall", "f1", "jaccard_iou")
            ):
                errors.append(f"invalid structural metric: {edge_name}")
        if structural.get("schema_valid_rate") != coverage.get("schema_valid_rate"):
            errors.append("schema-valid rate differs between report sections")
    cost = report.get("cost_accounting", {})
    if not isinstance(cost, Mapping):
        errors.append("cost_accounting must be an object")
    else:
        if cost.get("request_count") != membership.get("sample_count"):
            errors.append("request count differs from membership count")
        if cost.get("total_tokens") != cost.get("prompt_tokens", 0) + cost.get("completion_tokens", 0):
            errors.append("aggregate token totals disagree")
    safety = report.get("safety", {})
    expected_safety = {
        "gold_modified": False,
        "network_called_by_evaluator": False,
        "llm_called_by_evaluator": False,
        "row_level_predictions_persisted_in_report": False,
    }
    if safety != expected_safety:
        errors.append("report safety boundary changed")
    forbidden_keys = {"gold_records", "attempts", "predictions", "source_text", "source_details"}
    if forbidden_keys & set(report):
        errors.append("row-level data leaked into aggregate report")
    return errors


def validate_style_review_document(
    document: Mapping[str, Any],
    *,
    require_blank: bool = False,
) -> list[str]:
    """Validate a human style-equivalence review document."""
    errors: list[str] = []
    if document.get("schema_version") != STYLE_REVIEW_VERSION:
        errors.append("style review version changed")
    if document.get("human_only") is not True:
        errors.append("style review must remain human-only")
    if document.get("allowed_decisions") != list(STYLE_DECISIONS):
        errors.append("style review decisions changed")
    records = document.get("records")
    if not isinstance(records, list):
        return errors + ["style review records must be an array"]
    seen: set[tuple[str, str, str]] = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            errors.append(f"style records[{index}] must be an object")
            continue
        identity = (
            str(record.get("sample_id")),
            str(record.get("clause_id")),
            str(record.get("field")),
        )
        if identity in seen:
            errors.append(f"duplicate style review identity: {identity}")
        seen.add(identity)
        decision = record.get("decision")
        if decision is not None and decision not in STYLE_DECISIONS:
            errors.append(f"invalid style decision at records[{index}]")
        if require_blank and (
            decision is not None
            or record.get("reviewer") is not None
            or record.get("review_notes") is not None
            or record.get("review_status") != "awaiting_human_review"
        ):
            errors.append(f"style records[{index}] was auto-filled")
    sampling = document.get("sampling", {})
    if not isinstance(sampling, Mapping) or sampling.get("selected") != len(records):
        errors.append("style sampling count disagrees")
    return errors
