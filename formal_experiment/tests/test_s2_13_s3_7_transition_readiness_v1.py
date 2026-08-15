# -*- coding: utf-8 -*-
"""Focused tests for the S2.13 -> S3.7 transition readiness capsule v1.

Covers:
  * deterministic, byte-identical builder rebuild + no-overwrite refusal
  * the builder never touches Gold / predictions / results / contract /
    methods / gates
  * the independent verifier passes on the canonical outputs (with the seven
    independent verifiers actually executed and the audit re-run)
  * fail-closed negative cases: missing file, hash/content tamper,
    prediction disguised as Gold Rule Records, dropped rule ID, forged
    Oracle authorization, S2.13 mislabeled complete, development promoted
    to formal, dropped verifier entry
  * audit regression: with final_experiment_ready=true the audit no longer
    emits the stale contradictory "remains false" / "capsule NOT produced
    yet" statements
  * stale pre-freeze reports remain byte-unchanged and are explicitly
    superseded (never overwritten)
  * no Gold Rule Record was created or inferred (9-rule-ID absence guard)
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

BUILDER_SCRIPT = ROOT / "scripts" / "build_s2_13_s3_7_transition_readiness_v1.py"
VERIFIER_SCRIPT = ROOT / "scripts" / "verify_s2_13_s3_7_transition_readiness_v1.py"
OUT_JSON = ROOT / "outputs" / "reports" / \
    "s2_13_s3_7_transition_readiness_v1.json"
OUT_MD = ROOT / "outputs" / "reports" / \
    "s2_13_s3_7_transition_readiness_v1.md"
OUT_MANIFEST = ROOT / "outputs" / "reports" / \
    "s2_13_s3_7_transition_readiness_v1.manifest.json"
OUT_EXPORT = ROOT / "outputs" / "reports" / \
    "s2_13_s3_7_transition_readiness_v1_export_index.json"

EXPECTED_RULE_IDS = [
    "article6", "article7", "article15", "article16", "article17",
    "article20", "article22", "article33", "article34",
]


def _load_builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s2_13_s3_7_transition_readiness_builder", BUILDER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_verifier() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s2_13_s3_7_transition_readiness_verifier", VERIFIER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _republish(tmp_path: Path,
               mutate: Callable[[dict[str, Any]], None]) -> tuple[Path, Path, Path, Path]:
    """Write a tampered report (+ re-rendered md + real manifest/export
    copies) into tmp_path so the verifier can be pointed at them."""
    builder = _load_builder()
    report = _load(OUT_JSON)
    mutate(report)
    report_p = tmp_path / "report.json"
    report_p.write_text(json.dumps(report, ensure_ascii=False, indent=2)
                        + "\n", encoding="utf-8")
    md_p = tmp_path / "report.md"
    md_p.write_bytes(builder.render_md(report).encode("utf-8"))
    man_p = tmp_path / "manifest.json"
    man_p.write_bytes(OUT_MANIFEST.read_bytes())
    exp_p = tmp_path / "export_index.json"
    exp_p.write_bytes(OUT_EXPORT.read_bytes())
    return report_p, man_p, exp_p, md_p


def _failed_check_names(result: dict[str, Any]) -> list[str]:
    return [c["name"] for c in result["checks"] if not c["ok"]]


def _failed_details(result: dict[str, Any]) -> str:
    return " || ".join(c["detail"] for c in result["checks"] if not c["ok"])


# ---------------------------------------------------------------------------
# Builder determinism and no-overwrite
# ---------------------------------------------------------------------------
def test_builder_byte_identical_rebuild_and_no_sensitive_touches() -> None:
    sensitive = [
        ROOT / "data" / "gold" / "stage1" / "process_records" /
        "stage1_process_gold_v1.json",
        ROOT / "data" / "gold" / "stage3" / "stage3_matching_gold_v1.json",
        ROOT / "data" / "gold" / "stage3" / "stage3_violation_gold_v1.json",
        ROOT / "data" / "predictions" / "b0_formal_arm_v1" /
        "predictions.json",
        ROOT / "data" / "results" / "b0_formal_arm_v1" /
        "evaluation_coarse.json",
        ROOT / "configs" / "experiment_contract.json",
        ROOT / "configs" / "methods.json",
    ]
    before = {p: _sha(p.read_bytes()) for p in sensitive}
    outputs = [OUT_JSON, OUT_MD, OUT_MANIFEST, OUT_EXPORT]
    first = {p: p.read_bytes() if p.exists() else None for p in outputs}
    proc = subprocess.run(
        [sys.executable, str(BUILDER_SCRIPT)], cwd=ROOT,
        capture_output=True, text=True, check=False)
    assert proc.returncode == 0, (
        f"builder failed: {proc.returncode}\n{proc.stdout}\n{proc.stderr}")
    second = {p: p.read_bytes() for p in outputs}
    for p in outputs:
        assert second[p] == first[p], (
            f"builder rebuild is not byte-identical: {p}")
    after = {p: _sha(p.read_bytes()) for p in sensitive}
    assert after == before, (
        "builder touched Gold / predictions / results / contract / methods")


def test_builder_no_overwrite_refusal(tmp_path: Path) -> None:
    builder = _load_builder()
    target = tmp_path / "out.json"
    target.write_bytes(b"first")
    with pytest.raises(builder.BuilderFail):
        builder._write(target, b"second")
    builder._write(target, b"first")  # identical bytes allowed
    assert target.read_bytes() == b"first"


# ---------------------------------------------------------------------------
# Positive verifier run (executes the seven verifiers + audit)
# ---------------------------------------------------------------------------
def test_verifier_passes_on_canonical_outputs() -> None:
    verifier = _load_verifier()
    result = verifier.verify(run_external=True)
    assert result["verified"] is True, (
        "canonical capsule must verify: " + _failed_details(result))


def test_report_declares_and_binds_superseded_stale_reports() -> None:
    report = _load(OUT_JSON)
    declared = {item["path"] for item in report["supersedes"]}
    stale = [
        "outputs/reports/s2_13_stage2_freeze_gap_capsule.json",
        "outputs/reports/s2_13_stage2_freeze_gap_capsule.md",
        "outputs/reports/s3_7_oracle_readiness_v2.json",
        "outputs/reports/s37_oracle_readiness_v1.json",
        "outputs/reports/formal_benchmark_release_v2.manifest.json",
        "scripts/build_s1_5_s3_7_readiness_v1.py",
        "scripts/build_s3_7_oracle_readiness.py",
    ]
    for path in stale:
        assert path in declared
    for item in report["supersedes"]:
        p = ROOT / item["path"]
        assert p.is_file()
        assert _sha(p.read_bytes()) == item["sha256"], (
            f"superseded asset {item['path']} was modified on disk")


def test_no_gold_rule_record_created_or_inferred() -> None:
    matches = [p for p in (ROOT / "data" / "gold").rglob("*")
               if p.is_file() and "rule_record" in p.name.lower()]
    assert matches == [], (
        f"Gold Rule Records must not exist, found: {matches}")
    report = _load(OUT_JSON)
    assert report["gold_rule_records"]["exist"] is False
    assert set(report["gold_rule_records"]["covered_rule_ids"]) == \
        set(EXPECTED_RULE_IDS)


# ---------------------------------------------------------------------------
# Fail-closed negative cases
# ---------------------------------------------------------------------------
def test_verifier_fails_on_missing_report_file(tmp_path: Path) -> None:
    verifier = _load_verifier()
    result = verifier.verify(report_path=tmp_path / "missing.json",
                             manifest_path=tmp_path / "missing_manifest.json",
                             export_path=tmp_path / "missing_export.json",
                             md_path=tmp_path / "missing.md",
                             run_external=False)
    assert result["verified"] is False
    assert "report JSON readable" in _failed_check_names(result)


def test_verifier_fails_on_content_tamper(tmp_path: Path) -> None:
    verifier = _load_verifier()
    report_p = tmp_path / "report.json"
    corrupted = OUT_JSON.read_bytes().replace(b'"report_id"', b'"report_xd"',
                                              1)
    report_p.write_bytes(corrupted)
    man_p = tmp_path / "manifest.json"
    man_p.write_bytes(OUT_MANIFEST.read_bytes())
    exp_p = tmp_path / "export_index.json"
    exp_p.write_bytes(OUT_EXPORT.read_bytes())
    md_p = tmp_path / "report.md"
    md_p.write_bytes(OUT_MD.read_bytes())
    result = verifier.verify(report_path=report_p, manifest_path=man_p,
                             export_path=exp_p, md_path=md_p,
                             run_external=False)
    assert result["verified"] is False


def test_verifier_fails_prediction_disguised_as_gold_rule_records(
        tmp_path: Path) -> None:
    def mutate(report: dict[str, Any]) -> None:
        report["gold_rule_records"]["exist"] = True
    paths = _republish(tmp_path, mutate)
    verifier = _load_verifier()
    result = verifier.verify(report_path=paths[0], manifest_path=paths[1],
                             export_path=paths[2], md_path=paths[3],
                             run_external=False)
    assert result["verified"] is False
    assert "Gold Rule Records absence and 9 rule IDs re-derived" in \
        _failed_check_names(result)


def test_verifier_fails_on_dropped_rule_id(tmp_path: Path) -> None:
    def mutate(report: dict[str, Any]) -> None:
        report["gold_rule_records"]["covered_rule_ids"].pop()
    paths = _republish(tmp_path, mutate)
    verifier = _load_verifier()
    result = verifier.verify(report_path=paths[0], manifest_path=paths[1],
                             export_path=paths[2], md_path=paths[3],
                             run_external=False)
    assert result["verified"] is False
    assert "Gold Rule Records absence and 9 rule IDs re-derived" in \
        _failed_check_names(result)


def test_verifier_fails_on_forged_oracle_authorization(
        tmp_path: Path) -> None:
    def mutate(report: dict[str, Any]) -> None:
        report["oracle_control"]["formal_oracle_authorized"] = True
        report["oracle_control"]["authorization_sentence"] = \
            "I authorize starting the formal Oracle"
    paths = _republish(tmp_path, mutate)
    verifier = _load_verifier()
    result = verifier.verify(report_path=paths[0], manifest_path=paths[1],
                             export_path=paths[2], md_path=paths[3],
                             run_external=False)
    assert result["verified"] is False
    assert "oracle control flags re-derived" in _failed_check_names(result)


def test_verifier_fails_on_s2_13_marked_complete(tmp_path: Path) -> None:
    def mutate(report: dict[str, Any]) -> None:
        for item in report["dependency_matrix"]["stage2"]:
            if item["task_id"] == "S2.13":
                item["status"] = "verified"
                item["blockers"] = []
    paths = _republish(tmp_path, mutate)
    verifier = _load_verifier()
    result = verifier.verify(report_path=paths[0], manifest_path=paths[1],
                             export_path=paths[2], md_path=paths[3],
                             run_external=False)
    assert result["verified"] is False
    assert "S2.13" in _failed_details(result)
    assert any("dependency matrix re-derived" in name
               for name in _failed_check_names(result))


def test_verifier_fails_on_development_promoted_to_formal(
        tmp_path: Path) -> None:
    def mutate(report: dict[str, Any]) -> None:
        report["stage3_development_only"]["s3_4"]["status"] = "verified"
    paths = _republish(tmp_path, mutate)
    verifier = _load_verifier()
    result = verifier.verify(report_path=paths[0], manifest_path=paths[1],
                             export_path=paths[2], md_path=paths[3],
                             run_external=False)
    assert result["verified"] is False
    assert any("NOT promoted to formal" in name
               for name in _failed_check_names(result))


def test_verifier_fails_on_dropped_verifier_entry(tmp_path: Path) -> None:
    def mutate(report: dict[str, Any]) -> None:
        report["verifiers_executed"].pop(
            "scripts/verify_stage1_process_gold.py")
    paths = _republish(tmp_path, mutate)
    verifier = _load_verifier()
    result = verifier.verify(report_path=paths[0], manifest_path=paths[1],
                             export_path=paths[2], md_path=paths[3],
                             run_external=False)
    assert result["verified"] is False
    assert "report schema valid" in _failed_check_names(result)


# ---------------------------------------------------------------------------
# Audit contradiction regression (audit.py dynamic wording fix)
# ---------------------------------------------------------------------------
def test_audit_never_contradicts_its_own_final_ready_value() -> None:
    from formal_experiment.audit import collect_project_audit
    audit = collect_project_audit()
    final_ready = bool(audit["final_experiment_ready"])
    claim_boundary = str(audit.get("claim_boundary", ""))
    warnings = audit.get("findings", {}).get("warnings", [])
    estg_warning = " ".join(
        item.get("message", "") for item in warnings
        if item.get("code") == "estg_reconstruction_development_only")
    capsule_pass = any(
        item.get("code") == "formal_predictions_results_capsule_complete"
        for item in audit.get("findings", {}).get("passes", []))
    if final_ready:
        # the stale contradictory wording must be gone
        assert "remains false" not in claim_boundary
        assert "NOT produced yet" not in claim_boundary
        assert "remains false" not in estg_warning
        assert "does NOT mean S2.13" in claim_boundary
        assert "capsule covers all three methods" in claim_boundary
    # regardless of state, the capsule wording must agree with the
    # derived pass (no true/false contradiction in either direction)
    assert ("capsule covers all three methods" in claim_boundary) == \
        capsule_pass
