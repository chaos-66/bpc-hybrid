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
    assert methods["direct_llm"]["claim_scope"] == "formal"
    assert methods["sun_llm_fallback"]["claim_scope"] == "formal"
    assert methods["direct_llm"]["is_formal_arm"] is True
    assert methods["sun_llm_fallback"]["is_formal_arm"] is True
    assert methods["sun_llm_fallback"]["gate_status"].startswith("ready")
    assert "comparison_arm_only" in methods["sun_llm_fallback"]["gate_status"]
    assert cmp["decisions"]["h1_downgraded_to_comparison_only"] is True
    assert cmp["zero_api"]["new_llm_api_calls"] == 0
    assert cmp["zero_api"]["real_api_calls_total_historical"] == 300
    assert "not_comparable" in cmp["comparability_boundaries"]
    assert "modality_evidence_span_metrics" in cmp["comparability_boundaries"]
    assert cmp["coarse_view"]["main_view_publishable"] is True
    assert cmp["coarse_view"]["g04_contract_authorized"] is True
    assert cmp["formal_arm_capsules"]["all_three_published_and_verified"] is True


def test_formal_arm_capsules_published() -> None:
    """2026-08-11: the D1/H1 formal arm capsules exist in the formal
    directories (user-authorized zero-API snapshot publications)."""
    for tag in ("direct_llm_formal_arm_v1", "sun_llm_fallback_formal_arm_v1"):
        pred = ROOT / "data" / "predictions" / tag / "predictions.json"
        res = ROOT / "data" / "results" / tag / "evaluation_fine.json"
        man = ROOT / "outputs" / "reports" / f"{tag}.manifest.json"
        assert pred.exists(), tag
        assert res.exists(), tag
        assert man.exists(), tag
        manifest = json.loads(man.read_text(encoding="utf-8"))
        assert manifest["claim_scope"] == "formal"
        assert manifest["is_formal_performance_result"] is True
        assert manifest["zero_api"]["new_llm_calls"] == 0


def test_decision_packages_record_proposal_and_application() -> None:
    """The v2 decision packages document the authorized proposal; methods.json
    now carries the APPLIED state (2026-08-11 user authorization)."""
    methods = json.loads((ROOT / "configs" / "methods.json")
                         .read_text(encoding="utf-8"))
    current = {m["id"]: m for m in methods["methods"]}
    for mid, applied_status in (
            ("direct_llm", "ready"),
            ("sun_llm_fallback", "ready")):
        p = (ROOT / "outputs" / "reports"
             / f"{mid}_method_gate_decision_dry_run_v2.json")
        assert p.exists(), f"{mid} v2 package missing"
        pkg = json.loads(p.read_text(encoding="utf-8"))
        assert pkg["schema_version"] == "method_gate_decision_dry_run@2.0.0"
        change = pkg["methods_json_change"]
        before = change["before"]
        if "after" in change:  # D1 package: single proposed after
            after = change["after"]
        else:  # H1 package: recommended Option A after
            after = change["options"]["A_recommended_ready_plus_role"]["after"]
        assert before["formal_status"] != after["formal_status"]
        assert after["formal_status"] == "ready"
        assert pkg["purpose"]
        assert pkg["rollback"]
        assert pkg["zero_api_path"]["new_llm_calls_required_for_default_path"] == 0
        # applied state on disk matches the authorized proposal
        assert current[mid]["formal_status"] == applied_status
        assert current[mid]["command_status"] == "formal_ready_candidate_authorized"
    assert current["sun_llm_fallback"]["role"] == "comparison_arm_only"
    assert "comparison-only" in current["sun_llm_fallback"]["notes"].lower()
