"""D1 span-coordinate canonicalizer tests (D1-R1 + opt-in grounding repair).

Level 0 (exact coordinates) and Level 1 (unique exact occurrence) keep the
pre-repair behaviour.  The opt-in ``repair_v1`` policy adds Level 2: repeated
exact occurrences are resolved with the model's own original offsets via a
deterministic one-to-one minimum-cost assignment; ties stay unresolved.  The
default remains ``legacy`` (pre-repair) until promotion is explicitly
authorized, and ``legacy`` must still reproduce the pre-repair behaviour.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.d1_span_canonicalizer import (  # noqa: E402
    DEFAULT_COST_METRIC,
    DEFAULT_POLICY,
    POLICY_LEGACY,
    POLICY_REPAIR,
    STATUS_DEGRADED,
    STATUS_FAILED,
    STATUS_REANCHORED,
    STATUS_UNCHANGED,
    canonicalize_record_coordinates,
)

SRC = "The taxpayer shall depreciate the acquisition costs in accordance with Section 11(1)."


def make_clause(
    clause_span,
    *,
    clause_id="c01",
    actors=None,
    actions=None,
    conditions=None,
    constraints=None,
    exceptions=None,
    evidence=None,
    modality_label="obligation",
    actor_action_map=None,
    order_relations=None,
):
    return {
        "clause_id": clause_id,
        "clause_span": clause_span,
        "modality": {"label": modality_label, "evidence": evidence or []},
        "actors": actors or [],
        "actions": actions or [],
        "conditions": conditions or [],
        "constraints": constraints or [],
        "exceptions": exceptions or [],
        "actor_action_map": actor_action_map or [],
        "order_relations": order_relations or [],
    }


def make_record(clauses, source):
    return {
        "schema_version": "1.0.0",
        "sample_id": "estg_demo",
        "source_id": "estg_demo",
        "source_text": source,
        "clauses": clauses,
        "method": {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
        "unsupported_or_ambiguous": [],
    }


def whole_clause(source, clause_id="c01", **kwargs):
    return make_clause({"text": source, "start": 0, "end": len(source)}, clause_id=clause_id, **kwargs)


def span(text, start, end, span_id=None, normalized=None):
    out = {"text": text, "start": start, "end": end,
           "normalized": normalized or " ".join(text.casefold().split())}
    if span_id is not None:
        out["id"] = span_id
    return out


def repair(record, source, **kwargs):
    """Run the opt-in grounding repair explicitly (the default stays legacy)."""
    kwargs.setdefault("policy", POLICY_REPAIR)
    return canonicalize_record_coordinates(record, source, **kwargs)


# ---------------------------------------------------------------------------
# T1 / Level 0
# ---------------------------------------------------------------------------


def test_t1_exact_actor_coordinate_is_untouched():
    r = make_record(
        [whole_clause(SRC, actors=[span("The taxpayer", 0, 12, "a01", "taxpayer")])],
        SRC,
    )
    out, audit = repair(r, SRC)
    assert audit["status"] == STATUS_UNCHANGED
    assert audit["reanchored_count"] == 0
    assert audit["unchanged_spans"] == 1
    assert out == r


# ---------------------------------------------------------------------------
# T2 / Level 1
# ---------------------------------------------------------------------------


def test_t2_unique_exact_occurrence_reanchors():
    r = make_record(
        [whole_clause(SRC, constraints=[span("in accordance with Section 11(1)", 53, 85, "c01", "x")])],
        SRC,
    )
    out, audit = repair(r, SRC)
    assert audit["status"] == STATUS_REANCHORED
    fixed = out["clauses"][0]["constraints"][0]
    assert (fixed["start"], fixed["end"]) == (52, 84)
    assert audit["reanchored_unique_exact"] == 1
    assert audit["repeated_occurrence_cases"] == 0


# ---------------------------------------------------------------------------
# T3 / Level 2 nearest
# ---------------------------------------------------------------------------


def test_t3_repeated_occurrence_unique_nearest_reanchors_second():
    src = "the tax office shall pay and the tax office shall act."
    second = src.rindex("the tax office")
    text = "the tax office"
    r = make_record(
        [whole_clause(src, actors=[span(text, second - 2, second - 2 + len(text), "a01")])],
        src,
    )
    out, audit = repair(r, src)
    fixed = out["clauses"][0]["actors"][0]
    assert (fixed["start"], fixed["end"]) == (second, second + len(text))
    assert audit["status"] == STATUS_REANCHORED
    assert audit["repeated_occurrence_cases"] == 1
    assert audit["repeated_occurrence_recovered"] == 1
    assert audit["reanchored_repeated_exact"] == 1
    assert fixed["id"] == "a01"


# ---------------------------------------------------------------------------
# T4 / tie stays unresolved
# ---------------------------------------------------------------------------


def test_t4_repeated_occurrence_exact_tie_is_unresolved():
    # "ab" occurs at 0 and 10; (5, 7) is equidistant under both metrics.
    src = "ab" + "x" * 8 + "ab"
    r = make_record([whole_clause(src, actors=[span("ab", 5, 7, "a01")])], src)
    out, audit = repair(r, src)
    assert out["clauses"][0]["actors"] == []
    assert audit["status"] == STATUS_DEGRADED
    assert audit["dropped_spans"] == ["clauses[0].actors[0]"]
    assert audit["repeated_occurrence_cases"] == 1
    assert audit["repeated_occurrence_unresolved"] == 1
    assert audit["tie_cases"] == 1
    assert audit["assignment_ambiguities"] == 1
    event = audit["resolution_events"][-1]
    assert event["outcome"] == "unresolved"
    assert event["reason"] == "equal_minimum_cost_assignment"


# ---------------------------------------------------------------------------
# T5 / two identical actors, two occurrences -> one-to-one
# ---------------------------------------------------------------------------


def test_t5_two_identical_actors_one_to_one_recovery():
    src = "the fund must be supervised and the fund must grant benefits."
    first = src.index("the fund")
    second = src.rindex("the fund")
    text = "the fund"
    r = make_record(
        [whole_clause(src, actors=[
            span(text, 1, 1 + len(text), "a01"),
            span(text, second - 2, second - 2 + len(text), "a02"),
        ])],
        src,
    )
    out, audit = repair(r, src)
    actors = out["clauses"][0]["actors"]
    assert [(a["id"], a["start"], a["end"]) for a in actors] == [
        ("a01", first, first + len(text)),
        ("a02", second, second + len(text)),
    ]
    assert audit["reanchored_repeated_exact"] == 2
    assert audit["one_to_one_assignment_cases"] == 1


# ---------------------------------------------------------------------------
# T6 / global assignment, not greedy nearest
# ---------------------------------------------------------------------------


def test_t6_global_assignment_beats_greedy_nearest():
    src = "the fund must be supervised and " + "z" * 20 + " the fund must grant benefits."
    first = src.index("the fund")
    second = src.rindex("the fund")
    text = "the fund"
    # Both predictions are closer to the first occurrence; greedy nearest would
    # send both there.  One-to-one forces the second prediction onto the second
    # occurrence, and that is the unique minimum-cost assignment.
    r = make_record(
        [whole_clause(src, actors=[
            span(text, 2, 2 + len(text), "a01"),
            span(text, 5, 5 + len(text), "a02"),
        ])],
        src,
    )
    out, audit = repair(r, src)
    actors = out["clauses"][0]["actors"]
    assert [(a["id"], a["start"]) for a in actors] == [("a01", first), ("a02", second)]
    assert audit["one_to_one_assignment_cases"] == 1
    assert audit["assignment_ambiguities"] == 0


# ---------------------------------------------------------------------------
# T7 / predictions > occurrences
# ---------------------------------------------------------------------------


def test_t7_more_predictions_than_occurrences_never_reuses_an_occurrence():
    src = "the fund must be supervised and " + "z" * 20 + " the fund must grant benefits."
    first = src.index("the fund")
    second = src.rindex("the fund")
    text = "the fund"
    middle = (first + second) // 2
    r = make_record(
        [whole_clause(src, actors=[
            span(text, 1, 1 + len(text), "a01"),
            span(text, middle, middle + len(text), "a02"),
            span(text, second - 1, second - 1 + len(text), "a03"),
        ])],
        src,
    )
    out, audit = repair(r, src)
    actors = out["clauses"][0]["actors"]
    assert [(a["id"], a["start"]) for a in actors] == [("a01", first), ("a03", second)]
    assert audit["dropped_spans"] == ["clauses[0].actors[1]"]
    assert audit["repeated_occurrence_recovered"] == 2
    assert audit["repeated_occurrence_unresolved"] == 1
    events = {e["path"]: e for e in audit["resolution_events"] if e["field"] == "actors"}
    assert events["clauses[0].actors[1]"]["reason"] == (
        "insufficient_free_occurrences_for_all_predictions"
    )


# ---------------------------------------------------------------------------
# T8 / actor_action_map stays consistent
# ---------------------------------------------------------------------------


def test_t8_recovered_actor_keeps_actor_action_edge():
    src = "the fund must pay and the fund must pay."
    second = src.rindex("the fund")
    text = "the fund"
    r = make_record(
        [whole_clause(
            src,
            actors=[span(text, second - 2, second - 2 + len(text), "a01")],
            actions=[span("must pay", 13, 21, "p01")],
            actor_action_map=[{"actor_id": "a01", "action_id": "p01"}],
        )],
        src,
    )
    out, audit = repair(r, src)
    assert out["clauses"][0]["actors"][0]["start"] == second
    assert out["clauses"][0]["actor_action_map"] == [{"actor_id": "a01", "action_id": "p01"}]
    assert audit["dropped_edges"] == []


def test_t8_unresolved_actor_still_drops_dangling_edge():
    src = "ab" + "x" * 8 + "ab"
    r = make_record(
        [whole_clause(
            src,
            actors=[span("ab", 5, 7, "a01")],
            actions=[span("xx", 2, 4, "p01")],
            actor_action_map=[{"actor_id": "a01", "action_id": "p01"}],
        )],
        src,
    )
    out, audit = repair(r, src)
    assert out["clauses"][0]["actors"] == []
    assert out["clauses"][0]["actor_action_map"] == []
    assert audit["dropped_edges"] == ["clauses[0].actor_action_map[0]"]


# ---------------------------------------------------------------------------
# T9 / the repair is general, not actor-specific
# ---------------------------------------------------------------------------


def test_t9_repeated_recovery_applies_to_all_fields():
    src = "the fund shall pay the fund shall pay."
    second = src.rindex("the fund")
    text = "the fund"
    off = second - 2
    r = make_record(
        [whole_clause(
            src,
            actions=[span(text, off, off + len(text), "p01")],
            conditions=[span(text, off, off + len(text), "q01")],
            constraints=[span(text, off, off + len(text), "c01")],
            exceptions=[span(text, off, off + len(text), "e01")],
            evidence=[span(text, off, off + len(text))],
        )],
        src,
    )
    out, audit = repair(r, src)
    clause = out["clauses"][0]
    for field in ("actions", "conditions", "constraints", "exceptions"):
        fixed = clause[field][0]
        assert (fixed["start"], fixed["end"]) == (second, second + len(text)), field
    ev = clause["modality"]["evidence"][0]
    assert (ev["start"], ev["end"]) == (second, second + len(text))
    assert audit["reanchored_repeated_exact"] == 5
    assert audit["repeated_occurrence_recovered"] == 5


# ---------------------------------------------------------------------------
# T10 / determinism
# ---------------------------------------------------------------------------


def test_t10_repeated_runs_are_identical():
    src = "the fund must be supervised and the fund must grant benefits."
    text = "the fund"
    second = src.rindex(text)
    r = make_record(
        [whole_clause(src, actors=[
            span(text, 1, 1 + len(text), "a01"),
            span(text, second - 2, second - 2 + len(text), "a02"),
        ])],
        src,
    )
    out1, audit1 = repair(copy.deepcopy(r), src)
    out2, audit2 = repair(copy.deepcopy(r), src)
    assert out1 == out2
    assert audit1 == audit2


# ---------------------------------------------------------------------------
# Legacy policy + no silent promotion
# ---------------------------------------------------------------------------


def test_legacy_policy_still_drops_repeated_occurrence():
    src = "the fund must be supervised and the fund must grant benefits."
    text = "the fund"
    second = src.rindex(text)
    r = make_record(
        [whole_clause(src, actors=[
            span(text, 1, 1 + len(text), "a01"),
            span(text, second - 2, second - 2 + len(text), "a02"),
        ])],
        src,
    )
    out, audit = canonicalize_record_coordinates(r, src, policy=POLICY_LEGACY)
    assert out["clauses"][0]["actors"] == []
    assert audit["dropped_spans"] == ["clauses[0].actors[0]", "clauses[0].actors[1]"]
    assert audit["reanchored_repeated_exact"] == 0


def test_default_policy_does_not_silently_promote_the_repair():
    src = "the fund must be supervised and the fund must grant benefits."
    text = "the fund"
    second = src.rindex(text)
    r = make_record(
        [whole_clause(src, actors=[
            span(text, 1, 1 + len(text), "a01"),
            span(text, second - 2, second - 2 + len(text), "a02"),
        ])],
        src,
    )
    assert DEFAULT_POLICY == POLICY_LEGACY
    default_out, default_audit = canonicalize_record_coordinates(r, src)
    legacy_out, legacy_audit = canonicalize_record_coordinates(r, src, policy=POLICY_LEGACY)
    assert default_out == legacy_out
    assert default_audit["status"] == legacy_audit["status"]
    assert default_audit["dropped_spans"] == legacy_audit["dropped_spans"]
    assert default_out["clauses"][0]["actors"] == []


def test_cost_metric_parameter_is_recorded_and_start_only_runs():
    src = "ab" + "x" * 8 + "ab"
    r = make_record([whole_clause(src, actors=[span("ab", 5, 7, "a01")])], src)
    out, audit = repair(r, src, cost_metric="abs_start_only")
    assert audit["cost_metric"] == "abs_start_only"
    assert out["clauses"][0]["actors"] == []  # still a tie under start-only
    with pytest.raises(Exception):
        canonicalize_record_coordinates(r, src, policy="nope")


# ---------------------------------------------------------------------------
# Pre-existing behaviour that must remain unchanged
# ---------------------------------------------------------------------------


def test_valid_record_is_untouched():
    r = make_record(
        [whole_clause(SRC, constraints=[span("in accordance with Section 11(1)", 52, 84, "c01", "x")])],
        SRC,
    )
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_UNCHANGED
    assert audit["reanchored_count"] == 0
    assert out == r


def test_off_by_one_clause_span_reanchors():
    r = make_record([whole_clause(SRC)], SRC)
    r["clauses"][0]["clause_span"] = {"text": SRC, "start": 1, "end": len(SRC) + 1}
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_REANCHORED
    assert out["clauses"][0]["clause_span"] == {"text": SRC, "start": 0, "end": len(SRC)}


def test_zero_occurrence_drops_span_and_degrades():
    r = make_record(
        [whole_clause(SRC, constraints=[span("nonexistent phrase here", 10, 30, "c01", "x")])],
        SRC,
    )
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_DEGRADED
    assert audit["dropped_spans"] == ["clauses[0].constraints[0]"]
    assert out["clauses"][0]["constraints"] == []


def test_non_integer_offsets_drop_span_and_degrades():
    bad = {"id": "c01", "text": "in accordance with Section 11(1)", "start": "52", "end": 84}
    r = make_record([whole_clause(SRC, constraints=[bad])], SRC)
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_DEGRADED
    assert audit["dropped_spans"] == ["clauses[0].constraints[0]"]
    assert out["clauses"][0]["constraints"] == []


def test_bad_clause_span_drops_clause_and_degrades():
    r = make_record([whole_clause("completely invented clause text")], SRC)
    r["clauses"][0]["clause_span"] = {"text": "completely invented clause text", "start": 0, "end": 30}
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_DEGRADED
    assert audit["dropped_clauses"] == [0]
    assert out["clauses"] == []


def test_missing_clauses_treated_as_empty():
    r = make_record([whole_clause(SRC)], SRC)
    del r["clauses"]
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_UNCHANGED
    assert out["clauses"] == []


def test_record_level_violations_still_fail_closed():
    r = make_record([whole_clause(SRC)], SRC)
    r["clauses"] = {"not": "a list"}
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_FAILED
    assert audit["failed_reasons"] == ["clauses_not_list"]
    assert out == r


def test_dangling_actor_action_edge_is_dropped_not_fatal():
    r = make_record(
        [whole_clause(
            SRC,
            actors=[span("The taxpayer", 0, 12, "a01", "taxpayer")],
            actions=[span("depreciate the acquisition costs", 19, 51, "p01")],
            actor_action_map=[
                {"actor_id": "a01", "action_id": "p01"},
                {"actor_id": "a01", "action_id": "p99"},
            ],
        )],
        SRC,
    )
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_DEGRADED
    assert audit["dropped_edges"] == ["clauses[0].actor_action_map[1]"]
    assert out["clauses"][0]["actor_action_map"] == [{"actor_id": "a01", "action_id": "p01"}]


def test_dangling_order_relation_is_dropped_not_fatal():
    r = make_record(
        [whole_clause(
            SRC,
            actions=[span("depreciate the acquisition costs", 19, 51, "p01")],
            order_relations=[{"before_action_id": "p01", "after_action_id": "p02",
                              "evidence": [{"text": "then", "start": 0, "end": 4}]}],
        )],
        SRC,
    )
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_DEGRADED
    assert audit["dropped_edges"] == ["clauses[0].order_relations[0]"]
    assert out["clauses"][0]["order_relations"] == []


def test_dangling_edge_with_null_actor_id_is_kept():
    r = make_record(
        [whole_clause(
            SRC,
            actions=[span("depreciate the acquisition costs", 19, 51, "p01")],
            actor_action_map=[{"actor_id": None, "action_id": "p01"}],
        )],
        SRC,
    )
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_UNCHANGED
    assert out["clauses"][0]["actor_action_map"] == [{"actor_id": None, "action_id": "p01"}]


def test_resolution_event_schema_is_complete():
    src = "the tax office shall pay and the tax office shall act."
    second = src.rindex("the tax office")
    text = "the tax office"
    r = make_record(
        [whole_clause(src, actors=[span(text, second - 2, second - 2 + len(text), "a01")])],
        src,
    )
    _out, audit = repair(r, src)
    event = next(e for e in audit["resolution_events"] if e["field"] == "actors")
    for key in (
        "path", "clause_index", "clause_id", "field", "span_index", "span_id",
        "text", "original_start", "original_end", "candidate_occurrences",
        "strategy", "chosen", "distance", "outcome", "reason", "cost_metric",
    ):
        assert key in event
    assert event["outcome"] == "reanchored_repeated_exact"
    assert event["candidate_occurrences"] == [
        {"start": 0, "end": len(text)},
        {"start": second, "end": second + len(text)},
    ]
    assert event["chosen"] == {"start": second, "end": second + len(text)}
    assert event["cost_metric"] == DEFAULT_COST_METRIC