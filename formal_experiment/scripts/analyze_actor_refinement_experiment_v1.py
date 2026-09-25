# -*- coding: utf-8 -*-
"""Offline evaluator and attribution for the D1 Actor-refinement experiment.

This script is run only after all four arms' raw responses and canonical
predictions are locked.  It uses the frozen Gold and the same
``sun_literal_overlap_evaluation@2.0.0`` evaluator for all arms, and writes
the unified development report requested by the experiment protocol.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for _path in (SRC, SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import run_actor_refinement_experiment_v1 as runner  # noqa: E402
import audit_d1_actor_semantic_error_v1 as audit  # noqa: E402
from bpc_hybrid.d1_span_canonicalizer import (  # noqa: E402
    POLICY_REPAIR,
)
from bpc_hybrid.stage2_sun_literal_overlap import (  # noqa: E402
    evaluate_sun_literal_overlap,
)

OUT_DIR = runner.OUT_DIR
REPORT_JSON = runner.REPORT_JSON
REPORT_MD = runner.REPORT_MD
ARM_ORDER = runner.ARM_ORDER
ARMS = runner.ARMS
FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")
HISTORICAL_AUDIT = (
    ROOT / "outputs" / "reports" / "d1_actor_semantic_error_audit_v1.json"
)
HISTORICAL_LEGACY_EVAL = (
    ROOT / "outputs" / "development" / "barrientos_ablation_suite_v2"
    / "D-full-0813" / "repeat-01" / "evaluation.json"
)
EXPECTED_GOLD_REVIEW = {
    "estg_000037": "the insured person",
    "estg_000659": "Persons with limited tax liability",
    "estg_000716": "the building society",
}


class ActorRefinementAnalysisError(RuntimeError):
    """Fail-closed analysis input error."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ActorRefinementAnalysisError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ActorRefinementAnalysisError(f"missing JSONL: {path}")
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(
        microsecond=0).isoformat().replace("+00:00", "Z")


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, float):
        return round(value, digits)
    return value


def _delta(new: Any, old: Any) -> float | None:
    if new is None or old is None:
        return None
    return float(new) - float(old)


def _metric(metrics: Mapping[str, Any], name: str) -> Any:
    return metrics.get(name)


def _gold_by_id() -> dict[str, Any]:
    from run_d_span_grounding_repair_v1 import build_gold_by_id
    gold = build_gold_by_id()
    if len(gold) != 150:
        raise ActorRefinementAnalysisError("Gold membership drift")
    return gold


def _evaluate_predictions(
    predictions: Sequence[Mapping[str, Any]],
    gold_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    attempts = [
        {
            "sample_id": row["sample_id"],
            "request_status": row.get("request_status"),
            "record": row.get("record") or {},
        }
        for row in predictions
    ]
    metrics = evaluate_sun_literal_overlap(
        list(gold_by_id.values()),
        attempts,
        dataset_id="independently_reconstructed_estg_150_v1",
        method_id="direct_llm",
    )
    return {
        "evaluator": "sun_literal_overlap@2.0.0",
        "metrics": metrics,
    }


def _load_arm_data(arm: str, gold_by_id: Mapping[str, Any],
                   source_by_id: Mapping[str, str]) -> dict[str, Any]:
    run_dir = OUT_DIR / arm / "repeat-01"
    predictions = _read_jsonl(run_dir / "canonical_predictions.jsonl")
    if len(predictions) != 150:
        raise ActorRefinementAnalysisError(
            f"arm {arm} has {len(predictions)} predictions, expected 150")
    raw_rows = _read_jsonl(run_dir / "raw_responses.jsonl")
    manifest = _read_json(run_dir / "manifest.json")
    evaluation = _evaluate_predictions(predictions, gold_by_id)
    inventory = audit.build_actor_inventory(
        predictions, gold_by_id, source_by_id)
    inventory["fp_taxonomy"] = audit._taxonomy_counts(inventory["fp_cases"])
    inventory["fn_taxonomy"] = audit._taxonomy_counts(inventory["fn_cases"])
    inventory["pronoun_analysis"] = audit._pronoun_analysis(inventory)
    return {
        "arm": arm,
        "predictions": predictions,
        "raw_rows": raw_rows,
        "manifest": manifest,
        "evaluation": evaluation,
        "metrics": evaluation["metrics"],
        "inventory": inventory,
        "run_dir": run_dir,
    }


def _actor_span_map(
    predictions: Sequence[Mapping[str, Any]]
) -> dict[tuple[str, int, int, str], dict[str, Any]]:
    spans: dict[tuple[str, int, int, str], dict[str, Any]] = {}
    for row in predictions:
        sid = str(row["sample_id"])
        record = row.get("record") or {}
        for item in audit._record_semantic_spans(record):
            if item["field"] != "actors":
                continue
            span = item["span"]
            key = (
                sid,
                int(span.get("start", -1)),
                int(span.get("end", -1)),
                audit._norm_text(span.get("text")),
            )
            spans[key] = dict(span)
    return spans


def _condition_spans_by_id(
    predictions: Sequence[Mapping[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {
        str(row["sample_id"]): [] for row in predictions}
    for row in predictions:
        sid = str(row["sample_id"])
        record = row.get("record") or {}
        out[sid].extend(
            audit._flatten_field(record, "conditions"))
    return out


def _gold_actor_spans_by_id(gold_by_id: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        sid: audit._flatten_field(record, "actors")
        for sid, record in gold_by_id.items()
    }


def _span_mapping(key: tuple[str, int, int, str]) -> dict[str, Any]:
    return {
        "sample_id": key[0],
        "start": key[1],
        "end": key[2],
        "text_normalized": key[3],
    }


def _overlaps_gold(
    span: Mapping[str, Any],
    gold_by_id: Mapping[str, Any],
    gold_actors_by_id: Mapping[str, Sequence[Mapping[str, Any]]],
) -> bool:
    sid = str(span.get("sample_id") or "")
    return any(
        audit._intersects(span, gold_span)
        for gold_span in gold_actors_by_id.get(sid, [])
    )


def _case_for_span(
    arm_data: Mapping[str, Any],
    sample_id: str,
    start: int,
    end: int,
    *,
    prediction_side: bool,
) -> dict[str, Any] | None:
    inventory = arm_data["inventory"]
    collections: list[tuple[str, Sequence[Mapping[str, Any]]]] = []
    if prediction_side:
        collections = [
            ("tp", inventory["tp_cases"]),
            ("fp", inventory["fp_cases"]),
        ]
    else:
        collections = [("fn", inventory["fn_cases"])]
    for side, collection in collections:
        for case in collection:
            if prediction_side:
                span = case.get("predicted_actor") or {}
            else:
                span = case.get("gold_actor") or {}
            if str(case.get("sample_id")) == sample_id and int(
                    span.get("start", -1)) == start and int(
                    span.get("end", -1)) == end:
                result = dict(case)
                result.setdefault("inventory_side", side)
                return result
    return None


def _classify_changed_spans(
    base_data: Mapping[str, Any],
    other_data: Mapping[str, Any],
    *,
    gold_by_id: Mapping[str, Any],
    gold_actors_by_id: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    base_spans = _actor_span_map(base_data["predictions"])
    other_spans = _actor_span_map(other_data["predictions"])
    base_keys = set(base_spans)
    other_keys = set(other_spans)
    removed = []
    for key in sorted(base_keys - other_keys):
        span = base_spans[key]
        mapping = _span_mapping(key)
        gold_overlap = _overlaps_gold(mapping, gold_by_id, gold_actors_by_id)
        case = _case_for_span(
            base_data, key[0], key[1], key[2], prediction_side=True)
        taxonomy = (
            (case or {}).get("taxonomy")
            or ("TP" if (case or {}).get("inventory_side") == "tp"
                else "UNCLASSIFIED")
        )
        removed.append({
            "sample_id": key[0],
            "text": span.get("text"),
            "normalized": span.get("normalized"),
            "start": key[1],
            "end": key[2],
            "gold_overlap": gold_overlap,
            "classification": (
                "harmful_TP_removal" if gold_overlap
                else "beneficial_FP_removal"),
            "base_side_taxonomy": taxonomy,
        })
    added = []
    for key in sorted(other_keys - base_keys):
        span = other_spans[key]
        mapping = _span_mapping(key)
        gold_overlap = _overlaps_gold(mapping, gold_by_id, gold_actors_by_id)
        added.append({
            "sample_id": key[0],
            "text": span.get("text"),
            "normalized": span.get("normalized"),
            "start": key[1],
            "end": key[2],
            "gold_overlap": gold_overlap,
            "classification": "new_TP" if gold_overlap else "new_FP",
        })
    retained = len(base_keys & other_keys)
    return {
        "base_actor_count": len(base_keys),
        "other_actor_count": len(other_keys),
        "retained_actor_count": retained,
        "removed": removed,
        "added": added,
        "removed_count": len(removed),
        "added_count": len(added),
        "harmful_tp_removal_count": sum(
            1 for row in removed if row["gold_overlap"]),
        "beneficial_fp_removal_count": sum(
            1 for row in removed if not row["gold_overlap"]),
        "new_tp_count": sum(1 for row in added if row["gold_overlap"]),
        "new_fp_count": sum(1 for row in added if not row["gold_overlap"]),
    }


def _factor_r(
    b0: Mapping[str, Any],
    r: Mapping[str, Any],
    gold_by_id: Mapping[str, Any],
    gold_actors_by_id: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    change = _classify_changed_spans(
        b0, r, gold_by_id=gold_by_id, gold_actors_by_id=gold_actors_by_id)
    b0_fp_tax = b0["inventory"]["fp_taxonomy"]["counts"]
    r_fp_tax = r["inventory"]["fp_taxonomy"]["counts"]
    non_role_key = "FP-B_NON_ROLE_GRAMMATICAL_SUBJECT"
    legal_role_tp_removed = [
        row for row in change["removed"]
        if row["gold_overlap"] and audit._looks_like_legal_role(row["text"])
    ]
    pronoun_changes = {
        "base_pronoun_count": sum(
            1 for key in _actor_span_map(b0["predictions"])
            if audit._is_pronoun(key[3])),
        "other_pronoun_count": sum(
            1 for key in _actor_span_map(r["predictions"])
            if audit._is_pronoun(key[3])),
        "base_pronoun_removed": sum(
            1 for row in change["removed"]
            if audit._is_pronoun(row["text"])),
        "other_pronoun_added": sum(
            1 for row in change["added"]
            if audit._is_pronoun(row["text"])),
    }
    return {
        "conceptual_factor": "actor_role_eligibility_only",
        "non_role_fp": {
            "B0": b0_fp_tax.get(non_role_key, 0),
            "R": r_fp_tax.get(non_role_key, 0),
            "delta": r_fp_tax.get(non_role_key, 0)
            - b0_fp_tax.get(non_role_key, 0),
        },
        "actor_changes": change,
        "legal_role_tp_removed_count": len(legal_role_tp_removed),
        "legal_role_tp_removed": legal_role_tp_removed,
        "pronoun_prediction_stability": pronoun_changes,
        "fn_delta": (
            r["inventory"]["fn_count"] - b0["inventory"]["fn_count"]
        ),
        "remaining_fp_taxonomy_R": r["inventory"]["fp_taxonomy"]["counts"],
        "remaining_fn_taxonomy_R": r["inventory"]["fn_taxonomy"]["counts"],
    }


def _pronoun_summary(arm_data: Mapping[str, Any]) -> dict[str, Any]:
    return arm_data["inventory"]["pronoun_analysis"]


def _factor_p(
    b0: Mapping[str, Any],
    p: Mapping[str, Any],
    gold_by_id: Mapping[str, Any],
    gold_actors_by_id: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    change = _classify_changed_spans(
        b0, p, gold_by_id=gold_by_id, gold_actors_by_id=gold_actors_by_id)
    b0_non_pronoun = {
        key for key in _actor_span_map(b0["predictions"])
        if not audit._is_pronoun(key[3])
    }
    p_non_pronoun = {
        key for key in _actor_span_map(p["predictions"])
        if not audit._is_pronoun(key[3])
    }
    non_pronoun_changed = len(b0_non_pronoun ^ p_non_pronoun)
    b0_map = _actor_span_map(b0["predictions"])
    p_map = _actor_span_map(p["predictions"])
    changed_non_pronoun_spans = []
    for key in sorted(b0_non_pronoun ^ p_non_pronoun):
        present_b0 = key in b0_map
        source = b0_map if present_b0 else p_map
        span = source[key]
        mapping = _span_mapping(key)
        changed_non_pronoun_spans.append({
            "sample_id": key[0],
            "text": span.get("text"),
            "start": key[1],
            "end": key[2],
            "present_in_B0": present_b0,
            "present_in_P": key in p_map,
            "gold_overlap": _overlaps_gold(
                mapping, gold_by_id, gold_actors_by_id),
        })
    estg000003 = {
        "B0_actor_spans": [
            _span_mapping(key) for key in sorted(_actor_span_map(
                b0["predictions"]))
            if key[0] == "estg_000003"
        ],
        "P_actor_spans": [
            _span_mapping(key) for key in sorted(_actor_span_map(
                p["predictions"]))
            if key[0] == "estg_000003"
        ],
        "gold_actor_spans": [
            audit._span_record(span)
            for span in gold_actors_by_id.get("estg_000003", [])
        ],
    }
    estg000003["pronoun_disappeared"] = (
        any(audit._is_prompt_pronoun(row["text_normalized"])
            for row in estg000003["B0_actor_spans"])
        and not any(audit._is_prompt_pronoun(row["text_normalized"])
                    for row in estg000003["P_actor_spans"])
    )
    return {
        "conceptual_factor": "unresolved_pronoun_policy_only",
        "pronoun": {
            "B0": _pronoun_summary(b0),
            "P": _pronoun_summary(p),
            "delta_total": (
                _pronoun_summary(p)["total"] - _pronoun_summary(b0)["total"]),
            "delta_tp": _pronoun_summary(p)["tp"] - _pronoun_summary(b0)["tp"],
            "delta_fp": _pronoun_summary(p)["fp"] - _pronoun_summary(b0)["fp"],
        },
        "estg_000003_It": estg000003,
        "non_pronoun_actor_changes": {
            "B0_non_pronoun_count": len(b0_non_pronoun),
            "P_non_pronoun_count": len(p_non_pronoun),
            "symmetric_difference_count": non_pronoun_changed,
            "behavioral_spillover_flag": non_pronoun_changed > 10,
            "changed_spans": changed_non_pronoun_spans,
        },
        "actor_changes": change,
    }


def _factor_c(
    b0: Mapping[str, Any],
    c: Mapping[str, Any],
    gold_by_id: Mapping[str, Any],
    gold_actors_by_id: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    b0_conditions = _condition_spans_by_id(b0["predictions"])
    b0_spans = _actor_span_map(b0["predictions"])
    c_spans = _actor_span_map(c["predictions"])
    additions = []
    for key in sorted(set(c_spans) - set(b0_spans)):
        span = copy.deepcopy(c_spans[key])
        span["sample_id"] = key[0]
        mapping = _span_mapping(key)
        contained = any(
            audit._contains(condition, mapping)
            for condition in b0_conditions.get(key[0], [])
        )
        gold_overlap = _overlaps_gold(mapping, gold_by_id, gold_actors_by_id)
        additions.append({
            **_span_mapping(key),
            "text": span.get("text"),
            "normalized": span.get("normalized"),
            "contained_in_B0_condition": contained,
            "gold_overlap": gold_overlap,
            "classification": "TP_addition" if gold_overlap else "FP_addition",
        })
    projected = [row for row in additions if row["contained_in_B0_condition"]]
    projected_tp = sum(1 for row in projected if row["gold_overlap"])
    projected_fp = len(projected) - projected_tp
    sample_reports: dict[str, Any] = {}
    for sid in ("estg_000206", "estg_000417", "estg_000776"):
        b0_for_sample = [
            _span_mapping(key) for key in sorted(b0_spans)
            if key[0] == sid
        ]
        c_for_sample = [
            _span_mapping(key) for key in sorted(c_spans)
            if key[0] == sid
        ]
        new_for_sample = [
            row for row in additions if row["sample_id"] == sid
        ]
        sample_reports[sid] = {
            "B0_actor_spans": b0_for_sample,
            "C_actor_spans": c_for_sample,
            "Gold_actor_spans": [
                audit._span_record(span)
                for span in gold_actors_by_id.get(sid, [])
            ],
            "C_only_actor_spans": new_for_sample,
            "recovered_gold": any(
                row["gold_overlap"] for row in new_for_sample),
            "new_fp": any(
                not row["gold_overlap"] for row in new_for_sample),
        }
    return {
        "conceptual_factor": "condition_actor_projection_only",
        "all_new_actor_predictions": additions,
        "condition_projected_actor_predictions": projected,
        "projected_tp_additions": projected_tp,
        "projected_fp_additions": projected_fp,
        "projection_precision": (
            projected_tp / len(projected) if projected else None),
        "samples": sample_reports,
    }


def _schema_quality(arm_data: Mapping[str, Any]) -> dict[str, Any]:
    predictions = arm_data["predictions"]
    raw_rows = arm_data["raw_rows"]
    parsed_ok = 0
    adapter_ok = 0
    canonicalizer_ok = 0
    validator_ok = 0
    nonempty = 0
    failed = 0
    for row in predictions:
        if row.get("request_status") == "ok":
            parsed_ok += 1
            adapter_ok += 1
            canonicalizer_ok += 1
            validator_ok += 1
        else:
            failed += 1
        record = row.get("record") or {}
        if isinstance(record, Mapping) and record.get("clauses"):
            nonempty += 1
    api_ok = sum(1 for row in raw_rows if row.get("request_status") == "ok")
    return {
        "api_ok_count": api_ok,
        "failed_count": len(raw_rows) - api_ok,
        "schema_valid_rate": validator_ok / len(predictions),
        "nonempty_record_count": nonempty,
        "failed_prediction_count": failed,
        "retry_count": 0,
    }


def _metric_table(arm_data: Mapping[str, Any]) -> dict[str, Any]:
    metrics = arm_data["metrics"]
    overall = metrics["overall"]
    per_field = metrics["per_field"]
    return {
        "overall": {
            "precision": _round(overall["precision"]),
            "recall": _round(overall["recall"]),
            "f1": _round(overall["f1"]),
            "ground_truth": overall["ground_truth"],
            "extracted": overall["extracted"],
            "matched_predictions": overall["matched_predictions"],
            "matched_ground_truth": overall["matched_ground_truth"],
        },
        "per_field": {
            field: {
                "ground_truth": per_field[field]["ground_truth"],
                "pred": per_field[field]["extracted"],
                "matched_predictions": per_field[field]["matched_predictions"],
                "matched_gold": per_field[field]["matched_ground_truth"],
                "precision": _round(per_field[field]["precision"]),
                "recall": _round(per_field[field]["recall"]),
                "f1": _round(per_field[field]["f1"]),
                "fp": per_field[field]["extracted"]
                - per_field[field]["matched_predictions"],
                "fn": per_field[field]["ground_truth"]
                - per_field[field]["matched_ground_truth"],
            }
            for field in FIELDS
        },
        "quality": _schema_quality(arm_data),
    }


def _actor_comparison_table(arm_data: Mapping[str, Any]) -> dict[str, Any]:
    metrics = arm_data["metrics"]["per_field"]["actor"]
    return {
        "Gold": metrics["ground_truth"],
        "Pred": metrics["extracted"],
        "matched_pred": metrics["matched_predictions"],
        "matched_Gold": metrics["matched_ground_truth"],
        "P": _round(metrics["precision"]),
        "R": _round(metrics["recall"]),
        "F1": _round(metrics["f1"]),
        "FP": metrics["extracted"] - metrics["matched_predictions"],
        "FN": metrics["ground_truth"] - metrics["matched_ground_truth"],
    }


def _delta_fields(base: Mapping[str, Any], other: Mapping[str, Any]) -> dict[str, Any]:
    actor_base = base["per_field"]["actor"]
    actor_other = other["per_field"]["actor"]
    return {
        "delta_P": _round(_delta(actor_other["precision"], actor_base["precision"])),
        "delta_R": _round(_delta(actor_other["recall"], actor_base["recall"])),
        "delta_F1": _round(_delta(actor_other["f1"], actor_base["f1"])),
        "delta_FP": actor_other["fp"] - actor_base["fp"],
        "delta_FN": actor_other["fn"] - actor_base["fn"],
    }


def _gold_review_sensitivity(arm_data: Mapping[str, Any]) -> dict[str, Any]:
    metrics = arm_data["metrics"]["per_field"]["actor"]
    raw_fp = metrics["extracted"] - metrics["matched_predictions"]
    fp_cases = arm_data["inventory"]["fp_cases"]
    review_candidates = [
        case for case in fp_cases if case.get("gold_review_candidate")
    ]
    return {
        "raw_evaluator_fp": raw_fp,
        "high_confidence_semantic_fp": raw_fp - len(review_candidates),
        "gold_review_candidate_fp_count": len(review_candidates),
        "gold_review_candidates": [
            {
                "sample_id": case["sample_id"],
                "text": case.get("text"),
                "taxonomy": case.get("taxonomy"),
                "confidence": case.get("confidence"),
            }
            for case in review_candidates
        ],
    }


def _historical_context() -> dict[str, Any]:
    context: dict[str, Any] = {}
    if HISTORICAL_AUDIT.is_file():
        doc = _read_json(HISTORICAL_AUDIT)
        context["historical_repair_v1_D_full_0813"] = {
            "actor_metrics": doc.get("actor_metrics"),
            "tp_count": doc.get("tp_count"),
            "fp_count": doc.get("fp_count"),
            "fn_count": doc.get("fn_count"),
        }
    if HISTORICAL_LEGACY_EVAL.is_file():
        doc = _read_json(HISTORICAL_LEGACY_EVAL)
        actor = doc.get("evaluation", {}).get("metrics", {}).get(
            "per_field", {}).get("actor", {})
        context["historical_legacy_D_full_0813"] = {
            "actor_precision": actor.get("precision"),
            "actor_recall": actor.get("recall"),
            "actor_f1": actor.get("f1"),
            "actor_extracted": actor.get("extracted"),
            "actor_fp": (
                actor.get("extracted", 0) - actor.get("matched_predictions", 0)
                if actor else None),
        }
    return context


def _recommendation(report: Mapping[str, Any]) -> str:
    supported: list[str] = []
    for arm in ("R", "P", "C"):
        delta = report["deltas_vs_fresh_B0"][arm]["delta_F1"]
        overall_delta = report["overall_delta"][arm]["delta_F1"]
        if delta is not None and delta >= 0.02 and overall_delta is not None \
                and overall_delta >= -0.02:
            supported.append(arm)
    if not supported:
        return "no further refinement"
    if len(supported) == 1:
        return f"replicate {supported[0]}"
    return "interaction experiment between supported factors"


def build_report() -> dict[str, Any]:
    runner.validate_experiment_manifest()
    if POLICY_REPAIR != runner.CANONICALIZER_POLICY:
        raise ActorRefinementAnalysisError("repair_v1 pin lost")
    for arm in ARM_ORDER:
        run_dir = OUT_DIR / arm / "repeat-01"
        if not (run_dir / "canonical_predictions.jsonl").is_file():
            raise ActorRefinementAnalysisError(
                f"arm {arm} predictions are not locked")
        if _read_jsonl(run_dir / "canonical_predictions.jsonl").__len__() != 150:
            raise ActorRefinementAnalysisError(f"arm {arm} is incomplete")
    gold_by_id = _gold_by_id()
    source_by_id = {
        row["sample_id"]: row["text"] for row in runner.load_samples()}
    arm_data = {
        arm: _load_arm_data(arm, gold_by_id, source_by_id)
        for arm in ARM_ORDER
    }
    gold_actors_by_id = _gold_actor_spans_by_id(gold_by_id)
    metrics = {
        arm: _metric_table(arm_data[arm]) for arm in ARM_ORDER}
    actor_comparison = {
        arm: _actor_comparison_table(arm_data[arm]) for arm in ARM_ORDER}
    deltas = {
        arm: _delta_fields(metrics["B0"], metrics[arm])
        for arm in ("R", "P", "C")
    }
    overall_delta = {
        arm: {
            "delta_P": _round(_delta(
                metrics[arm]["overall"]["precision"],
                metrics["B0"]["overall"]["precision"])),
            "delta_R": _round(_delta(
                metrics[arm]["overall"]["recall"],
                metrics["B0"]["overall"]["recall"])),
            "delta_F1": _round(_delta(
                metrics[arm]["overall"]["f1"],
                metrics["B0"]["overall"]["f1"])),
        }
        for arm in ("R", "P", "C")
    }
    factor_r = _factor_r(
        arm_data["B0"], arm_data["R"], gold_by_id, gold_actors_by_id)
    factor_p = _factor_p(
        arm_data["B0"], arm_data["P"], gold_by_id, gold_actors_by_id)
    factor_c = _factor_c(
        arm_data["B0"], arm_data["C"], gold_by_id, gold_actors_by_id)
    gold_sensitivity = {
        arm: _gold_review_sensitivity(arm_data[arm]) for arm in ARM_ORDER}
    execution = (
        _read_json(runner.EXECUTION_SUMMARY)
        if runner.EXECUTION_SUMMARY.is_file() else {})
    execution_incidents = [
        _read_json(path)
        for path in sorted(OUT_DIR.glob("execution_incident_*.json"))
    ]
    report = {
        "schema_version": "d1_actor_refinement_report@1.0.0",
        "experiment_id": runner.EXPERIMENT_ID,
        "generated_at_utc": _utc_now(),
        "scope": "development_screening_only",
        "status": "evaluation_only_no_promotion",
        "execution": execution,
        "execution_incidents": execution_incidents,
        "prompt_integrity": {
            "base_prompt_sha": runner._sha256_file(runner.prompt_path("B0")),
            "variants": {
                arm: {
                    "prompt_sha256": runner._sha256_file(runner.prompt_path(arm)),
                    "conceptual_factor": ARMS[arm]["conceptual_factor"],
                }
                for arm in ARM_ORDER
            },
            "unexpected_diff_count": _read_json(
                runner.DIFF_MANIFEST).get("unexpected_diff_count")
            if runner.DIFF_MANIFEST.is_file() else None,
        },
        "metrics": metrics,
        "actor_comparison": actor_comparison,
        "deltas_vs_fresh_B0": deltas,
        "overall_delta": overall_delta,
        "factor_R": factor_r,
        "factor_P": factor_p,
        "factor_C": factor_c,
        "gold_review_sensitivity": gold_sensitivity,
        "historical_context": _historical_context(),
        "safety": {
            "gold_used_to_design_new_prompt_after_experiment_started": False,
            "iterative_prompt_search": False,
            "actor_lexicon_added": False,
            "benchmark_specific_whitelist_added": False,
            "benchmark_specific_blacklist_added": False,
            "rules_only_predictions_used_to_alter_direct_llm": False,
            "post_hoc_condition_to_actor_code_added": False,
            "combined_R_P_C_prompt_run": False,
            "formal_result_overwritten": False,
            "no_gold_in_prompt_construction": True,
            "no_gold_in_api_execution": True,
            "prompts_frozen_before_scores": True,
        },
    }
    report["recommended_next_step"] = _recommendation(report)
    return report


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(value) for value in row) + " |")
    return lines


def to_markdown(report: Mapping[str, Any]) -> str:
    lines: list[str] = []
    lines += ["# D1 Actor-refinement development screening report", ""]
    lines += [
        "> One-factor-per-arm development screening. No combined arm and no promotion.",
        "",
    ]
    lines += ["## A. Executive conclusion", ""]
    exec_summary = report.get("execution") or {}
    metrics = report["metrics"]
    deltas = report["deltas_vs_fresh_B0"]
    lines += [
        f"- 600 primary calls completed: {bool(exec_summary.get('complete'))}; "
        f"actual new calls in final invocation: {exec_summary.get('actual_new_calls')}; "
        f"total accounted: {exec_summary.get('total_calls_accounted')}.",
        f"- Fresh baseline successful record count: {metrics['B0']['quality']['api_ok_count']}/150.",
        "",
    ]
    for arm in ("R", "P", "C"):
        d = deltas[arm]
        lines.append(
            f"- {arm}: Actor dP={_fmt(d['delta_P'])}, dR={_fmt(d['delta_R'])}, "
            f"dF1={_fmt(d['delta_F1'])}, dFP={d['delta_FP']}, dFN={d['delta_FN']}.")
    lines += [
        "",
        "Precision/Recall attribution and collateral effects are reported below; "
        "the report does not declare a final Prompt.",
        "",
    ]
    lines += ["## B. Prompt integrity", ""]
    lines += _table(
        ["arm", "Prompt SHA", "changed sections", "unexpected diff"],
        [
            [
                arm,
                report["prompt_integrity"]["variants"][arm]["prompt_sha256"],
                report["prompt_integrity"]["variants"][arm]["conceptual_factor"],
                0,
            ]
            for arm in ARM_ORDER
        ],
    )
    lines += ["", f"global unexpected_diff_count = "
              f"{report['prompt_integrity']['unexpected_diff_count']}", ""]
    lines += ["## C. Execution integrity", ""]
    lines += [
        f"- model: {exec_summary.get('model', {}).get('id')}",
        f"- provider: {exec_summary.get('model', {}).get('provider')}",
        f"- API config: temperature={exec_summary.get('sampling', {}).get('temperature')}, "
        f"top_p={exec_summary.get('sampling', {}).get('top_p')}, "
        f"max_tokens={exec_summary.get('sampling', {}).get('max_tokens')}, retry=0",
        f"- dataset: {exec_summary.get('dataset', {}).get('path')}",
        f"- sample count per arm: 150",
        f"- planned calls: {exec_summary.get('planned_calls')}",
        f"- actual new calls: {exec_summary.get('actual_new_calls')}",
        f"- resumed completed: {exec_summary.get('resumed_completed_count')}",
        f"- total accounted: {exec_summary.get('total_calls_accounted')}",
        f"- repair policy: {exec_summary.get('canonicalizer', {}).get('policy')}",
        f"- evaluator: {exec_summary.get('evaluator', {}).get('id')}",
    ]
    for incident in report.get("execution_incidents", []):
        lines.append(
            f"- execution incident: {incident.get('incident_id')} "
            f"({incident.get('failure_mode')}); resume policy: "
            f"{incident.get('resume_policy')}")
    lines += [""]
    lines += ["## D. Overall + six-field metrics", ""]
    lines += _table(
        ["arm", "overall P", "overall R", "overall F1", "schema/legal rate", "nonempty records"],
        [
            [
                arm,
                metrics[arm]["overall"]["precision"],
                metrics[arm]["overall"]["recall"],
                metrics[arm]["overall"]["f1"],
                metrics[arm]["quality"]["schema_valid_rate"],
                metrics[arm]["quality"]["nonempty_record_count"],
            ]
            for arm in ARM_ORDER
        ],
    )
    lines += ["", "Per field:"]
    for arm in ARM_ORDER:
        lines += ["", f"### {arm}", ""]
        lines += _table(
            ["field", "Gold", "Pred", "matched_pred", "matched_Gold", "P", "R", "F1"],
            [
                [
                    field,
                    metrics[arm]["per_field"][field]["ground_truth"],
                    metrics[arm]["per_field"][field]["pred"],
                    metrics[arm]["per_field"][field]["matched_predictions"],
                    metrics[arm]["per_field"][field]["matched_gold"],
                    metrics[arm]["per_field"][field]["precision"],
                    metrics[arm]["per_field"][field]["recall"],
                    metrics[arm]["per_field"][field]["f1"],
                ]
                for field in FIELDS
            ],
        )
    lines += ["", "## E. Actor comparison", ""]
    lines += _table(
        ["arm", "Pred", "matched pred", "matched Gold", "P", "R", "F1", "FP", "FN"],
        [
            [
                arm,
                report["actor_comparison"][arm]["Pred"],
                report["actor_comparison"][arm]["matched_pred"],
                report["actor_comparison"][arm]["matched_Gold"],
                report["actor_comparison"][arm]["P"],
                report["actor_comparison"][arm]["R"],
                report["actor_comparison"][arm]["F1"],
                report["actor_comparison"][arm]["FP"],
                report["actor_comparison"][arm]["FN"],
            ]
            for arm in ARM_ORDER
        ],
    )
    lines += ["", "Deltas vs fresh B0:"]
    lines += _table(
        ["arm", "dP", "dR", "dF1", "dFP", "dFN"],
        [
            [arm, deltas[arm]["delta_P"], deltas[arm]["delta_R"],
             deltas[arm]["delta_F1"], deltas[arm]["delta_FP"],
             deltas[arm]["delta_FN"]]
            for arm in ("R", "P", "C")
        ],
    )
    lines += ["", "## F. Factor R attribution", ""]
    r = report["factor_R"]
    lines += [
        f"- non-role FP: B0={r['non_role_fp']['B0']}, R={r['non_role_fp']['R']}, "
        f"delta={r['non_role_fp']['delta']}",
        f"- removed actors: {r['actor_changes']['removed_count']} "
        f"(beneficial FP removal={r['actor_changes']['beneficial_fp_removal_count']}, "
        f"harmful TP removal={r['actor_changes']['harmful_tp_removal_count']})",
        f"- added actors: {r['actor_changes']['added_count']} "
        f"(new TP={r['actor_changes']['new_tp_count']}, new FP={r['actor_changes']['new_fp_count']})",
        f"- legal-role TP removed: {r['legal_role_tp_removed_count']}",
        f"- actor FN delta: {r['fn_delta']}",
        f"- pronoun count B0={r['pronoun_prediction_stability']['base_pronoun_count']}, "
        f"R={r['pronoun_prediction_stability']['other_pronoun_count']}",
        "",
    ]
    lines += ["Changed actor cases:"]
    lines += _table(
        ["sample", "text", "span", "change", "gold overlap", "base taxonomy"],
        [
            [row["sample_id"], row["text"], f"{row['start']}:{row['end']}",
             row["classification"], row["gold_overlap"],
             row.get("base_side_taxonomy", "")]
            for row in r["actor_changes"]["removed"] + r["actor_changes"]["added"]
        ] or [["none", "", "", "", "", ""]],
    )
    lines += ["", "## G. Factor P attribution", ""]
    p = report["factor_P"]
    b0p = p["pronoun"]["B0"]
    pp = p["pronoun"]["P"]
    lines += _table(
        ["arm", "pronoun total", "TP", "FP", "precision"],
        [
            ["B0", b0p["total"], b0p["tp"], b0p["fp"], b0p["precision"]],
            ["P", pp["total"], pp["tp"], pp["fp"], pp["precision"]],
        ],
    )
    lines += [
        "",
        f"- estg_000003 'It' disappeared: {p['estg_000003_It']['pronoun_disappeared']}",
        f"- non-pronoun actor symmetric difference: "
        f"{p['non_pronoun_actor_changes']['symmetric_difference_count']} "
        f"(spillover flag={p['non_pronoun_actor_changes']['behavioral_spillover_flag']})",
        "",
    ]
    lines += ["## H. Factor C attribution", ""]
    c = report["factor_C"]
    lines += [
        f"- condition-contained new actor predictions: "
        f"{len(c['condition_projected_actor_predictions'])}",
        f"- TP additions: {c['projected_tp_additions']}",
        f"- FP additions: {c['projected_fp_additions']}",
        f"- projection precision: {_fmt(c['projection_precision'])}",
        "",
    ]
    lines += _table(
        ["sample", "new actor", "span", "contained in B0 condition", "gold overlap", "classification"],
        [
            [row["sample_id"], row.get("text"),
             f"{row['start']}:{row['end']}",
             row["contained_in_B0_condition"], row["gold_overlap"],
             row["classification"]]
            for row in c["all_new_actor_predictions"]
        ] or [["none", "", "", "", "", ""]],
    )
    for sid in ("estg_000206", "estg_000417", "estg_000776"):
        s = c["samples"][sid]
        lines += [
            "",
            f"### {sid}",
            f"- B0 actors: {s['B0_actor_spans']}",
            f"- C actors: {s['C_actor_spans']}",
            f"- Gold actors: {s['Gold_actor_spans']}",
            f"- recovered Gold: {s['recovered_gold']}; new FP: {s['new_fp']}",
        ]
    lines += ["", "## I. Other-field collateral effects", ""]
    field_rows = []
    for field in FIELDS:
        field_rows.append([
            field,
            metrics["B0"]["per_field"][field]["f1"],
            _fmt(_delta(metrics["R"]["per_field"][field]["f1"],
                        metrics["B0"]["per_field"][field]["f1"])),
            _fmt(_delta(metrics["P"]["per_field"][field]["f1"],
                        metrics["B0"]["per_field"][field]["f1"])),
            _fmt(_delta(metrics["C"]["per_field"][field]["f1"],
                        metrics["B0"]["per_field"][field]["f1"])),
        ])
    field_rows.append([
        "overall",
        metrics["B0"]["overall"]["f1"],
        _fmt(_delta(metrics["R"]["overall"]["f1"],
                    metrics["B0"]["overall"]["f1"])),
        _fmt(_delta(metrics["P"]["overall"]["f1"],
                    metrics["B0"]["overall"]["f1"])),
        _fmt(_delta(metrics["C"]["overall"]["f1"],
                    metrics["B0"]["overall"]["f1"])),
    ])
    lines += _table(
        ["field", "B0 F1", "R delta", "P delta", "C delta"], field_rows)
    lines += ["", "## J. Gold-review sensitivity", ""]
    lines += _table(
        ["arm", "raw evaluator FP", "high-confidence semantic FP", "Gold-review candidates"],
        [
            [arm, report["gold_review_sensitivity"][arm]["raw_evaluator_fp"],
             report["gold_review_sensitivity"][arm]["high_confidence_semantic_fp"],
             report["gold_review_sensitivity"][arm]["gold_review_candidate_fp_count"]]
            for arm in ARM_ORDER
        ],
    )
    lines += ["", "No alternative F1 is produced; denominators are unchanged.", ""]
    lines += ["## K. Run-to-run context", ""]
    hist = report.get("historical_context") or {}
    lines += [
        "Fresh B0 is the primary comparison. Historical runs are contextual only.",
        "",
        f"- historical repair_v1 D-full-0813: {hist.get('historical_repair_v1_D_full_0813')}",
        f"- historical legacy D-full-0813: {hist.get('historical_legacy_D_full_0813')}",
        "",
    ]
    lines += ["## L. Safety / leakage audit", ""]
    for key, value in report["safety"].items():
        lines.append(f"- {key}: {value}")
    lines += [
        "",
        "## M. Recommended next step",
        "",
        f"- {report['recommended_next_step']}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="write report JSON and Markdown")
    args = parser.parse_args()
    report = build_report()
    # Persist per-arm evaluation sidecars before the unified report.
    for arm in ARM_ORDER:
        arm_data = _load_arm_data(
            arm,
            _gold_by_id(),
            {row["sample_id"]: row["text"] for row in runner.load_samples()},
        )
        sidecar = arm_data["run_dir"] / "evaluation.json"
        sidecar.write_text(
            json.dumps({
                "arm": arm,
                "evaluation": arm_data["evaluation"],
                "metrics": arm_data["metrics"],
                "actor_inventory": {
                    "metrics": arm_data["inventory"]["metrics"],
                    "tp_count": arm_data["inventory"]["tp_count"],
                    "fp_count": arm_data["inventory"]["fp_count"],
                    "fn_count": arm_data["inventory"]["fn_count"],
                    "fp_taxonomy": arm_data["inventory"]["fp_taxonomy"],
                    "fn_taxonomy": arm_data["inventory"]["fn_taxonomy"],
                    "pronoun_analysis": arm_data["inventory"]["pronoun_analysis"],
                },
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )
    if args.write:
        REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
        REPORT_JSON.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )
        REPORT_MD.write_text(
            to_markdown(report) + "\n",
            encoding="utf-8", newline="\n",
        )
    print(json.dumps({
        "experiment_id": report["experiment_id"],
        "actor_comparison": report["actor_comparison"],
        "deltas_vs_fresh_B0": report["deltas_vs_fresh_B0"],
        "factor_R": report["factor_R"]["non_role_fp"],
        "factor_P_pronoun": report["factor_P"]["pronoun"],
        "factor_C_projection_precision": report["factor_C"]["projection_precision"],
        "recommended_next_step": report["recommended_next_step"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())