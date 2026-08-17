# -*- coding: utf-8 -*-
"""S2.12 method-adapter dry-run (Checkpoint E3).

The B0/H1/D1 method arms produce canonical attempt envelopes
  {sample_id, request_status, record: {sample_id, clauses: [...]},
   error_category}
over the same Stage 2 canonical prediction schema. For the S2.12 complex
corpus run the SAME envelope + canonical clause/span shape is reused, so
the conversion is an identity over the canonical fields with explicit
validation (fail-closed):

  * adapt_method_attempts(attempts, method_id) validates the envelope and
    the canonical record shape (sample_id present, record.clauses is a
    list, every clause carries modality + the five span fields) and
    returns the canonical attempts
  * the v1 whole-field flat {field: string} shape is NOT accepted (it
    cannot represent multi-span clauses); a clear error names the schema
    mismatch

ZERO LLM/API; deterministic; never reads Gold.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")
METHOD_IDS = ("sun_rule_only", "sun_llm_fallback", "direct_llm")


class AdapterFail(Exception):
    """Fail-closed adapter abort."""


def adapt_method_attempts(attempts: Sequence[Mapping[str, Any]],
                          method_id: str) -> list[dict[str, Any]]:
    if method_id not in METHOD_IDS:
        raise AdapterFail(f"unknown method_id {method_id!r}; expected one "
                          f"of {METHOD_IDS}")
    out: list[dict[str, Any]] = []
    for i, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            raise AdapterFail(f"attempt[{i}] is not an object")
        sample_id = attempt.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id:
            raise AdapterFail(f"attempt[{i}]: missing sample_id")
        record = attempt.get("record")
        if not isinstance(record, dict):
            raise AdapterFail(f"{sample_id}: missing canonical record")
        if record.get("sample_id") != sample_id:
            raise AdapterFail(f"{sample_id}: record sample_id mismatch")
        clauses = record.get("clauses")
        if not isinstance(clauses, list):
            raise AdapterFail(
                f"{sample_id}: record has no clauses list; the v1 flat "
                "{field: string} shape is NOT accepted (cannot represent "
                "multi-span clauses)")
        for clause in clauses:
            if not isinstance(clause, dict):
                raise AdapterFail(f"{sample_id}: clause is not an object")
            if not isinstance(clause.get("modality"), dict):
                raise AdapterFail(f"{sample_id}: clause modality missing")
            for field in SPAN_FIELDS:
                entry = clause.get(field)
                span_list = None
                if isinstance(entry, dict) and \
                        isinstance(entry.get("spans"), list):
                    span_list = entry["spans"]          # S2.11 v2 shape
                elif isinstance(entry, list):
                    span_list = entry                   # formal plural shape
                else:
                    plural = clause.get(field + "s")
                    if isinstance(plural, list):
                        span_list = plural              # canonical plural
                if span_list is None:
                    raise AdapterFail(
                        f"{sample_id}: clause field {field!r} missing span "
                        "array")
        out.append({
            "sample_id": sample_id,
            "request_status": attempt.get("request_status"),
            "record": record,
            "error_category": attempt.get("error_category"),
        })
    return out
