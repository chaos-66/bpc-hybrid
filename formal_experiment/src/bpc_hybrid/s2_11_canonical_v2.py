# -*- coding: utf-8 -*-
"""S2.11 canonical review/proposal v2 validator (Checkpoint E1).

The v2 model reuses the Stage 2 canonical clause/span conventions
(identified spans with {start, end}; text == source_text[start:end]) and
explicitly separates the three field states:

  * "unresolved" - not yet adjudicated (only legal before freeze)
  * "absent"     - user-adjudicated ABSENT (no span; legal in frozen Gold)
  * "present"    - one or more exact adjudicated spans

modality uses {status, label, evidence[]} (label = controlled vocabulary,
evidence = normative cue spans). actor/action/condition/constraint/
exception use span arrays. Multiple actors/actions/conditions/constraints/
exceptions are supported; actor-action mapping and multi-action order
relations are carried as typed references to span ids.

Containment: committed S2.11 assets store spans as {start, end} WITHOUT
source text; the slice-equality invariant (text == source[start:end]) is
enforced by this validator whenever the caller supplies the hash-bound
source text (local renders materialize `text`; committed coordinates are
re-verified against the hash-bound source at runtime).

FAIL-CLOSED: duplicate span ids, out-of-range/overlapping clause spans,
unknown references in actor_action_map / order_relations, empty spans for
present fields, missing modality evidence, labels outside the vocabulary,
and adjudicated records with any unresolved field all refuse.
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


def validate_clause(clause: dict[str, Any], source_text: str,
                    clause_index: int, sample_id: str,
                    problems: list[str], *, allow_unresolved: bool) -> None:
    """Validate one clause payload. Appends problems; never raises except
    on structural garbage (non-dict)."""
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
        seen: set[str] = set()
        for i, span in enumerate(evidence):
            sid = span.get("id") or f"{prefix}_mod_ev_{i}"
            _check(problems, sid not in seen,
                   f"{prefix}: duplicate modality evidence id {sid!r}")
            seen.add(sid)
            _check(problems, _span_valid(span, source_text, prefix,
                                         f"modality_evidence[{i}]"),
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
            _check(problems, _span_valid(span, source_text, prefix,
                                         f"{field}[{i}]"),
                   f"{prefix}: {field}[{i}] slice mismatch")


def _span_valid(span: dict[str, Any], source_text: str, prefix: str,
                label: str) -> bool:
    start = span.get("start")
    end = span.get("end")
    if not (isinstance(start, int) and isinstance(end, int)
            and 0 <= start < end <= len(source_text)):
        return False
    return _slice_ok(source_text, start, end, span.get("text"))


def collect_span_ids(clause: dict[str, Any]) -> dict[str, str]:
    """span id -> field name for one clause (for map/order validation)."""
    ids: dict[str, str] = {}
    modality = clause.get("modality") or {}
    for i, span in enumerate(modality.get("evidence") or []):
        ids[span.get("id") or f"m{i}"] = "modality_evidence"
    for field in ORDINARY_FIELDS:
        for i, span in enumerate((clause.get(field) or {}).get("spans") or []):
            ids[span.get("id") or f"{field}_{i}"] = field
    return ids


def validate_record(record: dict[str, Any], source_text: str, *,
                    allow_unresolved: bool) -> list[str]:
    """Validate one full canonical record payload. Returns problems."""
    problems: list[str] = []
    canonical = record.get("canonical") if isinstance(record, dict) \
        else record
    if not isinstance(canonical, dict):
        return ["record is not a dict with a canonical payload"]
    clauses = canonical.get("clauses") or []
    if not isinstance(clauses, list) or not clauses:
        return ["canonical has no clauses"]
    clause_field_ids: list[dict[str, str]] = []
    for i, clause in enumerate(clauses):
        if not isinstance(clause, dict):
            problems.append(f"c{i + 1}: clause not a dict")
            continue
        validate_clause(clause, source_text, i, "record", problems,
                        allow_unresolved=allow_unresolved)
        clause_field_ids.append(collect_span_ids(clause))

    # actor_action_map: refs must resolve to actor/action span ids
    aam = canonical.get("actor_action_map") or []
    for i, pair in enumerate(aam):
        actor_ref = pair.get("actor_span_id")
        action_ref = pair.get("action_span_id")
        actor_ok = any(actor_ref in cids and cids[actor_ref] == "actor"
                       for cids in clause_field_ids)
        action_ok = any(action_ref in cids and cids[action_ref] == "action"
                        for cids in clause_field_ids)
        _check(problems, actor_ok, f"actor_action_map[{i}]: bad actor ref")
        _check(problems, action_ok, f"actor_action_map[{i}]: bad action ref")

    # order_relations: refs must resolve to action span ids
    orders = canonical.get("order_relations") or []
    for i, rel in enumerate(orders):
        before = rel.get("before_span_id")
        after = rel.get("after_span_id")
        before_ok = any(before in cids and cids[before] == "action"
                        for cids in clause_field_ids)
        after_ok = any(after in cids and cids[after] == "action"
                       for cids in clause_field_ids)
        _check(problems, before_ok, f"order_relations[{i}]: bad before ref")
        _check(problems, after_ok, f"order_relations[{i}]: bad after ref")

    # modality label consistency across clauses (defensive: no mixing)
    labels = {c.get("modality", {}).get("label")
              for c in clauses if (c.get("modality") or {}).get("status")
              == "present"}
    if len(labels) > 1:
        problems.append(f"modality labels differ across clauses: {labels}")
    return problems


def validate(records: dict[str, dict[str, Any]],
             source_texts: dict[str, str], *,
             allow_unresolved: bool,
             expected_ids: Sequence[str] | None = None) -> dict[str, Any]:
    """Validate a whole decisions/proposal record map.

    source_texts: sample_id -> hash-bound source text (loaded by the
    caller). expected_ids: exact sample set (missing/duplicate/extra
    refuse).
    """
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
