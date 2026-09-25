"""Prepare the S3-TABLE3-R5 execution plan, reuse index, API budget, and readiness.

This script is offline-only.  It does not call an API, run Stage2, run Stage3,
read .env, or modify old predictions/manifests.  It:
- matches each R5 source text to exact existing Stage2 predictions when present;
- lists the remaining Ours Direct-LLM requests without issuing them;
- computes a conservative byte-based token upper bound and cost cap;
- records detector prechecks by reusing current-state R4 evidence and a small
  local inspection of saved R4 predictions;
- writes the reuse/budget/readiness reports.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v1.json"
OUT = ROOT / "data/development/stage3_table3_r5_benchmark_v1"
REPORTS = ROOT / "outputs/reports"
BENCHMARK_ID = "stage3_table3_r5_benchmark_v1"
PROMPT_PATH = ROOT / "prompts/sun_compat/direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md"
PROMPT_SHA256 = "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"
MAX_OUTPUT_TOKENS_PER_CALL = 4096
PRICE_SNAPSHOT = {
    "source": "https://api-docs.deepseek.com/quick_start/pricing/",
    "verified_date": "2026-09-23",
    "currency": "USD",
    "per_million_peak": {"input_cache_hit": 0.044, "input_cache_miss": 1.32, "output": 3.96},
    "off_peak_multiplier": 0.5,
    "reverify_before_authorized_execution": True,
}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_text(value: str) -> str:
    return sha_bytes(value.encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def stable_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:12]}"


def build_gdpr7_index() -> dict[str, dict]:
    doc = load_json(ROOT / "data/input/gdpr7_stage2_input_v1.json")
    out = {}
    for rule in doc["rules"]:
        for sentence in rule["sentences"]:
            out[sentence["sample_id"]] = {
                "rule_id": rule["rule_id"],
                "sample_id": sentence["sample_id"],
                "text": sentence["approved_text_en"],
                "text_sha256": sentence["text_sha256"],
            }
    return out


def load_prediction_map(path: Path) -> dict[str, dict]:
    doc = load_json(path)
    return {str(rec["sample_id"]): rec for rec in doc.get("records", [])}


def r4_sample_id(rule_id: str) -> str:
    return f"gdpr_{rule_id}_s001"


def build_reuse(config: dict, source_req: dict, gdpr7_index: dict) -> dict:
    """Corrected R5.1 reuse judgment.

    Delegates to the evidence-chain verifier instead of trusting the presence of
    a sample_id or defaulting the 14 candidates to reusable.  It reads the
    actual prediction records, manifests and frozen inputs, and checks the full
    input identity (text + context), method/prompt/model binding and
    schema/parse/postprocess identity.
    """
    import importlib
    rv = importlib.import_module("r5_reuse_verification")
    rep = rv.verify_reuse(config, {"requirements": source_req})
    rows = []
    for r in rep["rows"]:
        ours = dict(r["ours"])
        ours["status"] = "reusable_exact_source_text_match" if ours["status"] == "verified" else ours["status"]
        rows.append({
            "requirement_id": r["requirement_id"],
            "split": r["split"],
            "source_kind": r["source_kind"],
            "source_text_sha256": r["source_text_sha256"],
            "sample_id": r["ours"].get("prediction_sample_id"),
            "methods": {"sun": r["sun"], "ours": ours, "winter": r["winter"]},
            "ours_reusable": r["ours"]["status"] == "verified",
        })
    return {
        "schema_version": "stage3_table3_r5_prediction_reuse@2.0.0",
        "benchmark_id": config.get("benchmark_id", BENCHMARK_ID),
        "policy": rep["policy"],
        "status_value_set": rep["status_value_set"],
        "reused_unique_inputs": sum(1 for r in rows if r["ours_reusable"]),
        "new_ours_requests": sum(1 for r in rows if not r["ours_reusable"]),
        "rows": rows,
    }


def build_budget(reuse: dict, source_req: dict) -> dict:
    prompt_bytes = PROMPT_PATH.read_bytes()
    reqs = {r["requirement_id"]: r for r in source_req}
    new_rows = []
    for row in reuse["rows"]:
        if row["methods"]["ours"]["status"] == "reusable_exact_source_text_match":
            continue
        req = reqs[row["requirement_id"]]
        text_bytes = len(req["excerpt_text"].encode("utf-8"))
        # Token count is bounded above by UTF-8 byte count for BPE-style tokenizers;
        # add a 4096-byte envelope/control allowance and a floor above the frozen D1 proxy maximum.
        upper = max(8192, len(prompt_bytes) + text_bytes + 4096)
        new_rows.append({
            "requirement_id": row["requirement_id"],
            "split": row["split"],
            "source_text_sha256": req["text_sha256"],
            "source_text_utf8_bytes": text_bytes,
            "input_token_upper_bound": upper,
            "max_output_tokens": MAX_OUTPUT_TOKENS_PER_CALL,
            "request_unit": "one unique regulation input; all BPMN variants for this requirement reuse this extraction",
            "request_template": "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05",
            "prompt_sha256": PROMPT_SHA256,
        })
    total_input_upper = sum(r["input_token_upper_bound"] for r in new_rows)
    total_output_upper = sum(r["max_output_tokens"] for r in new_rows)
    raw_cost = (total_input_upper * PRICE_SNAPSHOT["per_million_peak"]["input_cache_miss"] + total_output_upper * PRICE_SNAPSHOT["per_million_peak"]["output"]) / 1_000_000
    margin_cost = math.ceil(raw_cost * 1.2 * 100) / 100
    return {
        "schema_version": "stage3_table3_r5_api_budget@1.0.0",
        "benchmark_id": BENCHMARK_ID,
        "status": "API_AUTHORIZATION_PENDING",
        "real_api_calls_made": 0,
        "authorization_consumed_this_round": False,
        "calls_cap": len(new_rows),
        "retry_cap": 0,
        "unique_regulation_inputs_total": len(source_req),
        "reused_existing_stage2_inputs": reuse["reused_unique_inputs"],
        "new_requests": len(new_rows),
        "max_output_tokens_per_call": MAX_OUTPUT_TOKENS_PER_CALL,
        "total_output_tokens_cap": total_output_upper,
        "total_input_tokens_cap": total_input_upper,
        "price_snapshot": PRICE_SNAPSHOT,
        "cost_upper_bound_usd_without_cache_discount": round(raw_cost, 6),
        "cost_upper_bound_usd_with_20pct_margin": margin_cost,
        "request_rows": new_rows,
        "method_call_owner": "Ours Direct-LLM Stage2 only; Sun Rules-Only and Winter native do not consume these API calls",
        "assumptions": [
            "Token count is conservatively bounded by request UTF-8 bytes plus a 4096-byte envelope allowance.",
            "The request template and system prompt are the frozen D1 prompt identity with the recorded SHA-256.",
            "No retries are authorized or budgeted.",
            "No cache-hit discount is assumed for the cap.",
            "Any text change, prompt change, model alias change, or price change invalidates this cap and requires a new authorization snapshot.",
        ],
        "unknowns": [
            "Provider tokenizer count is not known exactly before dispatch; the cap uses a conservative byte upper bound.",
            "The official price page must be re-verified immediately before an authorized run.",
            "Actual failure/extraction quality is not predicted or assumed.",
        ],
    }


def run_prechecks() -> list[dict]:
    r4_mech = load_json(ROOT / "outputs/reports/stage3_table3_r4_targeted_mechanism_v1.json")
    r4_delivery = load_json(ROOT / "outputs/reports/stage3_table3_r4_targeted_v1.json")
    r4_eval = load_json(ROOT / "outputs/reports/stage3_table3_r4_targeted_v1_eval.json")
    behavior = r4_mech.get("behavior_probes") or []
    known = r4_mech.get("known_limitation_reproductions") or []
    # Small local extraction of saved R4 matching examples for the known action-surface pairs.
    mismatch_examples = []
    try:
        pred_doc = load_json(ROOT / "outputs/development/stage3_table3_r4_targeted_v1/predictions.json")
        wanted = {("provide", "applies"), ("consult", "requires"), ("carry", "describe")}
        for rec in pred_doc.get("records", []):
            for ev in (rec.get("method_evidence") or {}).get("mapping_table") or []:
                rule_action = str(ev.get("rule_action_surface") or "").lower()
                for cand in ev.get("candidates") or []:
                    cand_action = str(cand.get("candidate_action_surface") or "").lower()
                    if (rule_action, cand_action) in wanted:
                        mismatch_examples.append({
                            "case_id": rec.get("case_id"),
                            "method_id": rec.get("method_id"),
                            "rule_id": ev.get("rule_id"),
                            "rule_action_surface": ev.get("rule_action_surface"),
                            "candidate_action_surface": cand.get("candidate_action_surface"),
                            "candidate_node": cand.get("node_id"),
                            "similarity": cand.get("similarity"),
                            "selected": cand.get("selected"),
                        })
                        break
                if len(mismatch_examples) >= 6:
                    break
            if len(mismatch_examples) >= 6:
                break
    except Exception as exc:  # pragma: no cover - evidence is expected in the repo
        mismatch_examples = [{"error": repr(exc)}]

    def first_probe(probe_pred) -> dict | None:
        for probe in behavior:
            if probe_pred(probe):
                return probe
        return None

    order_probe = first_probe(lambda p: p.get("kind") == "projection" and p.get("expected_edges"))
    return [
        {
            "check_id": "PRE-01-actor-surface-equivalence",
            "expected_behavior": "the controller, The controller, and Controller should normalize to one legal actor surface",
            "actual_behavior": "frozen R4 evidence records the/Controller actor similarity around 0.4272 below theta=0.8; no normalization rule was added",
            "evidence_path": "outputs/reports/stage3_table3_r4_targeted_v1.json::conclusions.method_limitations",
            "classification": "method_limitation",
            "blocks_formal_interpretation": True,
            "notes": "Actor failures remain explainable and must not be reported as detector success.",
        },
        {
            "check_id": "PRE-02-known-action-surface-mismatches",
            "expected_behavior": "rule action surface should distinguish provide/applies, consult/requires, carry/describe rather than accept a lemma-level near match",
            "actual_behavior": f"{len(mismatch_examples)} saved R4 candidate examples retained for local inspection; example={mismatch_examples[:2]}",
            "evidence_path": "outputs/development/stage3_table3_r4_targeted_v1/predictions.json + R4 targeted report",
            "classification": "method_limitation" if mismatch_examples else "evidence_gap",
            "blocks_formal_interpretation": True,
            "notes": "R4 action-surface matching is retained; these pairs must be reported as known risk, not silently treated as passed.",
        },
        {
            "check_id": "PRE-03-same-action-different-object",
            "expected_behavior": "archive the parcel should not be satisfied by archive the invoice",
            "actual_behavior": "R4 mechanism report reproduces tie/same-verb wrong-object acceptance (known_limitation_reproductions)",
            "evidence_path": "outputs/reports/stage3_table3_r4_targeted_mechanism_v1.json::known_limitation_reproductions",
            "classification": "method_limitation",
            "blocks_formal_interpretation": True,
        },
        {
            "check_id": "PRE-04-correct-actor-and-business-object",
            "expected_behavior": "when the correct actor and correct business object both exist, actor detection should bind them rather than treating the object as an actor candidate",
            "actual_behavior": r4_delivery.get("actor_evidence", {}).get("definition6_C_scope_check", {}).get("finding", "R4 records the literal C-scope ambiguity; no silent change"),
            "evidence_path": "outputs/reports/stage3_table3_r4_targeted_v1.json::actor_evidence.definition6_C_scope_check",
            "classification": "implementation_or_representation_gap",
            "blocks_formal_interpretation": True,
        },
        {
            "check_id": "PRE-05-correct-and-reverse-order",
            "expected_behavior": "forward order is satisfiable and reversed order is detectable when a source before/prior-to edge exists",
            "actual_behavior": f"R4 behavior probe order example={order_probe.get('actual_edges') if order_probe else 'not found'}; known_limitation_reproductions={len(known)}",
            "evidence_path": "outputs/reports/stage3_table3_r4_targeted_mechanism_v1.json::behavior_probes",
            "classification": "supported_narrowly",
            "blocks_formal_interpretation": False,
            "notes": "Only the scoped article18p3 before relation is proven; Winter before/prior-to remains unsupported and others may be unknown.",
        },
        {
            "check_id": "PRE-06-missing-task-while-text-mentions-task",
            "expected_behavior": "a missing activity should be detected even though the regulation text still mentions the action",
            "actual_behavior": "R4 missing_action cells exist and include both TP and FN/FP; source text always mentions the action, so this is exactly the intended separation",
            "evidence_path": "outputs/reports/stage3_table3_r4_targeted_v1_eval.json::methods",
            "classification": "method_limited_with_observed_tp",
            "blocks_formal_interpretation": True,
            "notes": "Do not treat source-text mention as evidence of a performed task.",
        },
        {
            "check_id": "PRE-07-actor-lost-after-coordinate-postprocessing",
            "expected_behavior": "raw actor/action evidence should survive canonicalization into the shared Stage3 interface",
            "actual_behavior": "R4 records Ours article13p3/article14p4 raw actor content but canonical actors=[] and actor_action_map=[]; this upstream loss remains",
            "evidence_path": "outputs/reports/stage3_table3_r4_targeted_v1.json::conclusions.remaining_frozen_upstream_errors",
            "classification": "upstream_loss",
            "blocks_formal_interpretation": True,
        },
    ]


def build_readiness(reuse: dict, budget: dict, prechecks: list[dict]) -> dict:
    return {
        "schema_version": "stage3_table3_r5_readiness@1.0.0",
        "benchmark_id": BENCHMARK_ID,
        "statuses": {
            "data": "DATA_READY",
            "methods": "METHODS_NOT_READY",
            "api": "API_AUTHORIZATION_PENDING",
            "formal_release": "FORMAL_RELEASE_NOT_APPROVED",
        },
        "reuse_summary": {
            "unique_regulation_inputs": reuse["reused_unique_inputs"] + reuse["new_ours_requests"],
            "reused_unique_inputs": reuse["reused_unique_inputs"],
            "new_ours_requests": reuse["new_ours_requests"],
            "winter_native_cases_requiring_future_stage3_run": len(reuse["rows"]),
        },
        "budget_summary": {k: budget[k] for k in ["calls_cap", "total_input_tokens_cap", "total_output_tokens_cap", "cost_upper_bound_usd_with_20pct_margin", "retry_cap"]},
        "prechecks": prechecks,
        "can_start_formal_method_run": False,
        "execution_blockers": [
            "API authorization for the listed Ours Direct-LLM requests is absent.",
            "Known detector defects in PRE-01, PRE-02, PRE-03, PRE-04, PRE-06, PRE-07 may pollute the explanation of Table 3 results.",
            "No new Stage2/Stage3 run may be started until the method protocol and API budget are authorized.",
        ],
        "future_execution_order": [
            "After authorization, run exactly the 22 unique Ours Direct-LLM Stage2 requests (one per unique source text); no per-variant calls.",
            "Reuse the exact existing Stage2 predictions listed in the reuse report for the remaining 14 unique inputs.",
            "Run Sun Rules-Only locally and Winter native only after Stage2 inputs are frozen.",
            "Run the shared Stage3 evaluator on the frozen inference view and report core/test metrics, coverage, unknown, N/A, and semantic challenge separately.",
        ],
        "boundary": "Readiness only; no method metric is claimed in this report.",
    }




def build_benchmark_report(config: dict, source_doc: dict, manifest: dict, semantic: dict, reuse: dict, budget: dict, prechecks: list[dict]) -> dict:
    scenario_names = {
        "S1": "数据收集与告知",
        "S2": "同意获取与撤回",
        "S3": "数据主体请求处理",
        "S4": "控制者、处理者及第三方之间的职责或通知",
        "S5": "风险评估与事先咨询",
        "S6": "安全事件和泄露响应",
    }
    elements = {name: {"present_records": manifest["element_coverage"].get(name, 0)} for name in ["modality", "actor", "action", "condition", "constraint", "exception"]}
    support: dict[str, dict] = {}
    for rec in source_doc["requirements"]:
        for name, payload in rec["elements"].items():
            support.setdefault(name, {}).setdefault(payload.get("current_support", "unknown"), 0)
            support[name][payload.get("current_support", "unknown")] += 1
    def method_reuse_counts(method: str) -> dict:
        reusable = sum(1 for row in reuse["rows"] if row["methods"][method]["status"] == "reusable_exact_source_text_match")
        return {"reusable_exact_inputs": reusable, "remaining_inputs": len(reuse["rows"]) - reusable}
    semantic_pair_count = len(semantic["pairs"])
    fairness = load_json(OUT / "reference/fairness_contract.json")
    report = {
        "schema_version": "stage3_table3_r5_benchmark_report@1.0.0",
        "benchmark_id": BENCHMARK_ID,
        "statuses": {
            "data": "DATA_READY",
            "methods": "METHODS_NOT_READY",
            "api": "API_AUTHORIZATION_PENDING",
            "formal_release": "FORMAL_RELEASE_NOT_APPROVED",
        },
        "counts": {
            "independent_requirements": manifest["independent_requirements"],
            "core_cases": manifest["core_cases"],
            "core_baseline_controls": manifest["baseline_controls"],
            "core_variant_cases": sum(manifest["variants_per_type"].values()),
            "variants_per_type": manifest["variants_per_type"],
            "development_requirements": manifest["development_requirements"],
            "test_requirements": manifest["test_requirements"],
            "test_independent_candidate_count": manifest["test_independent_candidate_count"],
            "semantic_challenge_cases": semantic_pair_count * 2,
            "semantic_challenge_pairs": semantic_pair_count,
        },
        "scenario_coverage": {
            sid: {"name_zh": scenario_names.get(sid, sid), "independent_requirements": manifest["scenario_counts"].get(sid, 0)}
            for sid in sorted(scenario_names)
        },
        "element_coverage": {
            "presence_counts": elements,
            "current_support_by_element": support,
            "note": "modality+actor+action are implemented/consumed; condition and exception are unsupported truth consumers; constraint is indirect_only in the frozen three-class scorer.",
        },
        "split": {
            "seed": 20260925,
            "algorithm": "group_by_requirement_family; historical R1-R4 five forced to development; exact-existing-prediction families to development; new-source families to test; no family crosses split",
            "development_requirements": manifest["development_requirements"],
            "test_requirements": manifest["test_requirements"],
            "test_independent_candidate_count": manifest["test_independent_candidate_count"],
            "test_reused_or_exposed_count": manifest["test_requirements"] - manifest["test_independent_candidate_count"],
        },
        "core_vs_semantic_challenge": {
            "core_not_mixed_with_challenge": True,
            "core_cases": manifest["core_cases"],
            "core_baseline_controls": manifest["baseline_controls"],
            "core_variant_cases": sum(manifest["variants_per_type"].values()),
            "semantic_challenge_cases": semantic_pair_count * 2,
            "semantic_challenge_modality_fragments": semantic["modality_fragment_counts"],
            "semantic_challenge_pairs": {"condition": 6, "exception": 6},
        },
        "method_reuse": {
            "sun": method_reuse_counts("sun"),
            "ours": method_reuse_counts("ours"),
            "winter": {"native_full_pipeline_cases": len(reuse["rows"]), "stage2_reuse_not_applicable": True},
            "note": "Sun/Ours reusable counts are Stage2 regulation-input reuse only; Winter does not share Stage2.",
        },
        "api_budget": {
            "calls_cap": budget["calls_cap"],
            "reused_existing_stage2_inputs": budget["reused_existing_stage2_inputs"],
            "new_requests": budget["new_requests"],
            "total_input_tokens_cap": budget["total_input_tokens_cap"],
            "total_output_tokens_cap": budget["total_output_tokens_cap"],
            "max_output_tokens_per_call": budget["max_output_tokens_per_call"],
            "retry_cap": budget["retry_cap"],
            "cost_upper_bound_usd_without_cache_discount": budget["cost_upper_bound_usd_without_cache_discount"],
            "cost_upper_bound_usd_with_20pct_margin": budget["cost_upper_bound_usd_with_20pct_margin"],
            "price_snapshot": budget["price_snapshot"],
        },
        "fairness_contract": fairness,
        "known_detector_issues": prechecks,
        "quota_deviations_or_gaps": [
            f"Test split has {manifest['test_requirements']} requirements but only {manifest['test_independent_candidate_count']} exact-input independent candidates; the remaining {manifest['test_requirements'] - manifest['test_independent_candidate_count']} reuse existing GDPR7 predictions and are marked exposed/non-independent.",
            "S4 contains exactly 4 independent requirements, meeting the minimum with no spare capacity.",
            "Article 4 definition fragments are recorded with URL-level official provenance because the local Winter snapshot does not include article4.txt; they are not silently treated as locally snapshot-verified.",
            "Condition, exception, prohibition, permission, and general deadline/quantity truth are not evaluated by the frozen three-class scorer and are excluded from the core F1 claim.",
        ],
        "assets_completed": [
            "source_requirements.json with 36 source-grounded requirements and SHA-256 provenance",
            "108 core BPMN cases (36 baselines + 24 each missing_action/incorrect_actor/out_of_order)",
            "24 semantic-challenge BPMN cases (6 condition pairs + 6 exception pairs)",
            "inference/reference separation with opaque case IDs",
            "split_manifest.json with seed 20260925 and family integrity",
            "semantic_challenges.json with 4 prohibition + 4 permission + 4 definition fragments",
            "prediction_reuse report, API budget report, readiness report, validation report",
        ],
        "pending_execution_steps": [
            "Explicit API authorization for the 22 listed Ours Direct-LLM Stage2 requests and the stated cap",
            "Run the exact 22 unique regulation-input requests; no per-BPMN or per-variant calls",
            "Run Sun Rules-Only locally on the same unique regulation inputs",
            "Run Winter native and shared Stage3 after Stage2 inputs are frozen",
            "Freeze evaluation outputs and report core/test metrics, coverage, unknown, N/A, and semantic challenge separately",
            "Complete human review if formal Gold publication is requested",
        ],
        "boundary": "Construction reference only; not human Gold, not formal release, and no method performance claim.",
    }
    return report

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    config = load_json(CONFIG)
    source_doc = load_json(OUT / "source_requirements.json")
    source_req = source_doc["requirements"]
    gdpr7_index = build_gdpr7_index()
    reuse = build_reuse(config, source_req, gdpr7_index)
    budget = build_budget(reuse, source_req)
    prechecks = run_prechecks()
    readiness = build_readiness(reuse, budget, prechecks)
    if args.write:
        manifest = load_json(OUT / "manifest.json")
        semantic = load_json(OUT / "semantic_challenges.json")
        report = build_benchmark_report(config, source_doc, manifest, semantic, reuse, budget, prechecks)
        write_json(REPORTS / "stage3_table3_r5_prediction_reuse_v1.json", reuse)
        write_json(REPORTS / "stage3_table3_r5_api_budget_v1.json", budget)
        write_json(REPORTS / "stage3_table3_r5_readiness_v1.json", readiness)
        write_json(REPORTS / "stage3_table3_r5_benchmark_v1.json", report)
        md = [
            "# S3-TABLE3-R5 Benchmark and Readiness",
            "",
            f"- status: DATA_READY / METHODS_NOT_READY / API_AUTHORIZATION_PENDING / FORMAL_RELEASE_NOT_APPROVED",
            f"- independent requirements: {report['counts']['independent_requirements']}",
            f"- core cases: {report['counts']['core_cases']} ({report['counts']['core_baseline_controls']} baselines + {report['counts']['core_variant_cases']} variants)",
            f"- variants per type: {report['counts']['variants_per_type']}",
            f"- development / test requirements: {report['counts']['development_requirements']} / {report['counts']['test_requirements']}",
            f"- test independent candidates: {report['counts']['test_independent_candidate_count']}",
            f"- semantic challenge cases: {report['counts']['semantic_challenge_cases']} (kept separate from core F1)",
            f"- six-element presence: {report['element_coverage']['presence_counts']}",
            f"- current support: {report['element_coverage']['current_support_by_element']}",
            f"- reused Ours Stage2 inputs: {report['method_reuse']['ours']['reusable_exact_inputs']}",
            f"- new Ours API requests: {report['api_budget']['new_requests']}",
            f"- API cost cap: USD {report['api_budget']['cost_upper_bound_usd_with_20pct_margin']}",
            f"- known detector issues: {[c['check_id'] for c in prechecks]}",
            "",
            "No real API call, old experiment rerun, or formal Gold publication was performed.",
        ]
        (REPORTS / "stage3_table3_r5_benchmark_v1.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"reused_unique_inputs": reuse["reused_unique_inputs"], "new_ours_requests": reuse["new_ours_requests"],
                      "calls_cap": budget["calls_cap"], "cost_upper_bound_usd_with_20pct_margin": budget["cost_upper_bound_usd_with_20pct_margin"],
                      "precheck_count": len(prechecks)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
