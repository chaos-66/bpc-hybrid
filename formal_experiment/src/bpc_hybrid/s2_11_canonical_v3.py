# -*- coding: utf-8 -*-
"""S2.11 canonical review/proposal v3 validator (Checkpoint F).

v3 strengthens the v2 canonical rules with the targeted corrections
identified in Checkpoint F (proposal v2 -> v3):

  * EVERY span id (modality evidence AND ordinary fields) must be unique
    across the whole record; duplicate ids refuse (v2 only checked
    modality evidence ids and collect_span_ids silently overwrote
    duplicates via a dict)
  * clause ids must be unique within a record
  * actor_action_map edges must reference EXISTING spans, both ends in
    the SAME clause, and duplicate edges refuse; COVERAGE: in any clause
    that has at least one actor and at least one action, EVERY action
    must be mapped by at least one edge (each action executed by an
    actor of that clause is recorded)
  * order_relations must reference two DIFFERENT existing action spans
  * field states unresolved/absent/present, modality label vocabulary,
    byte-verified slice equality (text == source[start:end] against the
    hash-bound source at runtime) are carried forward from v2
  * span collection is list-based (no dict-overwrite hiding)

Containment: committed assets store coordinates only; slice equality is
verified whenever the caller supplies the hash-bound source text.
"""

from __future__ import annotations

from typing import Any, Sequence

MODALITY_LABELS = ("obligation", "permission", "prohibition", "definition")
ORDINARY_FIELDS = ("actor", "action", "condition", "constraint", "exception")
ALL_FIELDS = ("modality",) + ORDINARY_FIELDS
FIELD_STATES = ("unresolved", "absent", "present")


class CanonicalFail(Exception):
    """Fail-closed canonical validation abort."""


def _check(problems: list[str], ok: bool, message: str) -> None:
    if not ok:
        problems.append(message)


def _slice_ok(source_text: str, start: int, end: int,
              text: str | None) -> bool:
    if not (0 <= start < end <= len(source_text)):
        return False
    if text is not None and text != source_text[start:end]:
        return False
    return True


def _span_valid(span: dict[str, Any], source_text: str) -> bool:
    start = span.get("start")
    end = span.get("end")
    if not (isinstance(start, int) and isinstance(end, int)
            and 0 <= start < end <= len(source_text)):
        return False
    return _slice_ok(source_text, start, end, span.get("text"))


def validate_clause(clause: dict[str, Any], source_text: str,
                    clause_index: int, sample_id: str,
                    problems: list[str], *, allow_unresolved: bool) -> None:
    prefix = f"{sample_id} c{clause_index + 1}"
    clause_span = clause.get("clause_span") or {}
    cs = clause_span.get("start")
    ce = clause_span.get("end")
    _check(problems, isinstance(cs, int) and isinstance(ce, int)
           and 0 <= cs < ce <= len(source_text),
           f"{prefix}: bad clause_span")
    if isinstance(cs, int) and isinstance(ce, int):
        _check(problems, _slice_ok(source_text, cs, ce,
                                   clause_span.get("text")),
               f"{prefix}: clause_span slice mismatch")

    modality = clause.get("modality") or {}
    mstatus = modality.get("status")
    _check(problems, mstatus in FIELD_STATES,
           f"{prefix}: bad modality status {mstatus!r}")
    if mstatus == "present":
        label = modality.get("label")
        _check(problems, label in MODALITY_LABELS,
               f"{prefix}: modality label {label!r} outside "
               f"{MODALITY_LABELS}")
        evidence = modality.get("evidence") or []
        _check(problems, isinstance(evidence, list) and len(evidence) >= 1,
               f"{prefix}: present modality requires >=1 evidence span")
        for i, span in enumerate(evidence):
            _check(problems, _span_valid(span, source_text),
                   f"{prefix}: modality evidence[{i}] slice mismatch")
    elif mstatus == "absent":
        _check(problems, modality.get("label") is None,
               f"{prefix}: absent modality must not carry a label")
    elif mstatus == "unresolved" and not allow_unresolved:
        problems.append(f"{prefix}: modality unresolved in adjudicated")

    for field in ORDINARY_FIELDS:
        entry = clause.get(field) or {}
        status = entry.get("status")
        _check(problems, status in FIELD_STATES,
               f"{prefix}: bad {field} status {status!r}")
        spans = entry.get("spans") or []
        _check(problems, isinstance(spans, list),
               f"{prefix}: {field} spans must be a list")
        if status == "present":
            _check(problems, len(spans) >= 1,
                   f"{prefix}: present {field} requires >=1 span")
        elif status == "absent":
            _check(problems, len(spans) == 0,
                   f"{prefix}: absent {field} must have no spans")
        elif status == "unresolved" and not allow_unresolved:
            problems.append(f"{prefix}: {field} unresolved in adjudicated")
        for i, span in enumerate(spans):
            _check(problems, _span_valid(span, source_text),
                   f"{prefix}: {field}[{i}] slice mismatch")


def collect_span_ids(clause: dict[str, Any],
                     clause_index: int) -> list[tuple[str, str]]:
    """All (span_id, field) of a clause as a LIST (duplicates are NOT
    hidden by dict overwrite; the caller detects them)."""
    out: list[tuple[str, str]] = []
    modality = clause.get("modality") or {}
    for i, span in enumerate(modality.get("evidence") or []):
        out.append((span.get("id"), "modality_evidence"))
    for field in ORDINARY_FIELDS:
        for span in (clause.get(field) or {}).get("spans") or []:
            out.append((span.get("id"), field))
    return out


def validate_record(record: dict[str, Any], source_text: str, *,
                    allow_unresolved: bool) -> list[str]:
    problems: list[str] = []
    canonical = record.get("canonical") if isinstance(record, dict) \
        else record
    if not isinstance(canonical, dict):
        return ["record is not a dict with a canonical payload"]
    clauses = canonical.get("clauses") or []
    if not isinstance(clauses, list) or not clauses:
        return ["canonical has no clauses"]

    # ---- clause id uniqueness + per-clause structural checks ------------
    clause_ids: list[str] = []
    clause_id_fields: list[list[tuple[str, str]]] = []
    for i, clause in enumerate(clauses):
        if not isinstance(clause, dict):
            problems.append(f"c{i + 1}: clause not a dict")
            continue
        cid = clause.get("clause_id")
        if not isinstance(cid, str) or not cid:
            problems.append(f"c{i + 1}: missing clause_id")
        elif cid in clause_ids:
            problems.append(f"duplicate clause id {cid!r}")
        clause_ids.append(cid)
        validate_clause(clause, source_text, i, "record", problems,
                        allow_unresolved=allow_unresolved)
        clause_id_fields.append(collect_span_ids(clause, i))

    # ---- span id uniqueness across the whole record (list-based) --------
    seen: dict[str, str] = {}
    for i, fields in enumerate(clause_id_fields):
        for sid, field in fields:
            if not sid:
                continue
            if sid in seen:
                problems.append(
                    f"duplicate span id {sid!r} ({seen[sid]} and "
                    f"c{i + 1}.{field})")
            else:
                seen[sid] = f"c{i + 1}.{field}"

    # ---- actor_action_map: existence, same clause, no dup, coverage -----
    aam = canonical.get("actor_action_map") or []
    edges: set[tuple[str, str]] = set()
    for i, pair in enumerate(aam):
        actor_ref = pair.get("actor_span_id")
        action_ref = pair.get("action_span_id")
        edge = (actor_ref, action_ref)
        if edge in edges:
            problems.append(f"actor_action_map[{i}]: duplicate edge")
        edges.add(edge)
        actor_clause = _ref_clause(actor_ref, clause_id_fields, "actor")
        action_clause = _ref_clause(action_ref, clause_id_fields, "action")
        _check(problems, actor_clause is not None,
               f"actor_action_map[{i}]: bad actor ref {actor_ref!r}")
        _check(problems, action_clause is not None,
               f"actor_action_map[{i}]: bad action ref {action_ref!r}")
        if actor_clause is not None and action_clause is not None and \
                actor_clause != action_clause:
            problems.append(
                f"actor_action_map[{i}]: actor and action are in different "
                "clauses")
    # coverage: every action in a clause that also has actors must be
    # mapped by some edge whose actor lies in the same clause
    for i, fields in enumerate(clause_id_fields):
        actor_ids = {sid for sid, f in fields if f == "actor"}
        action_ids = [sid for sid, f in fields if f == "action"]
        if not actor_ids or not action_ids:
            continue
        for aid in action_ids:
            mapped = any(b == aid and a in actor_ids
                         for (a, b) in edges)
            if not mapped:
                problems.append(
                    f"c{i + 1}: action {aid!r} has no actor_action_map edge "
                    "to an actor of this clause")

    # ---- order_relations: two different existing actions ---------------
    action_ids = {sid for fields in clause_id_fields
                  for sid, f in fields if f == "action"}
    orders = canonical.get("order_relations") or []
    for i, rel in enumerate(orders):
        before = rel.get("before_span_id")
        after = rel.get("after_span_id")
        _check(problems, before in action_ids,
               f"order_relations[{i}]: bad before ref {before!r}")
        _check(problems, after in action_ids,
               f"order_relations[{i}]: bad after ref {after!r}")
        if before == after:
            problems.append(f"order_relations[{i}]: before == after")
    return problems


def _ref_clause(ref: str, clause_id_fields: list[list[tuple[str, str]]],
                field: str) -> int | None:
    for i, fields in enumerate(clause_id_fields):
        if any(sid == ref and f == field for sid, f in fields):
            return i
    return None


def validate(records: dict[str, dict[str, Any]],
             source_texts: dict[str, str], *,
             allow_unresolved: bool,
             expected_ids: Sequence[str] | None = None) -> dict[str, Any]:
    problems: list[str] = []
    if expected_ids is not None:
        expected = set(expected_ids)
        actual = set(records)
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing:
            problems.append(f"missing sample ids: {missing}")
        if extra:
            problems.append(f"extra sample ids: {extra}")
    for sample_id, record in sorted(records.items()):
        text = source_texts.get(sample_id)
        if text is None:
            problems.append(f"{sample_id}: no hash-bound source text "
                            "supplied")
            continue
        problems.extend(
            f"{sample_id}: {p}" for p in
            validate_record(record, text, allow_unresolved=allow_unresolved))
    return {
        "valid": not problems,
        "problems": problems,
        "record_count": len(records),
    }
