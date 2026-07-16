"""Offline S2.3 public marker lexicon reconstruction tests."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from bpc_hybrid.sun_style.marker_lexicon import MarkerLexicon
from bpc_hybrid.sun_style.public_marker_lexicon import (
    CATEGORY_FILES,
    EXPECTED_CATEGORY_COUNTS,
    EXTENSIONS_REL,
    MANIFEST_REL,
    PUBLIC_MARKER_EXPECTATIONS,
    SOURCE_REL,
    PublicMarkerLexiconError,
    build_artifact_documents,
    expected_artifact_bytes,
    materialize_or_check,
    validate_source_snapshot,
    verify_public_marker_lexicon,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/public_marker_lexicon/marker_cases_en_v1.json"


def _source() -> dict:
    return json.loads((ROOT / SOURCE_REL).read_text(encoding="utf-8"))


def _copy_gate_capsule(tmp_path: Path) -> Path:
    root = tmp_path / "formal_experiment"
    shutil.copytree(ROOT / "resources/lexicon", root / "resources/lexicon")
    (root / "configs").mkdir(parents=True)
    shutil.copyfile(ROOT / "configs/experiment_contract.json", root / "configs/experiment_contract.json")
    return root


def test_source_snapshot_and_generated_counts_are_exact() -> None:
    source = _source()
    validate_source_snapshot(source)
    documents = build_artifact_documents(ROOT / SOURCE_REL)
    manifest = documents[MANIFEST_REL]
    counts = {
        category: manifest["category_files"][category]["entry_count"]
        for category in CATEGORY_FILES
    }
    assert counts == EXPECTED_CATEGORY_COUNTS
    assert sum(counts.values()) == 64
    assert manifest["development_extensions"]["entry_count"] == 0
    assert manifest["boundaries"]["training_run"] is False
    assert manifest["boundaries"]["evaluation_run"] is False
    assert manifest["boundaries"]["s2_4_or_later_activated"] is False


def test_public_source_duplicates_merge_without_losing_provenance() -> None:
    docs = build_artifact_documents(ROOT / SOURCE_REL)
    conditions = docs[CATEGORY_FILES["condition"]]["entries"]
    provided = next(item for item in conditions if item["surface"] == "provided that")
    assert provided["source_ids"] == [
        "lexnlp_conditions_local_audit_2026_07_12",
        "paper_examples_local_audit_2026_07_12",
    ]


def test_definition_and_action_do_not_gain_guessed_markers() -> None:
    docs = build_artifact_documents(ROOT / SOURCE_REL)
    modality = docs[CATEGORY_FILES["modality"]]
    assert modality["class_counts"]["definition"] == 0
    assert all(item.get("modality_class") != "definition" for item in modality["entries"])
    source = _source()
    assert source["policy"]["action_strategy"] == "syntax_only_no_action_marker_lexicon"


def test_generated_resources_match_exact_deterministic_bytes() -> None:
    first = expected_artifact_bytes(ROOT / SOURCE_REL)
    second = expected_artifact_bytes(ROOT / SOURCE_REL)
    assert first == second
    report = materialize_or_check(ROOT, write=False)
    assert report["written"] == []
    assert report["source_sha256"] == PUBLIC_MARKER_EXPECTATIONS.source_file_sha256
    assert report["manifest_sha256"] == PUBLIC_MARKER_EXPECTATIONS.manifest_file_sha256


def test_builder_writes_missing_files_but_refuses_differing_overwrite(tmp_path: Path) -> None:
    root = tmp_path / "formal_experiment"
    source_target = root / SOURCE_REL
    source_target.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / SOURCE_REL, source_target)
    report = materialize_or_check(root, write=True)
    assert len(report["written"]) == 7
    changed = root / CATEGORY_FILES["condition"]
    changed.write_text("{}\n", encoding="utf-8")
    with pytest.raises(PublicMarkerLexiconError, match="refusing to overwrite"):
        materialize_or_check(root, write=True)


def test_production_gate_cross_checks_contract_and_hard_hashes() -> None:
    report = verify_public_marker_lexicon(ROOT)
    assert report["ready"] is True, report
    assert report["category_counts"] == EXPECTED_CATEGORY_COUNTS
    assert report["combined_payload_sha256"] == PUBLIC_MARKER_EXPECTATIONS.combined_payload_sha256


def test_gate_fails_if_generated_bytes_are_modified(tmp_path: Path) -> None:
    root = _copy_gate_capsule(tmp_path)
    target = root / CATEGORY_FILES["actor"]
    target.write_bytes(target.read_bytes() + b"\n")
    report = verify_public_marker_lexicon(root)
    assert report["ready"] is False
    assert "public_marker_generated_bytes_mismatch" in report["blockers"]


def test_gate_fails_if_contract_relaxes_stage_boundary(tmp_path: Path) -> None:
    root = _copy_gate_capsule(tmp_path)
    contract_path = root / "configs/experiment_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["stage2_dataset"]["public_marker_lexicon"]["training_run"] = True
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    report = verify_public_marker_lexicon(root)
    assert report["ready"] is False
    assert "public_marker_contract_mismatch" in report["blockers"]


def test_source_validation_rejects_test_driven_extension_policy() -> None:
    source = copy.deepcopy(_source())
    source["policy"]["development_extension_strategy"]["test_time_additions_forbidden"] = False
    with pytest.raises(PublicMarkerLexiconError, match="extension policy"):
        validate_source_snapshot(source)


def test_source_validation_rejects_unrecorded_marker_addition() -> None:
    source = copy.deepcopy(_source())
    source["sources"][0]["markers"].append(
        {"field": "actor", "surface": "controller", "ambiguity": "low"}
    )
    with pytest.raises(PublicMarkerLexiconError, match="expected 66"):
        validate_source_snapshot(source)


def test_explicit_public_loader_matches_positive_and_boundary_fixtures() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    lexicon = MarkerLexicon.from_public_v1()

    for case in fixture["positive_cases"]:
        text = case["text"].casefold()
        field = case["field"]
        if field == "modality":
            marker, label = lexicon.find_modality(text) or (None, None)
            assert marker == case["surface"]
            assert label == case["modality_class"]
        elif field == "condition":
            assert case["surface"] in {item[2] for item in lexicon.find_all_conditions(text)}
        elif field == "constraint":
            assert case["surface"] in {item[2] for item in lexicon.find_all_constraints(text)}
        elif field == "exception":
            assert case["surface"] in {item[2] for item in lexicon.find_all_exceptions(text)}
        elif field == "actor":
            assert lexicon.find_actor(text) == (
                text.index(case["surface"]),
                text.index(case["surface"]) + len(case["surface"]),
                case["surface"],
            )

    for case in fixture["boundary_negative_cases"]:
        text = case["text"].casefold()
        if case["field"] == "modality":
            assert lexicon.find_modality(text) is None
        else:
            assert lexicon.find_actor(text) is None


def test_empty_extension_registry_is_hash_locked_and_inactive() -> None:
    extension = json.loads((ROOT / EXTENSIONS_REL).read_text(encoding="utf-8"))
    assert extension["entries"] == []
    assert extension["_meta"]["activation"] == "not_included_in_v1"
    assert extension["_meta"]["policy"]["test_time_additions_forbidden"] is True

