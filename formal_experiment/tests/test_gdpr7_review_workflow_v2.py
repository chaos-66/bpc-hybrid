# -*- coding: utf-8 -*-
"""Workflow tests for the GDPR7 six-element review v2 structured layer.

Everything runs against SYNTHETIC mini fixtures on ``tmp_path`` (2 rules x 5
sentences = 10 sentences).  The committed real blank surface
(``gdpr7_six_element_review_blank_v1.json``), the real v1 editable file
(``gdpr7_six_element_review_decisions_v1.json``) and the real v2 editable file
(when it exists) are NEVER written by these tests; a module-scoped autouse
fixture asserts their bytes are unchanged before and after the whole module
(real paths are only read when they exist).  The real v2 file is created only
by the acceptance owner via the v2 builder; it is never generated inside this
test module.

Coverage (mirrors the Task-C delivery spec, items a-l):

* (a) the v2 builder: structure / overwrite refusal / identity with blank /
  recorded v1 + blank sha256;
* (b) the two legal single-element forms: rule_items==null (legacy fast path)
  and rule_items==[i1] mirroring the legacy six;
* (c) two executors + two actions: legacy(i1) + structured i2 (edited values)
  passes the v2 validator;
* (d) one executor with two actions: cross-item identical actor value passes;
* (e) order_relations legal edge vs self-loop / dangling reference errors;
* (f) legal "no actor / no order": rejected actor block, orders null/[] legal;
* (g) illegal matrix: item with null decisions, orders referencing missing
  items, legacy/items[0] mirror conflict, duplicate item_id, non-verbatim
  edited value, modality outside the 4 labels;
* (h) collect_stats_v2 counting;
* (i) export_canonical_records_v2: Rules-Only-canonical-compatible rows,
  verbatim coordinates, no text-key leakage, then first-valid-span projection
  consumption of a minimal capsule built from the exported row (synthetic);
* (j) importer: legal v2 source import / illegal refusal with zero writes /
  missing confirmation refusal / non-empty v1 --upgrade refusal;
* (k) freeze verifier: v2-unfinished frozen=false, fully-decided + valid
  confirmation frozen=true;
* (l) tool pure parsers: relation-line parsing and error handling.
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
    DEFAULT_EDITABLE_V2_PATH,
    SCHEMA_BLANK,
    SCHEMA_EDITABLE,
    SCHEMA_EDITABLE_V2,
    audit_filled_document_v2,
    collect_stats_v2,
    doc_json_bytes,
    export_canonical_records_v2,
    migrate_v1_to_v2,
    recompute_doc_status_v2,
    recompute_sentence_review_state_v2,
    sentence_reviewed_v2,
    sha256_file,
    sha256_text,
    validate_blank_document,
    validate_editable_document_v2,
    validate_sentence_review_v2,
)
from bpc_hybrid.gdpr_s2_s3_projection import (  # noqa: E402
    project_external_sentence,
)
from build_gdpr7_review_editable_v2 import (  # noqa: E402
    build_editable_v2,
)
from gdpr7_review_tool_v1 import (  # noqa: E402
    parse_aam_line,
    parse_order_line,
)
from import_gdpr7_review_decisions_v1 import (  # noqa: E402
    import_decisions,
    plan_import,
    upgrade_decisions_file,
    v1_is_empty,
)
from validate_gdpr7_review_filled_v1 import (  # noqa: E402
    check_filled_v2,
)
from verify_gdpr7_review_freeze_v1 import (  # noqa: E402
    check_frozen_v2,
)

# ---------------------------------------------------------------------------
# Synthetic fixture factories (mini blank: 2 rules x 5 sentences)
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
                  candidate: dict, rule_text_start: int = 0) -> dict:
    return {
        "sample_id": sample_id,
        "sentence_idx": sentence_idx,
        "char_span": [rule_text_start, rule_text_start + len(text)],
        "text_sha256": sha256_text(text),
        "sentence_text": text,
        "candidate": candidate,
        "review": _review_block(),
    }


def _dec(decision, edited=None) -> dict:
    return {"decision": decision, "edited_value": edited}


def _filled_review(**fields) -> dict:
    """Build a fully-decided review block from six {decision, edited_value}
    fields; a ``None`` field stays undecided (only used for fast-path tests)."""
    review = _review_block()
    for field in ALL_FIELDS:
        if field in fields:
            review[field] = fields[field]
    return review


def _make_rule(rule_id: str, sentences: list[dict]) -> dict:
    return {
        "rule_id": rule_id,
        "rule_text_sha256": sha256_text(f"{rule_id} rule text"),
        "source_binding": {
            "inference_pack": "data/development/human_review/"
                              "stage3_gold_inference_v1.json",
            "inference_pack_sha256": "0" * 64,
            "rule_text_char_count": 20,
        },
        "sentences": sentences,
    }


def _article_sentences() -> list[dict]:
    """2 rules x 5 sentences.  Texts contain each actor/action phrase exactly
    once so verbatim span export is unique where tests rely on it."""
    s1_text = ("the data subject shall delete the personal data, and the "
               "controller shall keep the records.")
    return [
        make_sentence("gdpr_v2_a_s001", 0, s1_text,
                      _candidate(modality="obligation",
                                 actor="the data subject",
                                 action="delete the personal data")),
        make_sentence("gdpr_v2_a_s002", 1,
                      "the controller shall erase the personal data without "
                      "undue delay.",
                      _candidate(modality="obligation",
                                 actor="the controller",
                                 action="erase the personal data",
                                 constraint="without undue delay",
                                 constraint_kind="time_limit")),
        make_sentence("gdpr_v2_a_s003", 2,
                      "the controller may retain the personal data for a "
                      "limited period.",
                      _candidate(modality="permission",
                                 actor="the controller",
                                 action="retain the personal data",
                                 constraint="for a limited period",
                                 constraint_kind="time_limit")),
        make_sentence("gdpr_v2_a_s004", 3,
                      "the controller shall not disclose the personal data "
                      "unless the law requires disclosure.",
                      _candidate(modality="prohibition",
                                 actor="the controller",
                                 action="disclose the personal data",
                                 exception="unless the law requires disclosure",
                                 exception_kind="unless_clause")),
        make_sentence("gdpr_v2_a_s005", 4,
                      "processing must be lawful and processing must be fair.",
                      _candidate(modality="obligation",
                                 action="be lawful",
                                 condition="processing must be fair")),
    ]


def _article_b_sentences() -> list[dict]:
    s1_text = ("the controller shall erase the personal data, and the "
               "controller shall notify the authority without undue delay.")
    return [
        make_sentence("gdpr_v2_b_s001", 0, s1_text,
                      _candidate(modality="obligation",
                                 actor="the controller",
                                 action="erase the personal data",
                                 constraint="without undue delay",
                                 constraint_kind="time_limit")),
        make_sentence("gdpr_v2_b_s002", 1,
                      "the data subject has the right to obtain a copy of "
                      "the personal data.",
                      _candidate(modality="obligation",
                                 actor="the data subject",
                                 action="obtain a copy of the personal data")),
        make_sentence("gdpr_v2_b_s003", 2,
                      "the controller shall protect the personal data by "
                      "appropriate security measures.",
                      _candidate(modality="obligation",
                                 actor="the controller",
                                 action="protect the personal data",
                                 constraint="by appropriate security measures",
                                 constraint_kind="manner")),
        make_sentence("gdpr_v2_b_s004", 3,
                      "personal data may be kept no longer than necessary.",
                      _candidate(modality="permission",
                                 action="be kept",
                                 constraint="no longer than necessary",
                                 constraint_kind="time_limit")),
        make_sentence("gdpr_v2_b_s005", 4,
                      "the controller shall document every processing "
                      "activity.",
                      _candidate(modality="obligation",
                                 actor="the controller",
                                 action="document every processing activity")),
    ]


def make_blank_doc() -> dict:
    rules = [
        _make_rule("article_v2a", _article_sentences()),
        _make_rule("article_v2b", _article_b_sentences()),
    ]
    return {
        "schema_version": SCHEMA_BLANK,
        "dataset_id": "gdpr7_six_element_review_test_v2",
        "claim": "synthetic blank for unit tests",
        "status": "blank_unreviewed",
        "counts": {"rules": 2, "sentences": 10},
        "rules": rules,
    }


def _to_editable_v2(doc: dict) -> dict:
    """Transform a blank-like doc into the v2 editable layout (pure copy)."""
    out = copy.deepcopy(doc)
    out["schema_version"] = SCHEMA_EDITABLE_V2
    out["supersedes"] = SCHEMA_EDITABLE
    out["previous_editable_file"] = "gdpr7_six_element_review_decisions_v1.json"
    for _rid, sentence in _flat(out):
        review = sentence["review"]
        review.setdefault("rule_items", None)
        review.setdefault("actor_action_map", None)
        review.setdefault("order_relations", None)
    return out


def _flat(doc: dict) -> list[tuple[str, dict]]:
    out = []
    for rule in doc.get("rules", []):
        rid = rule.get("rule_id")
        for sentence in rule.get("sentences", []):
            out.append((rid, sentence))
    return out


def write_blank(tmp_path: Path) -> tuple[Path, dict]:
    blank_doc = make_blank_doc()
    problems = validate_blank_document(blank_doc)
    assert problems == [], f"fixture blank invalid: {problems}"
    blank_path = tmp_path / "blank.json"
    blank_path.write_bytes(doc_json_bytes(blank_doc))
    return blank_path, blank_doc


def build_v2_fixture(tmp_path: Path, with_v1: bool = True
                     ) -> tuple[Path, Path, Path, dict, dict]:
    """Write a mini blank + (optionally) an empty v1 editable + build the v2
    editable file; return the file handles and in-memory docs."""
    blank_path, blank_doc = write_blank(tmp_path)
    v1_path: Path | None = None
    if with_v1:
        # an all-empty v1 editable (every decision null, unreviewed)
        v1_doc = copy.deepcopy(blank_doc)
        v1_doc["schema_version"] = SCHEMA_EDITABLE
        v1_doc["status"] = "editing_unreviewed"
        v1_doc["created_at_utc"] = "2026-01-01T00:00:00Z"
        v1_doc["source_blank_sha256"] = sha256_file(blank_path)
        v1_path = tmp_path / "editable_v1.json"
        v1_path.write_bytes(doc_json_bytes(v1_doc))
    out = tmp_path / "editable_v2.json"
    editable_doc = build_editable_v2(
        blank_path=blank_path, output=out, v1_file=v1_path,
        created_at_utc="2026-01-01T00:00:00Z")
    return blank_path, out, (v1_path or tmp_path / "no_v1.json"), \
        blank_doc, editable_doc


def find_sentence_doc(doc: dict, sample_id: str) -> dict:
    for _rid, sentence in _flat(doc):
        if sentence["sample_id"] == sample_id:
            return sentence
    raise KeyError(sample_id)


def make_confirmation_event(path: Path, source_path: Path, target_path: Path,
                            blank_path: Path, reviewer: str = "reviewer-x") -> dict:
    instruction = "import the decisions I explicitly provided"
    conf = {
        "schema_version": CONFIRMATION_SCHEMA,
        "event_id": "gdpr7_review_import_confirmation_v2_test_0001",
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


def fill_legacy(sentence: dict, **field_decisions) -> dict:
    """Set the given legacy six fields on a sentence (in place)."""
    review = sentence["review"]
    for field, entry in field_decisions.items():
        review[field] = dict(entry)
    return sentence


def make_item(sample_id: str, n: int, **block_decisions) -> dict:
    item = {"item_id": f"{sample_id}.i{n}"}
    for field in ALL_FIELDS:
        item[field] = dict(block_decisions.get(
            field, {"decision": "rejected", "edited_value": None}))
    return item


def mirror_item_from(sentence: dict, n: int = 1) -> dict:
    """Build rule_items[0] as an exact mirror of the legacy six blocks."""
    review = sentence["review"]
    item = {"item_id": f"{sentence['sample_id']}.i{n}"}
    for field in ALL_FIELDS:
        item[field] = copy.deepcopy(review[field])
    return item


def fully_decide_legacy(sentence: dict) -> dict:
    """Mark all six legacy fields decided using the sentence candidate."""
    cand = sentence["candidate"] or {}
    review = sentence["review"]
    for field in ALL_FIELDS:
        value = cand.get(field)
        if value is None:
            review[field] = _dec("accepted", None)
        else:
            review[field] = _dec("accepted", None)
    return sentence


# ---------------------------------------------------------------------------
# (g) real files are byte-unchanged by this whole module
# ---------------------------------------------------------------------------

REAL_PATHS = (Path(DEFAULT_BLANK_PATH), Path(DEFAULT_EDITABLE_PATH),
              Path(DEFAULT_EDITABLE_V2_PATH))


@pytest.fixture(scope="module", autouse=True)
def real_files_unchanged():
    before = {p: sha256_file(p) for p in REAL_PATHS if p.is_file()}
    yield
    for p, expected in before.items():
        assert p.is_file(), f"real file disappeared during tests: {p}"
        assert sha256_file(p) == expected, \
            f"real file bytes changed during tests: {p}"


# ---------------------------------------------------------------------------
# (a) v2 builder
# ---------------------------------------------------------------------------


def test_builder_v2_structure_and_identity(tmp_path: Path) -> None:
    blank_path, out, v1_path, blank_doc, editable_doc = \
        build_v2_fixture(tmp_path)
    assert editable_doc["schema_version"] == SCHEMA_EDITABLE_V2
    assert editable_doc["supersedes"] == SCHEMA_EDITABLE
    assert editable_doc["previous_editable_file"] == \
        "gdpr7_six_element_review_decisions_v1.json"
    assert editable_doc["dataset_id"] == blank_doc["dataset_id"]
    assert editable_doc["status"] == "editing_unreviewed"
    assert editable_doc["counts"] == blank_doc["counts"]
    assert editable_doc["created_at_utc"] == "2026-01-01T00:00:00Z"
    assert editable_doc["source_blank_sha256"] == sha256_file(blank_path)
    assert editable_doc["v1_editable_sha256"] == sha256_file(v1_path)
    # every sentence review gained the v2 keys
    for _rid, sentence in _flat(editable_doc):
        assert set(sentence["review"]).issuperset(
            {"rule_items", "actor_action_map", "order_relations"})
    # identity with the blank surface is clean
    problems = validate_editable_document_v2(editable_doc)
    assert problems == [], problems
    audit = audit_filled_document_v2(editable_doc, blank_doc, require_blank=True)
    assert audit["errors"] == [], audit["errors"]
    # the on-disk file parses back identically
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk == editable_doc


def test_builder_v2_refuses_overwrite_and_nonempty_v1(tmp_path: Path) -> None:
    blank_path, out, _v1_path, _blank_doc, _editable_doc = \
        build_v2_fixture(tmp_path)
    # overwrite refusal
    with pytest.raises(FileExistsError):
        build_editable_v2(blank_path=blank_path, output=out)
    # non-empty v1 file is refused (never auto-copied)
    bad_v1 = tmp_path / "bad_v1.json"
    bad_doc = json.loads(blank_path.read_text(encoding="utf-8"))
    bad_doc["schema_version"] = SCHEMA_EDITABLE
    bad_doc["rules"][0]["sentences"][0]["review"]["modality"] = \
        {"decision": "accepted", "edited_value": None}
    bad_doc["rules"][0]["sentences"][0]["review"]["review_state"] = "reviewed"
    bad_v1.write_bytes(doc_json_bytes(bad_doc))
    with pytest.raises(ValueError):
        build_editable_v2(blank_path=blank_path,
                          output=tmp_path / "other_v2.json",
                          v1_file=bad_v1)


def test_builder_v2_without_v1_records_none(tmp_path: Path) -> None:
    blank_path, _out, _v1_path, _blank_doc, _editable_doc = \
        build_v2_fixture(tmp_path, with_v1=False)
    # the fixture used no v1; rebuild explicitly without a v1 file
    out2 = tmp_path / "editable_v2_no_v1.json"
    editable = build_editable_v2(blank_path=blank_path, output=out2,
                                 v1_file=None,
                                 created_at_utc="2026-01-01T00:00:00Z")
    assert editable["v1_editable_sha256"] is None


# ---------------------------------------------------------------------------
# (b) two legal single-element forms
# ---------------------------------------------------------------------------


def test_single_element_fast_path_and_mirror_form(tmp_path: Path) -> None:
    _blank_path, _out, _v1_path, blank_doc, editable_doc = \
        build_v2_fixture(tmp_path)
    s = find_sentence_doc(editable_doc, "gdpr_v2_a_s001")
    fully_decide_legacy(s)
    recompute_sentence_review_state_v2(s)
    # form 1: rule_items null (legacy fast path)
    ok, errs, _w = validate_sentence_review_v2(s)
    assert ok, errs
    assert sentence_reviewed_v2(s) is True

    # form 2: rule_items == [i1] mirroring the legacy six
    s2 = copy.deepcopy(s)
    s2["review"]["rule_items"] = [make_item("gdpr_v2_a_s001", 1)]
    # mirror i1 must equal legacy: copy legacy six entries
    i1 = s2["review"]["rule_items"][0]
    for field in ALL_FIELDS:
        i1[field] = copy.deepcopy(s2["review"][field])
    recompute_sentence_review_state_v2(s2)
    ok, errs, _w = validate_sentence_review_v2(s2)
    assert ok, errs
    assert sentence_reviewed_v2(s2) is True
    # mirror mismatch becomes an error
    s3 = copy.deepcopy(s2)
    s3["review"]["rule_items"][0]["action"] = \
        {"decision": "edited", "edited_value": "erase the personal data"}
    ok, errs, _w = validate_sentence_review_v2(s3)
    assert not ok
    assert any("镜像" in e for e in errs)


# ---------------------------------------------------------------------------
# (c) two executors + two actions (all items edited, verbatim)
# ---------------------------------------------------------------------------


def test_two_executors_two_actions(tmp_path: Path) -> None:
    _blank_path, _out, _v1_path, blank_doc, editable_doc = \
        build_v2_fixture(tmp_path)
    s = find_sentence_doc(editable_doc, "gdpr_v2_a_s001")
    # legacy (i1): actor A + action X (candidate values verbatim in text)
    r = s["review"]
    r["modality"] = _dec("accepted", None)          # obligation (candidate)
    r["actor"] = _dec("accepted", None)             # the data subject
    r["action"] = _dec("edited", "delete the personal data")
    r["condition"] = _dec("rejected", None)
    r["constraint"] = _dec("rejected", None)
    r["exception"] = _dec("rejected", None)
    # structured i1 = mirror of legacy; i2 = actor B + action Y edited
    r["rule_items"] = [
        make_item("gdpr_v2_a_s001", 1,
                  modality=r["modality"], actor=r["actor"],
                  action=r["action"]),
        make_item("gdpr_v2_a_s001", 2,
                  modality=_dec("edited", "obligation"),
                  actor=_dec("edited", "the controller"),
                  action=_dec("edited", "keep the records")),
    ]
    recompute_sentence_review_state_v2(s)
    ok, errs, warns = validate_sentence_review_v2(s)
    assert ok, errs
    assert sentence_reviewed_v2(s) is True
    # cross-item map and order are also legal here
    s["review"]["actor_action_map"] = [
        {"actor_item_id": "gdpr_v2_a_s001.i1",
         "action_item_id": "gdpr_v2_a_s001.i2"}]
    s["review"]["order_relations"] = [
        {"before_item_id": "gdpr_v2_a_s001.i1",
         "after_item_id": "gdpr_v2_a_s001.i2"}]
    ok, errs, _w = validate_sentence_review_v2(s)
    assert ok, errs


# ---------------------------------------------------------------------------
# (d) one executor with multiple actions (same actor value across items)
# ---------------------------------------------------------------------------


def test_one_executor_multiple_actions(tmp_path: Path) -> None:
    _blank_path, _out, _v1_path, blank_doc, editable_doc = \
        build_v2_fixture(tmp_path)
    s = find_sentence_doc(editable_doc, "gdpr_v2_b_s001")
    r = s["review"]
    r["modality"] = _dec("accepted", None)
    r["actor"] = _dec("accepted", None)   # the controller
    r["action"] = _dec("edited", "erase the personal data")
    r["condition"] = _dec("rejected", None)
    r["constraint"] = _dec("accepted", None)  # without undue delay
    r["exception"] = _dec("rejected", None)
    # i2 has the SAME actor value (the controller) and a second action
    r["rule_items"] = [
        make_item("gdpr_v2_b_s001", 1,
                  modality=r["modality"], actor=r["actor"],
                  action=r["action"], constraint=r["constraint"]),
        make_item("gdpr_v2_b_s001", 2,
                  modality=_dec("edited", "obligation"),
                  actor=_dec("edited", "the controller"),
                  action=_dec("edited", "notify the authority without undue "
                                        "delay")),
    ]
    recompute_sentence_review_state_v2(s)
    ok, errs, _w = validate_sentence_review_v2(s)
    assert ok, errs
    assert sentence_reviewed_v2(s) is True


# ---------------------------------------------------------------------------
# (e) order_relations legal / illegal
# ---------------------------------------------------------------------------


def test_order_relations_legal_and_illegal(tmp_path: Path) -> None:
    _blank_path, _out, _v1_path, blank_doc, editable_doc = \
        build_v2_fixture(tmp_path)
    s = find_sentence_doc(editable_doc, "gdpr_v2_b_s001")
    r = s["review"]
    for field in ALL_FIELDS:
        r[field] = _dec("accepted", None)
    # rule_items[0] must mirror the legacy six
    r["rule_items"] = [
        mirror_item_from(s),
        make_item("gdpr_v2_b_s001", 2),
    ]
    # legal edge
    r["order_relations"] = [
        {"before_item_id": "gdpr_v2_b_s001.i1",
         "after_item_id": "gdpr_v2_b_s001.i2"}]
    ok, errs, _w = validate_sentence_review_v2(s)
    assert ok, errs
    # self-loop is an error
    s2 = copy.deepcopy(s)
    s2["review"]["order_relations"] = [
        {"before_item_id": "gdpr_v2_b_s001.i1",
         "after_item_id": "gdpr_v2_b_s001.i1"}]
    ok, errs, _w = validate_sentence_review_v2(s2)
    assert not ok
    assert any("自环" in e for e in errs)
    # dangling reference is an error
    s3 = copy.deepcopy(s)
    s3["review"]["order_relations"] = [
        {"before_item_id": "gdpr_v2_b_s001.i1",
         "after_item_id": "gdpr_v2_b_s001.i9"}]
    ok, errs, _w = validate_sentence_review_v2(s3)
    assert not ok
    assert any("不存在" in e for e in errs)


# ---------------------------------------------------------------------------
# (f) legal no-actor / no-order
# ---------------------------------------------------------------------------


def test_no_actor_rejected_and_orders_empty_legal(tmp_path: Path) -> None:
    _blank_path, _out, _v1_path, blank_doc, editable_doc = \
        build_v2_fixture(tmp_path)
    s = find_sentence_doc(editable_doc, "gdpr_v2_b_s004")
    r = s["review"]
    r["modality"] = _dec("accepted", None)   # permission
    r["actor"] = _dec("rejected", None)      # no actor (legal absence)
    r["action"] = _dec("edited", "be kept")
    r["condition"] = _dec("rejected", None)
    r["constraint"] = _dec("edited", "no longer than necessary")
    r["exception"] = _dec("rejected", None)
    r["rule_items"] = [make_item("gdpr_v2_b_s004", 1,
                                 modality=r["modality"], actor=r["actor"],
                                 action=r["action"],
                                 constraint=r["constraint"])]
    # orders as empty array and as null are both legal
    r["order_relations"] = []
    r["actor_action_map"] = []
    recompute_sentence_review_state_v2(s)
    ok, errs, _w = validate_sentence_review_v2(s)
    assert ok, errs
    s2 = copy.deepcopy(s)
    s2["review"]["order_relations"] = None
    s2["review"]["actor_action_map"] = None
    ok, errs, _w = validate_sentence_review_v2(s2)
    assert ok, errs


# ---------------------------------------------------------------------------
# (g) illegal matrix
# ---------------------------------------------------------------------------


def test_illegal_matrix(tmp_path: Path) -> None:
    _blank_path, _out, _v1_path, blank_doc, editable_doc = \
        build_v2_fixture(tmp_path)

    def base() -> dict:
        s = find_sentence_doc(copy.deepcopy(editable_doc), "gdpr_v2_a_s001")
        r = s["review"]
        for field in ALL_FIELDS:
            r[field] = _dec("accepted", None)
        # rule_items[0] must mirror the legacy six
        r["rule_items"] = [
            mirror_item_from(s),
            make_item("gdpr_v2_a_s001", 2),
        ]
        return s

    # 1) item with null decisions -> sentence unfinished (error)
    s = base()
    s["review"]["rule_items"][1]["action"] = _dec(None)
    ok, errs, _w = validate_sentence_review_v2(s)
    assert not ok and any("未全决" in e for e in errs)

    # 2) order references a missing item
    s = base()
    s["review"]["order_relations"] = [
        {"before_item_id": "gdpr_v2_a_s001.i1",
         "after_item_id": "gdpr_v2_a_s001.i42"}]
    ok, errs, _w = validate_sentence_review_v2(s)
    assert not ok and any("不存在" in e for e in errs)

    # 3) legacy vs items[0] mirror conflict
    s = base()
    s["review"]["action"] = _dec("edited", "erase the personal data")
    ok, errs, _w = validate_sentence_review_v2(s)
    assert not ok and any("镜像" in e for e in errs)

    # 4) duplicate item_id
    s = base()
    s["review"]["rule_items"][1]["item_id"] = "gdpr_v2_a_s001.i1"
    ok, errs, _w = validate_sentence_review_v2(s)
    assert not ok and any("duplicate" in e or "重复" in e for e in errs)

    # 5) edited text value not a verbatim substring
    s = base()
    s["review"]["rule_items"][1]["action"] = \
        _dec("edited", "does something entirely different")
    ok, errs, _w = validate_sentence_review_v2(s)
    assert not ok
    assert any(("verbatim" in e) or ("substring" in e) or ("逐字" in e)
               for e in errs), errs

    # 6) modality outside the 4 labels
    s = base()
    s["review"]["rule_items"][1]["modality"] = _dec("edited", "must")
    ok, errs, _w = validate_sentence_review_v2(s)
    assert not ok and any("modality" in e for e in errs)

    # 7) empty rule_items array is illegal
    s = base()
    s["review"]["rule_items"] = []
    ok, errs, _w = validate_sentence_review_v2(s)
    assert not ok


# ---------------------------------------------------------------------------
# (h) collect_stats_v2 counting
# ---------------------------------------------------------------------------


def test_collect_stats_v2(tmp_path: Path) -> None:
    _blank_path, _out, _v1_path, _blank_doc, editable_doc = \
        build_v2_fixture(tmp_path)
    stats = collect_stats_v2(editable_doc)
    assert stats["sentences_total"] == 10
    assert stats["reviewed"] == 0
    assert stats["structured_sentences"] == 0
    assert stats["items_total"] == 0
    assert stats["item_blocks_decided"] == 0
    assert stats["fields_total"] == 60

    # decide sentence s001 as structured (2 items fully decided)
    s = find_sentence_doc(editable_doc, "gdpr_v2_a_s001")
    r = s["review"]
    r["modality"] = _dec("accepted", None)
    r["actor"] = _dec("accepted", None)
    r["action"] = _dec("edited", "delete the personal data")
    r["condition"] = _dec("rejected", None)
    r["constraint"] = _dec("rejected", None)
    r["exception"] = _dec("rejected", None)
    r["rule_items"] = [
        make_item("gdpr_v2_a_s001", 1, modality=r["modality"],
                  actor=r["actor"], action=r["action"]),
        make_item("gdpr_v2_a_s001", 2,
                  modality=_dec("edited", "obligation"),
                  actor=_dec("edited", "the controller"),
                  action=_dec("edited", "keep the records")),
    ]
    r["actor_action_map"] = [
        {"actor_item_id": "gdpr_v2_a_s001.i1",
         "action_item_id": "gdpr_v2_a_s001.i2"}]
    r["order_relations"] = [
        {"before_item_id": "gdpr_v2_a_s001.i1",
         "after_item_id": "gdpr_v2_a_s001.i2"}]
    recompute_sentence_review_state_v2(s)
    ok, errs, _w = validate_sentence_review_v2(s)
    assert ok, errs

    # legacy-only full decision on another sentence
    s2 = find_sentence_doc(editable_doc, "gdpr_v2_a_s002")
    for field in ALL_FIELDS:
        s2["review"][field] = _dec("accepted", None)
    recompute_sentence_review_state_v2(s2)

    stats = collect_stats_v2(editable_doc)
    assert stats["reviewed"] == 2
    assert stats["unreviewed"] == 8
    assert stats["structured_sentences"] == 1
    assert stats["items_total"] == 2
    assert stats["item_blocks_decided"] == 12
    assert stats["actor_action_map_total"] == 1
    assert stats["order_relations_total"] == 1
    # structured sentence: surface == 12 blocks (2 items x 6);
    # legacy-only sentence: surface == 6 blocks
    assert stats["decisions_total"] == 12 + 6
    assert stats["fields_total"] == 60 + 6  # +6 capacity from i2 of s001
    # item count via item_fields_total
    assert stats["item_fields_total"] == 12


# ---------------------------------------------------------------------------
# (i) canonical export -> first-valid-span consumption
# ---------------------------------------------------------------------------


def _structured_sentence_for_export(doc: dict) -> dict:
    s = find_sentence_doc(doc, "gdpr_v2_a_s001")
    r = s["review"]
    r["modality"] = _dec("accepted", None)
    r["actor"] = _dec("accepted", None)
    r["action"] = _dec("edited", "delete the personal data")
    r["condition"] = _dec("rejected", None)
    r["constraint"] = _dec("rejected", None)
    r["exception"] = _dec("rejected", None)
    r["rule_items"] = [
        make_item("gdpr_v2_a_s001", 1, modality=r["modality"],
                  actor=r["actor"], action=r["action"]),
        make_item("gdpr_v2_a_s001", 2,
                  modality=_dec("edited", "obligation"),
                  actor=_dec("edited", "the controller"),
                  action=_dec("edited", "keep the records")),
    ]
    r["actor_action_map"] = [
        {"actor_item_id": "gdpr_v2_a_s001.i1",
         "action_item_id": "gdpr_v2_a_s001.i2"}]
    r["order_relations"] = [
        {"before_item_id": "gdpr_v2_a_s001.i1",
         "after_item_id": "gdpr_v2_a_s001.i2"}]
    recompute_sentence_review_state_v2(s)
    ok, errs, _w = validate_sentence_review_v2(s)
    assert ok, errs
    return s


def test_export_canonical_and_stage3_projection(tmp_path: Path) -> None:
    _blank_path, _out, _v1_path, _blank_doc, editable_doc = \
        build_v2_fixture(tmp_path)
    _structured_sentence_for_export(editable_doc)
    result = export_canonical_records_v2(editable_doc)
    assert "rows" in result and "telemetry" in result
    rows = result["rows"]
    assert len(rows) == 10, "one canonical row per sentence"
    row = next(r for r in rows if r["sample_id"] == "gdpr_v2_a_s001")

    # shape compatibility with the Rules-Only capsule records[].record rows
    for key in ("schema_version", "sample_id", "source_id", "clauses",
                "method", "validation"):
        assert key in row, key
    clause = row["clauses"][0]
    for key in ("clause_id", "clause_span", "modality", "actors", "actions",
                "conditions", "constraints", "exceptions",
                "actor_action_map", "order_relations"):
        assert key in clause, key

    # no text key leaks anywhere in the row
    def _no_text_keys(obj) -> None:
        if isinstance(obj, dict):
            assert "text" not in obj and "normalized" not in obj, \
                f"text leak: {obj}"
            for v in obj.values():
                _no_text_keys(v)
        elif isinstance(obj, list):
            for v in obj:
                _no_text_keys(v)

    _no_text_keys(row)

    # implicit 1:1 within items AND explicit cross edges are exported
    aam = clause["actor_action_map"]
    actors = clause["actors"]
    actions = clause["actions"]
    actor_ids = {a["id"] for a in actors}
    action_ids = {a["id"] for a in actions}
    assert len(actors) == 2 and len(actions) == 2
    for edge in aam:
        assert edge["actor_id"] in actor_ids
        assert edge["action_id"] in action_ids
    # explicit cross edge actor(i1) -> action(i2) is present
    a1 = next(a for a in actors if "gdpr_v2_a_s001.c1.actor.1" in a["id"])
    x2 = next(a for a in actions if "gdpr_v2_a_s001.c1.action.2" in a["id"])
    assert {"actor_id": a1["id"], "action_id": x2["id"]} in aam

    # order relations reference action span ids
    assert len(clause["order_relations"]) == 1
    o = clause["order_relations"][0]
    assert o["before_action_id"] in action_ids
    assert o["after_action_id"] in action_ids

    # coordinates locate the verbatim values in the sentence text
    sentence = find_sentence_doc(editable_doc, "gdpr_v2_a_s001")
    stext = sentence["sentence_text"]
    for span in actors + actions:
        assert stext[span["start"]:span["end"]] in stext

    # Stage-3 read: build the minimal capsule envelope (same shape as the
    # s2_12 / direct-llm prediction rows) and run first-valid-span.
    capsule = {
        "sample_id": row["sample_id"],
        "request_status": "ok",
        "record": {"sample_id": row["sample_id"], "clauses": row["clauses"]},
        "error_category": None,
    }
    proj = project_external_sentence(capsule, stext, row["sample_id"])
    assert proj["ok"] is True, proj
    srec = proj["sentence"]
    assert srec["action"] == "delete the personal data"
    assert srec["actor"] == "the data subject"
    assert srec["modality"] == "obligation"
    # missing fields are explicitly counted (None values)
    assert srec["condition"] is None
    assert srec["constraint"] is None
    assert srec["exception"] is None


# ---------------------------------------------------------------------------
# (j) importer (v2)
# ---------------------------------------------------------------------------


def test_importer_v2_legal_import_and_guards(tmp_path: Path) -> None:
    blank_path, out, _v1_path, _blank_doc, _editable_doc = \
        build_v2_fixture(tmp_path)
    target_before = out.read_bytes()

    # build a legal v2 source with structured content on sentence s001
    source_doc = json.loads(out.read_text(encoding="utf-8"))
    s = find_sentence_doc(source_doc, "gdpr_v2_a_s001")
    r = s["review"]
    r["modality"] = _dec("accepted", None)
    r["actor"] = _dec("accepted", None)
    r["action"] = _dec("edited", "delete the personal data")
    r["condition"] = _dec("rejected", None)
    r["constraint"] = _dec("rejected", None)
    r["exception"] = _dec("rejected", None)
    r["rule_items"] = [
        make_item("gdpr_v2_a_s001", 1, modality=r["modality"],
                  actor=r["actor"], action=r["action"]),
        make_item("gdpr_v2_a_s001", 2,
                  modality=_dec("edited", "obligation"),
                  actor=_dec("edited", "the controller"),
                  action=_dec("edited", "keep the records")),
    ]
    r["actor_action_map"] = []
    r["order_relations"] = []
    recompute_sentence_review_state_v2(s)
    recompute_doc_status_v2(source_doc)
    assert audit_filled_document_v2(source_doc, json.loads(
        blank_path.read_text(encoding="utf-8")), require_blank=True)["errors"] == []
    source_path = tmp_path / "source_v2.json"
    source_path.write_bytes(doc_json_bytes(source_doc))

    # dry-run: nothing written
    dry = import_decisions(source_path=source_path, target_path=out,
                           blank_path=blank_path, confirmation_path=None,
                           apply=False)
    assert dry["exit_code"] == 0, dry["blocked"]
    assert out.read_bytes() == target_before

    # apply without confirmation -> exit 2, zero writes
    no_conf = import_decisions(source_path=source_path, target_path=out,
                               blank_path=blank_path, confirmation_path=None,
                               apply=True)
    assert no_conf["exit_code"] == 2
    assert out.read_bytes() == target_before

    # illegal source (edited value not verbatim) -> blocked apply, zero writes
    bad = copy.deepcopy(source_doc)
    find_sentence_doc(bad, "gdpr_v2_a_s001")["review"]["action"] = \
        _dec("edited", "not in the sentence at all")
    bad_path = tmp_path / "bad_v2.json"
    bad_path.write_bytes(doc_json_bytes(bad))
    plan = plan_import(bad, json.loads(out.read_text(encoding="utf-8")),
                       json.loads(blank_path.read_text(encoding="utf-8")))
    assert plan["blocked"], "illegal source must be blocked"
    conf_bad = make_confirmation_event(tmp_path / "conf_bad.json", bad_path,
                                       out, blank_path)
    blocked = import_decisions(source_path=bad_path, target_path=out,
                               blank_path=blank_path,
                               confirmation_path=tmp_path / "conf_bad.json",
                               apply=True)
    assert blocked["exit_code"] == 1
    assert out.read_bytes() == target_before

    # legal apply
    conf = make_confirmation_event(tmp_path / "conf.json", source_path, out,
                                   blank_path)
    applied = import_decisions(source_path=source_path, target_path=out,
                               blank_path=blank_path,
                               confirmation_path=tmp_path / "conf.json",
                               apply=True)
    assert applied["exit_code"] == 0, applied["blocked"]
    target_after = json.loads(out.read_text(encoding="utf-8"))
    t_s = find_sentence_doc(target_after, "gdpr_v2_a_s001")
    assert isinstance(t_s["review"]["rule_items"], list) \
        and len(t_s["review"]["rule_items"]) == 2
    assert t_s["review"]["review_state"] == "reviewed"


def test_upgrade_decisions_refuses_nonempty_v1(tmp_path: Path) -> None:
    blank_path, _out, _v1_path, _blank_doc, editable_doc = \
        build_v2_fixture(tmp_path)
    # an empty v1 file migrates cleanly (dry run, zero writes)
    empty_v1 = tmp_path / "empty_v1.json"
    empty_doc = copy.deepcopy(editable_doc)
    empty_doc["schema_version"] = SCHEMA_EDITABLE
    empty_doc.pop("supersedes", None)
    empty_doc.pop("previous_editable_file", None)
    for _rid, sentence in _flat(empty_doc):
        review = sentence["review"]
        for field in ALL_FIELDS:
            review[field] = {"decision": None, "edited_value": None}
        review["rule_items"] = None
        review["actor_action_map"] = None
        review["order_relations"] = None
        review["review_state"] = "unreviewed"
    empty_v1.write_bytes(doc_json_bytes(empty_doc))
    assert v1_is_empty(json.loads(empty_v1.read_text(encoding="utf-8"))) == []

    # non-empty v1 must be refused
    nonempty = copy.deepcopy(json.loads(empty_v1.read_text(encoding="utf-8")))
    find_sentence_doc(nonempty, "gdpr_v2_a_s001")["review"]["modality"] = \
        {"decision": "accepted", "edited_value": None}
    ne_path = tmp_path / "nonempty_v1.json"
    ne_path.write_bytes(doc_json_bytes(nonempty))
    assert v1_is_empty(nonempty) != []

    migrated = migrate_v1_to_v2(nonempty)
    assert migrated["schema_version"] == SCHEMA_EDITABLE_V2

    # the CLI-level function refuses non-empty v1 with exit code 2
    res = upgrade_decisions_file(v1_path=ne_path, blank_path=blank_path,
                                 target_path=tmp_path / "never_v2.json",
                                 confirmation_path=None, dry_run=False)
    assert res["exit_code"] == 2
    assert not (tmp_path / "never_v2.json").exists()

    # empty v1 dry-run succeeds with zero writes
    res2 = upgrade_decisions_file(v1_path=empty_v1, blank_path=blank_path,
                                  target_path=tmp_path / "upgraded_v2.json",
                                  confirmation_path=None, dry_run=True)
    assert res2["exit_code"] == 0
    assert not (tmp_path / "upgraded_v2.json").exists()


# ---------------------------------------------------------------------------
# (k) freeze verifier (v2)
# ---------------------------------------------------------------------------


def test_freeze_v2_not_frozen_and_frozen(tmp_path: Path) -> None:
    blank_path, out, _v1_path, blank_doc, editable_doc = \
        build_v2_fixture(tmp_path)
    # incomplete (blank) -> frozen=false
    res = check_frozen_v2(file_doc=editable_doc, blank_doc=blank_doc,
                          confirmation_doc=None)
    assert res["frozen"] is False
    assert any("reviewed" in r for r in res["reasons"])
    assert any("confirmation" in r for r in res["reasons"])

    # fully decided structured doc + valid confirmation -> frozen=true
    doc = copy.deepcopy(editable_doc)
    for _rid, sentence in _flat(doc):
        r = sentence["review"]
        for field in ALL_FIELDS:
            r[field] = _dec("accepted", None)
    s = find_sentence_doc(doc, "gdpr_v2_a_s001")
    r = s["review"]
    r["rule_items"] = [
        mirror_item_from(s),
        make_item("gdpr_v2_a_s001", 2),
    ]
    recompute_doc_status_v2(doc)
    doc_bytes = doc_json_bytes(doc)
    doc_path = tmp_path / "full_v2.json"
    doc_path.write_bytes(doc_bytes)

    source_path = tmp_path / "source_full_v2.json"
    source_path.write_bytes(doc_bytes)
    conf_doc = make_confirmation_event(tmp_path / "conf_freeze.json",
                                       source_path, doc_path, blank_path)
    res2 = check_frozen_v2(
        file_doc=doc, blank_doc=blank_doc, confirmation_doc=conf_doc,
        source_file_sha256=sha256_file(source_path),
        blank_file_sha256=sha256_file(blank_path))
    assert res2["frozen"] is True, res2["reasons"]
    assert res2["counts"]["items_total"] == 2
    assert res2["counts"]["item_blocks_decided"] == 12

    # remove one item block decision -> frozen=false (items 六块未全决)
    doc2 = copy.deepcopy(doc)
    find_sentence_doc(doc2, "gdpr_v2_a_s001")["review"]["rule_items"][1] \
        ["action"] = {"decision": None, "edited_value": None}
    res3 = check_frozen_v2(file_doc=doc2, blank_doc=blank_doc,
                           confirmation_doc=conf_doc,
                           source_file_sha256=sha256_file(source_path),
                           blank_file_sha256=sha256_file(blank_path))
    assert res3["frozen"] is False
    assert any("item_blocks_decided" in r for r in res3["reasons"])


# ---------------------------------------------------------------------------
# (l) tool pure parsers
# ---------------------------------------------------------------------------


def test_tool_relation_parsers() -> None:
    sid = "gdpr_v2_a_s001"
    entry, err = parse_aam_line("i1.actor>i2.action", sid)
    assert err is None
    assert entry == {"actor_item_id": f"{sid}.i1",
                     "action_item_id": f"{sid}.i2"}
    entry, err = parse_order_line("i2>i3", sid)
    assert err is None
    assert entry == {"before_item_id": f"{sid}.i2",
                     "after_item_id": f"{sid}.i3"}
    # invalid / self-loop lines report errors
    assert parse_aam_line("i1.actor>i1.action", sid)[1] is not None
    assert parse_aam_line("i0.actor>i2.action", sid)[1] is not None
    assert parse_aam_line("1.actor>2.action", sid)[1] is not None
    assert parse_aam_line("i1>i2", sid)[1] is not None
    assert parse_order_line("i1>i1", sid)[1] is not None
    assert parse_order_line("i2", sid)[1] is not None
    assert parse_order_line("i2.actor>i3.action", sid)[1] is not None
    assert parse_aam_line("", sid)[1] is not None
    assert parse_order_line("", sid)[1] is not None
