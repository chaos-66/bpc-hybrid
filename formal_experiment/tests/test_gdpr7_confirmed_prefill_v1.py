"""Content-bound human import: preserve evidence and never invent case Gold."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "confirmed_prefill", ROOT / "scripts/import_gdpr7_confirmed_prefill_v1.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@pytest.fixture
def inputs():
    proposals = json.loads((m.DRAFT / "proposals.json").read_bytes())
    source = json.loads((ROOT / m.BOUND_PATHS[0]).read_bytes())
    hashes = {rel: m.sha((ROOT / rel).read_bytes()) for rel in m.BOUND_PATHS}
    confirmation = {"schema_version": "gdpr7_prefill_user_confirmation@1.0.0",
                    "event_id": "synthetic-test-confirmation", "reviewer": "test-human",
                    "human_confirmed": True, "user_message_verbatim": "Test fixture only",
                    "scope": "accept_current_prefill_documents_without_edits",
                    "source_sha256": hashes}
    return proposals, source, confirmation, hashes


def test_all_confirmed_without_modality_or_evidence_loss(inputs):
    draft, source, event, hashes = inputs
    unchanged = copy.deepcopy(draft)
    doc, case = m.build_confirmed(*inputs)
    assert draft == unchanged
    assert doc["counts"] == {"rules": 9, "sentences": 74, "items": 92,
                             "anchored_spans": 320, "human_confirmed": 74,
                             "item_field_decisions": 552}
    assert doc["is_gold"] is False and doc["publication_authorized"] is False
    rows = {r["sample_id"]: r for r in doc["records"]}
    mixed = rows["gdpr_article17_s001"]["rule_items"]
    assert [i["modality"] for i in mixed] == ["permission", "obligation"]
    assert mixed[0]["actor"][0]["text"] == "The data subject"
    # Same spelling occurs twice: preserve the controller occurrence attached
    # to the second (obligation) norm, rather than re-locating with find().
    original = next(r for r in draft["records"] if r["sample_id"] == "gdpr_article17_s001")
    assert mixed[1]["actor"] == original["suggested_rule_items"][1]["actor"]
    assert len(rows["gdpr_article16_s001"]["rule_items"][0]["action"]) == 2
    for before, after in zip(draft["records"], doc["records"]):
        for key in ("context_links", "temporal_suggestions", "review_note_zh"):
            assert before[key] == after[key]


@pytest.mark.parametrize("field,value", [
    ("human_confirmed", False), ("reviewer", ""), ("scope", "publish_all_gold"),
    ("event_id", ""), ("user_message_verbatim", ""), ("source_sha256", {}),
])
def test_missing_or_mismatched_confirmation_refused(inputs, field, value):
    inputs[2][field] = value
    with pytest.raises(ValueError):
        m.build_confirmed(*inputs)


@pytest.mark.parametrize("damage", ["text", "offset", "identity", "actor_reference", "context_reference"])
def test_invalid_evidence_refused(inputs, damage):
    draft = inputs[0]
    row = next(r for r in draft["records"] if r["sample_id"] == "gdpr_article33_s001")
    item = row["suggested_rule_items"][0]
    if damage == "text":
        row["sentence_text"] += " Modified."
    elif damage == "offset":
        item["actor"][0]["start"] += 1
    elif damage == "identity":
        row["rule_text_sha256"] = "0" * 64
    elif damage == "actor_reference":
        item["actor_action_map"][0]["actor_span_index"] = 100
    else:
        row["context_links"] = ["not_a_real_sample"]
    with pytest.raises(ValueError):
        m.build_confirmed(*inputs)


def test_case_confirmation_keeps_acknowledged_uncertainty(inputs):
    _, case = m.build_confirmed(*inputs)
    assert case["document_content_acknowledged"] is True
    assert case["article22_s001_modality"] == "prohibition"
    assert case["whole_process_compliant"] is None
    assert case["control_gold_confirmed"] is False
    assert case["variant_timeout_gold_confirmed"] is False
    assert case["existing_gold_modified"] is False
    assert len(case["unresolved_as_acknowledged"]) == 2


def test_changed_human_markdown_is_not_overwritten(inputs, tmp_path, monkeypatch):
    for folder in (m.DRAFT, m.CASE):
        relative = folder.relative_to(ROOT)
        dest = tmp_path / relative
        dest.mkdir(parents=True)
        for path in folder.iterdir():
            if path.is_file():
                (dest / path.name).write_bytes(path.read_bytes())
    input_path = tmp_path / m.BOUND_PATHS[0]
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes((ROOT / m.BOUND_PATHS[0]).read_bytes())
    changed = tmp_path / m.BOUND_PATHS[2]
    changed.write_bytes(changed.read_bytes() + "\n人工修改\n".encode())
    before = changed.read_bytes()
    event = tmp_path / "test_event.json"
    event.write_bytes(m.encode(inputs[2]))
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "DRAFT", tmp_path / m.DRAFT.relative_to(ROOT))
    monkeypatch.setattr(m, "CASE", tmp_path / m.CASE.relative_to(ROOT))
    with pytest.raises(ValueError, match="reviewed draft changed"):
        m.prepare(event)
    assert changed.read_bytes() == before


def test_publish_preserves_bytes_and_refuses_existing_bundle(tmp_path):
    dest = tmp_path / "confirmed"
    files = {"review.json": b'{"confirmed": true}\n', "notes.md": "人工确认\n".encode()}
    m.publish_new_bundle(dest, files)
    assert {p.name: p.read_bytes() for p in dest.iterdir()} == files
    with pytest.raises(ValueError, match="refusing overwrite"):
        m.publish_new_bundle(dest, {"review.json": b"changed"})
    assert (dest / "review.json").read_bytes() == files["review.json"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["confirmed"]


def test_failed_publish_cleans_only_its_own_stage(tmp_path, monkeypatch):
    preserved = tmp_path / "user-notes.md"
    preserved.write_bytes(b"user content")
    def fail_rename(*args):
        raise OSError("simulated rename failure")
    monkeypatch.setattr(m.os, "rename", fail_rename)
    with pytest.raises(OSError, match="simulated"):
        m.publish_new_bundle(tmp_path / "confirmed", {"review.json": b"data"})
    assert list(tmp_path.iterdir()) == [preserved]
    assert preserved.read_bytes() == b"user content"


def test_publish_uses_inherited_directory_permissions(tmp_path, monkeypatch):
    created = []
    mkdir = Path.mkdir
    def observe(path, mode=0o777, parents=False, exist_ok=False):
        created.append((path.parent, mode))
        return mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)
    monkeypatch.setattr(Path, "mkdir", observe)
    m.publish_new_bundle(tmp_path / "confirmed", {"review.json": b"data"})
    assert created == [(tmp_path, 0o777)]
