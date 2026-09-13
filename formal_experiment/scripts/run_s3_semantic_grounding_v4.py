# -*- coding: utf-8 -*-
"""Offline evidence runner for the v4 field-wise grounding application chain.

This script does not call a real LLM.  It rebuilds the v4 candidate pack from
the frozen v3 predictions, checks that all advertised evidence ids remain
visible after truncation, and writes constructed end-to-end cases that prove
(and keep counterexamples for) the following chain:

    input pack -> semantic match -> anonymous-id reverse mapping
    -> program-side node/evidence binding -> local check re-execution
    -> program decision.

The constructed cases are implementation evidence only; they must never be
reported as real LLM performance.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for candidate in (SRC,):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.s3_semantic_grounding_llm_v1 import (  # noqa: E402
    validate_semantic_grounding_response,
)
from bpc_hybrid.s3_semantic_grounding_v4 import (  # noqa: E402
    NONE_LABEL,
    apply_llm_grounding,
    build_fallback_pack,
    strip_grounding_context,
)
from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES  # noqa: E402

V3_EVIDENCE = ROOT / "outputs/evidence/s3_semantic_grounding_v3"
V3_PREDICTIONS = V3_EVIDENCE / "predictions.jsonl"
V3_ARTIFACT_HASHES = V3_EVIDENCE / "artifact_hashes.json"
V4_EVIDENCE = ROOT / "outputs/evidence/s3_semantic_grounding_v4"
V4_DEVELOPMENT = ROOT / "outputs/development/s3_semantic_grounding_v4"
REPORT_JSON = ROOT / "outputs/reports/s3_semantic_grounding_v4.json"
REPORT_MD = ROOT / "outputs/reports/s3_semantic_grounding_v4.md"
PACK_NAME = "llm_fallback_candidate_pack_v4.json"
DEMO_NAME = "offline_grounding_demo.json"
REVISION = "s3_semantic_grounding_v4"
TYPES = list(EXTENDED_TYPES)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def clean_checks() -> dict[str, Any]:
    return {
        target: {"status": "not_applicable", "observable": True,
                  "violation": False, "reason": "empty_rule_field"}
        for target in TYPES
    }


def unknown_condition_checks() -> dict[str, Any]:
    checks = clean_checks()
    checks["required_condition_not_enforced"] = {
        "status": "unknown", "observable": False, "violation": None,
        "reason": "action_grounding_unresolved",
    }
    return checks


def make_record(*, condition: str = "consent obtained",
                include_flow: bool = True) -> dict[str, Any]:
    return {
        "process_id": "p",
        "pools": [{"process_ref": "p", "name": "Controller"}],
        "lanes": [],
        "activities": [
            {"id": "A1", "name": "review request"},
            {"id": "A2", "name": "notify subject"},
        ],
        "events": [], "gateways": [],
        "sequence_flows": (
            [{"id": "F1", "name": None, "source_ref": "A1", "target_ref": "A2",
              "condition_expression": condition}] if include_flow else []
        ),
        "control_flow": {},
    }


def make_xml(*, include_flow: bool = True) -> Any:
    parts = ['<process id="p">']
    if include_flow:
        parts.append('<sequenceFlow id="F1" sourceRef="A1" targetRef="A2" />')
    parts.append("</process>")
    return ET.fromstring("".join(parts))


def make_row(*, action: str = "notify subject", modality: str = "obligation",
             condition: str = "consent obtained", constraint: str | None = None,
             action_status: str = "unresolved",
             checks: Mapping[str, Any] | None = None,
             record: Mapping[str, Any] | None = None,
             condition_evidence: Sequence[Mapping[str, Any]] | None = None,
             evidence_ids: Sequence[str] | None = None) -> dict[str, Any]:
    record = record or make_record(condition=condition)
    sentence = {
        "rule_id": "r1", "sentence_idx": 0, "modality": modality,
        "actor": "the controller", "action": action, "condition": condition,
        "constraint": constraint, "exception": None,
    }
    local_context = {
        "candidate_activities": [
            {"activity_id": "A2", "label": "notify subject", "owners": [],
             "similarity": 0.9, "lexical_coverage": 0.9},
        ],
        "nodes": [{"id": "A2", "kind": "activity", "label": "notify subject"}],
        "sequence_flows": [],
        "condition_evidence": list(condition_evidence or [
            {"id": "F1", "text": condition, "kind": "condition_expression"},
        ]),
        "constraint_bound_evidence": [],
        "constraint_unbound_evidence": [],
        "exception_handler_candidates": [],
        "evidence_ids": list(evidence_ids or ["F1"]),
    }
    return {
        "item_id": "demo-item", "side": "variant", "process_id": "p",
        "rule_id": "r1", "expected_label": "required_condition_not_enforced",
        "predicted_violation_type": None,
        "decision": {"predicted": None, "decision": "abstention",
                     "reason": "semantic_grounding_ambiguous"},
        "checks": dict(checks or unknown_condition_checks()),
        "action_grounding": {
            "schema": "s3_semantic_grounding_action@1.0.0",
            "status": action_status, "reason": "demo_stub",
            "activity_id": None, "candidate_activity_ids": ["A2"],
            "candidates": [{"activity_id": "A2", "label": "notify subject",
                             "owners": [], "similarity": 0.9,
                             "lexical_coverage": 0.9}],
            "alternatives": [],
        },
        "model_visible_rule_input": sentence,
        "canonical_rule_input_hash": "rule", "canonical_process_input_hash": "process",
        "bpmn_sha256": "bpmn", "compact_local_context": local_context,
        "control_global_compliance": None,
        "fallback_triggers": [],
        "_grounding_context": {
            "sentence": sentence, "record": record, "xml_root": make_xml(),
        },
    }


def pack_and_ids(row: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    pack = build_fallback_pack([row])
    if pack["item_count"] != 1:
        raise RuntimeError("demo pack did not contain exactly one item")
    item = pack["items"][0]
    return pack, item, dict(item["anonymized_id_map"])


def apply_response(row: Mapping[str, Any], pack: Mapping[str, Any],
                   response: Mapping[str, Any]) -> dict[str, Any]:
    return apply_llm_grounding(
        [row],
        [{"source_index": 0, "fallback_item_id": pack["items"][0]["fallback_item_id"],
          "status": "validated", "response": response}],
        pack=pack,
        contexts={(0, "variant"): row["_grounding_context"]},
    )[0]


def snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "action_grounding_status": (row.get("action_grounding") or {}).get("status"),
        "action_real_activity_id": (row.get("action_grounding") or {}).get("activity_id"),
        "checks": {
            target: {
                "status": (row.get("checks", {}).get(target) or {}).get("status"),
                "observable": (row.get("checks", {}).get(target) or {}).get("observable"),
                "violation": (row.get("checks", {}).get(target) or {}).get("violation"),
                "source": (row.get("checks", {}).get(target) or {}).get("source"),
            }
            for target in TYPES
        },
        "decision": copy.deepcopy(row.get("decision")),
        "predicted_violation_type": row.get("predicted_violation_type"),
    }


def case_action_and_condition_progress() -> dict[str, Any]:
    checks = unknown_condition_checks()
    checks["constraint_violated"] = {
        "status": "unknown", "observable": False, "violation": None,
        "reason": "unsupported_abstract_constraint_kind",
    }
    row = make_row(checks=checks, constraint="without undue delay")
    pack, item, ids = pack_and_ids(row)
    response = {
        "action_grounding": {"status": "matched", "activity_id": ids["A2"],
                             "confidence": 0.9},
        "condition": {"status": "enforced", "evidence_ids": [ids["F1"]],
                      "confidence": 0.9},
        "constraint": {"status": "ambiguous", "evidence_ids": [], "confidence": 0.0},
        "exception": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
    }
    validation = validate_semantic_grounding_response(
        json.dumps(response), {"input_payload": item["llm_visible_payload"]})
    after = apply_response(row, pack, response)
    assert validation["status"] == "valid"
    assert after["action_grounding"]["activity_id"] == "A2"
    assert after["checks"]["required_condition_not_enforced"]["violation"] is False
    assert after["checks"]["constraint_violated"]["status"] == "unknown"
    assert after["predicted_violation_type"] is None
    return {
        "case_id": "action_and_condition_progress_ambiguous_constraint_abstains",
        "expectation": "one ambiguous field does not block the resolved field",
        "validation": validation,
        "before": snapshot(row),
        "model_response": response,
        "after": snapshot(after),
        "passed": True,
    }


def case_prohibition_recheck() -> dict[str, Any]:
    checks = unknown_condition_checks()
    checks["prohibited_action_present"] = {
        "status": "unresolved", "observable": False, "violation": None,
        "reason": "action_grounding_unresolved",
    }
    row = make_row(modality="prohibition", checks=checks)
    pack, item, ids = pack_and_ids(row)
    response = {
        "action_grounding": {"status": "matched", "activity_id": ids["A2"],
                             "confidence": 0.9},
        "condition": {"status": "ambiguous", "evidence_ids": [], "confidence": 0.0},
        "constraint": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
        "exception": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
    }
    after = apply_response(row, pack, response)
    assert after["checks"]["prohibited_action_present"]["violation"] is True
    assert after["predicted_violation_type"] == "prohibited_action_present"
    return {
        "case_id": "action_id_reversed_and_prohibited_check_updated",
        "expectation": "action resolution updates the consuming prohibited_action_present check",
        "before": snapshot(row),
        "model_response": response,
        "after": snapshot(after),
        "passed": True,
    }


def case_negative_claim_without_closed_scope() -> dict[str, Any]:
    row = make_row(record=make_record(include_flow=False),
                   checks=unknown_condition_checks())
    pack, item, ids = pack_and_ids(row)
    response = {
        "action_grounding": {"status": "matched", "activity_id": ids["A2"],
                             "confidence": 0.9},
        "condition": {"status": "not_enforced", "evidence_ids": [], "confidence": 0.95},
        "constraint": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
        "exception": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
    }
    after = apply_response(row, pack, response)
    assert after["checks"]["required_condition_not_enforced"]["violation"] is not True
    assert after["predicted_violation_type"] is None
    return {
        "case_id": "negative_claim_requires_closed_program_scope",
        "expectation": "an absence claim without complete program scope keeps abstention",
        "before": snapshot(row),
        "model_response": response,
        "after": snapshot(after),
        "passed": True,
    }


def case_hallucinated_evidence() -> dict[str, Any]:
    row = make_row(record=make_record(condition="different condition"),
                   checks=unknown_condition_checks())
    pack, item, ids = pack_and_ids(row)
    response = {
        "action_grounding": {"status": "matched", "activity_id": ids["A2"],
                             "confidence": 0.9},
        "condition": {"status": "enforced", "evidence_ids": ["HALLUCINATED"],
                      "confidence": 0.99},
        "constraint": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
        "exception": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
    }
    after = apply_response(row, pack, response)
    failures = after["llm_application"]["evidence_binding_failures"]
    assert after["checks"]["required_condition_not_enforced"]["violation"] is not True
    assert any(item["kind"].startswith("evidence_id") for item in failures)
    return {
        "case_id": "irrelevant_or_hallucinated_evidence_rejected",
        "expectation": "high confidence is not enough without bound evidence",
        "before": snapshot(row),
        "model_response": response,
        "after": snapshot(after),
        "evidence_binding_failures": failures,
        "passed": True,
    }


def case_context_truncation_reachability() -> dict[str, Any]:
    condition_evidence = [
        {"id": f"E{i:02d}", "text": f"evidence {i}", "kind": "condition_expression"}
        for i in range(25)
    ]
    row = make_row(checks=unknown_condition_checks(),
                   condition_evidence=condition_evidence,
                   evidence_ids=[entry["id"] for entry in condition_evidence])
    pack, item, ids = pack_and_ids(row)
    local = item["llm_visible_payload"]["local_context"]
    visible_ids = {entry["id"] for entry in local["condition_evidence"]}
    advertised = set(local["evidence_ids"])
    assert item["evidence_ids_visible_in_payload"] is True
    assert advertised <= visible_ids
    assert "E24" not in advertised
    return {
        "case_id": "truncated_context_never_advertises_cut_off_evidence",
        "expectation": "allowed evidence ids are derived after truncation",
        "visible_condition_evidence_count": len(local["condition_evidence"]),
        "advertised_evidence_ids": sorted(advertised),
        "passed": True,
    }


def run_demo() -> dict[str, Any]:
    cases = [
        case_action_and_condition_progress(),
        case_prohibition_recheck(),
        case_negative_claim_without_closed_scope(),
        case_hallucinated_evidence(),
        case_context_truncation_reachability(),
    ]
    return {
        "schema_version": "s3_semantic_grounding_offline_chain_demo@1.0.0",
        "revision": REVISION,
        "status": "OFFLINE_IMPLEMENTATION_EVIDENCE_NOT_LLM_PERFORMANCE",
        "claim_boundary": (
            "Constructed cases test the implementation chain only.  They are "
            "not a real LLM run and contain no real-model performance metric."),
        "real_api_calls": 0,
        "network_calls": 0,
        "case_count": len(cases),
        "passed_count": sum(1 for case in cases if case.get("passed")),
        "cases": cases,
    }


def render_markdown(metrics: Mapping[str, Any]) -> str:
    pack = metrics["candidate_pack"]
    demo = metrics["offline_demo"]
    lines = [
        "# s3_semantic_grounding_v4 (offline implementation evidence)",
        "",
        "本 revision 修复 LLM 结果的逐字段应用、匿名活动 ID 反向映射、动作解决后的局部检查重跑、",
        "以及证据与目标动作范围的程序化绑定。全部为零 API 的离线构造验证。",
        "",
        "## Candidate pack (v4)",
        "",
        f"- Fallback items: **{pack['item_count']}**",
        f"- All advertised evidence ids visible in payload: "
        f"**{pack['all_evidence_ids_visible_in_payload']}**",
        f"- Semantic rule fields preserved: "
        f"**{pack['semantic_fields_preserved_for_all_items']}**",
        "",
        "## Offline chain cases",
        "",
        f"- Cases passed: **{demo['passed_count']}/{demo['case_count']}**",
        "- Status: **OFFLINE_IMPLEMENTATION_EVIDENCE_NOT_LLM_PERFORMANCE**",
        "",
        "| Case | Expectation |",
        "|---|---|",
    ]
    for case in demo["cases"]:
        lines.append(f"| {case['case_id']} | {case['expectation']} |")
    lines += [
        "",
        "## Boundary",
        "",
        "Constructed cases prove input -> semantic response -> anonymous-id reverse mapping -> "
        "program node/evidence binding -> local check re-execution -> decision wiring.  They do "
        "not establish real LLM accuracy or improvement.",
        "",
    ]
    return "\n".join(lines)


def run(*, overwrite: bool = False) -> dict[str, Any]:
    if any(path.exists() for path in (V4_EVIDENCE, V4_DEVELOPMENT, REPORT_JSON, REPORT_MD)):
        if not overwrite:
            raise RuntimeError("refusing to overwrite existing v4 outputs")
    hashes = read_json(V3_ARTIFACT_HASHES)
    key = "outputs/evidence/s3_semantic_grounding_v3/predictions.jsonl"
    expected = (hashes.get("artifacts") or {}).get(key)
    actual = sha256_file(V3_PREDICTIONS)
    if not expected or expected != actual:
        raise RuntimeError("v3 predictions artifact hash mismatch; refusing to reuse")
    rows = read_rows(V3_PREDICTIONS)
    pack = build_fallback_pack(rows)
    demo = run_demo()
    metrics = {
        "schema_version": "s3_semantic_grounding_v4_metrics@1.0.0",
        "revision": REVISION,
        "scope": "development_only",
        "status": "OFFLINE_IMPLEMENTATION_EVIDENCE_NOT_LLM_PERFORMANCE",
        "real_api_calls": 0,
        "network_calls": 0,
        "reused_v3_predictions": {
            "path": key,
            "sha256": actual,
            "match": True,
        },
        "candidate_pack": {
            "schema_version": pack["schema_version"],
            "item_count": pack["item_count"],
            "side_counts": pack["side_counts"],
            "trigger_counts": pack["trigger_counts"],
            "all_evidence_ids_visible_in_payload": pack[
                "all_evidence_ids_visible_in_payload"],
            "semantic_fields_preserved_for_all_items": pack[
                "semantic_fields_preserved_for_all_items"],
        },
        "offline_demo": demo,
    }
    manifest = {
        "schema_version": "s3_semantic_grounding_v4_manifest@1.0.0",
        "revision": REVISION,
        "scope": "development_only",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            key: actual,
        },
        "implementation_hashes": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in (
                Path(__file__),
                ROOT / "src/bpc_hybrid/s3_semantic_grounding_v4.py",
                ROOT / "src/bpc_hybrid/s3_semantic_grounding_llm_v1.py",
                ROOT / "src/bpc_hybrid/s3_semantic_grounding_v2.py",
                ROOT / "configs/stage3_semantic_grounding_v4.json",
                ROOT / "tests/test_s3_semantic_grounding_v4.py",
                ROOT / "outputs/evidence/s3_semantic_grounding_v3/predictions.jsonl",
            ) if path.is_file()
        },
        "safety": {
            "human_gold_read": False,
            "human_gold_modified": False,
            "real_api_calls": 0,
            "network_calls": 0,
            "constructed_cases_not_llm_performance": True,
        },
    }
    V4_EVIDENCE.mkdir(parents=True, exist_ok=True)
    V4_DEVELOPMENT.mkdir(parents=True, exist_ok=True)
    write_json(V4_EVIDENCE / PACK_NAME, pack)
    write_json(V4_EVIDENCE / DEMO_NAME, demo)
    write_json(V4_EVIDENCE / "manifest.json", manifest)
    write_json(V4_DEVELOPMENT / PACK_NAME, pack)
    write_json(V4_DEVELOPMENT / DEMO_NAME, demo)
    write_json(V4_DEVELOPMENT / "manifest.json", manifest)
    write_json(REPORT_JSON, {
        "schema_version": "s3_semantic_grounding_v4_report@1.0.0",
        "revision": REVISION,
        "status": "OFFLINE_IMPLEMENTATION_EVIDENCE_NOT_LLM_PERFORMANCE",
        "metrics": metrics,
        "manifest": manifest,
    })
    REPORT_MD.write_text(render_markdown(metrics), encoding="utf-8", newline="\n")
    artifacts = [
        V4_EVIDENCE / PACK_NAME, V4_EVIDENCE / DEMO_NAME,
        V4_EVIDENCE / "manifest.json", V4_DEVELOPMENT / PACK_NAME,
        V4_DEVELOPMENT / DEMO_NAME, V4_DEVELOPMENT / "manifest.json",
        REPORT_JSON, REPORT_MD,
    ]
    write_json(V4_EVIDENCE / "artifact_hashes.json", {
        "schema_version": "s3_semantic_grounding_v4_artifact_hashes@1.0.0",
        "revision": REVISION,
        "artifacts": {path.relative_to(ROOT).as_posix(): sha256_file(path)
                      for path in artifacts},
    })
    return {"metrics": metrics, "manifest": manifest, "demo": demo}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = run(overwrite=args.overwrite)
    print(json.dumps({
        "revision": REVISION,
        "candidate_pack_items": result["metrics"]["candidate_pack"]["item_count"],
        "offline_demo_cases": result["metrics"]["offline_demo"]["case_count"],
        "offline_demo_passed": result["metrics"]["offline_demo"]["passed_count"],
        "real_api_calls": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
