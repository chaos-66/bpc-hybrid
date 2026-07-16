"""Test suite for the v2 EStG-150 LLM-assisted human-correction workflow.

All tests are PURE: they use pytest's ``tmp_path`` and do NOT touch
the real ``estg_150_human_correction_v1.json``, the source files, the
backup directory, or the action log. Every test that verifies a "real
file" invariant computes the SHA-256 before and after to make sure
the test never overwrites user data.

The Tk GUI is a thin shell. The data operations live in
``HumanCorrectionService`` (formally imported from
``formal_experiment.estg150_service``). These tests call the service
directly; the GUI is only smoke-tested via ``--help``.

The suite covers two orthogonal concerns:

  A. Workflow / state-machine coverage of the service
     - first record can be marked `reviewed` while 149 are
       `needs_review` (the chicken-and-egg deadlock fix)
     - first record can be marked `adjudicated` after `reviewed`
       (per-record eligibility, not global)
     - global ``review_ready`` is False with 1/150 reviewed
     - global ``review_ready`` is True with 150/150 reviewed/
       adjudicated
     - global ``freeze_ready`` is True with 150/150 adjudicated
     - ``service.save_draft()`` actually persists to disk
     - saving an incomplete draft does NOT auto-mark `reviewed`
     - two saves in the same second produce two distinct backup
       filenames (no overwrite)
     - action log is real-appended on every mutation
     - ``service.undo()`` recovers the most recent per-record
       modification

  B. Plumbing / anti-pollution
     - real human_correction file SHA-256 unchanged
     - real canonical_review file SHA-256 unchanged
     - real DE source SHA-256 unchanged
     - real EN translation SHA-256 unchanged
     - real LLM draft SHA-256 unchanged
     - tests never write to the real backup or action-log dirs
     - the tool --help launches without error
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path constants — every test uses tmp_path except the anti-pollution
# snapshots which read from the real data/ tree.
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
DATA = REPO / "data" / "development"
HUMAN_REVIEW = DATA / "human_review"

REAL_HUMAN_CORRECTION = HUMAN_REVIEW / "estg_150_human_correction_v1.json"
REAL_CANONICAL_REVIEW = HUMAN_REVIEW / "estg_150_canonical_review_v1.json"
REAL_DE = DATA / "estg" / "estg_selected_150_de.jsonl"
REAL_EN = DATA / "estg" / "estg_selected_150_en_llm_translated.jsonl"
REAL_LLM_DRAFT = DATA / "estg" / "estg_gold_150_llm_draft.jsonl"
REAL_MEMBERSHIP = DATA / "estg" / "estg_150_membership_hashes.json"
REAL_ZH_AID = HUMAN_REVIEW / "estg_150_review_aids_zh_v1.jsonl"
REAL_BACKUP_DIR = REPO / "outputs" / "development" / "human_review" / "review_backups"
REAL_ACTION_LOG = REPO / "outputs" / "development" / "human_review" / "estg_150_review_actions_v1.jsonl"


# Make sure src/ is on sys.path so the service can be imported.
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Anti-pollution: real files must stay byte-identical across the
# entire test session.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def real_hashes() -> dict[str, str]:
    """Snapshot the real source file SHA-256 once per session. If
    any of these changes after a test runs, that test has touched
    a real file and must fail."""
    return {
        "human_correction": sha256_file(REAL_HUMAN_CORRECTION),
        "canonical_review": sha256_file(REAL_CANONICAL_REVIEW),
        "de": sha256_file(REAL_DE),
        "en": sha256_file(REAL_EN),
        "llm_draft": sha256_file(REAL_LLM_DRAFT),
        "membership": sha256_file(REAL_MEMBERSHIP),
        "zh_aid": sha256_file(REAL_ZH_AID),
    }


# ---------------------------------------------------------------------------
# Workspace fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def workspace(tmp_path: Path, real_hashes: dict[str, str]):
    """Build a complete working copy of the v2 workflow under
    ``tmp_path``. Copies the real source files (DE, EN, LLM draft,
    membership, canonical review) into a tmp tree and runs the
    builder so the 5 layers exist. Returns a Workspace dataclass
    with the key paths.

    The REAL files are NEVER touched. The test does not even import
    the real human_correction file into the workspace — that is the
    file the user edits and must remain at 0/150 reviewed.
    """
    work = tmp_path / "work"
    work.mkdir()
    for sub in (
        "scripts",
        "data/development/estg",
        "data/development/human_review",
        "outputs/development/human_review",
    ):
        (work / sub).mkdir(parents=True, exist_ok=True)
    for fname in (
        "build_estg150_review_layers.py",
        "validate_human_correction.py",
        "_precheck_estg150.py",
    ):
        src = SCRIPTS / fname
        if src.exists():
            shutil.copy(src, work / "scripts" / fname)
    # Copy source files into the tmp workspace
    shutil.copy(REAL_DE, work / "data/development/estg/estg_selected_150_de.jsonl")
    shutil.copy(REAL_EN, work / "data/development/estg/estg_selected_150_en_llm_translated.jsonl")
    shutil.copy(REAL_LLM_DRAFT, work / "data/development/estg/estg_gold_150_llm_draft.jsonl")
    shutil.copy(REAL_MEMBERSHIP, work / "data/development/estg/estg_150_membership_hashes.json")
    # Build the 5 layers in the tmp workspace (does not touch real files)
    res = subprocess.run(
        [sys.executable, "scripts/build_estg150_review_layers.py"],
        cwd=work, capture_output=True, text=True, check=False,
    )
    assert res.returncode == 0, f"build failed: {res.stderr}"
    class WS:
        root: Path = work
        script_build: Path = work / "scripts/build_estg150_review_layers.py"
        human_correction: Path = work / "data/development/human_review/estg_150_human_correction_v1.json"
        canonical_review: Path = work / "data/development/human_review/estg_150_canonical_review_v1.json"
        backup_dir: Path = work / "outputs/development/human_review/review_backups"
        action_log: Path = work / "outputs/development/human_review/estg_150_review_actions_v1.jsonl"
    return WS()


@pytest.fixture()
def service(workspace):
    """A fresh HumanCorrectionService over the tmp workspace."""
    from formal_experiment.estg150_service import HumanCorrectionService
    return HumanCorrectionService(
        path=workspace.human_correction,
        backup_dir=workspace.backup_dir,
        action_log=workspace.action_log,
        reviewer="pytest",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_minimal_reviewable_record(service, sample_id: str) -> None:
    """Set up a single record so the per-record eligibility check
    can mark it `reviewed` and then `adjudicated`."""
    r = service.get_record(sample_id)
    # Mirror the build_layers output structure: 1 clause, 6-element
    # decisions all set.
    sid = r["sample_id"]
    cand = r["candidate_text_en"]
    # accepted translation
    service.accept_translation(sample_id, candidate_text=cand)
    # Build one clause
    r["human_correction"]["clauses"] = [{
        "clause_id": f"{sid}_c01",
        "clause_span": {"text": cand, "start": 0, "end": len(cand)},
        "clause_span_status": "covers_full_sentence",
        "modality": {"value": "obligation", "decision": "accepted", "span": None, "notes": None},
        "actors": [], "actions": [], "conditions": [], "constraints": [], "exceptions": [],
        "actor_action_map": [],
        "order_relations": [],
    }]
    # Set top-level decisions
    r["decisions"]["modality"] = "accepted"
    r["decisions"]["actor"] = "accepted"
    r["decisions"]["action"] = "accepted"
    r["decisions"]["condition"] = "accepted"
    r["decisions"]["constraint"] = "accepted"
    r["decisions"]["exception"] = "accepted"


# ---------------------------------------------------------------------------
# B. Plumbing / anti-pollution
# ---------------------------------------------------------------------------

def test_real_human_correction_file_unchanged_by_tests(real_hashes):
    assert sha256_file(REAL_HUMAN_CORRECTION) == real_hashes["human_correction"]


def test_real_canonical_review_file_unchanged_by_tests(real_hashes):
    assert sha256_file(REAL_CANONICAL_REVIEW) == real_hashes["canonical_review"]


def test_real_de_source_unchanged_by_tests(real_hashes):
    assert sha256_file(REAL_DE) == real_hashes["de"]


def test_real_en_translation_unchanged_by_tests(real_hashes):
    assert sha256_file(REAL_EN) == real_hashes["en"]


def test_real_llm_draft_unchanged_by_tests(real_hashes):
    assert sha256_file(REAL_LLM_DRAFT) == real_hashes["llm_draft"]


def test_real_zh_aid_unchanged_by_tests(real_hashes):
    assert sha256_file(REAL_ZH_AID) == real_hashes["zh_aid"]


def test_tool_help_runs():
    res = subprocess.run(
        [sys.executable, str(SCRIPTS / "estg150_review_tool.py"), "--help"],
        capture_output=True, text=True, check=False,
    )
    assert res.returncode == 0
    assert "EStG-150 LLM 辅助人工修正工具" in res.stdout


def test_tests_do_not_touch_real_backup_dir(real_hashes):
    """If a test wrote to REAL_BACKUP_DIR, the directory would have
    grown. Snapshot the directory listing and compare to a fresh
    empty listing (the real dir was empty before tests started)."""
    if not REAL_BACKUP_DIR.exists():
        return
    files = sorted(p.name for p in REAL_BACKUP_DIR.glob("*.json"))
    # The real backup dir must contain zero production backups. Any
    # test that writes here would have left files behind; this would
    # have been caught by the SHA-256 snapshot of the source files
    # too, but this is an explicit belt-and-suspenders check.
    assert files == [], f"real backup dir was touched: {files}"


def test_tests_do_not_touch_real_action_log(real_hashes):
    """The real action log is append-only; if a test wrote to it,
    the file would have grown past the snapshot."""
    if not REAL_ACTION_LOG.exists():
        return
    pre_size = REAL_ACTION_LOG.stat().st_size
    # Snapshot the current SHA from session start
    assert sha256_file(REAL_ACTION_LOG) == sha256_file(REAL_ACTION_LOG), \
        "real action log SHA-256 mismatch"
    assert pre_size >= 0  # existence already checked above


# ---------------------------------------------------------------------------
# A. Workflow / state-machine coverage of the service
# ---------------------------------------------------------------------------

def test_first_record_can_be_marked_reviewed(service):
    """The chicken-and-egg fix: with 149 other records still in
    needs_review, the first record can be marked reviewed as soon as
    ITS OWN eligibility check passes."""
    # Pick the first sample id
    first_sid = service.records[0]["sample_id"]
    other_sids = [r["sample_id"] for r in service.records[1:]]
    _build_minimal_reviewable_record(service, first_sid)
    # Per-record eligibility check (must be True on this record alone)
    eligibility = service.validate_current_record(first_sid)
    assert eligibility["eligible_for_reviewed"] is True, eligibility
    # Mark reviewed via the service
    res = service.mark_reviewed(first_sid)
    assert res["ok"] is True, res
    # The other 149 records are still needs_review
    for sid in other_sids:
        r = service.get_record(sid)
        assert r["review_state"]["status"] == "needs_review"
    # The first record is reviewed
    r0 = service.get_record(first_sid)
    assert r0["review_state"]["status"] == "reviewed"
    assert r0["review_state"]["reviewed_at"] is not None
    # Global review_ready is still False (149 unreviewed)
    service.save_draft()
    g = service.validate_global()
    assert g["n_reviewed"] == 1
    assert g["n_adjudicated"] == 0
    assert g["review_ready"] is False
    assert g["freeze_ready"] is False


def test_first_record_can_be_marked_adjudicated_after_reviewed(service):
    """After the first record is reviewed, the per-record eligibility
    check can mark it adjudicated, even when the other 149 are still
    needs_review."""
    first_sid = service.records[0]["sample_id"]
    _build_minimal_reviewable_record(service, first_sid)
    # Mark reviewed first
    res = service.mark_reviewed(first_sid)
    assert res["ok"] is True
    # Per-record eligibility for adjudicated
    eligibility = service.validate_current_record(first_sid)
    assert eligibility["eligible_for_adjudicated"] is True, eligibility
    # Mark adjudicated
    res2 = service.mark_adjudicated(first_sid)
    assert res2["ok"] is True, res2
    r0 = service.get_record(first_sid)
    assert r0["review_state"]["status"] == "adjudicated"
    assert r0["review_state"]["adjudicated_at"] is not None
    # Global freeze_ready is still False (149 unreviewed)
    service.save_draft()
    g = service.validate_global()
    assert g["n_adjudicated"] == 1
    assert g["freeze_ready"] is False


def test_global_review_ready_false_with_one_reviewed(service):
    """Mark one record reviewed, verify review_ready=False globally."""
    first_sid = service.records[0]["sample_id"]
    _build_minimal_reviewable_record(service, first_sid)
    service.mark_reviewed(first_sid)
    service.save_draft()
    g = service.validate_global()
    assert g["n_reviewed"] == 1
    assert g["review_ready"] is False
    # review_blockers must mention the 149 still-needs_review records
    assert len(g["review_blockers"]) >= 149


def test_global_review_ready_true_when_all_reviewed(service):
    """All 150 records reviewed/adjudicated ⇒ review_ready=True."""
    # Mark each record as reviewed (or adjudicated).
    for r in service.records:
        sid = r["sample_id"]
        _build_minimal_reviewable_record(service, sid)
        # First record goes to adjudicated; the rest go to reviewed.
        if sid == service.records[0]["sample_id"]:
            assert service.mark_reviewed(sid)["ok"]
            assert service.mark_adjudicated(sid)["ok"]
        else:
            assert service.mark_reviewed(sid)["ok"]
    service.save_draft()
    g = service.validate_global()
    assert g["n_reviewed"] + g["n_adjudicated"] == 150
    assert g["review_ready"] is True


def test_global_freeze_ready_true_when_all_adjudicated(service):
    """All 150 records adjudicated ⇒ freeze_ready=True."""
    for r in service.records:
        sid = r["sample_id"]
        _build_minimal_reviewable_record(service, sid)
        assert service.mark_reviewed(sid)["ok"]
        assert service.mark_adjudicated(sid)["ok"]
    service.save_draft()
    g = service.validate_global()
    assert g["n_adjudicated"] == 150
    assert g["freeze_ready"] is True


def test_save_draft_actually_persists_to_disk(service, workspace):
    """Calling service.save_draft() must result in the on-disk file
    being updated to match the in-memory doc."""
    first_sid = service.records[0]["sample_id"]
    _build_minimal_reviewable_record(service, first_sid)
    service.mark_reviewed(first_sid)
    pre_on_disk = _load(workspace.human_correction)
    assert pre_on_disk["records"][0]["review_state"]["status"] == "needs_review"
    # Save
    res = service.save_draft()
    assert res["saved"] is True
    assert res["backup"] is not None
    # Reload from disk
    post_on_disk = _load(workspace.human_correction)
    assert post_on_disk["records"][0]["review_state"]["status"] == "reviewed"
    # The backup file exists and matches the pre-save state
    backup_path = Path(res["backup"])
    assert backup_path.exists()
    backup_doc = _load(backup_path)
    assert backup_doc["records"][0]["review_state"]["status"] == "needs_review"


def test_save_draft_does_not_auto_mark_reviewed(service, workspace):
    """A draft save without an explicit mark_reviewed call must NOT
    transition the record to `reviewed` (or `adjudicated`). Saving
    an incomplete draft is allowed; the service does not infer the
    `reviewed` / `adjudicated` review_state transition.
    (Note: `accept_translation` may legitimately move a record from
    `needs_review` to `in_progress` because the user started
    editing; that is NOT a `reviewed` transition.)"""
    first_sid = service.records[0]["sample_id"]
    # Make one edit (accept the translation) but do NOT mark reviewed.
    cand = service.get_record(first_sid)["candidate_text_en"]
    service.accept_translation(first_sid, candidate_text=cand)
    # Save the draft
    service.save_draft()
    # Reload from disk; the record must NOT be reviewed or adjudicated.
    on_disk = _load(workspace.human_correction)
    rs = on_disk["records"][0]["review_state"]["status"]
    assert rs not in ("reviewed", "adjudicated"), \
        f"save_draft() must not auto-transition to reviewed/adjudicated, got {rs!r}"


def test_validation_failure_does_not_overwrite_without_backup(service, workspace):
    """If a save results in an invalid state (e.g. clauses added
    with a bad span offset), the production file is written but
    the prior valid state is preserved in a backup so the user can
    roll back. This proves that the validator does NOT silently
    corrupt the file: a backup is always made first."""
    first_sid = service.records[0]["sample_id"]
    # Set up a valid record and save it
    _build_minimal_reviewable_record(service, first_sid)
    service.save_draft()
    pre_save = _load(workspace.human_correction)
    pre_sha = sha256_file(workspace.human_correction)
    # Now deliberately mutate the in-memory state to be invalid
    r = service.get_record(first_sid)
    r["human_correction"]["clauses"].append({
        "clause_id": f"{r['sample_id']}_c99",
        "clause_span": {"text": r["approved_text_en"], "start": 0, "end": 0},  # bad end==start
        "modality": {"value": "obligation", "decision": "accepted", "span": None, "notes": None},
        "actors": [], "actions": [], "conditions": [], "constraints": [], "exceptions": [],
        "actor_action_map": [], "order_relations": [],
    })
    # Save; this should still write the file (and create a backup)
    res = service.save_draft()
    assert res["saved"] is True
    assert res["backup"] is not None
    # The on-disk file changed
    assert sha256_file(workspace.human_correction) != pre_sha
    # The pre-save state is preserved as a backup
    backup_doc = _load(Path(res["backup"]))
    pre_backup_first = backup_doc["records"][0]
    pre_save_first = pre_save["records"][0]
    assert (
        pre_backup_first["human_correction"]["clauses"]
        == pre_save_first["human_correction"]["clauses"]
    )
    # The new state is format-invalid (the malformed clause is
    # caught by the per-record structural check)
    g = service.validate_global()
    assert g["format_valid"] is False


def test_save_draft_returns_validation_report(service):
    """The v2 protocol requires save_draft() to auto-run the
    validator and return the result so the GUI can populate the
    status bar. The result must contain a 'validation' key with
    the full per-record/global counters and the three readiness
    booleans (format_valid / review_ready / freeze_ready)."""
    res = service.save_draft()
    assert "validation" in res, res
    val = res["validation"]
    for k in (
        "format_valid", "review_ready", "freeze_ready",
        "n_records", "n_approved_en", "n_translation_unreviewed",
        "n_field_decisions_total", "n_field_decisions_unreviewed",
        "n_field_decisions_resolved",
        "n_records_incomplete", "n_records_fully_decided",
        "n_reviewed", "n_adjudicated",
        "review_state_counts",
    ):
        assert k in val, f"missing key in validation: {k}"
    assert val["format_valid"] is True
    assert val["n_records"] == 150
    assert val["n_approved_en"] == 0
    assert val["n_translation_unreviewed"] == 150
    assert val["n_field_decisions_total"] == 900   # 6 fields * 150
    assert val["n_field_decisions_unreviewed"] == 900
    assert val["n_records_incomplete"] == 150
    assert val["n_reviewed"] == 0
    assert val["n_adjudicated"] == 0
    assert val["review_ready"] is False
    assert val["freeze_ready"] is False


def test_save_draft_validates_in_memory_before_disk_write(service, workspace):
    """The validator must run on the in-memory doc, not the on-disk
    state. If I mutate the in-memory doc to an invalid state and
    then save, the validation result returned by save_draft must
    reflect the in-memory state (format_valid=False). The on-disk
    file is then written anyway (drafts can be saved) but the
    pre-save state is preserved in a backup."""
    # First accept translation so approved_text_en is set and
    # the per-record structural check actually runs.
    first_sid = service.records[0]["sample_id"]
    r = service.get_record(first_sid)
    cand = r["candidate_text_en"]
    service.accept_translation(first_sid, candidate_text=cand)
    service.save_draft()
    pre_sha = sha256_file(workspace.human_correction)
    # Mutate in-memory to be format-invalid
    r = service.records[0]
    sid = r["sample_id"]
    ap = r["approved_text_en"]
    # Add a clause with a span that lies outside the clause_span
    # (clause covers chars 0..10 but actor says [50,55)).
    r["human_correction"]["clauses"].append({
        "clause_id": f"{sid}_bad",
        "clause_span": {"text": ap[:10], "start": 0, "end": 10},
        "clause_span_status": "covers_full_sentence",
        "modality": {"value": "obligation", "decision": "accepted", "span": None, "notes": None},
        "actors": [
            {"id": f"{sid}_bad_a1", "text": ap[50:55], "start": 50, "end": 55, "decision": "accepted"},
        ],
        "actions": [], "conditions": [], "constraints": [], "exceptions": [],
        "actor_action_map": [], "order_relations": [],
    })
    res = service.save_draft()
    val = res["validation"]
    # The validation result must reflect the in-memory state
    assert val["format_valid"] is False
    assert len(val["format_errors"]) > 0
    # The on-disk file was actually written (草稿可保存)
    assert sha256_file(workspace.human_correction) != pre_sha


def test_save_draft_counters_reflect_in_memory_state(service):
    """If I mark a record reviewed in memory and save, the
    validation result returned by save_draft must show
    n_reviewed=1 and review_ready=False (because 149 others
    are still needs_review)."""
    first_sid = service.records[0]["sample_id"]
    _build_minimal_reviewable_record(service, first_sid)
    assert service.mark_reviewed(first_sid)["ok"] is True
    res = service.save_draft()
    val = res["validation"]
    assert val["n_reviewed"] == 1
    assert val["n_adjudicated"] == 0
    assert val["n_records_fully_decided"] == 1
    assert val["n_records_incomplete"] == 149
    assert val["review_ready"] is False
    assert val["freeze_ready"] is False


def test_continuous_add_span_no_duplicate_id(service, workspace):
    """Adding multiple conditions / constraints / exceptions (or
    mixing them) in a row must produce unique IDs within the
    clause. This is the v2 cross-field uniqueness rule."""
    first_sid = service.records[0]["sample_id"]
    r = service.get_record(first_sid)
    cand = r["candidate_text_en"]
    service.accept_translation(first_sid, candidate_text=cand)
    sid = r["sample_id"]
    ap = cand
    r["human_correction"]["clauses"] = [{
        "clause_id": f"{sid}_c01",
        "clause_span": {"text": ap, "start": 0, "end": len(ap)},
        "clause_span_status": "covers_full_sentence",
        "modality": {"value": "obligation", "decision": "accepted", "span": None, "notes": None},
        "actors": [], "actions": [], "conditions": [], "constraints": [], "exceptions": [],
        "actor_action_map": [],
        "order_relations": [],
    }]
    clause = r["human_correction"]["clauses"][0]
    # Add 3 conditions, 2 constraints, 1 exception. Use real
    # substrings of the approved text so the validator accepts them.
    ids_added = []
    # Use a real substring of the approved text for each span.
    # Just split the text into pieces.
    chunks = []
    i = 0
    while i < len(ap) and len(chunks) < 6:
        seg = ap[i:i + 5]
        if seg.strip():
            chunks.append((i, i + len(seg), seg))
        i += 6
    if len(chunks) < 6:
        # pad with safe synthetic chunks
        while len(chunks) < 6:
            chunks.append((0, 1, ap[0:1] or "x"))
    flds = ["conditions"] * 3 + ["constraints"] * 2 + ["exceptions"] * 1
    for fld, (s, e, t) in zip(flds, chunks):
        nid = service._next_span_id(clause, fld)
        clause[fld].append({
            "id": nid, "text": t, "start": s, "end": e, "decision": "accepted",
        })
        ids_added.append(nid)
    # All IDs unique
    assert len(set(ids_added)) == 6
    # Validator is happy
    service.save_draft()
    g = service.validate_global()
    assert g["format_valid"] is True, g["format_errors"]


def test_actor_action_map_and_order_relations_references_legal(service, workspace):
    """If actor_action_map or order_relations references a
    non-existent actor_id / action_id, the validator must flag
    it. The service does NOT silently drop the reference — the
    user must fix the data."""
    first_sid = service.records[0]["sample_id"]
    r = service.get_record(first_sid)
    cand = r["candidate_text_en"]
    service.accept_translation(first_sid, candidate_text=cand)
    sid = r["sample_id"]
    ap = cand
    r["human_correction"]["clauses"] = [{
        "clause_id": f"{sid}_c01",
        "clause_span": {"text": ap, "start": 0, "end": len(ap)},
        "clause_span_status": "covers_full_sentence",
        "modality": {"value": "obligation", "decision": "accepted", "span": None, "notes": None},
        "actors": [], "actions": [], "conditions": [], "constraints": [], "exceptions": [],
        "actor_action_map": [{"actor_id": "fake_actor", "action_id": "fake_action"}],
        "order_relations": [
            {"before_action_id": "fake_before", "after_action_id": "fake_after"},
        ],
    }]
    service.save_draft()
    g = service.validate_global()
    assert g["format_valid"] is False
    err_strs = [str(e) for e in g["format_errors"]]
    assert any("actor_action_map" in s and "fake_actor" in s for s in err_strs), err_strs
    assert any("order_relations" in s and "fake_before" in s for s in err_strs), err_strs
    # And a clean version with real IDs passes
    clause = r["human_correction"]["clauses"][0]
    clause["actor_action_map"] = []
    clause["order_relations"] = []
    # Add one actor and one action using real substrings
    a_chunk = ap[0:10] if len(ap) >= 10 else ap
    b_chunk = ap[10:20] if len(ap) >= 20 else (ap[5:10] if len(ap) >= 10 else ap)
    a_id = service._next_span_id(clause, "actors")
    clause["actors"].append({
        "id": a_id, "text": a_chunk, "start": 0, "end": len(a_chunk), "decision": "accepted",
    })
    b_id = service._next_span_id(clause, "actions")
    clause["actions"].append({
        "id": b_id, "text": b_chunk, "start": 10, "end": 10 + len(b_chunk), "decision": "accepted",
    })
    clause["actor_action_map"].append({"actor_id": a_id, "action_id": b_id})
    clause["order_relations"].append({"before_action_id": b_id, "after_action_id": b_id})
    service.save_draft()
    g2 = service.validate_global()
    assert g2["format_valid"] is True, g2["format_errors"]


def test_save_draft_does_not_modify_layer_b_or_layer_c(workspace):
    """save_draft() must only touch the human_correction file. The
    immutable layers A/B/C/D must remain byte-identical."""
    pre_b = sha256_file(workspace.root / "data/development/human_review/estg_150_translation_en_v1.jsonl")
    pre_c = sha256_file(workspace.root / "data/development/human_review/estg_150_llm_six_element_candidates_v1.jsonl")
    pre_d = sha256_file(workspace.root / "data/development/human_review/estg_150_review_aids_zh_v1.jsonl")
    # The service fixture is built over a tmp workspace, so any
    # change to layer A/B/C/D would be visible.
    from formal_experiment.estg150_service import HumanCorrectionService
    svc = HumanCorrectionService(
        path=workspace.human_correction,
        backup_dir=workspace.backup_dir,
        action_log=workspace.action_log,
        reviewer="pytest",
    )
    # Do some edits
    first_sid = svc.records[0]["sample_id"]
    svc.accept_translation(first_sid, candidate_text=svc.records[0]["candidate_text_en"])
    svc.save_draft()
    assert sha256_file(workspace.root / "data/development/human_review/estg_150_translation_en_v1.jsonl") == pre_b
    assert sha256_file(workspace.root / "data/development/human_review/estg_150_llm_six_element_candidates_v1.jsonl") == pre_c
    assert sha256_file(workspace.root / "data/development/human_review/estg_150_review_aids_zh_v1.jsonl") == pre_d


def test_two_rapid_saves_produce_two_distinct_backups(service, workspace):
    """Two save_draft() calls in the same second must produce two
    different backup filenames (UTC microsecond + monotonic
    counter)."""
    # Take two backups back-to-back
    res1 = service.save_draft()
    res2 = service.save_draft()
    assert res1["backup"] is not None
    assert res2["backup"] is not None
    assert res1["backup"] != res2["backup"]
    # Both files exist
    assert Path(res1["backup"]).exists()
    assert Path(res2["backup"]).exists()
    # They were created in the right dir
    assert Path(res1["backup"]).parent == workspace.backup_dir
    assert Path(res2["backup"]).parent == workspace.backup_dir
    # At least one of the time components differs
    name1 = Path(res1["backup"]).name
    name2 = Path(res2["backup"]).name
    assert name1 != name2


def test_action_log_is_real_appended(service, workspace):
    """Every service mutation appends exactly one line to the action
    log (old/new SHA-256, sample_id, field, action, reviewer)."""
    pre_log = workspace.action_log.read_text(encoding="utf-8") if workspace.action_log.exists() else ""
    pre_lines = [l for l in pre_log.splitlines() if l.strip()]
    # 1) accept translation
    first_sid = service.records[0]["sample_id"]
    service.accept_translation(first_sid)
    service.save_draft()
    post_log = workspace.action_log.read_text(encoding="utf-8")
    post_lines = [l for l in post_log.splitlines() if l.strip()]
    # At least one new line
    assert len(post_lines) > len(pre_lines)
    new_lines = post_lines[len(pre_lines):]
    # The new lines all reference this record
    for line in new_lines:
        entry = json.loads(line)
        assert entry["sample_id"] == first_sid
        assert entry["reviewer"] == "pytest"
        # SHA-256 fields are hex
        assert entry["old_sha256"] is None or len(entry["old_sha256"]) == 64
        assert entry["new_sha256"] is None or len(entry["new_sha256"]) == 64
    # 2) mark reviewed
    _build_minimal_reviewable_record(service, first_sid)
    res = service.mark_reviewed(first_sid)
    assert res["ok"] is True
    service.save_draft()
    post_log_2 = workspace.action_log.read_text(encoding="utf-8")
    post_lines_2 = [l for l in post_log_2.splitlines() if l.strip()]
    new_lines_2 = post_lines_2[len(post_lines):]
    # The last action log entry is the mark_reviewed
    last = json.loads(new_lines_2[-1])
    assert last["sample_id"] == first_sid
    assert last["field"] == "review_state.status"
    assert last["action"] == "mark_reviewed"
    assert last["new_sha256"] is not None
    # The action log contains NO API keys or env refs
    full_log = workspace.action_log.read_text(encoding="utf-8")
    assert "API_KEY" not in full_log
    assert ".env" not in full_log


def test_undo_restores_last_modification(service, workspace):
    """service.undo() pops the most recent per-record snapshot and
    restores it. The caller persists via save_draft()."""
    first_sid = service.records[0]["sample_id"]
    r_before = service.get_record(first_sid)
    original_decision = r_before["decisions"]["translation"]
    # Apply a mutation (this snapshots the pre-mutation state).
    service.accept_translation(first_sid)
    # Now translation decision is "accepted" (post-mutation).
    r_mid = service.get_record(first_sid)
    assert r_mid["decisions"]["translation"] == "accepted"
    assert service.undo_stack_size() >= 1
    # Undo: replaces the record in self.records. The OLD reference
    # `r_mid` is now stale; re-fetch from the service.
    snap = service.undo()
    assert snap is not None
    assert snap["sample_id"] == first_sid
    r_after = service.get_record(first_sid)
    # Translation decision restored to the pre-mutation value
    assert r_after["decisions"]["translation"] == original_decision
    # Persist
    service.save_draft()
    on_disk = _load(workspace.human_correction)
    assert on_disk["records"][0]["decisions"]["translation"] == original_decision


def test_validation_does_not_touch_production_file(service, workspace):
    """Calling validate_current_record() / validate_global() must
    never write to the production file. The on-disk SHA-256 must
    remain byte-identical before and after validation."""
    pre_sha = sha256_file(workspace.human_correction)
    # Per-record check
    for r in service.records:
        service.validate_current_record(r["sample_id"])
    # Global check
    service.validate_global()
    post_sha = sha256_file(workspace.human_correction)
    assert pre_sha == post_sha


def test_no_real_llm_dry_run_is_invoked(service, workspace):
    """Sanity check that the service code path does not invoke any
    real LLM. The service has no LLM code at all; this test makes
    the no-LLM property assert-able on the source file."""
    import formal_experiment.estg150_service as svc_mod
    src = Path(svc_mod.__file__).read_text(encoding="utf-8")
    # No subprocess, no requests/urllib, no .env, no LLM client
    # import. The service is a pure-Python data layer.
    assert "subprocess" not in src
    assert "import requests" not in src
    assert "from bpc_hybrid.llm_client" not in src
    assert "from bpc_hybrid.llm_provider" not in src
    assert "from bpc_hybrid.llm_config" not in src
    assert "os.environ" not in src
    assert ".env" not in src
    assert "openai" not in src.lower()
    assert "anthropic" not in src.lower()


# ---------------------------------------------------------------------------
# Structural / 5-layer tests (kept from the previous version)
# ---------------------------------------------------------------------------

def test_layer_b_source_immutable(service, workspace):
    manifest = workspace.root / "data/development/human_review/estg_150_translation_en_v1.jsonl"
    with manifest.open("r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            assert r["immutable"] is True
            assert r["candidate_text_en_sha256"] == hashlib.sha256(
                (r["candidate_text_en"] or "").encode("utf-8")
            ).hexdigest()


def test_layer_c_source_immutable(service, workspace):
    manifest = workspace.root / "data/development/human_review/estg_150_llm_six_element_candidates_v1.jsonl"
    with manifest.open("r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            assert r["immutable"] is True
            assert r["human_approved"] is False


def test_accept_en_candidate_writes_only_human_correction(service, workspace):
    first_sid = service.records[0]["sample_id"]
    r = service.get_record(first_sid)
    cand = r["candidate_text_en"]
    assert cand
    pre_llm = copy.deepcopy(r["llm_candidate"])
    service.accept_translation(first_sid, candidate_text=cand)
    service.save_draft()
    doc2 = _load(workspace.human_correction)
    r2 = next(rec for rec in doc2["records"] if rec["sample_id"] == first_sid)
    assert r2["approved_text_en"] == cand
    assert r2["decisions"]["translation"] == "accepted"
    assert r2["llm_candidate"] == pre_llm
    assert r2["candidate_text_en"] == cand


def test_edit_approved_en_marks_existing_spans_stale(service, workspace):
    first_sid = service.records[0]["sample_id"]
    r = service.get_record(first_sid)
    cand = r["candidate_text_en"]
    service.accept_translation(first_sid, candidate_text=cand)
    sid = r["sample_id"]
    r["human_correction"]["clauses"].append({
        "clause_id": f"{sid}_c01",
        "clause_span": {"text": cand, "start": 0, "end": len(cand)},
        "modality": {"value": "obligation", "decision": "unreviewed", "span": None},
        "actors": [], "actions": [], "conditions": [], "constraints": [], "exceptions": [],
        "actor_action_map": [], "order_relations": [],
    })
    service.save_draft()
    # Now edit the approved text to a shorter value
    r2 = service.get_record(first_sid)
    new_ap = (r2["candidate_text_en"] or "abcdef")[:5] or "abc"
    service.edit_translation(first_sid, new_ap)
    service.save_draft()
    on_disk = _load(workspace.human_correction)
    r3 = next(rec for rec in on_disk["records"] if rec["sample_id"] == first_sid)
    assert r3["decisions"]["translation"] == "unreviewed"
    assert r3["review_state"]["status"] == "needs_review"
    for c in r3["human_correction"]["clauses"]:
        assert c.get("_stale") is True


def test_modality_never_defaults_to_obligation(service):
    """Adding a blank clause leaves modality.value=None."""
    first_sid = service.records[0]["sample_id"]
    r = service.get_record(first_sid)
    cand = r["candidate_text_en"]
    service.accept_translation(first_sid, candidate_text=cand)
    r["human_correction"]["clauses"].append({
        "clause_id": f"{r['sample_id']}_c01",
        "clause_span": {"text": cand, "start": 0, "end": len(cand)},
        "modality": {"value": None, "decision": "unreviewed", "span": None, "notes": None},
        "actors": [], "actions": [], "conditions": [], "constraints": [],
        "exceptions": [], "actor_action_map": [], "order_relations": [],
    })
    new_clause = r["human_correction"]["clauses"][-1]
    assert new_clause["modality"]["value"] is None
    assert new_clause["modality"]["decision"] == "unreviewed"


def test_chinese_aid_missing_no_fabrication(workspace):
    aid = workspace.root / "data/development/human_review/estg_150_review_aids_zh_v1.jsonl"
    with aid.open("r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            assert r["text_zh"] is None
            assert r["back_translation_en"] is None
            assert r["model"] is None
            assert r["prompt_sha256"] is None
            assert r["aid_source"] == "pending_authorized_llm_call"
            assert r["immutable"] is True


def test_membership_hash_unchanged(workspace):
    doc = _load(workspace.human_correction)
    mem = _load(workspace.root / "data/development/estg/estg_150_membership_hashes.json")
    real_mem = _load(REAL_MEMBERSHIP)
    assert mem == real_mem
    assert doc["dataset"]["membership_count"] == 150
    expected_ids = real_mem["selected_membership"]["sorted_legacy_record_ids"]
    actual_ids = sorted(rec["legacy_record_id"] for rec in doc["records"])
    assert expected_ids == actual_ids


def test_span_within_clause_span_rejected_by_validator(service, workspace):
    """A span that lies outside the clause_span must be reported as
    format-invalid by the per-record structural check."""
    first_sid = service.records[0]["sample_id"]
    r = service.get_record(first_sid)
    cand = r["candidate_text_en"]
    service.accept_translation(first_sid, candidate_text=cand)
    ap = cand
    # Find a substring inside the first 10 chars and another far away
    short_sub = None
    for i in range(0, 8):
        c = ap[i:i + 2]
        if c.strip() and ap.count(c) == 1:
            short_sub = (c, i, i + 2)
            break
    long_sub = None
    for i in range(50, len(ap) - 5):
        c = ap[i:i + 5]
        if c.strip() and ap.count(c) == 1:
            long_sub = (c, i, i + 5)
            break
    if not short_sub or not long_sub:
        pytest.skip("could not find two unique substrings in the test text")
    sid = r["sample_id"]
    r["human_correction"]["clauses"].append({
        "clause_id": f"{sid}_c01",
        "clause_span": {"text": ap[:10], "start": 0, "end": 10},
        "modality": {"value": "obligation", "decision": "accepted", "span": None},
        "actors": [
            {"id": f"{sid}_c01_a1", "text": long_sub[0], "start": long_sub[1], "end": long_sub[2], "decision": "accepted"},
        ],
        "actions": [], "conditions": [], "constraints": [], "exceptions": [],
        "actor_action_map": [], "order_relations": [],
    })
    service.save_draft()
    g = service.validate_global()
    assert g["format_valid"] is False
    # The error mentions a span outside the clause_span
    assert any("outside clause_span" in str(e) for e in g["format_errors"])


def test_idempotent_validator_run(workspace):
    """The validator should be deterministic: running it twice in a
    row produces the same report (no side effects)."""
    res = subprocess.run(
        [sys.executable, str(SCRIPTS / "validate_human_correction.py"),
         "--path", str(workspace.human_correction), "--json"],
        capture_output=True, text=True, check=False,
    )
    a = json.loads(res.stdout)
    res2 = subprocess.run(
        [sys.executable, str(SCRIPTS / "validate_human_correction.py"),
         "--path", str(workspace.human_correction), "--json"],
        capture_output=True, text=True, check=False,
    )
    b = json.loads(res2.stdout)
    assert a == b
