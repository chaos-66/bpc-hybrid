from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/analyze_estg150_b0_b3b_typed_ownership_diagnostic_v1.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("b3b_typed_ownership_v1", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


B3B = _load_module()
LEXICON = B3B.load_lexicon_v2(ROOT)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _span(text: str, source: str, *, occurrence: int = 0, span_id: str = "s"):
    cursor = -1
    for _ in range(occurrence + 1):
        cursor = source.index(text, cursor + 1)
    return {
        "id": span_id,
        "text": text,
        "start": cursor,
        "end": cursor + len(text),
        "normalized": " ".join(text.casefold().split()),
    }


def _clause(
    source: str,
    *,
    conditions=None,
    constraints=None,
    actors=None,
    actions=None,
    modality=None,
    exceptions=None,
    clause_id: str = "c1",
):
    return {
        "clause_id": clause_id,
        "clause_span": {
            "id": f"{clause_id}.span",
            "text": source,
            "start": 0,
            "end": len(source),
            "normalized": " ".join(source.casefold().split()),
        },
        "actors": deepcopy(actors or []),
        "actions": deepcopy(actions or []),
        "modality": deepcopy(modality or []),
        "conditions": deepcopy(conditions or []),
        "constraints": deepcopy(constraints or []),
        "exceptions": deepcopy(exceptions or []),
        "actor_action_edges": [],
    }


def _apply(source: str, **kwargs):
    parent = _clause(source, **kwargs)
    candidate, events, stats = B3B.apply_typed_ownership_to_clause(
        parent, source, LEXICON
    )
    return parent, candidate, events, stats


@pytest.mark.parametrize(
    ("source", "marker", "expected_type"),
    [
        ("subject to approval, file", "subject to", "applicability_condition"),
        ("if approved, file", "if", "condition_subordinator"),
    ],
)
def test_constraint_moves_to_condition_for_typed_condition_evidence(
    source, marker, expected_type
) -> None:
    parent_span = _span(source, source)
    _parent, candidate, _events, stats = _apply(
        source, constraints=[parent_span]
    )
    hits, errors = B3B.collect_clause_typed_hits(source, 0, LEXICON)
    assert not errors
    assert any(hit.surface == marker and hit.scope_type == expected_type for hit in hits)
    assert candidate["constraints"] == []
    assert B3B._span_value_key(candidate["conditions"][0]) == B3B._span_value_key(
        parent_span
    )
    assert stats["constraint_to_condition_fired"] == 1
    assert stats["constraint_to_condition"] == 1


@pytest.mark.parametrize(
    ("source", "expected_type"),
    [
        ("file within 30 days", "temporal_limit"),
        ("file at least 3 reports", "quantitative_comparator"),
        ("file pursuant to section 1", "legal_reference"),
        ("file for the purpose of reporting", "purpose_scope"),
    ],
)
def test_condition_moves_to_constraint_for_strong_constraint_type(
    source, expected_type
) -> None:
    parent_span = _span(source, source)
    _parent, candidate, _events, stats = _apply(source, conditions=[parent_span])
    hits, errors = B3B.collect_clause_typed_hits(source, 0, LEXICON)
    assert not errors
    assert any(hit.scope_type == expected_type for hit in hits)
    assert candidate["conditions"] == []
    assert B3B._span_value_key(candidate["constraints"][0]) == B3B._span_value_key(
        parent_span
    )
    assert stats["condition_to_constraint_fired"] == 1
    assert stats["condition_to_constraint"] == 1


def test_dual_typed_evidence_keeps_parent_field() -> None:
    source = "if approved, file within 30 days"
    parent_span = _span("within 30 days", source)
    _parent, candidate, events, stats = _apply(source, conditions=[parent_span])
    assert B3B._span_value_key(candidate["conditions"][0]) == B3B._span_value_key(
        parent_span
    )
    assert candidate["constraints"] == []
    assert stats["ambiguous_parent_unchanged"] == 1
    assert events[0]["operation"] == "ambiguous_parent_unchanged"


def test_exception_evidence_keeps_parent_field() -> None:
    source = "unless waived, file within 30 days"
    parent_span = _span("within 30 days", source)
    _parent, candidate, _events, stats = _apply(source, conditions=[parent_span])
    assert B3B._span_value_key(candidate["conditions"][0]) == B3B._span_value_key(
        parent_span
    )
    assert candidate["constraints"] == []
    assert stats["exception_parent_unchanged"] == 1


def test_no_typed_evidence_keeps_parent_field() -> None:
    source = "ordinary reporting phrase"
    parent_span = _span(source, source)
    _parent, candidate, _events, stats = _apply(source, constraints=[parent_span])
    assert B3B._span_value_key(candidate["constraints"][0]) == B3B._span_value_key(
        parent_span
    )
    assert candidate["conditions"] == []
    assert stats["no_typed_evidence_parent_unchanged"] == 1


def test_target_exact_duplicate_deletes_only_source() -> None:
    source = "subject to approval"
    source_span = _span(source, source, span_id="source")
    target_span = _span(source, source, span_id="target")
    _parent, candidate, events, stats = _apply(
        source, constraints=[source_span], conditions=[target_span]
    )
    assert candidate["constraints"] == []
    assert len(candidate["conditions"]) == 1
    assert stats["target_exact_duplicate"] == 1
    assert events[-1]["operation"] == "target_duplicate_suppressed"


def test_target_normalized_duplicate_deletes_only_source() -> None:
    source = "subject to approval; subject to approval"
    source_span = _span("subject to approval", source, occurrence=0, span_id="source")
    target_span = _span("subject to approval", source, occurrence=1, span_id="target")
    _parent, candidate, _events, stats = _apply(
        source, constraints=[source_span], conditions=[target_span]
    )
    assert candidate["constraints"] == []
    assert len(candidate["conditions"]) == 1
    assert candidate["conditions"][0]["start"] == target_span["start"]
    assert stats["target_normalized_duplicate"] == 1


def test_target_overlap_equivalent_deletes_only_source() -> None:
    source = "subject to approval"
    source_span = _span(source, source, span_id="source")
    target_span = _span("approval", source, span_id="target")
    _parent, candidate, _events, stats = _apply(
        source, constraints=[source_span], conditions=[target_span]
    )
    assert candidate["constraints"] == []
    assert len(candidate["conditions"]) == 1
    assert candidate["conditions"][0]["text"] == "approval"
    assert stats["target_overlap_equivalent"] == 1


def test_target_capacity_fail_closed_keeps_parent_field() -> None:
    source = "a b c d e f subject to approval"
    source_span = _span("subject to approval", source)
    targets = [_span(token, source, span_id=f"t{i}") for i, token in enumerate("abcdef")]
    _parent, candidate, events, stats = _apply(
        source, constraints=[source_span], conditions=targets
    )
    assert len(candidate["conditions"]) == 6
    assert B3B._span_value_key(candidate["constraints"][0]) == B3B._span_value_key(
        source_span
    )
    assert stats["target_capacity_fail_closed"] == 1
    assert events[-1]["operation"] == "target_capacity_fail_closed"


def test_move_preserves_span_text_offsets_and_normalized() -> None:
    source = "file within 30 days"
    parent_span = _span(source, source)
    _parent, candidate, _events, _stats = _apply(source, conditions=[parent_span])
    moved = candidate["constraints"][0]
    for key in ("text", "start", "end", "normalized"):
        assert moved[key] == parent_span[key]


def test_non_target_fields_and_modality_remain_exact() -> None:
    source = "file within 30 days"
    actor = _span("file", source, span_id="actor")
    action = _span("file", source, span_id="action")
    exception = _span("30 days", source, span_id="exception")
    modality = {"type": "obligation", "strength": "shall"}
    parent, candidate, _events, _stats = _apply(
        source,
        conditions=[_span(source, source)],
        actors=[actor],
        actions=[action],
        exceptions=[exception],
        modality=modality,
    )
    for field in (
        "actors",
        "actions",
        "exceptions",
        "modality",
        "actor_action_edges",
        "clause_span",
    ):
        assert candidate[field] == parent[field]


def test_attempt_wrapper_preserves_segmentation_and_adds_no_raw_span() -> None:
    source = "file within 30 days"
    clause = _clause(source, conditions=[_span(source, source)])
    attempts = [{"sample_id": "opaque-test", "record": {"source_text": source, "clauses": [clause]}}]
    candidate, ownership = B3B.apply_typed_ownership_attempts(attempts, LEXICON)
    purity = B3B._assert_route_purity(attempts, candidate)
    assert len(candidate[0]["record"]["clauses"]) == 1
    assert purity["span_boundary_changes"] == 0
    assert purity["new_raw_spans"] == 0
    assert purity["other_fields_exact"] is True
    assert ownership["changed_unique_spans"] == 1
    assert ownership["counts"]["target_capacity_fail_closed"] == 0
    assert ownership["counts"]["target_normalized_duplicate"] == 0
    assert ownership["counts"]["constraint_to_condition"] == 0


def test_production_shaped_rule_has_no_sample_or_gold_branch() -> None:
    signature = inspect.signature(B3B.apply_typed_ownership_to_clause)
    source = inspect.getsource(B3B.apply_typed_ownership_to_clause).casefold()
    assert "sample_id" not in signature.parameters
    assert "sample_id" not in source
    assert "build_canonical_gold" not in source
    assert "evaluate_stage2" not in source


def test_malformed_span_fails_closed() -> None:
    source = "file within 30 days"
    malformed = _span(source, source)
    malformed["text"] = "wrong source slice"
    parent, candidate, _events, stats = _apply(source, conditions=[malformed])
    assert B3B._span_value_key(candidate["conditions"][0]) == B3B._span_value_key(
        parent["conditions"][0]
    )
    for field in candidate:
        if field != "conditions":
            assert candidate[field] == parent[field]
    assert stats["span_source_slice_mismatch"] == 1


def test_malformed_typed_evidence_fails_closed(monkeypatch) -> None:
    source = "file within 30 days"
    parent = _clause(source, conditions=[_span(source, source)])
    monkeypatch.setattr(
        B3B,
        "collect_clause_typed_hits",
        lambda *_args, **_kwargs: ([], ["typed_scope_classification_error"]),
    )
    candidate, events, stats = B3B.apply_typed_ownership_to_clause(
        parent, source, LEXICON
    )
    assert candidate == parent
    assert events == []
    assert stats == {"malformed_evidence": 1}


def test_windows_utf8_cli_help() -> None:
    environment = dict(os.environ)
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--runtime-home" in completed.stdout


def test_all_fixed_bindings_still_match() -> None:
    paths = {
        "parent_manifest": B3B.PARENT_MANIFEST,
        "scope_resolver": B3B.SCOPE_RESOLVER,
        "lexicon_manifest": B3B.LEXICON_MANIFEST,
        "evaluator": B3B.EVALUATOR,
        "b3a_v2": B3B.B3A_V2,
        "active_registry": B3B.ACTIVE_REGISTRY,
        "tregex_registry": B3B.TREGEX_REGISTRY,
        "production_bridge": B3B.PRODUCTION_BRIDGE,
    }
    assert {key: _sha256(path) for key, path in paths.items()} == B3B.EXPECTED_HASHES


def test_parent_attempts_binding_is_an_array() -> None:
    attempts = json.loads(B3B.PARENT_ATTEMPTS.read_text(encoding="utf-8"))
    assert isinstance(attempts, list)
    assert len(attempts) == 150


def test_rule_spec_is_fixed_and_excludes_sample_logic() -> None:
    encoded = json.dumps(B3B.RULE_SPEC, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(encoded.encode("utf-8")).hexdigest() == B3B.RULE_SPEC_SHA256
    assert B3B.RULE_SPEC["sample_specific_logic"] is False
    assert B3B.TARGET_CAPACITY == 6


def test_production_module_has_no_gold_or_evaluator_import_if_instantiated() -> None:
    production = ROOT / "src/bpc_hybrid/b0_v10/typed_ownership_b3b.py"
    if not production.exists():
        return
    source = production.read_text(encoding="utf-8").casefold()
    assert "gold" not in source
    assert "evaluator" not in source


def test_not_instantiated_diagnostic_is_self_consistent() -> None:
    output = ROOT / "outputs/development/s27_estg150_b0_b3b_typed_ownership_diagnostic_v1"
    diagnostic = json.loads((output / "diagnostic.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert diagnostic["decision"] == "not_instantiated"
    assert diagnostic["all_instantiation_gates_passed"] is False
    assert diagnostic["candidate_all150_run"] is False
    assert diagnostic["production_candidate_created"] is False
    assert diagnostic["ownership"]["counts"]["target_capacity_fail_closed"] == 0
    assert diagnostic["ownership"]["counts"]["target_normalized_duplicate"] == 0
    assert manifest["artifact"]["sha256"] == _sha256(output / "diagnostic.json")
    assert manifest["artifact"]["bytes"] == (output / "diagnostic.json").stat().st_size


def test_not_instantiated_created_no_production_candidate() -> None:
    forbidden = (
        ROOT / "src/bpc_hybrid/b0_v10/typed_ownership_b3b.py",
        ROOT / "src/bpc_hybrid/estg150_b0_development_b3b.py",
        ROOT / "scripts/run_estg150_b0_enhanced_b3b_development.py",
        ROOT / "configs/models/estg150_b0_b3b_preregistration_v1.json",
        ROOT / "configs/models/estg150_b0_enhanced_s27_b3b.json",
        ROOT / "tests/test_b0_b3b_typed_ownership.py",
        ROOT / "outputs/development/s27_estg150_b0_enhanced_b3b",
    )
    assert all(not path.exists() for path in forbidden)
