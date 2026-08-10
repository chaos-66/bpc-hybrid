"""Focused tests for the shared comparison hash correction + v2 gate
decision dry-runs + final-readiness hardening dry-run.

Covers:
- no hardcoded coarse-view hash; authoritative hash is cross-verified from
  the G0.4 manifest, the derived artifact recomputation and the B0 formal
  manifest; any disagreement fails closed
- comparison capsule carries the authoritative hash (d15061d7...39)
- D1/H1 prediction bytes unchanged (locked hashes) and 0 new API calls
- D1 v2 dry-run: zero-API default path, no "necessarily needs new LLM
  budget" claim
- H1 v2 dry-run: two options, recommended Option A, simulated blockers
  honest under current semantics
- hardening dry-run: all_three_ready reproduces the premature final gate +
  unconditional unexpected-ready error; comparison_only_ready not recognized
- nothing applied: methods.json / Gold / contract unchanged
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
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

AUTHORITATIVE_COARSE_SHA = (
    "d15061d74b41c58dd4278f0a675327099453564090005f9b58b1d352de5cfe39")
WRONG_COARSE_SHA = (
    "d15061d74b41c58d66cfdafc86f1b0f2dc91e1a51447afcafc4c67ebcb59c5c3")

REEVAL_SCRIPT = ROOT / "scripts" / "build_d1_h1_zero_api_reevaluation_v1.py"


def _load_reeval_module() -> object:
    spec = importlib.util.spec_from_file_location(
        "d1h1_reeval_corr", REEVAL_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["d1h1_reeval_corr"] = module
    spec.loader.exec_module(module)
    return module


def _no_hardcoded_hash_in_source() -> bool:
    src = REEVAL_SCRIPT.read_text(encoding="utf-8")
    return WRONG_COARSE_SHA not in src and AUTHORITATIVE_COARSE_SHA not in src


# --------------------------------------------------------------------------- hash binding


def test_no_hardcoded_coarse_hash_in_script() -> None:
    assert _no_hardcoded_hash_in_source()


def test_authoritative_hash_cross_verification(tmp_path: Path,
                                               monkeypatch) -> None:
    m = _load_reeval_module()
    result = m._authoritative_coarse_view_hash()
    assert result["semantic_sha256"] == AUTHORITATIVE_COARSE_SHA

    # tamper the G0.4 manifest hash -> must fail closed
    man_path = ROOT / "outputs" / "evidence" / "g04_formal_coarse_view_v1" / "manifest.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    man["derived_view"]["semantic_sha256"] = WRONG_COARSE_SHA
    fake = tmp_path / "manifest.json"
    fake.write_text(json.dumps(man), encoding="utf-8")
    monkeypatch.setattr(m, "G04_MANIFEST", fake)
    with pytest.raises(RuntimeError, match="hash disagreement"):
        m._authoritative_coarse_view_hash()


def test_derived_artifact_recompute_disagreement_fails(tmp_path: Path,
                                                       monkeypatch) -> None:
    m = _load_reeval_module()
    derived_path = ROOT / "outputs" / "evidence" / "g04_formal_coarse_view_v1" / "coarse_view_derived.json"
    derived = json.loads(derived_path.read_text(encoding="utf-8"))
    derived[0]["source_id"] = "tampered"
    fake = tmp_path / "derived.json"
    fake.write_text(json.dumps(derived), encoding="utf-8")
    monkeypatch.setattr(m, "G04_DERIVED", fake)
    with pytest.raises(RuntimeError, match="hash disagreement"):
        m._authoritative_coarse_view_hash()


def test_b0_manifest_disagreement_fails(tmp_path: Path, monkeypatch) -> None:
    m = _load_reeval_module()
    b0_path = ROOT / "outputs" / "reports" / "b0_formal_arm_v1.manifest.json"
    b0 = json.loads(b0_path.read_text(encoding="utf-8"))
    b0["g04"]["coarse_view_semantic_sha256"] = WRONG_COARSE_SHA
    fake = tmp_path / "b0.json"
    fake.write_text(json.dumps(b0), encoding="utf-8")
    monkeypatch.setattr(m, "B0_MANIFEST", fake)
    with pytest.raises(RuntimeError, match="B0 formal manifest"):
        m._authoritative_coarse_view_hash()


def test_comparison_capsule_carries_authoritative_hash() -> None:
    cmp = json.loads((ROOT / "outputs" / "evidence" / "d1_h1_zero_api_reeval_v1"
                      / "comparison_capsule.json").read_text(encoding="utf-8"))
    assert cmp["coarse_view"]["semantic_sha256"] == AUTHORITATIVE_COARSE_SHA
    assert "semantic_hash_source" in cmp["coarse_view"]
    assert "cross-verified" in cmp["coarse_view"]["semantic_hash_source"]
    # 2026-08-11 user authorization applied
    assert cmp["coarse_view"]["main_view_publishable"] is True
    assert cmp["coarse_view"]["g04_contract_authorized"] is True
    assert cmp["formal_arm_capsules"]["all_three_published_and_verified"] is True


def test_d1_h1_prediction_bytes_unchanged() -> None:
    d1 = (ROOT / "outputs" / "development"
          / "s27_d1_v6_r3_clean_rerun_150_hist56d_v1" / "d1_responses.jsonl")
    h1 = (ROOT / "outputs" / "development" / "s28d_h1_150_v4pro_v1"
          / "h1_predictions.jsonl")
    assert hashlib.sha256(d1.read_bytes()).hexdigest() == \
        "9188093c5b30d288c749e1dc6da9d88eb5df4fd4c08a73518f6b4ff243dca36e"
    assert hashlib.sha256(h1.read_bytes()).hexdigest() == \
        "4fd7c116d3f7841d72d27fa0dcadc9be2b8095fda189e28a74af1c298c22fccc"


def test_reeval_zero_new_api_calls() -> None:
    man = json.loads((ROOT / "outputs" / "evidence" / "d1_h1_zero_api_reeval_v1"
                      / "manifest.json").read_text(encoding="utf-8"))
    assert man["zero_api"]["new_llm_api_calls"] == 0
    cmp = json.loads((ROOT / "outputs" / "evidence" / "d1_h1_zero_api_reeval_v1"
                      / "comparison_capsule.json").read_text(encoding="utf-8"))
    assert cmp["zero_api"]["new_llm_api_calls"] == 0


# --------------------------------------------------------------------------- v2 gate dry-runs


def _load_report(name: str) -> dict:
    return json.loads((ROOT / "outputs" / "reports" / name)
                      .read_text(encoding="utf-8"))


def test_d1_v2_dry_run_zero_api_default_path() -> None:
    pkg = _load_report("direct_llm_method_gate_decision_dry_run_v2.json")
    assert pkg["status"] == "dry_run_not_applied"
    assert pkg["zero_api_path"]["new_llm_calls_required_for_default_path"] == 0
    assert pkg["zero_api_path"]["binding_ok"] is True
    # the v2 package states the corrected zero-API default path positively
    blob = json.dumps(pkg, ensure_ascii=False)
    assert pkg["zero_api_path"]["default_after_authorization"].startswith(
        "publish the existing bound snapshot zero-API")
    assert "binding breaks" in blob
    assert "was incorrect and is removed" in pkg["purpose"]
    assert "bound to formal input v2" in pkg["purpose"] or \
        "IS bound to formal input v2" in pkg["purpose"]
    assert "candidate" in pkg["purpose"].lower()


def test_h1_v2_dry_run_two_options_and_recommendation() -> None:
    pkg = _load_report("sun_llm_fallback_method_gate_decision_dry_run_v2.json")
    assert pkg["status"] == "dry_run_not_applied"
    opts = pkg["methods_json_change"]["options"]
    assert "A_recommended_ready_plus_role" in opts
    assert "B_keep_comparison_only_ready" in opts
    assert opts["A_recommended_ready_plus_role"][
        "audit_status_semantics_change_required"] is False
    assert opts["B_keep_comparison_only_ready"][
        "audit_status_semantics_change_required"] is True
    assert "Option A" in pkg["methods_json_change"]["recommended"]
    # simulated blockers honest: comparison_only_ready is NOT recognized
    sim_b = opts["B_keep_comparison_only_ready"]["simulated_blockers"]
    assert sim_b["formal_methods_not_ready"]["present"] is True
    # Option A would drop the blocker under current semantics
    sim_a = opts["A_recommended_ready_plus_role"]["simulated_blockers"]
    assert "sun_llm_fallback" not in sim_a["formal_methods_not_ready"][
        "non_ready_methods"]
    assert pkg["zero_api_path"]["new_llm_calls_required_for_default_path"] == 0
    assert "comparison-only" in pkg["purpose"].lower()


# --------------------------------------------------------------------------- hardening dry-run


def test_hardening_repro_all_three_ready_opens_gate() -> None:
    pkg = _load_report("final_readiness_hardening_dry_run.json")
    scenarios = pkg["minimal_reproduction"]["scenarios"]
    all_ready = scenarios["all_three_ready"]
    assert all_ready["final_experiment_ready (current status.py)"] is True
    assert all_ready["methods_unexpectedly_ready error (current audit.py)"] is True
    h1_proposed = scenarios["H1_comparison_only_ready_not_recognized"]
    assert h1_proposed["final_experiment_ready (current status.py)"] is False
    assert h1_proposed["method_blockers"]  # comparison_only_ready not recognized
    d1_alone = scenarios["D1_alone_ready"]
    assert d1_alone["final_experiment_ready (current status.py)"] is False
    assert "unified_authorization_sentence" in pkg
    assert "G0.4" in pkg["unified_authorization_sentence"]
    assert pkg["not_applied"] is True


def test_g04_decision_dry_run_not_applied() -> None:
    pkg = _load_report("g04_main_view_decision_dry_run.json")
    assert pkg["status"] == "dry_run_not_applied"
    assert pkg["proposal"]["modality_evidence_span_metrics"].startswith(
        "explicitly unavailable")
    assert pkg["proposal"]["no_gold_modification"] is True
    assert pkg["proposal"]["no_fabricated_modality_evidence_spans"] is True
    assert "never zeroed" in pkg["proposal"]["modality_evidence_span_metrics"]


# --------------------------------------------------------------------------- nothing applied


def test_methods_gold_contract_state_after_authorization() -> None:
    """2026-08-11 authorization applied to methods.json (D1/H1 ready);
    Gold and the experiment contract remain untouched."""
    methods = json.loads((ROOT / "configs" / "methods.json")
                         .read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in methods["methods"]}
    assert by_id["direct_llm"]["formal_status"] == "ready"
    assert by_id["direct_llm"]["command_status"] == \
        "formal_ready_candidate_authorized"
    assert by_id["sun_llm_fallback"]["formal_status"] == "ready"
    assert by_id["sun_llm_fallback"]["role"] == "comparison_arm_only"
    assert by_id["sun_rule_only"]["formal_status"] == "ready"
    gold = json.loads((ROOT / "data" / "gold" / "stage2"
                       / "estg150_formal_gold_v1.json")
                      .read_text(encoding="utf-8"))
    assert gold["schema_version"] == "stage2_formal_gold@1.0.0"
    contract = json.loads((ROOT / "configs" / "experiment_contract.json")
                          .read_text(encoding="utf-8"))
    assert contract["stage3"]["status"] == "locked"
