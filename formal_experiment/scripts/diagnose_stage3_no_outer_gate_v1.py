# -*- coding: utf-8 -*-
"""Diagnostic only: isolate the v3 outer gate from the Def5-7 checker.

This runner is intentionally *not* a formal method or evaluator.  It reads the
already-persisted Table 3 v3 predictions (Definition 4 matching only), then
replays exactly the same Def5-7 signal code with one change:

* current v3: only matching rows with ``matching_score > tau`` enter Def5-7;
* this counterfactual: every one of the 9 matching rows enters Def5-7.

All other inputs and settings are reused unchanged: the same v3 BPMN view, the
same persisted Stage-2-derived per-method rule records, the same SunScorer
instance and spaCy backend, and the same frozen tau/gamma/theta = 0.8.

The target rule id is read from the evaluator-only case map *after* the v3
predictions and rule records are loaded.  It is used solely for diagnostic
breakdown and evaluation; it is never fed back into Definition 4 or any formal
inference path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
)
from bpc_hybrid.stage3_sun_style_checker import (  # noqa: E402
    TYPES,
    normalize_sun_signal,
)
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

DEFAULT_VIEW = (
    ROOT / "data/development/stage3_synth/stage3_sun_style_inference_view_v3.json"
)
DEFAULT_CASE_MAP = (
    ROOT / "data/development/stage3_synth/stage3_sun_style_case_map_v3.json"
)
DEFAULT_STAGE2_INPUT = ROOT / "data/input/gdpr7_stage2_input_v1.json"
DEFAULT_TEXT_VIEW = (
    ROOT / "data/development/stage3_synth/stage3_regulation_text_view_v2.json"
)
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
SUN_CONFIG = ROOT / "configs/sun_stage3_development_v1.json"
DEFAULT_V3_DIR = ROOT / "outputs/development/stage3_table3_v3"
DEFAULT_OUT_JSON = ROOT / "outputs/reports/diagnose_stage3_no_outer_gate_v1.json"
DEFAULT_OUT_MD = ROOT / "outputs/reports/diagnose_stage3_no_outer_gate_v1.md"

METHODS: dict[str, dict[str, str]] = {
    "sun_rules_only_full_sun_stage3": {
        "label": "Sun",
        "rule_records_file": "rule_records_sun_rules_only_full_sun_stage3.json",
    },
    "ours_direct_llm_full_sun_stage3": {
        "label": "Ours",
        "rule_records_file": "rule_records_ours_direct_llm_full_sun_stage3.json",
    },
}
SCHEMA_VERSION = "stage3_no_outer_gate_diagnostic@1.0.0"
RULE_BASE_SIZE = 9


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _binary(tp: int, fp: int, fn: int, tn: int) -> dict[str, Any]:
    positive = tp + fn
    negative = fp + tn
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / positive if positive else None
    if positive <= 0:
        f1 = None
    elif precision is None and recall == 0:
        f1 = 0.0
    elif precision is None or recall is None:
        f1 = None
    else:
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) else 0.0)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "positive_count": positive,
        "negative_count": negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "precision_conservative": precision if precision is not None else 0.0,
        "recall_conservative": recall if recall is not None else 0.0,
        "f1_conservative": f1 if f1 is not None else 0.0,
    }


def _signals_for_record(
    scorer: SunScorer,
    model: Any,
    record: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Mirror the Def5-7 signal block inside SunStyleChecker.check.

    This function intentionally contains no gate.  The surrounding diagnostic
    decides which rules are passed to it; the formal checker is not modified.
    """
    if record.get("failed"):
        return {
            check_type: {
                "status": "unknown",
                "raw_score": None,
                "denominator": 0,
                "observable": False,
                "reason": "stage2_rule_record_failed",
                "evidence": {
                    "failure_reasons": list(record.get("failure_reasons") or [])
                },
            }
            for check_type in TYPES
        }

    raw_missing = scorer.missing_action(
        list(record.get("actions") or []), model)
    raw_actor = scorer.incorrect_actor(
        list(record.get("actions") or []),
        list(record.get("actors") or []),
        model,
        list(record.get("actor_action_pairs") or []),
    )
    raw_order = scorer.out_of_order(
        list(record.get("order_relations") or []),
        list(record.get("actions") or []),
        model,
    )
    return {
        "missing_action": normalize_sun_signal("missing_action", raw_missing),
        "incorrect_actor": normalize_sun_signal("incorrect_actor", raw_actor),
        "out_of_order": normalize_sun_signal("out_of_order", raw_order),
    }


def _check_without_outer_gate(
    *,
    scorer: SunScorer,
    model: Any,
    rule_records: Mapping[str, Mapping[str, Any]],
    matching_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Replay Def5-7 on all persisted Def4 matching rows.

    The formal checker loops the same rows but skips ``row['relevant'] ==
    False``.  This diagnostic omits only that skip.  Definition 4 itself is not
    recomputed; the exact persisted v3 matching rows are reused.
    """
    matching_rule_ids = [str(row["rule_id"]) for row in matching_rows]
    if set(matching_rule_ids) != set(map(str, rule_records)):
        raise ValueError(
            "persisted matching rows and rule records do not cover the same rules"
        )
    for row in matching_rows:
        score = float(row.get("matching_score") or 0.0)
        if bool(row.get("relevant")) != (score > scorer.tau):
            raise ValueError(
                "persisted relevance does not match the frozen tau in "
                f"rule {row.get('rule_id')!r}"
            )

    signals_by_rule: dict[str, dict[str, Any]] = {}
    violations: list[dict[str, Any]] = []
    for row in matching_rows:
        rule_id = str(row["rule_id"])
        record = rule_records[rule_id]
        signals = _signals_for_record(scorer, model, record)
        signals_by_rule[rule_id] = signals
        for check_type in TYPES:
            signal = signals[check_type]
            if signal.get("status") != "violated":
                continue
            violations.append({
                "rule_id": rule_id,
                "violation_type": check_type,
                "raw_score": signal.get("raw_score"),
                "denominator": signal.get("denominator"),
                "observable": bool(signal.get("observable")),
                "reason": signal.get("reason"),
            })

    return {
        "entered_rule_ids": matching_rule_ids,
        "signals_by_rule": signals_by_rule,
        "violations": violations,
        "violated_types": sorted({str(v["violation_type"]) for v in violations}),
    }


def _has_violation(
    row_or_payload: Mapping[str, Any] | None, rule_id: str, violation_type: str
) -> bool:
    if not row_or_payload:
        return False
    for violation in row_or_payload.get("violations") or []:
        if (str(violation.get("rule_id")) == rule_id
                and str(violation.get("violation_type")) == violation_type):
            return True
    return False


def _summary_from_variant_entries(entries: list[dict[str, Any]],
                                  tau: float) -> dict[str, Any]:
    scores = [float(e["matching_score"]) for e in entries]
    ranks = [int(e["rank"]) for e in entries]
    return {
        "target_rule_count": len(entries),
        "rank_1_count": sum(1 for r in ranks if r == 1),
        "rank_le_3_count": sum(1 for r in ranks if r <= 3),
        "rank_le_5_count": sum(1 for r in ranks if r <= 5),
        "matching_score_gt_tau_count": sum(
            1 for s in scores if s > tau),
        "matching_score_le_tau_count": sum(
            1 for s in scores if s <= tau),
        "current_v3_entered_def57_count": sum(
            1 for e in entries if e["current_v3_entered_def57"]),
        "blocked_by_outer_gate_count": sum(
            1 for e in entries if e["blocked_by_outer_gate"]),
        "matching_score": {
            "min": min(scores),
            "median": statistics.median(scores),
            "mean": statistics.mean(scores),
            "max": max(scores),
        },
        "rank": {
            "min": min(ranks),
            "median": statistics.median(ranks),
            "mean": statistics.mean(ranks),
            "max": max(ranks),
        },
    }


def _summary_no_gate(method_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, Counter] = defaultdict(Counter)
    tp = fp = fn = tn = 0
    for row in method_rows:
        target_type = str(row["target_violation_type"])
        v = row["variant"]
        c = row["control"]
        v_hit = bool(v["no_gate_emits_target"])
        c_hit = bool(c["no_gate_emits_target"])
        tp += int(v_hit)
        fn += int(not v_hit)
        fp += int(c_hit)
        tn += int(not c_hit)
        by_type[target_type].update({
            "variant_emits": int(v_hit),
            "control_emits": int(c_hit),
            "variant_second_layer_failure": int(v["second_layer_failure"]),
            "control_second_layer_failure": int(c["second_layer_failure"]),
        })
    return {
        "overall": _binary(tp, fp, fn, tn),
        "per_type": {
            key: dict(value) for key, value in sorted(by_type.items())
        },
        "entered_def57_count": sum(
            1 for row in method_rows
            if row["variant"]["no_gate_entered_def57"]),
        "variant_target_violation_count": tp,
        "control_target_violation_count": fp,
        "variant_second_layer_failure_count": sum(
            1 for row in method_rows if row["variant"]["second_layer_failure"]),
        "control_second_layer_failure_count": sum(
            1 for row in method_rows if row["control"]["second_layer_failure"]),
    }


def _current_summary(method_rows: list[dict[str, Any]]) -> dict[str, Any]:
    tp = fp = fn = tn = 0
    for row in method_rows:
        v_hit = bool(row["variant"]["current_v3_emits_target"])
        c_hit = bool(row["control"]["current_v3_emits_target"])
        tp += int(v_hit)
        fn += int(not v_hit)
        fp += int(c_hit)
        tn += int(not c_hit)
    return _binary(tp, fp, fn, tn)


def _compact_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": record.get("rule_id"),
        "modality": record.get("modality"),
        "failed": record.get("failed"),
        "failure_reasons": list(record.get("failure_reasons") or []),
        "action_count": len(record.get("actions") or []),
        "actor_count": len(record.get("actors") or []),
        "actor_action_pair_count": len(record.get("actor_action_pairs") or []),
        "order_relation_count": len(record.get("order_relations") or []),
        "actions_preview": list(record.get("actions") or [])[:3],
        "actors_preview": list(record.get("actors") or [])[:3],
    }


def evaluate(*, v3_dir: Path, view_path: Path, case_map_path: Path,
             stage2_input_path: Path, text_view_path: Path,
             nlp_model: str) -> dict[str, Any]:
    view = _load_json(view_path)
    if view.get("safety", {}).get("gold_labels_present") is not False:
        raise ValueError("v3 inference view is not declared Gold-blind")
    if view.get("safety", {}).get("rule_id_present") is not False:
        raise ValueError("v3 inference view must not contain rule ids")
    items = {str(item["case_id"]): item for item in view.get("items") or []}

    case_map = _load_json(case_map_path)
    eligible_variants = [
        c for c in case_map.get("cases") or []
        if c.get("eligible") and c.get("role") == "variant"
    ]
    pairs: dict[str, dict[str, Any]] = defaultdict(dict)
    for case in case_map.get("cases") or []:
        if case.get("eligible"):
            pairs[str(case["pair_id"])][str(case["role"])] = case
    pair_ids = sorted(pairs)
    if len(pair_ids) != 13:
        raise ValueError(f"expected 13 eligible pairs, found {len(pair_ids)}")
    if len(eligible_variants) != 13:
        raise ValueError(
            f"expected 13 eligible variant cases, found {len(eligible_variants)}")

    predictions_path = v3_dir / "predictions.jsonl"
    prediction_rows = _load_jsonl(predictions_path)
    pred_index = {
        (str(row["method_id"]), str(row["case_id"])): row
        for row in prediction_rows
    }

    sun_cfg = _load_json(SUN_CONFIG)
    thresholds = sun_cfg["method"]["thresholds"]
    tau = float(thresholds["tau"])
    gamma = float(thresholds["gamma"])
    theta = float(thresholds["theta"])
    if (gamma, theta) != (0.8, 0.8) or tau != 0.8:
        raise ValueError("frozen thresholds are not tau=gamma=theta=0.8")

    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    import spacy  # type: ignore

    nlp = spacy.load(nlp_model)
    sim = WinterSimilarity(nlp)
    scorer = SunScorer(sim, tau, gamma, theta, nlp=nlp)

    rule_records_by_method: dict[str, dict[str, Any]] = {}
    record_paths: dict[str, Path] = {}
    for method_id, method in METHODS.items():
        path = v3_dir / method["rule_records_file"]
        doc = _load_json(path)
        rule_records_by_method[method_id] = {
            str(key): value for key, value in (doc.get("records") or {}).items()
        }
        record_paths[method_id] = path

    model_cache: dict[tuple[str, str], Any] = {}

    def model_for(item: Mapping[str, Any]) -> Any:
        key = (str(item["bpmn_path"]), str(item["process_id"]))
        if key not in model_cache:
            bpmn_record = parse_bpmn_file(ROOT / str(item["bpmn_path"]),
                                          contract=contract)
            model_cache[key] = SunProcessModel(
                str(item["process_id"]), bpmn_record, nlp)
        return model_cache[key]

    no_gate_cache: dict[tuple[str, str], dict[str, Any]] = {}
    replay_validation = {"relevant_rule_signal_comparisons": 0, "mismatches": 0}

    def no_gate_for(method_id: str, case_id: str) -> dict[str, Any]:
        key = (method_id, case_id)
        if key not in no_gate_cache:
            row = pred_index.get(key)
            if row is None:
                raise KeyError(f"missing v3 prediction row for {key}")
            item = items.get(case_id)
            if item is None:
                raise KeyError(f"missing inference item for {case_id}")
            matching_rows = list(row.get("matching") or [])
            if len(matching_rows) != RULE_BASE_SIZE:
                raise ValueError(
                    f"{key} has {len(matching_rows)} matching rows, "
                    f"expected {RULE_BASE_SIZE}")
            result = _check_without_outer_gate(
                scorer=scorer,
                model=model_for(item),
                rule_records=rule_records_by_method[method_id],
                matching_rows=matching_rows,
            )
            persisted_signals = row.get("signals_by_rule") or {}
            for matching_row in matching_rows:
                if not bool(matching_row.get("relevant")):
                    continue
                rule_id = str(matching_row["rule_id"])
                replay_validation["relevant_rule_signal_comparisons"] += 1
                if result["signals_by_rule"].get(rule_id) != persisted_signals.get(rule_id):
                    replay_validation["mismatches"] += 1
                    raise ValueError(
                        "replayed Def5-7 signals differ from persisted v3 "
                        f"signals for {(method_id, case_id, rule_id)}"
                    )
            no_gate_cache[key] = result
        return no_gate_cache[key]

    pair_breakdown: list[dict[str, Any]] = []
    method_rows_for_summary: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for pair_id in pair_ids:
        variant = pairs[pair_id]["variant"]
        control = pairs[pair_id]["control"]
        target_rule_id = str(variant["target_rule_id"])
        target_violation_type = str(variant["target_violation_type"])
        pair_row: dict[str, Any] = {
            "pair_id": pair_id,
            "case_id": str(variant["case_id"]),
            "control_case_id": str(control["case_id"]),
            "process_id": str(variant["process_id"]),
            "target_violation_type": target_violation_type,
            "target_rule_id": target_rule_id,
            "target_rule_id_use": "diagnostic/evaluator-only; never fed to Def4 or inference",
            "methods": {},
        }

        for method_id, method in METHODS.items():
            method_rows_for_summary[method_id].append({
                "pair_id": pair_id,
                "target_violation_type": target_violation_type,
                "target_rule_id": target_rule_id,
            })
            # The summary rows are filled below with variant/control details.
            method_summary_row = method_rows_for_summary[method_id][-1]

            target_record = rule_records_by_method[method_id][target_rule_id]
            method_payload: dict[str, Any] = {
                "paper_label": method["label"],
                "target_rule_record": target_record,
                "target_rule_record_compact": _compact_record(target_record),
                "variant": {},
                "control": {},
            }

            for role, case in (("variant", variant), ("control", control)):
                case_id = str(case["case_id"])
                row = pred_index.get((method_id, case_id))
                if row is None:
                    raise KeyError(f"missing prediction row {(method_id, case_id)}")
                matching_entry = next(
                    (entry for entry in (row.get("matching") or [])
                     if str(entry.get("rule_id")) == target_rule_id),
                    None,
                )
                if matching_entry is None:
                    raise KeyError(
                        f"target rule {target_rule_id} missing from matching in "
                        f"{(method_id, case_id)}")

                matching_score = float(matching_entry.get("matching_score") or 0.0)
                action_ratio = float(matching_entry.get("action_ratio") or 0.0)
                actor_object_ratio = float(
                    matching_entry.get("actor_object_ratio") or 0.0)
                matched_gt_tau = matching_score > tau
                entered = bool(matching_entry.get("relevant", matched_gt_tau))
                if entered != matched_gt_tau:
                    raise ValueError(
                        f"persisted relevance disagrees with tau for "
                        f"{(method_id, case_id, target_rule_id)}")
                blocked = not entered
                current_emits = _has_violation(
                    row, target_rule_id, target_violation_type)

                no_gate = no_gate_for(method_id, case_id)
                no_gate_signal = (
                    no_gate["signals_by_rule"].get(target_rule_id, {})
                    .get(target_violation_type, {})
                )
                no_gate_emits = _has_violation(
                    no_gate, target_rule_id, target_violation_type)
                second_layer_failure = bool(
                    target_rule_id in no_gate["signals_by_rule"]
                    and not no_gate_emits
                )
                payload = {
                    "rank": int(matching_entry.get("rank") or 0),
                    "rule_base_size": len(row.get("matching") or []),
                    "matching_score": matching_score,
                    "action_ratio": action_ratio,
                    "actor_object_ratio": actor_object_ratio,
                    "matching_score_gt_tau": matched_gt_tau,
                    "current_v3_entered_def57": entered,
                    "current_v3_blocked_by_outer_gate": blocked,
                    "current_v3_emits_target": current_emits,
                    "no_gate_entered_def57": bool(
                        target_rule_id in no_gate["signals_by_rule"]),
                    "no_gate_target_signal": no_gate_signal,
                    "no_gate_emits_target": no_gate_emits,
                    "second_layer_failure": second_layer_failure,
                }
                method_payload[role] = payload

                if role == "variant":
                    method_summary_row.update({
                        "rank": payload["rank"],
                        "matching_score": matching_score,
                        "action_ratio": action_ratio,
                        "actor_object_ratio": actor_object_ratio,
                        "matching_score_gt_tau": matched_gt_tau,
                        "current_v3_entered_def57": entered,
                        "blocked_by_outer_gate": blocked,
                        "current_v3_emits_target": current_emits,
                        "no_gate_entered_def57": payload["no_gate_entered_def57"],
                        "no_gate_emits_target": no_gate_emits,
                        "second_layer_failure": second_layer_failure,
                        "variant": payload,
                    })
                else:
                    method_summary_row["control"] = payload

            pair_row["methods"][method_id] = method_payload

        pair_breakdown.append(pair_row)

    current_tau = tau
    current_summary = {
        method_id: {
            **_summary_from_variant_entries(rows, current_tau),
            "target_seeded_current_v3": _current_summary(rows),
        }
        for method_id, rows in sorted(method_rows_for_summary.items())
    }
    no_gate_summary = {
        method_id: _summary_no_gate(rows)
        for method_id, rows in sorted(method_rows_for_summary.items())
    }

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "diagnostic_complete",
        "scope": (
            "13-pair target-rule diagnostic and strict no-outer-gate "
            "counterfactual for Stage 3 Table 3 v3 Sun and Ours"
        ),
        "method_labels": {
            method_id: method["label"] for method_id, method in METHODS.items()
        },
        "thresholds": {"tau": tau, "gamma": gamma, "theta": theta},
        "outer_gate_definition": "matching_score > tau (tau=0.8)",
        "counterfactual_change": (
            "Definition 4 matching rows are reused exactly as persisted by v3; "
            "the only change is that every matching row enters the unchanged "
            "Def5-7 block instead of only rows with matching_score > tau."
        ),
        "not_a_formal_method": True,
        "target_rule_id_policy": (
            "The target rule id is read from the evaluator-only case map after "
            "v3 predictions exist; it is used only for this diagnostic and is "
            "not fed into Definition 4 or formal inference."
        ),
        "inputs": {
            "v3_predictions": {
                "path": _display_path(predictions_path),
                "sha256": _sha256_file(predictions_path),
            },
            "inference_view": {
                "path": _display_path(view_path),
                "sha256": _sha256_file(view_path),
            },
            "case_map": {
                "path": _display_path(case_map_path),
                "sha256": _sha256_file(case_map_path),
            },
            "stage2_input": {
                "path": _display_path(stage2_input_path),
                "sha256": _sha256_file(stage2_input_path),
            },
            "regulation_text_view": {
                "path": _display_path(text_view_path),
                "sha256": _sha256_file(text_view_path),
            },
            "sun_config": {
                "path": _display_path(SUN_CONFIG),
                "sha256": _sha256_file(SUN_CONFIG),
            },
            "rule_records": {
                method_id: {
                    "path": _display_path(path),
                    "sha256": _sha256_file(path),
                }
                for method_id, path in sorted(record_paths.items())
            },
        },
        "replay_validation": dict(replay_validation),
        "counts": {
            "eligible_pairs": len(pair_ids),
            "by_target_violation_type": dict(Counter(
                str(pairs[pair_id]["variant"]["target_violation_type"])
                for pair_id in pair_ids
            )),
            "rule_base_size": RULE_BASE_SIZE,
        },
        "summary": {
            "current_v3": current_summary,
            "no_outer_gate_counterfactual": no_gate_summary,
        },
        "pair_breakdown": pair_breakdown,
    }
    return report


def _render_md(report: dict[str, Any]) -> str:
    labels = report["method_labels"]
    lines = [
        "# Stage 3 diagnostic: no-outer-gate counterfactual",
        "",
        f"- status: `{report['status']}`",
        f"- scope: {report['scope']}",
        f"- thresholds: tau={report['thresholds']['tau']}, "
        f"gamma={report['thresholds']['gamma']}, "
        f"theta={report['thresholds']['theta']}",
        f"- outer gate: `{report['outer_gate_definition']}`",
        f"- counterfactual change: {report['counterfactual_change']}",
        "",
        "This is a diagnostic runner, not a formal method. It reuses the exact "
        "persisted v3 Definition 4 matching rows and changes only the gate into "
        "Definitions 5-7.",
        "",
        "## A. Current v3 outer-gate summary (13 positive variants)",
        "",
        "| Method | score>0.8 | score<=0.8 | rank1 | rank<=3 | rank<=5 | entered Def5-7 | blocked |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method_id, s in report["summary"]["current_v3"].items():
        lines.append(
            f"| {labels.get(method_id, method_id)} | "
            f"{s['matching_score_gt_tau_count']} | "
            f"{s['matching_score_le_tau_count']} | "
            f"{s['rank_1_count']} | {s['rank_le_3_count']} | "
            f"{s['rank_le_5_count']} | "
            f"{s['current_v3_entered_def57_count']} | "
            f"{s['blocked_by_outer_gate_count']} |"
        )
    lines += [
        "",
        "| Method | score min | median | mean | max | rank min | median | mean | max |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method_id, s in report["summary"]["current_v3"].items():
        sc = s["matching_score"]
        rk = s["rank"]
        lines.append(
            f"| {labels.get(method_id, method_id)} | "
            f"{sc['min']:.4f} | {sc['median']:.4f} | {sc['mean']:.4f} | "
            f"{sc['max']:.4f} | {rk['min']} | {rk['median']} | "
            f"{rk['mean']:.2f} | {rk['max']} |"
        )

    lines += [
        "",
        "## B. Strict no-outer-gate counterfactual",
        "",
        "| Method | TP | FP | FN | TN | Precision | Recall | F1 | variant hits | control hits |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method_id, s in report["summary"]["no_outer_gate_counterfactual"].items():
        b = s["overall"]
        lines.append(
            f"| {labels.get(method_id, method_id)} | {b['tp']} | {b['fp']} | "
            f"{b['fn']} | {b['tn']} | {b['precision_conservative']:.4f} | "
            f"{b['recall_conservative']:.4f} | {b['f1_conservative']:.4f} | "
            f"{s['variant_target_violation_count']} | "
            f"{s['control_target_violation_count']} |"
        )
    lines += [
        "",
        "| Method | target type | variant emits | control emits | variant second-layer failure | control second-layer failure |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for method_id, s in report["summary"]["no_outer_gate_counterfactual"].items():
        for target_type, stats in s["per_type"].items():
            lines.append(
                f"| {labels.get(method_id, method_id)} | {target_type} | "
                f"{stats.get('variant_emits', 0)} | "
                f"{stats.get('control_emits', 0)} | "
                f"{stats.get('variant_second_layer_failure', 0)} | "
                f"{stats.get('control_second_layer_failure', 0)} |"
            )

    lines += [
        "",
        "## C. Per-pair target-rule breakdown (current v3)",
        "",
    ]
    for method_id, label in labels.items():
        lines += [
            f"### {label}",
            "",
            "| pair_id | case_id | process_id | type | rule_id | rank | score | action_ratio | actor_object_ratio | score>0.8 | entered Def5-7 | blocked_by_outer_gate |",
            "|---|---|---|---|---|---:|---:|---:|---:|---|---|---|",
        ]
        for pair in report["pair_breakdown"]:
            m = pair["methods"][method_id]["variant"]
            lines.append(
                f"| {pair['pair_id']} | {pair['case_id']} | {pair['process_id']} | "
                f"{pair['target_violation_type']} | {pair['target_rule_id']} | "
                f"{m['rank']} | {m['matching_score']:.4f} | "
                f"{m['action_ratio']:.4f} | {m['actor_object_ratio']:.4f} | "
                f"{str(m['matching_score_gt_tau']).lower()} | "
                f"{str(m['current_v3_entered_def57']).lower()} | "
                f"{str(m['current_v3_blocked_by_outer_gate']).lower()} |"
            )
        lines.append("")

    lines += [
        "## D. Per-pair no-gate target signal",
        "",
    ]
    for method_id, label in labels.items():
        lines += [
            f"### {label}",
            "",
            "| pair_id | role | target signal status | raw score | reason | emits target | second_layer_failure |",
            "|---|---|---|---:|---|---|---|",
        ]
        for pair in report["pair_breakdown"]:
            for role in ("variant", "control"):
                m = pair["methods"][method_id][role]
                sig = m["no_gate_target_signal"] or {}
                lines.append(
                    f"| {pair['pair_id']} | {role} | "
                    f"{sig.get('status')} | {sig.get('raw_score')} | "
                    f"{sig.get('reason')} | "
                    f"{str(m['no_gate_emits_target']).lower()} | "
                    f"{str(m['second_layer_failure']).lower()} |"
                )
        lines.append("")

    lines += [
        "## E. Target-rule-record digest",
        "",
        "Full target-rule records are stored in the companion JSON report under "
        "`pair_breakdown[*].methods[*].target_rule_record`.",
        "",
        "| pair_id | method | failed | actions | actors | actor-action pairs | order relations | actions preview |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for pair in report["pair_breakdown"]:
        for method_id, label in labels.items():
            rec = pair["methods"][method_id]["target_rule_record_compact"]
            preview = "; ".join(str(x) for x in rec.get("actions_preview") or [])
            lines.append(
                f"| {pair['pair_id']} | {label} | "
                f"{str(rec.get('failed')).lower()} | {rec.get('action_count')} | "
                f"{rec.get('actor_count')} | "
                f"{rec.get('actor_action_pair_count')} | "
                f"{rec.get('order_relation_count')} | {preview} |"
            )

    lines += [
        "",
        "## F. Inputs and boundary",
        "",
        f"- v3 predictions SHA256: `{report['inputs']['v3_predictions']['sha256']}`",
        f"- case map SHA256: `{report['inputs']['case_map']['sha256']}`",
        f"- target rule id policy: {report['target_rule_id_policy']}",
        "- formal v3 checker, runner, evaluator and outputs were not modified.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v3-dir", type=Path, default=DEFAULT_V3_DIR)
    parser.add_argument("--view", type=Path, default=DEFAULT_VIEW)
    parser.add_argument("--case-map", type=Path, default=DEFAULT_CASE_MAP)
    parser.add_argument("--stage2-input", type=Path, default=DEFAULT_STAGE2_INPUT)
    parser.add_argument("--text-view", type=Path, default=DEFAULT_TEXT_VIEW)
    parser.add_argument("--nlp-model", default="en_core_web_sm")
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    report = evaluate(
        v3_dir=args.v3_dir,
        view_path=args.view,
        case_map_path=args.case_map,
        stage2_input_path=args.stage2_input,
        text_view_path=args.text_view,
        nlp_model=args.nlp_model,
    )
    _write_json(args.out_json, report)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(_render_md(report), encoding="utf-8", newline="\n")
    print(json.dumps({
        "report_json": str(args.out_json),
        "report_md": str(args.out_md),
        "status": report["status"],
        "summary": report["summary"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
