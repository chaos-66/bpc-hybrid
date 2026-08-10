"""Focused tests for the D1/H1 zero-API re-evaluation + comparison capsule.

Covers:
- D1/H1 binding verification (150 ids, text hashes, prompt lock, schema)
- claim-scope boundaries (candidate / formal-gate-blocked, never formal)
- nothing written to data/predictions or data/results
- zero new LLM calls
- decision dry-run packages exist, are not applied, and keep exact
  before/after
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REEVAL_DIR = ROOT / "outputs" / "evidence" / "d1_h1_zero_api_reeval_v1"


def _load(name: str) -> dict:
    return json.loads((REEVAL_DIR / name).read_text(encoding="utf-8"))


def test_reeval_capsule_exists_and_zero_api() -> None:
    if not (REEVAL_DIR / "manifest.json").exists():
        pytest.skip("re-evaluation not built yet")
    manifest = _load("manifest.json")
    assert manifest["zero_api"]["new_llm_api_calls"] == 0
    assert "d1/reevaluation.json" in manifest["artifacts"]
    assert "h1/reevaluation.json" in manifest["artifacts"]
    assert "comparison_capsule.json" in manifest["artifacts"]


def test_d1_h1_binding_ok_and_claim_scopes() -> None:
    if not (REEVAL_DIR / "manifest.json").exists():
        pytest.skip("re-evaluation not built yet")
    d1 = _load("d1/reevaluation.json")
    h1 = _load("h1/reevaluation.json")
    assert d1["binding"]["binding_ok"] is True
    assert h1["binding"]["binding_ok"] is True
    assert d1["claim_scope"] == "candidate"
    assert "formal-gate-blocked" in d1["gate_status"]
    assert h1["claim_scope"] == "candidate"
    assert "comparison-only" in h1["gate_status"]
    assert d1["new_llm_calls"] == 0 and h1["new_llm_calls"] == 0
    # D1 coarse five-field metrics match the historical per-field numbers
    coarse = d1["evaluation"]["coarse"]["span_fields"]
    expected = {"actor": 0.7579, "action": 0.9437, "condition": 0.8380,
                "constraint": 0.7427, "exception": 0.7619}
    for field, want in expected.items():
        got = round(coarse[field]["f1"], 4)
        assert abs(got - want) < 0.0002, f"D1 coarse {field}: {got} vs {want}"


def test_comparison_capsule_bindings_and_boundaries() -> None:
    if not (REEVAL_DIR / "manifest.json").exists():
        pytest.skip("re-evaluation not built yet")
    cmp = _load("comparison_capsule.json")
    assert cmp["schema_version"] == "shared_stage2_comparison_capsule@1.0.0"
    assert cmp["formal_input_v2"]["sha256"]
    assert cmp["formal_gold"]["sha256"]
    methods = cmp["methods"]
    assert methods["sun_rule_only"]["claim_scope"] == "formal"
    assert methods["direct_llm"]["claim_scope"] == "candidate"
    assert methods["sun_llm_fallback"]["claim_scope"] == "candidate"
    assert cmp["decisions"]["h1_downgraded_to_comparison_only"] is True
    assert cmp["zero_api"]["new_llm_api_calls"] == 0
    assert cmp["zero_api"]["real_api_calls_total_historical"] == 300
    assert "not_comparable" in cmp["comparability_boundaries"]
    assert "modality_evidence_span_metrics" in cmp["comparability_boundaries"]
    assert cmp["coarse_view"]["main_view_publishable"] is False


def test_nothing_written_to_formal_prediction_results_dirs() -> None:
    """D1/H1 candidate results must not appear in the formal directories."""
    for rel in ("data/predictions", "data/results"):
        d = ROOT / rel
        if not d.exists():
            continue
        for sub in d.iterdir():
            assert "d1" not in sub.name.lower()
            assert "h1" not in sub.name.lower()
            assert "direct_llm" not in sub.name.lower()
            assert "sun_llm_fallback" not in sub.name.lower()


def test_decision_packages_dry_run_not_applied() -> None:
    for mid in ("direct_llm", "sun_llm_fallback"):
        p = (ROOT / "outputs" / "reports"
             / f"{mid}_method_gate_decision_dry_run.json")
        if not p.exists():
            pytest.skip(f"{mid} decision package not built yet")
        pkg = json.loads(p.read_text(encoding="utf-8"))
        assert pkg["status"] == "dry_run_not_applied"
        before = pkg["methods_json_change"]["before"]
        after = pkg["methods_json_change"]["after"]
        assert before["formal_status"] != after["formal_status"]
        assert pkg["authorization_sentence"]
        assert pkg["rollback"]
        # methods.json on disk must still carry the BEFORE status
        methods = json.loads((ROOT / "configs" / "methods.json")
                             .read_text(encoding="utf-8"))
        current = next(m for m in methods["methods"] if m["id"] == mid)
        assert current["formal_status"] == before["formal_status"]
