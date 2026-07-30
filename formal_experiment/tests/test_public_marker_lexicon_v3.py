"""Source-only public marker lexicon v3 freeze tests."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from bpc_hybrid.sun_style.public_marker_lexicon_v3 import (
    CATEGORY_FILES,
    CATEGORY_ORDER,
    EXPECTED_COUNTS,
    MANIFEST_REL,
    REPORT_REL,
    RUNTIME_FIELDS,
    SOURCE_REL,
    PublicMarkerLexiconV3Error,
    build_artifact_bytes,
    flatten_entries,
    materialize_or_check,
    validate_source_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]


def _source() -> dict:
    return json.loads((ROOT / SOURCE_REL).read_text(encoding="utf-8"))


def test_v3_source_and_candidate_counts_are_exact() -> None:
    source = _source()
    validate_source_snapshot(source)
    entries = flatten_entries(source)
    assert {field: len(entries[field]) for field in CATEGORY_ORDER} == EXPECTED_COUNTS
    assert sum(map(len, entries.values())) == 87
    assert sum(len(entries[field]) for field in RUNTIME_FIELDS) == 80


def test_every_v3_marker_has_complete_per_marker_provenance() -> None:
    entries = flatten_entries(_source())
    required = {
        "source_id",
        "source_type",
        "title_or_project",
        "doi",
        "url",
        "source_version",
        "source_sha256",
        "access_date",
        "license_status",
        "redistribution_status",
        "exact_location",
        "item_location",
        "raw_evidence_text",
    }
    for field_entries in entries.values():
        for entry in field_entries:
            assert entry["field"] in CATEGORY_ORDER
            assert entry["surface"] == entry["normalized"]
            assert entry["is_derived"] is False
            assert entry["derivation"] is None
            assert entry["provenance"]
            for provenance in entry["provenance"]:
                assert required <= set(provenance)
                assert provenance["item_location"]
                assert provenance["raw_evidence_text"]


def test_v3_keeps_full_lexnlp_phrases_and_excludes_docs_only_customization() -> None:
    constraints = {entry["surface"] for entry in flatten_entries(_source())["constraint"]}
    assert {"equal to", "less than", "no later than", "not equal to"} <= constraints
    assert "smallest among" not in constraints


def test_v2_defect_audit_is_exact_and_all_named_surfaces_exist_in_v2() -> None:
    source = _source()
    groups = source["known_v2_provenance_defects"]["groups"]
    assert sum(len(group["markers"]) for group in groups) == 106
    for group in groups:
        payload = json.loads(
            (ROOT / f"resources/lexicon/{group['field']}_markers_en_v2.json").read_text(
                encoding="utf-8"
            )
        )
        surfaces = {entry["surface"] for entry in payload["entries"]}
        assert set(group["markers"]) <= surfaces


def test_v3_action_is_explicitly_empty_and_modality_is_not_runtime_bound() -> None:
    artifacts = build_artifact_bytes(ROOT / SOURCE_REL)
    action = json.loads(artifacts[CATEGORY_FILES["action"]])
    manifest = json.loads(artifacts[MANIFEST_REL])
    assert action["entries"] == []
    assert manifest["runtime_binding"]["bound_fields"] == list(RUNTIME_FIELDS)
    assert "MD" in manifest["runtime_binding"]["modality"]


def test_v3_generated_artifacts_match_exact_frozen_bytes() -> None:
    assert build_artifact_bytes(ROOT / SOURCE_REL) == build_artifact_bytes(ROOT / SOURCE_REL)
    report = materialize_or_check(ROOT, write=False)
    assert report["written"] == []
    assert set(report["checked"]) == {
        *CATEGORY_FILES.values(),
        MANIFEST_REL,
        REPORT_REL,
    }


def test_v3_builder_writes_missing_files_and_refuses_differing_overwrite(
    tmp_path: Path,
) -> None:
    root = tmp_path / "formal_experiment"
    source_target = root / SOURCE_REL
    source_target.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / SOURCE_REL, source_target)
    for field in {group["field"] for group in _source()["known_v2_provenance_defects"]["groups"]}:
        target = root / f"resources/lexicon/{field}_markers_en_v2.json"
        shutil.copyfile(ROOT / f"resources/lexicon/{field}_markers_en_v2.json", target)
    first = materialize_or_check(root, write=True)
    assert len(first["written"]) == 8
    changed = root / CATEGORY_FILES["condition"]
    changed.write_text("{}\n", encoding="utf-8")
    with pytest.raises(PublicMarkerLexiconV3Error, match="refusing to overwrite"):
        materialize_or_check(root, write=True)


def test_v3_validation_rejects_derived_or_test_driven_candidates() -> None:
    source = _source()
    derived = copy.deepcopy(source)
    derived["construction_policy"]["derived_markers_included"] = True
    with pytest.raises(PublicMarkerLexiconV3Error, match="derived"):
        validate_source_snapshot(derived)
    test_driven = copy.deepcopy(source)
    test_driven["construction_policy"]["forbidden_inputs"].remove("Gold annotations")
    with pytest.raises(PublicMarkerLexiconV3Error, match="forbidden-input"):
        validate_source_snapshot(test_driven)
