"""Paper-level Sun-strength H1 simulation via controlled perturbation.

PURPOSE: Draw a B0-strength vs H1/D1 performance curve to determine the
B0 F1 threshold at which H1 (B0 + LLM) starts to beat D1 (LLM alone).

THIS IS A SIMULATION, NOT A REAL BENCHMARK.
- It uses previously-cached D1 candidates (no new LLM calls).
- It synthesizes "B0 of strength p" by perturbing Gold clauses.
- The perturbation model approximates B0's actual error distribution
  (50% wrong modality, 30% wrong text, 20% deletion) but is NOT a faithful
  reproduction of any specific B0.

OUTPUT: Per-p F1, plus the "real B0" reference point.
DISCLOSURE: All outputs must be clearly labelled as simulation, never
as real benchmark. This is supplementary material for the paper.

Usage:
  python scripts/run_sun_strength_simulation.py
"""
import argparse
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

GOLD_PATH = ROOT / "data/development/human_review/estg_150_human_correction_v1.json"
D1_OUTPUT = ROOT / "outputs/paper_d1_pilot/d1_full150/d1_predicted_150.json"
B0_V10A_PATH = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json"
DEFAULT_OUT_DIR = ROOT / "outputs" / "paper_sun_strength_simulation"

ALL_MODALITIES = ["permission", "obligation", "prohibition", "definition"]

# Perturbation distribution matching real B0 error profile (FP=92, FN=67)
# 50% wrong modality, 30% wrong text, 20% delete
PERTURBATION_TYPES = (
    ["wrong_modality"] * 50 +
    ["wrong_text"]     * 30 +
    ["delete"]         * 20
)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_gold():
    with open(GOLD_PATH, encoding="utf-8") as f:
        d = json.load(f)
    out = {}
    for r in d.get("records", []):
        hc = r.get("human_correction", {}) or {}
        text = hc.get("approved_text_en") or r.get("approved_text_en") or ""
        clauses = []
        for c in (hc.get("clauses") or []):
            mod = c.get("modality", {}) or {}
            if not isinstance(mod, dict):
                continue
            mod_value = mod.get("value")
            mod_decision = mod.get("decision")
            if mod_decision not in ("accepted", "edited"):
                continue
            if mod_value not in ALL_MODALITIES:
                continue
            cspan = c.get("clause_span", {}) or {}
            clauses.append({
                "clause_id": c.get("clause_id"),
                "clause_text": cspan.get("text", ""),
                "modality": mod_value,
            })
        out[r["sample_id"]] = {
            "sample_id": r["sample_id"],
            "approved_text_en": text,
            "gold_clauses": clauses,
        }
    return out


def load_real_b0():
    with open(B0_V10A_PATH, encoding="utf-8") as f:
        d = json.load(f)
    out = {}
    for r in d:
        sid = r.get("sample_id")
        rec = r.get("record", {}) or {}
        clauses = []
        for c in (rec.get("clauses") or []):
            mod = (c.get("modality") or {}).get("label")
            if mod not in ALL_MODALITIES:
                continue
            cspan = c.get("clause_span", {}) or {}
            text = cspan.get("text", "")
            if not text:
                continue
            clauses.append({"clause_id": c.get("clause_id"), "clause_text": text, "modality": mod})
        out[sid] = clauses
    return out


def load_d1_candidates():
    """Read D1 candidates from aggregated D1 predicted file.
    D1 here = LLM-only prediction from a real DeepSeek V4 Pro call (no B0 hint).
    """
    with open(D1_OUTPUT, encoding="utf-8") as f:
        d = json.load(f)
    out = {}
    for sid, preds in d.get("predicted", {}).items():
        d1_clauses = []
        for p in (preds or []):
            d1_clauses.append({
                "clause_text": p.get("clause_text", ""),
                "modality": p.get("modality"),
            })
        out[sid] = d1_clauses
    return out


# ---------------------------------------------------------------------------
# Perturbation simulator
# ---------------------------------------------------------------------------
def perturb_gold_to_simulated_b0(gold_clauses, p, rng):
    """For each Gold clause, with probability p apply one of 3 perturbations.
    Returns the simulated B0 clause list.
    """
    out = []
    for gc in gold_clauses:
        if rng.random() < p:
            kind = rng.choice(PERTURBATION_TYPES)
            if kind == "wrong_modality":
                wrong = rng.choice([m for m in ALL_MODALITIES if m != gc["modality"]])
                out.append({
                    "clause_text": gc["clause_text"],
                    "modality": wrong,
                    "_perturbation": "wrong_modality",
                })
            elif kind == "wrong_text":
                out.append({
                    "clause_text": "[" + rng.choice(["a", "b", "c"]) + "]",  # unmatchable
                    "modality": gc["modality"],
                    "_perturbation": "wrong_text",
                })
            else:  # delete
                pass  # B0 missed this clause
        else:
            out.append({
                "clause_text": gc["clause_text"],
                "modality": gc["modality"],
                "_perturbation": "none",
            })
    return out


# ---------------------------------------------------------------------------
# Alignment + evaluation
# ---------------------------------------------------------------------------
def text_iou(a, b):
    ta = set((a or "").lower().split())
    tb = set((b or "").lower().split())
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union)


def best_effort_align(predicted_clauses, gold_clauses, iou_threshold=0.3):
    used_pi, used_gi = set(), set()
    pairs = []
    scored = []
    for pi, pc in enumerate(predicted_clauses):
        for gi, gc in enumerate(gold_clauses):
            iou = text_iou(pc.get("clause_text", ""), gc.get("clause_text", ""))
            scored.append((iou, pi, gi))
    scored.sort(reverse=True)
    for iou, pi, gi in scored:
        if pi in used_pi or gi in used_gi:
            continue
        if iou < iou_threshold:
            break
        pairs.append({"pred_idx": pi, "gold_idx": gi, "iou": round(iou, 4)})
        used_pi.add(pi)
        used_gi.add(gi)
    unmatched_pred = [pc for pi, pc in enumerate(predicted_clauses) if pi not in used_pi]
    unmatched_gold = [gc for gi, gc in enumerate(gold_clauses) if gi not in used_gi]
    return pairs, unmatched_pred, unmatched_gold


def evaluate_modality(predicted_clauses, gold_clauses):
    if not gold_clauses and not predicted_clauses:
        return None
    if not gold_clauses:
        return {"tp": 0, "fp": len(predicted_clauses), "fn": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0,
                "n_pred": len(predicted_clauses), "n_gold": 0, "n_pairs": 0}
    if not predicted_clauses:
        return {"tp": 0, "fp": 0, "fn": len(gold_clauses), "precision": 0.0, "recall": 0.0, "f1": 0.0,
                "n_pred": 0, "n_gold": len(gold_clauses), "n_pairs": 0}
    pairs, unmatched_pred, unmatched_gold = best_effort_align(predicted_clauses, gold_clauses)
    tp = fp = fn = 0
    for pair in pairs:
        pred_mod = predicted_clauses[pair["pred_idx"]].get("modality")
        gold_mod = gold_clauses[pair["gold_idx"]].get("modality")
        if pred_mod == gold_mod:
            tp += 1
        else:
            fp += 1
            fn += 1
    fn += len(unmatched_gold)
    fp += len(unmatched_pred)
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
            "n_pred": len(predicted_clauses), "n_gold": len(gold_clauses), "n_pairs": len(pairs)}


def combine_b0_llm(b0_clauses, llm_clauses, dedup_iou=0.5):
    """Naive union: keep B0's clauses + add LLM's clauses that don't IoU-match."""
    out = [dict(bc, source="B0") for bc in b0_clauses]
    for lc in llm_clauses:
        matched = any(
            text_iou(bc.get("clause_text", ""), lc.get("clause_text", "")) >= dedup_iou
            for bc in b0_clauses
        )
        if not matched:
            out.append(dict(lc, source="LLM"))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p-values", type=str, default="0.05,0.10,0.20,0.30,0.50,0.67")
    ap.add_argument("--n-seeds", type=int, default=5)
    ap.add_argument("--out", type=str, default=str(DEFAULT_OUT_DIR))
    args = ap.parse_args()

    p_values = [float(x) for x in args.p_values.split(",")]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Sun-strength H1 Simulation (controlled perturbation)")
    print("=" * 60)
    print(f"  p values: {p_values}")
    print(f"  seeds per p: {args.n_seeds}")
    print(f"  perturbation mix: 50% wrong_modality, 30% wrong_text, 20% delete")
    print()

    gold = load_gold()
    d1_cands = load_d1_candidates()
    real_b0 = load_real_b0()

    # Filter samples that have D1 candidates (148 of 150 from previous run)
    sample_ids = [sid for sid in gold.keys() if sid in d1_cands]
    print(f"  Gold: {len(gold)} samples")
    print(f"  D1 candidates: {len(d1_cands)} samples")
    print(f"  Real B0: {len(real_b0)} samples")
    print(f"  Simulating on: {len(sample_ids)} samples")
    print()

    # ------------------------------------------------------------------
    # Reference point: real B0 + D1 (cached)
    # ------------------------------------------------------------------
    print("Computing reference: real B0 v10a + D1 (cached)...")
    real_b0_b0 = []
    real_b0_d1 = []
    real_b0_h1 = []
    for sid in sample_ids:
        b0_c = real_b0.get(sid, [])
        d1_c = d1_cands.get(sid, [])
        h1_c = combine_b0_llm(b0_c, d1_c)
        gold_c = gold[sid]["gold_clauses"]
        real_b0_b0.append(evaluate_modality(b0_c, gold_c))
        real_b0_d1.append(evaluate_modality(d1_c, gold_c))
        real_b0_h1.append(evaluate_modality(h1_c, gold_c))

    def micro_f1(eval_list):
        tp = sum(e["tp"] for e in eval_list if e)
        fp = sum(e["fp"] for e in eval_list if e)
        fn = sum(e["fn"] for e in eval_list if e)
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}

    ref_b0 = micro_f1(real_b0_b0)
    ref_d1 = micro_f1(real_b0_d1)
    ref_h1 = micro_f1(real_b0_h1)
    print(f"  Real B0 F1 = {ref_b0['f1']:.4f}  (D1 cached, H1 = B0 ∪ D1)")
    print(f"  Real D1 F1 = {ref_d1['f1']:.4f}")
    print(f"  Real H1 F1 = {ref_h1['f1']:.4f}")
    print()

    # ------------------------------------------------------------------
    # Perturbation sweep
    # ------------------------------------------------------------------
    print("=" * 60)
    print("Perturbation sweep (per p, mean ± std over seeds)")
    print("=" * 60)
    curve = []  # list of dicts
    for p in p_values:
        sim_b0_f1s = []
        sim_h1_f1s = []
        for seed in range(args.n_seeds):
            rng = random.Random(seed * 1000 + int(p * 100))
            per_sample_b0 = []
            per_sample_h1 = []
            for sid in sample_ids:
                gold_c = gold[sid]["gold_clauses"]
                sim_b0 = perturb_gold_to_simulated_b0(gold_c, p, rng)
                d1_c = d1_cands.get(sid, [])
                h1 = combine_b0_llm(sim_b0, d1_c)
                per_sample_b0.append(evaluate_modality(sim_b0, gold_c))
                per_sample_h1.append(evaluate_modality(h1, gold_c))
            sim_b0_f1s.append(micro_f1(per_sample_b0)["f1"])
            sim_h1_f1s.append(micro_f1(per_sample_h1)["f1"])
        b0_mean = statistics.mean(sim_b0_f1s)
        b0_std = statistics.stdev(sim_b0_f1s) if len(sim_b0_f1s) > 1 else 0.0
        h1_mean = statistics.mean(sim_h1_f1s)
        h1_std = statistics.stdev(sim_h1_f1s) if len(sim_h1_f1s) > 1 else 0.0
        curve.append({
            "p": p,
            "b0_f1_mean": round(b0_mean, 4),
            "b0_f1_std": round(b0_std, 4),
            "h1_f1_mean": round(h1_mean, 4),
            "h1_f1_std": round(h1_std, 4),
            "n_seeds": args.n_seeds,
        })
        print(f"  p={p:.2f}  B0_sim F1 = {b0_mean:.4f} ± {b0_std:.4f}  |  H1 F1 = {h1_mean:.4f} ± {h1_std:.4f}  |  H1 vs D1 ({ref_d1['f1']:.4f}) delta = {h1_mean - ref_d1['f1']:+.4f}")

    # ------------------------------------------------------------------
    # Threshold: where does H1 first beat D1?
    # ------------------------------------------------------------------
    print()
    threshold = None
    for row in curve:
        if row["h1_f1_mean"] > ref_d1["f1"]:
            threshold = row
            break
    if threshold:
        print(f"  >>> H1 first exceeds D1 at p = {threshold['p']}  (B0_sim F1 = {threshold['b0_f1_mean']:.4f}, H1 F1 = {threshold['h1_f1_mean']:.4f})")
    else:
        print(f"  >>> H1 does not exceed D1 at any tested p value")

    print()
    print("Reference:")
    print(f"  D1 F1 (cached, real LLM) = {ref_d1['f1']:.4f}")
    print(f"  Real B0 v10a F1 = {ref_b0['f1']:.4f}")
    print()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    out_file = out_dir / "sun_strength_simulation_results.json"
    summary = {
        "experiment_type": "controlled_perturbation_simulation",
        "n_samples": len(sample_ids),
        "n_seeds_per_p": args.n_seeds,
        "perturbation_mix": {"wrong_modality": 0.50, "wrong_text": 0.30, "delete": 0.20},
        "reference": {
            "real_b0_v10a_f1": ref_b0["f1"],
            "real_d1_cached_f1": ref_d1["f1"],
            "real_h1_f1": ref_h1["f1"],
        },
        "curve": curve,
        "h1_exceeds_d1_at": threshold,
        "disclosure": (
            "Controlled perturbation simulation. NOT a real benchmark. "
            "We use Gold as 'ideal B0', then synthetically perturb with probability p "
            "to simulate a 'B0 of accuracy p'. Perturbation mix (50/30/20) matches the "
            "real B0 v10a error profile. D1 candidates are cached from a previous real LLM "
            "run (DeepSeek V4 Pro, 150 samples, see paper_pilot event). "
            "H1 here uses the same naive union + IoU dedup as the real H1 run. "
            "Result is illustrative: identifies B0 F1 threshold above which H1 > D1. "
            "Real B0 improvement is future work."
        ),
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()
