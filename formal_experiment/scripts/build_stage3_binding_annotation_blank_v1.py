# -*- coding: utf-8 -*-
"""Build the BLANK annotation surface for the Stage 3 rule-to-process binding.

Zero API.  Writes a template with pre-filled immutable context and EMPTY
decision fields for a human to complete.

Why this exists
---------------
`docs/research/STAGE3_OURS_ARM_FEASIBILITY_2026-09-21.md` establishes that the
remaining Table 3 work is a human annotation, not detector code: a real "Ours"
detector needs to know WHICH rule action each target BPMN activity discharges,
and that binding is currently annotated nowhere.

This builder does NOT invent any of that.  It emits, per paired item:

- the immutable context (variant id, process, rule, the rule's action spans and
  actor spans, the target activity id AND its human-readable name, the
  mutation type, the structural observation), and
- EMPTY decision fields (``decision_action_id``, ``decision_actor_id``,
  ``decision_note``, ``review_state``).

Filling it in is the user's call; the agent must never infer these values,
which would amount to authoring its own Ground Truth.

Outputs (new files only):

- ``data/development/stage3_synth/stage3_binding_annotation_blank_v1.json``
- ``outputs/reports/stage3_binding_annotation_blank_v1.{json,md}``

Usage:
    python scripts/build_stage3_binding_annotation_blank_v1.py
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

BENCHMARK = (ROOT / "data/development/stage3_synth"
             / "stage3_paired_benchmark_v1.json")
GOLD_RULES = ROOT / "data/gold/stage3/gdpr7_gold_rule_records_v1.json"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
OUT = (ROOT / "data/development/stage3_synth"
       / "stage3_binding_annotation_blank_v1.json")
TYPES = ("missing_action", "incorrect_actor", "out_of_order")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rule_side(rule_id: str) -> dict[str, Any]:
    """Rule-side action/actor spans for `rule_id`, read from the Gold Rules.

    Read-only context only; no decision is derived from it.
    """
    gold = _load(GOLD_RULES)
    actions: list[dict[str, Any]] = []
    actors: list[dict[str, Any]] = []
    order_relations: list[Any] = []
    clauses = 0
    for record in gold["records"]:
        if record.get("rule_id") != rule_id:
            continue
        for clause in record.get("clauses") or []:
            clauses += 1
            for span in clause.get("actions") or []:
                actions.append({"id": span.get("id"), "text": span.get("text"),
                                "clause_id": clause.get("clause_id"),
                                "clause_modality": (clause.get("modality")
                                                    or {}).get("label")})
            for span in clause.get("actors") or []:
                actors.append({"id": span.get("id"), "text": span.get("text"),
                               "clause_id": clause.get("clause_id")})
            order_relations.extend(clause.get("order_relations") or [])
    # de-duplicate by id, keep first occurrence
    def dedup(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set()
        out = []
        for row in rows:
            if row.get("id") in seen:
                continue
            seen.add(row.get("id"))
            out.append(row)
        return out
    return {
        "clauses": clauses,
        "actions": dedup(actions),
        "actors": dedup(actors),
        "order_relations_in_gold": order_relations,
    }


def build() -> dict[str, Any]:
    benchmark = _load(BENCHMARK)
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)

    activity_names: dict[str, str] = {}
    parse_cache: dict[str, Any] = {}

    def name_of(path: Path, activity_id: str | None) -> str | None:
        key = str(path)
        if key not in parse_cache:
            parse_cache[key] = parse_bpmn_file(path, contract=contract)
        for activity in parse_cache[key].get("activities") or []:
            if activity.get("id") == activity_id:
                return activity.get("name")
        return None

    rule_cache: dict[str, dict[str, Any]] = {}

    # One binding per PAIR: a control and its variant describe the same rule
    # action and the same target activity, so annotating per item would double
    # the human work for no information gain.
    pairs: dict[str, dict[str, Any]] = {}
    for item in benchmark["items"]:
        rule_id = item["rule_id"]
        if rule_id not in rule_cache:
            rule_cache[rule_id] = _rule_side(rule_id)
        grounding = item["grounding"]
        control_path = (ROOT / "data/input/stage1_stage3/gdpr7"
                        / f"{item['process_id']}.bpmn")
        target_activity = grounding.get("target_activity_id")
        entry = pairs.setdefault(item["pair_id"], {
            "pair_id": item["pair_id"],
            "immutable_context": {
                "process_id": item["process_id"],
                "rule_id": rule_id,
                "target_violation_type": item["target_violation_type"],
                "target_activity_id": target_activity,
                "target_activity_name": name_of(ROOT / item["bpmn_path"],
                                                target_activity),
                "control_activity_name": name_of(control_path,
                                                 target_activity),
                "order_pair": grounding.get("order_pair"),
                "rule_side": rule_cache[rule_id],
            },
            # ---- to be filled by a human; agents must NOT infer these ----
            "decision_action_id": None,
            "decision_actor_id": None,
            "decision_expected_lane": None,
            "decision_order_before_action_id": None,
            "decision_order_after_action_id": None,
            "decision_note": None,
            "review_state": "unreviewed",
        })
        entry["immutable_context"].setdefault("roles", {})[item["role"]] = {
            "item_id": item["item_id"],
            "bpmn_path": item["bpmn_path"],
            "bpmn_sha256": item["bpmn_sha256"],
            "gold_violation_type": item["gold_violation_type"],
            "structural_observation": item["structural_observation"],
        }

    items = [pairs[k] for k in sorted(pairs)]
    per_rule = Counter(i["immutable_context"]["rule_id"] for i in items)
    return {
        "schema_version": "stage3_binding_annotation_blank@1.0.0",
        "surface_id": "stage3_binding_annotation_blank_v1",
        "status": "blank_awaiting_human_annotation",
        "benchmark_id": benchmark["benchmark_id"],
        "benchmark_sha256": _sha256(BENCHMARK),
        "purpose": (
            "provide the rule-action -> BPMN-activity binding that the Ours "
            "detector requires as INPUT and that is currently annotated "
            "nowhere; agents must never infer these values"),
        "decision_fields": {
            "decision_action_id": ("the rule action span id (from "
                                   "immutable_context.rule_side.actions) that "
                                   "the target BPMN activity discharges"),
            "decision_actor_id": ("the rule actor span id that legitimately "
                                  "performs it"),
            "decision_expected_lane": ("the lane name in the CONTROL BPMN that "
                                       "legitimately owns the target activity"),
            "decision_order_before_action_id": ("for out_of_order only: the "
                                                "rule action that must precede"),
            "decision_order_after_action_id": ("for out_of_order only: the "
                                               "rule action that must follow"),
            "decision_note": "free-text rationale",
            "review_state": "unreviewed | reviewed | adjudicated",
        },
        "known_limits_recorded": {
            "order_relations_in_gold": (
                "the published Gold Rule Records carry ZERO order relations "
                "across 92 clauses, so the out_of_order decision fields cannot "
                "be anchored to existing Gold and would require new annotation "
                "of the rules themselves"),
            "actor_action_map_coverage": (
                "38 of 92 Gold clauses carry an actor_action_map link, so for "
                "most clauses the actor side must also be annotated rather "
                "than copied"),
        },
        "counts": {
            "items": len(items),
            "by_role": dict(Counter(r for i in items for r in (i["immutable_context"].get("roles") or {}))),
            "by_rule": dict(per_rule),
            "decisions_filled": 0,
        },
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "gold_modified": False,
            "benchmark_modified": False,
            "decisions_inferred_by_agent": False,
        },
        "items": items,
    }


def render(doc: dict[str, Any]) -> str:
    lines: list[str] = []
    counts = doc["counts"]
    lines.append("# Stage 3 rule-to-process binding: blank annotation surface")
    lines.append("")
    lines.append(f"Surface id: `{doc['surface_id']}` - status "
                 f"`{doc['status']}`.")
    lines.append("")
    lines.append(doc["purpose"] + ".")
    lines.append("")
    lines.append("## Why this is needed")
    lines.append("")
    lines.append("The 30-item mutation panel says WHICH BPMN activity was "
                 "mutated (`target_activity_id`) but never which rule action "
                 "that activity discharges, and both are multi-word spans, so "
                 "the correspondence is not recoverable by construction. A "
                 "grounded three-type detector needs it as input; deriving it "
                 "by similarity is the step measured to fail.")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- Pairs to annotate: **{counts['items']}** "
                 f"(each pair covers one control + one variant BPMN: "
                 f"{counts['by_role']})")
    lines.append(f"- By rule: {counts['by_rule']}")
    lines.append(f"- Decisions filled: **{counts['decisions_filled']}** "
                 f"(this is a blank template)")
    lines.append("")
    lines.append("## Fields to complete")
    lines.append("")
    lines.append("| Field | Meaning |")
    lines.append("|---|---|")
    for name, desc in doc["decision_fields"].items():
        lines.append(f"| `{name}` | {desc} |")
    lines.append("")
    lines.append("## Recorded limits (do not work around these silently)")
    lines.append("")
    for key, value in doc["known_limits_recorded"].items():
        lines.append(f"- **{key}**: {value}")
    lines.append("")
    lines.append("## Work estimate")
    lines.append("")
    lines.append(f"- {counts['items']} items, each needing an action binding "
                 "(and, for the 20 out_of_order items, an order pair).")
    lines.append("- `missing_action` and `incorrect_actor` are 10/10 "
                 "structurally detectable, so binding the action is sufficient "
                 "to score those two types.")
    lines.append("- `out_of_order` additionally needs order relations that do "
                 "not exist in the Gold yet, so it is the expensive third of "
                 "the work.")
    lines.append("")
    lines.append("## Provenance")
    lines.append("")
    lines.append(f"- Benchmark: `{doc['benchmark_id']}` "
                 f"(sha256 `{doc['benchmark_sha256']}`)")
    lines.append(f"- New LLM calls: {doc['safety']['llm_api_calls']}")
    lines.append(f"- Decisions inferred by agent: "
                 f"{doc['safety']['decisions_inferred_by_agent']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(ROOT / "outputs" / "reports"))
    args = parser.parse_args()

    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        raise SystemExit(
            f"refusing to overwrite the existing annotation surface: {OUT}")
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2,
                              sort_keys=True) + "\n", encoding="utf-8")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stage3_binding_annotation_blank_v1.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    text = render(doc)
    (out_dir / "stage3_binding_annotation_blank_v1.md").write_text(
        text, encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"wrote {out_dir / 'stage3_binding_annotation_blank_v1.json'}")
    print(f"wrote {out_dir / 'stage3_binding_annotation_blank_v1.md'}")
    print()
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
