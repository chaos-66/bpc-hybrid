from __future__ import annotations

from bpc_hybrid.estg150_b0_development_v2 import (
    align_german_to_english_units,
    english_marker_modality,
    parse_bridge_output_multi,
    plan_clause_units,
    _dedupe_spans,
    _trim_actor_span,
)


def test_record_label_replication_is_not_used_by_clause_routing() -> None:
    """Multi-clause English units get distinct DE units when available."""
    de = "Satz eins. Satz zwei. Satz drei."
    en = ["one.", "two.", "three."]
    aligned = align_german_to_english_units(de, en)
    assert len(aligned) == 3
    assert len(set(aligned)) == 3
    assert aligned[0] != aligned[1]


def test_english_marker_priority_prohibition_over_permission() -> None:
    assert english_marker_modality("The employee may not sell the allowance.") == "prohibition"
    assert english_marker_modality("The taxpayer shall file the return.") == "obligation"
    assert english_marker_modality("It may cover a shorter period.") == "permission"
    assert english_marker_modality("Income means net profit.") == "definition"


def test_multi_match_bridge_parser_keeps_all_field_matches() -> None:
    cases, summary = parse_bridge_output_multi(
        "MATCH\t0\taction\t0\t2\tfile claim\t0\tfalse\n"
        "MATCH\t0\taction\t3\t5\trecord decision\t1\tfalse\n"
        "MATCH\t0\tconstraint\t6\t8\twithin 30 days\t0\ttrue\n"
        "MISS\t0\texception\n"
        "TERMINAL_TREE_REMOVALS\t0\n"
        "SUMMARY\t1\t12\t3\t1\n"
    )
    assert len(cases) == 1
    assert len(cases[0]["fields"]["action"]) == 2
    assert cases[0]["fields"]["constraint"][0]["text"] == "within 30 days"
    assert cases[0]["fields"]["exception"] == []
    assert summary["match_count"] == 3
    assert summary["surgery_count"] == 1


def test_actor_trim_drops_pronouns_and_limits_width() -> None:
    src = "It"
    assert _trim_actor_span(src, {"id": "a1", "text": src, "start": 0, "end": 2, "normalized": "it"}) is None
    wide_text = "the very long administrative unit of the federal ministry for finance and research office"
    wide = {
        "id": "a2",
        "text": wide_text,
        "start": 0,
        "end": len(wide_text),
        "normalized": "x",
    }
    trimmed = _trim_actor_span(wide_text, wide)
    assert trimmed is not None
    assert len(trimmed["text"].split()) <= 12


def test_dedupe_prefers_longer_overlapping_span() -> None:
    spans = [
        {"id": "1", "text": "within 30", "start": 10, "end": 19, "normalized": "within 30"},
        {"id": "2", "text": "within 30 days", "start": 10, "end": 24, "normalized": "within 30 days"},
        {"id": "3", "text": "the fund", "start": 0, "end": 8, "normalized": "the fund"},
    ]
    out = _dedupe_spans(spans)
    assert len(out) == 2
    assert any(s["text"] == "within 30 days" for s in out)


def test_plan_clause_units_merges_list_fragments() -> None:
    source = "It may cover a shorter period if 1. a business is opened or closed."
    # synthetic CoreNLP-like annotation with two sentences
    annotation = {
        "sentences": [
            {
                "tokens": [
                    {"characterOffsetBegin": 0, "characterOffsetEnd": 2, "originalText": "It"},
                    {"characterOffsetBegin": 33, "characterOffsetEnd": 36, "originalText": "if"},
                ]
            },
            {
                "tokens": [
                    {"characterOffsetBegin": 37, "characterOffsetEnd": 39, "originalText": "1."},
                    {"characterOffsetBegin": 60, "characterOffsetEnd": 66, "originalText": "closed"},
                ]
            },
        ]
    }
    # Fix offsets to match source
    annotation = {
        "sentences": [
            {
                "tokens": [
                    {"characterOffsetBegin": 0, "characterOffsetEnd": 2},
                    {"characterOffsetBegin": 32, "characterOffsetEnd": 34},
                ]
            },
            {
                "tokens": [
                    {"characterOffsetBegin": 35, "characterOffsetEnd": 37},
                    {"characterOffsetBegin": 64, "characterOffsetEnd": 66},
                ]
            },
        ]
    }
    units = plan_clause_units(annotation, source)
    assert len(units) == 1
    assert units[0]["sentence_indexes"] == [0, 1]
