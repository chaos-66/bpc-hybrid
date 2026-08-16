"""Focused tests for the S2.11 / G0.5 pre-authorization decision capsule v5
(active capsule; v3/v4 are superseded historical capsules).

Covers:
  * ACTIVE v5 builder: deterministic byte-identical rebuild from current
    disk, no-overwrite refusal, no sensitive touches, references read-only
  * v5 verifier passes on the canonical outputs (seven independent
    verifiers executed, audit re-run)
  * v4 red-test facts recorded exactly (3 failed / test_returncode=1 /
    integrity_pass=false) and v5 restores the active suite integrity
  * supersedes declares v3 decision entries + full v3/v4 capsules; v3/v4
    CORE assets byte-exact against HEAD; lifecycle helper semantics
  * G0.5 raw-byte authorization hash domain (61938c99…) is the ONLY
    authorization hash; draft_not_frozen; not promotion-ready
  * gate ordering G1/G2/G5/G6 false+null, G3/G4 dry-run with raw-byte
    sentence binding
  * manifest/export exact-reconstruction negative cases
  * report-content tamper negative cases
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

from bpc_hybrid.capsule_lifecycle import (
    HistoricalCapsule,
    builder_rejects_with_no_overwrite_drift,
    historical_core_assets_match_head,
    verifier_rejection_is_binding_drift,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

BUILDER_SCRIPT = ROOT / "scripts" / "build_s2_11_g0_5_pre_authorization_v5.py"
VERIFIER_SCRIPT = ROOT / "scripts" / "verify_s2_11_g0_5_pre_authorization_v5.py"
OUT_JSON = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v5.json"
OUT_MD = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v5.md"
OUT_MANIFEST = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v5.manifest.json"
OUT_EXPORT = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v5_export_index.json"

REF_DIR = ROOT.parent / "references" / "barrientos_2026"
PDF_PATH = ROOT.parent / "references" / "papers" / \
    "Barrientos_2026_Impact_analysis.pdf"

DRAFT_RAW_SHA = \
    "61938c99a012f36b2b3b3d66a346b31a6c33fdd3f14be0179291ef1982a97586"
SEMANTIC_RAW_SHA = \
    "51a6e4fe43d33f79b33d14784d08266aff6576453daf9dca465de702ddae0760"

V3_CAPSULE = HistoricalCapsule(
    name="s2_11_g0_5_pre_authorization_v3",
    schema_rel="configs/schemas/s2_11_g0_5_pre_authorization_v3.schema.json",
    builder_rel="scripts/build_s2_11_g0_5_pre_authorization_v3.py",
    verifier_rel="scripts/verify_s2_11_g0_5_pre_authorization_v3.py",
    outputs=("outputs/reports/s2_11_g0_5_pre_authorization_v3.json",
             "outputs/reports/s2_11_g0_5_pre_authorization_v3.md",
             "outputs/reports/s2_11_g0_5_pre_authorization_v3.manifest.json",
             "outputs/reports/s2_11_g0_5_pre_authorization_v3_export_index.json"),
)
V4_CAPSULE = HistoricalCapsule(
    name="s2_11_g0_5_pre_authorization_v4",
    schema_rel="configs/schemas/s2_11_g0_5_pre_authorization_v4.schema.json",
    builder_rel="scripts/build_s2_11_g0_5_pre_authorization_v4.py",
    verifier_rel="scripts/verify_s2_11_g0_5_pre_authorization_v4.py",
    outputs=("outputs/reports/s2_11_g0_5_pre_authorization_v4.json",
             "outputs/reports/s2_11_g0_5_pre_authorization_v4.md",
             "outputs/reports/s2_11_g0_5_pre_authorization_v4.manifest.json",
             "outputs/reports/s2_11_g0_5_pre_authorization_v4_export_index.json"),
)


def _load_builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s2_11_g0_5_pre_authorization_builder_v5", BUILDER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_verifier() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s2_11_g0_5_pre_authorization_verifier_v5", VERIFIER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _copy_outputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    for src in (OUT_JSON, OUT_MD, OUT_MANIFEST, OUT_EXPORT):
        shutil.copy2(src, tmp_path / src.name)
    return (tmp_path / OUT_JSON.name, tmp_path / OUT_MANIFEST.name,
            tmp_path / OUT_EXPORT.name, tmp_path / OUT_MD.name)


def _tamper_manifest(tmp_path: Path,
                     mutate: Callable[[dict[str, Any]], None]) -> Path:
    _, man_p, _, _ = _copy_outputs(tmp_path)
    doc = _load(man_p)
    mutate(doc)
    man_p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    return man_p


def _tamper_export(tmp_path: Path,
                   mutate: Callable[[dict[str, Any]], None]) -> Path:
    _, _, exp_p, _ = _copy_outputs(tmp_path)
    doc = _load(exp_p)
    mutate(doc)
    exp_p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    return exp_p


def _verify_with(tmp_path: Path, manifest_p: Path, export_p: Path,
                 verifier: Any) -> dict[str, Any]:
    report_p = tmp_path / OUT_JSON.name
    md_p = tmp_path / OUT_MD.name
    return verifier.verify(report_path=report_p, manifest_path=manifest_p,
                           export_path=export_p, md_path=md_p,
                           run_external=False)


def _failed_check_names(result: dict[str, Any]) -> list[str]:
    return [c["name"] for c in result["checks"] if not c["ok"]]


def _failed_details(result: dict[str, Any]) -> str:
    return " || ".join(c["detail"] for c in result["checks"] if not c["ok"])


# ---------------------------------------------------------------------------
# ACTIVE v5 builder determinism
# ---------------------------------------------------------------------------
def test_v5_builder_byte_identical_rebuild_and_no_sensitive_touches() -> None:
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
        f"v5 builder failed: {proc.returncode}\n{proc.stdout}\n{proc.stderr}")
    second = {p: p.read_bytes() for p in outputs}
    for p in outputs:
        assert second[p] == first[p], (
            f"v5 builder rebuild is not byte-identical: {p}")
    after = {p: _sha(p.read_bytes()) for p in sensitive}
    assert after == before, (
        "v5 builder touched Gold / predictions / results / contract / methods")


def test_v5_builder_never_modifies_references() -> None:
    ref_files = sorted(p for p in REF_DIR.rglob("*") if p.is_file())
    ref_files.append(PDF_PATH)
    before = {str(p.relative_to(ROOT.parent)): _sha(p.read_bytes())
              for p in ref_files}
    proc = subprocess.run(
        [sys.executable, str(BUILDER_SCRIPT)], cwd=ROOT,
        capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    after = {str(p.relative_to(ROOT.parent)): _sha(p.read_bytes())
             for p in ref_files}
    assert after == before, "v5 builder modified references/"


def test_v5_builder_no_overwrite_refusal(tmp_path: Path) -> None:
    builder = _load_builder()
    target = tmp_path / "out.json"
    target.write_bytes(b"first")
    with pytest.raises(builder.BuilderFail):
        builder._write(target, b"second")
    builder._write(target, b"first")
    assert target.read_bytes() == b"first"


# ---------------------------------------------------------------------------
# ACTIVE v5 verifier
# ---------------------------------------------------------------------------
def test_v5_verifier_passes_on_canonical_outputs() -> None:
    verifier = _load_verifier()
    result = verifier.verify(run_external=True)
    assert result["verified"] is True, (
        "canonical v5 capsule must verify: " + _failed_details(result))


# ---------------------------------------------------------------------------
# v4 red-test facts
# ---------------------------------------------------------------------------
def test_v4_red_test_facts_recorded() -> None:
    report = _load(OUT_JSON)
    facts = report["v4_red_test_facts"]
    assert facts["v4_audit_not_verified"] is True
    assert facts["v4_change_event_failed_tests"] == 3
    assert facts["v4_change_event_test_returncode"] == 1
    assert facts["v4_change_event_integrity_pass"] is False
    assert facts["v5_restores_active_suite_integrity"] is True
    assert len(facts["minimal_counterexamples"]) >= 4
    joined = "\n".join(facts["minimal_counterexamples"]).lower()
    for needle in ("invalid_mode", "evidence_binding", "element_path",
                   "51a6e4fe"):
        assert needle in joined, f"missing counterexample needle: {needle}"


# ---------------------------------------------------------------------------
# Historical lifecycle semantics (helper-based)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("capsule", [V3_CAPSULE, V4_CAPSULE])
def test_historical_capsule_lifecycle_semantics(capsule: HistoricalCapsule,
                                                ) -> None:
    ok, changed = historical_core_assets_match_head(ROOT, capsule)
    assert ok, f"{capsule.name} core assets drifted from HEAD: {changed}"
    drift_ok, detail = builder_rejects_with_no_overwrite_drift(ROOT, capsule)
    assert drift_ok, (
        f"{capsule.name} builder must fail closed with a no-overwrite "
        f"rejection: {detail}")
    is_drift, vdetail = verifier_rejection_is_binding_drift(ROOT, capsule)
    assert is_drift, (
        f"{capsule.name} verifier rejection must be binding drift: "
        f"{vdetail}")


def test_supersedes_declares_v3_and_v4_capsules() -> None:
    report = _load(OUT_JSON)
    declared = {item["path"] for item in report["supersedes"]}
    required = [
        "configs/schemas/s2_11_g0_5_pre_authorization_v3.schema.json",
        "scripts/build_s2_11_g0_5_pre_authorization_v3.py",
        "scripts/verify_s2_11_g0_5_pre_authorization_v3.py",
        "tests/test_s2_11_g0_5_pre_authorization_v3.py",
        "outputs/reports/s2_11_g0_5_pre_authorization_v3.json",
        "outputs/reports/s2_11_g0_5_pre_authorization_v3.md",
        "outputs/reports/s2_11_g0_5_pre_authorization_v3.manifest.json",
        "outputs/reports/s2_11_g0_5_pre_authorization_v3_export_index.json",
        "configs/schemas/s2_11_g0_5_pre_authorization_v4.schema.json",
        "scripts/build_s2_11_g0_5_pre_authorization_v4.py",
        "scripts/verify_s2_11_g0_5_pre_authorization_v4.py",
        "tests/test_s2_11_g0_5_pre_authorization_v4.py",
        "outputs/reports/s2_11_g0_5_pre_authorization_v4.json",
        "outputs/reports/s2_11_g0_5_pre_authorization_v4.md",
        "outputs/reports/s2_11_g0_5_pre_authorization_v4.manifest.json",
        "outputs/reports/s2_11_g0_5_pre_authorization_v4_export_index.json",
        "outputs/reports/s2_11_license_adapter_readiness_v2.json",
        "outputs/reports/s2_11_data_qualification_mapping_dry_run.json",
        "outputs/reports/g0_7_barrientos_adapter_registry_dry_run.json",
        "outputs/reports/g0_7_barrientos_adapter_registry_dry_run.md",
    ]
    for path in required:
        assert path in declared, f"missing supersedes declaration: {path}"


# ---------------------------------------------------------------------------
# G0.5 raw-byte hash domain
# ---------------------------------------------------------------------------
def test_g05_raw_byte_hash_domain() -> None:
    report = _load(OUT_JSON)
    g5 = report["g0_5_candidate"]
    assert g5["status"] == "draft_not_frozen"
    assert g5["frozen"] is False
    assert g5["config_sha256"] == DRAFT_RAW_SHA
    assert g5["config_sha256"] != SEMANTIC_RAW_SHA
    config = _load(ROOT / g5["config_path"])
    assert config["status"] == "draft_not_frozen"
    pr = report["g0_5_promotion_readiness"]
    assert pr["g0_5_status"] == "draft_not_frozen"
    assert pr["promotion_ready_for_application"] is False
    assert any("user authorization manifest" in m for m in pr["missing"])
    assert pr["preregistration_claim_allowed"] is False
    # G4 dry-run sentence binds the RAW BYTE hash.
    g4 = next(g for g in report["user_gates"] if g["gate_id"] == "G4")
    assert DRAFT_RAW_SHA in g4["authorization_sentence"]
    assert "RAW BYTE sha256" in g4["authorization_sentence"]


# ---------------------------------------------------------------------------
# License separation + gates
# ---------------------------------------------------------------------------
def test_license_separation_and_gates() -> None:
    report = _load(OUT_JSON)
    la = report["license_audit"]
    assert la["paper_readable"] is True
    assert la["article_license"] == "CC-BY-4.0"
    assert la["article_license_scope"] == "article_only"
    assert la["article_license_does_not_auto_cover_artifact"] is True
    assert la["code_usable"] == "unknown_pending_confirmation"
    assert la["data_reusable"] == "unknown_pending_confirmation"
    assert la["ready_for_data_activation"] is False
    assert la["activation_authorization_sentence"] is None
    by_id = {g["gate_id"]: g for g in report["user_gates"]}
    for gate_id in ("G1", "G2", "G5", "G6"):
        gate = by_id[gate_id]
        assert gate["ready_for_authorization"] is False
        assert gate["authorization_sentence"] is None
    assert len(by_id["G5"]["missing"]) >= 4
    assert "Future sentence" in by_id["G5"].get(
        "future_authorization_sentence_after_prerequisites", "")
    builder = _load_builder()
    assert by_id["G3"]["authorization_sentence"] == builder.G3_SENTENCE
    assert by_id["G4"]["authorization_sentence"] == builder.g4_sentence(
        DRAFT_RAW_SHA)
    assert "Oracle" not in " ".join(
        g["authorization_sentence"] or "" for g in report["user_gates"])
    oc = report["oracle_control"]
    assert oc["formal_oracle_started"] is False
    assert oc["formal_oracle_authorized"] is False
    assert oc["ready_for_oracle_authorization"] is False
    assert oc["authorization_sentence"] is None
    assert oc["no_pseudo_oracle"] is True


def test_no_gold_no_api_no_gate_flips() -> None:
    report = _load(OUT_JSON)
    safety = report["safety"]
    assert safety["gates_unchanged"] is True
    assert safety["gold_predictions_results_contract_methods_unchanged"] is True
    assert safety["g0_5_frozen"] is False
    assert safety["references_read_only_not_activated"] is True
    assert safety["no_authorization_applied"] is True
    assert report["zero_api"]["new_llm_api_calls"] == 0
    matches = [p for p in (ROOT / "data" / "gold").rglob("*")
               if p.is_file() and (
                   "rule_record" in p.name.lower()
                   or "rule-record" in p.name.lower())]
    assert matches == []


def test_markdown_single_eof_newline() -> None:
    data = OUT_MD.read_bytes()
    assert data.endswith(b"\n")
    assert not data.endswith(b"\n\n")


# ---------------------------------------------------------------------------
# Manifest exact-reconstruction negative cases
# ---------------------------------------------------------------------------
def test_manifest_fails_on_emptied_bindings(tmp_path: Path) -> None:
    verifier = _load_verifier()
    man_p = _tamper_manifest(tmp_path, lambda m: m.update({"bindings": {}}))
    result = _verify_with(tmp_path, man_p, tmp_path / OUT_EXPORT.name,
                          verifier)
    assert result["verified"] is False
    assert any("manifest exact reconstruction" in n
               for n in _failed_check_names(result))


def test_manifest_fails_on_missing_one_binding(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(m: dict[str, Any]) -> None:
        m["bindings"].pop("references/papers/"
                          "Barrientos_2026_Impact_analysis.pdf")
    man_p = _tamper_manifest(tmp_path, mutate)
    result = _verify_with(tmp_path, man_p, tmp_path / OUT_EXPORT.name,
                          verifier)
    assert result["verified"] is False


def test_manifest_fails_on_emptied_implementation(tmp_path: Path) -> None:
    verifier = _load_verifier()
    man_p = _tamper_manifest(
        tmp_path, lambda m: m.update({"implementation": {}}))
    result = _verify_with(tmp_path, man_p, tmp_path / OUT_EXPORT.name,
                          verifier)
    assert result["verified"] is False


def test_manifest_fails_on_extra_unauthorized_binding(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(m: dict[str, Any]) -> None:
        m["bindings"]["configs/methods.json"] = "00" * 32
    man_p = _tamper_manifest(tmp_path, mutate)
    result = _verify_with(tmp_path, man_p, tmp_path / OUT_EXPORT.name,
                          verifier)
    assert result["verified"] is False


def test_manifest_fails_even_when_export_hash_recomputed(
        tmp_path: Path) -> None:
    verifier = _load_verifier()
    _, man_p, exp_p, _ = _copy_outputs(tmp_path)
    man_doc = _load(man_p)
    man_doc["bindings"].pop("docs/MASTER_PIPELINE.md")
    man_bytes = (json.dumps(man_doc, ensure_ascii=False, indent=2) + "\n") \
        .encode("utf-8")
    man_p.write_bytes(man_bytes)
    exp_doc = _load(exp_p)
    exp_doc["manifest"]["sha256"] = _sha(man_bytes)
    exp_doc["manifest"]["byte_size"] = len(man_bytes)
    exp_doc["artifacts"]["manifest"]["sha256"] = _sha(man_bytes)
    exp_doc["artifacts"]["manifest"]["byte_size"] = len(man_bytes)
    exp_p.write_text(json.dumps(exp_doc, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    result = _verify_with(tmp_path, man_p, exp_p, verifier)
    assert result["verified"] is False


# ---------------------------------------------------------------------------
# Export exact-reconstruction negative cases
# ---------------------------------------------------------------------------
def test_export_fails_on_missing_entry(tmp_path: Path) -> None:
    verifier = _load_verifier()
    exp_p = _tamper_export(
        tmp_path, lambda e: e["artifacts"].pop("report_json"))
    result = _verify_with(tmp_path, tmp_path / OUT_MANIFEST.name, exp_p,
                          verifier)
    assert result["verified"] is False


def test_export_fails_on_extra_entry(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(e: dict[str, Any]) -> None:
        e["artifacts"]["bogus"] = {"path": "x.json", "sha256": "00" * 32,
                                   "byte_size": 1}
    exp_p = _tamper_export(tmp_path, mutate)
    result = _verify_with(tmp_path, tmp_path / OUT_MANIFEST.name, exp_p,
                          verifier)
    assert result["verified"] is False


def test_export_fails_even_when_hashes_recomputed(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(e: dict[str, Any]) -> None:
        entry = e["artifacts"]["report_md"]
        other = OUT_JSON.read_bytes()
        entry["path"] = "outputs/reports/s2_11_g0_5_pre_authorization_v5.json"
        entry["sha256"] = _sha(other)
        entry["byte_size"] = len(other)
    exp_p = _tamper_export(tmp_path, mutate)
    result = _verify_with(tmp_path, tmp_path / OUT_MANIFEST.name, exp_p,
                          verifier)
    assert result["verified"] is False


# ---------------------------------------------------------------------------
# Report-content tamper negative cases
# ---------------------------------------------------------------------------
def _tamper_report(tmp_path: Path,
                   mutate: Callable[[dict[str, Any]], None],
                   verifier: Any) -> dict[str, Any]:
    _, man_p, exp_p, _ = _copy_outputs(tmp_path)
    report = _load(OUT_JSON)
    mutate(report)
    (tmp_path / OUT_JSON.name).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    builder = _load_builder()
    (tmp_path / OUT_MD.name).write_bytes(
        builder.render_md(report).encode("utf-8"))
    return verifier.verify(report_path=tmp_path / OUT_JSON.name,
                           manifest_path=man_p, export_path=exp_p,
                           md_path=tmp_path / OUT_MD.name,
                           run_external=False)


def test_report_fails_when_v4_facts_hidden(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(r: dict[str, Any]) -> None:
        r["v4_red_test_facts"]["v4_audit_not_verified"] = False
    result = _tamper_report(tmp_path, mutate, verifier)
    assert result["verified"] is False


def test_report_fails_when_g4_hash_not_raw_bytes(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(r: dict[str, Any]) -> None:
        for gate in r["user_gates"]:
            if gate["gate_id"] == "G4":
                gate["authorization_sentence"] = (
                    "I authorize freezing the G0.5 contract (semantic "
                    "hash 51a6e4fe…).")
    result = _tamper_report(tmp_path, mutate, verifier)
    assert result["verified"] is False
    assert any("G3/G4 ready=true" in n for n in _failed_check_names(result))


def test_report_fails_when_g5_marked_ready(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(r: dict[str, Any]) -> None:
        for gate in r["user_gates"]:
            if gate["gate_id"] == "G5":
                gate["ready_for_authorization"] = True
                gate["authorization_sentence"] = "I authorize the surface"
    result = _tamper_report(tmp_path, mutate, verifier)
    assert result["verified"] is False


def test_report_fails_when_adapter_not_hardened(tmp_path: Path) -> None:
    verifier = _load_verifier()
    result = _tamper_report(
        tmp_path,
        lambda r: r["adapter_status"].update({"hardened": False}),
        verifier)
    assert result["verified"] is False


def test_report_fails_when_promotion_ready(tmp_path: Path) -> None:
    verifier = _load_verifier()
    result = _tamper_report(
        tmp_path,
        lambda r: r["g0_5_promotion_readiness"].update(
            {"promotion_ready_for_application": True}),
        verifier)
    assert result["verified"] is False
