# -*- coding: utf-8 -*-
"""Preflight, mock execution, and real-run entry point for LLM fallback.

The script never sends a real request unless ``--real`` is given together with
a valid scope-matching authorization file and process-environment API
credentials.  ``--preflight`` is fully offline and produces the exact
authorization request.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.s3_semantic_grounding_llm_v1 import (  # noqa: E402
    AUTHORIZATION_SCOPE,
    LLMGroundingExecutionError,
    MockSemanticGroundingTransport,
    build_authorization_request,
    build_request_set,
    execute_fallback,
    validate_authorization,
)
from bpc_hybrid.s3_semantic_grounding_v2 import (  # noqa: E402
    REVISION as V2_REVISION,
    apply_llm_grounding,
    build_clean_control_set,
    evaluate_target_paired,
    evaluate_unified_objects,
    fallback_transition_metrics,
    json_sha256,
    unified_objects_clean,
    unified_objects_legacy,
)
from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES, NONE_LABEL  # noqa: E402

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
V2_CONFIG = ROOT / "configs/stage3_semantic_grounding_v2.json"
V2_EVIDENCE = ROOT / "outputs/evidence/s3_semantic_grounding_v2"
V2_PREDICTIONS = V2_EVIDENCE / "predictions.jsonl"
V2_FALLBACK_PACK = V2_EVIDENCE / "llm_fallback_candidate_pack_v1.json"
V2_REPORT = ROOT / "outputs/reports/s3_semantic_grounding_v2.json"
OUT_ROOT = ROOT / "outputs/development/s3_semantic_grounding_v2"
REPORT_ROOT = ROOT / "outputs/reports"
EVIDENCE_ROOT = ROOT / "outputs/evidence/s3_semantic_grounding_v2"
PACK_NAME = "llm_fallback_candidate_pack_v1.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                            for row in rows), encoding="utf-8", newline="\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def find_matching_authorizations(scope: str) -> list[dict[str, Any]]:
    matches = []
    for root in (ROOT / "configs", ROOT / "outputs/reports", ROOT / "outputs/evidence"):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                data = read_json(path)
            except Exception:
                continue
            if isinstance(data, dict) and data.get("scope") == scope \
                    and data.get("status") == "authorized_unconsumed":
                matches.append({"path": path.relative_to(ROOT).as_posix(),
                                "status": data.get("status"),
                                "model": data.get("model")})
    return matches


def authorization_inventory() -> list[dict[str, Any]]:
    inventory = []
    for root in (ROOT / "configs", ROOT / "outputs/reports"):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                data = read_json(path)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            scope = data.get("scope") or data.get("authorization_scope")
            status = data.get("status") or data.get("authorization_status")
            model = data.get("model")
            if not scope and not status:
                continue
            inventory.append({
                "path": path.relative_to(ROOT).as_posix(),
                "scope": scope,
                "status": status,
                "model": model,
            })
    return inventory


def evaluate_arm_c(before_rows: list[dict[str, Any]], results: list[dict[str, Any]],
                   panel: Mapping[str, Any]) -> dict[str, Any]:
    after_rows = apply_llm_grounding(before_rows, results)
    expected_by_item = {
        item["variant_id"]: item["expected_violation"]
        for item in panel["variants"]
    }
    variant_before = [row for row in before_rows if row["side"] == "variant"]
    control_before = [row for row in before_rows if row["side"] == "control"]
    variant_after = [row for row in after_rows if row["side"] == "variant"]
    control_after = [row for row in after_rows if row["side"] == "control"]
    target_before = evaluate_target_paired(variant_before, control_before, expected_by_item)
    target_after = evaluate_target_paired(variant_after, control_after, expected_by_item)
    clean_status_after = build_clean_control_set(control_after)
    if clean_status_after.get("verified_compliant_item_ids"):
        clean_metrics = evaluate_unified_objects(
            unified_objects_clean(variant_after, control_after, clean_status_after))
    else:
        clean_metrics = None
    return {
        "target_paired_before": target_before,
        "target_paired_after": target_after,
        "legacy_unified_after": evaluate_unified_objects(
            unified_objects_legacy(variant_after, control_after)),
        "clean_unified_after": clean_metrics,
        "control_global_compliance_after": clean_status_after["counts"],
        "fallback_transitions": fallback_transition_metrics(
            before_rows, after_rows, expected_by_item),
    }


def write_arm_comparison(b_v2_report: Mapping[str, Any], arm_c: Mapping[str, Any] | None,
                         status: str, authorization_request: Mapping[str, Any] | None) -> dict[str, Any]:
    b_target = b_v2_report["target_paired"]
    comparison = {
        "schema_version": "s3_semantic_grounding_v2_arm_comparison@1.0.0",
        "revision": V2_REVISION,
        "scope": "development_only",
        "arms": {
            "A_c36_similarity_baseline": {
                "status": "VERIFIED_PROJECT_FACT",
                "source": "outputs/reports/s3_formula_repair_v2.json reference/winter",
                "note": "Legacy BPMN-only collision and all-controls-as-none protocol.",
            },
            "B_semantic_grounding_v2_deterministic": {
                "status": "FROZEN_DEVELOPMENT_RESULT",
                "target_paired_macro_f1": b_target["macro_f1_four_types"],
                "per_type_f1": {t: b_target["per_type"][t]["f1"] for t in EXTENDED_TYPES},
                "control_target_false_positive_rate": b_target["control_target_false_positive_rate"],
                "pair_success_rate": b_target["pair_success_rate"],
                "target_field_unknown_rate": b_target["target_field_unknown_rate"],
                "source": "outputs/reports/s3_semantic_grounding_v2.json",
            },
            "C_semantic_grounding_v2_plus_llm_fallback": {
                "status": status,
                "real_run": bool(arm_c is not None),
                "arm_c_metrics": arm_c,
                "authorization_request": authorization_request,
            },
        },
        "fallback_benefit_harm_policy": (
            "If C is real-run, report unknown->correct, unknown->wrong, "
            "ambiguous->correct, ambiguous->wrong and clean-unified deltas; never "
            "report only improvements."
        ),
    }
    write_json(REPORT_ROOT / "s3_semantic_grounding_v2_arm_comparison.json", comparison)
    lines = [
        "# s3_semantic_grounding_v2 arm comparison",
        "",
        f"- A: C36 similarity baseline (historical; old evaluation protocol)",
        f"- B: Semantic Grounding v2 deterministic — target-paired Macro-F1 "
        f"**{b_target['macro_f1_four_types']:.4f}**, control target FP "
        f"**{b_target['control_target_false_positive_rate']:.4f}**, pair success "
        f"**{b_target['pair_success_rate']:.4f}**",
        f"- C: Semantic Grounding v2 + LLM fallback — **{status}**",
        "",
    ]
    if arm_c:
        lines.append("## C real-run transition counts")
        lines.append("")
        lines.append(f"`{json.dumps(arm_c['fallback_transitions']['counts'], ensure_ascii=False)}`")
        lines.append("")
    else:
        lines.append("C was not real-run. See the authorization request for the exact "
                     "scope/model/call/budget request.")
    (REPORT_ROOT / "s3_semantic_grounding_v2_arm_comparison.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return comparison


def preflight(pack: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    request_set = build_request_set(pack, config)
    auth_request = build_authorization_request(request_set, pack, config)
    matching = find_matching_authorizations(AUTHORIZATION_SCOPE)
    inventory = authorization_inventory()
    non_matching = [item for item in inventory
                    if item.get("scope") != AUTHORIZATION_SCOPE]
    preflight_dir = OUT_ROOT / "llm_fallback_preflight"
    write_json(preflight_dir / "request_set.json", {
        key: value for key, value in request_set.items() if key != "requests"
    })
    write_jsonl(preflight_dir / "canonical_requests.jsonl", request_set["requests"])
    write_json(REPORT_ROOT / "s3_semantic_grounding_v2_llm_authorization_request.json",
               auth_request)
    write_json(EVIDENCE_ROOT / "llm_authorization_request_v1.json", auth_request)
    md_lines = [
        "# LLM fallback authorization request (S3-SEMANTIC-GROUNDING-V2-FALLBACK)",
        "",
        f"- Provider/model: `{auth_request['provider']}` / `{auth_request['model']}`",
        f"- Fallback items / calls: **{auth_request['fallback_item_count']} / {auth_request['calls']}**",
        f"- Retry: `{auth_request['retry']}`; off-peak only: `{auth_request['off_peak_only']}`",
        f"- Expected input tokens: `{auth_request['expected_input_tokens']}`; "
        f"input cap: `{auth_request['max_input_tokens_cap']}`",
        f"- Max output tokens per call: `{auth_request['max_output_tokens_per_call']}`; "
        f"total output cap: `{auth_request['total_output_token_cap']}`",
        f"- USD cap: `{auth_request['usd_cap']}`; RMB cap (at 7.2): `{auth_request['rmb_cap_at_7.2']}`",
        f"- Request set hash: `{auth_request['request_set_sha256']}`",
        f"- Candidate pack hash: `{auth_request['candidate_pack_sha256']}`",
        f"- Execution command: `{auth_request['execution_command']}`",
        "",
        "## Exact one-sentence authorization",
        "",
        auth_request["suggested_authorization_sentence"],
        "",
        f"Sentence SHA-256: `{auth_request['suggested_authorization_sentence_sha256']}`",
        "",
    ]
    (REPORT_ROOT / "s3_semantic_grounding_v2_llm_authorization_request.md").write_text(
        "\n".join(md_lines), encoding="utf-8", newline="\n")
    report = {
        "schema_version": "s3_semantic_grounding_llm_preflight@1.0.0",
        "status": "READY_FOR_AUTHORIZATION_DECISION"
        if not matching else "MATCHING_AUTHORIZATION_FILES_FOUND_NEEDS_MANUAL_REVIEW",
        "real_api_calls": 0,
        "network_calls": 0,
        "request_count": request_set["request_count"],
        "request_set_sha256": request_set["request_set_sha256"],
        "candidate_pack_sha256": auth_request["candidate_pack_sha256"],
        "expected_input_tokens": request_set["total_input_tokens_estimate"],
        "total_output_token_cap": request_set["total_output_token_cap"],
        "usd_cap_requested": auth_request["usd_cap"],
        "rmb_cap_requested": auth_request["rmb_cap_at_7.2"],
        "matching_authorization_files": matching,
        "authorization_inventory_count": len(inventory),
        "non_matching_authorization_count": len(non_matching),
        "non_matching_authorization_examples": non_matching[:8],
        "authorization_required_scope": AUTHORIZATION_SCOPE,
        "authorization_request_path": "outputs/reports/s3_semantic_grounding_v2_llm_authorization_request.json",
        "authorization_request_md_path": "outputs/reports/s3_semantic_grounding_v2_llm_authorization_request.md",
        "execution_command": auth_request["execution_command"],
        "suggested_authorization_sentence": auth_request["suggested_authorization_sentence"],
        "suggested_authorization_sentence_sha256": auth_request["suggested_authorization_sentence_sha256"],
        "old_task_authorizations_not_reused": True,
    }
    write_json(REPORT_ROOT / "s3_semantic_grounding_v2_llm_preflight.json", report)
    write_json(EVIDENCE_ROOT / "llm_preflight.json", report)
    write_json(EVIDENCE_ROOT / "llm_preflight_request_set.json",
               {key: value for key, value in request_set.items() if key != "requests"})
    write_jsonl(EVIDENCE_ROOT / "llm_preflight_canonical_requests.jsonl",
                request_set["requests"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--mock", action="store_true")
    group.add_argument("--real", action="store_true")
    parser.add_argument("--authorization", type=Path, default=None)
    args = parser.parse_args()
    config = read_json(V2_CONFIG)["llm_fallback"]
    pack = read_json(V2_FALLBACK_PACK)
    if args.preflight:
        report = preflight(pack, config)
        b_report = read_json(V2_REPORT)
        write_arm_comparison(b_report, None, "IMPLEMENTED_READY_FOR_AUTHORIZATION",
                             report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.mock:
        request_set = build_request_set(pack, config)
        summary = execute_fallback(pack=pack, request_set=request_set, config=config,
                                   output_root=OUT_ROOT, mode="mock")
        write_json(REPORT_ROOT / "s3_semantic_grounding_v2_llm_mock_execution.json", summary)
        write_json(EVIDENCE_ROOT / "llm_mock_execution_summary.json", {
            "schema_version": summary["schema_version"],
            "mode": "mock",
            "mock_only_not_experimental": True,
            "counts": summary["counts"],
            "request_set_sha256": request_set["request_set_sha256"],
            "candidate_pack_sha256": json_sha256(pack),
            "total_input_tokens_estimate": summary["total_input_tokens_estimate"],
            "ledger_path": summary["ledger_path"],
            "normalized_path": summary["normalized_path"],
            "raw_response_dir": summary["raw_response_dir"],
        })
        panel = read_json(PANEL)
        before_rows = read_jsonl(V2_PREDICTIONS)
        arm_c_mock = evaluate_arm_c(before_rows, summary["results"], panel)
        arm_c_mock["mock_only_not_experimental"] = True
        arm_c_mock["note"] = (
            "Mock transport only: this file proves evaluator/ablation wiring. "
            "It must not be cited as an experimental LLM result."
        )
        write_json(REPORT_ROOT / "s3_semantic_grounding_v2_arm_c_mock.json", arm_c_mock)
        b_report = read_json(V2_REPORT)
        write_arm_comparison(b_report, None, "IMPLEMENTED_READY_FOR_AUTHORIZATION",
                             read_json(REPORT_ROOT / "s3_semantic_grounding_v2_llm_authorization_request.json"))
        print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
        return 0
    if args.authorization is None:
        raise SystemExit("--real requires --authorization path")
    authorization = read_json(args.authorization)
    request_set = build_request_set(pack, config)
    validation = validate_authorization(authorization, pack, request_set, config)
    if not validation["valid"]:
        raise SystemExit("authorization invalid: " + ",".join(validation["errors"]))
    summary = execute_fallback(pack=pack, request_set=request_set, config=config,
                               output_root=OUT_ROOT, mode="real",
                               authorization=authorization)
    panel = read_json(PANEL)
    before_rows = read_jsonl(V2_PREDICTIONS)
    arm_c = evaluate_arm_c(before_rows, summary["results"], panel)
    write_json(REPORT_ROOT / "s3_semantic_grounding_v2_llm_real_execution.json", summary)
    write_json(REPORT_ROOT / "s3_semantic_grounding_v2_arm_c_real.json", arm_c)
    b_report = read_json(V2_REPORT)
    write_arm_comparison(b_report, arm_c, "REAL_RUN_COMPLETE",
                         read_json(REPORT_ROOT / "s3_semantic_grounding_v2_llm_authorization_request.json"))
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
