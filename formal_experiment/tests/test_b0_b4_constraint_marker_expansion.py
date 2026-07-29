from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

from bpc_hybrid.estg150_b0_development_b4 import (  # noqa: E402
    ALLOWED_SCOPE_TESTS,
    FORBIDDEN_BROAD_SURFACES,
    METHOD_VARIANT,
    _validate_extension_document,
    load_lexicon_b4,
    new_marker_surfaces,
)
from bpc_hybrid.sun_style.lexicon_v2_runtime import (  # noqa: E402
    LexiconV2Error,
    load_lexicon_v2,
    match_field_markers,
    sha256_file,
)


EXTENSION = ROOT / "resources/lexicon/constraint_markers_en_v3_b4.json"
SOURCES = ROOT / "resources/lexicon/public_marker_sources_en_v3_b4.json"
MANIFEST = ROOT / "resources/lexicon/public_marker_lexicon_en_v3_b4.manifest.json"
CONFIG = ROOT / "configs/models/estg150_b0_enhanced_s27_b4.json"
RUNNER = ROOT / "scripts/run_estg150_b0_enhanced_b4_development.py"
MODULE = ROOT / "src/bpc_hybrid/estg150_b0_development_b4.py"


def _doc(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validation_inputs() -> tuple[dict, set[str], set[str]]:
    extension = _doc(EXTENSION)
    parent = load_lexicon_v2(ROOT)
    parent_surfaces = {entry.normalized for entry in parent.entries_by_field["constraint"]}
    source_ids = {source["source_id"] for source in _doc(SOURCES)["sources"]}
    return extension, parent_surfaces, source_ids


def test_b4_loads_exactly_25_new_active_constraint_markers() -> None:
    parent = load_lexicon_v2(ROOT)
    candidate = load_lexicon_b4(ROOT)
    assert candidate.lexicon_id == "public_marker_lexicon_en_v3_b4"
    assert len(new_marker_surfaces(ROOT)) == 25
    assert candidate.active_counts["constraint"] == parent.active_counts["constraint"] + 25 == 70
    for field in ("modality", "condition", "exception", "actor"):
        assert candidate.entries_by_field[field] == parent.entries_by_field[field]
        assert candidate.active_counts[field] == parent.active_counts[field]
        assert candidate.category_file_sha256[field] == parent.category_file_sha256[field]
    assert candidate.modality_patterns == parent.modality_patterns
    assert candidate.actor_surfaces == parent.actor_surfaces


def test_b4_entries_have_only_allowed_types_evidence_and_literal_safety() -> None:
    extension, parent_surfaces, source_ids = _validation_inputs()
    validated = _validate_extension_document(
        extension,
        parent_surfaces=parent_surfaces,
        source_ids=source_ids,
    )
    assert len(validated) == 25
    normalized = [row["normalized"] for row in validated]
    assert len(normalized) == len(set(normalized))
    assert not set(normalized) & parent_surfaces
    for row in validated:
        assert row["activation"] is True
        assert row["scope_test"] in ALLOWED_SCOPE_TESTS
        assert row["surface"] not in FORBIDDEN_BROAD_SURFACES
        assert len(row["synthetic_positive"]) >= 2
        assert len(row["synthetic_negative"]) >= 2
        assert "regex" not in row
        assert "sample_id" not in row
        assert "gold" not in row
        assert "fn" not in row


def test_each_b4_literal_matches_positives_and_rejects_negatives() -> None:
    for row in _doc(EXTENSION)["entries"]:
        pattern = re.compile(rf"\b{re.escape(row['surface'])}\b", re.IGNORECASE)
        assert all(pattern.search(text) for text in row["synthetic_positive"])
        assert all(pattern.search(text) is None for text in row["synthetic_negative"])


def test_b4_runtime_invokes_only_constraint_for_new_surfaces() -> None:
    runtime = load_lexicon_b4(ROOT)
    for row in _doc(EXTENSION)["entries"]:
        text = row["synthetic_positive"][0]
        constraint_surfaces = {hit["surface"] for hit in match_field_markers(text, "constraint", runtime)}
        assert row["surface"] in constraint_surfaces
        assert row["surface"] not in {hit["surface"] for hit in match_field_markers(text, "condition", runtime)}
        assert row["surface"] not in {hit["surface"] for hit in match_field_markers(text, "exception", runtime)}


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda doc: doc["entries"].__setitem__(0, {**doc["entries"][0], "activation": False}), "explicitly active"),
        (lambda doc: doc["entries"][0].__setitem__("scope_test", "condition_subordinator"), "scope type"),
        (lambda doc: doc["entries"][0].__setitem__("surface", "in"), "broad preposition"),
        (lambda doc: doc["entries"][0].__setitem__("normalized", "wrong"), "normalized"),
        (lambda doc: doc["entries"][0].__setitem__("source_ids", ["unknown"]), "source binding"),
    ],
)
def test_b4_malformed_resources_fail_closed(mutation, message: str) -> None:
    extension, parent_surfaces, source_ids = _validation_inputs()
    broken = copy.deepcopy(extension)
    mutation(broken)
    with pytest.raises(LexiconV2Error, match=message):
        _validate_extension_document(
            broken,
            parent_surfaces=parent_surfaces,
            source_ids=source_ids,
        )


def test_b4_source_snapshot_is_unlabeled_and_has_no_row_level_leakage() -> None:
    sources = _doc(SOURCES)
    policy = sources["source_policy"]
    assert policy["network_called"] is False
    assert policy["llm_api_called"] is False
    assert policy["gold_constraint_fields_read"] is False
    assert policy["false_negative_or_error_outcome_used"] is False
    assert policy["sample_id_recorded"] is False
    assert policy["text_snippet_recorded"] is False
    assert len(sources["sources"]) == 2
    observed = sources["sources"][1]
    assert observed["visible_field"] == "approved_text_en_only"
    assert observed["nonempty_text_count"] == 150
    assert len(observed["selected_surface_occurrence_counts"]) == 20
    assert all(count >= 1 for count in observed["selected_surface_occurrence_counts"].values())


def test_b4_manifest_and_fixed_parent_components_are_hash_bound() -> None:
    manifest = _doc(MANIFEST)
    assert manifest["constraint_extension"]["sha256"] == sha256_file(EXTENSION)
    assert manifest["source_snapshot"]["sha256"] == sha256_file(SOURCES)
    expected = {
        "src/bpc_hybrid/b0_v10/scope.py": "3c13d2d73d49476cd3449f50775c6b4b63ac68f5baa2f95a4b564e5ca8b30887",
        "src/bpc_hybrid/b0_v10/modality.py": "6dd2c74bbd5894353b921ff2f29506a950e6e6b2453b426ee451a042c0fc1246",
        "resources/corenlp/sun_phrase_patterns_v3_enhanced.json": "f49bad50fb6236137f1208aeef572d2a78c789726363897c637dc464c780e142",
        "tools/corenlp/SunPhraseRuleBatchBridgeMulti.java": "1a084befaf1a863889a26b58c5a049f2df846834e26c5643fe5a535c5c13f2a3",
        "outputs/development/s27_estg150_b0_enhanced_v10a/manifest.json": "88070fab4da3f7c708f055f6bc391b78cc888761c3d6fe117d17673c2c382315",
        "configs/stage2_evaluator_s210_v3.json": "28ce332564c5d10da08dea515aefe31cc2aacd91b6c6877aa1bfebe44f39ae7f",
    }
    for relative, digest in expected.items():
        assert sha256_file(ROOT / relative) == digest


def test_b4_config_runner_and_production_module_hold_scope() -> None:
    config = _doc(CONFIG)
    assert config["run_id"] == "s27_estg150_b0_enhanced_b4"
    assert config["method"]["method_variant"] == METHOD_VARIANT
    assert config["claim_scope"] == "development"
    assert config["method"]["paper_faithful_b0"] is False
    assert config["method"]["single_candidate"] is True
    assert config["method"]["new_active_marker_count"] == 25
    assert config["output"]["no_overwrite"] is True
    assert config["safety"]["active_registry_modified"] is False
    module_text = MODULE.read_text(encoding="utf-8")
    runner_text = RUNNER.read_text(encoding="utf-8")
    assert "run_b0_batch_b4" in module_text
    assert "run_corenlp_batch_v10" in module_text
    assert "build_canonical_record_v10" in module_text
    assert "placeholder_classifier_count" in module_text
    assert "refusing to overwrite" in runner_text
    assert "evaluation_all150.json" in runner_text
    assert "test_dataset" not in runner_text.casefold()
    assert "active_registry_modified\": True" not in runner_text


def test_b4_utf8_resources_round_trip() -> None:
    for path in (EXTENSION, SOURCES, MANIFEST, CONFIG):
        raw = path.read_bytes()
        assert raw.decode("utf-8").encode("utf-8") == raw

