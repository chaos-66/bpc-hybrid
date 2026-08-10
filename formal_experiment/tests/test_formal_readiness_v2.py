"""Focused tests for the B0/D1/H1 formal readiness v2 binding logic.

Covers zero-API binding verification with synthetic fixtures:
- a snapshot bound to formal input v2 (ids + text + recipe) is accepted
- id mismatch / text mismatch / missing snapshot are each reported
- mismatched historical predictions are never promoted
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

SPEC = "b0_d1_formal_readiness"
SCRIPT = ROOT / "scripts" / "build_b0_d1_formal_readiness_v2.py"


def _load_module() -> object:
    spec = importlib.util.spec_from_file_location(SPEC, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[SPEC] = module
    spec.loader.exec_module(module)
    return module


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _v2() -> dict:
    return {"schema_version": "estg150_formal_inference_input@2.0.0",
            "count": 150, "records": [
                {"sample_id": f"estg_{i:06d}", "input_text_sha256": _sha(f"t{i}".encode())}
                for i in range(1, 151)]}


def test_bound_snapshot_accepted(tmp_path: Path, monkeypatch) -> None:
    m = _load_module()
    v2 = _v2()
    v2_sha = {r["sample_id"]: r["input_text_sha256"] for r in v2["records"]}
    # a D1-style snapshot fully bound to v2
    inp = tmp_path / "input.jsonl"
    preds = tmp_path / "preds.jsonl"
    man = tmp_path / "manifest.json"
    inp.write_text("\n".join(
        json.dumps({"sample_id": f"estg_{i:06d}",
                    "text": f"t{i}"}) for i in range(1, 151)), encoding="utf-8")
    preds.write_text("\n".join(
        json.dumps({"sample_id": f"estg_{i:06d}",
                    "record": {"validation": {"schema_valid": True}}})
        for i in range(1, 151)), encoding="utf-8")
    man.write_text(json.dumps({
        "prompts": [{"sha256": "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"}],
        "llm_model": "deepseek-v4-pro",
        "sampling": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 4096},
        "gold_read_by_runner": False,
        "llm_calls": 150}), encoding="utf-8")
    registry = tmp_path / "registry.json"
    ev_real = ROOT / "configs" / "evaluation" / "sun_table8_literal_overlap_v2.json"
    registry.write_text(json.dumps({"recipe_lock": {
        "prompt": {"sha256": "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"},
        "evaluator": {"sha256": hashlib.sha256(ev_real.read_bytes()).hexdigest()}}}),
        encoding="utf-8")
    monkeypatch.setattr(m, "D1_INPUT", inp)
    monkeypatch.setattr(m, "D1_PREDICTIONS", preds)
    monkeypatch.setattr(m, "D1_MANIFEST", man)
    monkeypatch.setattr(m, "D1_REGISTRY", registry)
    monkeypatch.setattr(m, "EVALUATOR_CONFIG", ev_real)
    monkeypatch.setattr(m, "D1_PROMPT", ROOT / "prompts" / "sun_compat"
                        / "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md")
    result = m._verify_d1(v2, v2_sha)
    assert result["binding_ok"] is True
    assert result["zero_api_reevaluation_allowed"] is True


def test_unbound_snapshot_reports_first_mismatch(tmp_path: Path,
                                                 monkeypatch) -> None:
    m = _load_module()
    v2 = _v2()
    v2_sha = {r["sample_id"]: r["input_text_sha256"] for r in v2["records"]}
    inp = tmp_path / "input.jsonl"
    preds = tmp_path / "preds.jsonl"
    man = tmp_path / "manifest.json"
    # text differs from v2 for one row
    rows = [{"sample_id": f"estg_{i:06d}", "text": f"t{i}"} for i in range(1, 151)]
    rows[0]["text"] = "WRONG"
    inp.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    preds.write_text("\n".join(
        json.dumps({"sample_id": f"estg_{i:06d}",
                    "record": {"validation": {"schema_valid": True}}})
        for i in range(1, 151)), encoding="utf-8")
    man.write_text(json.dumps({
        "prompts": [{"sha256": "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"}],
        "llm_model": "deepseek-v4-pro",
        "sampling": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 4096},
        "gold_read_by_runner": False}), encoding="utf-8")
    registry = tmp_path / "registry.json"
    ev_real = ROOT / "configs" / "evaluation" / "sun_table8_literal_overlap_v2.json"
    registry.write_text(json.dumps({"recipe_lock": {
        "prompt": {"sha256": "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"},
        "evaluator": {"sha256": hashlib.sha256(ev_real.read_bytes()).hexdigest()}}}),
        encoding="utf-8")
    monkeypatch.setattr(m, "D1_INPUT", inp)
    monkeypatch.setattr(m, "D1_PREDICTIONS", preds)
    monkeypatch.setattr(m, "D1_MANIFEST", man)
    monkeypatch.setattr(m, "D1_REGISTRY", registry)
    monkeypatch.setattr(m, "EVALUATOR_CONFIG", ev_real)
    monkeypatch.setattr(m, "D1_PROMPT", ROOT / "prompts" / "sun_compat"
                        / "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md")
    result = m._verify_d1(v2, v2_sha)
    assert result["binding_ok"] is False
    assert result["zero_api_reevaluation_allowed"] is False
    assert "NOT bound" in result["verdict"]
    # the mismatched prediction must not be promoted
    assert "first mismatch" in result["verdict"]


def test_missing_snapshot_fails(tmp_path: Path, monkeypatch) -> None:
    m = _load_module()
    v2 = _v2()
    v2_sha = {r["sample_id"]: r["input_text_sha256"] for r in v2["records"]}
    monkeypatch.setattr(m, "D1_INPUT", tmp_path / "missing.jsonl")
    monkeypatch.setattr(m, "D1_PREDICTIONS", tmp_path / "missing_preds.jsonl")
    monkeypatch.setattr(m, "D1_MANIFEST", tmp_path / "missing_man.json")
    monkeypatch.setattr(m, "D1_REGISTRY", tmp_path / "missing_reg.json")
    monkeypatch.setattr(m, "EVALUATOR_CONFIG", tmp_path / "missing_eval.json")
    monkeypatch.setattr(m, "D1_PROMPT", tmp_path / "missing_prompt.md")
    result = m._verify_d1(v2, v2_sha)
    assert result["binding_ok"] is False
    assert any(not c["ok"] and "exists" in c["item"] for c in result["checks"])


def test_id_mismatch_fails(tmp_path: Path, monkeypatch) -> None:
    m = _load_module()
    v2 = _v2()
    v2_sha = {r["sample_id"]: r["input_text_sha256"] for r in v2["records"]}
    inp = tmp_path / "input.jsonl"
    preds = tmp_path / "preds.jsonl"
    man = tmp_path / "manifest.json"
    # only 149 rows -> id set mismatch
    inp.write_text("\n".join(
        json.dumps({"sample_id": f"estg_{i:06d}", "text": f"t{i}"})
        for i in range(1, 150)), encoding="utf-8")
    preds.write_text("\n".join(
        json.dumps({"sample_id": f"estg_{i:06d}",
                    "record": {"validation": {"schema_valid": True}}})
        for i in range(1, 150)), encoding="utf-8")
    man.write_text(json.dumps({
        "prompts": [{"sha256": "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"}],
        "llm_model": "deepseek-v4-pro",
        "sampling": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 4096},
        "gold_read_by_runner": False}), encoding="utf-8")
    registry = tmp_path / "registry.json"
    ev_real = ROOT / "configs" / "evaluation" / "sun_table8_literal_overlap_v2.json"
    registry.write_text(json.dumps({"recipe_lock": {
        "prompt": {"sha256": "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"},
        "evaluator": {"sha256": hashlib.sha256(ev_real.read_bytes()).hexdigest()}}}),
        encoding="utf-8")
    monkeypatch.setattr(m, "D1_INPUT", inp)
    monkeypatch.setattr(m, "D1_PREDICTIONS", preds)
    monkeypatch.setattr(m, "D1_MANIFEST", man)
    monkeypatch.setattr(m, "D1_REGISTRY", registry)
    monkeypatch.setattr(m, "EVALUATOR_CONFIG", ev_real)
    monkeypatch.setattr(m, "D1_PROMPT", ROOT / "prompts" / "sun_compat"
                        / "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md")
    result = m._verify_d1(v2, v2_sha)
    assert result["binding_ok"] is False
    assert any(not c["ok"] and ("150 rows" in c["item"] or "ids" in c["item"])
               for c in result["checks"])
