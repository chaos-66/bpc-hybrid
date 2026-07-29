"""Headless tests for the one-screen EStG-150 Sol review workflow."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.estg150_service import HumanCorrectionService
from formal_experiment.estg150_simple_review import (
    SimpleReviewError,
    layer_e_record_to_candidate,
    load_candidate_bundle,
    rebuild_candidate,
    validate_simple_candidate,
)


PILOT = (
    ROOT
    / "data/development/estg/llm_candidate_runs"
    / "codex_internal_gpt56sol_pilot3_v1/pass_b_candidates.json"
)
FULL_RUN = (
    ROOT
    / "data/development/estg/llm_candidate_runs"
    / "codex_internal_gpt56sol_full150_v1"
)
FULL_BUNDLE = FULL_RUN / "ai_review_candidates.json"
FULL_MANIFEST = FULL_RUN / "manifest.json"
REAL_LAYER_E = ROOT / "data/development/human_review/estg_150_human_correction_v1.json"
REAL_MEMBERSHIP = ROOT / "data/development/estg/estg_150_membership_hashes.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _edits(candidate: dict) -> list[dict]:
    return [
        {
            "clause_id": clause["clause_id"],
            "modality": clause["modality"]["label"],
            "actors": "\n".join(span["text"] for span in clause["actors"]),
            "actions": "\n".join(span["text"] for span in clause["actions"]),
            "conditions": "\n".join(span["text"] for span in clause["conditions"]),
            "constraints": "\n".join(span["text"] for span in clause["constraints"]),
            "exceptions": "\n".join(span["text"] for span in clause["exceptions"]),
        }
        for clause in candidate["clauses"]
    ]


@pytest.fixture()
def pilot_bundle() -> dict:
    return load_candidate_bundle(PILOT, expected_count=3)


@pytest.fixture()
def temp_service(tmp_path: Path) -> HumanCorrectionService:
    human_dir = tmp_path / "data/development/human_review"
    estg_dir = tmp_path / "data/development/estg"
    human_dir.mkdir(parents=True)
    estg_dir.mkdir(parents=True)
    layer_e = human_dir / REAL_LAYER_E.name
    shutil.copy(REAL_LAYER_E, layer_e)
    shutil.copy(REAL_MEMBERSHIP, estg_dir / REAL_MEMBERSHIP.name)
    return HumanCorrectionService(
        path=layer_e,
        backup_dir=tmp_path / "outputs/backups",
        action_log=tmp_path / "outputs/actions.jsonl",
        reviewer="pytest",
    )


def test_pilot_candidates_are_exact_and_editable(pilot_bundle):
    candidate = pilot_bundle["records"][0]
    validate_simple_candidate(candidate)
    rebuilt = rebuild_candidate(candidate, _edits(candidate))
    assert rebuilt == candidate


def test_hidden_span_locator_rejects_text_not_in_clause(pilot_bundle):
    candidate = pilot_bundle["records"][0]
    edits = _edits(candidate)
    edits[0]["actors"] = "this phrase is not in the regulation"
    with pytest.raises(SimpleReviewError, match="正文里找不到"):
        rebuild_candidate(candidate, edits)


def test_one_click_save_materializes_candidate_without_touching_immutable_layer_c(
    temp_service,
    pilot_bundle,
):
    candidate = copy.deepcopy(pilot_bundle["records"][0])
    sample_id = candidate["sample_id"]
    before = temp_service.get_record(sample_id)
    immutable_before = copy.deepcopy(before["llm_candidate"])

    finalized = rebuild_candidate(candidate, _edits(candidate))
    result = temp_service.apply_simple_review_candidate(sample_id, finalized)
    assert result["ok"] is True
    saved = temp_service.save_draft()
    assert saved["validation"]["format_valid"] is True

    after = temp_service.get_record(sample_id)
    assert after["review_state"]["status"] == "adjudicated"
    assert after["llm_candidate"] == immutable_before
    assert after["approved_text_en"] == finalized["translation"]["proposed_text_en"]
    assert len(after["human_correction"]["clauses"]) == len(finalized["clauses"])
    assert all(after["decisions"][field] == "edited" for field in (
        "modality", "actor", "action", "condition", "constraint", "exception"
    ))

    redisplayed = layer_e_record_to_candidate(after)
    validate_simple_candidate(redisplayed)
    assert redisplayed["translation"]["proposed_text_en"] == after["approved_text_en"]


def test_tests_never_change_real_layer_e(temp_service, pilot_bundle):
    before = _sha256(REAL_LAYER_E)
    candidate = pilot_bundle["records"][1]
    result = temp_service.apply_simple_review_candidate(
        candidate["sample_id"],
        rebuild_candidate(candidate, _edits(candidate)),
    )
    assert result["ok"] is True
    temp_service.save_draft()
    assert _sha256(REAL_LAYER_E) == before


def test_simple_tool_help_is_headless():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/estg150_simple_review_tool.py"), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0
    assert "极简 EStG-150" in result.stdout


def test_simple_screen_does_not_restore_legacy_decision_buttons():
    source = (ROOT / "scripts/estg150_simple_review_tool.py").read_text(encoding="utf-8")
    assert "保存并下一条" in source
    assert "稍后再看" in source
    for legacy_button in ("接受英文候选", "待裁决", "本条已复核", "本条已裁决"):
        assert legacy_button not in source


def test_full_sol_bundle_is_complete_hash_bound_and_matches_layer_e_membership():
    bundle = load_candidate_bundle(FULL_BUNDLE)
    manifest = json.loads(FULL_MANIFEST.read_text(encoding="utf-8"))
    layer_e = json.loads(REAL_LAYER_E.read_text(encoding="utf-8"))
    bundle_ids = [candidate["sample_id"] for candidate in bundle["records"]]
    layer_e_ids = {record["sample_id"] for record in layer_e["records"]}
    assert len(bundle_ids) == 150
    assert len(set(bundle_ids)) == 150
    assert set(bundle_ids) == layer_e_ids
    assert manifest["candidate_count"] == 150
    assert manifest["validated_candidate_count"] == 150
    assert manifest["candidate_bundle_sha256"] == _sha256(FULL_BUNDLE)
    assert manifest["layer_e_changed"] is False
