# -*- coding: utf-8 -*-
"""Build the final Stage-3 convergence report, root-cause ledger, and API gate.

This script is deterministic post-processing over the single frozen Stage-3
development run.  It does not call a model, read Gold into a method, mutate
predictions, or rerun any experiment.
"""

from __future__ import annotations

import json
import subprocess
from importlib import metadata
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs/reports"
DEV_OUT = ROOT / "outputs/development/stage3_final_v1"
BASE_REPORT = REPORTS / "stage3_final_convergence_report_v1.json"
BASE_REPORT_MD = REPORTS / "stage3_final_convergence_report_v1.md"
GRID = DEV_OUT / "dev_calibration_grid_v1.json"
SEM_FREEZE = REPORTS / "stage3_final_semantic_backend_freeze_v1.json"
ORDER_FREEZE = REPORTS / "stage3_final_order_adapter_freeze_v1.json"
ORDER_ELIG = REPORTS / "stage3_final_order_eligibility_v1.json"
POOL = ROOT / "data/development/stage3_final_development_pool_v1.json"
SUPPLEMENT = ROOT / "data/development/stage3_final_order_supplement_v1/manifest.json"
SPLIT = ROOT / "data/development/stage3_table3_r5_benchmark_v2/split_manifest.json"
ROOT_CAUSE_OUT = REPORTS / "stage3_final_convergence_root_causes_v1.json"
ATTRIBUTION_OUT = REPORTS / "stage3_final_improvement_attribution_v1.json"
API_PACKET_OUT = REPORTS / "stage3_final_api_authorization_packet_v1.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def git_info() -> dict[str, Any]:
    def run(*args: str) -> str:
        try:
            return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                                  text=True, check=True).stdout.strip()
        except Exception as exc:  # noqa: BLE001
            return f"<unavailable: {exc}>"

    return {
        "branch": run("branch", "--show-current"),
        "head_at_report_generation": run("rev-parse", "HEAD"),
        "starting_head": "5b2e1ffaf7189992a5f7c779aa41dffcb8a6787c",
        "status_short": run("status", "--short").splitlines(),
        "force_push_allowed": False,
        "note": "The post-report checkpoint commit hash is recorded in the handoff, not predicted inside this report.",
    }


def model_size_info(model_path: str | None) -> dict[str, Any]:
    if not model_path:
        return {"available": False}
    base = Path(model_path)
    snapshot = base
    revision = None
    refs = None
    # Walk up to the cache root if a snapshot directory was supplied.
    for parent in [base, *base.parents]:
        candidate_ref = parent / "refs" / "main"
        if candidate_ref.exists():
            refs = candidate_ref
            break
    if refs:
        revision = refs.read_text(encoding="utf-8").strip()
    weights_candidates = [
        snapshot / "model.safetensors",
        snapshot / "pytorch_model.bin",
    ]
    weight = next((p for p in weights_candidates if p.exists()), None)
    core_files = [
        snapshot / "config.json",
        snapshot / "config_sentence_transformers.json",
        snapshot / "modules.json",
        snapshot / "sentence_bert_config.json",
        snapshot / "tokenizer.json",
        snapshot / "tokenizer_config.json",
        snapshot / "special_tokens_map.json",
        snapshot / "vocab.txt",
        snapshot / "1_Pooling" / "config.json",
    ]
    if weight:
        core_files.append(weight)
    total = sum(p.stat().st_size for p in core_files if p.exists())
    return {
        "available": True,
        "model_path": str(base),
        "revision": revision,
        "weight_file": str(weight.relative_to(snapshot)) if weight else None,
        "core_inference_size_mib": round(total / (1024 * 1024), 3),
        "core_files": [str(p.relative_to(snapshot)) for p in core_files if p.exists()],
        "pooling_config": load_json(snapshot / "1_Pooling" / "config.json") if (snapshot / "1_Pooling" / "config.json").exists() else None,
        "modules": load_json(snapshot / "modules.json") if (snapshot / "modules.json").exists() else None,
    }


def versions() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for package in ("torch", "transformers", "sentence-transformers", "numpy", "spacy"):
        try:
            out[package] = metadata.version(package)
        except Exception:  # noqa: BLE001
            out[package] = None
    return out


def build_root_causes(base: Mapping[str, Any], eligibility: Mapping[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "id": "RC-SEM-01",
            "symptom": "Frozen R1 spaCy SM semantic backend under-mapped action predicates and left a large missing-action bottleneck.",
            "root_cause": "The small spaCy model has no static word vectors and only weak context tensors; shared action matching lacked a sentence-level semantic encoder.",
            "evidence": "Existing R1 diagnostic reported Ours action mapping 61/93 with SM versus 82/93 with MD; the final run exposes the same action-mapping gap.",
            "proposed_fix": "Promote a shared, local, Gold-blind MPNet backend using the model's declared mean-token pooling and L2 normalization.",
            "implemented": True,
            "sun_affected": True,
            "ours_affected": True,
            "gold_independent": True,
            "dev_effect": "MPNet was selected against the current R1 SM backend by the pre-registered method-neutral objective.",
            "status": "FIXED_AND_FROZEN",
        },
        {
            "id": "RC-MISS-01",
            "symptom": "Missing-action precision remains low because extra/fragment Stage-2 actions are scored as mandatory obligations.",
            "root_cause": "Stage-2 action spans sometimes contain subordinate fragments (e.g. prepositional continuations) and non-core clause actions; the denominator is not obligation-scoped.",
            "evidence": "The final selected run still has low missing-action precision for both methods; no obligation-scope revision was needed to remove the interface failure.",
            "proposed_fix": "If a future authorized run shows the same systematic fragment pattern, apply at most one shared ObligationScopedActionProjection revision.",
            "implemented": False,
            "sun_affected": True,
            "ours_affected": True,
            "gold_independent": True,
            "dev_effect": "Not changed; kept frozen to avoid an unlicensed second refinement.",
            "status": "DEFERRED_SINGLE_ALLOWED_REVISION",
        },
        {
            "id": "RC-ACTOR-01",
            "symptom": "Actor coverage and unknown rate remain uneven, especially for Sun.",
            "root_cause": "Definition 6 is intentionally action-bound; Stage-2 actor-action maps are incomplete for some records, so the cell is legitimately unknown rather than guessed.",
            "evidence": "Selected run coverage and unknown rates are reported separately; actor formula was not changed.",
            "proposed_fix": "No formula change. Preserve Definition 6 and report coverage.",
            "implemented": False,
            "sun_affected": True,
            "ours_affected": True,
            "gold_independent": True,
            "dev_effect": "Actor method frozen as required.",
            "status": "FROZEN_NO_CHANGE",
        },
        {
            "id": "RC-ORDER-01",
            "symptom": "Sun/Ours frozen Stage-2 records had empty order_relations, so Definition 7 always had denominator zero.",
            "root_cause": "Sun's paper requires U_r subset A_r x A_r but does not publish an automatic extraction algorithm; the project had no shared U_r adapter.",
            "evidence": "Frozen Sun/Ours order_relations were empty; new SharedRuleOrderAdapterV3 generated non-empty edges for R5-D-01/R5-D-02 Sun and for the R5-S4-T3 supplement for both methods.",
            "proposed_fix": "Implement one documented, Gold-blind, method-neutral SharedRuleOrderAdapterV3 using temporal markers, general syntax, existing Stage-2 actions, and the shared matcher.",
            "implemented": True,
            "sun_affected": True,
            "ours_affected": True,
            "gold_independent": True,
            "dev_effect": "Order F1 moved from interface-missing zero to 0.5 for both methods on the capability-aligned development scope.",
            "status": "FIXED_AND_FROZEN",
        },
        {
            "id": "RC-ORDER-02",
            "symptom": "Several source temporal relations have a nominalized or absent second action and cannot satisfy U_r subset A_r x A_r.",
            "root_cause": "Frozen Stage-2 A_r does not contain the second endpoint (e.g. approving, informing, lifted) for R5-S7-T1/R5-S8-T1 and some nominalized cases.",
            "evidence": "Adapter audits show no unique existing action pair for those requirements; they are retained in the eligibility report as outside/diagnostic rather than deleted.",
            "proposed_fix": "Capability-aligned order eligibility; keep them as diagnostics. Do not invent nominal-to-action endpoints.",
            "implemented": True,
            "sun_affected": True,
            "ours_affected": True,
            "gold_independent": True,
            "dev_effect": "Unknown order cells are reported instead of setting F1 to zero through spurious edges.",
            "status": "DOCUMENTED_FROZEN",
        },
        {
            "id": "RC-COV-01",
            "symptom": "Ours has no order edge for R5-D-01/R5-D-02 because its Stage-2 A_r lacks a process endpoint.",
            "root_cause": "Ours extracts the `provide ... prior to further processing` predicate as one action and does not separately extract `process`; this is a Stage-2 representation coverage gap.",
            "evidence": "Final order rows show Sun edges for D-01/D-02 but Ours denominator zero; this is the intended method comparison, not an adapter bug.",
            "proposed_fix": "Do not post-hoc repair Ours. A future authorized Stage-2 run may cover it; the final unseen run must not tune on this development result.",
            "implemented": False,
            "sun_affected": False,
            "ours_affected": True,
            "gold_independent": True,
            "dev_effect": "Ours order recall remains limited on existing cases; supplement gives an observable order signal.",
            "status": "REPRESENTATION_LIMITATION_FROZEN",
        },
    ]
    return {
        "schema_version": "stage3_final_convergence_root_causes@1.0.0",
        "status": "ROOT_CAUSE_LEDGER_FROZEN_AFTER_SINGLE_CONVERGENCE_RUN",
        "rows": rows,
        "open_root_cause_count": sum(1 for row in rows if row["status"] not in ("FIXED_AND_FROZEN", "DOCUMENTED_FROZEN", "FROZEN_NO_CHANGE")),
    }


def build_attribution(grid: Mapping[str, Any]) -> dict[str, Any]:
    best: dict[str, Mapping[str, Any]] = {}
    for backend, rows in grid["backends"].items():
        best[backend] = max(rows, key=lambda row: tuple(row["tie_break_key"]))
    sm = best.get("spacy_en_core_web_sm")
    mp = best.get("sentence_transformers_all_mpnet_base_v2")
    md = best.get("spacy_en_core_web_md")
    out: dict[str, Any] = {
        "schema_version": "stage3_final_improvement_attribution@1.0.0",
        "all_seen_development_pool": True,
        "comparable_backend_comparison": {},
        "order_representation": {},
        "action_scope_revision": {"implemented": False, "attributed_delta": None},
    }
    if sm and mp:
        for method in ("sun", "ours"):
            smr = sm[method]
            mpr = mp[method]
            out["comparable_backend_comparison"][method] = {
                "sm_to_mpnet_overall_micro_f1_delta": mpr["micro_f1"] - smr["micro_f1"],
                "sm_to_mpnet_macro_f1_delta": mpr["macro_f1"] - smr["macro_f1"],
                "sm_to_mpnet_missing_f1_delta": mpr["per_type"]["missing_action"]["f1"] - smr["per_type"]["missing_action"]["f1"],
                "sm_to_mpnet_actor_f1_delta": mpr["per_type"]["incorrect_actor"]["f1"] - smr["per_type"]["incorrect_actor"]["f1"],
                "sm_to_mpnet_order_f1_delta": mpr["per_type"]["out_of_order"]["f1"] - smr["per_type"]["out_of_order"]["f1"],
            }
    out["order_representation"] = {
        "old_frozen_r1_order_f1_on_previous_scope": 0.0,
        "new_selected_order_f1": mp["ours"]["per_type"]["out_of_order"]["f1"] if mp else None,
        "components": [
            "RC-ORDER-01 shared RuleRecord U_r adapter made order_relations non-empty where endpoints exist",
            "RC-ORDER-02 capability-aligned eligibility moved endpoint-unbound requirements out of the main F1 and retained them as diagnostics",
            "DEVELOPMENT-ONLY supplement supplied the missing R5-S4-T3 out_of_order control for an already-extracted action pair",
        ],
        "isolation_note": "The order change is a bundle of adapter + eligibility + supplement; it is not claimed as a single algorithmic F1 delta.",
    }
    return out


def build_api_packet(base: Mapping[str, Any], eligibility: Mapping[str, Any]) -> dict[str, Any]:
    split = load_json(SPLIT)
    candidates = list(split.get("candidate_requirement_ids") or [])
    return {
        "schema_version": "stage3_final_api_authorization_packet@1.0.0",
        "status": "API_AUTHORIZATION_REQUIRED",
        "STAGE3_METHOD_FROZEN": True,
        "FINAL_UNSEEN_BENCHMARK_PREPARED": False,
        "API_AUTHORIZATION_PACKET_READY": True,
        "candidate_unseen_requirement_ids": candidates,
        "candidate_count": len(candidates),
        "recommended_final_requirement_count": "12-16",
        "frozen_predictions_exist_for_candidates": False,
        "exact_blocker": (
            "There is no authorized unseen Stage-2/Gold packet for a 12-16 requirement source-family-separated GDPR holdout. "
            "The five remaining benchmark-v2 candidate requirements are source-only candidates and have no BPMN mutation packet or Ours prediction."
        ),
        "required_user_decisions": [
            "Approve the unseen source-family split and the exact 12-16 GDPR requirements for the final holdout.",
            "Approve construction/freeze of the final BPMN baselines, mutations, and prediction-blind Gold packet before any new Ours prediction.",
            "Approve the Ours Stage2 model, prompt hash, exact call count, max tokens, and worst-case cost cap for those final requirements.",
        ],
        "sun_api_calls_required": 0,
        "ours_api_calls_estimate_if_candidates_only": len(candidates),
        "ours_api_calls_estimate_if_12_to_16": "12-16 Stage-2 requests plus retries bounded by the approved protocol",
        "do_not_execute_without_explicit_authorization": True,
    }


def build_report(base: Mapping[str, Any], grid: Mapping[str, Any], eligibility: Mapping[str, Any],
                 root_causes: Mapping[str, Any], attribution: Mapping[str, Any],
                 api_packet: Mapping[str, Any], sem_freeze: Mapping[str, Any],
                 order_freeze: Mapping[str, Any]) -> dict[str, Any]:
    model_identity = (sem_freeze.get("selected_backend") or {})
    model_info = model_size_info(model_identity.get("model_path"))
    result: dict[str, Any] = {
        "schema_version": "stage3_final_convergence_report@2.0.0",
        "status": "STAGE3_METHOD_FROZEN_FINAL_UNSEEN_BENCHMARK_BLOCKED_PENDING_USER_AUTHORIZATION",
        "winter_mainline_status": "ARCHIVED_EXTERNAL_BASELINE",
        "report_a_git": git_info(),
        "report_b_root_causes": root_causes,
        "report_c_mpnet": {
            "backend": model_identity.get("short_name"),
            "kind": model_identity.get("kind"),
            "model_path": model_identity.get("model_path"),
            "model_info": model_info,
            "environment_versions": versions(),
            "pooling": "sentence-transformers declared mean-token pooling (1_Pooling/config.json) + L2 normalize",
            "similarity": "cosine after L2 normalization, clamped to [0,1]",
            "selected_gamma": base["selected"]["gamma"],
            "selected_theta": base["selected"]["theta"],
            "network_calls": 0,
            "downloaded_models_during_run": [],
            "backend_comparison": {},
        },
        "report_d_order_eligibility": eligibility,
        "report_e_order_adapter": {
            "adapter": "SharedRuleOrderAdapterV3",
            "schema_version": order_freeze.get("schema_version"),
            "implementation_sha256": order_freeze.get("implementation_sha256"),
            "gold_used": False,
            "method_shared": True,
            "nominal_to_action_invention": False,
            "generated_pairs": {},
            "ambiguous_or_failed_families": [],
            "u_r_generation_rate": {},
        },
        "report_f_development_result": {
            "definition": "pooled TP/FP/FN over all scored development cells for the frozen selected backend",
            "main_table": {m: base["dev_result"][m]["overall"] for m in ("sun", "ours")},
            "breakdown": {m: base["dev_result"][m]["per_type"] for m in ("sun", "ours")},
            "coverage": {m: base["dev_result"][m]["overall"]["coverage"] for m in ("sun", "ours")},
            "unknown_rate": {m: base["dev_result"][m]["overall"]["unknown_rate"] for m in ("sun", "ours")},
            "all_existing_cases_seen": True,
            "final_test_eligible": False,
        },
        "report_g_improvement_attribution": attribution,
        "report_h_remaining_limitations": [
            "Final unseen benchmark/Gold packet is not constructed; only five source-only candidate requirements remain.",
            "No Ours Stage-2 predictions exist for the unseen candidate requirements; explicit API authorization is required.",
            "Ours Stage-2 A_r lacks a distinct process endpoint for R5-D-01/R5-D-02, so order recall is limited there.",
            "R5-S7-T1/R5-S8-T1 are source action-action relations but their second endpoints are absent from both frozen Stage-2 A_r records.",
            "Actor unknown remains material for Sun due to Definition 6 action-bound coverage; Definition 6 was intentionally not changed.",
            "Missing-action precision remains limited by extra/fragment Stage-2 actions; no second action-scope revision was applied.",
        ],
        "report_i_freeze_status": {
            "SEMANTIC_BACKEND_FINAL_FROZEN": True,
            "GAMMA_FINAL_FROZEN": True,
            "THETA_FINAL_FROZEN": True,
            "MISSING_ACTION_METHOD_FROZEN": True,
            "ACTOR_METHOD_FROZEN": True,
            "ORDER_ELIGIBILITY_FROZEN": True,
            "ORDER_U_R_ADAPTER_FROZEN": True,
            "STAGE3_METHOD_FROZEN": True,
        },
        "report_j_final_table3_readiness": {
            "FINAL_TABLE3_READY": False,
            "FINAL_UNSEEN_BENCHMARK_PREPARED": False,
            "API_AUTHORIZATION_PACKET_READY": True,
            "exact_blocker": api_packet["exact_blocker"],
            "exact_next_action": "User must approve the final unseen source split, Gold/BPMN freeze, and bounded Ours Stage-2 API calls.",
            "api_packet": api_packet,
        },
        "legacy_development_report": base,
    }
    # backend comparison table
    for backend, rows in grid["backends"].items():
        best = max(rows, key=lambda row: tuple(row["tie_break_key"]))
        result["report_c_mpnet"]["backend_comparison"][backend] = {
            "gamma": best["gamma"],
            "theta": best["theta"],
            "objective": best["objective"],
            **{
                f"{method}_{metric}": (
                    best[method]["overall"]["f1"] if metric == "overall_f1"
                    else best[method]["macro_f1"] if metric == "macro_f1"
                    else best[method]["per_type"][metric]["f1"]
                )
                for method in ("sun", "ours")
                for metric in ("overall_f1", "macro_f1", "missing_action", "incorrect_actor", "out_of_order")
            },
        }
    # generated U_r pairs by method/requirement from order rows
    generated: dict[str, list[str]] = {"sun": [], "ours": []}
    failed: list[dict[str, Any]] = []
    for row in base.get("order_type_a_rows") or []:
        req = str(row["requirement_id"])
        for method in ("sun", "ours"):
            edges = ((row.get("methods") or {}).get(method) or {}).get("edges") or []
            if edges and req not in generated[method]:
                generated[method].append(req)
            if not edges:
                failed.append({"requirement_id": req, "method": method,
                               "reason": ((row.get("methods") or {}).get(method) or {}).get("signal_reason")})
    result["report_e_order_adapter"]["generated_pairs"] = generated
    result["report_e_order_adapter"]["ambiguous_or_failed_families"] = failed
    for method in ("sun", "ours"):
        main_requirements = list(eligibility.get("main_requirements") or [])
        generated_count = len(set(generated[method]) & set(main_requirements))
        result["report_e_order_adapter"]["u_r_generation_rate"][method] = {
            "generated_main_requirements": generated_count,
            "main_requirements": len(main_requirements),
            "rate": (generated_count / len(main_requirements)) if main_requirements else None,
        }
    return result


def format_md(report: Mapping[str, Any]) -> str:
    sel = report["legacy_development_report"]["selected"]
    dev = report["legacy_development_report"]["dev_result"]
    lines = [
        "# Stage 3 Final Convergence Report v1",
        "",
        f"- status: `{report['status']}`",
        f"- selected backend: `{sel['backend']}`",
        f"- gamma / theta / tau: `{sel['gamma']}` / `{sel['theta']}` / `{sel['tau']}`",
        f"- stage3 method frozen: `{report['report_i_freeze_status']['STAGE3_METHOD_FROZEN']}`",
        f"- final unseen benchmark prepared: `{report['report_j_final_table3_readiness']['FINAL_UNSEEN_BENCHMARK_PREPARED']}`",
        "",
        "## A. Git",
        "",
        f"- branch: `{report['report_a_git']['branch']}`",
        f"- starting HEAD: `{report['report_a_git']['starting_head']}`",
        f"- HEAD at report generation: `{report['report_a_git']['head_at_report_generation']}`",
        f"- force push allowed: `{report['report_a_git']['force_push_allowed']}`",
        "",
        "## B. Root Causes",
        "",
        "| ID | Status | Root cause |",
        "|---|---|---|",
    ]
    for row in report["report_b_root_causes"]["rows"]:
        lines.append(f"| {row['id']} | {row['status']} | {row['root_cause']} |")
    lines.extend([
        "",
        "## C. MPNet / Backend Comparison",
        "",
        f"- model: `{report['report_c_mpnet']['model_path']}`",
        f"- core inference size MiB: `{report['report_c_mpnet']['model_info'].get('core_inference_size_mib')}`",
        f"- pooling: `{report['report_c_mpnet']['pooling']}`",
        f"- selected gamma/theta: `{report['report_c_mpnet']['selected_gamma']}` / `{report['report_c_mpnet']['selected_theta']}`",
        "",
        "| Backend | gamma | theta | Sun macro | Ours macro | Sun micro | Ours micro | Sun order F1 | Ours order F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for backend, row in report["report_c_mpnet"]["backend_comparison"].items():
        lines.append(
            f"| {backend} | {fmt(row['gamma'],2)} | {fmt(row['theta'],2)} | "
            f"{fmt(row['sun_macro_f1'])} | {fmt(row['ours_macro_f1'])} | "
            f"{fmt(row['sun_overall_f1'])} | {fmt(row['ours_overall_f1'])} | "
            f"{fmt(row['sun_out_of_order'])} | {fmt(row['ours_out_of_order'])} |"
        )
    lines.extend([
        "",
        "## D. Order Eligibility",
        "",
        "| Requirement | Type | Evidence | Main metric? | Reason |",
        "|---|---|---|---|---|",
    ])
    for rid, row in sorted(report["report_d_order_eligibility"]["requirements"].items()):
        lines.append(
            f"| {rid} | {row.get('order_type')} | {row.get('order_evidence')} | "
            f"{row.get('main_metric')} | {row.get('reason')} |"
        )
    lines.extend([
        "",
        "## E. Shared Rule Order Adapter",
        "",
        f"- adapter: `{report['report_e_order_adapter']['adapter']}`",
        f"- Gold used: `{report['report_e_order_adapter']['gold_used']}`",
        f"- generated U_r: `{report['report_e_order_adapter']['generated_pairs']}`",
        f"- U_r generation rates: `{report['report_e_order_adapter']['u_r_generation_rate']}`",
        "",
        "## F. Final Development Result",
        "",
        "| Method | Precision | Recall | F1 |",
        "|---|---:|---:|---:|",
    ])
    for method in ("sun", "ours"):
        overall = dev[method]["overall"]
        lines.append(
            f"| {method.capitalize()} | {fmt(overall['precision'])} | {fmt(overall['recall'])} | {fmt(overall['f1'])} |"
        )
    lines.extend([
        "",
        "| Method | Missing F1 | Actor F1 | Order F1 | Macro-F1 | Coverage | Unknown rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for method in ("sun", "ours"):
        row = dev[method]
        overall = row["overall"]
        lines.append(
            f"| {method.capitalize()} | {fmt(row['per_type']['missing_action']['f1'])} | "
            f"{fmt(row['per_type']['incorrect_actor']['f1'])} | "
            f"{fmt(row['per_type']['out_of_order']['f1'])} | {fmt(row['macro_f1'])} | "
            f"{fmt(overall['coverage'])} | {fmt(overall['unknown_rate'])} |"
        )
    lines.extend([
        "",
        "## G. Improvement Attribution",
        "",
        f"- backend comparison: `{report['report_g_improvement_attribution']['comparable_backend_comparison']}`",
        f"- order representation: `{report['report_g_improvement_attribution']['order_representation']}`",
        "",
        "## H. Remaining Limitations",
        "",
    ])
    for item in report["report_h_remaining_limitations"]:
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## I. Freeze Status",
        "",
    ])
    for key, value in report["report_i_freeze_status"].items():
        lines.append(f"- {key} = `{value}`")
    lines.extend([
        "",
        "## J. Final Table 3 Readiness",
        "",
        f"- FINAL_TABLE3_READY = `{report['report_j_final_table3_readiness']['FINAL_TABLE3_READY']}`",
        f"- FINAL_UNSEEN_BENCHMARK_PREPARED = `{report['report_j_final_table3_readiness']['FINAL_UNSEEN_BENCHMARK_PREPARED']}`",
        f"- API_AUTHORIZATION_PACKET_READY = `{report['report_j_final_table3_readiness']['API_AUTHORIZATION_PACKET_READY']}`",
        f"- exact blocker: {report['report_j_final_table3_readiness']['exact_blocker']}",
        f"- exact next action: {report['report_j_final_table3_readiness']['exact_next_action']}",
        "",
        "## API Gate",
        "",
        f"- status: `{report['report_j_final_table3_readiness']['api_packet']['status']}`",
        f"- candidate unseen requirements: `{report['report_j_final_table3_readiness']['api_packet']['candidate_unseen_requirement_ids']}`",
        f"- do not execute without explicit authorization: `{report['report_j_final_table3_readiness']['api_packet']['do_not_execute_without_explicit_authorization']}`",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    base = load_json(BASE_REPORT)
    if "legacy_development_report" in base:
        base = base["legacy_development_report"]
    grid = load_json(GRID)
    eligibility = load_json(ORDER_ELIG)
    sem_freeze = load_json(SEM_FREEZE)
    order_freeze = load_json(ORDER_FREEZE)
    root_causes = build_root_causes(base, eligibility)
    attribution = build_attribution(grid)
    api_packet = build_api_packet(base, eligibility)
    report = build_report(base, grid, eligibility, root_causes, attribution, api_packet,
                          sem_freeze, order_freeze)
    write_json(ROOT_CAUSE_OUT, root_causes)
    write_json(ATTRIBUTION_OUT, attribution)
    write_json(API_PACKET_OUT, api_packet)
    write_json(BASE_REPORT, report)
    BASE_REPORT_MD.write_text(format_md(report), encoding="utf-8", newline="\n")
    print("wrote", ROOT_CAUSE_OUT)
    print("wrote", ATTRIBUTION_OUT)
    print("wrote", API_PACKET_OUT)
    print("wrote", BASE_REPORT)
    print("wrote", BASE_REPORT_MD)


if __name__ == "__main__":
    main()
