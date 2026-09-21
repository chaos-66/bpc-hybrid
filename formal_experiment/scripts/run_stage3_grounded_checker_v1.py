# -*- coding: utf-8 -*-
"""Run a GROUNDED three-type Stage 3 checker on the paired benchmark.

Zero API, zero network, deterministic.

Why a grounded checker
----------------------
The frozen predecessor arms (Sun et al. reconstruction, Winter et al. wrapper,
BM25, TF-IDF/SVD) all ground rule text onto BPMN activities by *similarity*.
On GDPR wording versus BPMN activity labels that mapping never clears the
threshold, which is why their per-type scores on this corpus are degenerate
(the unmutated originals already score as violations).

This runner instead consumes each item's **declared binding**
(``grounding.target_activity_id`` / ``expected_actor_lane`` / ``order_pair``)
and decides the three types structurally - the same observations the benchmark
itself is defined on.  It is therefore the natural upper bound: a grounded
checker *should* score near-perfectly, and any gap is a scoring or wiring bug
rather than a method difference.

That makes it the correct instrument for the objective's step 6: a benchmark
sanity check.  A healthy benchmark must let a correctly grounded method score
well.  If this runner does NOT score well, the benchmark is still broken.

Reported metrics (per violation type, plus the compliant class)
--------------------------------------------------------------
- precision / recall / F1 for each of the three violation types
- macro-F1 over the three types
- micro-F1 over the 60 items
- compliant specificity and false-positive rate on the 30 controls
- exact-type accuracy on the 30 variants

Usage:
    python scripts/run_stage3_grounded_checker_v1.py
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
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
)

BENCHMARK = (ROOT / "data/development/stage3_synth"
             / "stage3_paired_benchmark_v1.json")
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")
COMPLIANT = "compliant"
METHOD_ID = "grounded_structural_checker_v1"


def _edges(record: dict[str, Any]) -> set[tuple[str, str]]:
    out = set()
    for item in (record.get("control_flow") or {}).get("direct_edges") or []:
        if isinstance(item, dict):
            src, dst = item.get("source_ref"), item.get("target_ref")
            if src and dst:
                out.add((src, dst))
    return out


def _reachable(record: dict[str, Any]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for item in ((record.get("control_flow") or {}).get("reachable_pairs")
                 or []):
        if isinstance(item, dict):
            src, dst = item.get("source_ref"), item.get("target_ref")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            src, dst = item
        else:
            raise TypeError(f"unexpected reachable_pairs element: {item!r}")
        if src and dst:
            out.add((src, dst))
    return out


def _activities(record: dict[str, Any]) -> set[str]:
    return {a["id"] for a in record.get("activities") or []}


def _lane_of(record: dict[str, Any], activity_id: str | None) -> str | None:
    owner = None
    for lane in record.get("lanes") or []:
        if activity_id and activity_id in (lane.get("flow_node_refs") or []):
            owner = lane.get("name") or lane.get("id")
    return owner


def score(record: dict[str, Any], violation_type: str,
          grounding: dict[str, Any]) -> dict[str, Any]:
    """Structural score for one type; >0 means violation."""
    target = grounding.get("target_activity_id")
    if violation_type == "missing_action":
        present = target in _activities(record)
        return {"score": 0.0 if present else 1.0,
                "observable": True,
                "detail": {"target_present": present}}
    if violation_type == "incorrect_actor":
        lane = _lane_of(record, target)
        named = [l for l in record.get("lanes") or []
                 if (l.get("name") or "").strip()]
        moved = bool(lane) and any((l.get("name") or "") == lane
                                   for l in named)
        return {"score": 1.0 if moved else 0.0, "observable": True,
                "detail": {"target_lane": lane,
                           "named_lane_count": len(named)}}
    if violation_type == "out_of_order":
        pair = [n for n in (grounding.get("order_pair") or []) if n]
        if len(pair) != 2:
            return {"score": None, "observable": False,
                    "detail": {"reason": "no_order_pair"}}
        edges = _edges(record)
        reach = _reachable(record)
        forward = (pair[0], pair[1])
        backward = (pair[1], pair[0])
        fwd = forward in edges or forward in reach
        back = backward in edges or backward in reach
        return {"score": 1.0 if (back and not fwd) else 0.0,
                "observable": True,
                "detail": {"forward_holds": fwd, "backward_holds": back}}
    raise ValueError(f"unknown violation type: {violation_type}")


def decide(record: dict[str, Any], grounding: dict[str, Any]
           ) -> dict[str, Any]:
    """Emit ONE predicted label for the item.

    The benchmark binds each control/variant pair to exactly ONE violation
    type, so the grounded decision is: does that bound type hold?
    """
    target_type = grounding["target_violation_type"]
    result = score(record, target_type, grounding)
    if not result["observable"]:
        return {"predicted": None, "scores": {target_type: None},
                "observability": {target_type: result["detail"]}}
    violated = (result["score"] or 0.0) > 0.0
    return {
        "predicted": target_type if violated else COMPLIANT,
        "scores": {target_type: result["score"]},
        "observability": {target_type: result["detail"]},
    }


def prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision,
            "recall": recall, "f1": f1}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(ROOT / "outputs" / "reports"))
    args = parser.parse_args()

    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)

    cache: dict[str, Any] = {}
    predictions: list[dict[str, Any]] = []
    for item in benchmark["items"]:
        path = ROOT / item["bpmn_path"]
        key = str(path)
        if key not in cache:
            cache[key] = parse_bpmn_file(path, contract=contract)
        grounding = dict(item["grounding"])
        grounding["target_violation_type"] = item["target_violation_type"]
        decision = decide(cache[key], grounding)
        predictions.append({
            "item_id": item["item_id"],
            "pair_id": item["pair_id"],
            "role": item["role"],
            "target_violation_type": item["target_violation_type"],
            "gold": item["gold_violation_type"],
            "predicted": decision["predicted"],
            "unobservable": decision["predicted"] is None,
            "scores": decision["scores"],
            "observability": decision["observability"],
        })

    # ---- metrics ------------------------------------------------------
    per_type: dict[str, Any] = {}
    for t in TYPES:
        tp = sum(1 for p in predictions
                 if p["predicted"] == t and p["gold"] == t)
        fp = sum(1 for p in predictions
                 if p["predicted"] == t and p["gold"] != t)
        fn = sum(1 for p in predictions
                 if p["predicted"] != t and p["gold"] == t)
        per_type[t] = prf(tp, fp, fn)

    controls = [p for p in predictions if p["role"] == "control"]
    variants = [p for p in predictions if p["role"] == "variant"]
    correct_compliant = sum(1 for p in controls if p["predicted"] == COMPLIANT)
    specificity = (correct_compliant / len(controls)) if controls else 0.0
    false_positive_rate = 1.0 - specificity

    micro_tp = sum(1 for p in predictions if p["gold"] != COMPLIANT
                   and p["predicted"] == p["gold"])
    micro_fp = sum(1 for p in predictions if p["gold"] == COMPLIANT
                   and p["predicted"] != COMPLIANT)
    micro_fn = sum(1 for p in predictions if p["gold"] != COMPLIANT
                   and p["predicted"] != p["gold"])
    micro = prf(micro_tp, micro_fp, micro_fn)
    exact_type = sum(1 for p in variants if p["predicted"] == p["gold"])
    macro_f1 = sum(per_type[t]["f1"] for t in TYPES) / len(TYPES)

    report = {
        "schema_version": "stage3_grounded_checker_run@1.0.0",
        "method_id": METHOD_ID,
        "benchmark_id": benchmark["benchmark_id"],
        "benchmark_sha256": hashlib.sha256(
            BENCHMARK.read_bytes()).hexdigest(),
        "items": len(predictions),
        "per_type": per_type,
        "macro_f1": macro_f1,
        "micro_f1": micro,
        "compliant_specificity": specificity,
        "compliant_false_positive_rate": false_positive_rate,
        "controls_correct": correct_compliant,
        "controls": len(controls),
        "variant_exact_type_accuracy": exact_type / len(variants)
        if variants else None,
        "variant_exact_type_correct": exact_type,
        "variants": len(variants),
        "unobservable": sum(1 for p in predictions if p["unobservable"]),
        "claim_scope": "dev_only_benchmark_not_human_gold",
        "llm_calls": 0,
        "predictions": predictions,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "stage3_grounded_checker_v1.json"
    md_path = out_dir / "stage3_grounded_checker_v1.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n", encoding="utf-8")

    lines: list[str] = []
    lines.append("# Grounded Stage 3 checker on the paired benchmark")
    lines.append("")
    lines.append(f"Method id: `{METHOD_ID}` - {report['items']} items - "
                 f"{report['llm_calls']} LLM calls - scope "
                 f"`{report['claim_scope']}`.")
    lines.append("")
    lines.append("## Per-type results")
    lines.append("")
    lines.append("| Violation type | Precision | Recall | F1 | TP | FP | FN |")
    lines.append("|---|---|---|---|---|---|---|")
    for t in TYPES:
        row = per_type[t]
        lines.append(f"| {t} | {row['precision']:.4f} | {row['recall']:.4f} | "
                     f"{row['f1']:.4f} | {row['tp']} | {row['fp']} | "
                     f"{row['fn']} |")
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    lines.append(f"- Macro-F1 (three types): **{macro_f1:.4f}**")
    lines.append(f"- Micro-F1 (60 items): **{micro['f1']:.4f}** "
                 f"(P {micro['precision']:.4f} / R {micro['recall']:.4f})")
    lines.append(f"- Compliant specificity: **{specificity:.4f}** "
                 f"({correct_compliant}/{len(controls)} controls correct)")
    lines.append(f"- Compliant false-positive rate: {false_positive_rate:.4f}")
    lines.append(f"- Variant exact-type accuracy: "
                 f"{report['variant_exact_type_accuracy']:.4f} "
                 f"({exact_type}/{len(variants)})")
    lines.append(f"- Unobservable: {report['unobservable']}")
    lines.append("")
    lines.append("## Sanity verdict")
    lines.append("")
    if macro_f1 == 1.0 and specificity == 1.0:
        lines.append("**PASS.** A correctly grounded checker reaches a perfect "
                     "score, so the benchmark is measurable and its Ground "
                     "Truth is internally consistent. Predecessor arms that "
                     "score degenerate values on the same items are therefore "
                     "failing at grounding, not at the benchmark.")
    else:
        lines.append("**ATTENTION.** A correctly grounded checker does NOT "
                     "reach a perfect score, which means the benchmark or the "
                     "scoring wiring is still wrong. Do not report method "
                     "comparisons on it until this is resolved.")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print()
    try:
        print("\n".join(lines))
    except UnicodeEncodeError:
        sys.stdout.buffer.write("\n".join(lines).encode("utf-8",
                                                       errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
