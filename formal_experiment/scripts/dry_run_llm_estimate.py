"""Offline LLM call and cost estimator for the EStG-150 v2 workflow.

This is a **design-draft estimator**. It computes the call budget and
estimated cost for regenerating layer C and layer D, and prints the
chunking plan. It does NOT call any LLM. It does NOT touch any data
file. It does NOT read .env.

The 2026-07-13 update fixes the following issues from the previous
budget:

  1. Total call count = 675 = 150 (layer C) + 525 (layer D). With a
     per-runner ``max-calls=200`` cap, the runner needs at least
     4 batches (1 for layer C, 3 for layer D), not 1.
  2. ``max-calls=200`` is the per-runner batch cap. The runner
     refuses to exceed 200 in a single process; the orchestrator
     launches 4 sequential batches and stitches the manifest.
  3. ``annotation-only-default`` is a **placeholder** for a model
     that has not been chosen. Its price is
     ``hypothetical_rate`` and the cost is reported as "unverified".
     No real cost figure is given for a placeholder.
  4. All unverified model prices are marked
     ``price_snapshot_unverified`` in the JSON output and the
     per-model table renders them with the same tag.
  5. The runner is **not implemented** in this task; this estimator
     is a design draft. Real-LLM runs require an explicit user
     authorization and a real runner.
  6. Real-run outputs go to
     ``data/development/estg/llm_candidate_runs/<run_id>/``, NOT to
     ``data/input/`` (which is reserved for the frozen formal
     capsule). The estimator never recommends writing to
     ``data/input/``.
  7. Chunk + resume is the primary execution mode: the runner takes
     a ``--start-index`` / ``--end-index`` pair OR a sample-id
     manifest, and refuses to re-call any sample whose
     ``manifest.jsonl`` already has a successful row.

Run from workspace root:
    python formal_experiment/scripts/dry_run_llm_estimate.py
    python formal_experiment/scripts/dry_run_llm_estimate.py --help
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


DEFAULT_LAYER_B = REPO / "data/development/human_review/estg_150_translation_en_v1.jsonl"
DEFAULT_LAYER_C = REPO / "data/development/human_review/estg_150_llm_six_element_candidates_v1.jsonl"
DEFAULT_LAYER_D = REPO / "data/development/human_review/estg_150_review_aids_zh_v1.jsonl"
DEFAULT_PROMPTS_DIR = REPO / "prompts/sun_compat"


# ---------------------------------------------------------------------------
# Model prices (price snapshot — unverified)
# ---------------------------------------------------------------------------
# All entries are tagged ``price_snapshot_unverified``. The price
# snapshot is meant to give a back-of-envelope cost range, NOT an
# actionable number. The user must verify the price at the time of
# the real run. ``annotation-only-default`` is a **placeholder** for
# a model the user will pick; its rate is purely hypothetical.

PRICE_SNAPSHOT = {
    "snapshot_status": "price_snapshot_unverified",
    "snapshot_note": (
        "Prices below are conservative Q1 2026 list prices, not "
        "actionable. The user must verify each rate at the time of "
        "the real run. The 'annotation-only-default' entry is a "
        "placeholder; no real model is wired to it yet."
    ),
    "models": {
        "gpt-4o": {
            "prompt_per_1k": 0.005, "completion_per_1k": 0.015,
            "recommended_for_gold": False,
            "recommended_for_gold_reason": (
                "Same model family as D1 evaluation; using it for Gold "
                "introduces anchoring bias."
            ),
        },
        "gpt-4o-mini": {
            "prompt_per_1k": 0.00015, "completion_per_1k": 0.0006,
            "recommended_for_gold": False,
            "recommended_for_gold_reason": (
                "Cheap; can be used as the independent annotation model "
                "if the user wants to keep the Gold-build cost low."
            ),
        },
        "gpt-5": {
            "prompt_per_1k": 0.005, "completion_per_1k": 0.020,
            "recommended_for_gold": False,
            "recommended_for_gold_reason": (
                "Same model family as D1 evaluation; using it for Gold "
                "introduces anchoring bias."
            ),
        },
        "claude-3-5-sonnet": {
            "prompt_per_1k": 0.003, "completion_per_1k": 0.015,
            "recommended_for_gold": False,
            "recommended_for_gold_reason": (
                "Can serve as the independent annotation model; still "
                "expensive vs gpt-4o-mini."
            ),
        },
        "llama-3.1-70b-instruct": {
            "prompt_per_1k": 0.00088, "completion_per_1k": 0.00088,
            "recommended_for_gold": True,
            "recommended_for_gold_reason": (
                "Open-weight; cheapest realistic option for an "
                "independent annotation model."
            ),
        },
        "annotation-only-default": {
            # PLACEHOLDER. No real model is wired. Rate is purely
            # hypothetical. Do NOT report a dollar figure for this
            # entry in the per-model table; report "hypothetical_rate".
            "prompt_per_1k": None, "completion_per_1k": None,
            "is_placeholder": True,
            "recommended_for_gold": True,
            "recommended_for_gold_reason": (
                "PLACEHOLDER. The user must pick a concrete model "
                "(e.g. llama-3.1-70b-instruct or a local model with "
                "a separate API key) before any real run."
            ),
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_jsonl(p: Path) -> list[dict]:
    out: list[dict] = []
    if not p.exists():
        return out
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


# ---------------------------------------------------------------------------
# Call estimation
# ---------------------------------------------------------------------------

def estimate_layer_C_calls(prompts_dir: Path) -> dict:
    """Layer C: 1 call per sample = 150 calls total."""
    sys_prompt = (prompts_dir / "dry_run_six_element.md").read_text(encoding="utf-8")
    n_samples = 150
    avg_en_chars = 450
    sys_prompt_tokens = len(sys_prompt) // 4
    few_shot_tokens = 4 * 350
    sample_tokens = avg_en_chars // 4
    prompt_tokens = sys_prompt_tokens + few_shot_tokens + sample_tokens
    completion_tokens = 600
    return {
        "n_calls": n_samples,
        "prompt_tokens_per_call": prompt_tokens,
        "completion_tokens_per_call": completion_tokens,
        "total_prompt_tokens": n_samples * prompt_tokens,
        "total_completion_tokens": n_samples * completion_tokens,
        "total_tokens": n_samples * (prompt_tokens + completion_tokens),
    }


def estimate_layer_D_calls(prompts_dir: Path) -> dict:
    """Layer D: 3 calls per sample + 1 call per clause (avg 1.5
    clauses/sample) = 150 * (2 + 1.5) = 525 calls total."""
    sys_prompt_zh = (prompts_dir / "dry_run_zh_gloss.md").read_text(encoding="utf-8")
    sys_prompt_back = (prompts_dir / "dry_run_back_translation.md").read_text(encoding="utf-8")
    n_samples = 150
    avg_en_chars = 450
    avg_clauses = 1.5
    p1_sys = len(sys_prompt_zh) // 4
    p1_sample = avg_en_chars // 4
    p1_completion = avg_en_chars // 3
    p2_sys = len(sys_prompt_back) // 4
    p2_sample = p1_completion
    p2_completion = avg_en_chars // 4
    p3_sys = len(sys_prompt_zh) // 4
    p3_sample = (avg_en_chars // 4) // avg_clauses
    p3_completion = 200
    per_sample = (
        (p1_sys + p1_sample + p1_completion) +
        (p2_sys + p2_sample + p2_completion) +
        avg_clauses * (p3_sys + p3_sample + p3_completion)
    )
    return {
        "n_calls": int(n_samples * (2 + avg_clauses)),
        "calls_breakdown": {
            "chinese_translation": n_samples,
            "english_back_translation": n_samples,
            "per_clause_chinese_gloss": int(n_samples * avg_clauses),
        },
        "total_prompt_tokens": int(n_samples * (
            (p1_sys + p1_sample) + (p2_sys + p2_sample) + avg_clauses * (p3_sys + p3_sample)
        )),
        "total_completion_tokens": int(n_samples * (
            p1_completion + p2_completion + avg_clauses * p3_completion
        )),
        "total_tokens": int(per_sample * n_samples),
    }


def cost_estimate(
    total_prompt: int, total_completion: int, model: str, snapshot: dict
) -> dict:
    entry = snapshot["models"].get(model)
    if entry is None:
        return {
            "model": model,
            "error": f"model {model!r} not in price snapshot",
        }
    if entry.get("is_placeholder"):
        return {
            "model": model,
            "is_placeholder": True,
            "rate_status": "hypothetical_rate",
            "estimated_cost_usd": None,
            "note": (
                "No real model is wired to 'annotation-only-default' yet. "
                "Pick a concrete model (e.g. llama-3.1-70b-instruct) and "
                "verify its rate before any real run."
            ),
        }
    ppk = entry["prompt_per_1k"]
    cpk = entry["completion_per_1k"]
    cost = total_prompt / 1000.0 * ppk + total_completion / 1000.0 * cpk
    return {
        "model": model,
        "rate_status": snapshot["snapshot_status"],
        "rate_prompt_per_1k_usd": ppk,
        "rate_completion_per_1k_usd": cpk,
        "estimated_cost_usd_unverified": round(cost, 2),
    }


def plan_batches(n_calls: int, max_calls: int) -> list[tuple[int, int]]:
    """Plan non-overlapping index batches [start, end) of size
    <= max_calls. Each batch corresponds to one runner process."""
    if max_calls <= 0:
        raise ValueError("max_calls must be > 0")
    batches: list[tuple[int, int]] = []
    start = 0
    while start < n_calls:
        end = min(start + max_calls, n_calls)
        batches.append((start, end))
        start = end
    return batches


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--model", default="annotation-only-default",
        choices=sorted(PRICE_SNAPSHOT["models"].keys()),
        help="Model to estimate cost for. The default is a placeholder.",
    )
    ap.add_argument(
        "--max-calls-per-runner", type=int, default=200,
        help=(
            "Hard per-runner batch cap. The runner refuses to exceed "
            "this; the orchestrator launches multiple batches. "
            "Default 200. With 675 total calls this means at least 4 "
            "batches (1 for layer C, 3 for layer D)."
        ),
    )
    args = ap.parse_args()

    # Source / target integrity
    print("=== Source / target integrity ===")
    for label, p in (
        ("layer_B (immutable EN translation manifest)", DEFAULT_LAYER_B),
        ("layer_C (immutable LLM six-element manifest)", DEFAULT_LAYER_C),
        ("layer_D (immutable Chinese aid, all null pending LLM auth)", DEFAULT_LAYER_D),
    ):
        if p.exists():
            print(f"  {sha256_file(p)[:16]}  {label}  "
                  f"({p.stat().st_size:>7} B)  {p.name}")
        else:
            print(f"  [MISSING] {label}: {p}")

    print()
    print("=== Layer C (six-element candidate) ===")
    c = estimate_layer_C_calls(DEFAULT_PROMPTS_DIR)
    print(json.dumps(c, indent=2))

    print()
    print("=== Layer D (Chinese aid: zh + back-translation + per-clause gloss) ===")
    d = estimate_layer_D_calls(DEFAULT_PROMPTS_DIR)
    print(json.dumps(d, indent=2))

    print()
    total_calls = c["n_calls"] + d["n_calls"]
    total_prompt = c["total_prompt_tokens"] + d["total_prompt_tokens"]
    total_completion = c["total_completion_tokens"] + d["total_completion_tokens"]
    print("=== Totals (per-layer, BEFORE price) ===")
    print(json.dumps({
        "layer_C_calls": c["n_calls"],
        "layer_D_calls": d["n_calls"],
        "total_calls": total_calls,
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total_prompt + total_completion,
    }, indent=2))

    print()
    print("=== Cost estimate (UNVERIFIED; user must verify at run time) ===")
    cc = cost_estimate(c["total_prompt_tokens"], c["total_completion_tokens"], args.model, PRICE_SNAPSHOT)
    cd = cost_estimate(d["total_prompt_tokens"], d["total_completion_tokens"], args.model, PRICE_SNAPSHOT)
    print("layer C cost:")
    print(json.dumps(cc, indent=2))
    print("layer D cost:")
    print(json.dumps(cd, indent=2))
    total_cost_entry = {
        "model": args.model,
        "total_calls": total_calls,
        "rate_status": PRICE_SNAPSHOT["snapshot_status"],
    }
    if cc.get("estimated_cost_usd_unverified") is not None and \
       cd.get("estimated_cost_usd_unverified") is not None:
        total_cost_entry["estimated_cost_usd_unverified"] = round(
            cc["estimated_cost_usd_unverified"] + cd["estimated_cost_usd_unverified"], 2
        )
    else:
        total_cost_entry["estimated_cost_usd_unverified"] = None
        total_cost_entry["note"] = (
            "placeholder model; pick a concrete model and re-run."
        )
    print("total cost:")
    print(json.dumps(total_cost_entry, indent=2))

    print()
    print(f"=== Batch plan (max-calls-per-runner = {args.max_calls_per_runner}) ===")
    plan = {
        "layer_C": {
            "n_calls": c["n_calls"],
            "n_batches": len(plan_batches(c["n_calls"], args.max_calls_per_runner)),
            "batches": plan_batches(c["n_calls"], args.max_calls_per_runner),
        },
        "layer_D": {
            "n_calls": d["n_calls"],
            "n_batches": len(plan_batches(d["n_calls"], args.max_calls_per_runner)),
            "batches": plan_batches(d["n_calls"], args.max_calls_per_runner),
        },
        "total_batches": len(plan_batches(c["n_calls"], args.max_calls_per_runner))
                         + len(plan_batches(d["n_calls"], args.max_calls_per_runner)),
    }
    print(json.dumps(plan, indent=2))
    print()
    print("=== Chunk + resume semantics ===")
    print("Each runner batch takes --start-index and --end-index (inclusive")
    print("of [0, n_calls) within its layer). The runner reads the existing")
    print("manifest.jsonl and refuses to re-call any sample that already")
    print("has a successful row. An interrupted run can be resumed by")
    print("re-running the same batch with the same output dir.")
    print("Alternative: --sample-manifest path/to/sample_ids.jsonl lets the")
    print("user restrict the batch to a specific list of sample_ids.")

    print()
    print("=== Recommendations (offline; no real LLM call) ===")
    print("1. Use an INDEPENDENT annotation model that does NOT participate")
    print("   in B0/H1/D1 final comparison. The default placeholder is")
    print("   'annotation-only-default'; pick a concrete model first.")
    print("2. Per-runner batch cap: --max-calls 200 (default). With 675")
    print("   total calls the orchestrator must run at least 4 batches:")
    print("   1 for layer C, 3 for layer D. The cap on layer D's runner")
    print("   is NOT 400 — it is the same 200 per batch, applied 3 times.")
    print("3. Real-run outputs go to:")
    print("     data/development/estg/llm_candidate_runs/<run_id>/")
    print("   NEVER to data/input/ (reserved for the frozen formal capsule)")
    print("   and NEVER to data/gold/ (reserved for the locked Gold).")
    print("4. Layer D (Chinese aid) is still all-null; the review tool")
    print("   shows a placeholder banner and never fabricates Chinese.")
    print("5. The runner is NOT implemented in this task. This script is")
    print("   a design-draft estimator. Any real LLM call requires a")
    print("   separate user authorization and a real runner implementation.")
    print("6. The cost figures above are tagged")
    print(f"   '{PRICE_SNAPSHOT['snapshot_status']}'; verify each rate")
    print("   at the time of the real run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
