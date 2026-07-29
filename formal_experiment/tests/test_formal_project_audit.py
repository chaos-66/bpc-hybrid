"""Regression tests for the canonical formal-project audit.

These tests pin down the **2026-07-13 four-gate split (Event 22)**:

  1. human_review_input_ready
       True as soon as the data sources, schemas, tool, v2 file,
       authoritative contract gate status, and membership cross-check
       are all satisfied. Independent of 0/150 progress. The user
       can start the human review NOW.
       This is what `--require-human-review-ready` checks.

  2. human_review_freeze_ready
       True only after every record has been adjudicated. This is
       a NECESSARY but NOT SUFFICIENT condition for declaring
       formal Gold.

  3. formal_gold_publication_ready
       True only when human_review_freeze_ready AND route.locked AND
       dataset.locked AND stage3.locked AND the formal_gold_publication_gate
       is not blocked. Conservative: any missing or non-locked field
       keeps it false.

  4. final_experiment_ready
       True only when formal_gold_publication_ready AND methods are
       not blocked AND frozen input/gold are present.

The previously contradictory `formal_human_review_paused` blocker
is removed; the pause is now scoped to formal Gold publication only.
The deprecated alias `audit.human_review_ready` mirrors gate 1
(semantic: "user can start review NOW"), NOT gate 3.

All gate-transition tests use tmp_path / monkeypatch so they never
write to the real Layer E, real backup dir, or real action log.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FORMAL_SRC = PROJECT_ROOT / "src"
if str(FORMAL_SRC) not in sys.path:
    sys.path.insert(0, str(FORMAL_SRC))


# ---------------------------------------------------------------------------
# Status import — the core module under test.
# ---------------------------------------------------------------------------
from formal_experiment.audit import collect_project_audit
from formal_experiment.status import collect_status


def _codes(audit: dict, level: str) -> set[str]:
    return {item["code"] for item in audit["findings"][level]}


# ---------------------------------------------------------------------------
# Test fixture helpers
# ---------------------------------------------------------------------------

# The exact whitelist used by the contract and the status module for
# the formal_gold_publication_gate status. The tests must use this
# exact string when simulating an "all locks satisfied" contract, or
# the conservative whitelist check will keep
# formal_gold_publication_ready false (which is the correct
# conservative behavior).
PUBLICATION_WHITELIST_STATUS = "ready_for_formal_gold_publication"


def _sha256(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _make_format_valid_freeze_record(legacy_id: int) -> dict:
    """Build a record that is format-valid under the strict v2
    validator AND is freeze-ready (review_state.status = adjudicated,
    all decisions in the freeze-decision set).

    The record's `raw_text_de`, `candidate_text_en`, and
    `approved_text_en` are real strings so that the corresponding
    ``_sha256`` values match what the strict validator computes. The
    content is intentionally a short token (the legacy_id) so each
    record is unique but the fixture is still small.
    """
    text_de = f"de-text-{legacy_id:06d}"
    text_en = f"en-text-{legacy_id:06d}"
    ap_en = f"ap-en-{legacy_id:06d}"
    return {
        "sample_id": f"estg_{legacy_id:06d}",
        "legacy_record_id": legacy_id,
        "source_refs": {
            "german_source": "data/development/estg/estg_selected_150_de.jsonl",
            "english_translation_source": "data/development/estg/estg_selected_150_en_llm_translated.jsonl",
            "llm_candidate_source": "data/development/estg/estg_gold_150_llm_draft.jsonl",
            "chinese_aid_source": "data/development/human_review/estg_150_review_aids_zh_v1.jsonl",
        },
        "raw_text_de": text_de,
        "raw_text_de_sha256": _sha256(text_de),
        "candidate_text_en": text_en,
        "candidate_text_en_sha256": _sha256(text_en),
        "approved_text_en": ap_en,
        "approved_text_en_sha256": _sha256(ap_en),
        "approved_text_en_history": [],
        "llm_candidate": {
            "immutable": True,
            "candidate_source": "data/development/estg/estg_gold_150_llm_draft.jsonl",
            "candidate_sha256": _sha256("placeholder"),
            "missing_in_llm_candidate": True,
            "clauses": [],
        },
        "human_correction": {
            "approved_text_en": ap_en,
            "approved_text_en_decision": "accepted",
            "translation_notes": None,
            "clauses": [],
        },
        "decisions": {
            "translation": "accepted",
            "modality": "accepted",
            "actor": "accepted",
            "action": "accepted",
            "condition": "accepted",
            "constraint": "accepted",
            "exception": "accepted",
        },
        "review_state": {
            "status": "adjudicated",
            "reviewer": "user",
            "reviewed_at": "2026-07-13T00:00:00Z",
            "adjudicated_at": "2026-07-13T00:00:00Z",
            "notes": None,
        },
    }


def _build_v2_doc(membership: dict, records: list[dict]) -> dict:
    return {
        "schema_version": "estg_150_review_workflow@1.0.0",
        "dataset": {
            "name": "independently_reconstructed_estg_150",
            "version": "v1",
            "workflow": "llm_assisted_human_adjudicated",
            "membership_count": 150,
            "membership_source": "data/development/estg/estg_selected_150_de.jsonl",
            "membership_payload_sha256": membership["selected_membership"]["membership_payload_sha256"],
        },
        "records": records,
    }


def _write_freeze_ready_v2(tmp_path: Path) -> tuple[Path, Path]:
    """Build a 150/150 adjudicated, format-valid v2 doc and the
    matching membership hashes file in ``tmp_path``. Returns the
    (v2_path, membership_path) tuple."""
    real_v2 = PROJECT_ROOT / "data/development/human_review/estg_150_human_correction_v1.json"
    real_membership = PROJECT_ROOT / "data/development/estg/estg_150_membership_hashes.json"
    test_v2 = tmp_path / "estg_150_human_correction_v1.json"
    test_membership = tmp_path / "estg_150_membership_hashes.json"
    shutil.copy(real_v2, test_v2)
    shutil.copy(real_membership, test_membership)
    mem = json.loads(test_membership.read_text(encoding="utf-8"))
    ids = mem["selected_membership"]["sorted_legacy_record_ids"]
    assert len(ids) == 150
    records = [_make_format_valid_freeze_record(lid) for lid in ids]
    doc = _build_v2_doc(mem, records)
    test_v2.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return test_v2, test_membership


# ---------------------------------------------------------------------------
# 1. Current frozen state: all four booleans
# ---------------------------------------------------------------------------
def test_current_state_four_gates_reported_after_annotation_freeze() -> None:
    audit = collect_project_audit()
    assert audit["integrity_pass"] is True
    # All four booleans must be present
    for k in (
        "human_review_input_ready",
        "human_review_freeze_ready",
        "formal_gold_publication_ready",
        "final_experiment_ready",
    ):
        assert k in audit, f"missing gate: {k}"
    # S2.2 is frozen, while formal publication and final execution remain blocked.
    assert audit["human_review_input_ready"] is True
    assert audit["human_review_freeze_ready"] is True
    assert audit["stage2_annotation_freeze_verified"] is True
    assert audit["estg150_candidate_protocol_c0_verified"] is True
    assert audit["estg150_c1_transport_adapter_offline_ready"] is True
    assert audit["estg150_c1_runtime_verified"] is True
    assert audit["estg150_c1_runtime"]["candidate_count"] == 1
    assert audit["estg150_c1_runtime"]["total_tokens"] == 1996
    assert audit["estg150_c1_runtime"]["total_cost"] == "0.042987"
    assert audit["estg150_c1_runtime"]["precision"] is None
    assert audit["estg150_c1_runtime"]["recall"] is None
    assert audit["formal_gold_publication_ready"] is False
    assert audit["final_experiment_ready"] is False
    # The deprecated alias equals gate 1
    assert audit["human_review_ready"] is True
    assert audit["human_review_ready_semantics"].startswith("DEPRECATED")


# ---------------------------------------------------------------------------
# 2. --require-human-review-ready remains progress-independent
# ---------------------------------------------------------------------------
def test_require_human_review_ready_flag_passes_after_freeze() -> None:
    res = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "audit_project.py"),
         "--require-human-review-ready"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert res.returncode == 0, (
        f"--require-human-review-ready should pass whenever input is "
        f"ready), got exit {res.returncode}\n{res.stdout}\n{res.stderr}"
    )


# ---------------------------------------------------------------------------
# 3. --require-final-ready still fails at 0/150
# ---------------------------------------------------------------------------
def test_require_final_ready_flag_still_fails_at_zero_progress() -> None:
    res = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "audit_project.py"),
         "--require-final-ready"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert res.returncode == 2, (
        f"--require-final-ready must fail at 0/150, got exit {res.returncode}"
    )


# ---------------------------------------------------------------------------
# 4. Missing schema → input gate is false
# ---------------------------------------------------------------------------
def test_input_gate_false_when_schema_missing(monkeypatch) -> None:
    """If the human_review schema is removed, the input gate must
    become false even though every other precondition is satisfied."""
    from formal_experiment import status as status_mod
    orig = status_mod.HUMAN_REVIEW_SCHEMA
    monkeypatch.setattr(status_mod, "HUMAN_REVIEW_SCHEMA", PROJECT_ROOT / "no_such_schema.json")
    monkeypatch.setattr(
        "formal_experiment.audit.HUMAN_REVIEW_SCHEMA",
        PROJECT_ROOT / "no_such_schema.json",
    )
    s = status_mod.collect_status()
    assert s["human_review_input_ready"] is False
    # restore for the rest of the tests
    monkeypatch.setattr(status_mod, "HUMAN_REVIEW_SCHEMA", orig)
    monkeypatch.setattr("formal_experiment.audit.HUMAN_REVIEW_SCHEMA", orig)


# ---------------------------------------------------------------------------
# 5. Missing review tool / validator → input gate is false
# ---------------------------------------------------------------------------
def test_input_gate_false_when_tool_or_validator_missing(tmp_path, monkeypatch) -> None:
    """If the review tool or the validator script is missing, the
    input gate must be false. The simplest way to simulate the
    "missing" state without breaking the rest of the test
    environment is to build a fake REPO_ROOT under tmp_path that
    has the same structure but is missing the script files; the
    status function must reject the input gate in that case.
    """
    # Build a fake REPO_ROOT: same structure but no script files.
    fake = tmp_path / "fake_repo"
    (fake / "scripts").mkdir(parents=True)
    (fake / "data" / "development" / "estg").mkdir(parents=True)
    (fake / "data" / "development" / "human_review").mkdir(parents=True)
    # Copy the schema into the fake repo so we isolate "missing
    # script" as the failure cause
    real_schema = PROJECT_ROOT / "configs" / "schemas" / "human_gold_review.schema.json"
    schemas_dir = fake / "configs" / "schemas"
    schemas_dir.mkdir(parents=True)
    shutil.copy(real_schema, schemas_dir / "human_gold_review.schema.json")
    # Intentionally do NOT copy estg150_review_tool.py or
    # validate_human_correction.py into fake/scripts.
    from formal_experiment import status as status_mod
    from formal_experiment import paths as paths_mod
    orig_repo = status_mod.REPO_ROOT
    orig_hc = status_mod.HUMAN_CORRECTION_FILE
    orig_can = status_mod.CANONICAL_REVIEW_FILE
    orig_schema = status_mod.HUMAN_REVIEW_SCHEMA
    orig_frozen_in = status_mod.FROZEN_INPUT_DIR
    orig_frozen_gold = status_mod.FROZEN_GOLD_DIR
    orig_pack = status_mod.HUMAN_REVIEW_PACK
    orig_methods = status_mod.METHODS_CONFIG
    orig_contract = status_mod.EXPERIMENT_CONTRACT
    orig_winter = status_mod.WINTER_2020_REFERENCE_DIR
    orig_sun = status_mod.SUN_ORIGINAL_REFERENCE_DIR
    orig_membership = status_mod.ESTG_150_MEMBERSHIP_HASHES

    monkeypatch.setattr(status_mod, "REPO_ROOT", fake)
    # Other paths are derived from the parent (REPO_ROOT.parent) or
    # from siblings; the input-ready gate only depends on
    # REPO_ROOT, HUMAN_REVIEW_SCHEMA, HUMAN_CORRECTION_FILE,
    # CANONICAL_REVIEW_FILE, and the v2 schema.
    # We need HUMAN_REVIEW_SCHEMA to point to the fake schema
    monkeypatch.setattr(status_mod, "HUMAN_REVIEW_SCHEMA", schemas_dir / "human_gold_review.schema.json")
    # HUMAN_CORRECTION_FILE, CANONICAL_REVIEW_FILE, etc. will be
    # at fake/data/... — but they don't exist there. The function
    # already handles missing files (returns format_valid=False),
    # so the test verifies that the script-path check fires BEFORE
    # the v2-file check or alongside it.
    # For the v2 file, also point to non-existent so the test isn't
    # confused by file-finding.
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", fake / "data" / "development" / "human_review" / "estg_150_human_correction_v1.json")
    monkeypatch.setattr(status_mod, "CANONICAL_REVIEW_FILE", fake / "data" / "development" / "human_review" / "estg_150_canonical_review_v1.json")
    monkeypatch.setattr(status_mod, "FROZEN_INPUT_DIR", fake / "data" / "input")
    monkeypatch.setattr(status_mod, "FROZEN_GOLD_DIR", fake / "data" / "gold")
    monkeypatch.setattr(status_mod, "HUMAN_REVIEW_PACK", fake / "data" / "development" / "human_review" / "estg150_review_pack_v1.jsonl")
    monkeypatch.setattr(status_mod, "METHODS_CONFIG", fake / "configs" / "methods.json")
    monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", fake / "configs" / "experiment_contract.json")
    monkeypatch.setattr(status_mod, "WINTER_2020_REFERENCE_DIR", fake / "references" / "winter_2020_model_check")
    monkeypatch.setattr(status_mod, "SUN_ORIGINAL_REFERENCE_DIR", fake / "references" / "sun_program")
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", fake / "data" / "development" / "estg" / "estg_150_membership_hashes.json")
    s = status_mod.collect_status()
    assert s["human_review_input_ready"] is False
    # The specific reason is the missing scripts
    # Restore
    monkeypatch.setattr(status_mod, "REPO_ROOT", orig_repo)
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_hc)
    monkeypatch.setattr(status_mod, "CANONICAL_REVIEW_FILE", orig_can)
    monkeypatch.setattr(status_mod, "HUMAN_REVIEW_SCHEMA", orig_schema)
    monkeypatch.setattr(status_mod, "FROZEN_INPUT_DIR", orig_frozen_in)
    monkeypatch.setattr(status_mod, "FROZEN_GOLD_DIR", orig_frozen_gold)
    monkeypatch.setattr(status_mod, "HUMAN_REVIEW_PACK", orig_pack)
    monkeypatch.setattr(status_mod, "METHODS_CONFIG", orig_methods)
    monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", orig_contract)
    monkeypatch.setattr(status_mod, "WINTER_2020_REFERENCE_DIR", orig_winter)
    monkeypatch.setattr(status_mod, "SUN_ORIGINAL_REFERENCE_DIR", orig_sun)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_membership)


# ---------------------------------------------------------------------------
# 6. Duplicate / missing sample_id or membership mismatch → input gate false
# ---------------------------------------------------------------------------
def test_input_gate_false_on_sample_id_or_membership_mismatch(
    tmp_path: Path, monkeypatch,
) -> None:
    """If the v2 human_correction file's sample_ids disagree with the
    locked membership, the input gate must be false."""
    # Copy the real v2 human_correction file to tmp_path and corrupt
    # one sample_id.
    real_v2 = PROJECT_ROOT / "data" / "development" / "human_review" / "estg_150_human_correction_v1.json"
    test_v2 = tmp_path / "estg_150_human_correction_v1.json"
    shutil.copy(real_v2, test_v2)
    doc = json.loads(test_v2.read_text(encoding="utf-8"))
    # Duplicate an id by appending the first record again
    if doc["records"]:
        doc["records"].append(dict(doc["records"][0]))
    test_v2.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    from formal_experiment import status as status_mod
    orig = status_mod.HUMAN_CORRECTION_FILE
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
    s = status_mod.collect_status()
    assert s["membership_ok"] is False
    assert s["human_review_input_ready"] is False
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig)


# ---------------------------------------------------------------------------
# 7. Contract human_review_gate.status = paused → input gate is false
# ---------------------------------------------------------------------------
def test_input_gate_false_when_contract_status_paused(tmp_path: Path, monkeypatch) -> None:
    """The authoritative contract must allow starting the human
    review. If the contract is reverted to 'paused_until_route_v2_is_locked'
    or any blocking status, the input gate is false even if all
    other preconditions are satisfied."""
    contract = PROJECT_ROOT / "configs" / "experiment_contract.json"
    test_contract = tmp_path / "experiment_contract.json"
    doc = json.loads(contract.read_text(encoding="utf-8"))
    doc["human_review_gate"]["status"] = "paused_until_route_v2_is_locked"
    test_contract.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    from formal_experiment import status as status_mod
    orig = status_mod.EXPERIMENT_CONTRACT
    monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", test_contract)
    s = status_mod.collect_status()
    assert s["human_review_gate_contract_authorizes_input_start"] is False
    assert s["human_review_input_ready"] is False
    # Restore
    monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", orig)


# ---------------------------------------------------------------------------
# 8. 150/150 adjudicated but route/data reopened → freeze=True but
#    formal_gold=False, and the formal_gold_publication_paused
#    blocker must remain. The audit must NOT emit "Formal Gold can
#    be declared".
# ---------------------------------------------------------------------------
def test_freeze_true_but_gold_paused_keeps_publication_blocked(
    tmp_path: Path, monkeypatch,
) -> None:
    """Simulate 150/150 adjudicated by replacing the v2 file with a
    minimal doc whose review_state.status=adjudicated and freeze_ready=True.
    The route / dataset / stage3 / freeze_policy remain reopened. The
    audit must report:
      - human_review_freeze_ready = True
      - formal_gold_publication_ready = False
      - formal_gold_publication_paused blocker present
      - the message must NOT contain 'Formal Gold can be declared'"""
    test_v2, test_membership = _write_freeze_ready_v2(tmp_path)

    from formal_experiment import status as status_mod
    orig_v2 = status_mod.HUMAN_CORRECTION_FILE
    orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
    s = status_mod.collect_status()
    assert s["human_review_freeze_ready"] is True, s
    # The route/dataset/stage3 remain reopened, so formal_gold_publication_ready
    # must be False.
    assert s["formal_gold_publication_ready"] is False, s
    # Now run the audit and verify the blocker is present, and the
    # forbidden 'Formal Gold can be declared' message is absent.
    from formal_experiment import audit as audit_mod
    orig_v2_audit = audit_mod.HUMAN_CORRECTION_FILE
    monkeypatch.setattr(audit_mod, "HUMAN_CORRECTION_FILE", test_v2)
    audit = audit_mod.collect_project_audit()
    blockers = _codes(audit, "blockers")
    assert "formal_gold_publication_paused" in blockers
    # The audit output (the actual messages) must not say
    # "Formal Gold can be declared"
    all_msgs = " ".join(
        f["message"] for f in audit["findings"]["blockers"] + audit["findings"]["passes"]
    )
    assert "Formal Gold can be declared" not in all_msgs, all_msgs
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
    monkeypatch.setattr(audit_mod, "HUMAN_CORRECTION_FILE", orig_v2_audit)


# ---------------------------------------------------------------------------
# 9. Only when route + data + stage3 + freeze_policy are all locked
#    does formal_gold_publication_ready become true. If the contract
#    cannot express a condition, the test must prove the conservative
#    false behavior, not guess.
# ---------------------------------------------------------------------------
def test_formal_gold_publication_ready_only_when_all_five_locks_true(
    tmp_path: Path, monkeypatch,
) -> None:
    """Replace the contract with one where all five formal-gold
    preconditions are met (route.locked, dataset.locked, stage3.locked,
    formal_gold_publication_gate.status in the exact whitelist,
    human_correction freeze_ready). formal_gold_publication_ready
    must become True."""
    test_v2, test_membership = _write_freeze_ready_v2(tmp_path)

    # Replace the contract with a fully-locked variant
    contract_path = PROJECT_ROOT / "configs/experiment_contract.json"
    test_contract = tmp_path / "experiment_contract.json"
    cdoc = json.loads(contract_path.read_text(encoding="utf-8"))
    cdoc["route"]["status"] = "locked"
    cdoc["stage2_dataset"]["status"] = "locked_for_human_review"
    cdoc["stage3"]["status"] = "locked"
    cdoc["human_review_gate"]["status"] = "input_ready_for_human_review"
    # Event 23: the publication gate is exact-whitelist matched. The
    # whitelist is the contract's `allowed_publication_statuses` (or
    # the status module's default). The status value must be the
    # exact string in the whitelist; the old
    # "all_locks_satisfied" sentinel is intentionally not on the
    # whitelist.
    cdoc["formal_gold_publication_gate"]["status"] = PUBLICATION_WHITELIST_STATUS
    cdoc["formal_gold_publication_gate"]["allowed_publication_statuses"] = [
        PUBLICATION_WHITELIST_STATUS,
    ]
    test_contract.write_text(json.dumps(cdoc, ensure_ascii=False, indent=2), encoding="utf-8")

    from formal_experiment import status as status_mod
    orig_v2 = status_mod.HUMAN_CORRECTION_FILE
    orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
    orig_contract = status_mod.EXPERIMENT_CONTRACT
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
    monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", test_contract)
    s = status_mod.collect_status()
    # freeze_ready is true (150/150 adjudicated)
    assert s["human_review_freeze_ready"] is True
    # formal_gold_publication_ready is true (all five locks satisfied)
    assert s["formal_gold_publication_ready"] is True
    # final_experiment_ready is still false because methods are blocked
    # AND frozen input/gold are empty.
    assert s["final_experiment_ready"] is False

    # Now if we also clear the method block (impossible in real config
    # but for the conservative test we want to see the gate respond),
    # the test must show that the gate is sensitive to methods too.
    # This is a conservative negative test: if the methods are still
    # blocked, final_experiment_ready is false; we already asserted
    # that above.
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
    monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", orig_contract)


def test_formal_gold_publication_ready_conservative_when_route_only_unlocks(
    tmp_path: Path, monkeypatch,
) -> None:
    """Conservative behavior: even if route alone unlocks, formal Gold
    publication still requires ALL five preconditions. Removing any
    one must keep it false."""
    test_v2, test_membership = _write_freeze_ready_v2(tmp_path)

    # Replace contract: lock route only, keep dataset/stage3/fgg reopened
    contract_path = PROJECT_ROOT / "configs/experiment_contract.json"
    test_contract = tmp_path / "experiment_contract.json"
    cdoc = json.loads(contract_path.read_text(encoding="utf-8"))
    cdoc["route"]["status"] = "locked"
    cdoc["stage2_dataset"]["status"] = (
        "reopened_modality_verified_pending_phrase_gold_freeze_and_route_relock"
    )
    cdoc["stage3"]["status"] = "pending_final_subset_configuration_and_violation_gold_lock"
    cdoc["human_review_gate"]["status"] = "input_ready_for_human_review"
    cdoc["formal_gold_publication_gate"]["status"] = "blocked_pending_route_data_stage3_re_lock"
    cdoc["formal_gold_publication_gate"]["allowed_publication_statuses"] = [
        PUBLICATION_WHITELIST_STATUS,
    ]
    test_contract.write_text(json.dumps(cdoc, ensure_ascii=False, indent=2), encoding="utf-8")

    from formal_experiment import status as status_mod
    orig_v2 = status_mod.HUMAN_CORRECTION_FILE
    orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
    orig_contract = status_mod.EXPERIMENT_CONTRACT
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
    monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", test_contract)
    s = status_mod.collect_status()
    # freeze-ready is true
    assert s["human_review_freeze_ready"] is True
    # formal_gold_publication_ready MUST be false: route alone is not enough
    assert s["formal_gold_publication_ready"] is False
    # The blocker message must enumerate the missing conditions
    from formal_experiment import audit as audit_mod
    orig_v2_audit = audit_mod.HUMAN_CORRECTION_FILE
    monkeypatch.setattr(audit_mod, "HUMAN_CORRECTION_FILE", test_v2)
    audit = audit_mod.collect_project_audit()
    blockers = audit["findings"]["blockers"]
    fgg_blocker = next(
        (b for b in blockers if b["code"] == "formal_gold_publication_paused"),
        None,
    )
    assert fgg_blocker is not None
    msg = fgg_blocker["message"]
    assert "route.status=" in msg or "stage2_dataset.status=" in msg or "stage3.status=" in msg, msg
    # The forbidden phrase must not appear
    assert "Formal Gold can be declared" not in msg
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
    monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", orig_contract)
    monkeypatch.setattr(audit_mod, "HUMAN_CORRECTION_FILE", orig_v2_audit)


# ---------------------------------------------------------------------------
# 10. No formal runner or final metrics can rely on the deprecated alias
# ---------------------------------------------------------------------------
def test_no_formal_runner_uses_human_review_ready_alone() -> None:
    """Search formal_experiment/ for the deprecated alias. The only
    acceptable consumers are:
      - status.py / audit.py — define the field and report the gate
      - audit_project.py — the explicit --require-human-review-ready
        flag, kept for backward compatibility
      - validate_estg_human_review.py and test_estg_human_review.py
        — operate on the legacy review pack, with their own local
        human_review_ready field
    Any OTHER file (the v2 human_correction tool, the validators, the
    runners, the other tests) that needs "ready to publish Gold" must
    use one of the four explicit gate names. The tool / service /
    validator may still surface the alias for backward compatibility
    (it's a deprecation point, not a final-metric signal), but new
    audit / runner / final-metric code MUST NOT use the alias.
    """
    target = PROJECT_ROOT
    definers = (
        "src/formal_experiment/status.py",
        "src/formal_experiment/audit.py",
    )
    allowed_exact = (
        "scripts/audit_project.py",
        "scripts/validate_estg_human_review.py",
        "tests/test_estg_human_review.py",
        "tests/test_formal_project_audit.py",
    )
    bad: list[tuple[str, int, str]] = []
    for path in target.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = str(path.relative_to(target)).replace("\\", "/")
        if rel in definers:
            continue
        if rel in allowed_exact:
            continue
        # Any other file that references the alias is a violation.
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "human_review_ready" in line and "alias" not in line:
                bad.append((rel, lineno, line.strip()))
    assert not bad, (
        "These files reference human_review_ready but are NOT allowed to "
        "use the alias. New code must use one of "
        "human_review_input_ready / human_review_freeze_ready / "
        "formal_gold_publication_ready / final_experiment_ready:\n" +
        "\n".join(f"  {c[0]}:{c[1]}: {c[2]}" for c in bad)
    )


# ---------------------------------------------------------------------------
# Validator CLI consistency
# ---------------------------------------------------------------------------
def test_validate_human_correction_cli_allows_user_progress_and_keeps_gates_consistent() -> None:
    import subprocess
    cli = PROJECT_ROOT / "scripts" / "validate_human_correction.py"
    res = subprocess.run(
        [sys.executable, str(cli), "--json"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert res.returncode in (0, 2), res.stderr
    report = json.loads(res.stdout)
    assert report["n_records"] == 150
    assert 0 <= report["n_reviewed"] <= 150
    assert 0 <= report["n_adjudicated"] <= 150
    assert report["n_reviewed"] + report["n_adjudicated"] <= 150
    assert not report["review_ready"] or report["n_records_incomplete"] == 0
    assert not report["freeze_ready"] or report["n_adjudicated"] == 150
    if report["n_adjudicated"] < 150:
        assert report["freeze_ready"] is False


# ---------------------------------------------------------------------------
# Pre-existing governance tests kept
# ---------------------------------------------------------------------------
def test_audit_accepts_safe_reopened_route_without_exact_sun_claim() -> None:
    audit = collect_project_audit()
    assert "final_version_route_alignment_pending" in _codes(audit, "blockers")
    assert "official_sun_supplement_identified" in _codes(audit, "passes")
    assert "winter_reference_correctly_named" in _codes(audit, "passes")
    assert "sun_original_code_unavailable" in _codes(audit, "warnings")


def test_audit_checks_full_blank_estg_review_pack() -> None:
    audit = collect_project_audit()
    report = audit["datasets"]["estg150_human_review_pack"]
    assert report["unique_ids"] == 150
    assert report["invalid_json"] == 0
    assert "human_review_pack_structurally_valid" in _codes(audit, "passes")
    assert "span_multiclause_contract_locked" in _codes(audit, "passes")
    assert "legacy_review_pack_not_formal" in _codes(audit, "warnings")


def test_audit_keeps_later_experiment_phases_blocked() -> None:
    audit = collect_project_audit()
    blockers = _codes(audit, "blockers")
    assert "formal_capsule_not_frozen" in blockers
    assert "stage3_benchmark_not_locked" in blockers
    assert "formal_methods_not_ready" in blockers
    assert "stage2_dataset_route_relock_pending" in blockers
    assert "stage2_dataset_alignment_pending" not in blockers
    assert "sun_stage2_baseline_not_paper_faithful" not in blockers
    passes = _codes(audit, "passes")
    assert "s2_6_canonical_b0_composition_verified" in passes
    assert "b0_paper_faithful_components_present" in passes
    assert "direct_llm_runner_missing" not in blockers
    # Old contradictory blocker is removed
    assert "formal_human_review_paused" not in blockers
    # Formal route blockers remain, but the annotation freeze is now verified.
    assert "formal_gold_publication_paused" in blockers
    assert "annotation_freeze_pending" not in blockers
    assert "final_experiment_not_ready" in blockers
    assert "annotation_freeze_ready" in passes
    assert "s2_2_annotation_freeze_verified" in passes
    assert "estg150_candidate_protocol_c0_verified" in passes
    assert "estg150_c1_transport_adapter_offline_ready" in passes
    assert "estg150_c1_runtime_verified" in passes


def test_audit_checks_governance_controls() -> None:
    audit = collect_project_audit()
    passes = _codes(audit, "passes")
    assert "audit_event_log_valid" in passes
    assert "canonical_docs_present" in passes
    assert "formal_reports_versionable" in passes


def test_audit_module_has_no_network_or_llm_client_imports() -> None:
    source = (PROJECT_ROOT / "src/formal_experiment/audit.py").read_text(encoding="utf-8")
    forbidden = (
        "import requests", "import httpx", "import urllib",
        "import openai", "from openai", "RealAPITransport",
        "LLMClient", "load_dotenv",
    )
    for token in forbidden:
        assert token not in source
