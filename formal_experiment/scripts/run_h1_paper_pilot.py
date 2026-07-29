"""Paper-level H1 (rule + LLM fallback) best-effort pilot.

Bypasses the canonical protocol. Combines:
  - B0 v10a rule-based predictions (from outputs/development/...)
  - LLM (DeepSeek V4 Pro default) clause candidates
  - Naive union: keep B0's clauses, add LLM's clauses that don't IoU-match
  - Modality: B0's wins where available, else LLM's

This is a paper-level expedient, NOT the canonical selective-fallback H1.
Disclose the simplification in the paper.

Usage:
  python scripts/run_h1_paper_pilot.py --samples 5
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
# Load .env silently
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
B0_V10A_PATH = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json"
DEFAULT_OUT_DIR = ROOT / "outputs" / "paper_h1_pilot"

# ---------------------------------------------------------------------------
# Prompt
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

Return JSON in the form: {{"clauses": [...]}}

Example:
Source: "The controller shall process personal data only with the data subject's consent."
Output:
{{"clauses": [
  {{
    "clause_text": "The controller shall process personal data only with the data subject's consent.",
    "modality": "obligation",
    "evidence": "shall"
  }}
]}}

Now extract from:
Source: {source_text}

Output (JSON only):"""


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_gold():
    with open(GOLD_PATH, encoding="utf-8") as f:
        d = json.load(f)
    recs = d.get("records", [])
    out = {}
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
        out[r["sample_id"]] = {
            "sample_id": r["sample_id"],
            "approved_text_en": text,
            "gold_clauses": clauses,
        }
    return out


def load_b0_v10a():
    """Return {sample_id: {'clauses': [{'clause_text', 'modality', 'clause_id'}]}}"""
    with open(B0_V10A_PATH, encoding="utf-8") as f:
        d = json.load(f)
    out = {}
    for r in d:
        sid = r.get("sample_id")
        rec = r.get("record", {}) or {}
        clauses = []
        for c in (rec.get("clauses") or []):
            mod = (c.get("modality") or {}).get("label")
            if mod not in ("permission", "obligation", "prohibition", "definition"):
                continue
            cspan = c.get("clause_span", {}) or {}
            text = cspan.get("text", "")
            if not text:
                continue
            clauses.append({
                "clause_id": c.get("clause_id"),
                "clause_text": text,
                "modality": mod,
            })
        out[sid] = clauses
    return out


# ---------------------------------------------------------------------------
# LLM call (same as D1)
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
# Token IoU
# ---------------------------------------------------------------------------
def text_iou(a, b):
    ta = set((a or "").lower().split())
    tb = set((b or "").lower().split())
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union)


def best_match_score(a, b):
    """Token IoU or substring containment. Either is a match."""
    a_l = (a or "").lower()
    b_l = (b or "").lower()
    if not a_l or not b_l:
        return 0.0
    if a_l in b_l or b_l in a_l:
        return 1.0  # substring containment = perfect match
    return text_iou(a, b)


# ---------------------------------------------------------------------------
# H1 combination: B0 ∪ LLM (deduped by IoU >= 0.5)
# ---------------------------------------------------------------------------
def combine_b0_llm(b0_clauses, llm_clauses, dedup_iou=0.5):
    """Union B0 and LLM. Dedup ONLY by token IoU (not substring containment,
    because B0 splits clauses into pieces and substring would falsely dedup).
    Modality: B0 wins on overlap.
    """
    out = [dict(bc, source="B0") for bc in b0_clauses]
    for lc in llm_clauses:
        matched = any(
            text_iou(bc.get("clause_text", ""), lc.get("clause_text", "")) >= dedup_iou
            for bc in b0_clauses
        )
        if not matched:
            out.append({**lc, "source": "LLM"})
    return out


# ---------------------------------------------------------------------------
# Modality P/R/F1 (modality IoU alignment threshold 0.3)
# ---------------------------------------------------------------------------
def best_effort_align(predicted_clauses, gold_clauses, iou_threshold=0.3):
    used_pi, used_gi = set(), set()
    pairs = []
    scored = []
    for pi, pc in enumerate(predicted_clauses):
        for gi, gc in enumerate(gold_clauses):
            score = best_match_score(pc.get("clause_text", ""), gc.get("clause_text", ""))
            scored.append((score, pi, gi))
    scored.sort(reverse=True)
    for score, pi, gi in scored:
        if pi in used_pi or gi in used_gi:
            continue
        if score < iou_threshold:
            break
        pairs.append({"pred_idx": pi, "gold_idx": gi, "score": round(score, 4)})
        used_pi.add(pi)
        used_gi.add(gi)
    unmatched_pred = [pc for pi, pc in enumerate(predicted_clauses) if pi not in used_pi]
    unmatched_gold = [gc for gi, gc in enumerate(gold_clauses) if gi not in used_gi]
    return pairs, unmatched_pred, unmatched_gold


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
        print("ERROR: API key or base URL not set in .env")
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("H1 Paper Pilot (B0 v10a + LLM fallback union)")
    print("=" * 60)
    print(f"  Model:   {args.model}")
    print(f"  BaseURL: {args.base_url}")
    print(f"  Samples: {args.samples} (start idx {args.start})")
    print()

    gold = load_gold()
    b0 = load_b0_v10a()
    sample_ids = list(gold.keys())
    selected_ids = sample_ids[args.start : args.start + args.samples]
    print(f"  Gold loaded: {len(gold)} records")
    print(f"  B0 v10a loaded: {len(b0)} records")
    print(f"  Selected: {len(selected_ids)}")
    print()

    all_results = []
    # Track three evaluations per sample: B0 only, D1 (LLM only), H1 (B0+LLM)
    totals = {
        "b0": {"tp": 0, "fp": 0, "fn": 0},
        "d1": {"tp": 0, "fp": 0, "fn": 0},
        "h1": {"tp": 0, "fp": 0, "fn": 0},
    }
    total_in = total_out = 0
    parse_errors = 0

    for i, sid in enumerate(selected_ids, 1):
        rec = gold[sid]
        text = rec["approved_text_en"]
        n_gold = len(rec["gold_clauses"])
        b0_clauses = b0.get(sid, [])
        print(f"[{i}/{len(selected_ids)}] {sid}  gold={n_gold}  B0={len(b0_clauses)}")

        # LLM call
        prompt = USER_TEMPLATE.format(source_text=text)
        t0 = time.time()
        try:
            response, usage = call_llm(prompt, args.base_url, args.api_key, args.model, args.timeout)
        except Exception as e:
            print(f"  API ERROR: {type(e).__name__}: {str(e)[:200]}")
            all_results.append({"sample_id": sid, "error": f"api: {e}"})
            continue
        t1 = time.time()
        in_tok = usage.get("prompt_tokens", 0)
        out_tok = usage.get("completion_tokens", 0)
        total_in += in_tok
        total_out += out_tok

        # Parse LLM
        try:
            content = response["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except Exception as e:
            parse_errors += 1
            print(f"  PARSE ERROR: {e}")
            all_results.append({"sample_id": sid, "error": f"parse: {e}",
                                "raw": content[:300] if isinstance(content, str) else str(content)[:300]})
            # still evaluate B0 alone
            d1_pred = []
            continue

        llm_pred = []
        for c in (parsed.get("clauses") or []):
            if not isinstance(c, dict):
                continue
            mod = c.get("modality")
            if mod not in ("permission", "obligation", "prohibition", "definition"):
                continue
            llm_pred.append({
                "clause_text": c.get("clause_text", ""),
                "modality": mod,
                "evidence": c.get("evidence"),
            })

        # Three evaluations
        b0_eval = evaluate_modality(b0_clauses, rec["gold_clauses"])
        d1_eval = evaluate_modality(llm_pred, rec["gold_clauses"])
        h1_combined = combine_b0_llm(b0_clauses, llm_pred, dedup_iou=0.5)
        h1_eval = evaluate_modality(h1_combined, rec["gold_clauses"])

        # Accumulate
        if b0_eval:
            totals["b0"]["tp"] += b0_eval["tp"]
            totals["b0"]["fp"] += b0_eval["fp"]
            totals["b0"]["fn"] += b0_eval["fn"]
        if d1_eval:
            totals["d1"]["tp"] += d1_eval["tp"]
            totals["d1"]["fp"] += d1_eval["fp"]
            totals["d1"]["fn"] += d1_eval["fn"]
        if h1_eval:
            totals["h1"]["tp"] += h1_eval["tp"]
            totals["h1"]["fp"] += h1_eval["fp"]
            totals["h1"]["fn"] += h1_eval["fn"]

        b0_f1 = b0_eval["f1"] if b0_eval else 0.0
        d1_f1 = d1_eval["f1"] if d1_eval else 0.0
        h1_f1 = h1_eval["f1"] if h1_eval else 0.0
        print(f"  B0={len(b0_clauses)}  LLM={len(llm_pred)}  H1={len(h1_combined)}  | "
              f"B0_F1={b0_f1:.3f}  D1_F1={d1_f1:.3f}  H1_F1={h1_f1:.3f}  | "
              f"({t1-t0:.1f}s, {in_tok}+{out_tok} tok)")

        all_results.append({
            "sample_id": sid,
            "elapsed_s": round(t1 - t0, 2),
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "n_gold_clauses": n_gold,
            "n_b0_clauses": len(b0_clauses),
            "n_llm_clauses": len(llm_pred),
            "n_h1_clauses": len(h1_combined),
            "b0_eval": b0_eval,
            "d1_eval": d1_eval,
            "h1_eval": h1_eval,
        })

    def f1_from(t):
        tp, fp, fn = t["tp"], t["fp"], t["fn"]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return round(p, 4), round(r, 4), round(f, 4)

    p_b0, r_b0, f_b0 = f1_from(totals["b0"])
    p_d1, r_d1, f_d1 = f1_from(totals["d1"])
    p_h1, r_h1, f_h1 = f1_from(totals["h1"])

    summary = {
        "model": args.model,
        "n_samples": len(selected_ids),
        "n_with_eval": sum(1 for r in all_results if r.get("b0_eval") and r.get("d1_eval") and r.get("h1_eval")),
        "n_parse_errors": parse_errors,
        "b0": {"p": p_b0, "r": r_b0, "f1": f_b0, **totals["b0"]},
        "d1": {"p": p_d1, "r": r_d1, "f1": f_d1, **totals["d1"]},
        "h1": {"p": p_h1, "r": r_h1, "f1": f_h1, **totals["h1"]},
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_tokens": total_in + total_out,
    }

    print()
    print("=" * 60)
    print("AGGREGATE (modality micro)")
    print("=" * 60)
    print(f"  Samples: {summary['n_samples']} (with eval: {summary['n_with_eval']}, parse errors: {parse_errors})")
    print()
    print(f"  {'method':<10}  {'P':>7}  {'R':>7}  {'F1':>7}")
    print(f"  {'B0 (rule)':<10}  {p_b0:>7.4f}  {r_b0:>7.4f}  {f_b0:>7.4f}")
    print(f"  {'D1 (LLM)':<10}  {p_d1:>7.4f}  {r_d1:>7.4f}  {f_d1:>7.4f}")
    print(f"  {'H1 (B0+LLM)':<10} {p_h1:>7.4f}  {r_h1:>7.4f}  {f_h1:>7.4f}")
    print()
    print(f"  Tokens: in={total_in}  out={total_out}  total={total_in+total_out}")
    print()

    out_file = out_dir / f"h1_pilot_{int(time.time())}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            "per_sample": all_results,
            "disclosure": (
                "Paper-level H1 best-effort. H1 = B0 v10a clauses ∪ LLM clauses, "
                "deduped by token-IoU >= 0.5. Modality: B0's wins on overlap. "
                "Bypasses canonical protocol and selective-fallback H1 design. "
                "Modality P/R via token-IoU clause alignment (threshold 0.3, NOT exact span). "
                "Disclose both simplifications in the paper."
            ),
        }, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()
