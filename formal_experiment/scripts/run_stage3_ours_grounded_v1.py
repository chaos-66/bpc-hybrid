# -*- coding: utf-8 -*-
"""Grounded Stage-3 'Ours' detector framework.

Inputs
------
- Direct-LLM Rule Record: ``data/predictions/gdpr7_direct_llm_v1/predictions.json``
- Binding Gold: explicitly selected human-filled input (``--binding-gold``).
  Completed review decisions are not automatically promoted to Binding Gold.
- BPMN: the control/variant files named by the paired benchmark and the binding
  surface.

Outputs
-------
- ``missing_action``
- ``incorrect_actor``
- ``out_of_order``
- an evaluation report with precision/recall/F1, Macro-F1 and Micro-F1.

This script never creates, infers, or mutates Gold.  While the binding gold is
blank/unreviewed it fails closed and writes a blocked report instead of
fabricating predictions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
)
import validate_binding_gold_v1 as validator  # noqa: E402
from evaluate_stage3_ours_grounded_v1 import evaluate_predictions  # noqa: E402

DEFAULT_BENCHMARK = (
    ROOT / "data/development/stage3_synth"
    / "stage3_paired_benchmark_v1.json"
)
DEFAULT_RULE_RECORD = (
    ROOT / "data/predictions/gdpr7_direct_llm_v1/predictions.json"
)
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
OUT_DIR = ROOT / "outputs/development/stage3_ours_grounded_v1"
REPORT_JSON = ROOT / "outputs/reports/stage3_ours_grounded_v1.json"
REPORT_MD = ROOT / "outputs/reports/stage3_ours_grounded_v1.md"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")
COMPLIANT = "compliant"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _activity_ids(record: Mapping[str, Any]) -> set[str]:
    return {str(a.get("id")) for a in record.get("activities") or []
            if a.get("id") is not None}


def _lane_of(record: Mapping[str, Any], activity_id: str | None) -> str | None:
    owner = None
    for lane in record.get("lanes") or []:
        if activity_id and activity_id in (lane.get("flow_node_refs") or []):
            owner = lane.get("name") or lane.get("id")
    return owner


def _edges(record: Mapping[str, Any]) -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for item in (record.get("control_flow") or {}).get("direct_edges") or []:
        if isinstance(item, dict):
            src, dst = item.get("source_ref"), item.get("target_ref")
            if src and dst:
                edges.add((str(src), str(dst)))
    return edges


def _rule_record_index(rule_record: Mapping[str, Any]) -> dict[str, dict[str, set[str]]]:
    """Index Direct-LLM Rule Record actions/actors by rule id.

    The records are sentence-level sample ids such as
    ``gdpr_article33_s001``.  The paired benchmark and the binding gold use the
    rule id (``article33``), so prefix matching provides the read-only join
    used for provenance, never for Gold inference.
    """
    out: dict[str, dict[str, set[str]]] = {}

    def ensure(rule_id: str) -> dict[str, set[str]]:
        return out.setdefault(rule_id, {"action_ids": set(), "actor_ids": set()})

    for row in rule_record.get("records") or []:
        sample_id = str(row.get("sample_id") or "")
        record = row.get("record") or {}
        if not sample_id.startswith("gdpr_"):
            continue
        rest = sample_id[len("gdpr_"):]
        rule_id = rest.split("_s", 1)[0]
        bucket = ensure(rule_id)
        for clause in record.get("clauses") or []:
            for action in clause.get("actions") or []:
                if action.get("id") is not None:
                    bucket["action_ids"].add(str(action["id"]))
            for actor in clause.get("actors") or []:
                if actor.get("id") is not None:
                    bucket["actor_ids"].add(str(actor["id"]))
    return out


def _reachable(record: Mapping[str, Any]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for item in (record.get("control_flow") or {}).get("reachable_pairs") or []:
        if isinstance(item, dict):
            src, dst = item.get("source_ref"), item.get("target_ref")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            src, dst = item
        else:
            continue
        if src and dst:
            pairs.add((str(src), str(dst)))
    return pairs


def _decide_record(item: Mapping[str, Any], record: Mapping[str, Any],
                  rule_index: Mapping[str, Mapping[str, set[str]]] | None = None
                  ) -> dict[str, Any]:
    context = item.get("immutable_context") or {}
    target = context.get("target_activity_id")
    action_id = item.get("decision_action_id")
    expected_lane = item.get("decision_expected_lane")
    order_pair = [str(x) for x in (context.get("order_pair") or []) if x]
    record_activities = _activity_ids(record)
    actual_lane = _lane_of(record, str(target) if target else None)

    scores: dict[str, float | None] = {}
    details: dict[str, Any] = {
        "target_activity_id": target,
        "decision_action_id": action_id,
        "expected_lane": expected_lane,
        "actual_lane": actual_lane,
        "order_pair": order_pair,
    }
    rule_id = str((item.get("immutable_context") or {}).get("rule_id") or "")
    rule_side_ids = validator._rule_action_ids(item)
    if rule_index is not None and rule_id in rule_index:
        details["rule_record_action_id_match"] = (
            str(action_id) in rule_index[rule_id].get("action_ids", set()))
        actor_id = item.get("decision_actor_id")
        details["rule_record_actor_id_match"] = (
            None if actor_id is None else
            str(actor_id) in rule_index[rule_id].get("actor_ids", set()))
    details["binding_rule_side_action_id_match"] = (
        str(action_id) in rule_side_ids if action_id is not None else False)

    if not action_id or not target:
        for t in TYPES:
            scores[t] = None
        details["reason"] = "missing_human_action_binding"
        return {"scores": scores, "details": details,
                "predicted": None}

    scores["missing_action"] = (
        1.0 if str(target) not in record_activities else 0.0)
    details["missing_action_target_present"] = str(target) in record_activities

    if expected_lane is None:
        scores["incorrect_actor"] = None
        details["incorrect_actor_reason"] = "no_expected_lane"
    else:
        scores["incorrect_actor"] = (
            1.0 if str(actual_lane or "") != str(expected_lane) else 0.0)
        details["incorrect_actor_match"] = (
            str(actual_lane or "") == str(expected_lane))

    before = item.get("decision_order_before_action_id")
    after = item.get("decision_order_after_action_id")
    if len(order_pair) != 2:
        scores["out_of_order"] = None
        details["out_of_order_reason"] = "no_bpmn_order_pair"
    elif before is None or after is None:
        scores["out_of_order"] = None
        details["out_of_order_reason"] = "no_rule_side_order_binding"
    else:
        forward = (order_pair[0], order_pair[1])
        backward = (order_pair[1], order_pair[0])
        edges = _edges(record)
        reach = _reachable(record)
        fwd_holds = forward in edges or forward in reach
        back_holds = backward in edges or backward in reach
        scores["out_of_order"] = 1.0 if (back_holds and not fwd_holds) else 0.0
        details["out_of_order_forward_holds"] = fwd_holds
        details["out_of_order_backward_holds"] = back_holds
        details["rule_side_order"] = {"before": before, "after": after}

    violated = [t for t in TYPES if scores.get(t) == 1.0]
    if violated:
        predicted = next((t for t in TYPES if t in violated), violated[0])
    elif any(scores.get(t) is None for t in TYPES):
        predicted = None
    else:
        predicted = COMPLIANT
    return {"scores": scores, "details": details, "predicted": predicted}


def _decide_item(item: Mapping[str, Any], control: Mapping[str, Any],
                 variant: Mapping[str, Any],
                 rule_index: Mapping[str, Mapping[str, set[str]]] | None = None
                 ) -> dict[str, Any]:
    """Backward-compatible wrapper; the variant is the decision record."""
    return _decide_record(item, variant, rule_index)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n", encoding="utf-8", newline="\n")


def run(binding_path: Path, benchmark_path: Path, rule_record_path: Path,
        out_dir: Path = OUT_DIR, report_json: Path = REPORT_JSON,
        report_md: Path = REPORT_MD) -> dict[str, Any]:
    binding = _load(binding_path)
    validation = validator.validate_binding_gold(binding)
    validation["input_path"] = str(binding_path.relative_to(ROOT)).replace(
        "\\", "/")
    benchmark = _load(benchmark_path)
    rule_record = _load(rule_record_path)
    report: dict[str, Any] = {
        "schema_version": "stage3_ours_grounded_run@1.0.0",
        "status": "blocked_on_human_annotation",
        "binding_gold": validation,
        "benchmark_id": benchmark.get("benchmark_id"),
        "rule_record": {
            "path": str(rule_record_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256(rule_record_path),
            "schema_version": rule_record.get("schema_version"),
            "records": len(rule_record.get("records") or []),
            "rule_index_size": len(_rule_record_index(rule_record)),
        },
        "predictions_path": None,
        "evaluation": None,
        "llm_api_calls": 0,
        "network_calls": 0,
        "gold_modified": False,
        "benchmark_modified": False,
        "fabricated_gold": False,
    }
    if not validation.get("ready"):
        report["blocked_reason"] = (
            "Binding gold is not ready; human annotation must be completed "
            "before any Ours detector run. No predictions were generated.")
        _write_json(report_json, report)
        report_md.write_text(
            "# Stage 3 Ours grounded detector: blocked\n\n"
            f"- binding gold: `{validation['input_path']}`\n"
            f"- status: `{validation['status']}`\n"
            f"- ready items: {validation['items_ready']}/"
            f"{validation['items']}\n"
            f"- errors: {len(validation['errors'])}\n"
            f"- warnings: {len(validation['warnings'])}\n\n"
            "No predictions or Gold were generated. Complete the human "
            "binding annotation first, then re-run with the filled file.\n",
            encoding="utf-8", newline="\n")
        return report

    rule_index = _rule_record_index(rule_record)
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    benchmark_by_id = {
        str(item["item_id"]): item for item in benchmark.get("items") or []
    }
    cache: dict[str, Any] = {}

    def parse(rel: str) -> Mapping[str, Any]:
        if rel not in cache:
            cache[rel] = parse_bpmn_file(ROOT / rel, contract=contract)
        return cache[rel]

    predictions: list[dict[str, Any]] = []
    for item in binding.get("items") or []:
        roles = (item.get("immutable_context") or {}).get("roles") or {}
        pair_id = str(item.get("pair_id"))
        for role_name in ("control", "variant"):
            role = roles.get(role_name) or {}
            rel = role.get("bpmn_path")
            item_id = str(role.get("item_id") or pair_id)
            if not rel:
                raise ValueError(
                    f"binding item {pair_id} missing {role_name} bpmn path")
            record = parse(rel)
            decision = _decide_record(item, record, rule_index)
            bench_item = benchmark_by_id.get(item_id)
            predictions.append({
                "item_id": item_id,
                "pair_id": pair_id,
                "role": role_name,
                "target_violation_type": (
                    item.get("immutable_context") or {}
                ).get("target_violation_type"),
                "gold": (bench_item or {}).get("gold_violation_type"),
                "predicted": decision["predicted"],
                "scores": decision["scores"],
                "details": decision["details"],
                "review_state": item.get("review_state"),
            })

    out_dir.mkdir(parents=True, exist_ok=True)
    pred_path = out_dir / "predictions.jsonl"
    pred_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n"
                for row in predictions),
        encoding="utf-8", newline="\n")
    evaluation = evaluate_predictions(benchmark, predictions)
    report.update({
        "status": "complete",
        "predictions_path": str(pred_path.relative_to(ROOT)).replace(
            "\\", "/"),
        "evaluation": evaluation,
    })
    _write_json(report_json, report)
    _write_json(out_dir / "evaluation.json", evaluation)
    lines = [
        "# Stage 3 Ours grounded detector",
        "",
        f"- status: `{report['status']}`",
        f"- binding gold: `{validation['input_path']}`",
        f"- predictions: `{report['predictions_path']}`",
        "",
        "| Type | Precision | Recall | F1 | TP | FP | FN |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for t in TYPES:
        row = evaluation["per_type"][t]
        lines.append(
            f"| {t} | {row['precision']:.4f} | {row['recall']:.4f} | "
            f"{row['f1']:.4f} | {row['tp']} | {row['fp']} | {row['fn']} |")
    lines += [
        "",
        f"- Macro-F1: **{evaluation['macro_f1']:.4f}**",
        f"- Micro-F1: **{evaluation['micro_f1']['f1']:.4f}** "
        f"(P {evaluation['micro_f1']['precision']:.4f} / "
        f"R {evaluation['micro_f1']['recall']:.4f})",
        f"- Compliant specificity: {evaluation['compliant_specificity']:.4f}",
        f"- Unobservable: {evaluation['unobservable']}",
        "",
        "The detector consumes the human binding gold as input and never "
        "creates or infers Gold.",
    ]
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8",
                         newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding-gold", type=Path, required=True,
                        help="Explicit input path; completed batches are never auto-selected.")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--rule-record", type=Path, default=DEFAULT_RULE_RECORD)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--report-json", type=Path, default=REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    args = parser.parse_args()
    report = run(args.binding_gold, args.benchmark, args.rule_record,
                 args.out_dir, args.report_json, args.report_md)
    print(json.dumps({
        "status": report.get("status"),
        "blocked_reason": report.get("blocked_reason"),
        "ready": (report.get("binding_gold") or {}).get("ready"),
        "evaluation": report.get("evaluation"),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("status") == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
