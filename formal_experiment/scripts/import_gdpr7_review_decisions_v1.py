# -*- coding: utf-8 -*-
"""Import explicitly user-supplied GDPR7 six-element review decisions (v1/v2).

Imports decisions from a user-provided, already-filled EDITABLE-structure JSON
(the "source") into the formal editable document (the "target").  The source
is treated as an EXPLICIT human decision source: nothing is ever inferred, and
sentences/fields that are still undecided in the source are left untouched in
the target.

Schema dispatch (by the editable ``schema_version`` of the source AND target):

* v1 -> v1 (``gdpr7_six_element_review_editable@1.0.0``): legacy field-level
  import exactly as the original v1 tooling;
* v2 -> v2 (``gdpr7_six_element_review_editable@1.1.0``): additionally imports
  the structured layer (``rule_items`` / ``actor_action_map`` /
  ``order_relations``).  When a source sentence is structured, its whole
  structured state is applied and the target's legacy six blocks are
  re-mirrored from ``rule_items[0]`` (source wins on any conflict, as required
  by the final normative rule "legacy 镜像违规算 error，导入方必须同步");
  a legacy-only source sentence applies only its decided legacy fields;
* mixed v1 source + v2 target (or vice versa) is refused with a hint to use
  ``--upgrade-decisions-file`` first.

Guards (all fail-closed, zero LLM/API/network):

1. the source, the target and the blank surface must all parse; the source and
   the target must be valid editable documents whose immutable identity
   (dataset_id, counts, rule/sample order, sentence identity fields, candidate
   objects) is identical to the blank surface;
2. every decided field of the source is applied to the target only when it is
   legal (decision in accepted/edited/rejected; edited_value rules; v2
   structured rules); any source error blocks the whole import (``blocked``),
   and ``--apply`` then refuses with exit code 1 and zero writes;
3. ``--apply`` REQUIRES a confirmation event JSON (schema
   ``gdpr7_review_import_confirmation_event@1.0.0``) whose recorded sha256s
   (source_file_sha256 / target_file_sha256 / source_blank_sha256) must match
   the ACTUAL current bytes of the three files, whose reviewer must be
   non-empty (the reviewer is taken ONLY from the event), with
   ``gold_created == false`` and ``append_only == true``; a missing
   confirmation or any field/hash drift exits 2 with ZERO writes;
4. ``--dry-run`` needs no confirmation and never writes anything;
5. ``--upgrade-decisions-file <v1-path>`` migrates an ALL-EMPTY v1 editable
   file to the v2 schema (calls ``migrate_v1_to_v2``) and writes it to the
   target path (default v2 decisions file).  Like ``--apply`` it requires a
   confirmation whose ``source_file_sha256`` matches the v1 file bytes and
   whose ``target_file_sha256`` matches the migrated bytes that will be
   written; a non-empty v1 file is refused with exit 2 (decisions must be
   migrated by a human, never copied automatically);
6. the write itself is atomic: the previous target content is copied to
   ``<target>.bak`` and the new payload replaces the file via temp + rename.

Exit codes: 0 = applied (or clean dry-run); 1 = blocked (source/target
invalid) or a blocked dry-run; 2 = usage / file errors / confirmation missing
or drifted.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.gdpr7_review_rules_v1 import (  # noqa: E402
    ALL_FIELDS,
    DECISION_VALUES,
    DEFAULT_BLANK_PATH,
    DEFAULT_EDITABLE_PATH,
    DEFAULT_EDITABLE_V2_PATH,
    SCHEMA_EDITABLE,
    SCHEMA_EDITABLE_V2,
    atomic_save_json,
    audit_filled_document,
    audit_filled_document_v2,
    collect_stats,
    collect_stats_v2,
    doc_json_bytes,
    iter_flat_sentences,
    load_json,
    migrate_v1_to_v2,
    recompute_doc_status,
    recompute_doc_status_v2,
    recompute_sentence_review_state,
    recompute_sentence_review_state_v2,
    sha256_bytes,
    sha256_file,
    validate_confirmation_event,
    validate_field_decision,
)


def _schema_version(doc: Any) -> Any:
    return doc.get("schema_version") if isinstance(doc, dict) else None


# ---------------------------------------------------------------------------
# v1 apply (original semantics, unchanged)
# ---------------------------------------------------------------------------


def _apply_plan_v1(target_doc: dict[str, Any],
                   source_doc: dict[str, Any]) -> dict[str, Any]:
    """Apply every legal decided field of ``source_doc`` onto ``target_doc``.

    Mutates ``target_doc`` in place (callers pass a deep copy when the target
    file must stay untouched on failure).  Returns an application summary.
    """
    summary = {
        "sentences_touched": 0,
        "fields_applied": 0,
        "applied": {"accepted": 0, "edited": 0, "rejected": 0},
    }
    t_flat = list(iter_flat_sentences(target_doc))
    s_flat = list(iter_flat_sentences(source_doc))
    for (rid_t, t), (_rid_s, s) in zip(t_flat, s_flat):
        sid = t.get("sample_id")
        t_review = t.get("review")
        s_review = s.get("review")
        if not isinstance(t_review, dict) or not isinstance(s_review, dict):
            continue
        touched = False
        for field in ALL_FIELDS:
            s_entry = s_review.get(field)
            t_entry = t_review.get(field)
            if not isinstance(s_entry, dict) or not isinstance(t_entry, dict):
                continue
            decision = s_entry.get("decision")
            edited_value = s_entry.get("edited_value")
            if decision not in DECISION_VALUES:
                continue  # undecided in the source -> leave the target untouched
            ok, _ferr = validate_field_decision(
                field, decision, edited_value, t.get("sentence_text"))
            if not ok:
                continue  # defensive: a clean plan already excludes these
            t_entry["decision"] = decision
            t_entry["edited_value"] = edited_value
            summary["applied"][decision] += 1
            summary["fields_applied"] += 1
            touched = True
        if touched:
            summary["sentences_touched"] += 1
        if isinstance(s_review.get("notes"), str):
            t_review["notes"] = s_review["notes"]
        recompute_sentence_review_state(t)
    recompute_doc_status(target_doc)
    return summary


# ---------------------------------------------------------------------------
# v2 apply (structured layer included)
# ---------------------------------------------------------------------------


def _apply_sentence_v2(t: dict[str, Any], s: dict[str, Any],
                       summary: dict[str, Any]) -> bool:
    """Apply one v2 source sentence onto the matching target sentence.

    Returns True when anything was touched.  Structured source sentences
    (``rule_items`` non-null) copy the whole structured state and re-mirror
    the legacy six blocks from ``rule_items[0]`` (source wins).  Legacy-only
    source sentences apply only the decided legacy fields.
    """
    t_review = t.get("review")
    s_review = s.get("review")
    if not isinstance(t_review, dict) or not isinstance(s_review, dict):
        return False
    touched = False
    s_items = s_review.get("rule_items")
    if isinstance(s_items, list) and s_items:
        # structured source: authoritative copy of the whole structured state
        t_review["rule_items"] = copy.deepcopy(s_items)
        t_review["actor_action_map"] = copy.deepcopy(
            s_review.get("actor_action_map"))
        t_review["order_relations"] = copy.deepcopy(
            s_review.get("order_relations"))
        mirror = s_items[0] if isinstance(s_items[0], dict) else None
        if isinstance(mirror, dict):
            for field in ALL_FIELDS:
                block = mirror.get(field)
                if isinstance(block, dict):
                    t_review[field] = copy.deepcopy(block)
        summary["sentences_touched"] += 1
        for item in s_items:
            if isinstance(item, dict):
                for field in ALL_FIELDS:
                    block = item.get(field)
                    if isinstance(block, dict) \
                            and block.get("decision") in DECISION_VALUES:
                        summary["applied"][block["decision"]] += 1
                        summary["fields_applied"] += 1
        if isinstance(s_review.get("notes"), str):
            t_review["notes"] = s_review["notes"]
        recompute_sentence_review_state_v2(t)
        return True
    # legacy-only source: apply decided legacy fields (v1-style); the source
    # expresses "no extra structured items" for this sentence, so any stale
    # target structured state is cleared to keep the mirror invariant sound.
    source_decided_any = False
    for field in ALL_FIELDS:
        s_entry = s_review.get(field)
        if isinstance(s_entry, dict) and s_entry.get("decision") in DECISION_VALUES:
            source_decided_any = True
            break
    for field in ALL_FIELDS:
        s_entry = s_review.get(field)
        t_entry = t_review.get(field)
        if not isinstance(s_entry, dict) or not isinstance(t_entry, dict):
            continue
        decision = s_entry.get("decision")
        edited_value = s_entry.get("edited_value")
        if decision not in DECISION_VALUES:
            continue
        ok, _ferr = validate_field_decision(
            field, decision, edited_value, t.get("sentence_text"))
        if not ok:
            continue
        t_entry["decision"] = decision
        t_entry["edited_value"] = edited_value
        summary["applied"][decision] += 1
        summary["fields_applied"] += 1
        touched = True
    if source_decided_any and (
            isinstance(t_review.get("rule_items"), list)
            and t_review["rule_items"]):
        t_review["rule_items"] = None
        t_review["actor_action_map"] = None
        t_review["order_relations"] = None
        touched = True
    if touched:
        summary["sentences_touched"] += 1
    if isinstance(s_review.get("notes"), str):
        t_review["notes"] = s_review["notes"]
    recompute_sentence_review_state_v2(t)
    return touched


def _apply_plan_v2(target_doc: dict[str, Any],
                   source_doc: dict[str, Any]) -> dict[str, Any]:
    """Apply a v2 source document onto a v2 target document (in place)."""
    summary = {
        "sentences_touched": 0,
        "fields_applied": 0,
        "applied": {"accepted": 0, "edited": 0, "rejected": 0},
        "structured_sentences_applied": 0,
    }
    t_flat = list(iter_flat_sentences(target_doc))
    s_flat = list(iter_flat_sentences(source_doc))
    for (rid_t, t), (_rid_s, s) in zip(t_flat, s_flat):
        s_review = s.get("review")
        was_structured = isinstance(s_review, dict) \
            and isinstance(s_review.get("rule_items"), list) \
            and s_review["rule_items"]
        if _apply_sentence_v2(t, s, summary) and was_structured:
            summary["structured_sentences_applied"] += 1
    recompute_doc_status_v2(target_doc)
    return summary


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def plan_import_v1(source_doc: Any, target_doc: Any, blank_doc: Any
                   ) -> dict[str, Any]:
    """Original v1 planning (backward compatible)."""
    blocked: list[str] = []
    warnings: list[str] = []
    if not isinstance(source_doc, dict):
        return {"blocked": ["source document is not an object"], "warnings": []}
    if not isinstance(target_doc, dict):
        return {"blocked": ["target document is not an object"], "warnings": []}
    if source_doc.get("schema_version") != SCHEMA_EDITABLE:
        blocked.append(
            f"source schema_version {source_doc.get('schema_version')!r} != "
            f"{SCHEMA_EDITABLE!r}"
        )
    if target_doc.get("schema_version") != SCHEMA_EDITABLE:
        blocked.append(
            f"target schema_version {target_doc.get('schema_version')!r} != "
            f"{SCHEMA_EDITABLE!r}"
        )
    src_audit = audit_filled_document(source_doc, blank_doc, require_blank=True)
    blocked.extend(src_audit["errors"])
    warnings.extend(src_audit["warnings"])
    tgt_audit = audit_filled_document(target_doc, blank_doc, require_blank=True)
    blocked.extend(tgt_audit["errors"])
    return {"blocked": blocked, "warnings": warnings}


def plan_import_v2(source_doc: Any, target_doc: Any, blank_doc: Any
                   ) -> dict[str, Any]:
    """v2 planning: both documents must be v2 editable and v2-valid."""
    blocked: list[str] = []
    warnings: list[str] = []
    if not isinstance(source_doc, dict):
        return {"blocked": ["source document is not an object"], "warnings": []}
    if not isinstance(target_doc, dict):
        return {"blocked": ["target document is not an object"], "warnings": []}
    for label, doc in (("source", source_doc), ("target", target_doc)):
        if doc.get("schema_version") != SCHEMA_EDITABLE_V2:
            blocked.append(
                f"{label} schema_version {doc.get('schema_version')!r} != "
                f"{SCHEMA_EDITABLE_V2!r}"
            )
    src_audit = audit_filled_document_v2(source_doc, blank_doc,
                                         require_blank=True)
    blocked.extend(src_audit["errors"])
    warnings.extend(src_audit["warnings"])
    tgt_audit = audit_filled_document_v2(target_doc, blank_doc,
                                         require_blank=True)
    blocked.extend(tgt_audit["errors"])
    return {"blocked": blocked, "warnings": warnings}


def plan_import(source_doc: Any, target_doc: Any, blank_doc: Any) -> dict[str, Any]:
    """Dispatch the planning step by the source/target schema version."""
    s_v = _schema_version(source_doc)
    t_v = _schema_version(target_doc)
    if s_v == SCHEMA_EDITABLE_V2 or t_v == SCHEMA_EDITABLE_V2:
        if s_v != SCHEMA_EDITABLE_V2 or t_v != SCHEMA_EDITABLE_V2:
            return {
                "blocked": [
                    "schema mismatch: v2 import requires BOTH source and "
                    "target to be gdpr7_six_element_review_editable@1.1.0; "
                    "use --upgrade-decisions-file to migrate an empty v1 file "
                    "to v2 first"
                ],
                "warnings": [],
            }
        return plan_import_v2(source_doc, target_doc, blank_doc)
    return plan_import_v1(source_doc, target_doc, blank_doc)


# ---------------------------------------------------------------------------
# Import flow (files)
# ---------------------------------------------------------------------------


def import_decisions(source_path: Path,
                     target_path: Path,
                     blank_path: Path,
                     confirmation_path: Optional[Path] = None,
                     apply: bool = False) -> dict[str, Any]:
    """Run the import flow over real files (dry-run or apply).

    Returns a dict with ``exit_code`` (0 / 1 / 2), ``ok``, human-readable
    messages, the plan outcome and, for dry-run/apply alike, the resulting
    would-be/actual stats.  On apply success the file is replaced atomically
    after a ``.bak`` copy; on any failure NOTHING is written.
    """
    result: dict[str, Any] = {
        "ok": False,
        "exit_code": 2,
        "blocked": [],
        "warnings": [],
        "confirmation_problems": [],
        "applied": None,
        "stats": None,
        "backup": None,
        "written": False,
        "message": "",
    }

    def _fail(code: int, message: str) -> dict[str, Any]:
        result["message"] = message
        result["exit_code"] = code
        return result

    for label, path in (("source", source_path), ("target", target_path),
                        ("blank", blank_path)):
        if not Path(path).is_file():
            return _fail(2, f"{label} file missing: {path}")
    try:
        source_doc = load_json(source_path)
        target_doc = load_json(target_path)
        blank_doc = load_json(blank_path)
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(2, f"cannot read input files: {exc}")
    if not isinstance(source_doc, dict) or not isinstance(target_doc, dict) \
            or not isinstance(blank_doc, dict):
        return _fail(2, "source/target/blank must all be JSON objects")

    s_v = _schema_version(source_doc)
    t_v = _schema_version(target_doc)
    v2_mode = (s_v == SCHEMA_EDITABLE_V2 and t_v == SCHEMA_EDITABLE_V2)
    if (s_v == SCHEMA_EDITABLE_V2) != (t_v == SCHEMA_EDITABLE_V2):
        return _fail(2, "schema mismatch: v1/v2 mixed import is refused; "
                        "migrate the empty v1 file with "
                        "--upgrade-decisions-file first")

    plan = plan_import_v2(source_doc, target_doc, blank_doc) if v2_mode \
        else plan_import_v1(source_doc, target_doc, blank_doc)
    result["blocked"] = plan["blocked"]
    result["warnings"] = plan["warnings"]

    if not apply:
        would_be = copy.deepcopy(target_doc)
        applied = _apply_plan_v2(would_be, source_doc) if v2_mode \
            else _apply_plan_v1(would_be, source_doc)
        result["applied"] = applied
        result["stats"] = collect_stats_v2(would_be) if v2_mode \
            else collect_stats(would_be)
        result["ok"] = True
        result["exit_code"] = 1 if plan["blocked"] else 0
        result["message"] = (
            "dry-run done (nothing written)" if not plan["blocked"]
            else "dry-run done but blocked items exist (--apply would be refused)"
        )
        return result

    # --apply ----------------------------------------------------------------
    if confirmation_path is None:
        return _fail(2, "--apply requires --confirmation event JSON")
    if not Path(confirmation_path).is_file():
        return _fail(2, f"confirmation file missing: {confirmation_path}")
    try:
        conf = load_json(confirmation_path)
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(2, f"cannot read confirmation file: {exc}")
    if not isinstance(conf, dict):
        return _fail(2, "confirmation file is not a JSON object")
    conf_problems = validate_confirmation_event(
        conf,
        source_file_sha256=sha256_file(source_path),
        target_file_sha256=sha256_file(target_path),
        blank_file_sha256=sha256_file(blank_path),
    )
    if conf_problems:
        result["confirmation_problems"] = conf_problems
        return _fail(2, "confirmation validation failed (zero writes): "
                        + "; ".join(conf_problems))
    if plan["blocked"]:
        result["ok"] = False
        result["exit_code"] = 1
        result["message"] = "--apply refused: blocked items exist (zero writes)"
        return result

    new_doc = copy.deepcopy(target_doc)
    applied = _apply_plan_v2(new_doc, source_doc) if v2_mode \
        else _apply_plan_v1(new_doc, source_doc)
    backup = atomic_save_json(target_path, new_doc, keep_backup=True)
    result["applied"] = applied
    result["stats"] = collect_stats_v2(new_doc) if v2_mode \
        else collect_stats(new_doc)
    result["backup"] = str(backup) if backup else None
    result["written"] = True
    result["ok"] = True
    result["exit_code"] = 0
    result["message"] = (
        f"import done: {applied['fields_applied']} fields / "
        f"{applied['sentences_touched']} sentences "
        f"(backup: {result['backup']})"
    )
    return result


# ---------------------------------------------------------------------------
# v1 -> v2 upgrade of an all-empty v1 decisions file
# ---------------------------------------------------------------------------


def v1_is_empty(doc: Any) -> list[str]:
    """Problems that prevent auto-upgrade of a v1 decisions file.

    Empty list == the v1 document carries no decisions (every legacy decision
    null, every sentence unreviewed, no rule-level deviation) and may be
    structurally migrated to the v2 schema by a pure function.  Real decisions
    are NEVER copied: a non-empty v1 file must be migrated by a human.
    """
    problems: list[str] = []
    if not isinstance(doc, dict):
        return ["v1 editable document is not an object"]
    if doc.get("schema_version") != SCHEMA_EDITABLE:
        problems.append(
            f"v1 schema_version {doc.get('schema_version')!r} != "
            f"{SCHEMA_EDITABLE!r}"
        )
    for _rid, sentence in iter_flat_sentences(doc):
        sid = sentence.get("sample_id")
        review = sentence.get("review")
        if not isinstance(review, dict):
            continue
        if review.get("review_state") not in (None, "unreviewed"):
            problems.append(
                f"{sid}: review_state {review.get('review_state')!r} != "
                f"unreviewed（v1 非空；不能自动迁移）"
            )
        for field in ALL_FIELDS:
            entry = review.get(field)
            if isinstance(entry, dict) and entry.get("decision") is not None:
                problems.append(
                    f"{sid}: review.{field}.decision 非空（v1 非空；不能自动"
                    f"迁移，请人工迁移）"
                )
    return problems


def upgrade_decisions_file(v1_path: Path,
                           blank_path: Path,
                           target_path: Path,
                           confirmation_path: Optional[Path] = None,
                           dry_run: bool = False) -> dict[str, Any]:
    """Migrate an ALL-EMPTY v1 editable file to the v2 schema.

    When ``dry_run`` is False the migrated document is written to
    ``target_path`` (which must not exist yet) with the workflow's canonical
    byte layout, after a confirmation whose ``source_file_sha256`` matches the
    v1 file and whose ``target_file_sha256`` matches the migrated bytes that
    will be written.  Zero writes on any failure; never copies decisions.
    """
    result: dict[str, Any] = {
        "ok": False,
        "exit_code": 2,
        "blocked": [],
        "confirmation_problems": [],
        "written": False,
        "message": "",
        "target_sha256": None,
    }

    def _fail(code: int, message: str) -> dict[str, Any]:
        result["message"] = message
        result["exit_code"] = code
        return result

    for label, path in (("v1", v1_path), ("blank", blank_path)):
        if not Path(path).is_file():
            return _fail(2, f"{label} file missing: {path}")
    if Path(target_path).exists():
        return _fail(2, f"refusing to overwrite existing target: {target_path}")
    try:
        v1_doc = load_json(v1_path)
        blank_doc = load_json(blank_path)
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(2, f"cannot read input files: {exc}")

    problems = v1_is_empty(v1_doc)
    if problems:
        result["blocked"] = problems
        result["exit_code"] = 2
        result["message"] = ("v1 file is not empty; automatic migration "
                             "refused — migrate by a human first")
        return result

    migrated = migrate_v1_to_v2(v1_doc)
    payload = doc_json_bytes(migrated)
    result["target_sha256"] = sha256_bytes(payload)
    result["blocked"] = []

    if dry_run:
        result["ok"] = True
        result["exit_code"] = 0
        result["message"] = "upgrade dry-run done (nothing written)"
        return result

    if confirmation_path is None:
        return _fail(2, "upgrade requires --confirmation event JSON")
    if not Path(confirmation_path).is_file():
        return _fail(2, f"confirmation file missing: {confirmation_path}")
    try:
        conf = load_json(confirmation_path)
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(2, f"cannot read confirmation file: {exc}")
    conf_problems = validate_confirmation_event(
        conf,
        source_file_sha256=sha256_file(v1_path),
        target_file_sha256=result["target_sha256"],
        blank_file_sha256=sha256_file(blank_path),
    )
    if conf_problems:
        result["confirmation_problems"] = conf_problems
        return _fail(2, "confirmation validation failed (zero writes): "
                        + "; ".join(conf_problems))

    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    Path(target_path).write_bytes(payload)
    result["written"] = True
    result["ok"] = True
    result["exit_code"] = 0
    result["message"] = f"upgrade done: v1 -> v2 written to {target_path}"
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_plan(result: dict[str, Any]) -> None:
    for msg in result["blocked"]:
        print(f"  BLOCKED: {msg}")
    for msg in result["warnings"]:
        print(f"  WARN   : {msg}")
    if result["blocked"]:
        print(f"blocked={len(result['blocked'])} -> --apply would be refused "
              f"(zero writes)")
    if result["confirmation_problems"]:
        for msg in result["confirmation_problems"]:
            print(f"  CONFIRM: {msg}")
    if result.get("applied") is not None:
        applied = result["applied"]
        print(
            f"applied/would-be fields: accepted={applied['applied']['accepted']} "
            f"edited={applied['applied']['edited']} "
            f"rejected={applied['applied']['rejected']} "
            f"fields={applied['fields_applied']} "
            f"sentences={applied['sentences_touched']}"
        )
    if result.get("stats") is not None:
        stats = result["stats"]
        print(
            f"result state: sentences={stats['sentences_total']} "
            f"reviewed={stats['reviewed']} unreviewed={stats['unreviewed']} "
            f"decisions={stats['decisions_total']}/{stats['fields_total']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=None,
                        help="user-provided filled editable JSON (decisions "
                             "source); required for --dry-run/--apply")
    parser.add_argument("--file", type=Path, default=DEFAULT_EDITABLE_V2_PATH,
                        help="target formal editable file (default: v2 "
                             "decisions file)")
    parser.add_argument("--blank", type=Path, default=DEFAULT_BLANK_PATH,
                        help="blank surface used for identity checks")
    parser.add_argument("--confirmation", type=Path, default=None,
                        help="confirmation event JSON (required for --apply "
                             "and --upgrade-decisions-file)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true",
                        help="print would-be statistics; never write")
    action.add_argument("--apply", action="store_true",
                        help="apply the import (requires --confirmation)")
    action.add_argument("--upgrade-decisions-file", type=Path, metavar="V1_PATH",
                        default=None,
                        help="migrate an ALL-EMPTY v1 decisions file to the v2 "
                             "schema and write it to --file (requires "
                             "--confirmation; refuses non-empty v1)")
    args = parser.parse_args()

    if args.upgrade_decisions_file is not None:
        if args.source is not None:
            print("error: --source cannot be combined with "
                  "--upgrade-decisions-file", file=sys.stderr)
            return 2
        result = upgrade_decisions_file(
            v1_path=args.upgrade_decisions_file,
            blank_path=args.blank,
            target_path=args.file,
            confirmation_path=args.confirmation,
            dry_run=args.dry_run,
        )
        print(result["message"])
        _print_plan(result)
        return result["exit_code"]

    if args.source is None:
        print("error: --source is required for --dry-run/--apply",
              file=sys.stderr)
        return 2
    result = import_decisions(
        source_path=args.source,
        target_path=args.file,
        blank_path=args.blank,
        confirmation_path=args.confirmation,
        apply=args.apply,
    )
    print(result["message"])
    _print_plan(result)
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
