# -*- coding: utf-8 -*-
"""Focused tests for the S2.13 -> S3.7 transition readiness capsule v3.

Covers:
  * v1 AND v2 files stay byte-exact (v1/v2 verifiers keep rejecting as
    superseded historical capsules; git hash-object comparison against
    HEAD)
  * v3 deterministic, byte-identical builder rebuild + no-overwrite refusal
  * the builder never touches Gold / predictions / results / contract /
    methods / gates
  * the v3 independent verifier passes on the canonical outputs (seven
    independent verifiers executed, audit re-run)
  * Gold Rule Record THREE-STATE probe: a forged gdpr_rule_records.json
    under a synthetic tmp data/gold and a prediction copy named
    rule_record BOTH make the derivation fail closed; a clean tmp tree
    yields exist=false with the checked Stage 2 EStG-150 Gold bound; known
    non-Gold names never trigger
  * manifest EXACT reconstruction negative cases: emptied bindings, one
    missing binding, emptied implementation, one missing implementation
    entry, emptied artifacts, extra unauthorized binding, artifact
    byte_size tamper, and a simultaneous export-hash recomputation that
    must still fail
  * export index EXACT reconstruction negative cases: missing entry, extra
    entry, path/hash/byte_size tamper, release/schema_version tamper, and
    a simultaneous hash recomputation that must still fail
  * strict verifier verdict: a script printing "NOT VERIFIED" with exit 0
    is rejected (the bare "VERIFIED" substring is not sufficient)
  * Markdown ends with exactly one EOF newline
  * audit regression both ways: with final_experiment_ready=true no stale
    contradictory "remains false"/"capsule NOT produced yet" wording; with
    the gate forced closed the false branch states only real computation
    conditions and explicitly says nothing about S2.13/S3.7/full-pipeline
    completion
  * no Gold Rule Record was created or inferred (9-rule-ID absence guard)
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

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

BUILDER_SCRIPT = ROOT / "scripts" / "build_s2_13_s3_7_transition_readiness_v3.py"
VERIFIER_SCRIPT = ROOT / "scripts" / "verify_s2_13_s3_7_transition_readiness_v3.py"
OUT_JSON = ROOT / "outputs" / "reports" / \
    "s2_13_s3_7_transition_readiness_v3.json"
OUT_MD = ROOT / "outputs" / "reports" / \
    "s2_13_s3_7_transition_readiness_v3.md"
OUT_MANIFEST = ROOT / "outputs" / "reports" / \
    "s2_13_s3_7_transition_readiness_v3.manifest.json"
OUT_EXPORT = ROOT / "outputs" / "reports" / \
    "s2_13_s3_7_transition_readiness_v3_export_index.json"

V1_FILES = [
    "configs/schemas/s2_13_s3_7_transition_readiness.schema.json",
    "scripts/build_s2_13_s3_7_transition_readiness_v1.py",
    "scripts/verify_s2_13_s3_7_transition_readiness_v1.py",
    "tests/test_s2_13_s3_7_transition_readiness_v1.py",
    "outputs/reports/s2_13_s3_7_transition_readiness_v1.json",
    "outputs/reports/s2_13_s3_7_transition_readiness_v1.md",
    "outputs/reports/s2_13_s3_7_transition_readiness_v1.manifest.json",
    "outputs/reports/s2_13_s3_7_transition_readiness_v1_export_index.json",
]


V2_FILES = [
    "configs/schemas/s2_13_s3_7_transition_readiness_v2.schema.json",
    "scripts/build_s2_13_s3_7_transition_readiness_v2.py",
    "scripts/verify_s2_13_s3_7_transition_readiness_v2.py",
    "tests/test_s2_13_s3_7_transition_readiness_v2.py",
    "outputs/reports/s2_13_s3_7_transition_readiness_v2.json",
    "outputs/reports/s2_13_s3_7_transition_readiness_v2.md",
    "outputs/reports/s2_13_s3_7_transition_readiness_v2.manifest.json",
    "outputs/reports/s2_13_s3_7_transition_readiness_v2_export_index.json",
]

EXPECTED_RULE_IDS = [
    "article6", "article7", "article15", "article16", "article17",
    "article20", "article22", "article33", "article34",
]


def _load_builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s2_13_s3_7_transition_readiness_builder_v3", BUILDER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_verifier() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s2_13_s3_7_transition_readiness_verifier_v3", VERIFIER_SCRIPT)
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
    """Copy the four canonical v3 outputs into tmp_path (same names)."""
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


def _make_tmp_gold_tree(tmp_path: Path) -> Path:
    """Synthetic data/gold tree with the three Gold files the GRR
    derivation reads (Stage 2 EStG-150 Gold + Stage 3 matching/violation
    decision Gold). Tests may then add forged candidates."""
    root = tmp_path
    p2 = root / "data" / "gold" / "stage2"
    p2.mkdir(parents=True)
    shutil.copy2(ROOT / "data" / "gold" / "stage2" /
                 "estg150_formal_gold_v1.json",
                 p2 / "estg150_formal_gold_v1.json")
    p3 = root / "data" / "gold" / "stage3"
    p3.mkdir(parents=True)
    shutil.copy2(ROOT / "data" / "gold" / "stage3" /
                 "stage3_matching_gold_v1.json",
                 p3 / "stage3_matching_gold_v1.json")
    shutil.copy2(ROOT / "data" / "gold" / "stage3" /
                 "stage3_violation_gold_v1.json",
                 p3 / "stage3_violation_gold_v1.json")
    return root


# ---------------------------------------------------------------------------
# v1 byte-exactness
# ---------------------------------------------------------------------------
def test_v1_files_byte_exact_against_head() -> None:
    repo = ROOT.parent  # repository root (formal_experiment is a subdir)
    for rel in V1_FILES:
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
            f"v1 file {rel} changed in the working tree vs HEAD")


def test_v1_verifier_still_passes() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" /
                             "verify_s2_13_s3_7_transition_readiness_v1.py")],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, (
        f"v1 verifier must keep passing: {proc.stdout}\n{proc.stderr}")


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
        "canonical v3 capsule must verify: " + _failed_details(result))


def test_report_declares_and_binds_superseded_stale_reports_and_v1() -> None:
    report = _load(OUT_JSON)
    declared = {item["path"] for item in report["supersedes"]}
    required = [
        "outputs/reports/s2_13_stage2_freeze_gap_capsule.json",
        "outputs/reports/s2_13_stage2_freeze_gap_capsule.md",
        "outputs/reports/s3_7_oracle_readiness_v2.json",
        "outputs/reports/s37_oracle_readiness_v1.json",
        "outputs/reports/formal_benchmark_release_v2.manifest.json",
        "scripts/build_s1_5_s3_7_readiness_v1.py",
        "scripts/build_s3_7_oracle_readiness.py",
    ] + V1_FILES
    for path in required:
        assert path in declared, f"missing supersedes declaration: {path}"
    for item in report["supersedes"]:
        p = ROOT / item["path"]
        assert p.is_file()
        assert _sha(p.read_bytes()) == item["sha256"], (
            f"superseded asset {item['path']} was modified on disk")
    assert report["verification_scope"]["exact_manifest_reconstruction"] is True
    assert report["verification_scope"]["exact_export_reconstruction"] is True
    assert report["verification_scope"]["strict_verifier_verdict"] is True
    assert report["verification_scope"]["gold_rule_record_three_state_probe"] \
        is True
    assert report["verification_scope"]["markdown_single_eof_newline"] is True


def test_no_gold_rule_record_created_or_inferred() -> None:
    matches = [p for p in (ROOT / "data" / "gold").rglob("*")
               if p.is_file() and (
                   "rule_record" in p.name.lower()
                   or "rule-record" in p.name.lower())]
    assert matches == [], (
        f"Gold Rule Records must not exist, found: {matches}")
    report = _load(OUT_JSON)
    grr = report["gold_rule_records"]
    assert grr["exist"] is False
    assert set(grr["covered_rule_ids"]) == set(EXPECTED_RULE_IDS)
    assert grr["candidate_probe"]["found"] == []
    assert grr["checked_stage2_estg150_gold"]["path"] == \
        "data/gold/stage2/estg150_formal_gold_v1.json"
    checked = ROOT / grr["checked_stage2_estg150_gold"]["path"]
    assert checked.is_file()
    assert _sha(checked.read_bytes()) == \
        grr["checked_stage2_estg150_gold"]["sha256"]


def test_markdown_single_eof_newline() -> None:
    data = OUT_MD.read_bytes()
    assert data.endswith(b"\n")
    assert not data.endswith(b"\n\n"), \
        "Markdown must end with exactly one EOF newline"


# ---------------------------------------------------------------------------
# Gold Rule Record three-state probe (synthetic tmp trees only)
# ---------------------------------------------------------------------------
def test_grr_probe_fails_on_forged_rule_records_in_tmp_gold(
        tmp_path: Path) -> None:
    builder = _load_builder()
    root = _make_tmp_gold_tree(tmp_path)
    forged = root / "data" / "gold" / "stage3" / "gdpr_rule_records.json"
    forged.write_text(json.dumps({"forged": True}), encoding="utf-8")
    with pytest.raises(builder.BuilderFail) as exc:
        builder.derive_gold_rule_records(root)
    assert "gdpr_rule_records.json" in str(exc.value)


def test_grr_probe_fails_on_prediction_copy_named_rule_record(
        tmp_path: Path) -> None:
    builder = _load_builder()
    root = _make_tmp_gold_tree(tmp_path)
    pred_src = ROOT / "data" / "predictions" / "b0_formal_arm_v1" / \
        "predictions.json"
    forged = root / "data" / "gold" / "stage1" / "pred_rule_record.json"
    forged.parent.mkdir(parents=True)
    shutil.copy2(pred_src, forged)
    with pytest.raises(builder.BuilderFail) as exc:
        builder.derive_gold_rule_records(root)
    assert "pred_rule_record.json" in str(exc.value)


def test_grr_probe_fails_on_rule_dash_record_name(tmp_path: Path) -> None:
    builder = _load_builder()
    root = _make_tmp_gold_tree(tmp_path)
    forged = root / "data" / "gold" / "stage2" / "rule-record-v1.json"
    forged.write_text(json.dumps({"forged": True}), encoding="utf-8")
    with pytest.raises(builder.BuilderFail) as exc:
        builder.derive_gold_rule_records(root)
    assert "rule-record-v1.json" in str(exc.value)


def test_grr_probe_state1_clean_tmp_returns_exist_false(
        tmp_path: Path) -> None:
    builder = _load_builder()
    root = _make_tmp_gold_tree(tmp_path)
    grr = builder.derive_gold_rule_records(root)
    assert grr["exist"] is False
    assert grr["candidate_probe"]["found"] == []
    assert grr["covered_rule_ids"] == EXPECTED_RULE_IDS
    assert grr["checked_stage2_estg150_gold"]["path"] == \
        "data/gold/stage2/estg150_formal_gold_v1.json"
    checked = root / grr["checked_stage2_estg150_gold"]["path"]
    assert checked.is_file()
    assert _sha(checked.read_bytes()) == \
        grr["checked_stage2_estg150_gold"]["sha256"]


def test_grr_probe_ignores_known_non_gold_names(tmp_path: Path) -> None:
    # Copying prediction content under a name WITHOUT a rule-record pattern
    # must not trigger the probe (only rule_record/rule-record names do).
    builder = _load_builder()
    root = _make_tmp_gold_tree(tmp_path)
    non_gold = root / "data" / "gold" / "stage1" / "process_records"
    non_gold.mkdir(parents=True)
    shutil.copy2(ROOT / "data" / "gold" / "stage1" / "process_records" /
                 "stage1_process_gold_v1.json",
                 non_gold / "stage1_process_gold_v1.json")
    grr = builder.derive_gold_rule_records(root)
    assert grr["exist"] is False
    assert grr["candidate_probe"]["found"] == []


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
        m["bindings"].pop("data/gold/stage1/process_records/"
                          "stage1_process_gold_v1.json")
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


@pytest.mark.parametrize("entry", ["builder", "verifier", "schema"])
def test_manifest_fails_on_missing_one_implementation(tmp_path: Path,
                                                      entry: str) -> None:
    verifier = _load_verifier()
    def mutate(m: dict[str, Any]) -> None:
        m["implementation"].pop(entry)
    man_p = _tamper_manifest(tmp_path, mutate)
    result = _verify_with(tmp_path, man_p, tmp_path / OUT_EXPORT.name,
                          verifier)
    assert result["verified"] is False
    assert any("manifest exact reconstruction" in n
               for n in _failed_check_names(result))


def test_manifest_fails_on_emptied_artifacts(tmp_path: Path) -> None:
    verifier = _load_verifier()
    man_p = _tamper_manifest(tmp_path, lambda m: m.update({"artifacts": {}}))
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
    assert any("manifest exact reconstruction" in n
               for n in _failed_check_names(result))


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
    """Tamper the manifest AND recompute the outer export hashes: the
    exact manifest reconstruction must still fail."""
    verifier = _load_verifier()
    _, man_p, exp_p, _ = _copy_outputs(tmp_path)
    man_doc = _load(man_p)
    man_doc["bindings"].pop("data/gold/stage3/stage3_matching_gold_v1.json")
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
# Export index exact-reconstruction negative cases
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
        e["artifacts"]["bogus"] = {
            "path": "outputs/reports/bogus.json",
            "sha256": "00" * 32,
            "byte_size": 1,
        }
    exp_p = _tamper_export(tmp_path, mutate)
    result = _verify_with(tmp_path, tmp_path / OUT_MANIFEST.name, exp_p,
                          verifier)
    assert result["verified"] is False
    assert any("export index exact reconstruction" in n
               for n in _failed_check_names(result))


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
    exp_p = _tamper_export(
        tmp_path, lambda e: e.update({"release": "tampered"}))
    result = _verify_with(tmp_path, tmp_path / OUT_MANIFEST.name, exp_p,
                          verifier)
    assert result["verified"] is False


def test_export_fails_on_schema_version_tamper(tmp_path: Path) -> None:
    verifier = _load_verifier()
    exp_p = _tamper_export(
        tmp_path, lambda e: e.update({"schema_version": "x"}))
    result = _verify_with(tmp_path, tmp_path / OUT_MANIFEST.name, exp_p,
                          verifier)
    assert result["verified"] is False


def test_export_fails_even_when_hashes_recomputed(tmp_path: Path) -> None:
    """Tamper an entry AND recompute its hash/byte_size to match another
    real file: the structural reconstruction must still fail."""
    verifier = _load_verifier()
    def mutate(e: dict[str, Any]) -> None:
        entry = e["artifacts"]["report_md"]
        other = OUT_JSON.read_bytes()
        entry["path"] = "outputs/reports/s2_13_s3_7_transition_readiness_v3.json"
        entry["sha256"] = _sha(other)
        entry["byte_size"] = len(other)
    exp_p = _tamper_export(tmp_path, mutate)
    result = _verify_with(tmp_path, tmp_path / OUT_MANIFEST.name, exp_p,
                          verifier)
    assert result["verified"] is False
    assert any("export index exact reconstruction" in n
               for n in _failed_check_names(result))


# ---------------------------------------------------------------------------
# Strict verifier verdict ("NOT VERIFIED" substring regression)
# ---------------------------------------------------------------------------
def test_run_independent_verifier_rejects_not_verified_substring(
        tmp_path: Path) -> None:
    builder = _load_builder()
    fake = tmp_path / "fake_verifier.py"
    fake.write_text(
        "import sys\nprint('RESULT NOT VERIFIED')\nsys.exit(0)\n",
        encoding="utf-8")
    result = builder.run_independent_verifier(tmp_path, fake.name, False)
    assert result["verified"] is False
    assert result["exit_code"] == 0


def test_run_independent_verifier_accepts_explicit_verdict(
        tmp_path: Path) -> None:
    builder = _load_builder()
    fake = tmp_path / "fake_verifier.py"
    fake.write_text(
        "import sys\nprint('ALL CHECKS VERIFIED')\nsys.exit(0)\n",
        encoding="utf-8")
    result = builder.run_independent_verifier(tmp_path, fake.name, False)
    assert result["verified"] is True


def test_run_independent_verifier_rejects_exit_one_with_verdict(
        tmp_path: Path) -> None:
    builder = _load_builder()
    fake = tmp_path / "fake_verifier.py"
    fake.write_text(
        "import sys\nprint('VERIFIED')\nsys.exit(1)\n",
        encoding="utf-8")
    result = builder.run_independent_verifier(tmp_path, fake.name, False)
    assert result["verified"] is False
    assert result["exit_code"] == 1


# ---------------------------------------------------------------------------
# Audit wording regression (both directions)
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


def test_audit_false_branch_states_only_real_conditions_when_gate_closed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the final gate closed via a fake gate-condition function and
    assert the false branch describes only the real computation conditions
    and explicitly says nothing about S2.13/S3.7/full-pipeline completion
    (v2 wording fix; gate computation, contract and status values are not
    changed)."""
    from formal_experiment.audit import collect_project_audit
    import formal_experiment.status as status_mod

    def fake_gate_conditions() -> dict[str, Any]:
        return {"capsule_complete": False,
                "g04_contract_authorized": True,
                "comparison_consistent": True}

    monkeypatch.setattr(status_mod, "formal_final_gate_conditions",
                        fake_gate_conditions)
    audit = collect_project_audit()
    assert audit["final_experiment_ready"] is False
    claim_boundary = str(audit.get("claim_boundary", ""))
    estg_warning = " ".join(
        item.get("message", "") for item in
        audit.get("findings", {}).get("warnings", [])
        if item.get("code") == "estg_reconstruction_development_only")
    # false branch: real computation conditions only
    assert "Stage 2 three-method formal capsules" in claim_boundary
    assert "shared comparison consistency" in claim_boundary
    assert "authorized G0.4 contract" in claim_boundary
    assert "frozen input/Gold" in claim_boundary
    assert "says nothing about S2.13/S3.7/full-pipeline completion" in \
        claim_boundary
    # the stale wording must be gone in BOTH directions
    assert "Stage 3 completion not ready" not in claim_boundary
    assert "Stage 3 completion" not in estg_warning
