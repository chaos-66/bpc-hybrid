"""Verify the S2.10-E v1.2 evaluator on synthetic and adversarial cases."""

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

from bpc_hybrid.stage2_evaluation_v3 import (  # noqa: E402
    Stage2EvaluationError,
    clause_iou_pairs,
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    sha256_file,
    sha256_json,
    validate_evaluation_report,
)


CONTRACT = ROOT / "configs/stage2_evaluator_s210_v3.json"
REPORT_SCHEMA = ROOT / "configs/schemas/stage2_evaluation_report_v3.schema.json"
CANONICAL_SCHEMA = ROOT / "configs/schemas/stage2_prediction.schema.json"
IMPLEMENTATION = ROOT / "src/bpc_hybrid/stage2_evaluation_v3.py"
VERIFIER = ROOT / "scripts/verify_stage2_evaluator_s210_v3.py"
TEST = ROOT / "tests/test_s2_10_stage2_evaluation_v3.py"
FIXTURE = ROOT / "tests/fixtures/stage2_evaluator/s210_contract_fixture.json"
DEFAULT_MANIFEST = ROOT / "outputs/reports/s210_stage2_evaluator_contract_synthetic_v3.manifest.json"
EXPECTED_MEMBERSHIP_SHA256 = "f74be514b6ffed61cb196feb730ec6db29ca0c8e2ffd6a00cf248a6187e5af47"


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage2EvaluationError(f"JSON root must be an object: {path}")
    return value


def _schema_identity_errors(report: dict[str, Any]) -> list[str]:
    """Check the frozen schema identity without adding a runtime dependency."""
    schema = _load_object(REPORT_SCHEMA)
    errors: list[str] = []
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("report schema dialect changed")
    if properties.get("schema_version", {}).get("const") != report.get("schema_version"):
        errors.append("report schema version const disagrees")
    if set(required) != set(report):
        errors.append("report schema required root keys disagree")
    return errors


def _adversarial_local_id_report(
    fixture: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    gold = copy.deepcopy(fixture["gold_records"][0])
    attempt = copy.deepcopy(fixture["attempts"][0])
    gold_clause = gold["clauses"][0]
    pred_clause = attempt["record"]["clauses"][0]
    gold_clause["clause_id"] = "gold_clause"
    gold_clause["actors"][0]["id"] = "gold_actor"
    gold_clause["actions"][0]["id"] = "gold_action"
    gold_clause["actor_action_map"] = [
        {"actor_id": "gold_actor", "action_id": "gold_action"}
    ]
    pred_clause["clause_id"] = "method_clause"
    pred_clause["actors"][0]["id"] = "method_actor"
    pred_clause["actions"][0].update(
        {"id": "method_action", "text": "archive records", "end": 31}
    )
    pred_clause["actor_action_map"] = [
        {"actor_id": "method_actor", "action_id": "method_action"}
    ]
    pred_clause["clause_span"] = {
        "text": "The clerk shall archive records",
        "start": 0,
        "end": 31,
    }
    return evaluate_stage2(
        [gold],
        [attempt],
        contract=contract,
        dataset_id="s210_adversarial_method_local_ids",
        method_id=fixture["method_id"],
        expected_membership_sha256=membership_sha256([gold]),
    )


def verify() -> dict[str, Any]:
    contract = load_evaluator_contract(CONTRACT)
    fixture = _load_object(FIXTURE)
    if contract["canonical_schema"]["sha256"] != sha256_file(CANONICAL_SCHEMA):
        raise Stage2EvaluationError("canonical Stage 2 schema hash changed")
    if membership_sha256(fixture["gold_records"]) != EXPECTED_MEMBERSHIP_SHA256:
        raise Stage2EvaluationError("synthetic membership changed")
    for record in fixture["gold_records"]:
        source = record["source_text"].upper()
        if any(marker in source for marker in ("GDPR", "REGULATION (EU)", "ARTICLE 5")):
            raise Stage2EvaluationError("synthetic fixture contains formal legal text")

    report = evaluate_stage2(
        fixture["gold_records"],
        fixture["attempts"],
        contract=contract,
        dataset_id=fixture["dataset_id"],
        method_id=fixture["method_id"],
        expected_membership_sha256=EXPECTED_MEMBERSHIP_SHA256,
    )
    errors = validate_evaluation_report(report) + _schema_identity_errors(report)
    if errors:
        raise Stage2EvaluationError("v3 report validation failed: " + "; ".join(errors))
    reversed_fixture = copy.deepcopy(fixture)
    reversed_fixture["gold_records"].reverse()
    reversed_fixture["attempts"].reverse()
    for record in reversed_fixture["gold_records"]:
        record["clauses"].reverse()
    for attempt in reversed_fixture["attempts"]:
        if attempt.get("record"):
            attempt["record"]["clauses"].reverse()
    reversed_report = evaluate_stage2(
        reversed_fixture["gold_records"],
        reversed_fixture["attempts"],
        contract=contract,
        dataset_id=fixture["dataset_id"],
        method_id=fixture["method_id"],
        expected_membership_sha256=EXPECTED_MEMBERSHIP_SHA256,
    )
    if report != reversed_report:
        raise Stage2EvaluationError("v3 report depends on record or clause array order")

    adversarial = _adversarial_local_id_report(fixture, contract)
    adversarial_errors = validate_evaluation_report(adversarial) + _schema_identity_errors(adversarial)
    if adversarial_errors:
        raise Stage2EvaluationError(
            "adversarial report validation failed: " + "; ".join(adversarial_errors)
        )
    adversarial_segmentation = adversarial["structural_encoding"]["clause_segmentation"]
    if adversarial_segmentation["exact_match_count"] != 0:
        raise Stage2EvaluationError("adversarial exact segmentation must remain zero")
    if adversarial_segmentation["aligned_match_count"] != 1:
        raise Stage2EvaluationError("method-local-ID adversarial clause did not align")
    if adversarial["primary_metrics"]["fields"]["action"]["strict_exact"]["tp"] != 1:
        raise Stage2EvaluationError("method-local entity IDs incorrectly blocked exact span TP")

    gold_span = [{"id": "same", "text": "left", "start": 0, "end": 10}]
    disjoint = [{"id": "same", "text": "right", "start": 20, "end": 30}]
    shared_id_disjoint_rejected = clause_iou_pairs(gold_span, disjoint)[0] == []
    if not shared_id_disjoint_rejected:
        raise Stage2EvaluationError("shared method-local ID overrode disjoint spans")

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
        formal_scope_fail_closed = True
    else:
        formal_scope_fail_closed = False
    if not formal_scope_fail_closed:
        raise Stage2EvaluationError("formal scope bypassed final readiness")

    artifacts = {
        "contract": CONTRACT,
        "report_schema": REPORT_SCHEMA,
        "canonical_schema": CANONICAL_SCHEMA,
        "implementation": IMPLEMENTATION,
        "verifier": VERIFIER,
        "regression_tests": TEST,
        "fixture": FIXTURE,
    }
    segmentation = report["structural_encoding"]["clause_segmentation"]
    return {
        "schema_version": "s210_evaluator_verification_manifest@1.2.0",
        "task_id": "S2.10-E",
        "run_id": "s210_stage2_evaluator_contract_synthetic_v3",
        "status": "succeeded_candidate_for_future_development",
        "artifacts": {
            name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
            for name, path in artifacts.items()
        },
        "verification": {
            "membership_payload_sha256": EXPECTED_MEMBERSHIP_SHA256,
            "sample_count": report["membership"]["sample_count"],
            "manual_report_validation": True,
            "report_schema_identity_validation": True,
            "record_and_clause_array_order_invariant": True,
            "formal_scope_fail_closed": formal_scope_fail_closed,
            "shared_id_disjoint_span_rejected": shared_id_disjoint_rejected,
            "method_local_id_adversarial_aligned": True,
            "adversarial_exact_match_count": adversarial_segmentation["exact_match_count"],
            "adversarial_aligned_match_count": adversarial_segmentation["aligned_match_count"],
            "modality_macro_f1_synthetic": report["primary_metrics"]["modality"]["macro_f1"],
            "action_strict_f1_synthetic": report["primary_metrics"]["fields"]["action"]["strict_exact"]["f1"],
            "exact_clause_recall_synthetic": segmentation["exact_recall"],
            "aligned_clause_recall_synthetic": segmentation["alignment_recall"],
            "report_payload_sha256": sha256_json(report),
            "adversarial_report_payload_sha256": sha256_json(adversarial),
        },
        "safety": {
            "synthetic_fixture_only": True,
            "formal_gold_read_or_modified": False,
            "formal_predictions_read_or_created": False,
            "formal_performance_evaluation": False,
            "method_comparison": False,
            "paper_score_targeting_used": False,
            "threshold_search_used": False,
            "llm_api_called": False,
            "network_called": False,
            "row_level_predictions_persisted": False,
        },
        "claim_boundary": (
            "This exact gate verifies fixed method-independent alignment mechanics. "
            "Synthetic metric constants are not B0/H1/D1 performance and were not selected to match a paper score."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
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
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"S2.10-E v3 verification failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
