from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/analyze_estg150_b0_b3a_constraint_tregex_correction_v2.py"
JAVA = ROOT / "tools/corenlp/SunPhraseRuleDiagnosticB3aV2.java"
OUTPUT = ROOT / "outputs/development/s27_estg150_b0_b3a_constraint_tregex_diagnostic_v2"
STATUS = ROOT / "outputs/reports/s27_estg150_b0_b3a_status_correction_v2.manifest.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("b3a_correction_v2", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


B3A = _load_module()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _span(start: int, end: int, text: str) -> dict[str, object]:
    return {"start": start, "end": end, "text": text}


def _clause(
    text: str,
    constraints: list[dict[str, object]],
    *,
    start: int = 0,
    end: int | None = None,
) -> dict[str, object]:
    end = len(text) if end is None else end
    return {
        "clause_span": _span(start, end, text),
        "actors": [],
        "actions": [],
        "modality": [],
        "conditions": [],
        "constraints": constraints,
        "exceptions": [],
    }


def _record(sample_id: str, text: str, constraints: list[dict[str, object]]):
    return {
        "sample_id": sample_id,
        "source_text": text,
        "clauses": [_clause(text, constraints)],
    }


def test_predicted_clause_identity_includes_sample_id() -> None:
    assert B3A.predicted_clause_key("sample-a", 0) != B3A.predicted_clause_key(
        "sample-b", 0
    )


def test_duplicate_clause_text_does_not_merge_across_records() -> None:
    text = "within two days"
    keys = {
        B3A.predicted_clause_key("sample-a", 0),
        B3A.predicted_clause_key("sample-b", 0),
    }
    assert len(keys) == 2
    assert text == text


def test_gold_span_identity_includes_sample_and_clause() -> None:
    span = _span(0, 6, "within")
    assert B3A.gold_span_key("a", 0, "constraint", span) != B3A.gold_span_key(
        "b", 0, "constraint", span
    )
    assert B3A.gold_span_key("a", 0, "constraint", span) != B3A.gold_span_key(
        "a", 1, "constraint", span
    )


def test_duplicate_gold_text_does_not_merge_across_records() -> None:
    span_a = _span(0, 15, "within two days")
    span_b = _span(0, 15, "within two days")
    keys = {
        B3A.gold_span_key("sample-a", 0, "constraint", span_a),
        B3A.gold_span_key("sample-b", 0, "constraint", span_b),
    }
    assert len(keys) == 2


def test_predicted_span_identity_includes_clause_index() -> None:
    span = _span(0, 6, "within")
    assert B3A.predicted_span_key("a", 0, "constraint", span) != (
        B3A.predicted_span_key("a", 1, "constraint", span)
    )


def test_opaque_trace_hash_uses_full_instance_key() -> None:
    one = B3A.opaque_instance_hash(("sample-a", 0, "constraint", 0, 6))
    two = B3A.opaque_instance_hash(("sample-b", 0, "constraint", 0, 6))
    assert one != two
    assert len(one) == 64
    assert "sample-a" not in one


def test_same_text_with_different_gold_presence_is_not_cross_contaminated() -> None:
    text = "within two days"
    gold = [
        _record("sample-a", text, [_span(0, len(text), text)]),
        _record("sample-b", text, []),
    ]
    attempts = [
        {"sample_id": "sample-a", "record": _record("sample-a", text, [_span(0, len(text), text)])},
        {"sample_id": "sample-b", "record": _record("sample-b", text, [_span(0, len(text), text)])},
    ]
    buckets = B3A.parent_constraint_error_buckets(
        gold, attempts, anchor_surfaces=["within"]
    )
    assert buckets["fn"]["primary_bucket_total"] == 0
    assert buckets["fp"]["primary_bucket_total"] == 1
    assert buckets["fp"]["primary_buckets"] == {
        "matched_clause_no_gold_constraint": 1
    }


def test_fp_is_counted_inside_clause_that_also_has_gold_constraint() -> None:
    text = "within two days and after approval"
    gold_span = _span(0, 15, "within two days")
    extra = _span(20, 34, "after approval")
    gold = [_record("sample-a", text, [gold_span])]
    attempts = [
        {
            "sample_id": "sample-a",
            "record": _record("sample-a", text, [gold_span, extra]),
        }
    ]
    buckets = B3A.parent_constraint_error_buckets(
        gold, attempts, anchor_surfaces=["within", "after"]
    )
    assert buckets["fp"]["primary_bucket_total"] == 1
    assert buckets["fp"]["facets"].get("no_gold_constraint", 0) == 0


@pytest.mark.parametrize(
    ("candidate", "parent", "expected"),
    [
        (_span(0, 6, "Within"), _span(0, 6, "Within"), "exact_duplicate"),
        (_span(7, 13, "within"), _span(0, 6, "WITHIN"), "normalized_duplicate"),
        (_span(0, 15, "within two days"), _span(0, 6, "within"), "containment"),
        (_span(4, 11, "in two "), _span(0, 6, "within"), "partial_overlap"),
        (_span(20, 25, "later"), _span(0, 6, "within"), "genuinely_new"),
    ],
)
def test_parent_relation_classes(candidate, parent, expected) -> None:
    assert B3A.classify_parent_relation(candidate, [parent]) == expected


def test_union_real_dedup_merges_multi_pattern_same_span() -> None:
    accepted = [
        {**_span(0, 15, "within two days"), "pattern_id": "p1"},
        {**_span(0, 15, "within two days"), "pattern_id": "p2"},
    ]
    rows = B3A.dedupe_candidate_spans_like_v10(accepted)
    assert len(rows) == 1
    assert rows[0]["pattern_ids"] == ["p1", "p2"]
    assert rows[0]["raw_contributors"] == 2


def test_union_overlap_dedup_is_not_a_simple_pattern_sum() -> None:
    accepted = [
        {**_span(0, 15, "within two days"), "pattern_id": "p1"},
        {**_span(7, 15, "two days"), "pattern_id": "p2"},
    ]
    assert len(B3A.dedupe_candidate_spans_like_v10(accepted)) == 1


def test_add_only_composition_preserves_parent_and_adds_only_new() -> None:
    parent = [_span(0, 6, "within")]
    candidates = [
        {**_span(0, 6, "within"), "pattern_id": "p1"},
        {**_span(20, 25, "later"), "pattern_id": "p2"},
    ]
    combined, final, relations = B3A.compose_add_only_constraints(parent, candidates)
    assert combined[0] == parent[0]
    assert len(combined) == 2
    assert len(final) == 2
    assert relations["exact_duplicate"] == 1
    assert relations["genuinely_new"] == 1


def test_one_to_one_matching_does_not_recover_same_gold_twice() -> None:
    gold = [_span(0, 10, "same gold")]
    predicted = [_span(0, 5, "same"), _span(2, 10, "me gold")]
    pairs, unmatched_gold, unmatched_predicted = B3A.greedy_span_matches(gold, predicted)
    assert len(pairs) == 1
    assert not unmatched_gold
    assert len(unmatched_predicted) == 1


def test_bridge_parser_rejects_malformed_output() -> None:
    patterns = [{"pattern_id": "p", "tregex": "NP"}]
    with pytest.raises(B3A.B3aCorrectionError):
        B3A.parse_candidate_bridge_output(
            "COMPILE\t0\tp\ttrue\tok\n", patterns=patterns, expected_tree_count=1
        )


def test_bridge_parser_requires_compile_coverage() -> None:
    patterns = [
        {"pattern_id": "p1", "tregex": "NP"},
        {"pattern_id": "p2", "tregex": "PP"},
    ]
    stdout = "COMPILE\t0\tp1\ttrue\tok\nSUMMARY\t1\t2\t1\t0\n"
    with pytest.raises(B3A.B3aCorrectionError, match="coverage"):
        B3A.parse_candidate_bridge_output(
            stdout, patterns=patterns, expected_tree_count=1
        )


def test_six_frozen_patterns_are_loaded_verbatim_and_in_order() -> None:
    v1 = json.loads(B3A.V1_DIAGNOSTIC.read_text(encoding="utf-8"))
    patterns = B3A.load_frozen_patterns(v1)
    assert tuple(row["pattern_id"] for row in patterns) == B3A.EXPECTED_PATTERN_IDS
    assert [row["tregex"] for row in patterns] == [
        row["tregex"] for row in v1["candidate_patterns_evaluated"]
    ]


def test_diagnostic_java_is_isolated_and_has_no_tsurgeon() -> None:
    source = JAVA.read_text(encoding="utf-8")
    assert "class SunPhraseRuleDiagnosticB3aV2" in source
    assert "Tsurgeon" not in source
    assert "SunPhraseRuleBatchBridgeMulti" not in source


def test_production_sources_do_not_reference_diagnostic_bridge() -> None:
    needle = "SunPhraseRuleDiagnosticB3aV2"
    for path in (ROOT / "src").rglob("*.py"):
        assert needle not in path.read_text(encoding="utf-8")
    for path in (ROOT / "configs").rglob("*.json"):
        assert needle not in path.read_text(encoding="utf-8")
    assert needle not in B3A.PRODUCTION_BRIDGE.read_text(encoding="utf-8")


def test_protected_production_bridge_hash_is_fixed() -> None:
    assert _sha256(B3A.PRODUCTION_BRIDGE) == B3A.EXPECTED_HASHES["production_bridge"]


def test_v10a_parent_hash_is_fixed() -> None:
    assert _sha256(B3A.PARENT_MANIFEST) == B3A.EXPECTED_HASHES["parent_manifest"]


def test_cli_help_succeeds_under_windows_utf8_mode() -> None:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--runtime-home" in completed.stdout


def test_diagnostic_artifact_has_required_live_compile_and_offset_traces() -> None:
    diagnostic = json.loads((OUTPUT / "diagnostic.json").read_text(encoding="utf-8"))
    compile_rows = diagnostic["pattern_results"]
    assert len(compile_rows) == 6
    assert all(row["live_compile"] for row in compile_rows)
    runtime = diagnostic["live_runtime"]
    assert runtime["offset_validation_failures"] == 0
    assert runtime["offset_validated_match_count"] == runtime["candidate_raw_match_count"]


def test_diagnostic_artifact_reports_exclusive_176_fn_and_209_fp() -> None:
    diagnostic = json.loads((OUTPUT / "diagnostic.json").read_text(encoding="utf-8"))
    buckets = diagnostic["parent_error_analysis"]
    assert buckets["fn"]["primary_bucket_total"] == 176
    assert buckets["fp"]["primary_bucket_total"] == 209
    assert sum(buckets["fn"]["primary_buckets"].values()) == 176
    assert sum(buckets["fp"]["primary_buckets"].values()) == 209


def test_facet_buckets_are_explicitly_nonexclusive() -> None:
    diagnostic = json.loads((OUTPUT / "diagnostic.json").read_text(encoding="utf-8"))
    buckets = diagnostic["parent_error_analysis"]
    assert buckets["fn"]["facet_counts_are_nonexclusive"] is True
    assert buckets["fp"]["facet_counts_are_nonexclusive"] is True


def test_parent_table8_is_reproduced_exactly_before_delta() -> None:
    diagnostic = json.loads((OUTPUT / "diagnostic.json").read_text(encoding="utf-8"))
    assert diagnostic["baseline_reconstruction"]["frozen_parent_table8_exact"] is True
    assert diagnostic["table8_opportunity"]["parent_constraint"] == {
        "f1": pytest.approx(0.39560439560439564),
        "fn": 176,
        "fp": 209,
        "gold": 302,
        "precision": pytest.approx(0.3761194029850746),
        "pred": 335,
        "recall": pytest.approx(0.41721854304635764),
        "tp": 126,
    }


def test_status_correction_is_inconclusive_and_not_instantiated() -> None:
    report = json.loads(STATUS.read_text(encoding="utf-8"))
    assert report["corrected_v1_status"] == B3A.CORRECTED_V1_STATUS
    assert report["safety"]["production_candidate_created"] is False
    assert report["safety"]["candidate_all150_run"] is False
    assert report["safety"]["b3b_started"] is False


def test_no_production_candidate_or_all150_artifact_was_created() -> None:
    forbidden = (
        "*b3a*candidate*",
        "*b3a*all_150*",
        "*b3a*all150*",
        "*b3a*prereg*",
    )
    hits: list[Path] = []
    for root in (ROOT / "configs/models", ROOT / "outputs", ROOT / "scripts"):
        if root.exists():
            for pattern in forbidden:
                hits.extend(root.rglob(pattern))
    assert not hits


def test_persisted_sample_traces_are_opaque_hashes_only() -> None:
    diagnostic = json.loads((OUTPUT / "diagnostic.json").read_text(encoding="utf-8"))
    serialized = json.dumps(diagnostic, ensure_ascii=False)
    for section in ("fn", "fp"):
        hashes = diagnostic["parent_error_analysis"][section][
            "opaque_instance_hashes"
        ]
        assert hashes
        assert all(len(value) == 64 for value in hashes)
    assert '"sample_id":' not in serialized
    assert diagnostic["identity_contract"]["sample_id_allowlist_persisted"] is False
    assert '"clause_text_hash"' not in serialized
    assert '"gold_text_hash"' not in serialized
