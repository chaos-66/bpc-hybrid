# -*- coding: utf-8 -*-
"""Run the BONUS Stage-3 development replay.

Existing frozen signals are reused.  For the new development-only order
supplement, the frozen SharedRuleOrderAdapterV3 and shared checker are run with
the frozen MPNet/gamma/theta/tau.  No real Stage-2 or LLM API is called.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import spacy  # noqa: E402

from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file  # noqa: E402
from bpc_hybrid.stage3_v2.checker_v2 import SharedStage3CheckerV2  # noqa: E402
from bpc_hybrid.stage3_v2.evaluation_v2 import MAIN_ORDER_TYPE, evaluate_dev_method  # noqa: E402
from bpc_hybrid.stage3_v2.rule_order_adapter_v3 import SharedRuleOrderAdapterV3  # noqa: E402
from bpc_hybrid.stage3_v2.rule_record_converter_v2 import canonical_to_rule_record_v2  # noqa: E402
from bpc_hybrid.stage3_v2.semantic_matcher_v2 import ST_MPNET, SharedSemanticMatcherV2  # noqa: E402
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402

DEV_POOL = ROOT / "data/development/stage3_final_development_pool_v1.json"
CURRENT_SUPPLEMENT = ROOT / "data/development/stage3_final_order_supplement_v1/manifest.json"
BONUS_SUPPLEMENT = ROOT / "data/development/stage3_bonus_order_supplement_v1/manifest.json"
EXISTING_SIGNALS = ROOT / "outputs/development/stage3_final_v1/selected_dev_signals_v1.json"
ORDER_ELIGIBILITY = ROOT / "outputs/reports/stage3_final_order_eligibility_v1.json"
STAGE1_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
REPORTS = ROOT / "outputs/reports"
ORDER_OUT_JSON = REPORTS / "stage3_bonus_order_generalization_v1.json"
ORDER_OUT_MD = REPORTS / "stage3_bonus_order_generalization_v1.md"
DEV_OUT_JSON = REPORTS / "stage3_bonus_development_report_v1.json"
DEV_OUT_MD = REPORTS / "stage3_bonus_development_report_v1.md"
GAMMA = 0.55
THETA = 0.45
TAU = 0.8

BASELINE = {
    "sun": {"precision": 0.38144329896907214, "recall": 0.5362318840579711, "f1": 0.4457831325301205,
            "missing_f1": 0.4554455445544555, "actor_f1": 0.4262295081967213, "order_f1": 0.5,
            "macro_f1": 0.46055835091705893, "coverage": 0.6667, "unknown_rate": 0.3333},
    "ours": {"precision": 0.4392523364485981, "recall": 0.6811594202898551, "f1": 0.5340909090909091,
             "missing_f1": 0.49350649350649356, "actor_f1": 0.5684210526315789, "order_f1": 0.5,
             "macro_f1": 0.5206425153793575, "coverage": 0.8905, "unknown_rate": 0.1095},
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def canonical_from_stub(stub: Mapping[str, Any]) -> dict[str, Any]:
    source_text = str(stub["source_text"])
    actions = []
    for row in stub["actions"]:
        actions.append({
            "id": str(row["id"]),
            "text": str(row["text"]),
            "normalized": str(row["text"]),
            "start": int(row["start"]),
            "end": int(row["end"]),
        })
    clause = {
        "clause_id": str(stub["clause_id"]),
        "clause_span": {"start": 0, "end": len(source_text), "text": source_text},
        "modality": {"label": "obligation", "evidence": []},
        "actions": actions,
        "actors": [],
        "actor_action_map": [],
        "conditions": [],
        "constraints": [],
        "exceptions": [],
        "order_relations": [],
    }
    return {
        "sample_id": str(stub["clause_id"]).split(".")[0],
        "source_text": source_text,
        "clauses": [clause],
        "unsupported_or_ambiguous": [],
    }


def adapter_failure_reason(projection: Mapping[str, Any]) -> str | None:
    if projection.get("edges"):
        return None
    audits = list(projection.get("markers") or [])
    if not audits:
        return "OERR_TEMPORAL_MARKER_UNRESOLVED"
    for audit in audits:
        status_reason = str(audit.get("status_reason") or "")
        if status_reason == "empty_clause_context":
            return "OERR_TEMPORAL_MARKER_UNRESOLVED"
        if status_reason == "no_action_candidate_for_one_side":
            return "OERR_SEMANTIC_ENDPOINT_BINDING_FAIL"
        if status_reason == "ambiguous_or_below_threshold_endpoint_pair":
            return "OERR_ENDPOINT_AMBIGUOUS"
    return "OERR_OTHER"


def main() -> int:
    matcher = SharedSemanticMatcherV2.for_backend(ST_MPNET)
    nlp = spacy.load("en_core_web_sm")
    order_adapter = SharedRuleOrderAdapterV3(matcher)
    checker = SharedStage3CheckerV2(matcher, nlp, tau=TAU, gamma=GAMMA, theta=THETA)
    stage1_contract = load_stage1_contract(STAGE1_CONTRACT)

    dev = load_json(DEV_POOL)
    current = load_json(CURRENT_SUPPLEMENT)
    bonus = load_json(BONUS_SUPPLEMENT)
    signals_doc = load_json(EXISTING_SIGNALS)
    signals: dict[str, dict[tuple[str, str, str], Mapping[str, Any]]] = {
        "sun": dict(signals_doc["signals"]["sun"]),
        "ours": dict(signals_doc["signals"]["ours"]),
    }

    all_cases: list[dict[str, Any]] = [dict(c) for c in dev["cases"]]
    all_cases.extend({**dict(c), "_case_root": "current_supplement"} for c in current["cases"])
    all_cases.extend({**dict(c), "_case_root": "bonus_supplement"} for c in bonus["cases"])

    # Existing selected signals are nested case -> check_type; flatten to the
    # evaluator's (method, case_id, check_type) key.
    flat: dict[str, dict[tuple[str, str, str], Mapping[str, Any]]] = {"sun": {}, "ours": {}}
    for method in ("sun", "ours"):
        for case_id, checks in signals[method].items():
            for check_type, value in checks.items():
                flat[method][(method, case_id, check_type)] = value

    bonus_requirement_rows: list[dict[str, Any]] = []
    for req_id, req in bonus["requirements"].items():
        stub = req["endpoint_stub"]
        canonical = canonical_from_stub(stub)
        converted = canonical_to_rule_record_v2(canonical, str(stub["source_text"]), req_id, nlp, order_adapter=order_adapter)
        projection = converted.get("conversion_audit", {}).get("order_projection") or {}
        failure = adapter_failure_reason(projection)
        row = {
            "requirement_id": req_id,
            "citation": req["citation"],
            "source_text": req["source_text"],
            "before_action": req["before_action"],
            "after_action": req["after_action"],
            "eligibility_class": req["eligibility_class"],
            "o_flags": req["o_flags"],
            "endpoint_availability": req["endpoint_availability"],
            "sun_ur": projection.get("edge_pairs") or [],
            "ours_ur": projection.get("edge_pairs") or [],
            "adapter_projection_status": projection.get("status"),
            "adapter_projection_reason": projection.get("status_reason"),
            "failure_reason": failure,
            "cases": {},
        }
        for case in bonus["cases"]:
            if str(case["requirement_id"]) != req_id:
                continue
            if str(case.get("_case_root")) != "bonus_supplement":
                case_root = ROOT / "data/development/stage3_bonus_order_supplement_v1"
            else:
                case_root = ROOT / "data/development/stage3_bonus_order_supplement_v1"
            bpmn_path = case_root / str(case["bpmn_path"])
            model = SunProcessModel(str(case["process_id"]), parse_bpmn_file(bpmn_path, contract=stage1_contract), nlp)
            checked = checker.check_rule_record(converted, model)
            variant = str(case["variant"])
            for method in ("sun", "ours"):
                flat[method][(method, str(case["case_id"]), "missing_action")] = checked["missing_action"]
                flat[method][(method, str(case["case_id"]), "incorrect_actor")] = checked["incorrect_actor"]
                flat[method][(method, str(case["case_id"]), "out_of_order")] = checked["out_of_order"]
            row["cases"][variant] = {
                "case_id": case["case_id"],
                "gold_out_of_order": case["reference_states"]["out_of_order"],
                "missing_action": checked["missing_action"],
                "incorrect_actor": checked["incorrect_actor"],
                "out_of_order": checked["out_of_order"],
            }
        if failure is None:
            base = row["cases"].get("baseline", {}).get("out_of_order", {})
            mut = row["cases"].get("out_of_order", {}).get("out_of_order", {})
            if base.get("status") != "satisfied":
                failure = "OERR_REACHABILITY_FAIL"
            elif mut.get("status") != "violated":
                if mut.get("reason") == "no_rule_order_endpoints":
                    failure = "OERR_BPMN_ACTION_MAPPING_FAIL"
                else:
                    failure = "OERR_REACHABILITY_FAIL"
        row["failure_reason"] = failure
        bonus_requirement_rows.append(row)

    # Order scope for all requirements: frozen existing plus bonus main rows.
    eligibility = load_json(ORDER_ELIGIBILITY)["requirements"]
    order_scope = {str(rid): str(row.get("order_type") or "") for rid, row in eligibility.items()}
    for req_id in bonus["requirements"]:
        order_scope[req_id] = MAIN_ORDER_TYPE

    methods: dict[str, Any] = {}
    for method in ("sun", "ours"):
        methods[method] = evaluate_dev_method(method, all_cases, flat[method], order_scope)

    order_delta = {}
    for method in ("sun", "ours"):
        base_order = {
            "TP": 1, "FP": 0, "FN": 2, "TN": 1,
            "unknown_positive": 2, "unknown_negative": 4,
            "positive_support": 3, "negative_support": 5, "scored_cells": 8,
        }
        new_order = methods[method]["per_type"]["out_of_order"]
        order_delta[method] = {
            "delta_TP": int(new_order["TP"]) - base_order["TP"],
            "delta_FP": int(new_order["FP"]) - base_order["FP"],
            "delta_FN": int(new_order["FN"]) - base_order["FN"],
            "delta_TN": int(new_order["TN"]) - base_order["TN"],
            "delta_unknown_positive": int(new_order["unknown_positive"]) - base_order["unknown_positive"],
            "delta_unknown_negative": int(new_order["unknown_negative"]) - base_order["unknown_negative"],
            "new_support_cells": int(new_order["scored_cells"]) - base_order["scored_cells"],
        }

    payload = {
        "schema_version": "stage3_bonus_order_generalization@1.0.0",
        "status": "BONUS_DEV_ONLY_ORDER_GENERALIZATION_DIAGNOSTIC",
        "dev_only": True,
        "seen_during_method_development": True,
        "final_table3_eligible": False,
        "real_llm_api_calls": 0,
        "endpoint_policy": "DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_STAGE2_PREDICTION",
        "orders_adapter": "SharedRuleOrderAdapterV3",
        "order_adapter_changed": False,
        "selected_backend": ST_MPNET,
        "gamma": GAMMA,
        "theta": THETA,
        "tau": TAU,
        "requirements": bonus_requirement_rows,
        "main_metrics": {method: methods[method]["per_type"]["out_of_order"] for method in methods},
        "order_delta_vs_current_baseline": order_delta,
    }
    write_json(ORDER_OUT_JSON, payload)

    lines = ["# Stage 3 BONUS Development: Order Generalization v1", "",
             "- Status: `BONUS_DEV_ONLY_ORDER_GENERALIZATION_DIAGNOSTIC`",
             "- `DEV_ONLY = true`; `FINAL_TABLE3_ELIGIBLE = false`",
             "- `REAL_LLM_API_CALLS = 0`",
             "- Endpoint policy: dev-only synthetic endpoint stub, not a real Stage-2 prediction.",
             "- Adapter: `SharedRuleOrderAdapterV3` (unchanged).",
             "- Frozen backend and thresholds: MPNet / gamma `0.55` / theta `0.45` / tau `0.8`.", "",
             "| Requirement | Citation | Eligibility | Adapter status | U_r edge | Baseline order | Mutant order | Failure |",
             "|---|---|---|---|---|---|---|---|"]
    for row in bonus_requirement_rows:
        base = row["cases"].get("baseline", {}).get("out_of_order", {})
        mut = row["cases"].get("out_of_order", {}).get("out_of_order", {})
        lines.append(
            f"| {row['requirement_id']} | {row['citation']} | {row['eligibility_class']} | "
            f"{row['adapter_projection_status']} | {row['sun_ur']} | {base.get('status')} | {mut.get('status')} | "
            f"{row['failure_reason'] or ''} |"
        )
    lines.append("")
    lines.append("## Frozen-Scope Order Metrics (all main eligible requirements, including existing supplement)")
    lines.append("| Method | TP | FP | FN | TN | Positive support | Negative support | Precision | Recall | F1 | Coverage | Unknown rate |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for method in ("sun", "ours"):
        m = methods[method]["per_type"]["out_of_order"]
        lines.append(f"| {method.title()} | {m['TP']} | {m['FP']} | {m['FN']} | {m['TN']} | {m['positive_support']} | {m['negative_support']} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} | {m['coverage']:.4f} | {m['unknown_rate']:.4f} |")
    lines.append("")
    ORDER_OUT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")

    # Combined development report.
    report = {
        "schema_version": "stage3_bonus_development_report@1.0.0",
        "status": "BONUS_DEV_REPLAY_NOT_PAPER_FACING",
        "current_paper_baseline_preserved": True,
        "current_paper_table3_replaced": False,
        "final_unseen_benchmark_created": False,
        "real_llm_api_calls": 0,
        "all_existing_cases_seen": True,
        "final_test_eligible": False,
        "missing_denominator_changed": False,
        "actor_method_changed": False,
        "order_adapter_changed": False,
        "order_supplement_changed_benchmark": True,
        "baseline": BASELINE,
        "bonus_dev": {method: {
            "precision": methods[method]["overall"]["precision"],
            "recall": methods[method]["overall"]["recall"],
            "f1": methods[method]["overall"]["f1"],
            "missing_f1": methods[method]["per_type"]["missing_action"]["f1"],
            "actor_f1": methods[method]["per_type"]["incorrect_actor"]["f1"],
            "order_f1": methods[method]["per_type"]["out_of_order"]["f1"],
            "macro_f1": methods[method]["macro_f1"],
            "coverage": methods[method]["overall"]["coverage"],
            "unknown_rate": methods[method]["overall"]["unknown_rate"],
            "per_type": methods[method]["per_type"],
            "overall_counts": methods[method]["overall"],
        } for method in methods},
        "delta_vs_baseline": {method: {
            "delta_precision": methods[method]["overall"]["precision"] - BASELINE[method]["precision"],
            "delta_recall": methods[method]["overall"]["recall"] - BASELINE[method]["recall"],
            "delta_f1": methods[method]["overall"]["f1"] - BASELINE[method]["f1"],
            "delta_missing_f1": methods[method]["per_type"]["missing_action"]["f1"] - BASELINE[method]["missing_f1"],
            "delta_actor_f1": methods[method]["per_type"]["incorrect_actor"]["f1"] - BASELINE[method]["actor_f1"],
            "delta_order_f1": methods[method]["per_type"]["out_of_order"]["f1"] - BASELINE[method]["order_f1"],
            "delta_macro_f1": methods[method]["macro_f1"] - BASELINE[method]["macro_f1"],
        } for method in methods},
        "improvement_attribution": {
            "missing_scope_change": {"delta_TP": 0, "delta_FP": 0, "delta_FN": 0, "note": "No action-scope revision was implemented; frozen Missing denominator reused."},
            "actor": {"changed": False, "note": "Actor formula unchanged."},
            "order_supplement": order_delta,
        },
        "decisions": {
            "CURRENT_PAPER_BASELINE_PRESERVED": True,
            "MISSING_ROOT_CAUSE_RESOLVED": "MAPPING_DOMINANT_NO_ALLOWED_FIX",
            "ACTION_SCOPE_REVISION_IMPLEMENTED": False,
            "ORDER_GENERALIZATION_COMPLETE": True,
            "ORDER_ADAPTER_CHANGED": False,
            "BONUS_DEV_REPLAY_COMPLETE": True,
            "BONUS_RESULT_METHOD_VALID": False,
            "BONUS_RESULT_NUMERICALLY_IMPROVED": methods["ours"]["overall"]["f1"] > BASELINE["ours"]["f1"],
            "CANDIDATE_FOR_FUTURE_TABLE3_METHOD": False,
            "CURRENT_PAPER_TABLE3_REPLACED": False,
            "FINAL_UNSEEN_BENCHMARK_CREATED": False,
            "REAL_LLM_API_CALLS": 0,
        },
    }
    write_json(DEV_OUT_JSON, report)

    lines = ["# Stage 3 BONUS Development Report v1", "",
             "- Status: `BONUS_DEV_REPLAY_NOT_PAPER_FACING`",
             "- `CURRENT_PAPER_BASELINE_PRESERVED = true`; `CURRENT_PAPER_TABLE3_REPLACED = false`",
             "- `FINAL_UNSEEN_BENCHMARK_CREATED = false`; `REAL_LLM_API_CALLS = 0`",
             "- The order supplement is development-only and uses synthetic endpoint stubs; it is not a real Stage-2 result.", "",
             "## Main Table", "",
             "| Method | Precision | Recall | F1 |",
             "|---|---:|---:|---:|"]
    for method in ("sun", "ours"):
        r = report["bonus_dev"][method]
        lines.append(f"| {method.title()} | {r['precision']:.4f} | {r['recall']:.4f} | {r['f1']:.4f} |")
    lines += ["", "## Breakdown", "", "| Method | Missing F1 | Actor F1 | Order F1 | Macro-F1 | Coverage | Unknown rate |", "|---|---:|---:|---:|---:|---:|---:|"]
    for method in ("sun", "ours"):
        r = report["bonus_dev"][method]
        lines.append(f"| {method.title()} | {r['missing_f1']:.4f} | {r['actor_f1']:.4f} | {r['order_f1']:.4f} | {r['macro_f1']:.4f} | {r['coverage'] if r['coverage'] is not None else float('nan'):.4f} | {r['unknown_rate'] if r['unknown_rate'] is not None else float('nan'):.4f} |")
    lines += ["", "## Before vs After", "", "| Method | Baseline F1 | BONUS DEV F1 | Delta F1 |", "|---|---:|---:|---:|"]
    for method in ("sun", "ours"):
        d = report["delta_vs_baseline"][method]
        lines.append(f"| {method.title()} | {BASELINE[method]['f1']:.4f} | {report['bonus_dev'][method]['f1']:.4f} | {d['delta_f1']:+.4f} |")
    lines += ["", "## Attribution", "",
              "- Missing scope change: `ΔTP=0, ΔFP=0, ΔFN=0` (frozen denominator).",
              "- Actor: unchanged algorithm.",
              "- Order supplement added order cells only; see `stage3_bonus_order_generalization_v1.json` for ΔTP/FP/FN/TN and support.",
              "", "## Decision Fields", ""]
    for k, v in report["decisions"].items():
        lines.append(f"- `{k} = {str(v).lower() if isinstance(v, bool) else v}`")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("- The dominant remaining Missing-action problem is required-action mapping / BPMN-label semantic mismatch, not a clean removable denominator-scope contamination.")
    lines.append("- The action-scope gate was rejected; the frozen Definition 5 denominator is preserved.")
    lines.append("- The order supplement is a diagnostic only. It cannot replace the paper-facing Table 3 and does not prove a real Stage-2 order improvement.")
    lines.append("")
    DEV_OUT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("wrote", ORDER_OUT_JSON)
    print("wrote", DEV_OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
