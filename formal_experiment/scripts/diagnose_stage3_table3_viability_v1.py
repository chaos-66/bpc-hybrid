# -*- coding: utf-8 -*-
"""READ-ONLY Stage 3 benchmark viability diagnostic (zero API, zero writes).

Question: can the existing 30-item real-mutation panel
(``synthetic_controlled_error_extension_v1``) actually support the paper's
Table 3?

A benchmark is only viable if, for every item:
  1. the ORIGINAL (unmutated) BPMN scores as COMPLIANT for the mutation's
     target violation type, and
  2. the MUTATED BPMN scores as VIOLATING for that type,
  3. and the detector can actually OBSERVE that type at all.

This script measures (1)-(3) with the frozen Sun Stage 3 reconstruction
(``SunScorer``, gamma=0.8, the config's primary threshold) on both BPMNs of
every item, and reports the resulting 2x2 separability table plus the
observability failure reasons.

Nothing is written. No LLM/API is called.
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


def _rule_text(rule_id: str) -> str:
    for item in _load(INFERENCE_PACK).get("matching_items", []):
        if item["rule_id"] == rule_id:
            return item["rule_text"]
    raise RuntimeError(f"no rule text for {rule_id}")


def main() -> int:
    panel = _load(PANEL)
    config = _load(SUN_CONFIG)
    thresholds = config["method"]["thresholds"]
    gamma = float(thresholds["gamma"])
    tau = float(thresholds["tau"])
    theta = float(thresholds["theta"])

    print(f"panel          : {panel['panel_id']} ({panel['status']})")
    print(f"Sun thresholds : tau={tau} gamma={gamma} theta={theta}")
    print(f"variants       : {len(panel['variants'])}")
    print()

    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    scorer = SunScorer(sim, tau, gamma, theta, nlp=nlp)

    signal_path = (ROOT.parent / "references" / "winter_2020_model_check"
                   / "model_check" / "input" / "files" / "signalwords.txt")
    signalwords = [w.strip() for w in signal_path.read_text(
        encoding="utf-8", errors="replace").splitlines() if w.strip()]

    rule_cache: dict[str, Any] = {}
    model_cache: dict[tuple[str, str], Any] = {}

    def model_for(bpmn_path: Path, pid: str):
        key = (str(bpmn_path), pid)
        if key not in model_cache:
            record = parse_bpmn_file(bpmn_path, contract=contract)
            model_cache[key] = SunProcessModel(pid, record, nlp)
        return model_cache[key]

    def evaluate(bpmn_path: Path, pid: str, rule_id: str) -> dict[str, Any]:
        if rule_id not in rule_cache:
            rule_cache[rule_id] = extract_rule_record(
                rule_id, _rule_text(rule_id), nlp, signalwords)
        rule = rule_cache[rule_id]
        model = model_for(bpmn_path, pid)
        ma = scorer.missing_action(rule["actions"], model)
        ia = scorer.incorrect_actor(rule["actions"], rule["actors"], model,
                                    rule.get("actor_action_pairs"))
        oo = scorer.out_of_order(rule["order_relations"], rule["actions"],
                                 model)
        return {"missing_action": ma, "incorrect_actor": ia,
                "out_of_order": oo}

    rows: list[dict[str, Any]] = []
    for variant in panel["variants"]:
        pid = variant["process_id"]
        rule_id = variant["rule_id"]
        original = ROOT / variant["source_bpmn"]
        mutated = ROOT / variant["variant_bpmn"]
        target = variant["mutation_type"]
        if not original.is_file() or not mutated.is_file():
            print(f"  MISSING BPMN for {variant['variant_id']}")
            continue
        base = evaluate(original, pid, rule_id)
        var = evaluate(mutated, pid, rule_id)
        row = {
            "variant_id": variant["variant_id"],
            "process_id": pid,
            "rule_id": rule_id,
            "target_type": target,
            "target_activity_id": variant.get("target_activity_id"),
        }
        for t in TYPES:
            row[f"orig_{t}_score"] = base[t]["score"]
            row[f"var_{t}_score"] = var[t]["score"]
            # a type is observable when the detector produced a score at all
            # (incorrect_actor reports observable=False + a reason when its
            # precondition fails; the other two report score=None)
            row[f"orig_{t}_observable"] = bool(
                base[t].get("observable", base[t]["score"] is not None))
            row[f"var_{t}_observable"] = bool(
                var[t].get("observable", var[t]["score"] is not None))
            row[f"var_{t}_reason"] = var[t].get("reason")
            row[f"orig_{t}_reason"] = base[t].get("reason")
            row[f"var_{t}_denominator"] = var[t].get("denominator")
        rows.append(row)

    print("=" * 100)
    print("PER-ITEM SEPARABILITY (Sun reconstruction; violation iff score > 0)")
    print("=" * 100)
    header = (f"{'variant':<24}{'target':<17}{'orig':>7}{'mut':>7}"
              f"{'separable':>11}  {'mut_observable':>15}")
    print(header)
    print("-" * 100)
    separable = defaultdict(int)
    total = defaultdict(int)
    observable = defaultdict(int)
    for row in rows:
        t = row["target_type"]
        total[t] += 1
        o = row[f"orig_{t}_score"]
        m = row[f"var_{t}_score"]
        obs = row[f"var_{t}_observable"]
        if obs:
            observable[t] += 1
        ok = (o == 0.0) and (m is not None and m > 0.0) and obs
        if ok:
            separable[t] += 1
        print(f"{row['variant_id']:<24}{t:<17}"
              f"{('n/a' if o is None else f'{o:.3f}'):>7}"
              f"{('n/a' if m is None else f'{m:.3f}'):>7}"
              f"{('YES' if ok else 'no'):>11}  {str(obs):>15}")

    print()
    print("=" * 100)
    print("SUMMARY — items that are CLEANLY SEPARABLE (original compliant AND "
          "mutated violating AND observable)")
    print("=" * 100)
    for t in TYPES:
        print(f"  {t:<18} {separable[t]:>2}/{total[t]:<2} separable   "
              f"({observable[t]}/{total[t]} mutated observable)")
    print()

    print("=" * 100)
    print("OBSERVABILITY FAILURE REASONS ON THE MUTATED BPMN")
    print("=" * 100)
    reasons = Counter()
    for row in rows:
        t = row["target_type"]
        if not row[f"var_{t}_observable"]:
            reasons[(t, row[f"var_{t}_reason"])] += 1
    if not reasons:
        print("  none")
    for (t, reason), count in sorted(reasons.items()):
        print(f"  {t:<18} {str(reason):<45} x{count}")
    print()

    print("=" * 100)
    print("CROSS-TYPE CONTAMINATION — does a mutation also fire the OTHER "
          "types? (mutated score > 0)")
    print("=" * 100)
    for t in TYPES:
        print(f"  target={t}")
        for other in TYPES:
            fired = sum(1 for row in rows if row["target_type"] == t
                        and (row[f"var_{other}_score"] or 0) > 0.0)
            print(f"      mutated also fires {other:<18} {fired:>2}/{total[t]}")
    print()

    # wrong-type count over the 30 items as actually predicted
    exact = 0
    predicted_none = 0
    for row in rows:
        t = row["target_type"]
        fired = [k for k in TYPES if (row[f"var_{k}_score"] or 0) > 0.0]
        if fired == [t]:
            exact += 1
        if not fired:
            predicted_none += 1
    print("=" * 100)
    print("END-TO-END SHAPE ON THE MUTATED BPMNS (Sun, primary thresholds)")
    print("=" * 100)
    print(f"  exact single correct type : {exact}/{len(rows)}")
    print(f"  predicted no violation    : {predicted_none}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
