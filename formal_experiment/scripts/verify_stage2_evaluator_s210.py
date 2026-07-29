"""Verify the frozen S2.10 evaluator on synthetic evidence only."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage2_evaluation import (  # noqa: E402
    Stage2EvaluationError,
    build_style_review_template,
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    sha256_file,
    sha256_json,
    validate_evaluation_report,
    validate_style_review_document,
)


CONTRACT = ROOT / "configs" / "stage2_evaluator_s210.json"
REPORT_SCHEMA = ROOT / "configs" / "schemas" / "stage2_evaluation_report.schema.json"
STYLE_SCHEMA = ROOT / "configs" / "schemas" / "style_equivalent_review.schema.json"
CANONICAL_SCHEMA = ROOT / "configs" / "schemas" / "stage2_prediction.schema.json"
IMPLEMENTATION = ROOT / "src" / "bpc_hybrid" / "stage2_evaluation.py"
RUNNER = ROOT / "scripts" / "evaluate_stage2_s210.py"
VERIFIER = Path(__file__).resolve()
FIXTURE = ROOT / "tests" / "fixtures" / "stage2_evaluator" / "s210_contract_fixture.json"
DEFAULT_MANIFEST = ROOT / "outputs" / "reports" / "s210_stage2_evaluator_contract_synthetic_v2.manifest.json"
EXPECTED_MEMBERSHIP_SHA256 = "f74be514b6ffed61cb196feb730ec6db29ca0c8e2ffd6a00cf248a6187e5af47"


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage2EvaluationError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Stage2EvaluationError(f"JSON root must be an object: {path}")
    return value


def _assert_close(actual: float, expected: float, label: str) -> None:
    if abs(actual - expected) > 1e-12:
        raise Stage2EvaluationError(f"{label} changed: {actual} != {expected}")


def verify() -> dict[str, Any]:
    contract = load_evaluator_contract(CONTRACT)
    fixture = _load_object(FIXTURE)
    if fixture.get("schema_version") != "s210_contract_fixture@1.0.0":
        raise Stage2EvaluationError("synthetic fixture version changed")
    if contract["canonical_schema"]["sha256"] != sha256_file(CANONICAL_SCHEMA):
        raise Stage2EvaluationError("canonical Stage 2 schema hash changed")
    for record in fixture["gold_records"]:
        source = record["source_text"].upper()
        if any(marker in source for marker in ("GDPR", "REGULATION (EU)", "ARTICLE 5")):
            raise Stage2EvaluationError("synthetic fixture contains formal legal text")
    actual_membership = membership_sha256(fixture["gold_records"])
    if actual_membership != EXPECTED_MEMBERSHIP_SHA256:
        raise Stage2EvaluationError("synthetic membership changed")

    report = evaluate_stage2(
        fixture["gold_records"],
        fixture["attempts"],
        contract=contract,
        dataset_id=fixture["dataset_id"],
        method_id=fixture["method_id"],
        expected_membership_sha256=EXPECTED_MEMBERSHIP_SHA256,
    )
    report_errors = validate_evaluation_report(report)
    if report_errors:
        raise Stage2EvaluationError("report validation failed: " + "; ".join(report_errors))
    reversed_report = evaluate_stage2(
        list(reversed(fixture["gold_records"])),
        list(reversed(fixture["attempts"])),
        contract=contract,
        dataset_id=fixture["dataset_id"],
        method_id=fixture["method_id"],
        expected_membership_sha256=EXPECTED_MEMBERSHIP_SHA256,
    )
    if report != reversed_report:
        raise Stage2EvaluationError("evaluator output depends on input array order")

    modality = report["primary_metrics"]["modality"]
    fields = report["primary_metrics"]["fields"]
    coverage = report["semantic_coverage"]
    structural = report["structural_encoding"]
    cost = report["cost_accounting"]
    _assert_close(modality["macro_f1"], 5 / 12, "modality macro-F1")
    if modality["per_class"]["prohibition"]["precision"] is not None:
        raise Stage2EvaluationError("missing-class modality precision must be null/N/A")
    _assert_close(fields["action"]["strict_exact"]["f1"], 0.25, "action strict F1")
    _assert_close(fields["action"]["safe_normalized"]["f1"], 0.5, "action safe F1")
    _assert_close(fields["action"]["normalized_f1_lift"], 0.25, "action safe lift")
    expected_coverage = {
        "gold_required_count": 14,
        "predicted_count": 9,
        "matched_presence_count": 7,
        "complete_record_rate": 0.4,
        "schema_valid_rate": 0.6,
        "unsupported_or_ambiguous_rate": 0.2,
        "invalid_record_rate": 0.2,
        "api_error_rate": 0.2,
        "recovered_api_error_rate": 0.2,
        "any_api_error_rate": 0.4,
        "invalid_or_api_error_rate": 0.4,
    }
    for key, expected in expected_coverage.items():
        if coverage[key] != expected:
            raise Stage2EvaluationError(f"coverage {key} changed")
    if structural["actor_action_edges"]["f1"] != 0.5:
        raise Stage2EvaluationError("actor-action edge F1 changed")
    if structural["order_relation_edges"]["fn"] != 1:
        raise Stage2EvaluationError("order-relation missing edge was not counted")
    if cost != {
        "request_count": 5,
        "llm_call_count": 3,
        "prompt_tokens": 190,
        "completion_tokens": 36,
        "total_tokens": 226,
        "estimated_cost_usd": 0.0036,
        "latency_ms_total": 5227.0,
        "latency_ms_mean_per_request": 1045.4,
    }:
        raise Stage2EvaluationError("cost accounting changed")

    bad_attempts = copy.deepcopy(fixture["attempts"][:-1])
    try:
        evaluate_stage2(
            fixture["gold_records"],
            bad_attempts,
            contract=contract,
            dataset_id=fixture["dataset_id"],
            method_id=fixture["method_id"],
            expected_membership_sha256=EXPECTED_MEMBERSHIP_SHA256,
        )
    except Stage2EvaluationError:
        membership_fail_closed = True
    else:
        membership_fail_closed = False
    if not membership_fail_closed:
        raise Stage2EvaluationError("missing attempt did not fail closed")
    try:
        evaluate_stage2(
            fixture["gold_records"],
            fixture["attempts"],
            contract=contract,
            dataset_id=fixture["dataset_id"],
            method_id=fixture["method_id"],
            expected_membership_sha256=EXPECTED_MEMBERSHIP_SHA256,
            claim_scope="formal",
            formal_ready=False,
        )
    except Stage2EvaluationError:
        formal_fail_closed = True
    else:
        formal_fail_closed = False
    if not formal_fail_closed:
        raise Stage2EvaluationError("formal scope bypassed final readiness")

    style = build_style_review_template(
        fixture["style_review_candidates"],
        dataset_id=fixture["dataset_id"],
        method_id=fixture["method_id"],
        sample_size=2,
        seed=contract["style_equivalent_review"]["seed"],
    )
    style_errors = validate_style_review_document(style, require_blank=True)
    if style_errors:
        raise Stage2EvaluationError("style template validation failed: " + "; ".join(style_errors))

    artifact_paths = {
        "contract": CONTRACT,
        "report_schema": REPORT_SCHEMA,
        "style_review_schema": STYLE_SCHEMA,
        "canonical_schema": CANONICAL_SCHEMA,
        "implementation": IMPLEMENTATION,
        "runner": RUNNER,
        "verifier": VERIFIER,
        "fixture": FIXTURE,
    }
    return {
        "schema_version": "s210_evaluator_verification_manifest@1.1.0",
        "task_id": "S2.10-E",
        "run_id": "s210_stage2_evaluator_contract_synthetic_v2",
        "status": "succeeded",
        "artifacts": {
            name: {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(path),
            }
            for name, path in artifact_paths.items()
        },
        "verification": {
            "membership_payload_sha256": actual_membership,
            "sample_count": report["membership"]["sample_count"],
            "report_schema_valid": True,
            "style_review_schema_valid": True,
            "style_review_selected": len(style["records"]),
            "style_review_human_decisions_filled": 0,
            "array_order_invariant": True,
            "missing_attempt_fail_closed": membership_fail_closed,
            "formal_scope_fail_closed": formal_fail_closed,
            "modality_macro_f1_synthetic": modality["macro_f1"],
            "action_strict_f1_synthetic": fields["action"]["strict_exact"]["f1"],
            "action_safe_f1_synthetic": fields["action"]["safe_normalized"]["f1"],
            "schema_valid_rate_synthetic": coverage["schema_valid_rate"],
            "api_error_rate_synthetic": coverage["api_error_rate"],
            "recovered_api_error_rate_synthetic": coverage["recovered_api_error_rate"],
            "any_api_error_rate_synthetic": coverage["any_api_error_rate"],
            "actor_action_edge_f1_synthetic": structural["actor_action_edges"]["f1"],
            "report_payload_sha256": sha256_json(report),
            "style_template_payload_sha256": sha256_json(style),
        },
        "safety": {
            "synthetic_fixture_only": True,
            "formal_gold_read_or_modified": False,
            "formal_predictions_read_or_created": False,
            "formal_performance_evaluation": False,
            "method_comparison": False,
            "llm_api_called": False,
            "network_called": False,
            "row_level_predictions_persisted": False,
        },
        "claim_boundary": (
            "This manifest verifies evaluator and recovered-fallback mechanics on five synthetic attempts. "
            "Its metric values are contract-test constants, not B0/H1/D1 performance."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    manifest = verify()
    if args.manifest_out.exists():
        raise Stage2EvaluationError(f"refusing to overwrite manifest: {args.manifest_out}")
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest["verification"], ensure_ascii=False, sort_keys=True))
    print(f"Wrote {args.manifest_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
