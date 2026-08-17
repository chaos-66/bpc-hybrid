"""Focused publication and fail-closed tests for S2.11 Gold v1."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_s2_11_formal_gold_v1.py"
PUBLISHER = ROOT / "scripts" / "publish_s2_11_formal_gold_v1.py"
GOLD = ROOT / "data" / "gold" / "stage2" \
    / "s2_11_complex_corpus_formal_gold_v1.json"
DECISIONS = ROOT / "data" / "development" / "human_review" \
    / "s2_11_review_decisions_v2.json"
EVENT = ROOT / "configs" / "s2_11_batch_import_confirmation_event_v3.json"
G05 = ROOT / "configs" / "g05_complexity_frozen_v1.json"
MANIFEST = ROOT / "outputs" / "reports" \
    / "s2_11_formal_gold_v1.manifest.json"
EXPORT = ROOT / "outputs" / "reports" \
    / "s2_11_formal_gold_v1_export_index.json"


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, value) -> None:
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2)
                      + "\n").encode("utf-8"))


def test_publication_verifies_and_replays() -> None:
    result = _module(VERIFIER, "s211_gold_v_ok").verify()
    assert result["verified"] is True, [
        item for item in result["checks"] if not item["ok"]]
    assert len(result["checks"]) >= 27


def test_gold_is_36_record_coordinate_only_derivation() -> None:
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    assert gold["membership"]["published_records"] == 36
    assert len(gold["records"]) == 36
    assert gold["provenance"]["proposal_source"] \
        == "deepseek_offline_proposal_v3"
    assert gold["provenance"]["adjudication"] == "user_batch_confirmation"
    assert gold["provenance"]["reviewer"] == "hyc"
    assert gold["provenance"]["independent_from_scratch_expert_annotation"] \
        is False
    by_id = {row["sample_id"]: row for row in gold["records"]}
    assert set(by_id) == set(decisions["records"])
    for sample_id, row in by_id.items():
        assert row["canonical"] == decisions["records"][sample_id]["canonical"]
        assert "text" not in row["source"]
        for clause in row["canonical"]["clauses"]:
            assert set(clause["clause_span"]) == {"start", "end"}


def test_publisher_pure_derivation_matches_disk() -> None:
    module = _module(PUBLISHER, "s211_gold_publisher_test")
    documents = module.build_documents()
    assert documents[module.GOLD_REL] == GOLD.read_bytes()
    assert module.check(documents) == []


def test_extra_gold_field_fails(monkeypatch, tmp_path: Path) -> None:
    module = _module(VERIFIER, "s211_gold_v_extra")
    value = json.loads(GOLD.read_text(encoding="utf-8"))
    value["unexpected"] = True
    path = tmp_path / "gold.json"
    _write(path, value)
    monkeypatch.setattr(module, "GOLD", path)
    assert module.verify(run_replay=False)["verified"] is False


def test_reviewer_mismatch_fails(monkeypatch, tmp_path: Path) -> None:
    module = _module(VERIFIER, "s211_gold_v_reviewer")
    value = json.loads(DECISIONS.read_text(encoding="utf-8"))
    first = next(iter(value["records"].values()))
    first["review_metadata"]["reviewer"] = "not-hyc"
    path = tmp_path / "decisions.json"
    _write(path, value)
    monkeypatch.setattr(module, "DECISIONS", path)
    assert module.verify(run_replay=False)["verified"] is False


def test_confirmation_instruction_tamper_fails(monkeypatch,
                                                tmp_path: Path) -> None:
    module = _module(VERIFIER, "s211_gold_v_event")
    value = json.loads(EVENT.read_text(encoding="utf-8"))
    value["user_instruction_utf8"] += " tampered"
    path = tmp_path / "event.json"
    _write(path, value)
    monkeypatch.setattr(module, "EVENT", path)
    assert module.verify(run_replay=False)["verified"] is False


def test_g05_unfrozen_fails(monkeypatch, tmp_path: Path) -> None:
    module = _module(VERIFIER, "s211_gold_v_g05")
    value = json.loads(G05.read_text(encoding="utf-8"))
    value["status"] = "reopened"
    path = tmp_path / "g05.json"
    _write(path, value)
    monkeypatch.setattr(module, "G05", path)
    assert module.verify(run_replay=False)["verified"] is False


def test_manifest_hash_tamper_fails(monkeypatch, tmp_path: Path) -> None:
    module = _module(VERIFIER, "s211_gold_v_manifest")
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    first = next(iter(value["artifacts"].values()))
    first["sha256"] = "0" * 64
    path = tmp_path / "manifest.json"
    _write(path, value)
    monkeypatch.setattr(module, "MANIFEST", path)
    assert module.verify(run_replay=False)["verified"] is False


def test_export_hash_tamper_fails(monkeypatch, tmp_path: Path) -> None:
    module = _module(VERIFIER, "s211_gold_v_export")
    value = json.loads(EXPORT.read_text(encoding="utf-8"))
    value["independent_verifier"]["sha256"] = "0" * 64
    path = tmp_path / "export.json"
    _write(path, value)
    monkeypatch.setattr(module, "EXPORT", path)
    assert module.verify(run_replay=False)["verified"] is False
