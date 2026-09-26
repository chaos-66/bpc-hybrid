# -*- coding: utf-8 -*-
"""Build frozen Stage 3-v2 development assets.

This is an asset-construction script, not a calibration or evaluation script.
It reads the frozen source-only order eligibility manifest and the frozen
reference case metadata, filters the latter to ``split == development`` for the
development manifest, and writes no test case into any development asset.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data/development/stage3_table3_r5_benchmark_v2"
REFERENCE_CASES = BENCHMARK / "reference/reference_cases.json"
INFERENCE_VIEW = BENCHMARK / "inference/inference_view.json"
SPLIT_MANIFEST = BENCHMARK / "split_manifest.json"
ORDER_ELIGIBILITY = ROOT / "outputs/reports/stage3_table3_r5_order_eligibility_v2.json"
OUT_DATA = ROOT / "data/development/stage3_v2"
OUT_CONFIG = ROOT / "configs/stage3_v2_development_v1.json"
OUT_ORDER_SCOPE = ROOT / "outputs/reports/stage3_v2_order_scope_manifest_v1.json"
CORE_DEV_REQUIREMENTS = [
    "R5-D-01", "R5-D-02", "R5-D-03", "R5-D-04", "R5-D-05", "R5-D-06", "R5-D-07",
    "R5-D-08", "R5-D-09", "R5-D-10", "R5-D-11", "R5-D-12",
    "R5-S1-T1", "R5-S1-T2", "R5-S1-T3", "R5-S1-T4",
    "R5-S5-T1", "R5-S5-T2", "R5-S5-T3", "R5-S5-T4", "R5-S6-T3", "R5-S6-T4",
]
GAMMA_GRID = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
THETA_GRID = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
MAIN_ORDER_TYPE = "TYPE_A_explicit_action_precedence"
EXTENDED_ORDER_TYPE = "TYPE_B_trigger_precedence"
UNSUPPORTED_ORDER_TYPE = "TYPE_C_deadline_arithmetic_only"


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def main() -> None:
    reference = load_json(REFERENCE_CASES)
    inference = load_json(INFERENCE_VIEW)
    split_manifest = load_json(SPLIT_MANIFEST)
    order_manifest = load_json(ORDER_ELIGIBILITY)
    bpmn_by_case = {str(item["case_id"]): item["bpmn_path"] for item in inference["items"]}

    if set(split_manifest["development_requirement_ids"]) != set(CORE_DEV_REQUIREMENTS):
        raise RuntimeError("development requirement IDs changed; refusing asset build")
    dev_cases = []
    for case in reference["cases"]:
        if str(case.get("split")) != "development":
            continue
        case_id = str(case["case_id"])
        dev_cases.append({
            "case_id": case_id,
            "requirement_id": str(case["requirement_id"]),
            "source_family_id": str(case.get("source_family_id")),
            "split": "development",
            "variant": str(case.get("variant")),
            "scored_types": list(case.get("scored_types") or []),
            "ineligible_types": list(case.get("ineligible_types") or []),
            "reference_states": dict(case.get("reference_states") or {}),
            "order_pair": list(case.get("order_pair") or []),
            "target_node": case.get("target_node"),
            "bpmn_path": bpmn_by_case[case_id],
        })
    dev_cases.sort(key=lambda item: item["case_id"])
    if any(case["split"] != "development" for case in dev_cases):
        raise RuntimeError("development asset contains non-development case")
    if len(dev_cases) != 76:
        raise RuntimeError(f"expected 76 development cases, got {len(dev_cases)}")

    dev_manifest = {
        "schema_version": "stage3_v2_development_reference@1.0.0",
        "status": "DEVELOPMENT_ONLY_TEST_QUARANTINED",
        "source_reference_cases_path": str(REFERENCE_CASES.relative_to(ROOT)).replace("\\", "/"),
        "source_reference_cases_sha256": sha_file(REFERENCE_CASES),
        "source_split_manifest_sha256": sha_file(SPLIT_MANIFEST),
        "development_requirement_ids": CORE_DEV_REQUIREMENTS,
        "case_count": len(dev_cases),
        "test_cases_written": 0,
        "test_quarantine_statement": (
            "Only split == development cases are present in this file. Legacy test cases and "
            "legacy test metrics remain quarantined until backend and order projection are frozen."
        ),
        "cases": dev_cases,
    }
    dev_path = OUT_DATA / "reference_dev_v1.json"
    write_json(dev_path, dev_manifest)

    order_rows = {str(row["requirement_id"]): dict(row) for row in order_manifest["rows"]}
    requirements_scope = {}
    for requirement_id in sorted(set(order_rows) | set(CORE_DEV_REQUIREMENTS)):
        row = order_rows.get(requirement_id)
        if row is None:
            requirements_scope[requirement_id] = {
                "order_type": None,
                "main_metric_eligible": False,
                "split": "development" if requirement_id in CORE_DEV_REQUIREMENTS else None,
                "reason": "not_an_order_requirement",
            }
        else:
            order_type = str(row["order_type"])
            requirements_scope[requirement_id] = {
                "order_type": order_type,
                "main_metric_eligible": order_type == MAIN_ORDER_TYPE,
                "extended_diagnostic": order_type == EXTENDED_ORDER_TYPE,
                "unsupported_not_scored": order_type == UNSUPPORTED_ORDER_TYPE,
                "split": str(row.get("split")),
                "citation": row.get("citation"),
                "order_evidence": row.get("order_evidence"),
                "source_family_id": row.get("source_family_id"),
            }
    order_scope = {
        "schema_version": "stage3_v2_order_scope_manifest@1.0.0",
        "status": "ORDER_SCOPE_FROZEN_SOURCE_ONLY",
        "source_manifest_path": str(ORDER_ELIGIBILITY.relative_to(ROOT)).replace("\\", "/"),
        "source_manifest_sha256": sha_file(ORDER_ELIGIBILITY),
        "main_metric_type": MAIN_ORDER_TYPE,
        "extended_diagnostic_type": EXTENDED_ORDER_TYPE,
        "unsupported_not_scored_type": UNSUPPORTED_ORDER_TYPE,
        "scope_rule": (
            "Main Table 3-v2 out_of_order is TYPE_A_explicit_action_precedence only. "
            "TYPE_B is preserved as an extended diagnostic and TYPE_C is unsupported/not-scored."
        ),
        "requirements": requirements_scope,
        "order_requirement_ids": sorted(order_rows),
        "development_type_a_cases": sorted(
            str(case["case_id"]) for case in dev_cases
            if requirements_scope.get(str(case["requirement_id"]), {}).get("order_type") == MAIN_ORDER_TYPE
        ),
    }
    order_scope_path = OUT_ORDER_SCOPE
    write_json(order_scope_path, order_scope)

    config = {
        "schema_version": "stage3_v2_development_config@1.0.0",
        "experiment_id": "stage3_v2_shared_semantic_and_type_a_order",
        "status": "PREREGISTERED_BEFORE_DEV_METRICS",
        "winter_mainline_status": "ARCHIVED_EXTERNAL_BASELINE",
        "scope": {
            "methods": ["sun", "ours"],
            "shared_stage3": True,
            "same_bpmn": True,
            "same_stage1": True,
            "same_matcher": True,
            "same_thresholds": True,
            "same_order_projection": True,
            "same_gold": True,
            "same_evaluator": True,
            "only_difference": "Stage2 regulatory representation",
        },
        "semantic_backend": {
            "preferred_candidate": "sentence-transformers/all-mpnet-base-v2",
            "lightweight_candidate": "sentence-transformers/all-MiniLM-L6-v2",
            "local_candidate_short_names": ["spacy_en_core_web_md", "spacy_en_core_web_sm"],
            "max_backends": 2,
            "allow_download_without_approval": False,
            "download_policy": "MODEL_DOWNLOAD_REQUIRED if preferred local candidate absent",
            "normalization": {
                "unicode": "NFKC",
                "strip": True,
                "whitespace_collapse": True,
                "casefold": True,
                "role_leading_article_normalization": "retained from approved shared role surface",
            },
            "forbidden": [
                "actor_synonyms",
                "action_synonyms",
                "gdpr_specific_dictionary",
                "gold_specific_rewrites",
                "verb_equivalence_table",
                "business_object_lookup_table",
            ],
            "similarity": "cosine_or_identified_spacy_text_similarity",
            "cache_key_policy": "backend_identity_sha256 + normalized_text_a + normalized_text_b",
            "batch_order_independent": True,
        },
        "thresholds": {
            "tau": 0.8,
            "gamma_grid": GAMMA_GRID,
            "theta_grid": THETA_GRID,
            "grid_frozen_before_metrics": True,
            "tau_note": "Definition 4 matching_score is diagnostic only in no-gate protocol.",
        },
        "calibration": {
            "development_only": True,
            "test_access_forbidden": True,
            "legacy_test_quarantine": True,
            "objective": "mean_of_sun_and_ours_development_macro_f1",
            "objective_definition": "mean(Sun dev macro-F1, Ours dev macro-F1)",
            "macro_definition": "mean of missing_action, incorrect_actor, TYPE_A out_of_order F1 with standard zero_division=0",
            "tie_breakers": [
                "higher_combined_dev_objective",
                "higher_min_method_macro_f1",
                "lower_mean_unknown_rate",
                "higher_mean_overall_precision",
                "larger_gamma_plus_theta",
            ],
            "method_neutral": True,
            "one_sweep_per_backend": True,
            "forbidden_objectives": ["ours_minus_sun", "maximize_ours_alone"],
        },
        "order_scope": {
            "manifest_path": str(order_scope_path.relative_to(ROOT)).replace("\\", "/"),
            "main_metric": MAIN_ORDER_TYPE,
            "extended_diagnostics": [EXTENDED_ORDER_TYPE],
            "unsupported_not_scored": [UNSUPPORTED_ORDER_TYPE],
            "type_classification_source": "source_semantics_and_frozen_order_eligibility",
            "prediction_used_for_type_assignment": False,
            "native_relation_precedence": True,
            "endpoint_must_bind_existing_stage2_action": True,
            "nominal_endpoint_forbidden": True,
        },
        "integrity": {
            "gold_modified": False,
            "benchmark_modified": False,
            "ours_stage2_prediction_modified": False,
            "sun_stage2_prediction_modified": False,
            "historical_v1_overwrite_allowed": False,
            "real_api_calls": 0,
            "network_calls": 0,
        },
    }
    write_json(OUT_CONFIG, config)
    print(json.dumps({
        "development_manifest": str(dev_path.relative_to(ROOT)).replace("\\", "/"),
        "order_scope": str(order_scope_path.relative_to(ROOT)).replace("\\", "/"),
        "config": str(OUT_CONFIG.relative_to(ROOT)).replace("\\", "/"),
        "development_cases": len(dev_cases),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
