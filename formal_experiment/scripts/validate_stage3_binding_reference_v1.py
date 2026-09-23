# -*- coding: utf-8 -*-
"""Strict validator for the Stage-3 binding reference.

It validates provenance and referential integrity; it never fills or creates a
binding.  ``--require-ready`` passes only when every benchmark pair has a
human-approved, eligible binding (currently impossible for the ineligible
process-only out_of_order pairs, which is intentional).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file  # noqa: E402

REFERENCE = ROOT / "data/development/stage3_synth/stage3_binding_reference_v1.json"
BENCHMARK = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_v1.json"
ELIGIBILITY = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_eligibility_v1.json"
GOLD_RULES = ROOT / "data/gold/stage3/gdpr7_gold_rule_records_v1.json"
CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rule_action_ids(gold: dict[str, Any], rule_id: str) -> set[str]:
    out: set[str] = set()
    for record in gold.get("records") or []:
        if str(record.get("rule_id")) != str(rule_id):
            continue
        for clause in record.get("clauses") or []:
            for action in clause.get("actions") or []:
                if action.get("id"):
                    out.add(str(action["id"]))
    return out


def _rule_actor_ids(gold: dict[str, Any], rule_id: str) -> set[str]:
    out: set[str] = set()
    for record in gold.get("records") or []:
        if str(record.get("rule_id")) != str(rule_id):
            continue
        for clause in record.get("clauses") or []:
            for actor in clause.get("actors") or []:
                if actor.get("id"):
                    out.add(str(actor["id"]))
    return out


def validate(reference_path: Path = REFERENCE,
             require_ready: bool = False) -> dict[str, Any]:
    reference = _load(reference_path)
    benchmark = _load(BENCHMARK)
    eligibility = {
        (str(r["pair_id"]), str(r["violation_type"])): bool(r["eligible"])
        for r in _load(ELIGIBILITY)["records"]
    }
    gold = _load(GOLD_RULES)
    contract = load_stage1_contract(CONTRACT)
    cache: dict[str, dict[str, Any]] = {}

    def parsed(rel_path: str) -> dict[str, Any]:
        if rel_path not in cache:
            cache[rel_path] = parse_bpmn_file(ROOT / rel_path, contract=contract)
        return cache[rel_path]

    errors: list[str] = []
    warnings: list[str] = []
    ready_pairs = 0
    for record in reference.get("records") or []:
        pair_id = str(record.get("pair_id") or "")
        label = pair_id or "<missing-pair>"
        target_type = str(record.get("target_violation_type") or "")
        rule_id = str(record.get("rule_id") or "")
        action = record.get("action_binding") or {}
        actor = record.get("actor_binding") or {}
        order = record.get("order_binding") or {}
        control = record.get("control") or {}
        control_path = str(control.get("bpmn_path") or "")
        if not control_path:
            errors.append(f"{label}: missing control.bpmn_path")
            continue
        actual_sha = _sha256(ROOT / control_path)
        if control.get("bpmn_sha256") and actual_sha != control.get("bpmn_sha256"):
            errors.append(f"{label}: control BPMN sha256 mismatch")
        process = parsed(control_path)
        activity_ids = {str(a.get("id")) for a in process.get("activities") or []}
        lane_ids = {str(l.get("id")) for l in process.get("lanes") or []}
        lane_names = {str(l.get("name")) for l in process.get("lanes") or []
                      if l.get("name")}
        pool_names = {str(p.get("name")) for p in process.get("pools") or []
                      if p.get("name")}

        if target_type not in ("missing_action", "incorrect_actor", "out_of_order"):
            errors.append(f"{label}: invalid target_violation_type {target_type!r}")
        if record.get("target_activity_id") not in activity_ids:
            errors.append(f"{label}: target_activity_id absent from control BPMN")
        if action.get("rule_action_id") and str(action["rule_action_id"]) not in _rule_action_ids(gold, rule_id):
            errors.append(f"{label}: action_binding.rule_action_id not in rule {rule_id}")
        if actor.get("rule_actor_id") and str(actor["rule_actor_id"]) not in _rule_actor_ids(gold, rule_id):
            errors.append(f"{label}: actor_binding.rule_actor_id not in rule {rule_id}")
        if actor.get("expected_lane_id") and str(actor["expected_lane_id"]) not in (
                lane_ids | lane_names | pool_names):
            errors.append(f"{label}: expected_lane_id absent from control BPMN")
        before = order.get("before_rule_action_id")
        after = order.get("after_rule_action_id")
        if (before is None) != (after is None):
            errors.append(f"{label}: order endpoints must both be null or both set")
        if before and str(before) not in _rule_action_ids(gold, rule_id):
            errors.append(f"{label}: order before id not in rule {rule_id}")
        if after and str(after) not in _rule_action_ids(gold, rule_id):
            errors.append(f"{label}: order after id not in rule {rule_id}")
        if before and after and str(before) == str(after):
            errors.append(f"{label}: order endpoints are identical")

        eligible = eligibility.get((pair_id, target_type), False)
        if eligible and record.get("review_state") == "human_approved":
            ready_pairs += 1
        if not eligible:
            warnings.append(f"{label}: ineligible for formal {target_type} evaluation")

    all_human_eligible = (
        ready_pairs == len(reference.get("records") or [])
        and bool(reference.get("records"))
    )
    if require_ready and not all_human_eligible:
        errors.append(
            "reference is not ready for a full formal run: "
            f"{ready_pairs}/{len(reference.get('records') or [])} pairs eligible "
            f"and human-approved")

    ready = all_human_eligible and not errors
    return {
        "schema_version": "stage3_binding_reference_validator@1.0.0",
        "input_path": str(reference_path.relative_to(ROOT)).replace("\\", "/"),
        "status": "ready" if ready else "provisional_or_incomplete",
        "items": len(reference.get("records") or []),
        "ready_pairs": ready_pairs,
        "errors": errors,
        "warnings": warnings,
        "ready": ready,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    report = validate(args.reference, args.require_ready)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                            sort_keys=True) + "\n",
                                 encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if (report["ready"] or not args.require_ready) else 1


if __name__ == "__main__":
    raise SystemExit(main())
