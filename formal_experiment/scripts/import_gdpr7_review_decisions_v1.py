# -*- coding: utf-8 -*-
"""Import explicitly user-supplied GDPR7 six-element review decisions (v1).

Imports decisions from a user-provided, already-filled EDITABLE-structure JSON
(the "source"; same schema as the workflow's editing file) into the formal
editable document (the "target",
``data/development/human_review/gdpr7_six_element_review_decisions_v1.json``).
The source is treated as an EXPLICIT human decision source: nothing is ever
inferred, and sentences/fields that are still undecided in the source are left
untouched in the target.

Guards (all fail-closed, zero LLM/API/network):

1. the source, the target and the blank surface must all parse; the source and
   the target must be valid editable documents whose immutable identity
   (dataset_id, counts, rule/sample order, sentence identity fields, candidate
   objects) is identical to the blank surface;
2. every decided field of the source is applied to the target only when it is
   legal (decision in accepted/edited/rejected; edited_value rules); any source
   error blocks the whole import (``blocked``), and ``--apply`` then refuses
   with exit code 1 and zero writes;
3. ``--apply`` REQUIRES a confirmation event JSON (schema
   ``gdpr7_review_import_confirmation_event@1.0.0``) whose recorded sha256s
   (source_file_sha256 / target_file_sha256 / source_blank_sha256) must match
   the ACTUAL current bytes of the three files, whose reviewer must be
   non-empty (the reviewer is taken ONLY from the event), with
   ``gold_created == false`` and ``append_only == true``; a missing
   confirmation or any field/hash drift exits 2 with ZERO writes;
4. ``--dry-run`` needs no confirmation and never writes anything - it prints
   the would-be statistics and the blocked details;
5. the write itself is atomic: the previous target content is copied to
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
    SCHEMA_EDITABLE,
    atomic_save_json,
    audit_filled_document,
    collect_stats,
    iter_flat_sentences,
    load_json,
    recompute_doc_status,
    recompute_sentence_review_state,
    sha256_file,
    validate_confirmation_event,
    validate_field_decision,
)


def _apply_plan(target_doc: dict[str, Any],
                source_doc: dict[str, Any]) -> dict[str, Any]:
    """Apply every legal decided field of ``source_doc`` onto ``target_doc``.

    Mutates ``target_doc`` in place (callers pass a deep copy when the target
    file must stay untouched on failure). Returns an application summary.
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


def plan_import(source_doc: Any, target_doc: Any, blank_doc: Any) -> dict[str, Any]:
    """Pure planning: blocked reasons + advisory warnings.

    Returns ``{"blocked": [...], "warnings": [...]}``. ``blocked`` covers every
    error of the source OR the target against the shared editable structure and
    the blank identity; ``warnings`` come from the source audit (advisory).
    """
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


def import_decisions(source_path: Path,
                     target_path: Path,
                     blank_path: Path,
                     confirmation_path: Optional[Path] = None,
                     apply: bool = False) -> dict[str, Any]:
    """Run the import flow over real files (dry-run or apply).

    Returns a dict with ``exit_code`` (0 / 1 / 2), ``ok``, human-readable
    messages, the plan outcome and, for dry-run/apply alike, the resulting
    would-be/actual stats. On apply success the file is replaced atomically
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

    plan = plan_import(source_doc, target_doc, blank_doc)
    result["blocked"] = plan["blocked"]
    result["warnings"] = plan["warnings"]

    if not apply:
        # dry-run: compute the would-be state on a deep copy, never write.
        would_be = copy.deepcopy(target_doc)
        applied = _apply_plan(would_be, source_doc)
        result["applied"] = applied
        result["stats"] = collect_stats(would_be)
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
    applied = _apply_plan(new_doc, source_doc)
    backup = atomic_save_json(target_path, new_doc, keep_backup=True)
    result["applied"] = applied
    result["stats"] = collect_stats(new_doc)
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
    parser.add_argument("--source", type=Path, required=True,
                        help="user-provided filled editable JSON (decisions source)")
    parser.add_argument("--file", type=Path, default=DEFAULT_EDITABLE_PATH,
                        help="target formal editable file")
    parser.add_argument("--blank", type=Path, default=DEFAULT_BLANK_PATH,
                        help="blank surface used for identity checks")
    parser.add_argument("--confirmation", type=Path, default=None,
                        help="confirmation event JSON (required for --apply)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true",
                        help="print would-be statistics; never write")
    action.add_argument("--apply", action="store_true",
                        help="apply the import (requires --confirmation)")
    args = parser.parse_args()

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
