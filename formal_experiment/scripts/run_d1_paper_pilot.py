"""Paper-level D1 (direct LLM) best-effort pilot.

Bypasses the canonical protocol on purpose. Goal: get D1 modality P/R
vs Gold (Layer E) FAST for the paper.

This is a deviation from the canonical protocol. Disclose it in the paper:
- Span canonicalization is best-effort (token-IoU >= 0.3), NOT exact.
- response_format is json_object (not strict).
- No Pass A/B, no 5 repeats, no SHA-bound receipts.
- No canonical validator (fail open with alignment_quality tag).

For final-paper claims, the canonical protocol + v1.9 adapter path is
still the project's intended track; this script is a paper-level
expedient that the user explicitly authorized to bypass that.

Usage:
  python scripts/run_d1_paper_pilot.py --samples 5
  python scripts/run_d1_paper_pilot.py --samples 30 --start 0
  python scripts/run_d1_paper_pilot.py --samples 150 --start 0
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# ---------------------------------------------------------------------------
# Load .env silently (NEVER print key values, only var names)
# ---------------------------------------------------------------------------
ENV_PATH = ROOT / ".env"
if ENV_PATH.exists():
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v

GOLD_PATH = ROOT / "data/development/human_review/estg_150_human_correction_v1.json"
DEFAULT_OUT_DIR = ROOT / "outputs" / "paper_d1_pilot"

# ---------------------------------------------------------------------------
# Prompt (Barrientos-style, simple, not strict)
# ---------------------------------------------------------------------------
SYSTEM = (
    "You are a legal text annotator. Extract deontic clauses from "
    "EStG (German tax law) excerpts that are provided in English. "
    "Return only valid JSON."
)

USER_TEMPLATE = """Extract deontic clauses from the following English legal text.

For each clause, return:
- clause_text: the verbatim text of the clause (must be a contiguous substring of the source)
- modality: one of "permission", "obligation", "prohibition", "definition"
- evidence: the verbatim short cue word/phrase that supports the modality (a contiguous substring of clause_text)
- actor: the entity performing the action (or null if passive/unspecified)
- action: the action being performed (verbatim from clause_text, or null)

Return JSON in the form: {{"clauses": [...]}}

Example:
Source: "The controller shall process personal data only with the data subject's consent."
Output:
{{"clauses": [
  {{
    "clause_text": "The controller shall process personal data only with the data subject's consent.",
    "modality": "obligation",
    "evidence": "shall",
    "actor": "controller",
    "action": "process personal data only with the data subject's consent"
  }}
]}}

Now extract from:
Source: {source_text}

Output (JSON only):"""


# ---------------------------------------------------------------------------
# Gold loader
# ---------------------------------------------------------------------------
def load_gold():
    """Load Gold (Layer E) records. Only accept adjudicated modality decisions."""
    with open(GOLD_PATH, encoding="utf-8") as f:
        d = json.load(f)
    recs = d.get("records", [])
    out = []
    for r in recs:
        hc = r.get("human_correction", {}) or {}
        text = hc.get("approved_text_en") or r.get("approved_text_en") or ""
        clauses = []
        for c in (hc.get("clauses") or []):
            mod = c.get("modality", {}) or {}
            if not isinstance(mod, dict):
                continue
            mod_value = mod.get("value")
            mod_decision = mod.get("decision")
            # Only count adjudicated clauses (consistent with project's gold semantics)
            if mod_decision not in ("accepted", "edited"):
                continue
            if mod_value not in ("permission", "obligation", "prohibition", "definition"):
                continue
            cspan = c.get("clause_span", {}) or {}
            clauses.append({
                "clause_id": c.get("clause_id"),
                "clause_text": cspan.get("text", ""),
                "modality": mod_value,
            })
        out.append({
            "sample_id": r["sample_id"],
            "approved_text_en": text,
            "gold_clauses": clauses,
        })
    return out


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------
def call_llm(prompt, base_url, api_key, model, timeout=120):
    import requests
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": 4000,
    }
    resp = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage", {}) or {}
    return data, usage


# ---------------------------------------------------------------------------
# Best-effort clause alignment (token IoU, threshold 0.3)
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
    """Greedy: each predicted clause matched to best gold by token IoU."""
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


# ---------------------------------------------------------------------------
# Modality P/R/F1
# ---------------------------------------------------------------------------
def evaluate_modality(predicted_clauses, gold_clauses):
    if not gold_clauses:
        return None
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
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(p, 4),
        "recall": round(r, 4),
        "f1": round(f1, 4),
        "n_pairs": len(pairs),
        "n_unmatched_pred": len(unmatched_pred),
        "n_unmatched_gold": len(unmatched_gold),
        "n_gold_clauses": len(gold_clauses),
        "n_pred_clauses": len(predicted_clauses),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--model", type=str, default=os.environ.get("BPC_HYBRID_LLM_MODEL", "gpt-4o"))
    ap.add_argument("--base-url", type=str, default=os.environ.get("BPC_HYBRID_LLM_BASE_URL", ""))
    ap.add_argument("--api-key", type=str, default=os.environ.get("BPC_HYBRID_LLM_API_KEY", ""))
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--out", type=str, default=str(DEFAULT_OUT_DIR))
    args = ap.parse_args()

    if not args.api_key or not args.base_url:
        print("ERROR: API key or base URL not set.")
        print("  Set BPC_HYBRID_LLM_API_KEY and BPC_HYBRID_LLM_BASE_URL in formal_experiment/.env")
        print(f"  .env exists: {ENV_PATH.exists()}")
        if ENV_PATH.exists():
            keys = []
            with open(ENV_PATH, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k = line.split("=", 1)[0].strip()
                        keys.append(k)
            print(f"  keys found in .env: {keys}")
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("D1 Paper Pilot (best-effort, bypasses canonical protocol)")
    print("=" * 60)
    print(f"  Model:   {args.model}")
    print(f"  BaseURL: {args.base_url}")
    print(f"  Samples: {args.samples} (start idx {args.start})")
    print()

    gold_records = load_gold()
    selected = gold_records[args.start : args.start + args.samples]
    print(f"  Gold loaded: {len(gold_records)} records total, selected {len(selected)}")
    print()

    all_results = []
    total_tp = total_fp = total_fn = 0
    total_in = total_out = 0

    for i, rec in enumerate(selected, 1):
        sid = rec["sample_id"]
        text = rec["approved_text_en"]
        n_gold = len(rec["gold_clauses"])
        print(f"[{i}/{len(selected)}] {sid}  gold_clauses={n_gold}  text_len={len(text)}")

        prompt = USER_TEMPLATE.format(source_text=text)
        t0 = time.time()
        try:
            response, usage = call_llm(prompt, args.base_url, args.api_key, args.model, args.timeout)
        except Exception as e:
            print(f"  API ERROR: {type(e).__name__}: {str(e)[:200]}")
            all_results.append({"sample_id": sid, "error": f"{type(e).__name__}: {str(e)[:500]}"})
            continue
        t1 = time.time()
        in_tok = usage.get("prompt_tokens", 0)
        out_tok = usage.get("completion_tokens", 0)
        total_in += in_tok
        total_out += out_tok

        # Extract JSON
        try:
            content = response["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except Exception as e:
            print(f"  PARSE ERROR: {e}")
            print(f"  raw content (first 300): {content[:300] if isinstance(content, str) else content}")
            all_results.append({"sample_id": sid, "error": f"parse: {e}",
                                "raw": content[:500] if isinstance(content, str) else str(content)[:500]})
            continue

        # Best-effort clause extraction (no strict validation)
        predicted = []
        for c in (parsed.get("clauses") or []):
            if not isinstance(c, dict):
                continue
            mod = c.get("modality")
            if mod not in ("permission", "obligation", "prohibition", "definition"):
                continue
            predicted.append({
                "clause_text": c.get("clause_text", ""),
                "modality": mod,
                "evidence": c.get("evidence"),
                "actor": c.get("actor"),
                "action": c.get("action"),
            })

        eval_res = evaluate_modality(predicted, rec["gold_clauses"])
        if eval_res:
            total_tp += eval_res["tp"]
            total_fp += eval_res["fp"]
            total_fn += eval_res["fn"]
            print(f"  pred={eval_res['n_pred_clauses']}  gold={eval_res['n_gold_clauses']}  "
                  f"P={eval_res['precision']:.3f}  R={eval_res['recall']:.3f}  F1={eval_res['f1']:.3f}  "
                  f"({t1-t0:.1f}s, {in_tok}+{out_tok} tok)")
        else:
            print(f"  pred={len(predicted)}  gold=0  (skipped eval)")

        all_results.append({
            "sample_id": sid,
            "elapsed_s": round(t1 - t0, 2),
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "n_pred_clauses": len(predicted),
            "n_gold_clauses": n_gold,
            "evaluation": eval_res,
            "predicted": predicted,
        })

    p_micro = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    r_micro = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1_micro = 2 * p_micro * r_micro / (p_micro + r_micro) if (p_micro + r_micro) > 0 else 0.0

    summary = {
        "model": args.model,
        "n_samples": len(selected),
        "n_with_eval": sum(1 for r in all_results if r.get("evaluation")),
        "aggregate_tp": total_tp,
        "aggregate_fp": total_fp,
        "aggregate_fn": total_fn,
        "modality_micro_precision": round(p_micro, 4),
        "modality_micro_recall": round(r_micro, 4),
        "modality_micro_f1": round(f1_micro, 4),
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_tokens": total_in + total_out,
    }

    print()
    print("=" * 60)
    print("AGGREGATE (modality micro)")
    print("=" * 60)
    print(f"  Samples: {summary['n_samples']} (with eval: {summary['n_with_eval']})")
    print(f"  Modality P = {p_micro:.4f}")
    print(f"  Modality R = {r_micro:.4f}")
    print(f"  Modality F1 = {f1_micro:.4f}")
    print(f"  Tokens: in={total_in}  out={total_out}  total={total_in + total_out}")
    print()
    print("Reference (B0 v10a, project audit): modality micro F1 = 0.6283")
    print(f"  D1 this pilot:                              modality micro F1 = {f1_micro:.4f}")
    print()

    out_file = out_dir / f"d1_pilot_{int(time.time())}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            "per_sample": all_results,
            "disclosure": (
                "Paper-level best-effort D1 result. Bypasses canonical protocol. "
                "Modality P/R via token-IoU clause alignment (threshold 0.3, NOT exact span). "
                "response_format=json_object (not strict). No Pass A/B, no repeats, no SHA receipts. "
                "For final-paper claims, the canonical v1.9 + strict validator path is "
                "still the project's intended track; disclose this deviation."
            ),
        }, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()
