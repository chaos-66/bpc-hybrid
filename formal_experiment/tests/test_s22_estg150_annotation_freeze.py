from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from formal_experiment.s2_2_freeze_gate import (
    MANIFEST_REL,
    S22FreezeExpectations,
    verify_s2_2_freeze_gate,
)


ROOT = Path(__file__).resolve().parents[1]


def _load_verifier():
    path = ROOT / "scripts/verify_estg150_s22_freeze.py"
    spec = importlib.util.spec_from_file_location("_test_s22_verifier", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_s22_receipt_is_deterministic_and_exact() -> None:
    verifier = _load_verifier()
    actual = json.loads((ROOT / MANIFEST_REL).read_text(encoding="utf-8"))
    rebuilt = verifier.build_manifest()
    assert rebuilt == actual
    assert rebuilt["validation"]["n_records"] == 150
    assert rebuilt["validation"]["n_field_decisions_resolved"] == 900
    assert rebuilt["validation"]["n_adjudicated"] == 150
    assert rebuilt["annotation_summary"]["clause_count"] == 231
    assert rebuilt["route_boundaries"]["formal_gold_publication_ready"] is False
    assert rebuilt["safety"]["llm_api_called"] is False


def test_s22_machine_gate_verifies_contract_and_receipt() -> None:
    gate = verify_s2_2_freeze_gate(ROOT)
    assert gate["ready"] is True, gate
    assert gate["annotation_frozen"] is True
    assert gate["formal_gold_published"] is False
    assert gate["formal_stage2_method_run_authorized"] is False
    assert gate["records"] == 150
    assert gate["resolved_field_decisions"] == 900
    assert gate["adjudicated"] == 150
    assert gate["clause_count"] == 231


def test_s22_wrong_expected_source_hash_fails_closed() -> None:
    wrong = S22FreezeExpectations(source_sha256="0" * 64)
    gate = verify_s2_2_freeze_gate(ROOT, expectations=wrong)
    assert gate["ready"] is False
    assert "s2_2_freeze_source_hash_mismatch" in gate["blockers"]


def test_s22_rejects_non_adjudicated_layer_e(tmp_path: Path) -> None:
    verifier = _load_verifier()
    source = json.loads(verifier.DEFAULT_SOURCE.read_text(encoding="utf-8"))
    source["records"][0]["review_state"]["status"] = "reviewed"
    tampered = tmp_path / "human_correction.json"
    tampered.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(verifier.AnnotationFreezeError, match="not freeze-ready"):
        verifier.build_manifest(tampered)
