"""Prepare S3-TABLE3-R5.1 execution materials (v2): reuse, API budget, readiness.

Offline only.  Uses the corrected per-record reuse verification and recomputes
the budget from the actual corrected unique request list.  The old 22-call /
1.18 USD v1 budget is NOT inherited.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import r5_reuse_verification as rv  # noqa: E402

CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v2.json"
OUT = ROOT / "data/development/stage3_table3_r5_benchmark_v2"
REPORTS = ROOT / "outputs/reports"
BENCHMARK_ID = "stage3_table3_r5_benchmark_v2"
MAX_OUTPUT_TOKENS_PER_CALL = 4096


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _gdpr7_manifest() -> dict:
    return load_json(ROOT / "data/predictions/gdpr7_direct_llm_v1/manifest.json")


def read_price_evidence() -> dict:
    """Read the recorded provider price snapshot from the actual gdpr7 manifest."""
    manifest = load_json(ROOT / "data/predictions/gdpr7_direct_llm_v1/manifest.json")
    pricing = manifest.get("pricing") or {}
    off_peak = {
        "input_cache_hit_per_million": pricing.get("input_cache_hit_per_million"),
        "input_cache_miss_per_million": pricing.get("input_cache_miss_per_million"),
        "output_per_million": pricing.get("output_per_million"),
    }
    # Peak is the conservative end; the recorded snapshot is the off-peak rate and
    # the price page records an off-peak multiplier of 0.5 (see v1 price snapshot).
    peak = {k: (v * 2 if v is not None else None) for k, v in off_peak.items()}
    return {
        "source": "data/predictions/gdpr7_direct_llm_v1/manifest.json::pricing (recorded provider snapshot)",
        "snapshot_is_off_peak": off_peak,
        "peak_derivation": "peak = 2 x recorded off-peak; the recorded off-peak multiplier is 0.5",
        "peak_used_for_cap": peak,
        "currency": pricing.get("currency", "USD"),
        "verified_date_recorded_in_manifest": manifest.get("timestamp_utc") or manifest.get("run_id"),
        "reverify_before_authorized_execution": True,
    }


def build_budget(reuse: dict, config: dict, source_doc: dict) -> dict:
    prompt_bytes = (ROOT / rv.R5_PROMPT_REL).read_bytes()
    specs = {r["requirement_id"]: r for r in config["requirements"]}
    sources = {r["requirement_id"]: r for r in source_doc["requirements"]}
    price = read_price_evidence()
    peak = price["peak_used_for_cap"]
    rows = []
    for row in reuse["rows"]:
        if not row["core_eligible"]:
            continue
        if row["ours"]["status"] == "verified":
            continue
        src = sources[row["requirement_id"]]
        text_bytes = len(src["excerpt_text"].encode("utf-8"))
        upper = max(8192, len(prompt_bytes) + text_bytes + 4096)
        rows.append({
            "requirement_id": row["requirement_id"],
            "split": row["split"],
            "source_family_id": row["source_family_id"],
            "source_text_sha256": src["text_sha256"],
            "source_text_utf8_bytes": text_bytes,
            "reuse_status": row["ours"]["status"],
            "input_token_upper_bound": upper,
            "max_output_tokens": MAX_OUTPUT_TOKENS_PER_CALL,
            "request_unit": "one unique regulation input; all BPMN variants for this requirement reuse this extraction",
            "request_template": "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05",
            "prompt_sha256_from_file": rv.sha_bytes((ROOT / rv.R5_PROMPT_REL).read_bytes()),
        })
    total_input_upper = sum(r["input_token_upper_bound"] for r in rows)
    total_output_upper = sum(r["max_output_tokens"] for r in rows)
    raw_cost = (total_input_upper * (peak["input_cache_miss_per_million"] or 0)
                + total_output_upper * (peak["output_per_million"] or 0)) / 1_000_000
    margin = math.ceil(raw_cost * 1.2 * 100) / 100
    candidate_rows = [r["requirement_id"] for r in reuse["rows"] if not r["core_eligible"]]
    return {
        "schema_version": "stage3_table3_r5_api_budget@2.0.0",
        "benchmark_id": BENCHMARK_ID,
        "status": "API_AUTHORIZATION_PENDING",
        "real_api_calls_made": 0,
        "authorization_consumed_this_round": False,
        "supersedes": "stage3_table3_r5_api_budget_v1 (old 22-call / 1.18 USD cap is NOT inherited)",
        "api_unit": "one unique regulation input (source text); never one call per BPMN variant",
        "calls_cap_core_request_list": len(rows),
        "retry_cap": 0,
        "unique_regulation_inputs_total": len(reuse["rows"]),
        "core_requirements": sum(1 for r in reuse["rows"] if r["core_eligible"]),
        "reused_existing_stage2_inputs": sum(1 for r in reuse["rows"] if r["core_eligible"] and r["ours"]["status"] == "verified"),
        "new_requests": len(rows),
        "candidate_assets_excluded_from_current_request_list": candidate_rows,
        "candidate_assets_note": "the 5 non-core candidate requirements (permission/prohibition assets) are NOT in the current request list; adding them would add 5 calls and requires a future authorization",
        "max_output_tokens_per_call": MAX_OUTPUT_TOKENS_PER_CALL,
        "total_output_tokens_cap": total_output_upper,
        "total_input_tokens_cap": total_input_upper,
        "token_estimation_method": "BPE token count bounded above by request UTF-8 byte count; prompt bytes + source-text bytes + 4096-byte envelope; floor 8192",
        "model_identity": {
            "id": (_gdpr7_manifest().get("model") or {}).get("id"),
            "published_alias": (_gdpr7_manifest().get("model") or {}).get("published_alias"),
            "prompt_name": (_gdpr7_manifest().get("model") or {}).get("prompt_name"),
            "prompt_sha256_recorded_in_manifest": (_gdpr7_manifest().get("model") or {}).get("prompt_sha256"),
            "prompt_sha256_from_file": rv.sha_bytes((ROOT / rv.R5_PROMPT_REL).read_bytes()),
            "binding_note": "model alias and prompt identity are read from the recorded gdpr7 Direct-LLM manifest; must be re-verified before an authorized run",
        },
        "price_evidence": price,
        "cost_upper_bound_usd_without_cache_discount": round(raw_cost, 6),
        "cost_upper_bound_usd_with_20pct_margin": margin,
        "cost_cap_is_not_predicted_bill": True,
        "request_rows": rows,
        "method_call_owner": "Ours Direct-LLM Stage2 only; Sun Rules-Only and Winter native consume 0 API calls",
        "assumptions": [
            "No retries are authorized or budgeted.",
            "No cache-hit discount is assumed.",
            "Any text, prompt, model-alias or price change invalidates this cap.",
        ],
    }


def build_readiness(reuse: dict, budget: dict, config: dict, source_doc: dict) -> dict:
    s = reuse["summary"]
    return {
        "schema_version": "stage3_table3_r5_readiness@2.0.0",
        "benchmark_id": BENCHMARK_ID,
        "boundary": "Readiness only; no method metric is claimed.",
        "statuses": {
            "data": "DATA_READY_FOR_FROZEN_SCOPE",
            "methods": "METHODS_NOT_READY",
            "api": "API_AUTHORIZATION_PENDING",
            "formal_release": "FORMAL_RELEASE_NOT_APPROVED",
        },
        "data_scope": {
            "frozen_core_scope": "three-class (missing_action / incorrect_actor / out_of_order) on source-grounded obligations only",
            "core_requirements": budget["core_requirements"],
            "core_cases": None,  # filled from manifest by the report writer
            "candidate_assets_out_of_scope": budget["candidate_assets_excluded_from_current_request_list"],
            "condition_exception_truth_still_unsupported": True,
            "permission_prohibition_assets_not_scored": True,
        },
        "reuse_summary": s,
        "budget_summary": {k: budget[k] for k in
                           ["calls_cap_core_request_list", "total_input_tokens_cap", "total_output_tokens_cap",
                            "cost_upper_bound_usd_with_20pct_margin", "retry_cap"]},
        "can_start_formal_method_run": False,
        "execution_blockers": [
            "API authorization for the corrected Ours Direct-LLM request list is absent.",
            "METHODS_NOT_READY: R4 actor-surface equivalence, action mis-matching, same-action-different-object, actor/BO candidate scope, and coordinate postprocessing were NOT fixed this round.",
            "No new Stage2/Stage3 run may start until the method protocol and API budget are authorized.",
        ],
        "future_execution_order": [
            f"After authorization, run exactly {budget['new_requests']} unique Ours Direct-LLM Stage2 requests (one per unique source text); no per-variant calls.",
            "Reuse the verified existing Stage2 predictions listed in the reuse report.",
            "Run Sun Rules-Only locally and Winter native after Stage2 inputs are frozen.",
            "Run shared Stage3 on the frozen inference view; report core metrics, coverage, unknown, N/A and semantic challenges separately.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    config = load_json(CONFIG)
    source_doc = load_json(OUT / "source_requirements.json")
    manifest = load_json(OUT / "manifest.json")
    reuse = rv.verify_reuse(config, source_doc)
    budget = build_budget(reuse, config, source_doc)
    readiness = build_readiness(reuse, budget, config, source_doc)
    semantic = load_json(OUT / "semantic_challenges.json")
    if args.write:
        write_json(REPORTS / "stage3_table3_r5_prediction_reuse_v2.json", reuse)
        write_json(REPORTS / "stage3_table3_r5_api_budget_v2.json", budget)
        write_json(REPORTS / "stage3_table3_r5_readiness_v2.json", readiness)
        summary = {
            "schema_version": "stage3_table3_r5_benchmark_report@2.0.0",
            "benchmark_id": BENCHMARK_ID,
            "status": "DATA_READY_FOR_FROZEN_SCOPE / METHODS_NOT_READY / API_AUTHORIZATION_PENDING / FORMAL_RELEASE_NOT_APPROVED",
            "counts": {
                "independent_requirements": manifest["independent_requirements"],
                "core_requirements": manifest["core_requirements"],
                "candidate_requirements": manifest["candidate_requirements"],
                "core_cases": manifest["core_cases"],
                "baseline_controls": manifest["baseline_controls"],
                "variants_per_type": manifest["variants_per_type"],
                "development_requirements": manifest["development_requirements"],
                "test_requirements": manifest["test_requirements"],
                "core_test_requirements": manifest["core_test_requirements"],
                "source_family_count": manifest["source_family_count"],
                "source_family_count_by_split": manifest["source_family_count_by_split"],
                "independent_test_source_family_ids": manifest["independent_test_source_family_ids"],
                "semantic_challenge_pairs": manifest["semantic_challenge_pair_counts"],
            },
            "six_element": {
                "presence_counts": manifest["element_coverage"],
                "evidence_scope_counts": manifest["element_evidence_scope_counts"],
            },
            "reuse": reuse["summary"],
            "budget": {k: budget[k] for k in ["calls_cap_core_request_list", "new_requests",
                                              "reused_existing_stage2_inputs", "total_input_tokens_cap",
                                              "total_output_tokens_cap", "cost_upper_bound_usd_with_20pct_margin",
                                              "retry_cap", "price_evidence"]},
            "boundary": "AI-constructed, source-grounded construction reference; not human Gold and not a Table 3 result.",
        }
        write_json(REPORTS / "stage3_table3_r5_benchmark_v2.json", summary)
    print(json.dumps({"ours_verified": reuse["summary"]["ours_verified_reusable"],
                      "ours_new": reuse["summary"]["ours_new_requests"],
                      "core_new_requests": budget["new_requests"],
                      "cost_cap": budget["cost_upper_bound_usd_with_20pct_margin"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
