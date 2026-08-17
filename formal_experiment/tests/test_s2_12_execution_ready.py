"""Focused tests for the S2.12 Checkpoint D execution readiness (zero
LLM/API, fail-closed).

Covers:
  * stratified evaluator: deterministic synthetic run, explicit error-type
    accounting (correct/missed/misclassified/extra), fail-closed on sample
    mismatch / missing field / bad level / empty set
  * execution-ready builder: deterministic double build, frozen plan with
    preregistration, G0.5 strata counts (36 records), S2.11 freeze not
    reached, API budget dry-run (0 calls, sentence unused), no Gold
  * independent verifier: passes on committed assets; fails closed on
    tampered plan status / tampered readiness gates / tampered binding
  * no >=40-char contiguous raw corpus fragment in any committed S2.12
    asset; reviewer/user never written
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from bpc_hybrid.s2_12_stratified_evaluator import (
    DECISION_FIELDS,
    EvaluatorFail,
    evaluate,
)
import s2_12_build_execution_ready as builder
import verify_s2_12_execution_ready as verifier

ROOT = Path(__file__).resolve().parents[1]

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
PLAN_CONFIG_REL = "configs/s2_12_execution_plan_v1.json"
PLAN_REPORT_REL = "outputs/reports/s2_12_execution_plan_v1.json"
READINESS_REL = "outputs/reports/s2_12_execution_readiness_v1.json"

VERIFIER_INPUTS = [
    MEMBERSHIP_REL,
    "configs/g05_complexity_frozen_v1.json",
    "configs/g05_complexity_candidate_draft_v1.json",
    "configs/g05_authorization_manifest_v1.json",
    "data/development/human_review/s2_11_review_decisions_v1.json",
    "outputs/reports/s2_11_g5_review_surface_v1.json",
    "outputs/reports/s2_11_candidate_run_v1.json",
    "outputs/reports/s2_11_proposal_report_v1.json",
    "outputs/reports/s2_11_batch_import_dry_run_v1.json",
    PLAN_CONFIG_REL,
    PLAN_REPORT_REL,
    READINESS_REL,
]


def _load(rel: str) -> dict[str, Any]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _has_40_char_corpus_fragment(blob: str) -> bool:
    membership = _load(MEMBERSHIP_REL)
    for record_id, rec in membership["records"].items():
        doc = json.loads(
            (ROOT.parent / rec["path"]).read_bytes().decode("utf-8"))
        scenario, rid, version = record_id.split("/")
        for entry in doc:
            if str(entry.get("ID")) == rid and \
                    str(entry.get("version")) == version.lstrip("v"):
                text = entry["text"]
                for i in range(len(text) - 39):
                    if text[i:i + 40] in blob:
                        return True
                break
    return False


# ---------------------------------------------------------------------------
# Stratified evaluator
# ---------------------------------------------------------------------------
def _fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    predictions = {
        "s1": {"modality": "obligation", "actor": "nurse", "action": "a",
               "condition": None, "constraint": None, "exception": None},
        "s2": {"modality": "obligation", "actor": "nurse", "action": "b",
               "condition": None, "constraint": None, "exception": None},
        "s3": {"modality": "permission", "actor": "nurse", "action": "c",
               "condition": None, "constraint": None, "exception": None},
    }
    gold = {
        "s1": {"modality": "obligation", "actor": "nurse", "action": "a",
               "condition": None, "constraint": None, "exception": None},
        "s2": {"modality": "obligation", "actor": "doctor", "action": "b",
               "condition": None, "constraint": None, "exception": None},
        "s3": {"modality": "obligation", "actor": "nurse", "action": "d",
               "condition": None, "constraint": None, "exception": None},
    }
    levels = {"s1": "L1", "s2": "L1", "s3": "L1"}
    return predictions, gold, levels


def test_evaluator_deterministic_and_error_types() -> None:
    predictions, gold, levels = _fixture()
    first = evaluate(predictions, gold, levels)
    second = evaluate(predictions, gold, levels)
    assert first == second
    assert first["sample_count"] == 3
    f1 = first["strata"]["L1"]["per_field"]
    # modality: s1 correct, s2 correct, s3 misclassified (permission vs
    # obligation) -> tp=2, fp=1, fn=1
    assert f1["modality"]["error_types"] == {
        "correct": 2, "missed": 0, "misclassified": 1, "extra": 0}
    assert f1["modality"]["precision"] == pytest.approx(0.6667)
    assert f1["modality"]["recall"] == pytest.approx(0.6667)
    # s1 actor correct; s2 actor misclassified; s3 actor correct
    assert f1["actor"]["error_types"]["correct"] == 2
    assert f1["actor"]["error_types"]["misclassified"] == 1
    # s1 action correct; s2 correct; s3 misclassified
    assert f1["action"]["error_types"]["correct"] == 2
    assert f1["action"]["error_types"]["misclassified"] == 1
    # absent fields (both null everywhere): no errors, no correct counts
    assert f1["exception"]["error_types"] == {
        "correct": 0, "missed": 0, "misclassified": 0, "extra": 0}


def test_evaluator_extra_type() -> None:
    predictions = {
        "s1": {"modality": "obligation", "actor": "nurse", "action": "a",
               "condition": "x", "constraint": None, "exception": None},
    }
    gold = {
        "s1": {"modality": "obligation", "actor": "nurse", "action": "a",
               "condition": None, "constraint": None, "exception": None},
    }
    result = evaluate(predictions, gold, {"s1": "L1"})
    et = result["strata"]["L1"]["per_field"]["condition"]["error_types"]
    assert et == {"correct": 0, "missed": 0, "misclassified": 0, "extra": 1}
    assert result["strata"]["L1"]["per_field"]["condition"]["extra"] == 1


def test_evaluator_fail_closed_sample_mismatch() -> None:
    predictions, gold, levels = _fixture()
    del predictions["s3"]
    with pytest.raises(EvaluatorFail, match="sample mismatch"):
        evaluate(predictions, gold, levels)


def test_evaluator_fail_closed_missing_field() -> None:
    predictions, gold, levels = _fixture()
    del predictions["s1"]["actor"]
    with pytest.raises(EvaluatorFail, match="missing field"):
        evaluate(predictions, gold, levels)


def test_evaluator_fail_closed_bad_level() -> None:
    predictions, gold, levels = _fixture()
    levels["s1"] = "L9"
    with pytest.raises(EvaluatorFail, match="outside"):
        evaluate(predictions, gold, levels)


def test_evaluator_fail_closed_empty() -> None:
    with pytest.raises(EvaluatorFail, match="empty sample set"):
        evaluate({}, {}, {})


def test_evaluator_levels_mismatch() -> None:
    predictions, gold, levels = _fixture()
    levels["s4"] = "L1"
    with pytest.raises(EvaluatorFail, match="levels sample mismatch"):
        evaluate(predictions, gold, levels)


# ---------------------------------------------------------------------------
# Builder (pure build(); writes go to the real ROOT only via main())
# ---------------------------------------------------------------------------
def test_builder_deterministic_double_build() -> None:
    first = json.dumps(builder.build(), sort_keys=True, ensure_ascii=False)
    second = json.dumps(builder.build(), sort_keys=True, ensure_ascii=False)
    assert first == second


def test_builder_plan_frozen_and_preregistered() -> None:
    plan_config, plan_report, readiness = builder.build()
    assert plan_config["status"] == "frozen"
    pre = plan_config["preregistration"]
    assert pre["declared_before_results"] is True
    assert set(pre["strata_level_counts"]) == {"L1", "L2", "L3"}
    assert sum(pre["strata_level_counts"].values()) == 36
    assert plan_config["gold"]["gold_files_created"] is False
    assert plan_config["zero_api"] == {"new_llm_api_calls": 0}
    assert plan_report["population"]["review_population"] == 36
    assert readiness["status"] == "ready_for_execution_pending_user_gates"
    assert readiness["runner"]["real_run_refused"] is True
    assert readiness["gates"]["s2_11_freeze"]["ready"] is False
    assert readiness["gates"]["api_budget_authorization"]["ready"] is False


def test_builder_api_budget_dry_run_sentence_unused() -> None:
    _, plan_report, readiness = builder.build()
    budget = plan_report["api_budget_dry_run"]
    assert budget["status"] == "dry_run_not_applied"
    assert budget["calls_made"] == 0
    assert budget["authorized"] is False
    assert budget["sentence_used"] is False
    assert budget["typical_total"] == 72
    assert budget["hard_cap"] == 100
    assert readiness["api_budget_dry_run"] == budget


def test_committed_assets_match_builder_output() -> None:
    plan_config, plan_report, readiness = builder.build()
    assert plan_config == _load(PLAN_CONFIG_REL)
    assert plan_report == _load(PLAN_REPORT_REL)
    assert readiness == _load(READINESS_REL)


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------
def test_verifier_passes_on_committed_assets() -> None:
    result = verifier.verify()
    assert result["verified"] is True, \
        "; ".join(c["name"] for c in result["checks"] if not c["ok"])


@pytest.fixture()
def verifier_tmp(tmp_path: Path):
    """Copy the 12 verifier inputs into a tmp formal_experiment tree."""
    root = tmp_path / "formal_experiment"
    for rel in VERIFIER_INPUTS:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    old = verifier.ROOT
    verifier.ROOT = root
    yield root
    verifier.ROOT = old


def test_verifier_fails_on_tampered_plan_status(verifier_tmp: Path) -> None:
    p = verifier_tmp / PLAN_CONFIG_REL
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["status"] = "unfrozen"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    result = verifier.verify()
    assert result["verified"] is False
    assert any("plan is frozen" in c["name"] for c in result["checks"]
               if not c["ok"])


def test_verifier_fails_on_tampered_readiness_gates(
        verifier_tmp: Path) -> None:
    p = verifier_tmp / READINESS_REL
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["gates"]["s2_11_freeze"]["ready"] = True
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    result = verifier.verify()
    assert result["verified"] is False


def test_verifier_fails_on_tampered_binding(verifier_tmp: Path) -> None:
    p = verifier_tmp / PLAN_REPORT_REL
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["bindings"][MEMBERSHIP_REL] = "00" * 64
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    result = verifier.verify()
    assert result["verified"] is False
    assert any("plan report bindings exact" in c["name"]
               for c in result["checks"] if not c["ok"])


def test_verifier_fails_when_api_event_exists(verifier_tmp: Path) -> None:
    event = verifier_tmp / "configs" / "s2_12_api_budget_authorization_v1.json"
    event.write_text(json.dumps({"forged": True}), encoding="utf-8")
    result = verifier.verify()
    assert result["verified"] is False
    assert any("no API budget authorization event exists" in c["name"]
               for c in result["checks"] if not c["ok"])


# ---------------------------------------------------------------------------
# Containment
# ---------------------------------------------------------------------------
def test_committed_s2_12_assets_have_no_raw_corpus_fragments() -> None:
    for rel in (PLAN_CONFIG_REL, PLAN_REPORT_REL, READINESS_REL):
        blob = json.dumps(_load(rel), ensure_ascii=False)
        assert not _has_40_char_corpus_fragment(blob), rel
    # reviewer/user is never written anywhere
    for rel in (PLAN_CONFIG_REL, PLAN_REPORT_REL, READINESS_REL):
        blob = json.dumps(_load(rel), ensure_ascii=False)
        assert '"reviewer": "user"' not in blob
        assert "reviewer_never_user" not in blob  # no false claim needed
    assert _sha((ROOT / READINESS_REL).read_bytes()) == \
        _sha((ROOT / READINESS_REL).read_bytes())
