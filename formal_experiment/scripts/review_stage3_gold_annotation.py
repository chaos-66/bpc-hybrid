# -*- coding: utf-8 -*-
"""Interactive adjudication tool for the Stage 3 Gold annotation pack.

The blank pack (data/development/human_review/stage3_gold_annotation_blank_v1.json)
is immutable. The tool edits a human-correction copy
(data/development/human_review/stage3_gold_annotation_human_correction_v1.json)
that starts as a deep copy of the blank pack. Every adjudication is written
atomically with a timestamped backup; only the user's keystrokes may change
review_state / decision fields. Agents never infer decisions.

Each question shows the full context needed to decide:
- the BPMN process and its activities,
- the regulation text (rule_text) the item refers to,
- the pre-filled candidate judgement and its evidence,
so the user can see directly whether a rule-process pair is relevant and
whether a violation candidate holds.

Commands (same for both item kinds):
  matching   : y = relevant, n = not relevant
  violation  : missing_action | incorrect_actor | out_of_order | none (=compliant)
  navigation : s = skip (leave unreviewed), u = undo last decision, q = save & quit
At the end the tool prints the freeze summary; the pack is frozen only when
every item is adjudicated (then run verify/validate with the freeze flag).

Usage:
    python scripts/review_stage3_gold_annotation.py
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_formal_dataset import Stage1FormalDatasetError  # noqa: E402

BLANK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_blank_v1.json"
EDITABLE = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"
BACKUP_DIR = ROOT / "data" / "development" / "human_review" / "backups"

MATCHING_COMMANDS = {"y": True, "n": False}
VIOLATION_COMMANDS = {
    "missing_action": "missing_action",
    "incorrect_actor": "incorrect_actor",
    "out_of_order": "out_of_order",
    "none": None,
}
NAV_COMMANDS = {"s": "skip", "u": "undo", "q": "quit"}


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage1FormalDatasetError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1FormalDatasetError(f"{label} root must be an object")
    return value


def _backup(path: Path, backup_dir: Path) -> None:
    if not path.exists():
        return
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    target = backup_dir / f"stage3_gold_correction_backup_{stamp}.json"
    shutil.copy2(path, target)


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _item_list(pack: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    items = [(i["item_id"], i) for i in pack["matching_items"]]
    items += [(i["item_id"], i) for i in pack["violation_items"]]
    return items


def _process_activities(pack: dict[str, Any], process_id: str) -> list[str]:
    for p in pack["processes"]:
        if p["process_id"] == process_id:
            return p["activity_names"]
    return []


def _fmt(text: str, width: int = 110) -> str:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\n      ".join(lines)


def _render(kind: str, item_id: str, item: dict[str, Any], pack: dict[str, Any],
            idx: int, total: int) -> str:
    activities = _process_activities(pack, item["process_id"])
    lines = [
        f"[{idx}/{total}] {item_id}  |  process: {item['process_id']}  |  rule: {item['rule_id']} ({item.get('rule_ref', '')})",
        "  " + "-" * 100,
        "  PROCESS activities:",
    ]
    for i, act in enumerate(activities, 1):
        lines.append(f"    {i}. {act}")
    lines.append("  RULE text:")
    lines.append(f"      {_fmt(item['rule_text'])}")
    if kind == "matching":
        rel = "relevant" if item["candidate_relevant"] else "NOT relevant (negative pair)"
        ev = item.get("evidence_activity") or "no direct activity evidence"
        lines.append(f"  PRE-FILL: candidate {rel}  (evidence activity: {ev})")
        lines.append("  DECIDE : y = relevant, n = not relevant, s = skip, u = undo, q = save & quit")
    else:
        vt = item["candidate_violation_type"] or "none"
        loc = item.get("candidate_location") or "n/a"
        lines.append(f"  PRE-FILL: candidate violation {vt}  (location: {loc})")
        lines.append(f"    evidence: {_fmt(item['candidate_evidence'])}")
        lines.append("  DECIDE : missing_action | incorrect_actor | out_of_order | none | s | u | q")
    lines.append("  " + "-" * 100)
    return "\n".join(lines)


def _import_decisions(pack: dict[str, Any], editable: Path, backup_dir: Path,
                      spec: str) -> int:
    """Import explicitly supplied human decisions in the form
    ``m001:y,m002:n,v001:missing_action,v002:none,...``. The tool validates
    ids and values, writes the correction pack atomically with a backup, and
    prints the resulting freeze summary. Decisions are never inferred: the
    spec must come verbatim from the user."""
    items = dict(_item_list(pack))
    applied = 0
    errors: list[str] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if ":" not in token:
            errors.append(f"malformed token: {token}")
            continue
        item_id, raw = token.split(":", 1)
        item_id = item_id.strip()
        value = raw.strip().lower()
        item = items.get(item_id)
        if item is None:
            errors.append(f"unknown item id: {item_id}")
            continue
        if item_id.startswith("m"):
            if value not in MATCHING_COMMANDS:
                errors.append(f"{item_id}: invalid matching value {value!r} (use y/n)")
                continue
            item["decision_relevant"] = MATCHING_COMMANDS[value]
            item["review_state"] = "adjudicated"
            item.pop("decision_violation_type", None)
            item.pop("decision_evidence", None)
        else:
            if value not in VIOLATION_COMMANDS:
                errors.append(f"{item_id}: invalid violation value {value!r}")
                continue
            item["decision_violation_type"] = VIOLATION_COMMANDS[value]
            item["decision_evidence"] = item.get("candidate_evidence")
            item["review_state"] = "adjudicated"
            item.pop("decision_relevant", None)
        applied += 1
    if errors:
        print("import errors (nothing was written):")
        for e in errors:
            print(f"  - {e}")
        return 2
    _backup(editable, backup_dir)
    _write_atomic(editable, pack)
    print(f"imported {applied} user decisions")
    return _freeze_summary(pack, editable)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blank", type=Path, default=BLANK)
    parser.add_argument("--editable", type=Path, default=EDITABLE)
    parser.add_argument("--backup-dir", type=Path, default=BACKUP_DIR)
    parser.add_argument("--reviewed-all", action="store_true",
                        help="print the freeze summary without entering the interactive loop")
    parser.add_argument("--print-batch", nargs=2, type=int, metavar=("START", "COUNT"),
                        help="print items START..START+COUNT-1 (1-based) with full context, no interaction")
    parser.add_argument("--import-decisions", metavar="SPEC",
                        help="import user decisions 'm001:y,m002:n,v001:none,...' (batch mode, no interaction)")
    args = parser.parse_args()

    blank = _load_json(args.blank, "Stage 3 gold blank pack")
    if args.editable.exists():
        pack = _load_json(args.editable, "Stage 3 gold correction pack")
    else:
        pack = copy.deepcopy(blank)
        _backup(args.editable, args.backup_dir)
        _write_atomic(args.editable, pack)

    if args.import_decisions:
        return _import_decisions(pack, args.editable, args.backup_dir, args.import_decisions)

    if args.print_batch:
        start, count = args.print_batch
        items = _item_list(pack)
        total = len(items)
        for idx in range(start - 1, min(start - 1 + count, total)):
            item_id, item = items[idx]
            print(_render(
                "matching" if item_id.startswith("m") else "violation",
                item_id, item, pack, idx + 1, total,
            ))
            print()
        return 0

    if args.reviewed_all:
        return _freeze_summary(pack, args.editable)

    items = _item_list(pack)
    total = len(items)
    history: list[tuple[str, dict[str, Any]]] = []
    idx = 0
    while idx < total:
        item_id, item = items[idx]
        if item["review_state"] == "adjudicated":
            idx += 1
            continue
        print()
        print(_render(
            "matching" if item_id.startswith("m") else "violation",
            item_id, item, pack, idx + 1, total,
        ))
        try:
            answer = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n(save & quit)")
            answer = "q"
        if answer in NAV_COMMANDS:
            action = NAV_COMMANDS[answer]
            if action == "skip":
                idx += 1
                continue
            if action == "quit":
                break
            if action == "undo":
                if history:
                    prev_id, prev = history.pop()
                    item_id2, current = items[prev_id]
                    current["review_state"] = prev["review_state"]
                    current["decision_relevant"] = prev.get("decision_relevant")
                    current["decision_violation_type"] = prev.get("decision_violation_type")
                    current["decision_evidence"] = prev.get("decision_evidence")
                    _backup(args.editable, args.backup_dir)
                    _write_atomic(args.editable, pack)
                    print(f"  undone {prev_id}")
                else:
                    print("  nothing to undo")
                continue
        if item_id.startswith("m"):
            if answer not in MATCHING_COMMANDS:
                print("  invalid: use y / n / s / u / q")
                continue
            decision = MATCHING_COMMANDS[answer]
            history.append((idx, copy.deepcopy(item)))
            item["decision_relevant"] = decision
            item["review_state"] = "adjudicated"
        else:
            if answer not in VIOLATION_COMMANDS:
                print("  invalid: use missing_action / incorrect_actor / out_of_order / none / s / u / q")
                continue
            decision = VIOLATION_COMMANDS[answer]
            history.append((idx, copy.deepcopy(item)))
            item["decision_violation_type"] = decision
            item["decision_evidence"] = item.get("candidate_evidence")
            item["review_state"] = "adjudicated"
        _backup(args.editable, args.backup_dir)
        _write_atomic(args.editable, pack)
        idx += 1

    return _freeze_summary(pack, args.editable)


def _freeze_summary(pack: dict[str, Any], editable: Path) -> int:
    m_items = pack.get("matching_items", [])
    v_items = pack.get("violation_items", [])
    all_items = m_items + v_items
    adjudicated = sum(1 for i in all_items if i["review_state"] == "adjudicated")
    unreviewed = sum(1 for i in all_items if i["review_state"] == "unreviewed")
    freeze_ready = adjudicated == len(all_items) and len(all_items) > 0
    print()
    print("=" * 60)
    print(f"correction pack : {editable}")
    print(f"total items     : {len(all_items)}  (matching {len(m_items)} + violation {len(v_items)})")
    print(f"adjudicated     : {adjudicated}")
    print(f"unreviewed      : {unreviewed}")
    print(f"freeze_ready    : {freeze_ready}")
    if freeze_ready:
        print("All items adjudicated. Run the verifier with the freeze flag to lock the Gold.")
    print("=" * 60)
    return 0 if freeze_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
