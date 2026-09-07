# -*- coding: utf-8 -*-
"""Workflow tests for the GDPR7 six-element review editable layer (v1).

Everything runs against SYNTHETIC mini fixtures on ``tmp_path`` (2 rules x 4
sentences = 8 sentences / 48 review fields, containing a null-modality
sentence, a multi-modal-verb sentence and a sentence whose candidate text value
is not a verbatim substring). The committed real blank surface
(``gdpr7_six_element_review_blank_v1.json``) and the real editable file
(``gdpr7_six_element_review_decisions_v1.json``) are NEVER written by these
tests; a module-scoped autouse fixture asserts their bytes are unchanged before
and after the whole module (real paths are only read when they exist).

Coverage (mirrors the workflow spec):

* (a) the editable builder: output/blank consistency, source_blank_sha256,
  overwrite refusal;
* (b) the single-field decision matrix (invalid decision, edited without
  value, modality outside the controlled labels, text field not a verbatim
  substring, accepted/rejected carrying an edited_value, legal edited);
* (c) progress statistics (``collect_stats`` / tool ``compute_progress``);
* (d) the filled validator: fully legal document -> 0 errors; missing field
  entry -> error; reviewed state with an undecided field -> error;
* (e) the importer: dry-run without confirmation; --apply without confirmation
  refused with zero writes; confirmation hash drift refused with zero writes;
  blocked (illegal source) apply refused; legal import converges the target to
  the source;
* (f) the freeze verifier: not fully decided -> frozen=false; fully decided +
  valid confirmation -> frozen=true;
* (g) real blank/editable bytes unchanged across the whole module.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from bpc_hybrid.gdpr7_review_rules_v1 import (  # noqa: E402
    ALL_FIELDS,
    CANDIDATE_SOURCE,
    CONFIRMATION_SCHEMA,
    DEFAULT_BLANK_PATH,
    DEFAULT_EDITABLE_PATH,
    SCHEMA_BLANK,
    SCHEMA_EDITABLE,
    audit_filled_document,
    collect_stats,
    doc_json_bytes,
    sha256_file,
    sha256_text,
    validate_blank_document,
    validate_field_decision,
    validate_sentence_review,
)
from build_gdpr7_review_editable_v1 import (  # noqa: E402
    build_editable,
)
from gdpr7_review_tool_v1 import (  # noqa: E402
    compute_progress,
    list_lines,
    progress_lines,
)
from import_gdpr7_review_decisions_v1 import (  # noqa: E402
    import_decisions,
    plan_import,
)
from validate_gdpr7_review_filled_v1 import (  # noqa: E402
    check_filled,
)
from verify_gdpr7_review_freeze_v1 import (  # noqa: E402
    check_frozen,
)

BLANK_SCHEMA_VERSION = SCHEMA_BLANK
EDITABLE_SCHEMA_VERSION = SCHEMA_EDITABLE

# ---------------------------------------------------------------------------
# Synthetic fixture factories (mini blank: 2 rules x 4 sentences)
# ---------------------------------------------------------------------------


def _review_block() -> dict:
    review = {field: {"decision": None, "edited_value": None}
              for field in ALL_FIELDS}
    review["review_state"] = "unreviewed"
    review["notes"] = None
    return review


def _candidate(modality=None, actor=None, action=None, condition=None,
               constraint=None, exception=None, constraint_kind=None,
               exception_kind=None) -> dict:
    return {
        "modality": modality,
        "actor": actor,
        "action": action,
        "condition": condition,
        "constraint": constraint,
        "exception": exception,
        "constraint_kind": constraint_kind,
        "exception_kind": exception_kind,
        "candidate_source": CANDIDATE_SOURCE,
        "is_gold": False,
    }


def make_sentence(sample_id: str, sentence_idx: int, text: str,
                  candidate: dict) -> dict:
    return {
        "sample_id": sample_id,
        "sentence_idx": sentence_idx,
        "char_span": [0, len(text)],
        "text_sha256": sha256_text(text),
        "sentence_text": text,
        "candidate": candidate,
        "review": _review_block(),
    }


def _article33_sentences() -> list[dict]:
    return [
        make_sentence(
            "gdpr_article33_s001", 0,
            "In the case of a personal data breach, the controller shall "
            "notify the supervisory authority not later than 72 hours.",
            _candidate(
                modality="obligation", actor="the controller",
                action="notify the supervisory authority",
                condition="In the case of a personal data breach",
                constraint="not later than 72 hours",
                constraint_kind="time_limit")),
        make_sentence(  # null-modality sentence (candidate modality null)
            "gdpr_article33_s002", 1,
            "The controller keeps documentation of all personal data breaches.",
            _candidate(actor="The controller",
                       action="keeps documentation")),
        make_sentence(  # multi-modal-verb sentence (must + shall)
            "gdpr_article33_s003", 2,
            "The controller must erase the personal data and shall notify the "
            "supervisory authority without undue delay.",
            _candidate(
                modality="obligation", actor="the controller",
                action="erase the personal data",
                constraint="without undue delay",
                constraint_kind="time_limit")),
        make_sentence(  # candidate actor is NOT a verbatim substring
            "gdpr_article33_s004", 3,
            "The processor shall only process personal data on documented "
            "instructions of the controller.",
            _candidate(
                modality="obligation", actor="the data controller",
                action="process personal data")),
    ]


def _article7_sentences() -> list[dict]:
    return [
        make_sentence(
            "gdpr_article7_s001", 0,
            "Consent shall be given by a statement or by a clear affirmative "
            "act.",
            _candidate(modality="obligation", actor="Consent",
                       action="given by a statement or by a clear "
                              "affirmative act")),
        make_sentence(
            "gdpr_article7_s002", 1,
            "The controller shall be able to demonstrate that the data "
            "subject has consented to the processing of his or her personal "
            "data.",
            _candidate(modality="obligation", actor="The controller",
                       action="demonstrate")),
        make_sentence(
            "gdpr_article7_s003", 2,
            "The data subject shall have the right to withdraw his or her "
            "consent at any time.",
            _candidate(modality="obligation", actor="The data subject",
                       action="withdraw his or her consent at any time")),
        make_sentence(
            "gdpr_article7_s004", 3,
            "Consent shall not be considered freely given if the performance "
            "of a contract is conditional on consent.",
            _candidate(
                modality="obligation", actor=None, action=None,
                condition="if the performance of a contract is conditional "
                          "on consent")),
    ]


def make_blank_doc() -> dict:
    rules = [
        {
            "rule_id": "article33",
            "rule_text_sha256": sha256_text("article33 rule text"),
            "source_binding": {
                "inference_pack": "data/development/human_review/"
                                  "stage3_gold_inference_v1.json",
                "inference_pack_sha256": "0" * 64,
                "rule_text_char_count": 20,
            },
            "sentences": _article33_sentences(),
        },
        {
            "rule_id": "article7",
            "rule_text_sha256": sha256_text("article7 rule text"),
            "source_binding": {
                "inference_pack": "data/development/human_review/"
                                  "stage3_gold_inference_v1.json",
                "inference_pack_sha256": "0" * 64,
                "rule_text_char_count": 20,
            },
            "sentences": _article7_sentences(),
        },
    ]
    return {
        "schema_version": SCHEMA_BLANK,
        "dataset_id": "gdpr7_six_element_review_test_v1",
        "claim": "synthetic blank for unit tests",
        "status": "blank_unreviewed",
        "counts": {"rules": 2, "sentences": 8},
        "rules": rules,
    }


def write_blank(tmp_path: Path) -> tuple[Path, dict]:
    blank_doc = make_blank_doc()
    problems = validate_blank_document(blank_doc)
    assert problems == [], f"fixture blank invalid: {problems}"
    blank_path = tmp_path / "blank.json"
    blank_path.write_bytes(doc_json_bytes(blank_doc))
    return blank_path, blank_doc


def build_editable_fixture(tmp_path: Path) -> tuple[Path, Path, dict, dict]:
    """Write a mini blank + build the editable file; return the 4 handles."""
    blank_path, blank_doc = write_blank(tmp_path)
    out = tmp_path / "editable.json"
    editable_doc = build_editable(
        blank_path=blank_path, output=out,
        created_at_utc="2026-01-01T00:00:00Z")
    return blank_path, out, blank_doc, editable_doc


def _all_sentences(doc: dict) -> list[dict]:
    return [s for r in doc["rules"] for s in r["sentences"]]


def fill_all_accepted(doc: dict) -> dict:
    """Set every field of every sentence to accepted (legal), all reviewed."""
    for sentence in _all_sentences(doc):
        for field in ALL_FIELDS:
            sentence["review"][field] = {"decision": "accepted",
                                         "edited_value": None}
        sentence["review"]["review_state"] = "reviewed"
        sentence["review"]["notes"] = None
    doc["status"] = "editing_complete"
    return doc


def make_confirmation_event(path: Path, source_path: Path, target_path: Path,
                            blank_path: Path, reviewer: str = "reviewer-x") -> dict:
    instruction = "import the decisions I explicitly provided"
    conf = {
        "schema_version": CONFIRMATION_SCHEMA,
        "event_id": "gdpr7_review_import_confirmation_test_0001",
        "source_user_instruction_utf8": instruction,
        "source_user_instruction_utf8_sha256": sha256_text(instruction),
        "reviewer": reviewer,
        "source_file_sha256": sha256_file(source_path),
        "target_file_sha256": sha256_file(target_path),
        "source_blank_sha256": sha256_file(blank_path),
        "gold_created": False,
        "append_only": True,
        "created_at_utc": "2026-01-01T00:00:00Z",
    }
    path.write_bytes(doc_json_bytes(conf))
    return conf


# ---------------------------------------------------------------------------
# (g) real blank / editable files are byte-unchanged by this whole module
# ---------------------------------------------------------------------------

REAL_PATHS = (Path(DEFAULT_BLANK_PATH), Path(DEFAULT_EDITABLE_PATH))


@pytest.fixture(scope="module", autouse=True)
def real_files_unchanged():
    before = {p: sha256_file(p) for p in REAL_PATHS if p.is_file()}
    yield
    for p, expected in before.items():
        assert p.is_file(), f"real file disappeared during tests: {p}"
        assert sha256_file(p) == expected, \
            f"real file bytes changed during tests: {p}"


# ---------------------------------------------------------------------------
# (a) editable builder: blank consistency + overwrite refusal
# ---------------------------------------------------------------------------

def test_build_editable_consistent_with_blank(tmp_path: Path) -> None:
    blank_path, out, blank_doc, editable_doc = build_editable_fixture(tmp_path)
    assert editable_doc["schema_version"] == EDITABLE_SCHEMA_VERSION
    assert editable_doc["dataset_id"] == blank_doc["dataset_id"]
    assert editable_doc["status"] == "editing_unreviewed"
    assert editable_doc["counts"] == blank_doc["counts"]
    assert editable_doc["created_at_utc"] == "2026-01-01T00:00:00Z"
    assert editable_doc["source_blank_sha256"] == sha256_file(blank_path)
    # rules[] copied verbatim (identity + candidate + untouched review blocks)
    assert editable_doc["rules"] == blank_doc["rules"]
    # the blank source file itself was only read
    assert sha256_file(blank_path) == editable_doc["source_blank_sha256"]
    # the on-disk editable parses back to the same content
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk == editable_doc


def test_build_editable_refuses_overwrite(tmp_path: Path) -> None:
    blank_path, out, _blank_doc, _editable_doc = build_editable_fixture(tmp_path)
    with pytest.raises(FileExistsError):
        build_editable(blank_path=blank_path, output=out)
    # file untouched by the refusal
    assert json.loads(out.read_text(encoding="utf-8"))["schema_version"] \
        == EDITABLE_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# (b) single-field decision matrix
# ---------------------------------------------------------------------------

FIELD_MATRIX_TEXT = (
    "The controller shall notify the supervisory authority not later than "
    "72 hours."
)


@pytest.mark.parametrize("field,decision,edited,expect_ok", [
    # invalid decision value
    ("modality", "approved", None, False),
    ("actor", "needs_adjudication", None, False),
    ("action", None, None, True),  # undecided + no edited_value is legal
    ("action", None, "notify", False),  # undecided must not carry a value
    # edited: modality controlled labels
    ("modality", "edited", "obligation", True),
    ("modality", "edited", "permission", True),
    ("modality", "edited", "must", False),
    ("modality", "edited", None, False),
    ("modality", "edited", "", False),
    # edited: text fields verbatim substring
    ("actor", "edited", "The controller", True),
    ("actor", "edited", "the controller", False),
    ("actor", "edited", "the data controller", False),
    ("action", "edited", "notify the supervisory authority", True),
    ("action", "edited", "notifies the supervisory authority", False),
    ("condition", "edited", "not later than 72 hours", True),
    ("constraint", "edited", "not later than 72 hours", True),
    ("exception", "edited", "72 hours.", True),
    # accepted / rejected must carry edited_value None
    ("actor", "accepted", None, True),
    ("actor", "accepted", "the controller", False),
    ("actor", "rejected", None, True),
    ("actor", "rejected", "the controller", False),
])
def test_field_decision_matrix(field: str, decision, edited, expect_ok: bool
                               ) -> None:
    ok, errors = validate_field_decision(
        field, decision, edited, FIELD_MATRIX_TEXT)
    assert ok is expect_ok, (field, decision, edited, errors)


def test_field_decision_unknown_field() -> None:
    ok, errors = validate_field_decision("nonsense", "accepted", None, "x")
    assert ok is False and errors


def test_sentence_review_level_rules() -> None:
    text = "The controller shall notify the supervisory authority."
    sentence = make_sentence(
        "gdpr_x_s001", 0, text,
        _candidate(modality="obligation", actor="the controller",
                   action="notify the supervisory authority"))
    # untouched blank-like sentence is legal
    ok, errors, warnings = validate_sentence_review(sentence)
    assert ok, errors
    # legal edited decision on a text field
    sentence["review"]["action"] = {
        "decision": "edited", "edited_value": "notify the supervisory authority"}
    ok, errors, _w = validate_sentence_review(sentence)
    assert ok, errors
    # accepted decision that carries an edited_value is illegal
    sentence["review"]["condition"] = {
        "decision": "accepted", "edited_value": "x"}
    ok, errors, _w = validate_sentence_review(sentence)
    assert not ok
    assert any("edited_value" in e for e in errors)


# ---------------------------------------------------------------------------
# (c) progress statistics (pure functions)
# ---------------------------------------------------------------------------

def test_collect_stats_and_progress(tmp_path: Path) -> None:
    _blank_path, out, _blank_doc, editable_doc = build_editable_fixture(tmp_path)

    stats0 = collect_stats(editable_doc)
    assert stats0["sentences_total"] == 8
    assert stats0["fields_total"] == 48
    assert stats0["reviewed"] == 0
    assert stats0["unreviewed"] == 8
    assert stats0["decisions_total"] == 0
    assert stats0["per_field_decided"] == {f: 0 for f in ALL_FIELDS}

    # decide exactly one sentence (six fields) on a copy
    working = copy.deepcopy(editable_doc)
    sentence = _all_sentences(working)[0]
    for field in ALL_FIELDS:
        sentence["review"][field] = {"decision": "accepted",
                                     "edited_value": None}
    sentence["review"]["review_state"] = "reviewed"

    stats1 = collect_stats(working)
    assert stats1["reviewed"] == 1
    assert stats1["unreviewed"] == 7
    assert stats1["decisions_total"] == 6
    assert stats1["accepted"] == 6
    assert stats1["per_field_decided"] == {f: 1 for f in ALL_FIELDS}

    progress = compute_progress(working)
    assert progress["sentences_total"] == 8
    assert progress["reviewed"] == 1
    assert progress["unreviewed"] == 7
    assert progress["decisions_total"] == 6
    assert progress["fields_total"] == 48
    assert progress["remaining_unreviewed"] == 7
    lines = progress_lines(working)
    assert any("已决字段=6/48" in line for line in lines)

    # multi-modal + non-verbatim candidate sentences surface warnings
    warnings = collect_stats(editable_doc)["warnings_by_sample"]
    assert "gdpr_article33_s003" in warnings  # must + shall
    assert "gdpr_article33_s004" in warnings  # candidate actor not substring
    assert any("情态动词" in w for w in warnings["gdpr_article33_s003"])
    assert any("非逐字子串" in w for w in warnings["gdpr_article33_s004"])

    listtext = "\n".join(list_lines(editable_doc))
    assert "[1/8] gdpr_article33_s001 (article33)" in listtext


# ---------------------------------------------------------------------------
# (d) filled validator
# ---------------------------------------------------------------------------

def test_filled_validator_fully_legal_document(tmp_path: Path) -> None:
    _blank_path, _out, blank_doc, editable_doc = build_editable_fixture(tmp_path)
    fill_all_accepted(editable_doc)
    result = check_filled(editable_doc, blank_doc)
    assert result["errors"] == [], result["errors"]
    assert result["complete"] is True
    assert result["stats"]["reviewed"] == 8
    assert result["stats"]["decisions_total"] == 48
    assert result["stats"]["accepted"] == 48


def test_filled_validator_missing_field_entry_is_error(tmp_path: Path) -> None:
    _blank_path, _out, blank_doc, editable_doc = build_editable_fixture(tmp_path)
    fill_all_accepted(editable_doc)
    del _all_sentences(editable_doc)[3]["review"]["condition"]
    result = check_filled(editable_doc, blank_doc)
    assert result["errors"], "missing review field entry must be an error"
    assert any("condition" in e for e in result["errors"])


def test_filled_validator_dropped_sentence_is_error(tmp_path: Path) -> None:
    _blank_path, _out, blank_doc, editable_doc = build_editable_fixture(tmp_path)
    # tamper: drop one sentence but leave top-level counts untouched
    editable_doc["rules"][0]["sentences"].pop()
    result = check_filled(editable_doc, blank_doc)
    assert result["errors"]
    assert any("sentence count" in e for e in result["errors"])


def test_filled_validator_reviewed_but_undecided_field(tmp_path: Path) -> None:
    _blank_path, _out, blank_doc, editable_doc = build_editable_fixture(tmp_path)
    fill_all_accepted(editable_doc)
    # wipe one decision but keep the state reviewed -> hard error
    sentence = _all_sentences(editable_doc)[0]
    sentence["review"]["modality"] = {"decision": None, "edited_value": None}
    result = check_filled(editable_doc, blank_doc)
    assert result["errors"]
    assert any("reviewed" in e and "undecided" in e for e in result["errors"])


def test_filled_validator_partial_unreviewed_is_ok_but_incomplete(
        tmp_path: Path) -> None:
    _blank_path, _out, blank_doc, editable_doc = build_editable_fixture(tmp_path)
    result = check_filled(editable_doc, blank_doc)
    assert result["errors"] == []  # untouched editable: valid, nothing decided
    assert result["complete"] is False


# ---------------------------------------------------------------------------
# (e) importer
# ---------------------------------------------------------------------------

def _filled_source(tmp_path: Path, editable_path: Path) -> Path:
    """Copy the editable file and fill it completely -> user source file."""
    source_doc = json.loads(editable_path.read_text(encoding="utf-8"))
    fill_all_accepted(source_doc)
    source_path = tmp_path / "source.json"
    source_path.write_bytes(doc_json_bytes(source_doc))
    return source_path


def test_import_dry_run_and_apply_flow(tmp_path: Path) -> None:
    blank_path, out, _blank_doc, _editable_doc = build_editable_fixture(tmp_path)
    source_path = _filled_source(tmp_path, out)

    # dry-run: no confirmation needed, nothing written
    before = out.read_bytes()
    dry = import_decisions(source_path=source_path, target_path=out,
                           blank_path=blank_path, confirmation_path=None,
                           apply=False)
    assert dry["exit_code"] == 0, dry["blocked"]
    assert dry["stats"]["reviewed"] == 8
    assert dry["stats"]["decisions_total"] == 48
    assert out.read_bytes() == before, "dry-run must not write"

    # apply without confirmation -> exit 2, zero writes
    no_conf = import_decisions(source_path=source_path, target_path=out,
                               blank_path=blank_path, confirmation_path=None,
                               apply=True)
    assert no_conf["exit_code"] == 2
    assert out.read_bytes() == before, "apply without confirmation wrote data"

    # apply with confirmation whose blank sha drifted -> exit 2, zero writes
    drifted = make_confirmation_event(tmp_path / "conf_drift.json",
                                      source_path, out, blank_path)
    drifted["source_blank_sha256"] = "f" * 64
    (tmp_path / "conf_drift.json").write_bytes(doc_json_bytes(drifted))
    drift_result = import_decisions(
        source_path=source_path, target_path=out, blank_path=blank_path,
        confirmation_path=tmp_path / "conf_drift.json", apply=True)
    assert drift_result["exit_code"] == 2
    assert out.read_bytes() == before, "hash-drift apply wrote data"

    # legal apply: converges the target file to the source content
    conf = make_confirmation_event(tmp_path / "conf.json", source_path, out,
                                   blank_path)
    applied = import_decisions(
        source_path=source_path, target_path=out, blank_path=blank_path,
        confirmation_path=tmp_path / "conf.json", apply=True)
    assert applied["exit_code"] == 0, applied["blocked"]
    assert applied["applied"]["fields_applied"] == 48
    assert applied["applied"]["sentences_touched"] == 8
    target_after = json.loads(out.read_text(encoding="utf-8"))
    source_doc = json.loads(source_path.read_text(encoding="utf-8"))
    assert target_after["rules"] == source_doc["rules"]
    assert target_after["status"] == "editing_complete"
    assert (out.parent / (out.name + ".bak")).is_file(), ".bak must be created"

    # second apply is refused (confirmation target sha no longer matches)
    stale = import_decisions(source_path=source_path, target_path=out,
                             blank_path=blank_path,
                             confirmation_path=tmp_path / "conf.json",
                             apply=True)
    assert stale["exit_code"] == 2  # target_file_sha256 drift vs current file


def test_import_apply_refused_when_source_blocked(tmp_path: Path) -> None:
    blank_path, out, _blank_doc, _editable_doc = build_editable_fixture(tmp_path)
    # build an illegal source: an edited value that is not a verbatim substring
    source_doc = json.loads(out.read_text(encoding="utf-8"))
    fill_all_accepted(source_doc)
    sentence = _all_sentences(source_doc)[0]
    sentence["review"]["action"] = {
        "decision": "edited", "edited_value": "does something else entirely"}
    sentence["review"]["review_state"] = "reviewed"
    source_path = tmp_path / "bad_source.json"
    source_path.write_bytes(doc_json_bytes(source_doc))

    plan = plan_import(source_doc, json.loads(out.read_text(encoding="utf-8")),
                       json.loads(blank_path.read_text(encoding="utf-8")))
    assert plan["blocked"], "illegal source must be blocked"

    before = out.read_bytes()
    conf = make_confirmation_event(tmp_path / "conf.json", source_path, out,
                                   blank_path)
    blocked = import_decisions(source_path=source_path, target_path=out,
                               blank_path=blank_path,
                               confirmation_path=tmp_path / "conf.json",
                               apply=True)
    assert blocked["exit_code"] == 1
    assert out.read_bytes() == before, "blocked apply must not write"


def test_import_undecided_source_leaves_target_untouched(tmp_path: Path) -> None:
    blank_path, out, _blank_doc, editable_doc = build_editable_fixture(tmp_path)
    # partially decide one field of one sentence via the tool-style save path
    sentence = _all_sentences(editable_doc)[0]
    sentence["review"]["modality"] = {"decision": "accepted",
                                      "edited_value": None}
    sentence["review"]["notes"] = "partial note"
    out.write_bytes(doc_json_bytes(editable_doc))

    # source: copy of the current target with the second sentence fully decided
    source_doc = copy.deepcopy(editable_doc)
    second = _all_sentences(source_doc)[1]
    for field in ALL_FIELDS:
        second["review"][field] = {"decision": "accepted",
                                   "edited_value": None}
    second["review"]["review_state"] = "reviewed"
    source_path = tmp_path / "source_partial.json"
    source_path.write_bytes(doc_json_bytes(source_doc))

    conf = make_confirmation_event(tmp_path / "conf.json", source_path, out,
                                   blank_path)
    applied = import_decisions(source_path=source_path, target_path=out,
                               blank_path=blank_path,
                               confirmation_path=tmp_path / "conf.json",
                               apply=True)
    assert applied["exit_code"] == 0, applied["blocked"]
    target_after = json.loads(out.read_text(encoding="utf-8"))
    t0 = _all_sentences(target_after)[0]
    t1 = _all_sentences(target_after)[1]
    # pre-existing partial decision on sentence 0 preserved
    assert t0["review"]["modality"]["decision"] == "accepted"
    assert t0["review"]["notes"] == "partial note"
    # sentence 0 stayed unreviewed (only 1/6 decided)
    assert t0["review"]["review_state"] == "unreviewed"
    # sentence 1 became fully reviewed
    assert t1["review"]["review_state"] == "reviewed"


# ---------------------------------------------------------------------------
# (f) freeze verifier
# ---------------------------------------------------------------------------

def test_freeze_not_frozen_when_incomplete(tmp_path: Path) -> None:
    blank_path, _out, blank_doc, editable_doc = build_editable_fixture(tmp_path)
    result = check_frozen(file_doc=editable_doc, blank_doc=blank_doc,
                          confirmation_doc=None)
    assert result["frozen"] is False
    assert any("reviewed" in r for r in result["reasons"])
    assert any("confirmation" in r for r in result["reasons"])


def test_freeze_frozen_when_complete_with_confirmation(tmp_path: Path) -> None:
    blank_path, out, blank_doc, _editable_doc = build_editable_fixture(tmp_path)
    editable_doc = json.loads(out.read_text(encoding="utf-8"))
    fill_all_accepted(editable_doc)

    source_doc = copy.deepcopy(editable_doc)
    source_path = tmp_path / "source.json"
    source_path.write_bytes(doc_json_bytes(source_doc))

    conf_doc = make_confirmation_event(tmp_path / "conf.json", source_path,
                                       out, blank_path)
    result = check_frozen(
        file_doc=editable_doc, blank_doc=blank_doc, confirmation_doc=conf_doc,
        source_file_sha256=sha256_file(source_path),
        blank_file_sha256=sha256_file(blank_path))
    assert result["frozen"] is True, result["reasons"]
    assert result["counts"]["reviewed"] == 8
    assert result["counts"]["decisions_total"] == 48


def test_freeze_rejects_undecided_field_with_valid_confirmation(
        tmp_path: Path) -> None:
    blank_path, out, blank_doc, _editable_doc = build_editable_fixture(tmp_path)
    editable_doc = json.loads(out.read_text(encoding="utf-8"))
    fill_all_accepted(editable_doc)
    _all_sentences(editable_doc)[0]["review"]["exception"] = {
        "decision": None, "edited_value": None}
    editable_doc["status"] = "editing_in_progress"

    source_doc = copy.deepcopy(editable_doc)
    source_path = tmp_path / "source.json"
    source_path.write_bytes(doc_json_bytes(source_doc))
    conf_doc = make_confirmation_event(tmp_path / "conf.json", source_path,
                                       out, blank_path)
    result = check_frozen(
        file_doc=editable_doc, blank_doc=blank_doc, confirmation_doc=conf_doc,
        source_file_sha256=sha256_file(source_path),
        blank_file_sha256=sha256_file(blank_path))
    assert result["frozen"] is False
    assert any("decisions_total" in r for r in result["reasons"])


# ---------------------------------------------------------------------------
# sanity: the synthetic blank/editable fixtures satisfy every shared invariant
# ---------------------------------------------------------------------------

def test_fixture_blank_and_editable_audit_clean(tmp_path: Path) -> None:
    blank_path, _out, blank_doc, editable_doc = build_editable_fixture(tmp_path)
    assert validate_blank_document(blank_doc) == []
    audit = audit_filled_document(editable_doc, blank_doc, require_blank=True)
    assert audit["errors"] == [], audit["errors"]
    # editable schema + source_blank_sha256 record present
    assert editable_doc["source_blank_sha256"] == sha256_file(blank_path)
    assert blank_path.read_bytes() == json.dumps(
        blank_doc, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
