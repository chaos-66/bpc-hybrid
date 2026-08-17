"""Focused tests for the S2.11 / G0.5 pre-authorization decision capsule v6
(now a SUPERSEDED HISTORICAL capsule after Checkpoint A of the
user-authorized non-API application round; the applied-gates assets and
the review surface are the current entries).

v6's core assets (schema/builder/verifier/four outputs) stay byte-exact,
anchored to the FIXED v6 ORIGIN COMMIT 518047d4c97ab691fdf0edeeea27c6cf1674765e
(hardcoded SHA-256 map, independent of HEAD). Once the assets its
manifest binds legitimately evolve (Checkpoint A applies G1-G4/G6 and
freezes G0.5), the historical v6 builder MUST fail closed and the
historical v6 verifier MUST reject with a declared binding/state-drift
diagnosis.

Covers:
  * historical core assets match the FIXED ORIGIN map (disk bytes AND
    origin-commit git blobs); the historical builder fails closed and
    never touches Gold/predictions/results/contract/methods/references
  * the historical verifier rejection belongs to the declared
    binding/state-drift patterns and never modifies outputs
  * v5 audit facts recorded exactly (green receipt 2118 passed / 24
    skipped / 19 warnings in 941.91s; NOT a red checkpoint; hand-built
    validation-result protection overturned) and v6 counterexamples
  * FIXED ORIGIN anchors: the v6 report binds the v3/v4/v5 origin commits
    and the hardcoded SHA-256 maps; disk AND origin-commit blobs match;
    the v5 HEAD-relative blind spot is demonstrated and closed (same
    wrong bytes in HEAD+disk still fail the fixed check)
  * G0.5 SEALED chain regression: classify_frozen has NO validation-result
    parameter; the exact v5 hand-built 64-hex dict is rejected; prior
    results are derived from disk evidence
  * supersedes declares v3 decision entries + full v3/v4/v5 capsules
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

BUILDER_SCRIPT = ROOT / "scripts" / "build_s2_11_g0_5_pre_authorization_v6.py"
VERIFIER_SCRIPT = ROOT / "scripts" / "verify_s2_11_g0_5_pre_authorization_v6.py"
OUT_JSON = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v6.json"
OUT_MD = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v6.md"
OUT_MANIFEST = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v6.manifest.json"
OUT_EXPORT = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v6_export_index.json"

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
V6_CAPSULE = HistoricalCapsule(
    name="s2_11_g0_5_pre_authorization_v6",
    schema_rel="configs/schemas/s2_11_g0_5_pre_authorization_v6.schema.json",
    builder_rel="scripts/build_s2_11_g0_5_pre_authorization_v6.py",
    verifier_rel="scripts/verify_s2_11_g0_5_pre_authorization_v6.py",
    outputs=("outputs/reports/s2_11_g0_5_pre_authorization_v6.json",
             "outputs/reports/s2_11_g0_5_pre_authorization_v6.md",
             "outputs/reports/s2_11_g0_5_pre_authorization_v6.manifest.json",
             "outputs/reports/s2_11_g0_5_pre_authorization_v6_export_index.json"),
)
V5_CAPSULE = HistoricalCapsule(
    name="s2_11_g0_5_pre_authorization_v5",
    schema_rel="configs/schemas/s2_11_g0_5_pre_authorization_v5.schema.json",
    builder_rel="scripts/build_s2_11_g0_5_pre_authorization_v5.py",
    verifier_rel="scripts/verify_s2_11_g0_5_pre_authorization_v5.py",
    outputs=("outputs/reports/s2_11_g0_5_pre_authorization_v5.json",
             "outputs/reports/s2_11_g0_5_pre_authorization_v5.md",
             "outputs/reports/s2_11_g0_5_pre_authorization_v5.manifest.json",
             "outputs/reports/s2_11_g0_5_pre_authorization_v5_export_index.json"),
)


def _load_builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s2_11_g0_5_pre_authorization_builder_v6", BUILDER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_verifier() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s2_11_g0_5_pre_authorization_verifier_v6", VERIFIER_SCRIPT)
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
# Historical capsule lifecycle semantics (v6 is SUPERSEDED after Checkpoint
# A): its core assets stay byte-exact against the FIXED v6 ORIGIN COMMIT
# (518047d…; hardcoded SHA-256 map, independent of HEAD). Once the assets
# its manifest binds legitimately evolve (Checkpoint A applies G1-G4/G6
# and freezes G0.5), the historical builder MUST fail closed and the
# historical verifier MUST reject with a binding/state-drift diagnosis.
# ---------------------------------------------------------------------------
def test_historical_core_assets_match_fixed_origin_and_builder_fails_closed() -> None:
    ok, detail = historical_core_assets_match_fixed_origin(ROOT, "v6")
    assert ok, f"v6 core assets drifted from the fixed origin anchor: {detail}"
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
    drift_ok, detail2 = builder_rejects_with_no_overwrite_drift(
        ROOT, V6_CAPSULE)
    assert drift_ok, (
        "v6 builder must fail closed when its bound assets evolved: "
        f"{detail2}")
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
                                                               V6_CAPSULE)
    assert drift_ok, detail
    after = {str(p.relative_to(ROOT.parent)): _sha(p.read_bytes())
             for p in ref_files}
    assert after == before, "historical builder modified references/"


def test_v6_builder_no_overwrite_refusal(tmp_path: Path) -> None:
    builder = _load_builder()
    target = tmp_path / "out.json"
    target.write_bytes(b"first")
    with pytest.raises(builder.BuilderFail):
        builder._write(target, b"second")
    builder._write(target, b"first")
    assert target.read_bytes() == b"first"


# ---------------------------------------------------------------------------
# Historical verifier rejection semantics
# ---------------------------------------------------------------------------
def test_historical_verifier_rejection_is_binding_drift() -> None:
    is_drift, detail = verifier_rejection_is_binding_drift(ROOT, V6_CAPSULE)
    assert is_drift, (
        "v6 verifier must reject with failures that all belong to the "
        f"declared binding/state-drift patterns: {detail}")


def test_historical_verifier_never_touches_outputs() -> None:
    before = {}
    for rel in V6_CAPSULE.outputs:
        p = ROOT / rel
        before[rel] = p.read_bytes() if p.is_file() else None
    is_drift, detail = verifier_rejection_is_binding_drift(ROOT, V6_CAPSULE)
    assert is_drift, detail
    for rel, data in before.items():
        p = ROOT / rel
        assert (p.read_bytes() if p.is_file() else None) == data


# ---------------------------------------------------------------------------
# v5 audit facts
# ---------------------------------------------------------------------------
def test_v5_audit_facts_recorded() -> None:
    report = _load(OUT_JSON)
    facts = report["v5_audit_facts"]
    assert facts["v5_audit_green"] is True
    assert facts["v5_final_receipt"] == \
        "2118 passed, 24 skipped, 19 warnings in 941.91s"
    assert facts["v5_handbuilt_validation_claim_overturned"] is True
    assert facts["v5_not_a_red_checkpoint"] is True
    assert facts["v5_historical_events_preserved"] is True
    assert len(facts["v6_counterexamples"]) >= 6
    joined = "\n".join(facts["v6_counterexamples"]).lower()
    for needle in ("64 lowercase hex", "no validation-result parameter",
                   "derive_prior_results", "61938c99", "51a6e4fe"):
        assert needle in joined, f"missing counterexample needle: {needle}"


# ---------------------------------------------------------------------------
# FIXED ORIGIN anchors (v3/v4/v5, HEAD-independent)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("version", ["v3", "v4", "v5"])
def test_fixed_origin_anchors_match_disk_and_git(version: str) -> None:
    ok, detail = historical_core_assets_match_fixed_origin(ROOT, version)
    assert ok, f"{version} core assets drifted from the fixed origin " \
               f"anchor: {detail}"


def test_report_binds_fixed_origin_anchors() -> None:
    from bpc_hybrid.capsule_lifecycle import (
        FIXED_ORIGIN_COMMITS, fixed_core_asset_hashes)
    report = _load(OUT_JSON)
    anchors = report["fixed_origin_anchors"]
    assert set(anchors) == {"v3", "v4", "v5"}
    for version, info in anchors.items():
        assert info["origin_commit"] == FIXED_ORIGIN_COMMITS[version]
        assets = info["assets"]
        assert set(assets) == set(fixed_core_asset_hashes(version))
        for key, want in fixed_core_asset_hashes(version).items():
            assert assets[key]["sha256"] == want
            p = ROOT / _rel_for(version, key)
            assert p.is_file()
            assert _sha(p.read_bytes()) == want


def _rel_for(version: str, key: str) -> str:
    from bpc_hybrid.capsule_lifecycle import CORE_ASSET_REL_TEMPLATES
    for k, t in CORE_ASSET_REL_TEMPLATES:
        if k == key:
            return t.format(v=version)
    raise AssertionError(f"unknown asset key {key}")


def test_same_wrong_bytes_in_head_and_disk_still_fails_fixed_origin(
        monkeypatch: Any, tmp_path: Path) -> None:
    """v5 regression: `historical_core_assets_match_head` compares disk to
    HEAD, so a commit that rewrites a historical asset in HEAD *and* on
    disk with the same wrong bytes passes it. The v6 fixed-origin check
    must still fail because the hardcoded SHA-256 map is HEAD-independent."""
    from bpc_hybrid import capsule_lifecycle as cl
    root = tmp_path / "formal_experiment"
    wrong = b"WRONG-BYTES-SAME-IN-HEAD-AND-DISK"
    for rel in cl.core_asset_rels("v3"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(wrong)
    # Simulate HEAD pointing at the SAME wrong bytes (the v5 blind spot).
    monkeypatch.setattr(cl, "git_head_blob", lambda repo, rel: wrong)
    old_ok, _ = cl.historical_core_assets_match_head(root, V3_CAPSULE)
    assert old_ok, (
        "the old HEAD-relative check must pass here by construction "
        "(this is the v5 blind spot we are closing)")
    ok, detail = cl.historical_core_assets_match_fixed_origin(root, "v3")
    assert not ok, "the fixed origin map must catch the same-wrong-bytes case"
    assert "disk_mismatch" in detail


@pytest.mark.parametrize("version", ["v3", "v4", "v5", "v6"])
def test_historical_capsule_lifecycle_semantics(version: str) -> None:
    capsule = {"v3": V3_CAPSULE, "v4": V4_CAPSULE, "v5": V5_CAPSULE,
               "v6": V6_CAPSULE}[version]
    ok, detail = historical_core_assets_match_fixed_origin(ROOT, version)
    assert ok, f"{capsule.name} core assets drifted from the fixed origin " \
               f"anchor: {detail}"
    drift_ok, d2 = builder_rejects_with_no_overwrite_drift(ROOT, capsule)
    assert drift_ok, (
        f"{capsule.name} builder must fail closed with a no-overwrite "
        f"rejection: {d2}")
    is_drift, vdetail = verifier_rejection_is_binding_drift(ROOT, capsule)
    assert is_drift, (
        f"{capsule.name} verifier rejection must be binding drift: "
        f"{vdetail}")


def test_supersedes_declares_v3_v4_and_v5_capsules() -> None:
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
        "configs/schemas/s2_11_g0_5_pre_authorization_v5.schema.json",
        "scripts/build_s2_11_g0_5_pre_authorization_v5.py",
        "scripts/verify_s2_11_g0_5_pre_authorization_v5.py",
        "tests/test_s2_11_g0_5_pre_authorization_v5.py",
        "outputs/reports/s2_11_g0_5_pre_authorization_v5.json",
        "outputs/reports/s2_11_g0_5_pre_authorization_v5.md",
        "outputs/reports/s2_11_g0_5_pre_authorization_v5.manifest.json",
        "outputs/reports/s2_11_g0_5_pre_authorization_v5_export_index.json",
        "outputs/reports/s2_11_license_adapter_readiness_v2.json",
        "outputs/reports/s2_11_data_qualification_mapping_dry_run.json",
        "outputs/reports/g0_7_barrientos_adapter_registry_dry_run.json",
        "outputs/reports/g0_7_barrientos_adapter_registry_dry_run.md",
    ]
    for path in required:
        assert path in declared, f"missing supersedes declaration: {path}"
    assert len(declared) == 28


# ---------------------------------------------------------------------------
# G0.5 SEALED frozen-application chain (regression counterexamples)
# ---------------------------------------------------------------------------
def _real_draft_config_path() -> Path:
    import bpc_hybrid.g05_complexity_candidate as g05
    root = Path(g05.__file__).resolve().parents[2]
    return root / "configs" / "g05_complexity_candidate_draft_v1.json"


def _write_json(path: Path, doc: dict[str, Any]) -> str:
    data = json.dumps(doc, ensure_ascii=False, sort_keys=True,
                      indent=2).encode("utf-8")
    path.write_bytes(data)
    return _sha(data)


def _make_frozen_fixture(
        tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    from bpc_hybrid.g05_complexity_candidate import (
        APPROVED_AUTHORIZATION_SCOPE,
        AUTHORIZATION_EVENT_KIND,
        AUTHORIZATION_MANIFEST_SCHEMA_VERSION,
        approved_authorization_sentence,
        derive_prior_results,
    )
    root = tmp_path
    draft_path = root / "draft.json"
    draft_path.write_bytes(_real_draft_config_path().read_bytes())
    frozen_path = root / "frozen.json"
    doc = dict(_load(_real_draft_config_path()))
    doc["status"] = "frozen"
    doc["frozen_before_new_results"] = True
    doc["retrospective_use_forbidden"] = True
    frozen_path.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2)
                            .encode("utf-8"))
    draft_sha = _sha(draft_path.read_bytes())
    frozen_sha = _sha(frozen_path.read_bytes())
    sentence = approved_authorization_sentence(draft_sha)
    event_path = root / "authorization_event.json"
    event_sha = _write_json(event_path, {
        "kind": AUTHORIZATION_EVENT_KIND,
        "event_id": "syn-g05-event-1",
        "authorization_sentence": sentence,
        "scope": APPROVED_AUTHORIZATION_SCOPE,
        "manifest_id": "syn-g05-auth-1",
        "append_only": True,
    })
    manifest_path = root / "manifest.json"
    _write_json(manifest_path, {
        "schema_version": AUTHORIZATION_MANIFEST_SCHEMA_VERSION,
        "manifest_id": "syn-g05-auth-1",
        "authorization_applied": True,
        "draft_config_path": "draft.json",
        "draft_config_sha256": draft_sha,
        "approved_frozen_config_path": "frozen.json",
        "approved_frozen_config_sha256": frozen_sha,
        "scope": APPROVED_AUTHORIZATION_SCOPE,
        "authorization_sentence": sentence,
        "authorization_sentence_sha256": _sha(sentence.encode("utf-8")),
        "retrospective_use_forbidden": True,
        "frozen_before_new_results": True,
        "s2_10_retrospective_use_forbidden": True,
        "prior_results_scan_sha256":
            derive_prior_results(root)["scan_sha256"],
        "authorization_event_id": "syn-g05-event-1",
        "authorization_event_path": "authorization_event.json",
        "authorization_event_sha256": event_sha,
        "application_checkpoint": {
            "pending_commit_not_applied": True,
            "commit_sha256": None,
        },
    })
    return root, draft_path, frozen_path, manifest_path


def test_classify_frozen_rejects_handbuilt_64_hex_validation_result(
        tmp_path: Path) -> None:
    """THE v5 vulnerability regression: the exact hand-built dict v5
    accepted (64-hex token + correct frozen hash + valid=true) must be
    rejected. classify_frozen has NO validation-result parameter at all."""
    from bpc_hybrid.g05_complexity_candidate import (
        classify_frozen, G05ClassificationError)
    root, draft, frozen, manifest = _make_frozen_fixture(tmp_path)
    fake = {
        "frozen_application_valid": True,
        "validation_token": "00" * 32,
        "approved_frozen_config_sha256": _sha(frozen.read_bytes()),
    }
    with pytest.raises(TypeError):
        classify_frozen({}, frozen, fake)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        classify_frozen(  # type: ignore[call-arg]
            {}, frozen_config_path=frozen, validation_result=fake)
    # A forged MANIFEST file (even with a well-formed token field) cannot
    # unlock the classifier either: the full approved binding is required.
    forged = tmp_path / "forged_manifest.json"
    _write_json(forged, fake)
    with pytest.raises(G05ClassificationError) as exc:
        classify_frozen({}, draft_config_path=draft,
                        frozen_config_path=frozen,
                        authorization_manifest_path=forged,
                        project_root=root)
    assert "manifest" in exc.value.message.lower()


def test_classify_frozen_rejects_results_then_authorization(
        tmp_path: Path) -> None:
    from bpc_hybrid.g05_complexity_candidate import (
        classify_frozen, G05ClassificationError)
    root, draft, frozen, manifest = _make_frozen_fixture(tmp_path)
    res = root / "outputs" / "evidence"
    res.mkdir(parents=True)
    (res / "g05_new_corpus_result.json").write_bytes(b"{}")
    with pytest.raises(G05ClassificationError) as exc:
        classify_frozen({}, draft_config_path=draft,
                        frozen_config_path=frozen,
                        authorization_manifest_path=manifest,
                        project_root=root)
    assert "prior" in exc.value.message.lower()


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
        entry["path"] = "outputs/reports/s2_11_g0_5_pre_authorization_v6.json"
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


def test_report_fails_when_v5_facts_hidden(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(r: dict[str, Any]) -> None:
        r["v5_audit_facts"]["v5_audit_green"] = False
    result = _tamper_report(tmp_path, mutate, verifier)
    assert result["verified"] is False


def test_report_fails_when_v5_receipt_replaced(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(r: dict[str, Any]) -> None:
        r["v5_audit_facts"]["v5_final_receipt"] = "2059 passed"
    result = _tamper_report(tmp_path, mutate, verifier)
    assert result["verified"] is False


def test_report_fails_when_origin_anchor_tampered(tmp_path: Path) -> None:
    verifier = _load_verifier()
    def mutate(r: dict[str, Any]) -> None:
        r["fixed_origin_anchors"]["v3"]["assets"]["schema"]["sha256"] = \
            "11" * 32
    result = _tamper_report(tmp_path, mutate, verifier)
    assert result["verified"] is False
    assert any("FIXED ORIGIN" in n for n in _failed_check_names(result))


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
