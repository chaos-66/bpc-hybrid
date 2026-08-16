"""Focused tests for the S2.11 / G0.5 pre-authorization decision capsule v4
(corrective, now a SUPERSEDED historical capsule under v6 lifecycle
semantics).

v4's core assets (schema/builder/verifier/four outputs) stay byte-exact,
anchored to the FIXED v4 ORIGIN COMMIT 8e8b488ea6d91ef0e6d0cf942ff9729e3e6776f6
(hardcoded SHA-256 map, independent of HEAD). Once the assets its
manifest binds legitimately evolve, the historical v4 builder MUST fail
closed with a no-overwrite rejection and the historical v4 verifier MUST
reject with a declared binding/state-drift diagnosis.

Covers:
  * historical core assets match the FIXED ORIGIN map (disk bytes AND
    origin-commit git blobs); the historical builder fails closed
    (no-overwrite) and never touches Gold/predictions/results/
    contract/methods/references
  * the historical verifier rejection belongs to the declared
    binding/state-drift patterns and never modifies outputs
  * v3 capsule files byte-exact against HEAD
  * article vs artifact license separation with the REAL publisher PDF
    evidence chain (PyPDF2 re-extraction of DOI / CC BY statement /
    artifact URL / title)
  * G0.5 promotion readiness (draft_not_frozen, not promotion-ready)
  * gate ordering: G1/G2/G5/G6 ready=false+null, G3/G4 ready=true with
    exact dry-run sentences, G5 conditional future sentence only
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
    historical_core_assets_match_fixed_origin,
    verifier_rejection_is_binding_drift,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

BUILDER_SCRIPT = ROOT / "scripts" / "build_s2_11_g0_5_pre_authorization_v4.py"
VERIFIER_SCRIPT = ROOT / "scripts" / "verify_s2_11_g0_5_pre_authorization_v4.py"
OUT_JSON = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v4.json"
OUT_MD = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v4.md"
OUT_MANIFEST = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v4.manifest.json"
OUT_EXPORT = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v4_export_index.json"

REF_DIR = ROOT.parent / "references" / "barrientos_2026"
PDF_PATH = ROOT.parent / "references" / "papers" / \
    "Barrientos_2026_Impact_analysis.pdf"

# v3 core assets must stay byte-exact; the v3 TEST file may legitimately
# change under the v5 lifecycle semantics (test-semantics correction only).
V3_TEST_FILE = "tests/test_s2_11_g0_5_pre_authorization_v3.py"
V3_CORE_FILES = [
    "configs/schemas/s2_11_g0_5_pre_authorization_v3.schema.json",
    "scripts/build_s2_11_g0_5_pre_authorization_v3.py",
    "scripts/verify_s2_11_g0_5_pre_authorization_v3.py",
    "outputs/reports/s2_11_g0_5_pre_authorization_v3.json",
    "outputs/reports/s2_11_g0_5_pre_authorization_v3.md",
    "outputs/reports/s2_11_g0_5_pre_authorization_v3.manifest.json",
    "outputs/reports/s2_11_g0_5_pre_authorization_v3_export_index.json",
]


def _load_builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s2_11_g0_5_pre_authorization_builder_v4", BUILDER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_verifier() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s2_11_g0_5_pre_authorization_verifier_v4", VERIFIER_SCRIPT)
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
# Historical capsule lifecycle semantics (v6): v4 is a SUPERSEDED capsule.
# Its core assets stay byte-exact against the FIXED v4 ORIGIN COMMIT
# (8e8b488e…; hardcoded SHA-256 map, independent of HEAD); once the
# assets its manifest binds legitimately evolve, the historical builder
# MUST fail closed with a no-overwrite rejection and the historical
# verifier MUST reject with a binding/state-drift diagnosis.
# ---------------------------------------------------------------------------
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


def test_historical_core_assets_match_fixed_origin_and_builder_fails_closed() -> None:
    ok, detail = historical_core_assets_match_fixed_origin(ROOT, "v4")
    assert ok, f"v4 core assets drifted from the fixed origin anchor: {detail}"
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
    drift_ok, detail = builder_rejects_with_no_overwrite_drift(ROOT,
                                                               V4_CAPSULE)
    assert drift_ok, (
        "v4 builder must fail closed with a no-overwrite rejection when "
        f"its bound assets evolved: {detail}")
    after = {p: _sha(p.read_bytes()) for p in sensitive}
    assert after == before, (
        "historical builder touched Gold / predictions / results / "
        "contract / methods")


def test_historical_builder_never_modifies_references() -> None:
    ref_files = sorted(p for p in REF_DIR.rglob("*") if p.is_file())
    ref_files.append(PDF_PATH)
    before = {str(p.relative_to(ROOT.parent)): _sha(p.read_bytes())
              for p in ref_files}
    drift_ok, detail = builder_rejects_with_no_overwrite_drift(ROOT,
                                                               V4_CAPSULE)
    assert drift_ok, detail
    after = {str(p.relative_to(ROOT.parent)): _sha(p.read_bytes())
             for p in ref_files}
    assert after == before, "historical builder modified references/"


def test_builder_no_overwrite_refusal(tmp_path: Path) -> None:
    builder = _load_builder()
    target = tmp_path / "out.json"
    target.write_bytes(b"first")
    with pytest.raises(builder.BuilderFail):
        builder._write(target, b"second")
    builder._write(target, b"first")
    assert target.read_bytes() == b"first"


# ---------------------------------------------------------------------------
# Historical verifier rejection semantics (v5)
# ---------------------------------------------------------------------------
def test_historical_verifier_rejection_is_binding_drift() -> None:
    is_drift, detail = verifier_rejection_is_binding_drift(ROOT, V4_CAPSULE)
    assert is_drift, (
        "v4 verifier must reject with failures that all belong to the "
        f"declared binding/state-drift patterns: {detail}")


def test_historical_verifier_never_touches_outputs() -> None:
    before = {}
    for rel in V4_CAPSULE.outputs:
        p = ROOT / rel
        before[rel] = p.read_bytes() if p.is_file() else None
    is_drift, detail = verifier_rejection_is_binding_drift(ROOT, V4_CAPSULE)
    assert is_drift, detail
    for rel, data in before.items():
        p = ROOT / rel
        assert (p.read_bytes() if p.is_file() else None) == data


def test_v3_core_files_byte_exact_against_head() -> None:
    repo = ROOT.parent
    for rel in V3_CORE_FILES:
        repo_rel = f"formal_experiment/{rel}"
        proc = subprocess.run(
            ["git", "-C", str(repo), "hash-object", repo_rel],
            cwd=repo, capture_output=True, text=True, check=True)
        blob = proc.stdout.strip()
        proc2 = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", f"HEAD:{repo_rel}"],
            cwd=repo, capture_output=True, text=True, check=True)
        head_blob = proc2.stdout.strip()
        assert blob == head_blob, (
            f"v3 core file {rel} changed in the working tree vs HEAD")


def test_report_declares_and_binds_superseded_v3_entries() -> None:
    report = _load(OUT_JSON)
    declared = {item["path"] for item in report["supersedes"]}
    required = [
        "outputs/reports/s2_11_license_adapter_readiness_v2.json",
        "outputs/reports/s2_11_data_qualification_mapping_dry_run.json",
        "outputs/reports/g0_7_barrientos_adapter_registry_dry_run.json",
        "outputs/reports/g0_7_barrientos_adapter_registry_dry_run.md",
    ] + V3_CORE_FILES + [V3_TEST_FILE]
    for path in required:
        assert path in declared, f"missing supersedes declaration: {path}"
    for item in report["supersedes"]:
        p = ROOT / item["path"]
        assert p.is_file()
        if item["path"] == V3_TEST_FILE:
            # The v3 TEST file legitimately changed under the v5 lifecycle
            # semantics (test-semantics correction only); the v4 report's
            # recorded hash for it is historical and is allowed to drift.
            continue
        assert _sha(p.read_bytes()) == item["sha256"], (
            f"superseded asset {item['path']} was modified on disk")


# ---------------------------------------------------------------------------
# License separation (article vs artifact) with the real PDF evidence chain
# ---------------------------------------------------------------------------
def test_article_license_fields() -> None:
    report = _load(OUT_JSON)
    la = report["license_audit"]
    assert la["paper_readable"] is True
    assert la["article_license"] == "CC-BY-4.0"
    assert la["article_license_scope"] == "article_only"
    assert la["article_license_does_not_auto_cover_artifact"] is True
    ae = la["article_evidence"]
    assert ae["doi"] == "10.1016/j.infsof.2026.108079"
    assert ae["ccby_url"] == "http://creativecommons.org/licenses/by/4.0/"
    assert ae["artifact_url"].startswith("https://anonymous.4open.science/")
    pdf = ROOT.parent / ae["pdf_path"]
    assert pdf.is_file()
    assert _sha(pdf.read_bytes()) == ae["pdf_sha256"]
    assert pdf.stat().st_size == ae["pdf_byte_size"]


def test_artifact_license_fail_closed() -> None:
    report = _load(OUT_JSON)
    la = report["license_audit"]
    assert la["code_usable"] == "unknown_pending_confirmation"
    assert la["data_reusable"] == "unknown_pending_confirmation"
    assert la["project_activatable"] is False
    assert la["ready_for_data_activation"] is False
    assert la["activation_authorization_sentence"] is None
    assert la["artifact_file_count"] >= 1
    # article license must NEVER imply artifact license
    assert la["article_license_does_not_auto_cover_artifact"] is True


def test_pdf_evidence_chain_re_extracted_read_only() -> None:
    """Real evidence-chain test: re-extract the publisher PDF text and
    assert the recorded title/DOI/CC BY statement/artifact URL actually
    appear in the PDF (read-only; no modification)."""
    import re
    pytest.importorskip("PyPDF2")
    from PyPDF2 import PdfReader
    builder = _load_builder()
    report = _load(OUT_JSON)
    ae = report["license_audit"]["article_evidence"]
    reader = PdfReader(str(PDF_PATH))
    full = "\n".join((page.extract_text() or "") for page in reader.pages)
    normalized = re.sub(r"\s+", " ", full)
    assert ae["title"].split(" on ")[0] in normalized
    assert ae["doi"] in normalized
    assert "open access article under the CC BY license" in normalized
    assert "creativecommons.org/licenses/by/4.0" in normalized
    assert "anonymous.4open.science" in normalized


def test_no_web_snippet_as_license_evidence() -> None:
    report = _load(OUT_JSON)
    notes = "\n".join(report["license_audit"]["evidence_notes"])
    assert "web-search" in notes or "search snippets" in notes


# ---------------------------------------------------------------------------
# G0.5 promotion readiness + adapter + gates
# ---------------------------------------------------------------------------
def test_g05_stays_draft_and_not_promotion_ready() -> None:
    report = _load(OUT_JSON)
    g5 = report["g0_5_candidate"]
    assert g5["status"] == "draft_not_frozen"
    assert g5["frozen"] is False
    pr = report["g0_5_promotion_readiness"]
    assert pr["g0_5_status"] == "draft_not_frozen"
    assert pr["promotion_ready_for_application"] is False
    assert any("user authorization manifest" in m for m in pr["missing"])
    assert pr["preregistration_claim_allowed"] is False
    config = _load(ROOT / g5["config_path"])
    assert config["status"] == "draft_not_frozen"


def test_adapter_hardened_synthetic_shadow_only() -> None:
    report = _load(OUT_JSON)
    ad = report["adapter_status"]
    assert ad["implementation"] == "synthetic_shadow_only"
    assert ad["hardened"] is True
    assert (ROOT / ad["source_path"]).is_file()
    assert (ROOT / ad["tests_path"]).is_file()
    assert len(ad["formal_activation_blocked_on"]) >= 5


def test_user_gates_order_and_sentences() -> None:
    report = _load(OUT_JSON)
    by_id = {g["gate_id"]: g for g in report["user_gates"]}
    assert set(by_id) == {"G1", "G2", "G3", "G4", "G5", "G6"}
    for gate_id in ("G1", "G2", "G5", "G6"):
        gate = by_id[gate_id]
        assert gate["ready_for_authorization"] is False
        assert gate["authorization_sentence"] is None
        assert len(gate["missing"]) >= 1
    assert len(by_id["G5"]["missing"]) >= 4
    future = by_id["G5"].get("future_authorization_sentence_after_"
                             "prerequisites")
    assert isinstance(future, str)
    assert "Future sentence" in future
    builder = _load_builder()
    assert by_id["G3"]["authorization_sentence"] == builder.G3_SENTENCE
    assert "structural mapping" in by_id["G3"]["authorization_sentence"]
    g4_sentence = by_id["G4"]["authorization_sentence"]
    assert "gate-application checkpoint" in g4_sentence
    assert "does NOT freeze G0.5 this round" in g4_sentence
    assert report["g0_5_candidate"]["config_sha256"] in g4_sentence
    assert "Oracle" not in " ".join(
        g["authorization_sentence"] or "" for g in report["user_gates"])


def test_no_oracle_authorization_sentence_anywhere() -> None:
    report = _load(OUT_JSON)
    oc = report["oracle_control"]
    assert oc["formal_oracle_started"] is False
    assert oc["formal_oracle_authorized"] is False
    assert oc["ready_for_oracle_authorization"] is False
    assert oc["authorization_sentence"] is None
    assert oc["no_pseudo_oracle"] is True


def test_no_gold_created_and_zero_api() -> None:
    report = _load(OUT_JSON)
    assert report["safety"]["gates_unchanged"] is True
    assert report["safety"]["gold_predictions_results_contract_methods_unchanged"] \
        is True
    assert report["safety"]["no_authorization_applied"] is True
    assert report["safety"]["references_read_only_not_activated"] is True
    assert report["zero_api"]["new_llm_api_calls"] == 0


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
    assert any("manifest exact reconstruction" in n
               for n in _failed_check_names(result))


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
    assert any("export index exact reconstruction" in n
               for n in _failed_check_names(result))


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
        entry["path"] = "outputs/reports/s2_11_g0_5_pre_authorization_v4.json"
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


def test_report_fails_when_article_license_downgraded(tmp_path: Path) -> None:
    verifier = _load_verifier()
    result = _tamper_report(
        tmp_path,
        lambda r: r["license_audit"].update(
            {"article_license": "unknown_pending_confirmation"}),
        verifier)
    assert result["verified"] is False


def test_report_fails_when_artifact_license_claimed(tmp_path: Path) -> None:
    verifier = _load_verifier()
    result = _tamper_report(
        tmp_path,
        lambda r: r["license_audit"].update(
            {"code_usable": "qualified", "ready_for_data_activation": True}),
        verifier)
    assert result["verified"] is False


def test_report_fails_when_g5_marked_ready(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(r: dict[str, Any]) -> None:
        for gate in r["user_gates"]:
            if gate["gate_id"] == "G5":
                gate["ready_for_authorization"] = True
                gate["authorization_sentence"] = "I authorize the surface"
    result = _tamper_report(tmp_path, mutate, verifier)
    assert result["verified"] is False


def test_report_fails_when_g4_sentence_unbound(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(r: dict[str, Any]) -> None:
        for gate in r["user_gates"]:
            if gate["gate_id"] == "G4":
                gate["authorization_sentence"] = (
                    "I authorize freezing the G0.5 contract.")
    result = _tamper_report(tmp_path, mutate, verifier)
    assert result["verified"] is False
    assert any("G3/G4 ready=true" in n for n in _failed_check_names(result))


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
