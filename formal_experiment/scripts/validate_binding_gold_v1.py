# -*- coding: utf-8 -*-
"""Validate the human Stage-3 rule-to-process binding gold surface.

This validator NEVER creates or infers Gold.  It only checks the format and
referential integrity of an annotation file that a human fills:

- every referenced BPMN file exists and matches its recorded sha256;
- action IDs exist in the item's rule-side action list;
- actor IDs exist in the item's rule-side actor list;
- target activity IDs exist in the control BPMN (and, when the mutation is not
  missing_action, in the variant BPMN too);
- expected lanes exist in the control BPMN;
- order relation fields have a valid pair format;
- review_state is one of unreviewed/reviewed/adjudicated.

The input must be explicitly selected with ``--binding-gold``. Completed
review batches and their archived templates are never selected automatically.
A ready run requires every item to have a non-null decision and review_state
in {reviewed, adjudicated}.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
)

STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
VALID_REVIEW_STATES = ("unreviewed", "reviewed", "adjudicated")
VALID_TYPES = ("missing_action", "incorrect_actor", "out_of_order")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("id")) for row in rows if row.get("id") is not None}


def _rule_action_ids(item: dict[str, Any]) -> set[str]:
    rule_side = item.get("immutable_context", {}).get("rule_side") or {}
    return _ids(rule_side.get("actions") or [])


def _rule_actor_ids(item: dict[str, Any]) -> set[str]:
    rule_side = item.get("immutable_context", {}).get("rule_side") or {}
    return _ids(rule_side.get("actors") or [])


def _lane_tokens(record: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for lane in record.get("lanes") or []:
        for key in ("id", "name"):
            value = lane.get(key)
            if value:
                tokens.add(str(value))
    return tokens


def _activity_ids(record: dict[str, Any]) -> set[str]:
    return {str(a.get("id")) for a in record.get("activities") or []
            if a.get("id") is not None}


def validate_binding_gold(
    doc: dict[str, Any],
    *,
    structural_contract: Path = STRUCTURAL_CONTRACT,
    require_ready: bool = False,
) -> dict[str, Any]:
    """Return a machine-readable validation report; never mutates Gold."""
    errors: list[str] = []
    warnings: list[str] = []
    items = doc.get("items")
    if not isinstance(items, list) or not items:
        errors.append("items must be a non-empty list")
        items = []

    contract = load_stage1_contract(structural_contract)
    parse_cache: dict[str, dict[str, Any]] = {}
    action_exists = {"present": 0, "null": 0, "missing": 0}
    actor_exists = {"present": 0, "null": 0, "missing": 0}
    activity_exists = {"present": 0, "missing": 0}
    lane_exists = {"present": 0, "null": 0, "missing": 0}
    review_states: Counter[str] = Counter()
    ready_items = 0

    def parse_bpmn(path: Path) -> dict[str, Any]:
        key = str(path)
        if key not in parse_cache:
            if not path.is_file():
                raise FileNotFoundError(path)
            parse_cache[key] = parse_bpmn_file(path, contract=contract)
        return parse_cache[key]

    for index, item in enumerate(items):
        label = item.get("pair_id") or f"item[{index}]"
        context = item.get("immutable_context") or {}
        target_type = str(context.get("target_violation_type") or "")
        if target_type not in VALID_TYPES:
            errors.append(f"{label}: invalid target_violation_type {target_type!r}")

        review_state = str(item.get("review_state") or "")
        review_states[review_state] += 1
        if review_state not in VALID_REVIEW_STATES:
            errors.append(
                f"{label}: invalid review_state {review_state!r}")

        actions = _rule_action_ids(item)
        actors = _rule_actor_ids(item)

        # action / actor references
        action_id = item.get("decision_action_id")
        if action_id is None:
            action_exists["null"] += 1
        elif str(action_id) in actions:
            action_exists["present"] += 1
        else:
            action_exists["missing"] += 1
            errors.append(f"{label}: decision_action_id {action_id!r} not in rule_side.actions")

        actor_id = item.get("decision_actor_id")
        if actor_id is None:
            actor_exists["null"] += 1
        elif str(actor_id) in actors:
            actor_exists["present"] += 1
        else:
            actor_exists["missing"] += 1
            errors.append(f"{label}: decision_actor_id {actor_id!r} not in rule_side.actors")

        # order relation format
        before = item.get("decision_order_before_action_id")
        after = item.get("decision_order_after_action_id")
        if (before is None) != (after is None):
            errors.append(
                f"{label}: order relation must have both before and after "
                f"or neither")
        if before is not None and str(before) not in actions:
            errors.append(f"{label}: order before {before!r} not in rule actions")
        if after is not None and str(after) not in actions:
            errors.append(f"{label}: order after {after!r} not in rule actions")
        if before is not None and after is not None and str(before) == str(after):
            errors.append(f"{label}: order relation endpoints are identical")
        if target_type == "out_of_order" and (before is None or after is None):
            warnings.append(
                f"{label}: out_of_order item has no rule-side order endpoints")
        if target_type != "out_of_order" and (before is not None or after is not None):
            warnings.append(
                f"{label}: non-out_of_order item carries rule-side order endpoints")

        # BPMN references
        roles = context.get("roles") or {}
        target_activity = context.get("target_activity_id")
        expected_lane = item.get("decision_expected_lane")
        control_role = roles.get("control") or {}
        variant_role = roles.get("variant") or {}
        for role_name, role in (("control", control_role), ("variant", variant_role)):
            rel = role.get("bpmn_path")
            if not rel:
                errors.append(f"{label}: {role_name} bpmn_path missing")
                continue
            path = ROOT / rel
            if not path.is_file():
                errors.append(f"{label}: {role_name} BPMN missing: {rel}")
                continue
            actual_sha = _sha256(path)
            expected_sha = role.get("bpmn_sha256")
            if expected_sha and actual_sha != expected_sha:
                errors.append(
                    f"{label}: {role_name} BPMN sha256 mismatch "
                    f"({actual_sha[:12]} != {str(expected_sha)[:12]})")
            try:
                record = parse_bpmn(path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{label}: cannot parse {role_name} BPMN: {exc}")
                continue

            if role_name == "control":
                if target_activity and target_activity in _activity_ids(record):
                    activity_exists["present"] += 1
                elif target_activity:
                    activity_exists["missing"] += 1
                    errors.append(
                        f"{label}: target_activity_id {target_activity!r} "
                        f"not in control BPMN")
                else:
                    errors.append(f"{label}: target_activity_id missing")
                if expected_lane is None:
                    lane_exists["null"] += 1
                elif str(expected_lane) in _lane_tokens(record):
                    lane_exists["present"] += 1
                else:
                    lane_exists["missing"] += 1
                    errors.append(
                        f"{label}: expected lane {expected_lane!r} not in "
                        f"control BPMN")
            else:
                if target_activity and target_activity not in _activity_ids(record):
                    if target_type != "missing_action":
                        warnings.append(
                            f"{label}: target activity absent from variant for "
                            f"non-missing_action type")

        if review_state in ("reviewed", "adjudicated"):
            filled = all(item.get(k) is not None for k in (
                "decision_action_id", "decision_actor_id",
                "decision_expected_lane"))
            if target_type == "out_of_order":
                filled = filled and before is not None and after is not None
            if filled:
                ready_items += 1

    ready = bool(items) and ready_items == len(items) and not errors
    if require_ready and not ready:
        errors.append(
            f"binding gold is not ready: {ready_items}/{len(items)} items "
            f"filled/reviewed; errors={len(errors)}")

    return {
        "schema_version": "stage3_binding_gold_validator@1.0.0",
        "input_path": str(doc.get("_input_path", "")) if False else None,
        "surface_id": doc.get("surface_id"),
        "schema_version_input": doc.get("schema_version"),
        "status": ("ready" if ready else
                   "blank_awaiting_human_annotation" if not any(
                       item.get("review_state") not in (None, "unreviewed")
                       for item in items) else "invalid_or_incomplete"),
        "items": len(items),
        "items_ready": ready_items,
        "review_state_counts": dict(review_states),
        "action_reference_counts": action_exists,
        "actor_reference_counts": actor_exists,
        "activity_reference_counts": activity_exists,
        "lane_reference_counts": lane_exists,
        "errors": errors,
        "warnings": warnings,
        "ready": ready,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding-gold", type=Path, required=True,
                        help="Explicit input path; completed batches are never auto-selected.")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    doc = _load(args.binding_gold)
    report = validate_binding_gold(doc, require_ready=args.require_ready)
    report["input_path"] = str(args.binding_gold.relative_to(ROOT)).replace(
        "\\", "/")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if (report["ready"] or not args.require_ready) else 1


if __name__ == "__main__":
    raise SystemExit(main())
