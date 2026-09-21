# -*- coding: utf-8 -*-
"""READ-ONLY Stage 3 threshold + root-cause diagnostic (zero API, zero writes).

Follow-up to ``stage3_benchmark_viability_v1.py``.  That run showed the
30-item panel has ZERO cleanly separable items at the Sun primary thresholds
(tau=0.8, gamma=0.8, theta=0.8), because the UNMUTATED originals are already
scored as violations.

This script answers two questions:

A. Is that a THRESHOLD artifact?  Sweep gamma over the config's declared
   sweep grid and report, per type, how many items become separable
   (original compliant AND mutated violating AND observable).

B. Is it a STRUCTURAL artifact?  For out_of_order specifically, report the
   detector's denominator on the mutated BPMNs (a zero denominator means the
   rule's order relations never map to process actions, so the type cannot be
   observed at all regardless of threshold), and for missing_action report the
   per-item action counts on the original vs mutated model so we can see
   whether the mutation changes the observable input.

Nothing is written.  No LLM/API is called.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import spacy  # noqa: E402

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
)
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402
from bpc_hybrid.sun_stage3.sun_rule_extraction import (  # noqa: E402
    extract_rule_record,
)
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import (  # noqa: E402
    WinterSimilarity,
)

PANEL = (ROOT / "data/development/stage3_synth"
         / "synthetic_controlled_error_extension_v1.json")
INFERENCE_PACK = (ROOT / "data/development/human_review"
                  / "stage3_gold_inference_v1.json")
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
SUN_CONFIG = ROOT / "configs/sun_stage3_development_v1.json"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    panel = _load(PANEL)
    config = _load(SUN_CONFIG)
    th = config["method"]["thresholds"]
    tau, theta = float(th["tau"]), float(th["theta"])
    gamma_grid = [float(g) for g in th["sweeps"]["gamma"]]

    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    signal_path = (ROOT.parent / "references" / "winter_2020_model_check"
                   / "model_check" / "input" / "files" / "signalwords.txt")
    signalwords = [w.strip() for w in signal_path.read_text(
        encoding="utf-8", errors="replace").splitlines() if w.strip()]

    rule_cache: dict[str, Any] = {}

    def rule_for(rule_id: str):
        if rule_id not in rule_cache:
            rule_cache[rule_id] = extract_rule_record(
                rule_id, _rule_text(rule_id), nlp, signalwords)
        return rule_cache[rule_id]

    def _rule_text(rule_id: str) -> str:
        for item in _load(INFERENCE_PACK).get("matching_items", []):
            if item["rule_id"] == rule_id:
                return item["rule_text"]
        raise RuntimeError(rule_id)

    model_cache: dict[str, Any] = {}

    def model_for(path: Path, pid: str):
        key = str(path)
        if key not in model_cache:
            model_cache[key] = SunProcessModel(
                pid, parse_bpmn_file(path, contract=contract), nlp)
        return model_cache[key]

    print("=" * 98)
    print("A. GAMMA SWEEP — separable items per type "
          "(tau=%.1f theta=%.1f)" % (tau, theta))
    print("=" * 98)
    print(f"{'gamma':>7} | " + " | ".join(
        f"{t:>17}" for t in TYPES) + " |  total")
    print("-" * 98)
    for gamma in gamma_grid:
        scorer = SunScorer(sim, tau, gamma, theta, nlp=nlp)
        counts = defaultdict(int)
        totals = Counter(v["mutation_type"] for v in panel["variants"])
        for v in panel["variants"]:
            pid, rule_id, t = v["process_id"], v["rule_id"], v["mutation_type"]
            rule = rule_for(rule_id)
            try:
                base = _score(scorer, rule, model_for(ROOT / v["source_bpmn"], pid), t)
                var = _score(scorer, rule, model_for(ROOT / v["variant_bpmn"], pid), t)
            except Exception:
                continue
            if base["observable"] and var["observable"] \
                    and base["score"] == 0.0 and (var["score"] or 0) > 0.0:
                counts[t] += 1
        cells = " | ".join(f"{counts[t]:>2}/{totals[t]:<2} separable"
                           for t in TYPES)
        print(f"{gamma:>7.1f} | {cells} |  {sum(counts.values())}/30")

    print()
    print("=" * 98)
    print("B. STRUCTURAL ROOT CAUSE at the primary gamma=0.8")
    print("=" * 98)
    scorer = SunScorer(sim, tau, 0.8, theta, nlp=nlp)

    oo_denoms = Counter()
    ma_actions: list[tuple[int, int, int]] = []
    ia_reasons = Counter()
    for v in panel["variants"]:
        pid, rule_id, t = v["process_id"], v["rule_id"], v["mutation_type"]
        rule = rule_for(rule_id)
        om = model_for(ROOT / v["source_bpmn"], pid)
        vm = model_for(ROOT / v["variant_bpmn"], pid)
        if t == "out_of_order":
            oo = scorer.out_of_order(rule["order_relations"], rule["actions"], vm)
            oo_denoms[oo["denominator"]] += 1
        if t == "missing_action":
            ma_actions.append((len(rule["actions"]), len(om.actions), len(vm.actions)))
        if t == "incorrect_actor":
            ia = scorer.incorrect_actor(rule["actions"], rule["actors"], vm,
                                        rule.get("actor_action_pairs"))
            ia_reasons[ia.get("reason") or "observable"] += 1

    print("out_of_order DENOMINATOR on the mutated BPMN (primary gamma=0.8):")
    for denom, count in sorted(oo_denoms.items()):
        print(f"    denominator={denom:<4} x{count}   "
              f"{'<-- type UNOBSERVABLE (no order relation maps)' if denom == 0 else ''}")
    print()
    print("missing_action observable inputs (rule_actions, original_model_actions,"
          " mutated_model_actions):")
    changed = sum(1 for r, o, m in ma_actions if o != m)
    print(f"    items where the mutation changed the model action count: "
          f"{changed}/{len(ma_actions)}")
    for r, o, m in ma_actions[:10]:
        flag = "CHANGED" if o != m else "UNCHANGED"
        print(f"      rule={r:<3} orig_model={o:<3} mut_model={m:<3}  {flag}")
    print()
    print("incorrect_actor observability reason on the mutated BPMN:")
    for reason, count in ia_reasons.most_common():
        print(f"    {reason:<45} x{count}")
    print()
    print("Interpretation: a benchmark item is only usable if the detector can")
    print("OBSERVE the type AND the original process is compliant AND the")
    print("mutation makes it violate.  If the original already violates, the")
    print("panel measures nothing about the mutation.")
    return 0


def _score(scorer, rule, model, target: str) -> dict[str, Any]:
    if target == "missing_action":
        r = scorer.missing_action(rule["actions"], model)
        return {"score": r["score"], "observable": r["score"] is not None}
    if target == "incorrect_actor":
        r = scorer.incorrect_actor(rule["actions"], rule["actors"], model,
                                   rule.get("actor_action_pairs"))
        return {"score": r["score"], "observable": bool(r.get("observable"))}
    r = scorer.out_of_order(rule["order_relations"], rule["actions"], model)
    return {"score": r["score"], "observable": r["score"] is not None}


if __name__ == "__main__":
    raise SystemExit(main())
