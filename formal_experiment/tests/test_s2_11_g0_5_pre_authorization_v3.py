"""Focused tests for the S2.11 / G0.5 pre-authorization decision capsule v3.

v3 is a SUPERSEDED HISTORICAL capsule (v5 lifecycle semantics): its core
assets (schema/builder/verifier/four outputs) stay byte-exact; once the
assets its manifest binds legitimately evolve, the historical builder MUST
fail closed with a no-overwrite rejection and the historical verifier MUST
reject with a declared binding/state-drift diagnosis.

Covers:
  * historical core assets match HEAD; the historical builder fails
    closed (no-overwrite) and never touches Gold/predictions/results/
    contract/methods/references
  * the historical verifier rejection belongs to the declared
    binding/state-drift patterns (not arbitrary exceptions) and never
    modifies outputs
  * license audit fail-closed fields and read-only inventory
  * G0.5 stays draft_not_frozen; adapter stays synthetic_shadow_only
  * separated user gates: G1/G2 null sentences, G3/G4/G5 exact dry-run
    sentences
  * manifest exact-reconstruction negative cases (emptied bindings, one
    missing binding, emptied implementation, extra unauthorized binding,
    artifact byte_size tamper, simultaneous export-hash recomputation)
  * export exact-reconstruction negative cases (missing/extra entry,
    field tamper, release tamper, recomputed hashes)
  * superseded historical decision entries stay byte-unchanged
  * references/ is never modified (read-only proof)
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

BUILDER_SCRIPT = ROOT / "scripts" / "build_s2_11_g0_5_pre_authorization_v3.py"
VERIFIER_SCRIPT = ROOT / "scripts" / "verify_s2_11_g0_5_pre_authorization_v3.py"
OUT_JSON = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v3.json"
OUT_MD = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v3.md"
OUT_MANIFEST = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v3.manifest.json"
OUT_EXPORT = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v3_export_index.json"

REF_DIR = ROOT.parent / "references" / "barrientos_2026"

SUPERSEDED_REQUIRED = [
    "outputs/reports/s2_11_license_adapter_readiness_v2.json",
    "outputs/reports/s2_11_data_qualification_mapping_dry_run.json",
    "outputs/reports/g0_7_barrientos_adapter_registry_dry_run.json",
    "outputs/reports/g0_7_barrientos_adapter_registry_dry_run.md",
]


def _load_builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s2_11_g0_5_pre_authorization_builder_v3", BUILDER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_verifier() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s2_11_g0_5_pre_authorization_verifier_v3", VERIFIER_SCRIPT)
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
# Historical capsule lifecycle semantics (v5): v3 is a SUPERSEDED capsule.
# Its core assets stay byte-exact; once the assets its manifest binds
# legitimately evolve, the historical builder MUST fail closed with a
# no-overwrite rejection and the historical verifier MUST reject with a
# binding/state-drift diagnosis. This is the correct historical behavior,
# NOT a failure of v3.
# ---------------------------------------------------------------------------
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


def test_historical_core_assets_match_head_and_builder_fails_closed() -> None:
    ok, changed = historical_core_assets_match_head(ROOT, V3_CAPSULE)
    assert ok, f"v3 core assets drifted from HEAD: {changed}"
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
                                                               V3_CAPSULE)
    assert drift_ok, (
        "v3 builder must fail closed with a no-overwrite rejection when "
        f"its bound assets evolved: {detail}")
    after = {p: _sha(p.read_bytes()) for p in sensitive}
    assert after == before, (
        "historical builder touched Gold / predictions / results / "
        "contract / methods")


def test_historical_builder_never_modifies_references() -> None:
    if not REF_DIR.is_dir():
        pytest.skip("references/barrientos_2026 not present")
    ref_files = sorted(p for p in REF_DIR.rglob("*") if p.is_file())
    before = {str(p.relative_to(REF_DIR)): _sha(p.read_bytes())
              for p in ref_files}
    drift_ok, detail = builder_rejects_with_no_overwrite_drift(ROOT,
                                                               V3_CAPSULE)
    assert drift_ok, detail
    after = {str(p.relative_to(REF_DIR)): _sha(p.read_bytes())
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
    is_drift, detail = verifier_rejection_is_binding_drift(ROOT, V3_CAPSULE)
    assert is_drift, (
        "v3 verifier must reject with failures that all belong to the "
        f"declared binding/state-drift patterns: {detail}")


def test_historical_verifier_never_touches_outputs() -> None:
    before = {}
    for rel in V3_CAPSULE.outputs:
        p = ROOT / rel
        before[rel] = p.read_bytes() if p.is_file() else None
    is_drift, detail = verifier_rejection_is_binding_drift(ROOT, V3_CAPSULE)
    assert is_drift, detail
    for rel, data in before.items():
        p = ROOT / rel
        assert (p.read_bytes() if p.is_file() else None) == data


def test_report_declares_and_binds_superseded_entries() -> None:
    report = _load(OUT_JSON)
    declared = {item["path"] for item in report["supersedes"]}
    for path in SUPERSEDED_REQUIRED:
        assert path in declared, f"missing supersedes declaration: {path}"
    for item in report["supersedes"]:
        p = ROOT / item["path"]
        assert p.is_file()
        assert _sha(p.read_bytes()) == item["sha256"], (
            f"superseded asset {item['path']} was modified on disk")


def test_license_audit_fail_closed_and_read_only() -> None:
    report = _load(OUT_JSON)
    la = report["license_audit"]
    assert la["license_status"] == "unknown_pending_confirmation"
    assert la["ready_for_data_activation"] is False
    assert la["activation_authorization_sentence"] is None
    assert la["four_state"]["activation_granted"] is False
    assert la["file_count"] == len(la["files"])
    assert la["file_count"] >= 1
    # every inventoried file must exist on disk with the recorded hash
    for f in la["files"]:
        p = ROOT.parent / f["path"]
        assert p.is_file()
        assert _sha(p.read_bytes()) == f["sha256"]


def test_g05_stays_draft_not_frozen() -> None:
    report = _load(OUT_JSON)
    g5 = report["g0_5_candidate"]
    assert g5["status"] == "draft_not_frozen"
    assert g5["frozen"] is False
    config = _load(ROOT / g5["config_path"])
    assert config["status"] == "draft_not_frozen"
    assert config["retrospective_use_forbidden"] is True


def test_adapter_stays_synthetic_shadow_only() -> None:
    report = _load(OUT_JSON)
    ad = report["adapter_status"]
    assert ad["implementation"] == "synthetic_shadow_only"
    assert (ROOT / ad["source_path"]).is_file()
    assert (ROOT / ad["tests_path"]).is_file()
    assert len(ad["formal_activation_blocked_on"]) >= 4


def test_user_gates_separated_and_dry_run_only() -> None:
    report = _load(OUT_JSON)
    by_id = {g["gate_id"]: g for g in report["user_gates"]}
    assert set(by_id) == {"G1", "G2", "G3", "G4", "G5"}
    for gate_id in ("G1", "G2"):
        gate = by_id[gate_id]
        assert gate["ready_for_authorization"] is False
        assert gate["authorization_sentence"] is None
        assert len(gate["missing"]) >= 1
    builder = _load_builder()
    assert by_id["G3"]["authorization_sentence"] == builder.G3_SENTENCE
    assert by_id["G4"]["authorization_sentence"] == builder.G4_SENTENCE
    assert by_id["G5"]["authorization_sentence"] == builder.G5_SENTENCE
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
    assert report["safety"]["gold_predictions_results_contract_methods_unchanged"] \
        is True
    assert report["safety"]["gates_unchanged"] is True
    assert report["safety"]["references_read_only_not_activated"] is True
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
        m["bindings"].pop("configs/g05_complexity_candidate_draft_v1.json")
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


def test_manifest_fails_on_artifact_byte_size_tamper(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(m: dict[str, Any]) -> None:
        m["artifacts"]["report_json"]["byte_size"] += 1
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


@pytest.mark.parametrize("field", ["path", "sha256", "byte_size"])
def test_export_fails_on_entry_field_tamper(tmp_path: Path,
                                            field: str) -> None:
    verifier = _load_verifier()
    def mutate(e: dict[str, Any]) -> None:
        entry = e["artifacts"]["report_md"]
        if field == "path":
            entry["path"] = "outputs/reports/other.md"
        elif field == "sha256":
            entry["sha256"] = "11" * 32
        else:
            entry["byte_size"] += 7
    exp_p = _tamper_export(tmp_path, mutate)
    result = _verify_with(tmp_path, tmp_path / OUT_MANIFEST.name, exp_p,
                          verifier)
    assert result["verified"] is False


def test_export_fails_on_release_tamper(tmp_path: Path) -> None:
    verifier = _load_verifier()
    exp_p = _tamper_export(tmp_path, lambda e: e.update({"release": "x"}))
    result = _verify_with(tmp_path, tmp_path / OUT_MANIFEST.name, exp_p,
                          verifier)
    assert result["verified"] is False


def test_export_fails_even_when_hashes_recomputed(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(e: dict[str, Any]) -> None:
        entry = e["artifacts"]["report_md"]
        other = OUT_JSON.read_bytes()
        entry["path"] = "outputs/reports/s2_11_g0_5_pre_authorization_v3.json"
        entry["sha256"] = _sha(other)
        entry["byte_size"] = len(other)
    exp_p = _tamper_export(tmp_path, mutate)
    result = _verify_with(tmp_path, tmp_path / OUT_MANIFEST.name, exp_p,
                          verifier)
    assert result["verified"] is False


# ---------------------------------------------------------------------------
# Report-content tamper negative cases (schema consts)
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


def test_report_fails_when_license_status_flipped(tmp_path: Path) -> None:
    verifier = _load_verifier()
    result = _tamper_report(
        tmp_path,
        lambda r: r["license_audit"].update(
            {"license_status": "qualified"}),
        verifier)
    assert result["verified"] is False
    assert any("schema valid" in n or "license audit" in n
               for n in _failed_check_names(result))


def test_report_fails_when_activation_granted(tmp_path: Path) -> None:
    verifier = _load_verifier()
    result = _tamper_report(
        tmp_path,
        lambda r: r["license_audit"].update(
            {"ready_for_data_activation": True}),
        verifier)
    assert result["verified"] is False


def test_report_fails_when_g05_marked_frozen(tmp_path: Path) -> None:
    verifier = _load_verifier()
    result = _tamper_report(
        tmp_path,
        lambda r: r["g0_5_candidate"].update({"frozen": True}),
        verifier)
    assert result["verified"] is False


def test_report_fails_when_adapter_marked_formal(tmp_path: Path) -> None:
    verifier = _load_verifier()
    result = _tamper_report(
        tmp_path,
        lambda r: r["adapter_status"].update(
            {"implementation": "formal_ready"}),
        verifier)
    assert result["verified"] is False


def test_report_fails_when_g1_gate_ready(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(r: dict[str, Any]) -> None:
        for gate in r["user_gates"]:
            if gate["gate_id"] == "G1":
                gate["ready_for_authorization"] = True
                gate["authorization_sentence"] = "I provide license evidence"
    result = _tamper_report(tmp_path, mutate, verifier)
    assert result["verified"] is False
