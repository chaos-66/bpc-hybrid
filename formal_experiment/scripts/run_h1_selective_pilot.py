"""Paper-level H1 selective (LLM as B0 verifier + completer).

Bypasses canonical protocol. H1 = B0 first; LLM reviews each B0 clause
(keep/correct/remove) AND adds missed clauses.

For each B0 prediction, LLM is asked to:
  - keep      : B0 is correct, leave as-is
  - correct   : B0 is wrong, here is the corrected clause + modality
  - remove    : B0 is wrong AND should be discarded
  - add       : new clause B0 missed entirely

Final H1 = keep ∪ correct.corrected_text ∪ add.

Usage:
  python scripts/run_h1_selective_pilot.py --samples 5
  python scripts/run_h1_selective_pilot.py --samples 150
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

# --- Load .env silently ---
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
DEFAULT_OUT_DIR = ROOT / "outputs" / "paper_h1_selective_pilot"

# ---------------------------------------------------------------------------
# Prompt: LLM-as-verifier
# ---------------------------------------------------------------------------
SYSTEM = (
    "You are a legal text annotator. You will be given a legal text excerpt "
    "and a rule-based system's preliminary clause predictions. Your job is to "
    "review each B0 prediction and either keep / correct / remove it, and to "
    "add any clauses B0 missed. Return only valid JSON."
)

USER_TEMPLATE = """Review the following rule-based predictions for an EStG (German tax law) excerpt and produce a corrected clause set.

For each B0 prediction, decide ONE of:
- "keep"     : B0 is correct (right clause_text AND right modality). Include as-is.
- "correct"  : B0 is wrong in clause_text or modality. Provide the corrected clause_text and corrected_modality.
- "remove"   : B0 is wrong AND should be discarded entirely.

For the source text, also identify any clauses B0 missed entirely:
- "add"      : new clause that B0 did not predict at all.

Modality is one of: "permission", "obligation", "prohibition", "definition"
All clause_text values MUST be a contiguous substring of the source.

Return JSON in this exact form:
{{
  "keep": [{{"clause_text": "...", "modality": "..."}}],
  "correct": [{{"original_text": "...", "corrected_text": "...", "corrected_modality": "..."}}],
  "remove": [{{"original_text": "..."}}],
  "add": [{{"clause_text": "...", "modality": "..."}}]
}}

Example (B0 correct):
Source: "The controller shall process data only with consent. Companies may store anonymized data indefinitely."
B0 predictions:
- "The controller shall process data only with consent" -> obligation
- "Companies may store anonymized data indefinitely" -> permission

Output:
{{"keep": [
  {{"clause_text": "The controller shall process data only with consent", "modality": "obligation"}},
  {{"clause_text": "Companies may store anonymized data indefinitely", "modality": "permission"}}
], "correct": [], "remove": [], "add": []}}

Example (B0 wrong, needs correction):
Source: "The controller shall process data only with consent. Companies may store anonymized data indefinitely."
B0 predictions:
- "shall process" -> obligation
- "Companies may store" -> permission

Output:
{{"keep": [], "correct": [
  {{"original_text": "shall process", "corrected_text": "The controller shall process data only with consent", "corrected_modality": "obligation"}},
  {{"original_text": "Companies may store", "corrected_text": "Companies may store anonymized data indefinitely", "corrected_modality": "permission"}}
], "remove": [], "add": []}}

Now process:
Source: {source_text}
B0 predictions:
{b0_predictions}

Output (JSON only):"""


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
    return resp.json(), resp.json().get("usage", {}) or {}


# ---------------------------------------------------------------------------
# Combine H1 selective
# ---------------------------------------------------------------------------
def combine_selective(b0_clauses, llm_response):
    """H1 = keep + corrected.corrected_text + add. B0's keep gets B0's modality.
    llm_response is a dict with keys keep/correct/remove/add (any may be missing).
    """
    out = []
    # 1. Keep
    for k in (llm_response.get("keep") or []):
        if not isinstance(k, dict):
            continue
        mod = k.get("modality")
        if mod not in ("permission", "obligation", "prohibition", "definition"):
            continue
        ct = k.get("clause_text", "")
        if not ct:
            continue
        out.append({"clause_text": ct, "modality": mod, "decision": "keep"})
    # 2. Correct
    for c in (llm_response.get("correct") or []):
        if not isinstance(c, dict):
            continue
        mod = c.get("corrected_modality")
        if mod not in ("permission", "obligation", "prohibition", "definition"):
            continue
        ct = c.get("corrected_text", "")
        if not ct:
            continue
        out.append({"clause_text": ct, "modality": mod, "decision": "corrected",
                    "original_text": c.get("original_text", "")})
    # 3. Add
    for a in (llm_response.get("add") or []):
        if not isinstance(a, dict):
            continue
        mod = a.get("modality")
        if mod not in ("permission", "obligation", "prohibition", "definition"):
            continue
        ct = a.get("clause_text", "")
        if not ct:
            continue
        out.append({"clause_text": ct, "modality": mod, "decision": "added"})
    return out


# ---------------------------------------------------------------------------
# Token IoU + alignment + evaluation
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
    print("H1 Selective Pilot (B0 first, LLM verify + add)")
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
    totals = {
        "b0": {"tp": 0, "fp": 0, "fn": 0},
        "d1": {"tp": 0, "fp": 0, "fn": 0},
        "h1s": {"tp": 0, "fp": 0, "fn": 0},  # selective
    }
    total_in = total_out = 0
    parse_errors = 0
    fallbacks_to_b0 = 0

    for i, sid in enumerate(selected_ids, 1):
        rec = gold[sid]
        text = rec["approved_text_en"]
        n_gold = len(rec["gold_clauses"])
        b0_clauses = b0.get(sid, [])
        print(f"[{i}/{len(selected_ids)}] {sid}  gold={n_gold}  B0={len(b0_clauses)}")

        # Build B0 prediction block for prompt
        if b0_clauses:
            b0_block = "\n".join(
                f'- "{c["clause_text"][:200]}" -> {c["modality"]}'
                for c in b0_clauses
            )
        else:
            b0_block = "(B0 made no predictions for this source)"

        prompt = USER_TEMPLATE.format(source_text=text, b0_predictions=b0_block)
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
        llm_response = None
        try:
            content = response["choices"][0]["message"]["content"]
            llm_response = json.loads(content)
            if not isinstance(llm_response, dict):
                llm_response = None
                parse_errors += 1
        except Exception as e:
            parse_errors += 1
            print(f"  PARSE ERROR: {e}")

        # Build D1 (also call separately? No, parse LLM response as if it were D1)
        # For fair D1 comparison, we need a separate D1 call. For now, derive D1 from
        # this same call (keep + add clauses are the LLM's full prediction).
        if llm_response is None:
            # Fallback: use B0 alone
            h1s_clauses = [{"clause_text": c["clause_text"], "modality": c["modality"]} for c in b0_clauses]
            d1_clauses = []
            fallbacks_to_b0 += 1
        else:
            # H1 selective
            h1s_clauses_raw = combine_selective(b0_clauses, llm_response)
            h1s_clauses = [{"clause_text": c["clause_text"], "modality": c["modality"]} for c in h1s_clauses_raw]
            # D1: just use LLM's keep + add (the LLM's full vision)
            d1_clauses = []
            for k in (llm_response.get("keep") or []):
                if isinstance(k, dict) and k.get("modality") in ("permission", "obligation", "prohibition", "definition"):
                    d1_clauses.append({"clause_text": k.get("clause_text", ""), "modality": k["modality"]})
            for a in (llm_response.get("add") or []):
                if isinstance(a, dict) and a.get("modality") in ("permission", "obligation", "prohibition", "definition"):
                    d1_clauses.append({"clause_text": a.get("clause_text", ""), "modality": a["modality"]})
            # Also include corrected (LLM's view of what should be there)
            for c in (llm_response.get("correct") or []):
                if isinstance(c, dict) and c.get("corrected_modality") in ("permission", "obligation", "prohibition", "definition"):
                    d1_clauses.append({"clause_text": c.get("corrected_text", ""), "modality": c["corrected_modality"]})

        # Evaluations
        b0_eval = evaluate_modality(b0_clauses, rec["gold_clauses"])
        d1_eval = evaluate_modality(d1_clauses, rec["gold_clauses"])
        h1s_eval = evaluate_modality(h1s_clauses, rec["gold_clauses"])

        if b0_eval:
            totals["b0"]["tp"] += b0_eval["tp"]
            totals["b0"]["fp"] += b0_eval["fp"]
            totals["b0"]["fn"] += b0_eval["fn"]
        if d1_eval:
            totals["d1"]["tp"] += d1_eval["tp"]
            totals["d1"]["fp"] += d1_eval["fp"]
            totals["d1"]["fn"] += d1_eval["fn"]
        if h1s_eval:
            totals["h1s"]["tp"] += h1s_eval["tp"]
            totals["h1s"]["fp"] += h1s_eval["fp"]
            totals["h1s"]["fn"] += h1s_eval["fn"]

        b0_f1 = b0_eval["f1"] if b0_eval else 0.0
        d1_f1 = d1_eval["f1"] if d1_eval else 0.0
        h1s_f1 = h1s_eval["f1"] if h1s_eval else 0.0
        print(f"  B0={len(b0_clauses)}  D1={len(d1_clauses)}  H1s={len(h1s_clauses)}  | "
              f"B0_F1={b0_f1:.3f}  D1_F1={d1_f1:.3f}  H1s_F1={h1s_f1:.3f}  | "
              f"({t1-t0:.1f}s, {in_tok}+{out_tok} tok)")

        all_results.append({
            "sample_id": sid,
            "elapsed_s": round(t1 - t0, 2),
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "n_gold_clauses": n_gold,
            "n_b0_clauses": len(b0_clauses),
            "n_d1_clauses": len(d1_clauses),
            "n_h1s_clauses": len(h1s_clauses),
            "b0_eval": b0_eval,
            "d1_eval": d1_eval,
            "h1s_eval": h1s_eval,
            "llm_response": llm_response,
        })

    def f1_from(t):
        tp, fp, fn = t["tp"], t["fp"], t["fn"]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return round(p, 4), round(r, 4), round(f, 4)

    p_b0, r_b0, f_b0 = f1_from(totals["b0"])
    p_d1, r_d1, f_d1 = f1_from(totals["d1"])
    p_h1s, r_h1s, f_h1s = f1_from(totals["h1s"])

    summary = {
        "model": args.model,
        "n_samples": len(selected_ids),
        "n_with_eval": sum(1 for r in all_results if r.get("b0_eval") and r.get("d1_eval") and r.get("h1s_eval")),
        "n_parse_errors": parse_errors,
        "n_fallbacks_to_b0": fallbacks_to_b0,
        "b0": {"p": p_b0, "r": r_b0, "f1": f_b0, **totals["b0"]},
        "d1": {"p": p_d1, "r": r_d1, "f1": f_d1, **totals["d1"]},
        "h1s": {"p": p_h1s, "r": r_h1s, "f1": f_h1s, **totals["h1s"]},
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_tokens": total_in + total_out,
    }

    print()
    print("=" * 60)
    print("AGGREGATE (modality micro)")
    print("=" * 60)
    print(f"  Samples: {summary['n_samples']} (with eval: {summary['n_with_eval']}, parse errors: {parse_errors}, fallbacks to B0: {fallbacks_to_b0})")
    print()
    print(f"  {'method':<22}  {'P':>7}  {'R':>7}  {'F1':>7}")
    print(f"  {'B0 (rule)':<22}  {p_b0:>7.4f}  {r_b0:>7.4f}  {f_b0:>7.4f}")
    print(f"  {'D1 (LLM direct)':<22}  {p_d1:>7.4f}  {r_d1:>7.4f}  {f_d1:>7.4f}")
    print(f"  {'H1-selective (B0+LLM)':<22}  {p_h1s:>7.4f}  {r_h1s:>7.4f}  {f_h1s:>7.4f}")
    print()
    print(f"  Tokens: in={total_in}  out={total_out}  total={total_in + total_out}")
    print()

    out_file = out_dir / f"h1s_pilot_{int(time.time())}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            "per_sample": all_results,
            "disclosure": (
                "Paper-level H1 selective (LLM as B0 verifier + completer). "
                "H1 = LLM-verified B0 (keep/correct/remove) + LLM-added missing clauses. "
                "D1 here is derived from same LLM call (keep + add + corrected). "
                "Bypasses canonical protocol. Modality P/R via token-IoU alignment (threshold 0.3). "
                "Disclose in paper."
            ),
        }, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()
