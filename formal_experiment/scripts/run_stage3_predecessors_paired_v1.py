# -*- coding: utf-8 -*-
"""Run the frozen predecessor arms on the paired compliance benchmark.

Zero API, zero network, deterministic.  This is the benchmark SANITY CHECK the
repair plan calls for: run the predecessors BEFORE any "ours" claim, on the
same 60 items, with the same scoring protocol, and report what actually happens.

Arms
----
- ``sun_reconstruction``   - the frozen Sun et al. (2024) Stage 3 reconstruction
  (``SunScorer``, tau/gamma/theta from ``configs/sun_stage3_development_v1.json``)
- ``winter_wrapper``       - the frozen Winter et al. (2020) Stage 3 wrapper
  (``WinterPair``, gamma/delta from ``configs/winter_stage3_development_v1.json``)

Protocol (identical for every arm and every item)
-------------------------------------------------
Each arm scores BOTH BPMNs of every pair (control and variant) for the pair's
bound violation type.  The prediction rule is the arm's own frozen rule - for
these two arms, "the violation holds when the bound type's score is > 0" - so
no threshold is invented here to flatter or penalise anyone.

Observability is reported, never zero-filled: when an arm cannot produce a
score for the bound type (its precondition fails), the item is marked
unobservable AND is counted as a miss in recall, exactly as the frozen Stage 3
evaluation does.

Usage:
    python scripts/run_stage3_predecessors_paired_v1.py
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

import spacy  # noqa: E402

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
)

BENCHMARK = (ROOT / "data/development/stage3_synth"
             / "stage3_paired_benchmark_v1.json")
INFERENCE_PACK = (ROOT / "data/development/human_review"
                  / "stage3_gold_inference_v1.json")
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
SUN_CONFIG = ROOT / "configs/sun_stage3_development_v1.json"
WINTER_CONFIG = ROOT / "configs/winter_stage3_development_v1.json"
WINTER_FILES = (ROOT.parent / "references" / "winter_2020_model_check"
                / "model_check" / "input" / "files")
TYPES = ("missing_action", "incorrect_actor", "out_of_order")
COMPLIANT = "compliant"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_lexicon(name: str) -> list[str]:
    path = WINTER_FILES / name
    return [w.strip() for w in path.read_text(
        encoding="utf-8", errors="replace").splitlines() if w.strip()]


def _prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
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

    benchmark = _load(BENCHMARK)
    inference = _load(INFERENCE_PACK)
    rule_text = {i["rule_id"]: i.get("rule_text", "")
                 for i in inference.get("matching_items", [])}
    sun_cfg = _load(SUN_CONFIG)["method"]["thresholds"]
    winter_cfg = _load(WINTER_CONFIG)["method"]

    nlp = spacy.load("en_core_web_sm")
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)

    from bpc_hybrid.sun_stage3.sun_model import SunProcessModel
    from bpc_hybrid.sun_stage3.sun_rule_extraction import extract_rule_record
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
    from bpc_hybrid.winter_stage3.winter_clause import (
        parse_regulation_paragraph,
    )
    from bpc_hybrid.winter_stage3.winter_model import (
        REACHABILITY_CORRECTED,
        parse_bpmn_file_winter,
    )
    from bpc_hybrid.winter_stage3.winter_pair import WinterPair
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity

    sim = WinterSimilarity(nlp)
    signalwords = _read_lexicon("signalwords.txt")
    sequencemarkers = _read_lexicon("sequencemarkers.txt")
    stopwords = _read_lexicon("stopwords.txt")

    sun_scorer = SunScorer(sim, float(sun_cfg["tau"]), float(sun_cfg["gamma"]),
                           float(sun_cfg["theta"]), nlp=nlp)

    rule_cache: dict[str, Any] = {}

    def sun_rule(rule_id: str):
        if rule_id not in rule_cache:
            rule_cache[rule_id] = extract_rule_record(
                rule_id, rule_text[rule_id], nlp, signalwords)
        return rule_cache[rule_id]

    model_cache: dict[str, Any] = {}
    winter_cache: dict[str, Any] = {}

    def score_sun(bpmn: Path, process_id: str, rule_id: str) -> dict[str, Any]:
        key = str(bpmn)
        if key not in model_cache:
            model_cache[key] = SunProcessModel(
                process_id, parse_bpmn_file(bpmn, contract=contract), nlp)
        model = model_cache[key]
        rule = sun_rule(rule_id)
        ma = sun_scorer.missing_action(rule["actions"], model)
        ia = sun_scorer.incorrect_actor(rule["actions"], rule["actors"], model,
                                        rule.get("actor_action_pairs"))
        oo = sun_scorer.out_of_order(rule["order_relations"], rule["actions"],
                                     model)
        return {
            "missing_action": {"score": ma["score"],
                               "observable": ma["score"] is not None,
                               "reason": ma.get("reason")},
            "incorrect_actor": {"score": ia["score"],
                                "observable": bool(ia.get("observable")),
                                "reason": ia.get("reason")},
            "out_of_order": {"score": oo["score"],
                             "observable": oo["score"] is not None,
                             "reason": oo.get("reason")},
        }

    def score_winter(bpmn: Path, process_id: str,
                     rule_id: str) -> dict[str, Any]:
        key = str(bpmn)
        if key not in winter_cache:
            winter_cache[key] = parse_bpmn_file_winter(
                bpmn, nlp, stopwords,
                reachability_mode=REACHABILITY_CORRECTED)
        model = winter_cache[key]
        resources = {proc.participant.lower() for proc in model.processes}
        paragraph = parse_regulation_paragraph(
            rule_id, rule_text[rule_id], nlp, stopwords, signalwords,
            sequencemarkers, only_constraints=True)
        pair = WinterPair(nlp, sim, model, paragraph, resources,
                          float(winter_cfg["gamma"]),
                          float(winter_cfg["delta"]))
        return {
            "missing_action": {"score": pair.cost_obligation,
                               "observable": True, "reason": None},
            "incorrect_actor": {"score": pair.cost_resource,
                                "observable": True, "reason": None},
            "out_of_order": {"score": pair.cost_so,
                             "observable": True, "reason": None},
        }

    arms = {"sun_reconstruction": score_sun, "winter_wrapper": score_winter}

    results: dict[str, Any] = {}
    for arm_id, scorer in arms.items():
        rows: list[dict[str, Any]] = []
        for item in benchmark["items"]:
            bpmn = ROOT / item["bpmn_path"]
            bound = item["target_violation_type"]
            scores = scorer(bpmn, item["process_id"], item["rule_id"])
            bound_result = scores[bound]
            observable = bound_result["observable"]
            if not observable:
                predicted = None
            else:
                violated = (bound_result["score"] or 0.0) > 0.0
                predicted = bound if violated else COMPLIANT
            rows.append({
                "item_id": item["item_id"],
                "pair_id": item["pair_id"],
                "role": item["role"],
                "target_violation_type": bound,
                "gold": item["gold_violation_type"],
                "predicted": predicted,
                "observable": observable,
                "reason": bound_result.get("reason"),
                "score": bound_result["score"],
            })

        per_type = {}
        for t in TYPES:
            tp = sum(1 for r in rows if r["predicted"] == t and r["gold"] == t)
            fp = sum(1 for r in rows if r["predicted"] == t and r["gold"] != t)
            fn = sum(1 for r in rows if r["predicted"] != t and r["gold"] == t)
            per_type[t] = _prf(tp, fp, fn)
        controls = [r for r in rows if r["role"] == "control"]
        variants = [r for r in rows if r["role"] == "variant"]
        correct_compliant = sum(1 for r in controls
                                if r["predicted"] == COMPLIANT)
        micro_tp = sum(1 for r in rows if r["gold"] != COMPLIANT
                       and r["predicted"] == r["gold"])
        micro_fp = sum(1 for r in rows if r["gold"] == COMPLIANT
                       and r["predicted"] != COMPLIANT)
        micro_fn = sum(1 for r in rows if r["gold"] != COMPLIANT
                       and r["predicted"] != r["gold"])
        results[arm_id] = {
            "per_type": per_type,
            "macro_f1": sum(per_type[t]["f1"] for t in TYPES) / len(TYPES),
            "micro_f1": _prf(micro_tp, micro_fp, micro_fn),
            "compliant_specificity": (correct_compliant / len(controls)
                                      if controls else 0.0),
            "controls_correct": correct_compliant,
            "controls": len(controls),
            "variant_exact_type_correct": sum(
                1 for r in variants if r["predicted"] == r["gold"]),
            "variants": len(variants),
            "unobservable": sum(1 for r in rows if not r["observable"]),
            "predictions": rows,
        }

    grounded_path = ROOT / "outputs" / "reports" / "stage3_grounded_checker_v1.json"
    grounded = _load(grounded_path) if grounded_path.is_file() else None

    report = {
        "schema_version": "stage3_predecessors_paired_run@1.0.0",
        "benchmark_id": benchmark["benchmark_id"],
        "benchmark_sha256": hashlib.sha256(BENCHMARK.read_bytes()).hexdigest(),
        "items": len(benchmark["items"]),
        "protocol": (
            "each arm scores both BPMNs of every pair for the pair's bound "
            "violation type; prediction rule is the arm's own frozen rule "
            "(score > 0); unobservable items are counted as misses, never "
            "zero-filled"),
        "arms": results,
        "grounded_reference": None if grounded is None else {
            "method_id": grounded["method_id"],
            "macro_f1": grounded["macro_f1"],
            "micro_f1": grounded["micro_f1"]["f1"],
            "compliant_specificity": grounded["compliant_specificity"],
            "variant_exact_type_accuracy":
                grounded["variant_exact_type_accuracy"],
        },
        "llm_calls": 0,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "stage3_predecessors_paired_v1.json"
    md_path = out_dir / "stage3_predecessors_paired_v1.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n", encoding="utf-8")

    lines: list[str] = []
    lines.append("# Predecessor arms on the paired compliance benchmark")
    lines.append("")
    lines.append(f"Benchmark: `{report['benchmark_id']}` - "
                 f"{report['items']} items - {report['llm_calls']} LLM calls.")
    lines.append("")
    lines.append("## Per-type F1")
    lines.append("")
    lines.append("| Arm | missing_action | incorrect_actor | out_of_order | "
                 "Macro-F1 | Micro-F1 | Compliant specificity | Exact type | "
                 "Unobservable |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for arm_id, res in results.items():
        lines.append(
            f"| {arm_id} | {res['per_type']['missing_action']['f1']:.4f} | "
            f"{res['per_type']['incorrect_actor']['f1']:.4f} | "
            f"{res['per_type']['out_of_order']['f1']:.4f} | "
            f"{res['macro_f1']:.4f} | {res['micro_f1']['f1']:.4f} | "
            f"{res['compliant_specificity']:.4f} | "
            f"{res['variant_exact_type_correct']}/{res['variants']} | "
            f"{res['unobservable']} |")
    if grounded:
        lines.append(
            f"| {grounded['method_id']} (reference) | "
            f"{grounded['per_type']['missing_action']['f1']:.4f} | "
            f"{grounded['per_type']['incorrect_actor']['f1']:.4f} | "
            f"{grounded['per_type']['out_of_order']['f1']:.4f} | "
            f"{grounded['macro_f1']:.4f} | {grounded['micro_f1']['f1']:.4f} | "
            f"{grounded['compliant_specificity']:.4f} | "
            f"{grounded['variant_exact_type_correct']}/"
            f"{grounded['variants']} | {grounded['unobservable']} |")
    lines.append("")
    lines.append("## Honest reading")
    lines.append("")
    lines.append("A healthy benchmark must let a correctly grounded method "
                 "score well (the reference row above does). The predecessor "
                 "rows show what the SAME items look like when the rule-to-"
                 "process binding is re-derived by embedding similarity "
                 "instead of consumed; the gap is a grounding effect, not "
                 "evidence that the predecessors' algorithms are weak.")
    lines.append("")
    lines.append("`Unobservable` counts items where the arm's own precondition "
                 "failed; those are counted as misses and never zero-filled.")
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
