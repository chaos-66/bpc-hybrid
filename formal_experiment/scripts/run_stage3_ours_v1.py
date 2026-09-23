# -*- coding: utf-8 -*-
"""Run Stage-3 Ours: automatic grounding followed by the compliance detector.

Ordering is part of the safety contract:
1. load ONLY the Direct-LLM Rule Record + benchmark inference view;
2. build automatic grounding predictions on each pair's reference/control BPMN;
3. persist those predictions;
4. only then may an external evaluator read Binding Reference/Gold.

The detector consumes the persisted grounding predictions and the item BPMN.
It never reads mutation answers (`grounding`, `target_activity_id`,
`expected_lane`, `order_pair`, `gold_violation_type`, `target_violation_type`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

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
from bpc_hybrid.stage3_grounding.automatic_rule_process_grounding_v1 import (  # noqa: E402
    DEFAULT_DIRECT_PREDICTIONS,
    DEFAULT_STAGE2_INPUT,
    FORBIDDEN_INFERENCE_FIELDS,
    ROOT as PACKAGE_ROOT,
    build_all_grounding_predictions,
    project_benchmark_items,
)

BENCHMARK_VIEW = (
    ROOT / "data/development/stage3_synth"
    / "stage3_paired_benchmark_inference_view_v1.json"
)
OUT_DIR = ROOT / "outputs/development/stage3_ours_v1"
GROUNDING_JSON = OUT_DIR / "automatic_grounding_predictions_v1.json"
PREDICTIONS_JSONL = OUT_DIR / "predictions.jsonl"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"

TYPES = ("missing_action", "incorrect_actor", "out_of_order")
COMPLIANT = "compliant"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _activity_ids(record: dict[str, Any]) -> set[str]:
    return {str(a.get("id")) for a in record.get("activities") or []
            if a.get("id") is not None}


def _lane_of(record: dict[str, Any], activity_id: str) -> str | None:
    for lane in record.get("lanes") or []:
        if str(activity_id) in (lane.get("flow_node_refs") or []):
            return str(lane.get("id") or "")
    return None


def _edges(record: dict[str, Any]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for item in (record.get("control_flow") or {}).get("direct_edges") or []:
        if isinstance(item, dict):
            src, dst = item.get("source_ref"), item.get("target_ref")
            if src and dst:
                out.add((str(src), str(dst)))
    return out


def _reachable(record: dict[str, Any]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for item in (record.get("control_flow") or {}).get("reachable_pairs") or []:
        if isinstance(item, dict):
            src, dst = item.get("source_ref"), item.get("target_ref")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            src, dst = item
        else:
            continue
        if src and dst:
            out.add((str(src), str(dst)))
    return out


def _order_violation(record: dict[str, Any],
                     grounding: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Return a rule-order violation if and only if the Rule Record supplied
    usable order endpoints.  Process-only mutations without a rule-side order
    relation are deliberately unobservable here."""
    edges = _edges(record)
    reach = _reachable(record)
    details: list[dict[str, Any]] = []
    for relation in grounding.get("order_predictions") or []:
        before = relation.get("before_predicted_activity_id")
        after = relation.get("after_predicted_activity_id")
        if not before or not after:
            continue
        forward = (str(before), str(after))
        backward = (str(after), str(before))
        fwd = forward in edges or forward in reach
        back = backward in edges or backward in reach
        details.append({
            "before_rule_action_id": relation.get("before_rule_action_id"),
            "after_rule_action_id": relation.get("after_rule_action_id"),
            "before_activity_id": before,
            "after_activity_id": after,
            "forward_holds": fwd,
            "backward_holds": back,
        })
        if back and not fwd:
            return True, {"reason": "grounded_rule_order_inverted",
                          "relations": details}
    return False, {"reason": "no_grounded_rule_order",
                   "relations": details}


def decide_item(record: dict[str, Any], grounding: dict[str, Any]
                ) -> dict[str, Any]:
    present = _activity_ids(record)
    detector_ids = [str(x) for x in grounding.get("detector_activity_ids") or []]

    missing = [activity_id for activity_id in detector_ids
               if activity_id not in present]
    if missing:
        return {
            "predicted": "missing_action",
            "details": {
                "reason": "grounded_required_activity_absent",
                "missing_activity_ids": missing,
                "detector_activity_count": len(detector_ids),
            },
        }

    lane_mismatches: list[dict[str, Any]] = []
    lane_map = grounding.get("activity_lane_map") or {}
    for activity_id in detector_ids:
        if activity_id not in present:
            continue
        expected = lane_map.get(activity_id)
        actual = _lane_of(record, activity_id)
        if expected is not None and actual is not None and str(actual) != str(expected):
            lane_mismatches.append({
                "activity_id": activity_id,
                "expected_lane_id": expected,
                "actual_lane_id": actual,
            })
    if lane_mismatches:
        return {
            "predicted": "incorrect_actor",
            "details": {
                "reason": "grounded_activity_lane_changed",
                "lane_mismatches": lane_mismatches,
            },
        }

    order_violation, order_details = _order_violation(record, grounding)
    if order_violation:
        return {
            "predicted": "out_of_order",
            "details": order_details,
        }

    return {
        "predicted": COMPLIANT,
        "details": {
            "reason": "no_grounded_structural_violation",
            "detector_activity_count": len(detector_ids),
            "order_observable": bool(grounding.get("order_predictions")),
        },
    }


def run(
    *,
    benchmark_path: Path = BENCHMARK_VIEW,
    direct_predictions_path: Path = DEFAULT_DIRECT_PREDICTIONS,
    sentence_input_path: Path = DEFAULT_STAGE2_INPUT,
    out_dir: Path = OUT_DIR,
    nlp_model: str = "en_core_web_md",
) -> dict[str, Any]:
    benchmark = _load(benchmark_path)
    items = project_benchmark_items(benchmark)
    source_benchmark = str(benchmark.get("source_benchmark") or "")
    source_benchmark_sha256 = str(benchmark.get("source_benchmark_sha256") or "")
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)

    # Lazy import keeps the optional model out of CLI parsing and tests that
    # exercise only the detector wiring.
    import spacy  # type: ignore
    try:
        nlp = spacy.load(nlp_model, disable=["ner", "parser", "textcat"])
    except Exception:
        nlp = spacy.load("en_core_web_sm", disable=["ner", "parser", "textcat"])

    grounding_doc = build_all_grounding_predictions(
        benchmark_path=benchmark_path,
        direct_predictions_path=direct_predictions_path,
        sentence_input_path=sentence_input_path,
        nlp=nlp,
        contract_path=STRUCTURAL_CONTRACT,
    )

    grounding_json = out_dir / "automatic_grounding_predictions_v1.json"
    _write_json(grounding_json, grounding_doc)

    grounding_by_pair = {
        str(row["pair_id"]): row for row in grounding_doc["rows"]
    }
    cache: dict[str, dict[str, Any]] = {}

    def record_for(rel_path: str) -> dict[str, Any]:
        if rel_path not in cache:
            cache[rel_path] = parse_bpmn_file(ROOT / rel_path, contract=contract)
        return cache[rel_path]

    predictions: list[dict[str, Any]] = []
    for item in items:
        pair_id = str(item["pair_id"])
        grounding = grounding_by_pair.get(pair_id) or {}
        record = record_for(str(item["bpmn_path"]))
        decision = decide_item(record, grounding)
        predictions.append({
            "item_id": item["item_id"],
            "pair_id": pair_id,
            "role": item["role"],
            "rule_id": item["rule_id"],
            "process_id": item["process_id"],
            "predicted": decision["predicted"],
            "details": decision["details"],
            "grounding_reference_pair_id": pair_id,
            "inference_uses_benchmark_grounding_block": False,
            "inference_uses_binding_reference": False,
        })

    predictions_path = out_dir / "predictions.jsonl"
    _write_jsonl(predictions_path, predictions)
    run_report = {
        "schema_version": "stage3_ours_run@1.0.0",
        "method_id": "ours_automatic_grounding_detector_v1",
        "status": "complete",
        "benchmark_id": benchmark.get("benchmark_id"),
        "benchmark_view_path": str(
            benchmark_path.resolve().relative_to(ROOT.resolve())
        ).replace("\\", "/"),
        "benchmark_view_sha256": _sha256(benchmark_path),
        "source_benchmark": source_benchmark,
        "source_benchmark_sha256": source_benchmark_sha256,
        "items": len(predictions),
        "grounding_predictions_path": str(
            grounding_json.resolve().relative_to(ROOT.resolve())
        ).replace("\\", "/"),
        "predictions_path": str(
            predictions_path.resolve().relative_to(ROOT.resolve())
        ).replace("\\", "/"),
        "forbidden_inputs_not_read": list(FORBIDDEN_INFERENCE_FIELDS)
        + ["binding_reference", "mutation_manifest", "gold_label"],
        "inference_uses_benchmark_grounding_block": False,
        "inference_uses_binding_reference": False,
        "binding_reference_read_before_prediction_persisted": False,
        "llm_api_calls": 0,
        "network_calls": 0,
    }
    _write_json(out_dir / "run_manifest.json", run_report)
    return run_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK_VIEW,
                        help="Gold-blind inference view, not the full benchmark.")
    parser.add_argument("--direct-predictions", type=Path,
                        default=DEFAULT_DIRECT_PREDICTIONS)
    parser.add_argument("--stage2-input", type=Path, default=DEFAULT_STAGE2_INPUT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--nlp-model", default="en_core_web_md")
    args = parser.parse_args()
    report = run(
        benchmark_path=args.benchmark,
        direct_predictions_path=args.direct_predictions,
        sentence_input_path=args.stage2_input,
        out_dir=args.out_dir,
        nlp_model=args.nlp_model,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
