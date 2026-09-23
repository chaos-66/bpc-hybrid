# -*- coding: utf-8 -*-
"""Repaired Stage-3 paired benchmark comparison (Table 3 v2).

This module implements the controlled protocol requested for the third
experiment table:

* Sun and Ours replace only Stage 2.  Their persisted Stage-2 rule
  predictions are converted by the same ``gdpr_capsule_converter`` and scored
  by one frozen ``SunScorer`` instance with one frozen threshold triple.
* Winter runs through its native wrapper and frozen configuration.
* Inference sees only the current BPMN plus rule text / rule predictions.
  Prediction rows contain no pair role, gold label, target type, mutation
  description, control id, target activity id or expected lane.
* All three detector signals are produced and persisted for every item before
  the evaluator reads any benchmark label.

The evaluator is intentionally target-check scoped.  The paired benchmark
provides labels only for the injected check named by each pair; it does not
provide complete multi-label compliance annotations.  Non-target alarms are
therefore preserved in the prediction evidence but marked unevaluated instead
of being counted as false positives.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

TYPES = ("missing_action", "incorrect_actor", "out_of_order")
COMPLIANT = "compliant"
SCHEMA_VERSION = "stage3_table3_v2@1.0.0"

ALLOWED_INFERENCE_ITEM_KEYS = (
    "item_id",
    "pair_id",
    "bpmn_path",
    "rule_id",
    "process_id",
)

METHODS: dict[str, dict[str, Any]] = {
    "sun_rules_only_frozen_sun_stage3": {
        "label": "Sun (Rules-Only Stage 2 + frozen Sun Stage 3)",
        "paper_label": "Sun",
        "stage2_kind": "rules_only",
        "predictions_path": (
            "data/predictions/gdpr7_sun_rule_only_v1/predictions.json"
        ),
        "expected_schema": "gdpr7_sun_rule_only_predictions@1.0.0",
        "llm_used": False,
    },
    "ours_direct_llm_frozen_sun_stage3": {
        "label": "Ours (Direct-LLM Stage 2 + frozen Sun Stage 3)",
        "paper_label": "Ours",
        "stage2_kind": "direct_llm",
        "predictions_path": (
            "data/predictions/gdpr7_direct_llm_v1/predictions.json"
        ),
        "expected_schema": "gdpr7_direct_llm_predictions@1.0.0",
        "llm_used": True,
    },
    "winter_2020_native_wrapper": {
        "label": "Winter (native wrapper, frozen config)",
        "paper_label": "Winter",
        "stage2_kind": "native_regulation_text",
        "predictions_path": None,
        "expected_schema": None,
        "llm_used": False,
    },
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def project_inference_items(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Keep only current-BPMN inference fields; drop role and all labels."""
    out: list[dict[str, Any]] = []
    for raw in doc.get("items") or []:
        item = {key: raw.get(key) for key in ALLOWED_INFERENCE_ITEM_KEYS}
        if not all(item.get(key) for key in (
                "item_id", "pair_id", "bpmn_path", "rule_id", "process_id")):
            continue
        out.append(item)
    return out


def load_stage2_sentence_index(input_pack_path: Path) -> dict[str, str]:
    doc = load_json(input_pack_path)
    out: dict[str, str] = {}
    for rule in doc.get("rules") or []:
        for sentence in rule.get("sentences") or []:
            sample_id = str(sentence.get("sample_id") or "")
            text = str(sentence.get("approved_text_en") or "")
            if sample_id:
                out[sample_id] = text
    return out


def load_regulation_text_index(path: Path) -> dict[str, str]:
    doc = load_json(path)
    out: dict[str, str] = {}
    for row in doc.get("rule_texts") or []:
        rule_id = str(row.get("rule_id") or "")
        text = str(row.get("rule_text") or "")
        expected_hash = str(row.get("rule_text_sha256") or "")
        actual_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if expected_hash and expected_hash != actual_hash:
            raise ValueError(
                f"regulation text hash mismatch for {rule_id}: "
                f"{expected_hash} != {actual_hash}"
            )
        if rule_id:
            out[rule_id] = text
    return out


def build_converted_rule_records(
    *,
    predictions_path: Path,
    sentence_input_path: Path,
    expected_schema: str,
    rule_ids: Sequence[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Convert one Stage-2 capsule with the shared frozen converter."""
    from bpc_hybrid.sun_stage3.gdpr_capsule_converter import (
        build_rule_records,
        sentence_texts_by_sample,
    )

    capsule = load_json(predictions_path)
    input_doc = load_json(sentence_input_path)
    texts_by_sample = sentence_texts_by_sample(input_doc)
    records, summary = build_rule_records(
        capsule,
        texts_by_sample,
        list(rule_ids),
        expected_schema=expected_schema,
    )
    return records, summary


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def normalize_sun_signal(check_type: str, raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Turn a raw ``SunScorer`` result into an explicit three-state signal."""
    raw = dict(raw or {})
    details = _jsonable(raw.get("details") or [])
    if check_type == "missing_action":
        denominator = int(raw.get("denominator") or 0)
        score = raw.get("score")
        if denominator <= 0 or not details:
            return {
                "status": "unknown",
                "raw_score": score,
                "denominator": denominator,
                "observable": False,
                "reason": "no_rule_actions",
                "evidence": {"details": details},
            }
        status = "violated" if float(score or 0.0) > 0.0 else "satisfied"
        return {
            "status": status,
            "raw_score": score,
            "denominator": denominator,
            "observable": True,
            "reason": None,
            "evidence": {"details": details},
        }
    if check_type == "incorrect_actor":
        observable = bool(raw.get("observable", raw.get("score") is not None))
        score = raw.get("score")
        if not observable or score is None:
            return {
                "status": "unknown",
                "raw_score": score,
                "denominator": int(raw.get("denominator") or 0),
                "observable": False,
                "reason": raw.get("reason") or "unobservable_actor_relation",
                "evidence": _jsonable({
                    "details": raw.get("details") or [],
                    "unmapped_rule_actors": raw.get("unmapped_rule_actors") or [],
                }),
            }
        status = "violated" if float(score) > 0.0 else "satisfied"
        return {
            "status": status,
            "raw_score": score,
            "denominator": int(raw.get("denominator") or 0),
            "observable": True,
            "reason": None,
            "evidence": _jsonable({
                "details": raw.get("details") or [],
                "process_actor_candidates": raw.get("process_actor_candidates") or [],
                "matched_process_action_ids": raw.get("matched_process_action_ids") or [],
            }),
        }
    if check_type == "out_of_order":
        denominator = int(raw.get("denominator") or 0)
        score = raw.get("score")
        if denominator <= 0 or score is None:
            return {
                "status": "unknown",
                "raw_score": score,
                "denominator": denominator,
                "observable": False,
                "reason": raw.get("reason") or "no_rule_order_endpoints",
                "evidence": {"details": details},
            }
        status = "violated" if float(score) > 0.0 else "satisfied"
        return {
            "status": status,
            "raw_score": score,
            "denominator": denominator,
            "observable": True,
            "reason": None,
            "evidence": {"details": details},
        }
    raise ValueError(f"unknown check type: {check_type}")


def _winter_mapping_evidence(pair: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mapping in pair.mapping:
        model_obligation = mapping.get("model_obligation_lemmatized")
        if isinstance(model_obligation, list):
            model_text = " ".join(str(x) for x in model_obligation)
        elif model_obligation is None:
            model_text = ""
        else:
            model_text = str(model_obligation)
        paragraph_obligation = mapping.get("paragraph_obligation")
        paragraph_text = getattr(paragraph_obligation, "lemmatized", "")
        rows.append({
            "paragraph_obligation_lemmatized": str(paragraph_text or ""),
            "model_obligation_lemmatized": model_text,
            "model_resource": mapping.get("model_resource"),
            "similarity": mapping.get("sim_score"),
        })
    return rows


def winter_signals(
    *,
    pair: Any,
    model: Any,
    paragraph: Any,
    resource_set: set[str],
) -> dict[str, dict[str, Any]]:
    """Convert a native Winter ``WinterPair`` into explicit three-state signals."""
    n_obligations = len(paragraph.obligations)
    n_model_obligations = sum(
        len(values) for values in (model.obligations or {}).values()
    )
    flow_count = 0 if not paragraph.flows else len(paragraph.flows)
    mapping_evidence = _winter_mapping_evidence(pair)
    costs = {
        "cost_obligation": float(pair.cost_obligation),
        "cost_resource": float(pair.cost_resource),
        "cost_so": float(pair.cost_so),
        "fitness": float(pair.fitness),
    }

    if n_obligations <= 0:
        missing = {
            "status": "unknown",
            "raw_score": None,
            "denominator": 0,
            "observable": False,
            "reason": "no_rule_obligations",
            "evidence": {"obligation_count": 0, "mapping": mapping_evidence},
        }
    else:
        missing = {
            "status": ("violated" if costs["cost_obligation"] > 0.0
                       else "satisfied"),
            "raw_score": costs["cost_obligation"],
            "denominator": n_obligations,
            "observable": True,
            "reason": None,
            "evidence": {
                "obligation_count": n_obligations,
                "model_obligation_count": n_model_obligations,
                "mapping": mapping_evidence,
            },
        }

    if n_obligations <= 0:
        actor_reason = "no_rule_obligations"
        actor = {
            "status": "unknown",
            "raw_score": None,
            "denominator": 0,
            "observable": False,
            "reason": actor_reason,
            "evidence": {"resource_set": sorted(resource_set), "mapping": []},
        }
    elif not resource_set:
        actor = {
            "status": "unknown",
            "raw_score": None,
            "denominator": 0,
            "observable": False,
            "reason": "no_process_resource_labels",
            "evidence": {"resource_set": [], "mapping": mapping_evidence},
        }
    elif not model.processes:
        actor = {
            "status": "unknown",
            "raw_score": None,
            "denominator": 0,
            "observable": False,
            "reason": "no_process_models",
            "evidence": {"resource_set": sorted(resource_set), "mapping": mapping_evidence},
        }
    else:
        actor = {
            "status": ("violated" if costs["cost_resource"] > 0.0
                       else "satisfied"),
            "raw_score": costs["cost_resource"],
            "denominator": n_obligations,
            "observable": True,
            "reason": None,
            "evidence": {
                "resource_set": sorted(resource_set),
                "mapping": mapping_evidence,
            },
        }

    if flow_count <= 0:
        order = {
            "status": "unknown",
            "raw_score": None,
            "denominator": 0,
            "observable": False,
            "reason": "no_rule_side_flow_relations",
            "evidence": {"flow_count": 0, "mapping": mapping_evidence},
        }
    else:
        order = {
            "status": ("violated" if costs["cost_so"] > 0.0
                       else "satisfied"),
            "raw_score": costs["cost_so"],
            "denominator": flow_count,
            "observable": True,
            "reason": None,
            "evidence": {"flow_count": flow_count, "mapping": mapping_evidence},
        }

    return {
        "missing_action": missing,
        "incorrect_actor": actor,
        "out_of_order": order,
    }


def violated_types(signals: Mapping[str, Mapping[str, Any]]) -> list[str]:
    return [t for t in TYPES
            if (signals.get(t) or {}).get("status") == "violated"]


def _metric_block(
    *,
    positive: int,
    negative: int,
    tp: int,
    fp: int,
    fn: int,
    tn: int,
    unknown_positive: int,
    unknown_negative: int,
    variant_detected: int,
    control_fp: int,
    control_unknown: int,
    variant_unknown: int,
    pair_both_correct: int,
    pairs: int,
    cross_type_alarms: int,
    cross_type_unknowns: int,
) -> dict[str, Any]:
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    if positive <= 0:
        f1 = None
    elif precision is None and recall == 0:
        f1 = 0.0
    elif precision is None or recall is None:
        f1 = None
    else:
        f1 = (2.0 * precision * recall / (precision + recall)
              if (precision + recall) else 0.0)
    observed_fn = max(0, fn - unknown_positive)
    observable = tp + fp + tn + observed_fn
    total = positive + negative
    return {
        "positive_count": positive,
        "negative_count": negative,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "unknown_positive": unknown_positive,
        "unknown_negative": unknown_negative,
        "unknown": unknown_positive + unknown_negative,
        "observable": observable,
        "coverage": (observable / total) if total else None,
        "positive_coverage": (
            (tp + observed_fn) / positive if positive else None),
        "negative_coverage": (
            (tn + fp) / negative if negative else None),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "variant_detected": variant_detected,
        "control_fp": control_fp,
        "control_unknown": control_unknown,
        "variant_unknown": variant_unknown,
        "pair_both_correct": pair_both_correct,
        "pairs": pairs,
        "pair_both_correct_rate": (
            pair_both_correct / pairs if pairs else None),
        "cross_type_alarms": cross_type_alarms,
        "cross_type_unknowns": cross_type_unknowns,
        "non_target_evaluation_status": (
            "not_evaluated_no_reference_label"),
    }


def evaluate_predictions(
    *,
    benchmark: Mapping[str, Any],
    eligibility: Mapping[str, Any],
    prediction_rows: Sequence[Mapping[str, Any]],
    method_ids: Sequence[str],
) -> dict[str, Any]:
    """Recompute all reported counts from persisted prediction rows.

    The evaluator reads benchmark labels and eligibility only after the runner
    has persisted every prediction row.  It scores the *target check* of each
    eligible pair; non-target signals are reported as unevaluated alarms.
    """
    eligible = {
        (str(row.get("pair_id")), str(row.get("violation_type"))): bool(
            row.get("eligible"))
        for row in eligibility.get("records") or []
    }
    items = list(benchmark.get("items") or [])
    item_by_id = {str(item.get("item_id")): item for item in items}
    pred_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in prediction_rows:
        pred_by_key[(str(row.get("method_id")), str(row.get("item_id")))] = row

    methods_out: dict[str, Any] = {}
    for method_id in method_ids:
        method_rows = [r for r in prediction_rows
                       if str(r.get("method_id")) == method_id]
        per_type: dict[str, Any] = {}
        micro_tp = micro_fp = micro_fn = 0
        micro_unknown_positive = micro_unknown_negative = 0
        supported_types: list[str] = []
        for check_type in TYPES:
            scoped = [
                item for item in items
                if str(item.get("target_violation_type")) == check_type
                and eligible.get((str(item.get("pair_id")), check_type), False)
            ]
            positives = [i for i in scoped if i.get("role") == "variant"]
            negatives = [i for i in scoped if i.get("role") == "control"]
            pair_ids = sorted({str(i.get("pair_id")) for i in scoped})
            tp = fp = fn = tn = 0
            unknown_positive = unknown_negative = 0
            variant_detected = control_fp = control_unknown = 0
            variant_unknown = 0
            pair_success = 0
            cross_type_alarms = 0
            cross_type_unknowns = 0
            for item in scoped:
                method_pred = pred_by_key.get((method_id, str(item.get("item_id"))))
                signals = (method_pred or {}).get("signals") or {}
                signal = signals.get(check_type) or {}
                status = str(signal.get("status") or "unknown")
                non_target_statuses = [
                    str((signals.get(t) or {}).get("status") or "unknown")
                    for t in TYPES if t != check_type
                ]
                if any(s == "violated" for s in non_target_statuses):
                    cross_type_alarms += 1
                if any(s == "unknown" for s in non_target_statuses):
                    cross_type_unknowns += 1
                if item.get("role") == "variant":
                    if status == "violated":
                        tp += 1
                        variant_detected += 1
                    else:
                        fn += 1
                        if status == "unknown":
                            unknown_positive += 1
                            variant_unknown += 1
                else:
                    if status == "violated":
                        fp += 1
                        control_fp += 1
                    elif status == "satisfied":
                        tn += 1
                    else:
                        unknown_negative += 1
                        control_unknown += 1
            if positives:
                supported_types.append(check_type)
            for pair_id in pair_ids:
                variant = next((i for i in positives
                                if str(i.get("pair_id")) == pair_id), None)
                control = next((i for i in negatives
                                if str(i.get("pair_id")) == pair_id), None)
                if variant is None or control is None:
                    continue
                v_pred = pred_by_key.get((method_id, str(variant.get("item_id")))) or {}
                c_pred = pred_by_key.get((method_id, str(control.get("item_id")))) or {}
                v_status = str(((v_pred.get("signals") or {}).get(check_type) or {}).get("status") or "unknown")
                c_status = str(((c_pred.get("signals") or {}).get(check_type) or {}).get("status") or "unknown")
                if v_status == "violated" and c_status == "satisfied":
                    pair_success += 1
            block = _metric_block(
                positive=len(positives),
                negative=len(negatives),
                tp=tp,
                fp=fp,
                fn=fn,
                tn=tn,
                unknown_positive=unknown_positive,
                unknown_negative=unknown_negative,
                variant_detected=variant_detected,
                control_fp=control_fp,
                control_unknown=control_unknown,
                variant_unknown=variant_unknown,
                pair_both_correct=pair_success,
                pairs=len(pair_ids),
                cross_type_alarms=cross_type_alarms,
                cross_type_unknowns=cross_type_unknowns,
            )
            block["status"] = (
                "N/A_no_eligible_positive"
                if not positives else "evaluated_target_check"
            )
            per_type[check_type] = block
            if positives:
                micro_tp += tp
                micro_fp += fp
                micro_fn += fn
                micro_unknown_positive += unknown_positive
                micro_unknown_negative += unknown_negative
        macro_values = [per_type[t]["f1"] for t in supported_types
                        if per_type[t]["f1"] is not None]
        total_positive = sum(per_type[t]["positive_count"] for t in supported_types)
        total_negative = sum(per_type[t]["negative_count"] for t in supported_types)
        micro_precision = (micro_tp / (micro_tp + micro_fp)
                           if (micro_tp + micro_fp) else None)
        micro_recall = (micro_tp / (micro_tp + micro_fn)
                        if (micro_tp + micro_fn) else None)
        if total_positive <= 0:
            micro_f1 = None
        elif micro_precision is None and micro_recall == 0:
            micro_f1 = 0.0
        elif micro_precision is None or micro_recall is None:
            micro_f1 = None
        else:
            micro_f1 = (2.0 * micro_precision * micro_recall
                        / (micro_precision + micro_recall)
                        if (micro_precision + micro_recall) else 0.0)
        method_meta = METHODS.get(method_id, {})
        methods_out[method_id] = {
            "method_id": method_id,
            "label": method_meta.get("label", method_id),
            "paper_label": method_meta.get("paper_label", method_id),
            "prediction_rows": len(method_rows),
            "per_type": per_type,
            "macro_f1": (sum(macro_values) / len(macro_values)
                         if macro_values else None),
            "macro_f1_scope": supported_types,
            "micro_f1": {
                "positive_count": total_positive,
                "negative_count": total_negative,
                "tp": micro_tp,
                "fp": micro_fp,
                "fn": micro_fn,
                "unknown_positive": micro_unknown_positive,
                "unknown_negative": micro_unknown_negative,
                "unknown": micro_unknown_positive + micro_unknown_negative,
                "precision": micro_precision,
                "recall": micro_recall,
                "f1": micro_f1,
            },
            "not_evaluated_types": [
                t for t in TYPES if t not in supported_types
            ],
        }

    controls = [
        item for item in items
        if item.get("role") == "control"
        and eligible.get((
            str(item.get("pair_id")),
            str(item.get("target_violation_type")),
        ), False)
    ]
    control_counts = Counter(str(i.get("bpmn_path")) for i in controls)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "benchmark_id": benchmark.get("benchmark_id"),
        "eligibility_protocol": eligibility.get("schema_version")
        or "stage3_paired_benchmark_eligibility_v1",
        "aggregation_scope": (
            "target-check metrics on the pre-frozen eligible pairs; "
            "non-target alarms are retained as unevaluated"
        ),
        "denominators": {
            "eligible_items_total": len(controls) * 2,
            "eligible_pairs_total": len(controls),
            "positive_items_by_type": {
                t: sum(1 for i in items
                       if i.get("role") == "variant"
                       and str(i.get("target_violation_type")) == t
                       and eligible.get((str(i.get("pair_id")), t), False))
                for t in TYPES
            },
            "negative_items_by_type": {
                t: sum(1 for i in items
                       if i.get("role") == "control"
                       and str(i.get("target_violation_type")) == t
                       and eligible.get((str(i.get("pair_id")), t), False))
                for t in TYPES
            },
        },
        "duplicate_control_audit": {
            "eligible_control_items": len(controls),
            "unique_control_bpmn": len(control_counts),
            "duplicate_control_items": len(controls) - len(control_counts),
            "control_bpmn_counts": dict(sorted(control_counts.items())),
            "evidence_independence_warning": (
                "Repeated control BPMNs are not independent observations; "
                "the independent original-flow count is the unique-BPMN count."
            ),
        },
        "methods": methods_out,
    }


def markdown_table(report: Mapping[str, Any]) -> str:
    lines = [
        "# Stage 3 Table 3 v2 (repaired controlled comparison)",
        "",
        f"- benchmark: `{report.get('benchmark_id')}`",
        f"- aggregation: {report.get('aggregation_scope')}",
        f"- eligible pairs: {report['denominators']['eligible_pairs_total']}",
        f"- unique control BPMNs: {report['duplicate_control_audit']['unique_control_bpmn']}",
        f"- duplicate control items: {report['duplicate_control_audit']['duplicate_control_items']}",
        "",
        "| Method | Type | Positive | Negative | TP | FP | FN | TN | Unknown + | Unknown - | P | R | F1 | Coverage | Variant detected | Control FP | Pair both-correct |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method_id, method in report["methods"].items():
        for check_type in TYPES:
            block = method["per_type"][check_type]
            def fmt(value: Any, digits: int = 4) -> str:
                if value is None:
                    return "N/A"
                if isinstance(value, float):
                    return f"{value:.{digits}f}"
                return str(value)
            lines.append(
                "| {label} | {typ} | {pos} | {neg} | {tp} | {fp} | {fn} | {tn} | "
                "{up} | {un} | {p} | {r} | {f1} | {cov} | {vd} | {cfp} | {pbc} |".format(
                    label=method["label"],
                    typ=check_type,
                    pos=block["positive_count"],
                    neg=block["negative_count"],
                    tp=block["tp"],
                    fp=block["fp"],
                    fn=block["fn"],
                    tn=block["tn"],
                    up=block["unknown_positive"],
                    un=block["unknown_negative"],
                    p=fmt(block["precision"]),
                    r=fmt(block["recall"]),
                    f1=fmt(block["f1"]),
                    cov=fmt(block["coverage"]),
                    vd="{}/{}".format(block["variant_detected"], block["positive_count"]),
                    cfp="{}/{}".format(block["control_fp"], block["negative_count"]),
                    pbc="{}/{}".format(block["pair_both_correct"], block["pairs"]),
                )
            )
        lines.append(
            "| {label} | **macro** |  |  |  |  |  |  |  |  |  |  | {m} |  |  |  |  |".format(
                label=method["label"],
                m=fmt(method["macro_f1"]),
            )
        )
        micro = method["micro_f1"]
        lines.append(
            "| {label} | **micro** | {pos} | {neg} | {tp} | {fp} | {fn} |  | {up} | {un} | {p} | {r} | {f1} |  |  |  |  |".format(
                label=method["label"],
                pos=micro["positive_count"],
                neg=micro["negative_count"],
                tp=micro["tp"],
                fp=micro["fp"],
                fn=micro["fn"],
                up=micro["unknown_positive"],
                un=micro["unknown_negative"],
                p=fmt(micro["precision"]),
                r=fmt(micro["recall"]),
                f1=fmt(micro["f1"]),
            )
        )
    lines += [
        "",
        "`out_of_order` is N/A because the frozen rule records provide no rule-side order relation; it is not zero-filled.",
        "`unknown` positives count as misses; `unknown` negatives are not counted as correct rejections.",
        "Non-target alarms are retained in the per-item prediction evidence but marked unevaluated; the paired benchmark labels only the named target check.",
    ]
    return "\n".join(lines) + "\n"


__all__ = [
    "ALLOWED_INFERENCE_ITEM_KEYS",
    "COMPLIANT",
    "METHODS",
    "SCHEMA_VERSION",
    "TYPES",
    "build_converted_rule_records",
    "evaluate_predictions",
    "load_json",
    "load_regulation_text_index",
    "load_stage2_sentence_index",
    "markdown_table",
    "normalize_sun_signal",
    "project_inference_items",
    "sha256_file",
    "violated_types",
    "winter_signals",
]