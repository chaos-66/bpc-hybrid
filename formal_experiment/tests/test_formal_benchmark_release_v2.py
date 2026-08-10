"""Focused tests for formal benchmark release v2 (input fix + verifier).

Covers:
- v1 input is membership-only and NOT executable as model input
- v2 executable Gold-blind input: exactly 150 records, unique ids, text
  byte-identical to the frozen Layer E, no adjudication/candidate fields
- deterministic double-run byte-identical + no-overwrite
- independent verifier fails on tampering (hash / schema / record count /
  source text change)
- audit gains formal_benchmark_release_verified pass and fails closed when
  the release is tampered
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.publish_formal_benchmark_v2 import (  # noqa: E402
    FORBIDDEN_V2_FIELDS,
    build_v2_input,
    verify_v2_against_sources,
)

VERIFIER_PATH = ROOT / "scripts" / "verify_formal_benchmark_release_v2.py"
SPEC_NAME = "formal_benchmark_release_verifier"


def _load_verifier() -> object:
    spec = importlib.util.spec_from_file_location(SPEC_NAME, VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[SPEC_NAME] = module
    spec.loader.exec_module(module)
    return module


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- fixtures


def _layer_e_record(sample_id: str, legacy_id: int) -> dict:
    return {
        "sample_id": sample_id,
        "legacy_record_id": legacy_id,
        "approved_text_en": f"approved text for {sample_id}",
        "raw_text_de": f"deutscher text {legacy_id}",
        "approved_text_en_sha256": "a" * 64,
        "candidate_text_en": "candidate",
        "candidate_text_en_sha256": "b" * 64,
        "decisions": {"translation": "accepted"},
        "human_correction": {"clauses": []},
        "llm_candidate": {"draft": "x"},
        "review_state": {"status": "adjudicated"},
        "source_refs": {},
        "approved_text_en_history": [],
    }


def _layer_e_150() -> dict:
    return {"records": [_layer_e_record(f"estg_{i:06d}", i) for i in range(1, 151)]}


def _membership_hashes(records: list[dict]) -> dict:
    payload = ",".join(str(int(r["legacy_record_id"])) for r in sorted(
        records, key=lambda r: int(r["legacy_record_id"])))
    return {"selected_membership": {
        "membership_payload_sha256": _sha256_bytes(payload.encode("utf-8"))}}


def _gold_stage2(v2: dict, layer_e: dict) -> dict:
    le_by_id = {r["sample_id"]: r for r in layer_e["records"]}
    return {
        "schema_version": "stage2_formal_gold@1.0.0",
        "membership": {"payload_sha256": v2.get("membership_payload_sha256", "")},
        "records": [
            {"sample_id": r["sample_id"], "approved_text_en": r["approved_text_en"],
             "decisions": le_by_id[r["sample_id"]]["decisions"], "clauses": []}
            for r in v2["records"]]}


# --------------------------------------------------------------------------- v1 limitation


def test_v1_input_is_membership_only_not_executable() -> None:
    v1 = json.loads(
        (ROOT / "data" / "input" / "estg150_formal_input_v1.json")
        .read_text(encoding="utf-8"))
    assert "sample_ids" in v1
    assert len(v1["sample_ids"]) == 150
    # membership index only: no text payload, no records
    assert "records" not in v1
    assert "approved_text_en" not in v1
    assert "text" not in v1


def test_v1_status_marker_declares_limitation() -> None:
    marker = (ROOT / "data" / "input" / "estg150_formal_input_v1.STATUS.md")
    assert marker.exists()
    text = marker.read_text(encoding="utf-8")
    assert "membership-only; not sufficient as executable model input" in text


# --------------------------------------------------------------------------- v2 content


def test_v2_exactly_150_records_unique_ids() -> None:
    layer_e = _layer_e_150()
    v2 = build_v2_input(layer_e)
    assert v2["count"] == 150
    assert len(v2["records"]) == 150
    assert len({r["sample_id"] for r in v2["records"]}) == 150
    assert v2["schema_version"] == "estg150_formal_inference_input@2.0.0"


def test_v2_text_identical_to_frozen_layer_e() -> None:
    layer_e = _layer_e_150()
    v2 = build_v2_input(layer_e)
    by_id = {r["sample_id"]: r for r in layer_e["records"]}
    for rec in v2["records"]:
        src = by_id[rec["sample_id"]]
        assert rec["approved_text_en"] == src["approved_text_en"]
        assert rec["raw_text_de"] == src["raw_text_de"]
        assert rec["input_text_sha256"] == _sha256_bytes(
            src["approved_text_en"].encode("utf-8"))


def test_v2_no_gold_or_candidate_fields() -> None:
    layer_e = _layer_e_150()
    v2 = build_v2_input(layer_e)

    def scan(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k not in FORBIDDEN_V2_FIELDS, f"{path}/{k}"
                scan(v, f"{path}/{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                scan(v, f"{path}[{i}]")
    scan(v2)


def test_v2_verify_against_sources_detects_text_drift() -> None:
    layer_e = _layer_e_150()
    v2 = build_v2_input(layer_e)
    membership = _membership_hashes(layer_e["records"])
    gold = _gold_stage2(v2, layer_e)
    problems = verify_v2_against_sources(v2, layer_e, membership, gold)
    assert problems == []

    # change one approved_text_en in v2 -> verifier must flag it
    v2["records"][0]["approved_text_en"] = "tampered text"
    problems = verify_v2_against_sources(v2, layer_e, membership, gold)
    assert any("approved_text_en mismatch" in p for p in problems)


# --------------------------------------------------------------------------- publisher determinism (tmp paths)


def _run_publish(tmp_path: Path, monkeypatch) -> tuple[dict, str]:
    import scripts.publish_formal_benchmark_v2 as pub
    layer_e = _layer_e_150()
    membership = _membership_hashes(layer_e["records"])
    v2 = build_v2_input(layer_e)
    v2["membership_payload_sha256"] = membership["selected_membership"][
        "membership_payload_sha256"]
    gold = _gold_stage2(v2, layer_e)
    # patch module constants to tmp paths
    monkeypatch.setattr(pub, "LAYER_E", tmp_path / "layer_e.json")
    monkeypatch.setattr(pub, "MEMBERSHIP_HASHES", tmp_path / "membership.json")
    monkeypatch.setattr(pub, "V1_INPUT", tmp_path / "v1_input.json")
    monkeypatch.setattr(pub, "V1_PUBLICATION_MANIFEST", tmp_path / "v1_pub.json")
    monkeypatch.setattr(pub, "GOLD_STAGE2", tmp_path / "gold2.json")
    monkeypatch.setattr(pub, "GOLD_MATCHING", tmp_path / "match.json")
    monkeypatch.setattr(pub, "GOLD_VIOLATION", tmp_path / "viol.json")
    monkeypatch.setattr(pub, "STAGE3_CORRECTION", tmp_path / "corr.json")
    monkeypatch.setattr(pub, "STAGE3_INFERENCE", tmp_path / "inf.json")
    monkeypatch.setattr(pub, "INPUT_V2_SCHEMA", tmp_path / "schema.json")
    monkeypatch.setattr(pub, "OUT_V2", tmp_path / "out_v2.json")
    monkeypatch.setattr(pub, "OUT_V1_MARKER", tmp_path / "out_v1.STATUS.md")
    monkeypatch.setattr(pub, "OUT_MANIFEST", tmp_path / "out_manifest.json")
    monkeypatch.setattr(pub, "OUT_REPORT", tmp_path / "out_report.md")
    monkeypatch.setattr(pub, "OUT_EXPORT_INDEX", tmp_path / "out_index.json")
    (tmp_path / "layer_e.json").write_text(json.dumps(layer_e), encoding="utf-8")
    (tmp_path / "membership.json").write_text(json.dumps(membership), encoding="utf-8")
    (tmp_path / "v1_input.json").write_text(json.dumps(
        {"schema_version": "stage2_formal_input@1.0.0", "sample_ids":
         [r["sample_id"] for r in layer_e["records"]]}), encoding="utf-8")
    (tmp_path / "v1_pub.json").write_text(json.dumps(
        {"publication_status": "artifacts_published_and_verified", "artifacts": {}}),
        encoding="utf-8")
    (tmp_path / "gold2.json").write_text(json.dumps(gold), encoding="utf-8")
    (tmp_path / "match.json").write_text(json.dumps({"count": 25, "items": []}),
                                         encoding="utf-8")
    (tmp_path / "viol.json").write_text(json.dumps({"count": 33, "items": []}),
                                        encoding="utf-8")
    (tmp_path / "corr.json").write_text(json.dumps({"matching_items": [],
                                                    "violation_items": []}),
                                        encoding="utf-8")
    (tmp_path / "inf.json").write_text(json.dumps({"matching_items": [],
                                                   "violation_items": []}),
                                       encoding="utf-8")
    (tmp_path / "schema.json").write_text(json.dumps({"schema": True}),
                                          encoding="utf-8")
    out = {}
    out["v2_sha"] = pub._write_no_overwrite(pub.OUT_V2, v2)
    v1_marker = "- role: membership-only; not sufficient as executable model input\n"
    pub._write_text_no_overwrite(pub.OUT_V1_MARKER, v1_marker)
    manifest = pub.build_release_manifest(
        v2, out["v2_sha"], {"commit": "test", "dirty_paths": []},
        {"sha256": "x" * 64, "byte_size": 1, "record_count": 150,
         "schema": "s", "path": "p", "marker_sha256": "y" * 64,
         "marker_byte_size": 1},
        {"stage2": {"path": "p2", "sha256": "a" * 64, "byte_size": 1,
                    "record_count": 150, "schema": "s"},
         "matching": {"path": "p3", "sha256": "b" * 64, "byte_size": 1,
                      "record_count": 25, "schema": "s"},
         "violation": {"path": "p4", "sha256": "c" * 64, "byte_size": 1,
                       "record_count": 33, "schema": "s"}},
        "z" * 64)
    out["manifest_sha"] = pub._write_no_overwrite(pub.OUT_MANIFEST, manifest)
    return out, v2


def test_publisher_double_run_byte_identical_and_no_overwrite(
        tmp_path: Path, monkeypatch) -> None:
    first, _ = _run_publish(tmp_path, monkeypatch)
    second, _ = _run_publish(tmp_path, monkeypatch)
    assert first["v2_sha"] == second["v2_sha"]
    assert first["manifest_sha"] == second["manifest_sha"]
    # no-overwrite: changing v2 content must be refused
    import scripts.publish_formal_benchmark_v2 as pub
    tampered = json.loads((tmp_path / "out_v2.json").read_text(encoding="utf-8"))
    tampered["records"][0]["approved_text_en"] = "different text"
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        pub._write_no_overwrite(pub.OUT_V2, tampered)


# --------------------------------------------------------------------------- verifier tamper detection


def _materialize_release(tmp_path: Path, monkeypatch,
                         tamper: str | None = None) -> object:
    """Build a full release in tmp_path and load the verifier against it."""
    import scripts.publish_formal_benchmark_v2 as pub
    layer_e = _layer_e_150()
    membership = _membership_hashes(layer_e["records"])
    v2 = build_v2_input(layer_e)
    v2["membership_payload_sha256"] = membership["selected_membership"][
        "membership_payload_sha256"]
    gold2 = _gold_stage2(v2, layer_e)
    if tamper == "v2_text":
        v2["records"][5]["approved_text_en"] = "tampered"
    if tamper == "v2_schema":
        v2["schema_version"] = "wrong@9.9.9"
    paths = {
        "layer_e": tmp_path / "layer_e.json",
        "membership": tmp_path / "membership.json",
        "v2": tmp_path / "v2.json",
        "gold2": tmp_path / "gold2.json",
        "match": tmp_path / "match.json",
        "viol": tmp_path / "viol.json",
        "corr": tmp_path / "corr.json",
        "inf": tmp_path / "inf.json",
        "manifest": tmp_path / "manifest.json",
        "schema": tmp_path / "schema.json",
    }
    (tmp_path / "layer_e.json").write_text(json.dumps(layer_e), encoding="utf-8")
    (tmp_path / "membership.json").write_text(json.dumps(membership), encoding="utf-8")
    (tmp_path / "v2.json").write_text(json.dumps(v2), encoding="utf-8")
    (tmp_path / "gold2.json").write_text(json.dumps(gold2), encoding="utf-8")
    # published Stage 3 Gold items are decision-only (no review_state);
    # the frozen correction/inference packs carry review_state
    m_items_gold = [{"item_id": f"m{i:03d}"} for i in range(25)]
    v_items_gold = [{"item_id": f"v{i:03d}"} for i in range(33)]
    m_items_src = [{"item_id": f"m{i:03d}", "review_state": "adjudicated"}
                   for i in range(25)]
    v_items_src = [{"item_id": f"v{i:03d}", "review_state": "adjudicated"}
                   for i in range(33)]
    (tmp_path / "match.json").write_text(
        json.dumps({"count": 25, "items": m_items_gold}), encoding="utf-8")
    (tmp_path / "viol.json").write_text(
        json.dumps({"count": 33, "items": v_items_gold}), encoding="utf-8")
    (tmp_path / "corr.json").write_text(
        json.dumps({"matching_items": m_items_src, "violation_items": v_items_src}),
        encoding="utf-8")
    (tmp_path / "inf.json").write_text(
        json.dumps({"matching_items": m_items_src, "violation_items": v_items_src}),
        encoding="utf-8")
    (tmp_path / "schema.json").write_text(json.dumps({"schema": True}),
                                          encoding="utf-8")
    (tmp_path / "v1.json").write_text(json.dumps(
        {"schema_version": "stage2_formal_input@1.0.0",
         "sample_ids": [r["sample_id"] for r in layer_e["records"]]}),
        encoding="utf-8")
    manifest = {
        "schema_version": "formal_benchmark_release_manifest@2.0.0",
        "release": "formal_benchmark_release_v2",
        "artifacts": {
            "estg150_formal_input_v1.json": {
                "path": "v1.json",
                "sha256": _sha256_bytes((tmp_path / "v1.json").read_bytes()),
                "byte_size": (tmp_path / "v1.json").stat().st_size,
                "record_count": 150, "schema": "s"},
            "estg150_formal_inference_input_v2.json": {
                "path": "v2.json",
                "sha256": _sha256_bytes((tmp_path / "v2.json").read_bytes()),
                "byte_size": (tmp_path / "v2.json").stat().st_size,
                "record_count": 150, "schema": "estg150_formal_inference_input@2.0.0"},
            "stage2_gold": {"path": "gold2.json",
                            "sha256": _sha256_bytes((tmp_path / "gold2.json").read_bytes()),
                            "byte_size": (tmp_path / "gold2.json").stat().st_size,
                            "record_count": 150, "schema": "s"},
            "stage3_matching_gold": {"path": "match.json",
                                     "sha256": _sha256_bytes((tmp_path / "match.json").read_bytes()),
                                     "byte_size": (tmp_path / "match.json").stat().st_size,
                                     "record_count": 25, "schema": "s"},
            "stage3_violation_gold": {"path": "viol.json",
                                      "sha256": _sha256_bytes((tmp_path / "viol.json").read_bytes()),
                                      "byte_size": (tmp_path / "viol.json").stat().st_size,
                                      "record_count": 33, "schema": "s"},
        },
        "v1_limitation": {"label": "membership-only; not sufficient as executable model input"},
        "membership": {"payload_sha256": membership["selected_membership"]["membership_payload_sha256"]},
        "implementation_hashes": {},
        "git": {"commit": "test"},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # make tmp_path a git repo so the capsule-tracking check can pass
    import subprocess
    (tmp_path / "AGENTS.md").write_text("# fixture\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "AGENTS.md"], cwd=tmp_path, check=True)

    verifier = _load_verifier()
    monkeypatch.setattr(verifier, "RELEASE_MANIFEST", paths["manifest"])
    monkeypatch.setattr(verifier, "V2_INPUT", paths["v2"])
    monkeypatch.setattr(verifier, "V1_INPUT", tmp_path / "v1.json")
    monkeypatch.setattr(verifier, "LAYER_E", paths["layer_e"])
    monkeypatch.setattr(verifier, "MEMBERSHIP_HASHES", paths["membership"])
    monkeypatch.setattr(verifier, "GOLD_STAGE2", paths["gold2"])
    monkeypatch.setattr(verifier, "GOLD_MATCHING", paths["match"])
    monkeypatch.setattr(verifier, "GOLD_VIOLATION", paths["viol"])
    monkeypatch.setattr(verifier, "STAGE3_CORRECTION", paths["corr"])
    monkeypatch.setattr(verifier, "STAGE3_INFERENCE", paths["inf"])
    monkeypatch.setattr(verifier, "INPUT_V2_SCHEMA", paths["schema"])
    monkeypatch.setattr(verifier, "STAGE2_SCHEMA", paths["schema"])
    monkeypatch.setattr(verifier, "STAGE3_SCHEMA", paths["schema"])
    monkeypatch.setattr(verifier, "PREDICTION_SCHEMA", paths["schema"])
    monkeypatch.setattr(verifier, "METHODS_CONFIG", paths["schema"])
    monkeypatch.setattr(verifier, "EXPERIMENT_CONTRACT", paths["schema"])
    monkeypatch.setattr(verifier, "PUBLISHER", paths["schema"])
    monkeypatch.setattr(verifier, "VERIFIER", VERIFIER_PATH)
    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    return verifier


def test_verifier_passes_intact_release(tmp_path: Path, monkeypatch) -> None:
    verifier = _materialize_release(tmp_path, monkeypatch)
    result = verifier.verify_release()
    import sys
    for c in result["checks"]:
        if not c["ok"]:
            print("DEBUGFAIL", c, file=sys.stderr)
    assert result["verified"] is True, [
        c for c in result["checks"] if not c["ok"]]


def test_verifier_fails_on_tampered_text(tmp_path: Path, monkeypatch) -> None:
    verifier = _materialize_release(tmp_path, monkeypatch, tamper="v2_text")
    result = verifier.verify_release()
    assert result["verified"] is False
    names = [c["name"] for c in result["checks"] if not c["ok"]]
    assert any("text provenance" in n for n in names)


def test_verifier_fails_on_schema_tamper(tmp_path: Path, monkeypatch) -> None:
    verifier = _materialize_release(tmp_path, monkeypatch, tamper="v2_schema")
    result = verifier.verify_release()
    assert result["verified"] is False


def test_verifier_fails_on_missing_manifest(tmp_path: Path, monkeypatch) -> None:
    verifier = _materialize_release(tmp_path, monkeypatch)
    (tmp_path / "manifest.json").unlink()
    result = verifier.verify_release()
    assert result["verified"] is False
    assert any(c["name"] == "release manifest exists" and not c["ok"]
               for c in result["checks"])


def test_verifier_fails_on_record_count_tamper(tmp_path: Path,
                                               monkeypatch) -> None:
    verifier = _materialize_release(tmp_path, monkeypatch)
    v2 = json.loads((tmp_path / "v2.json").read_text(encoding="utf-8"))
    v2["records"] = v2["records"][:149]
    (tmp_path / "v2.json").write_text(json.dumps(v2), encoding="utf-8")
    result = verifier.verify_release()
    assert result["verified"] is False


# --------------------------------------------------------------------------- audit integration


def test_audit_gains_release_verified_pass() -> None:
    from formal_experiment.audit import collect_project_audit
    audit = collect_project_audit()
    passes = {item["code"] for item in audit["findings"]["passes"]}
    assert "formal_benchmark_release_verified" in passes
    assert "formal_gold_capsule_frozen" in passes
    warnings = {item["code"] for item in audit["findings"]["warnings"]}
    assert "formal_predictions_results_capsule_not_produced" in warnings
    errors = {item["code"] for item in audit["findings"]["errors"]}
    assert "formal_benchmark_release_invalid" not in errors
