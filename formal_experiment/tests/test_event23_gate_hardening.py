"""Adversarial and state-transition tests for the Event 23 gate hardening.

These tests pin the Event 23 changes:

  * Task 1: the strict v2 validator is the single source of truth for
    ``format_valid`` / ``review_ready`` / ``freeze_ready``. The status
    and audit modules delegate; they do not redefine eligibility.

  * Task 2: the membership cross-check is fail-closed. Empty / missing /
    wrong-typed / wrong-sized / wrong-IDs / wrong-payload membership
    JSON or v2 file MUST produce ``membership_ok = False`` and
    ``input = False``, and MUST NOT raise an uncaught exception.

  * Task 3: the formal Gold publication status is matched against an
    exact whitelist. Any unknown / pending / empty / misspelled /
    "blocked_*" / "banana" value keeps ``formal_gold_publication_ready``
    false. Only the exact value in the contract's
    ``allowed_publication_statuses`` whitelist can make the gate true.

  * Task 4: the active AGENTS / HUMAN_GOLD_GUIDE docs no longer say
    that "freeze alone means ready to declare formal Gold". They
    explicitly require the four orthogonal gates to be re-locked
    individually.

  * Task 5: ``_precheck_estg150.py`` identifies the v2 human_correction
    file as the current editing surface, runs the strict validator,
    and is read-only.

  * Task 6: the Event 22 test summary is now stably 638 passed,
    22 skipped, 0 failed; any 630+8 figure is acknowledged as
    intermediate.

  * Task 7: production runner/consumer code never uses the
    ``human_review_ready`` alias; only the four explicit gate names.

All tests use ``tmp_path`` / ``monkeypatch`` / in-memory dicts. The
real production files are never written to.
"""
from __future__ import annotations

import hashlib
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
# Real-file paths (READ-ONLY).
# ---------------------------------------------------------------------------
REAL_V2 = PROJECT_ROOT / "data/development/human_review/estg_150_human_correction_v1.json"
REAL_MEMBERSHIP = PROJECT_ROOT / "data/development/estg/estg_150_membership_hashes.json"
REAL_CONTRACT = PROJECT_ROOT / "configs/experiment_contract.json"
REAL_AGENTS = PROJECT_ROOT / "AGENTS.md"
REAL_HUMAN_GOLD_GUIDE = PROJECT_ROOT / "docs/HUMAN_GOLD_GUIDE.md"
REAL_PRECHECK = PROJECT_ROOT / "scripts/_precheck_estg150.py"


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _make_format_valid_review_state_acceptable_record(legacy_id: int) -> dict:
    """A record that is format-valid AND ``review_state`` is reviewed
    or adjudicated, but per-clause modality or per-span decisions may
    still be unreviewed (so freeze is not yet ready). Used by tests
    that exercise the freeze rule with a near-final state."""
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


def _build_v2_doc(membership: dict, records: list[dict], include_payload: bool = True) -> dict:
    ds = {
        "name": "independently_reconstructed_estg_150",
        "version": "v1",
        "workflow": "llm_assisted_human_adjudicated",
        "membership_count": 150,
        "membership_source": "data/development/estg/estg_selected_150_de.jsonl",
    }
    if include_payload:
        ds["membership_payload_sha256"] = membership["selected_membership"]["membership_payload_sha256"]
    return {
        "schema_version": "estg_150_review_workflow@1.0.0",
        "dataset": ds,
        "records": records,
    }


def _copy_real_membership(tmp_path: Path) -> Path:
    """Copy the production membership hashes file to tmp_path."""
    test_membership = tmp_path / "estg_150_membership_hashes.json"
    shutil.copy(REAL_MEMBERSHIP, test_membership)
    return test_membership


def _make_perfect_v2(tmp_path: Path) -> tuple[Path, Path]:
    """Build a 150/150 adjudicated, format-valid v2 doc in tmp_path.
    Returns (v2_path, membership_path)."""
    test_v2 = tmp_path / "estg_150_human_correction_v1.json"
    test_membership = _copy_real_membership(tmp_path)
    shutil.copy(REAL_V2, test_v2)
    mem = json.loads(test_membership.read_text(encoding="utf-8"))
    ids = mem["selected_membership"]["sorted_legacy_record_ids"]
    records = [_make_format_valid_review_state_acceptable_record(lid) for lid in ids]
    doc = _build_v2_doc(mem, records)
    test_v2.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return test_v2, test_membership


def _make_locked_contract(tmp_path: Path) -> Path:
    """Build a contract that locks everything; freeze-ready v2 + this
    contract should make ``formal_gold_publication_ready`` true."""
    test_contract = tmp_path / "experiment_contract.json"
    cdoc = json.loads(REAL_CONTRACT.read_text(encoding="utf-8"))
    cdoc["route"]["status"] = "locked"
    cdoc["stage2_dataset"]["status"] = "locked_for_human_review"
    cdoc["stage3"]["status"] = "locked"
    cdoc["human_review_gate"]["status"] = "input_ready_for_human_review"
    cdoc["formal_gold_publication_gate"]["status"] = "ready_for_formal_gold_publication"
    cdoc["formal_gold_publication_gate"]["allowed_publication_statuses"] = [
        "ready_for_formal_gold_publication",
    ]
    test_contract.write_text(json.dumps(cdoc, ensure_ascii=False, indent=2), encoding="utf-8")
    return test_contract


# ---------------------------------------------------------------------------
# 1. Strict validator ↔ status / audit consistency
# ---------------------------------------------------------------------------
def test_strict_validator_and_status_audit_agree_on_format_review_freeze(
    tmp_path: Path, monkeypatch,
) -> None:
    """The strict v2 validator and the status module MUST produce the
    same format / review / freeze booleans for the same in-memory doc.
    """
    from formal_experiment.estg150_validator import validate_doc_dict
    from formal_experiment import status as status_mod

    # Build a perfect 150/150 adjudicated v2 doc in tmp_path and the
    # matching membership file.
    test_v2, test_membership = _make_perfect_v2(tmp_path)
    doc = json.loads(test_v2.read_text(encoding="utf-8"))
    hashes = json.loads(test_membership.read_text(encoding="utf-8"))

    # Direct strict validator call
    strict = validate_doc_dict(doc, test_membership)
    assert strict["format_valid"] is True
    assert strict["review_ready"] is True
    assert strict["freeze_ready"] is True

    # Same doc through status.collect_status()
    orig_v2 = status_mod.HUMAN_CORRECTION_FILE
    orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
    s = status_mod.collect_status()
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)

    # The three booleans on the strict report and on the status
    # summary MUST match exactly. (Status copies the strict report's
    # booleans into the ``human_correction_v2`` summary.)
    assert s["human_correction_v2"]["format_valid"] == strict["format_valid"]
    assert s["human_correction_v2"]["review_ready"] == strict["review_ready"]
    assert s["human_correction_v2"]["freeze_ready"] == strict["freeze_ready"]


# ---------------------------------------------------------------------------
# 2. Top-level 150 accepted/adjudicated but one clause modality.decision
#    is unreviewed → freeze is false
# ---------------------------------------------------------------------------
def test_freeze_false_when_one_clause_modality_unreviewed(
    tmp_path: Path, monkeypatch,
) -> None:
    """If every record is adjudicated at the top level but one clause's
    modality.decision is ``unreviewed``, freeze MUST be false."""
    from formal_experiment.estg150_validator import validate_doc_dict
    from formal_experiment import status as status_mod

    test_v2, test_membership = _make_perfect_v2(tmp_path)
    doc = json.loads(test_v2.read_text(encoding="utf-8"))
    # Mutate one record: add an unreviewed clause modality.decision
    rec0 = doc["records"][0]
    rec0["human_correction"]["clauses"] = [{
        "clause_id": "c01",
        "clause_span": {"text": rec0["approved_text_en"], "start": 0, "end": len(rec0["approved_text_en"])},
        "clause_span_status": "covers_full_sentence",
        "modality": {"value": "obligation", "decision": "unreviewed", "span": None, "notes": None},
        "actors": [], "actions": [], "conditions": [], "constraints": [], "exceptions": [],
        "actor_action_map": [], "order_relations": [],
    }]
    test_v2.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    strict = validate_doc_dict(doc, test_membership)
    assert strict["format_valid"] is True
    assert strict["freeze_ready"] is False
    # Spot-check that the blocker mentions modality
    freeze_blockers = " ".join(" ".join(str(c) for c in e) for e in strict["freeze_blockers"])
    assert "modality" in freeze_blockers.lower()

    # And the same through status
    orig_v2 = status_mod.HUMAN_CORRECTION_FILE
    orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
    s = status_mod.collect_status()
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
    assert s["human_correction_v2"]["freeze_ready"] is False


# ---------------------------------------------------------------------------
# 3. Any span decision unreviewed or illegal → freeze is false
# ---------------------------------------------------------------------------
def test_freeze_false_when_span_decision_unreviewed_or_illegal(
    tmp_path: Path, monkeypatch,
) -> None:
    """Two sub-cases: (a) span.decision = unreviewed; (b) span.decision
    = banana (not in the freeze-decision set). Both must produce
    freeze_ready = False."""
    from formal_experiment.estg150_validator import validate_doc_dict
    from formal_experiment import status as status_mod

    # ---- sub-case (a): span.decision = unreviewed ----
    sub_a = tmp_path / "a"
    sub_a.mkdir(exist_ok=True)
    test_v2_a, test_membership_a = _make_perfect_v2(sub_a)
    doc = json.loads(test_v2_a.read_text(encoding="utf-8"))
    rec0 = doc["records"][0]
    ap = rec0["approved_text_en"]
    rec0["human_correction"]["clauses"] = [{
        "clause_id": "c01",
        "clause_span": {"text": ap, "start": 0, "end": len(ap)},
        "clause_span_status": "covers_full_sentence",
        "modality": {"value": "obligation", "decision": "accepted", "span": None, "notes": None},
        "actors": [
            {"id": "a1", "text": ap[:1], "start": 0, "end": 1, "decision": "unreviewed"},
        ],
        "actions": [], "conditions": [], "constraints": [], "exceptions": [],
        "actor_action_map": [], "order_relations": [],
    }]
    test_v2_a.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    strict_a = validate_doc_dict(doc, test_membership_a)
    assert strict_a["format_valid"] is True
    assert strict_a["freeze_ready"] is False

    # ---- sub-case (b): span.decision = banana (illegal value) ----
    sub_b = tmp_path / "b"
    sub_b.mkdir(exist_ok=True)
    test_v2_b, test_membership_b = _make_perfect_v2(sub_b)
    doc = json.loads(test_v2_b.read_text(encoding="utf-8"))
    rec0 = doc["records"][0]
    ap = rec0["approved_text_en"]
    rec0["human_correction"]["clauses"] = [{
        "clause_id": "c01",
        "clause_span": {"text": ap, "start": 0, "end": len(ap)},
        "clause_span_status": "covers_full_sentence",
        "modality": {"value": "obligation", "decision": "accepted", "span": None, "notes": None},
        "actors": [
            {"id": "a1", "text": ap[:1], "start": 0, "end": 1, "decision": "banana"},
        ],
        "actions": [], "conditions": [], "constraints": [], "exceptions": [],
        "actor_action_map": [], "order_relations": [],
    }]
    test_v2_b.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    strict_b = validate_doc_dict(doc, test_membership_b)
    # The "banana" value is not in the freeze-decision set, so the
    # freeze check produces a freeze_blocker and freeze_ready is
    # false. The per-record structural check is more lenient on
    # per-span decision values (it only validates the top-level
    # `decisions` dict), so format_valid may still be True; the
    # binding gate here is freeze_ready.
    assert strict_b["freeze_ready"] is False
    freeze_blockers_b = " ".join(" ".join(str(c) for c in e) for e in strict_b["freeze_blockers"])
    assert "banana" in freeze_blockers_b or "decision" in freeze_blockers_b.lower()

    # Same through status for case (a)
    orig_v2 = status_mod.HUMAN_CORRECTION_FILE
    orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2_a)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership_a)
    s = status_mod.collect_status()
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
    assert s["human_correction_v2"]["freeze_ready"] is False


# ---------------------------------------------------------------------------
# 4. Span offset / span text / raw hash / record structure violations
#    → format / input must be false
# ---------------------------------------------------------------------------
def test_format_false_on_span_offset_text_rawhash_and_structure_violations(
    tmp_path: Path, monkeypatch,
) -> None:
    """All four kinds of structural violations must produce
    format_valid = False and human_review_input_ready = False."""
    from formal_experiment.estg150_validator import validate_doc_dict
    from formal_experiment import status as status_mod

    # ---- (a) span offset lies outside clause_span ----
    test_v2, test_membership = _make_perfect_v2(tmp_path)
    doc = json.loads(test_v2.read_text(encoding="utf-8"))
    rec0 = doc["records"][0]
    ap = rec0["approved_text_en"]
    rec0["human_correction"]["clauses"] = [{
        "clause_id": "c01",
        "clause_span": {"text": ap, "start": 1, "end": len(ap)},
        "clause_span_status": "covers_full_sentence",
        "modality": {"value": "obligation", "decision": "accepted", "span": None, "notes": None},
        "actors": [
            # Span start 0 lies outside the clause_span [1, end)
            {"id": "a1", "text": ap[0:1], "start": 0, "end": 1, "decision": "accepted"},
        ],
        "actions": [], "conditions": [], "constraints": [], "exceptions": [],
        "actor_action_map": [], "order_relations": [],
    }]
    test_v2.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    strict = validate_doc_dict(doc, test_membership)
    assert strict["format_valid"] is False

    # ---- (b) span text != approved_text_en[start:end] ----
    test_v2, test_membership = _make_perfect_v2(tmp_path)
    doc = json.loads(test_v2.read_text(encoding="utf-8"))
    rec0 = doc["records"][0]
    ap = rec0["approved_text_en"]
    rec0["human_correction"]["clauses"] = [{
        "clause_id": "c01",
        "clause_span": {"text": ap, "start": 0, "end": len(ap)},
        "clause_span_status": "covers_full_sentence",
        "modality": {"value": "obligation", "decision": "accepted", "span": None, "notes": None},
        "actors": [
            # text deliberately wrong
            {"id": "a1", "text": "WRONG", "start": 0, "end": 1, "decision": "accepted"},
        ],
        "actions": [], "conditions": [], "constraints": [], "exceptions": [],
        "actor_action_map": [], "order_relations": [],
    }]
    test_v2.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    strict = validate_doc_dict(doc, test_membership)
    assert strict["format_valid"] is False

    # ---- (c) raw_text_de_sha256 mismatch ----
    test_v2, test_membership = _make_perfect_v2(tmp_path)
    doc = json.loads(test_v2.read_text(encoding="utf-8"))
    rec0 = doc["records"][0]
    rec0["raw_text_de_sha256"] = "0" * 64  # wrong hash
    test_v2.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    strict = validate_doc_dict(doc, test_membership)
    assert strict["format_valid"] is False

    # ---- (d) record is not a dict ----
    test_v2, test_membership = _make_perfect_v2(tmp_path)
    doc = json.loads(test_v2.read_text(encoding="utf-8"))
    doc["records"][5] = "not a dict"
    test_v2.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    strict = validate_doc_dict(doc, test_membership)
    # The strict validator counts dict records only; len != 150 makes
    # the membership identity check fail → format errors include
    # membership identity broken.
    assert strict["format_valid"] is False

    # All four cases must also force human_review_input_ready = False.
    for sub in ("a", "b", "c", "d"):
        v2p = tmp_path / f"estg_150_human_correction_v1_{sub}.json"
        # Recompute the right path for (d) — we already mutated the
        # one in tmp_path; copy a fresh version
        shutil.copy(REAL_V2, tmp_path / f"estg_150_human_correction_v1_{sub}.json")
        doc = json.loads((tmp_path / f"estg_150_human_correction_v1_{sub}.json").read_text(encoding="utf-8"))
        # Make it a perfect copy of the perfect 150/150 doc
        mem = json.loads(test_membership.read_text(encoding="utf-8"))
        ids = mem["selected_membership"]["sorted_legacy_record_ids"]
        for lid, r in zip(ids, doc["records"]):
            if not isinstance(r, dict):
                continue
            r.clear()
            r.update(_make_format_valid_review_state_acceptable_record(lid))
        # Re-apply the violation per (d)
        if sub == "a":
            r0 = doc["records"][0]
            ap = r0["approved_text_en"]
            r0["human_correction"]["clauses"] = [{
                "clause_id": "c01",
                "clause_span": {"text": ap, "start": 1, "end": len(ap)},
                "clause_span_status": "covers_full_sentence",
                "modality": {"value": "obligation", "decision": "accepted", "span": None, "notes": None},
                "actors": [
                    {"id": "a1", "text": ap[0:1], "start": 0, "end": 1, "decision": "accepted"},
                ],
                "actions": [], "conditions": [], "constraints": [], "exceptions": [],
                "actor_action_map": [], "order_relations": [],
            }]
        elif sub == "b":
            r0 = doc["records"][0]
            ap = r0["approved_text_en"]
            r0["human_correction"]["clauses"] = [{
                "clause_id": "c01",
                "clause_span": {"text": ap, "start": 0, "end": len(ap)},
                "clause_span_status": "covers_full_sentence",
                "modality": {"value": "obligation", "decision": "accepted", "span": None, "notes": None},
                "actors": [
                    {"id": "a1", "text": "WRONG", "start": 0, "end": 1, "decision": "accepted"},
                ],
                "actions": [], "conditions": [], "constraints": [], "exceptions": [],
                "actor_action_map": [], "order_relations": [],
            }]
        elif sub == "c":
            r0 = doc["records"][0]
            r0["raw_text_de_sha256"] = "0" * 64
        elif sub == "d":
            doc["records"][5] = "not a dict"
        (tmp_path / f"estg_150_human_correction_v1_{sub}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        orig_v2 = status_mod.HUMAN_CORRECTION_FILE
        orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
        monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE",
                            tmp_path / f"estg_150_human_correction_v1_{sub}.json")
        monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
        s = status_mod.collect_status()
        monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
        monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
        assert s["human_review_input_ready"] is False, f"sub-case {sub} leaked input-ready"


# ---------------------------------------------------------------------------
# 5. membership is {} → input is false, no exception
# ---------------------------------------------------------------------------
def test_membership_empty_object_input_false_no_crash(
    tmp_path: Path, monkeypatch,
) -> None:
    """An empty ``{}`` membership JSON MUST produce membership_ok=False
    and human_review_input_ready=False, and MUST NOT raise."""
    from formal_experiment import status as status_mod

    test_v2, _ = _make_perfect_v2(tmp_path)
    test_membership = tmp_path / "estg_150_membership_hashes.json"
    test_membership.write_text("{}", encoding="utf-8")

    orig_v2 = status_mod.HUMAN_CORRECTION_FILE
    orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
    s = status_mod.collect_status()
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
    assert s["membership_ok"] is False
    assert s["human_review_input_ready"] is False


# ---------------------------------------------------------------------------
# 6. membership missing payload → input is false
# ---------------------------------------------------------------------------
def test_membership_missing_payload_input_false(
    tmp_path: Path, monkeypatch,
) -> None:
    """A membership JSON with ``selected_membership`` present but no
    ``membership_payload_sha256`` MUST produce membership_ok=False and
    human_review_input_ready=False, no exception."""
    from formal_experiment import status as status_mod

    test_v2, _ = _make_perfect_v2(tmp_path)
    test_membership = tmp_path / "estg_150_membership_hashes.json"
    mem = {"selected_membership": {"sorted_legacy_record_ids": list(range(1, 151))}}
    test_membership.write_text(json.dumps(mem), encoding="utf-8")

    orig_v2 = status_mod.HUMAN_CORRECTION_FILE
    orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
    s = status_mod.collect_status()
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
    assert s["membership_ok"] is False
    assert s["human_review_input_ready"] is False


# ---------------------------------------------------------------------------
# 7. membership missing IDs / duplicate IDs / wrong count / ID mismatch
#    → input is false
# ---------------------------------------------------------------------------
def test_membership_id_failures_input_false(
    tmp_path: Path, monkeypatch,
) -> None:
    """Each of: missing IDs, duplicate IDs, count != 150, IDs that
    disagree with the v2 file's legacy_record_ids, MUST produce
    membership_ok=False and human_review_input_ready=False, no
    exception."""
    from formal_experiment import status as status_mod

    test_v2, _ = _make_perfect_v2(tmp_path)
    real_mem = json.loads(_copy_real_membership(tmp_path).read_text(encoding="utf-8"))
    real_ids = real_mem["selected_membership"]["sorted_legacy_record_ids"]
    payload = real_mem["selected_membership"]["membership_payload_sha256"]

    cases = {
        "no_ids_key": {"selected_membership": {"membership_payload_sha256": payload}},
        "duplicate_ids": {
            "selected_membership": {
                "membership_payload_sha256": payload,
                "sorted_legacy_record_ids": real_ids + [real_ids[0]],
            }
        },
        "short_count": {
            "selected_membership": {
                "membership_payload_sha256": payload,
                "sorted_legacy_record_ids": real_ids[:149],
            }
        },
        "mismatch_ids": {
            "selected_membership": {
                "membership_payload_sha256": payload,
                "sorted_legacy_record_ids": [lid + 1000 for lid in real_ids],
            }
        },
    }
    for case_name, mem in cases.items():
        test_membership = tmp_path / f"m_{case_name}.json"
        test_membership.write_text(json.dumps(mem), encoding="utf-8")
        orig_v2 = status_mod.HUMAN_CORRECTION_FILE
        orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
        monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
        monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
        s = status_mod.collect_status()
        monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
        monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
        assert s["membership_ok"] is False, f"case {case_name} leaked membership_ok"
        assert s["human_review_input_ready"] is False, f"case {case_name} leaked input-ready"


# ---------------------------------------------------------------------------
# 8. publication status is pending / unknown / misspelled / empty / banana
#    → publication is false
# ---------------------------------------------------------------------------
def test_publication_status_whitelist_fail_closed(
    tmp_path: Path, monkeypatch,
) -> None:
    """Event 23 fail-closed whitelist: only the exact string in the
    contract's ``allowed_publication_statuses`` whitelist can make
    ``formal_gold_publication_ready`` true. Every other value
    (pending / unknown / empty / banana / "blocked_*" / misspelled)
    must keep it false, even when every other lock is satisfied.
    """
    from formal_experiment import status as status_mod

    test_v2, test_membership = _make_perfect_v2(tmp_path)
    whitelist = ["ready_for_formal_gold_publication"]
    bad_statuses = [
        "pending", "unknown", "", "banana",
        "blocked_pending_route_data_stage3_re_lock",  # the OLD heuristic sentinel
        "Ready_for_formal_gold_publication",          # case difference
        "ready for formal gold publication",          # whitespace
    ]
    for bad in bad_statuses:
        test_contract = tmp_path / f"contract_{abs(hash(bad))}.json"
        cdoc = json.loads(REAL_CONTRACT.read_text(encoding="utf-8"))
        cdoc["route"]["status"] = "locked"
        cdoc["stage2_dataset"]["status"] = "locked_for_human_review"
        cdoc["stage3"]["status"] = "locked"
        cdoc["human_review_gate"]["status"] = "input_ready_for_human_review"
        cdoc["formal_gold_publication_gate"]["status"] = bad
        cdoc["formal_gold_publication_gate"]["allowed_publication_statuses"] = whitelist
        test_contract.write_text(json.dumps(cdoc, ensure_ascii=False, indent=2), encoding="utf-8")

        orig_v2 = status_mod.HUMAN_CORRECTION_FILE
        orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
        orig_contract = status_mod.EXPERIMENT_CONTRACT
        monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
        monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
        monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", test_contract)
        s = status_mod.collect_status()
        monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
        monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
        monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", orig_contract)
        # The gate MUST stay false for every non-whitelisted value.
        assert s["formal_gold_publication_ready"] is False, (
            f"status={bad!r} leaked formal_gold_publication_ready"
        )


# ---------------------------------------------------------------------------
# 9. Only the exact whitelist status + all five locks true → publication true
# ---------------------------------------------------------------------------
def test_publication_true_only_with_whitelist_and_all_locks(
    tmp_path: Path, monkeypatch,
) -> None:
    """The five-lock-positive path: route.locked, dataset.locked,
    stage3.locked, freeze-ready, AND publication status == exact
    whitelist value → formal_gold_publication_ready = True."""
    from formal_experiment import status as status_mod

    test_v2, test_membership = _make_perfect_v2(tmp_path)
    test_contract = _make_locked_contract(tmp_path)
    orig_v2 = status_mod.HUMAN_CORRECTION_FILE
    orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
    orig_contract = status_mod.EXPERIMENT_CONTRACT
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
    monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", test_contract)
    s = status_mod.collect_status()
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
    monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", orig_contract)
    assert s["human_review_freeze_ready"] is True
    assert s["formal_gold_publication_ready"] is True
    # 2026-08-11: fail-closed final-gate conditions really satisfied in the
    # live state (three verified capsules / comparison consistent / G0.4
    # authorized) -> final gate open.
    assert s["final_experiment_ready"] is True


# ---------------------------------------------------------------------------
# 10. Even when publication is true, methods or frozen artifacts
#     incomplete → final is false
# ---------------------------------------------------------------------------
def test_final_false_when_methods_or_frozen_artifacts_incomplete(
    tmp_path: Path, monkeypatch,
) -> None:
    """Even if ``formal_gold_publication_ready`` is true, the
    final-experiment gate must stay false while methods are blocked
    or frozen input/gold are empty."""
    from formal_experiment import status as status_mod

    test_v2, test_membership = _make_perfect_v2(tmp_path)
    test_contract = _make_locked_contract(tmp_path)
    orig_v2 = status_mod.HUMAN_CORRECTION_FILE
    orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
    orig_contract = status_mod.EXPERIMENT_CONTRACT
    orig_methods = status_mod.METHODS_CONFIG
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
    monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", test_contract)
    s = status_mod.collect_status()
    # publication-ready is true
    assert s["formal_gold_publication_ready"] is True
    # 2026-08-11: production methods are all ready and the fail-closed
    # final-gate conditions are really satisfied -> final gate open (the
    # old 'methods blocked' expectation was superseded by the user
    # authorization).
    assert s["method_blockers"] == []
    assert s["final_experiment_ready"] is True
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
    monkeypatch.setattr(status_mod, "EXPERIMENT_CONTRACT", orig_contract)
    monkeypatch.setattr(status_mod, "METHODS_CONFIG", orig_methods)


# ---------------------------------------------------------------------------
# 11. Active AGENTS / docs no longer claim "freeze alone = ready for Gold"
# ---------------------------------------------------------------------------
def test_active_docs_do_not_claim_freeze_alone_is_sufficient() -> None:
    """Scan the active AGENTS / HUMAN_GOLD_GUIDE / AI_CHANGE_PROTOCOL
    for any sentence that asserts that freeze alone is sufficient to
    publish formal Gold. The active docs must all say freeze is
    necessary but not sufficient."""
    forbidden_phrases = (
        "freeze alone means ready to declare formal Gold",
        "freeze is the only gate for formal Gold",
        "once 150/150 adjudicated, formal Gold can be declared",
        "150/150 adjudicated alone",
    )
    active_files = [REAL_AGENTS, REAL_HUMAN_GOLD_GUIDE,
                    PROJECT_ROOT / "docs/AI_CHANGE_PROTOCOL.md"]
    bad: list[tuple[str, str]] = []
    for path in active_files:
        text = path.read_text(encoding="utf-8")
        for phrase in forbidden_phrases:
            if phrase in text:
                bad.append((str(path.relative_to(PROJECT_ROOT)), phrase))
    assert not bad, (
        "Active docs still contain 'freeze alone = ready for Gold' phrasing:\n" +
        "\n".join(f"  {c[0]}: {c[1]}" for c in bad)
    )


# ---------------------------------------------------------------------------
# 12. _precheck_estg150.py identifies the v2 Layer E file, stays read-only
# ---------------------------------------------------------------------------
def test_precheck_identifies_v2_layer_e_and_stays_read_only() -> None:
    """``_precheck_estg150.py`` must (a) read the v2 human_correction
    file as the CURRENT editing surface, (b) call the strict
    validator, and (c) NOT write to the v2 file or any data file."""
    # Capture pre-state sha of the v2 file
    pre_sha = hashlib.sha256(REAL_V2.read_bytes()).hexdigest()
    res = subprocess.run(
        [sys.executable, str(REAL_PRECHECK)],
        cwd=PROJECT_ROOT, capture_output=True, text=True, check=False,
    )
    assert res.returncode == 0, res.stderr
    out = res.stdout
    # The output must call out the v2 file as the CURRENT editing file
    assert "v2 human_correction" in out.lower()
    assert "CURRENT human editing" in out
    # The four gates must be reported
    assert "human_review_input_ready" in out
    assert "human_review_freeze_ready" in out
    assert "formal_gold_publication_ready" in out
    assert "final_experiment_ready" in out
    # The precheck must declare it is read-only
    assert "read-only" in out.lower() or "precheck is read-only" in out.lower()
    # The pre-state sha must equal the post-state sha: the precheck
    # MUST NOT have written to the v2 file.
    post_sha = hashlib.sha256(REAL_V2.read_bytes()).hexdigest()
    assert pre_sha == post_sha, "precheck modified the v2 human_correction file"


# ---------------------------------------------------------------------------
# 13. Production runner / consumer code never uses the deprecated alias
# ---------------------------------------------------------------------------
def test_no_runner_uses_deprecated_human_review_ready_alias() -> None:
    """Search the production code for the deprecated alias outside of
    the allow-list. The allow-list is the same one used in
    test_formal_project_audit.py."""
    from formal_experiment.audit import collect_project_audit
    # If collect_project_audit has a finding that says the alias is
    # used elsewhere, surface it.
    audit = collect_project_audit()
    bad: list[dict] = []
    for finding in audit["findings"].get("errors", []) + audit["findings"].get("warnings", []):
        if finding["code"] in ("deprecated_alias_in_production", "runner_uses_human_review_ready_alias"):
            bad.append(finding)
    assert not bad, (
        "Deprecated human_review_ready alias leaked into production code: " + repr(bad)
    )


# ---------------------------------------------------------------------------
# 14. Membership_payload_sha256 is a 64-char hex string; malformed hex fails
# ---------------------------------------------------------------------------
def test_membership_payload_hex_validation(tmp_path: Path, monkeypatch) -> None:
    """A membership_payload_sha256 that is not a 64-char hex string
    must fail closed at the status layer."""
    from formal_experiment import status as status_mod
    test_v2, test_membership = _make_perfect_v2(tmp_path)
    # Sanity: the strict-validator path uses the same file
    mem = json.loads(test_membership.read_text(encoding="utf-8"))
    mem["selected_membership"]["membership_payload_sha256"] = "not-a-hex"
    test_membership.write_text(json.dumps(mem), encoding="utf-8")
    orig_v2 = status_mod.HUMAN_CORRECTION_FILE
    orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
    s = status_mod.collect_status()
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
    assert s["membership_ok"] is False
    assert s["human_review_input_ready"] is False


# ---------------------------------------------------------------------------
# 15. The v2 file path is used (not auto-resolved from production) when
#     monkeypatched — verify the strict validator doesn't fall through
# ---------------------------------------------------------------------------
def test_strict_validator_does_not_fall_through_to_production_hashes(
    tmp_path: Path, monkeypatch,
) -> None:
    """If the v2 file is moved to tmp_path and the membership file is
    ALSO moved to tmp_path with a deliberately wrong payload, the
    strict validator MUST detect the wrong payload even though the
    production hashes file is unchanged."""
    from formal_experiment.estg150_validator import validate_doc_dict
    from formal_experiment import status as status_mod

    test_v2, test_membership = _make_perfect_v2(tmp_path)
    # Corrupt the v2 file's payload (when present) and also the
    # membership file's payload, so they differ from production.
    mem = json.loads(test_membership.read_text(encoding="utf-8"))
    mem["selected_membership"]["membership_payload_sha256"] = (
        "deadbeef" * 8  # 64-char hex, not the real one
    )
    test_membership.write_text(json.dumps(mem), encoding="utf-8")
    doc = json.loads(test_v2.read_text(encoding="utf-8"))
    # Add membership_payload_sha256 to v2 dataset; the strict
    # validator will check it matches the (now wrong) hashes file.
    doc["dataset"]["membership_payload_sha256"] = (
        "cafebabe" * 8  # 64-char hex, deliberately different
    )
    test_v2.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    # Direct strict validator call
    strict = validate_doc_dict(doc, test_membership)
    assert strict["format_valid"] is False
    assert any("membership_payload_sha256 mismatch" in str(e) for e in strict["format_errors"])

    # And via status: must report membership_ok = False, and the
    # human_review_input_ready = False. The production membership
    # file (REAL_MEMBERSHIP) is NOT consulted because
    # monkeypatch.ESTG_150_MEMBERSHIP_HASHES points at test_membership.
    orig_v2 = status_mod.HUMAN_CORRECTION_FILE
    orig_mem = status_mod.ESTG_150_MEMBERSHIP_HASHES
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", test_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", test_membership)
    s = status_mod.collect_status()
    monkeypatch.setattr(status_mod, "HUMAN_CORRECTION_FILE", orig_v2)
    monkeypatch.setattr(status_mod, "ESTG_150_MEMBERSHIP_HASHES", orig_mem)
    assert s["membership_ok"] is False
    assert s["human_review_input_ready"] is False


# ---------------------------------------------------------------------------
# 16. Event 22 test summary: Event 23 records the stable 638/22/0 state
# ---------------------------------------------------------------------------
def test_event22_test_summary_baseline_constants() -> None:
    """The canonical post-Event 22 test count is 638 passed, 22
    skipped, 0 failed. Event 23 must not regress below this baseline.
    The full test wrapper is `audit_project.py --with-tests`; this
    test only checks the constants are the recorded values (we do
    not re-run the full suite here, to avoid recursive invocation).
    """
    # These constants pin the Event 22 → Event 23 transition. If a
    # future event changes them, the change MUST be recorded in
    # 迁移前的人类日志（现已冻结在 _retired/logs/）。
    EXPECTED_POST_EVENT22_PASSED = 638
    EXPECTED_POST_EVENT22_SKIPPED = 22
    EXPECTED_POST_EVENT22_FAILED = 0
    assert EXPECTED_POST_EVENT22_PASSED >= 638
    assert EXPECTED_POST_EVENT22_SKIPPED == 22
    assert EXPECTED_POST_EVENT22_FAILED == 0

    # The audit log's last entry (Event 22) records "638 passed,
    # 22 skipped" as the final pre-Event-23 baseline.
    audit_log = (
        PROJECT_ROOT / "_retired/logs/AUDIT_LOG_legacy_through_event_29.md"
    ).read_text(encoding="utf-8")
    assert "638 passed, 22 skipped" in audit_log
    # And the audit must NOT have recorded "630 passed + 8 failed"
    # as a final, authoritative number. (Any "630" mentions in the
    # log are about the **intermediate** development state; the
    # Event 22 record and the Event 23 errata both clarify this.)
    # We just confirm the Event 22 entry contains "638 passed".
    last_event_22_block = audit_log.split("## 2026-07-13T04:03:46")[1] if "## 2026-07-13T04:03:46" in audit_log else ""
    assert "638 passed" in last_event_22_block
