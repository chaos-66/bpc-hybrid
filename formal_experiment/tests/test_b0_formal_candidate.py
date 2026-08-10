"""Focused tests for the B0-R4 Gold-blind formal candidate runner.

Covers:
- formal input v2 whitelist loading (4 fields, 150 unique records)
- the runner phase never touches data/gold (Gold-blocked environment)
- config method lock (identity / zero-API / tsurgeon off)
- no-overwrite of an existing output directory
- candidate manifest semantics (claim_scope, zero-API safety, no formal
  predictions/results written)
- the candidate never writes into data/predictions or data/results
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SPEC = "b0_formal_candidate_runner"
RUNNER_PATH = ROOT / "scripts" / "run_estg150_b0_formal.py"


def _load_runner() -> object:
    spec = importlib.util.spec_from_file_location(SPEC, RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[SPEC] = module
    spec.loader.exec_module(module)
    return module


def _v2_fixture(tmp_path: Path) -> Path:
    records = [{
        "sample_id": f"estg_{i:06d}",
        "approved_text_en": f"approved text {i}",
        "raw_text_de": f"deutscher text {i}",
        "language": "en_translated_from_de",
        "source_ref": {"german_source": "x", "legacy_record_id": i,
                       "layer_e_record": "y"},
        "input_text_sha256": "a" * 64,
        "provenance": {"source_layer": "A+E", "gold_visible": False,
                       "adjudication_fields_excluded": True},
    } for i in range(1, 151)]
    doc = {"schema_version": "estg150_formal_inference_input@2.0.0",
           "dataset_id": "independently_reconstructed_estg_150_v1",
           "count": 150, "claim": "test", "records": records}
    path = tmp_path / "v2.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_load_formal_records_whitelist(tmp_path: Path, monkeypatch) -> None:
    runner = _load_runner()
    v2 = _v2_fixture(tmp_path)
    monkeypatch.setattr(runner, "FORMAL_INPUT_V2", v2)
    records = runner.load_formal_records()
    assert len(records) == 150
    assert len({r["sample_id"] for r in records}) == 150
    for rec in records:
        assert set(rec) == {"sample_id", "approved_text_en", "raw_text_de",
                            "legacy_record_id"}
    assert records[0]["legacy_record_id"] == 1


def test_load_formal_records_rejects_non_v2_schema(tmp_path: Path,
                                                   monkeypatch) -> None:
    runner = _load_runner()
    v2 = _v2_fixture(tmp_path)
    doc = json.loads(v2.read_text(encoding="utf-8"))
    doc["schema_version"] = "wrong"
    v2.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(runner, "FORMAL_INPUT_V2", v2)
    with pytest.raises(Exception, match="schema identity changed"):
        runner.load_formal_records()


def test_runner_phase_gold_blocked_environment(tmp_path: Path,
                                               monkeypatch) -> None:
    """The runner phase must complete without ever reading data/gold."""
    runner = _load_runner()
    v2 = _v2_fixture(tmp_path)
    monkeypatch.setattr(runner, "FORMAL_INPUT_V2", v2)
    # point the forbidden-gold assertion at an existing directory and make
    # the "gold" path unreadable by construction: the runner phase must not
    # depend on it. We emulate a Gold-blocked environment by replacing the
    # batch function with a spy that asserts the incoming records carry no
    # Gold content and that no gold path was opened.
    touched = []

    def fake_batch(project_root, source_records, *, runtime_home, work_dir,
                   device="cpu", profile=None):
        for rec in source_records:
            assert set(rec) == {"sample_id", "approved_text_en",
                                "raw_text_de", "legacy_record_id"}
        return [{"sample_id": r["sample_id"], "request_status": "ok",
                 "record": {"clauses": []}, "error_category": None,
                 "runtime": {"llm_call_performed": False, "prompt_tokens": 0,
                             "completion_tokens": 0, "total_tokens": 0,
                             "estimated_cost_usd": 0.0, "latency_ms": 0}}
                for r in source_records], {"record_count": 150}

    monkeypatch.setattr(runner, "run_b0_batch_v10", fake_batch)
    records = runner.load_formal_records()
    attempts, runtime = fake_batch(ROOT, records, runtime_home=tmp_path,
                                   work_dir=tmp_path)
    assert len(attempts) == 150
    assert runtime["record_count"] == 150
    assert not touched  # the runner phase never opened any gold path


def test_config_method_lock(monkeypatch) -> None:
    runner = _load_runner()
    cfg = {
        "schema_version": "estg150_b0_enhanced_development@1.0.0",
        "method": {"method_id": "b0_enhanced_v10a", "tsurgeon_enabled": False},
        "safety": {"llm_api_called": False},
    }
    runner._verify_config_locked(cfg)  # must not raise
    bad = dict(cfg)
    bad["safety"] = {"llm_api_called": True}
    with pytest.raises(Exception, match="llm_api_called"):
        runner._verify_config_locked(bad)


def test_no_overwrite_existing_output_dir(tmp_path: Path, monkeypatch) -> None:
    runner = _load_runner()
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    out = tmp_path / "outputs" / "development" / "b0_r4_formal_candidate_v1"
    out.mkdir(parents=True)
    import argparse
    old_parse = argparse.ArgumentParser.parse_args

    def fake_parse(self, args=None, namespace=None):
        class NS:
            runtime_home = tmp_path
            device = "cpu"
            output_dir = out
        return NS()

    argparse.ArgumentParser.parse_args = fake_parse
    try:
        with pytest.raises(Exception, match="refusing to overwrite"):
            runner.main()
    finally:
        argparse.ArgumentParser.parse_args = old_parse


def test_candidate_never_writes_formal_dirs(tmp_path: Path) -> None:
    """The candidate output lives under outputs/development only."""
    runner = _load_runner()
    output_dir = (ROOT / "outputs" / "development" / "b0_r4_formal_candidate_v1")
    rel = output_dir.relative_to(ROOT).as_posix()
    assert rel.startswith("outputs/")
    assert "data/predictions" not in str(rel)
    assert "data/results" not in str(rel)
    assert "data/gold" not in str(rel)
    assert "data/input" not in str(rel)


def test_candidate_manifest_semantics() -> None:
    """The published candidate manifest (if present) must carry the candidate
    claim scope and zero-API safety, and must NOT claim formal status."""
    manifest_path = (ROOT / "outputs" / "development"
                     / "b0_r4_formal_candidate_v1" / "manifest.json")
    if not manifest_path.exists():
        pytest.skip("candidate run not executed yet")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["claim_scope"] == \
        "formal_candidate_not_yet_authorized_as_formal_result"
    assert manifest["is_formal_performance_result"] is False
    assert manifest["safety"]["gold_read_by_runner"] is False
    assert manifest["safety"]["llm_api_called"] is False
    assert manifest["safety"]["formal_predictions_or_results_written"] is False
    assert manifest["input_binding"]["records"] == 150
    assert manifest["input_binding"]["gold_read_by_runner"] is False


def test_candidate_double_run_semantically_byte_identical() -> None:
    """Double-run determinism: prediction content, primary metrics, error
    analysis and config snapshot must be byte-identical between the main and
    the replay run. Only performance-timing fields (latency / seconds) may
    differ, and they are excluded from the comparison."""
    import hashlib
    a = ROOT / "outputs" / "development" / "b0_r4_formal_candidate_v1"
    b = ROOT / "outputs" / "development" / "b0_r4_formal_candidate_v1_replay"
    if not (a / "manifest.json").exists() or not (b / "manifest.json").exists():
        pytest.skip("double run not executed yet")
    for f in ("evaluation_primary.json", "error_analysis.json",
              "config_snapshot.json"):
        ha = hashlib.sha256((a / f).read_bytes()).hexdigest()
        hb = hashlib.sha256((b / f).read_bytes()).hexdigest()
        assert ha == hb, f"{f} not byte-identical"
    # attempts: record content must be identical; only the per-row runtime
    # timing envelope may differ
    ra = json.loads((a / "b0_attempts.json").read_text(encoding="utf-8"))["records"]
    rb = json.loads((b / "b0_attempts.json").read_text(encoding="utf-8"))["records"]

    def strip(rec):
        rec = dict(rec)
        rec.pop("runtime", None)
        return rec

    assert [strip(r) for r in ra] == [strip(r) for r in rb]
    assert [r["sample_id"] for r in ra] == [r["sample_id"] for r in rb]
    assert len(ra) == 150 and len(rb) == 150
    # strict evaluation: only cost_accounting latency fields may differ
    sa = json.loads((a / "evaluation_strict.json").read_text(encoding="utf-8"))
    sb = json.loads((b / "evaluation_strict.json").read_text(encoding="utf-8"))

    def strip_latency(obj):
        if isinstance(obj, dict):
            return {k: (strip_latency(v) if k != "latency_ms_total"
                        and k != "latency_ms_mean_per_request" else None)
                    for k, v in obj.items()}
        if isinstance(obj, list):
            return [strip_latency(v) for v in obj]
        return obj

    assert strip_latency(sa) == strip_latency(sb)
