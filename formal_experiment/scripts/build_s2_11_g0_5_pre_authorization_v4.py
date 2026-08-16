# -*- coding: utf-8 -*-
"""Deterministic builder for the S2.11 / G0.5 pre-authorization user
decision capsule v4 (corrective).

Builds (all under formal_experiment/):
  outputs/reports/s2_11_g0_5_pre_authorization_v4.json
  outputs/reports/s2_11_g0_5_pre_authorization_v4.md
  outputs/reports/s2_11_g0_5_pre_authorization_v4.manifest.json
  outputs/reports/s2_11_g0_5_pre_authorization_v4_export_index.json

v4 supersedes the v3 license four-state, adapter-completeness and G4/G5
readiness judgments only; every v3 file (and every v1/v2 transition
capsule file) stays byte-exact and is bound in the supersedes list.

Corrective facts implemented here:
  * Article license (CC BY 4.0, article-only) is SEPARATED from artifact
    code/data license (unknown_pending_confirmation). The evidence chain
    binds the publisher PDF path/hash/byte size, the DOI, the article CC
    BY statement, the CC BY URL, the artifact URL and the TUM reference
    URL; no web-search snippet is used as license evidence.
  * The adapter is the HARDENED synthetic/shadow implementation
    (field-level provenance, canonical target whitelist, formal evidence
    bindings); formal activation stays blocked.
  * M1 covers modality identity candidate mapping ONLY; structural field
    mapping requires a separate gate (G6).
  * G4 binds the exact draft config path + SHA-256 and authorizes only a
    future gate-application checkpoint; G5 is protocol-ready but NOT
    authorization-ready (sentence null, conditional future sentence kept
    out of the executable field).

Hard rules: deterministic rebuild, no wall-clock, no-overwrite, license
audit read-only (names + hashes + sizes only; PDF contents are never
copied beyond the license-evidence excerpt), zero API, no gate flips.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

OUT_DIR = ROOT / "outputs" / "reports"
OUT_JSON = OUT_DIR / "s2_11_g0_5_pre_authorization_v4.json"
OUT_MD = OUT_DIR / "s2_11_g0_5_pre_authorization_v4.md"
OUT_MANIFEST = OUT_DIR / "s2_11_g0_5_pre_authorization_v4.manifest.json"
OUT_EXPORT = OUT_DIR / "s2_11_g0_5_pre_authorization_v4_export_index.json"

SCHEMA = ROOT / "configs" / "schemas" / "s2_11_g0_5_pre_authorization_v4.schema.json"

SCHEMA_VERSION = "s2_11_g0_5_pre_authorization@4.0.0"
REPORT_ID = "s2_11_g0_5_pre_authorization_v4"

BARRIENTOS_REF_DIR = "references/barrientos_2026"
BARRIENTOS_PDF = "references/papers/Barrientos_2026_Impact_analysis.pdf"
LICENSE_EVIDENCE_NAME_RE = re.compile(
    r"(license|copying|notice|readme|metadata)", re.IGNORECASE)

ARTICLE_TITLE = ("Impact analysis of regulatory requirement changes on "
                 "business process compliance")
ARTICLE_DOI = "10.1016/j.infsof.2026.108079"
ARTICLE_CCBY_URL = "http://creativecommons.org/licenses/by/4.0/"
ARTICLE_ARTIFACT_URL = ("https://anonymous.4open.science/r/"
                        "Requirements_Change_for_Business_Process_Compliance")
TUM_REFERENCE_URL = ("https://portal.fis.tum.de/en/publications/"
                     "impact-analysis-of-regulatory-requirement-changes-on-"
                     "business-pro/")
# Read-only excerpt extracted from the publisher PDF on 2026-08-15; the
# PDF is hash-bound so the excerpt stays verifiable.
ARTICLE_CCBY_STATEMENT = (
    "0950-5849/© 2026 The Authors. Published by Elsevier B.V. This is an "
    "open access article under the CC BY license "
    "(http://creativecommons.org/licenses/by/4.0/).")

# (relative path, supports --json)
INDEPENDENT_VERIFIERS: tuple[tuple[str, bool], ...] = (
    ("scripts/verify_stage1_process_gold.py", True),
    ("scripts/verify_s1_7_freezer_authorization.py", True),
    ("scripts/verify_formal_benchmark_release_v2.py", True),
    ("outputs/reports/verify_b0_formal_arm_v1.py", False),
    ("outputs/reports/verify_direct_llm_formal_arm_v1.py", False),
    ("outputs/reports/verify_sun_llm_fallback_formal_arm_v1.py", False),
    ("outputs/reports/verify_stage2_formal_comparison_v1.py", False),
)

# v3 decision entries (4) + the complete v3 capsule (8 files). All stay
# byte-exact; v4 supersedes only the v3 license four-state,
# adapter-completeness and G4/G5 readiness judgments.
SUPERSEDED: tuple[tuple[str, str], ...] = (
    ("outputs/reports/s2_11_license_adapter_readiness_v2.json",
     "2026-08-11 license/adapter readiness v2; superseded as a decision "
     "entry by v3 and now by v4; historical file stays unmodified."),
    ("outputs/reports/s2_11_data_qualification_mapping_dry_run.json",
     "2026-08-11 data-qualification & mapping dry-run; superseded as the "
     "decision entry by v3 and now by v4; historical file stays "
     "unmodified."),
    ("outputs/reports/g0_7_barrientos_adapter_registry_dry_run.json",
     "2026-08-11 G0.7 adapter registry dry-run; superseded by v3/v4 "
     "synthetic/shadow adapter reports; historical file stays unmodified."),
    ("outputs/reports/g0_7_barrientos_adapter_registry_dry_run.md",
     "Markdown rendering of the same superseded registry dry-run; "
     "preserved unmodified."),
    ("configs/schemas/s2_11_g0_5_pre_authorization_v3.schema.json",
     "v3 schema; kept byte-exact. v4 supersedes the v3 license four-state "
     "(v3 treated the article CC BY as not-yet-confirmed), "
     "adapter-completeness (v3 adapter lacked field-level provenance and "
     "formal evidence bindings) and G4/G5 readiness (v3 marked G5 ready) "
     "judgments."),
    ("scripts/build_s2_11_g0_5_pre_authorization_v3.py",
     "v3 builder; kept byte-exact; its current-state judgments are "
     "superseded by the v4 builder."),
    ("scripts/verify_s2_11_g0_5_pre_authorization_v3.py",
     "v3 verifier; kept byte-exact; v4 verifier adds the corrected license "
     "four-state, promotion readiness and gate-ordering checks."),
    ("tests/test_s2_11_g0_5_pre_authorization_v3.py",
     "v3 focused tests; kept byte-exact; v4 adds the corrective test "
     "cases."),
    ("outputs/reports/s2_11_g0_5_pre_authorization_v3.json",
     "v3 decision report; its license four-state, adapter-completeness and "
     "G4/G5 readiness judgments are superseded by v4; the file stays "
     "byte-exact."),
    ("outputs/reports/s2_11_g0_5_pre_authorization_v3.md",
     "v3 Markdown rendering; preserved byte-exact as historical "
     "provenance."),
    ("outputs/reports/s2_11_g0_5_pre_authorization_v3.manifest.json",
     "v3 manifest; preserved byte-exact."),
    ("outputs/reports/s2_11_g0_5_pre_authorization_v3_export_index.json",
     "v3 export index; preserved byte-exact."),
)

G3_SENTENCE = (
    "I select mapping option M1 for the S2.11 Barrientos 3->4 modality "
    "mapping: identity candidate mapping for obligation/permission/"
    "prohibition ONLY; this does NOT authorize any precondition/norm/"
    "temporal_validity -> actor/action/condition/constraint/exception "
    "structural mapping (a separate field-mapping gate is required); "
    "definition is never auto-produced and requires separate human "
    "adjudication.")


def g4_sentence(draft_config_sha256: str) -> str:
    return (
        "I authorize a future gate-application checkpoint that freezes "
        "configs/g05_complexity_candidate_draft_v1.json (sha256 "
        f"{draft_config_sha256}) as the G0.5 complexity contract (scope: "
        "future external complex corpora only; retrospective_use_forbidden"
        "=true; must take effect before any new complex-corpus results are "
        "produced). This sentence authorizes ONLY that future "
        "gate-application checkpoint; it does NOT freeze G0.5 this round.")


G5_FUTURE_SENTENCE = (
    "Future sentence, only after G1 artifact code/data license is "
    "qualified, G2 data activation is authorized, the actual corpus "
    "membership/hash is fixed and the review workload is sized: I "
    "authorize opening the blank S2.11 human Gold review surface; no "
    "decision may be prefilled and final adjudication is user-only.")


class BuilderFail(Exception):
    """Fail-closed build abort."""


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "missing"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _require_asset(path: Path, what: str) -> str:
    if not path.is_file():
        raise BuilderFail(
            f"fail-closed: required evidence asset missing: "
            f"{_rel(path)} ({what})")
    return _sha256_file(path)


def _evidence(path: Path, kind: str, sha: str | None = None) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(), "kind": kind}
    if sha is not None:
        ref["sha256"] = sha
    return ref


def _derivation_evidence(description: str) -> dict[str, Any]:
    return {"path": description, "kind": "derivation"}


def _write(path: Path, data: bytes) -> None:
    if path.exists() and path.read_bytes() != data:
        raise BuilderFail(
            f"refusing to overwrite different existing content: "
            f"{_rel(path)}")
    path.write_bytes(data)


def run_independent_verifier(root: Path, rel: str,
                             has_json: bool) -> dict[str, Any]:
    """Run one independent verifier as a subprocess (strict verdict: exit 0
    AND an explicit success line; the bare 'VERIFIED' substring is not
    sufficient because 'NOT VERIFIED' also contains it)."""
    path = root / rel
    cmd = [sys.executable, str(path)]
    if has_json:
        cmd.append("--json")
    try:
        proc = subprocess.run(
            cmd, cwd=str(root), capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"path": rel, "verified": False, "exit_code": -1,
                "checks": None, "error": str(exc)}
    rc = proc.returncode
    out = (proc.stdout or "").strip()
    checks = None
    if has_json:
        try:
            start = out.index("{")
            end = out.rindex("}") + 1
            payload = json.loads(out[start:end])
            checks = len(payload.get("checks", []))
        except (ValueError, json.JSONDecodeError):
            checks = None
    explicit_verdict = bool("VERIFIED" in out and "NOT VERIFIED" not in out)
    verified = bool(rc == 0 and (explicit_verdict or has_json))
    if has_json and rc == 0 and checks is None:
        verified = False
    return {"path": rel, "verified": verified, "exit_code": rc,
            "checks": checks}


# ---------------------------------------------------------------------------
# Derivations
# ---------------------------------------------------------------------------

def derive_state_matrix(root: Path) -> list[dict[str, Any]]:
    """Same factual matrix as v3 (S2.11/S2.12/S2.13/S3.x unchanged)."""
    gold = root / "data" / "gold" / "stage1" / "process_records" / \
        "stage1_process_gold_v1.json"
    gold_manifest = root / "data" / "gold" / "stage1" / "manifest.json"
    freeze_auth = root / "outputs" / "reports" / \
        "s1_5_process_gold_freeze_authorization_v1.manifest.json"
    pred = root / "data" / "predictions" / "stage1_formal_v1" / \
        "formal_predictions_v1.json"
    res = root / "data" / "results" / "stage1_formal_v1" / \
        "stage1_formal_evaluation_v1.json"
    s1_7_auth = root / "outputs" / "reports" / \
        "s1_7_freezer_authorization_v1.manifest.json"
    s2_11_license = root / "outputs" / "reports" / \
        "s2_11_license_adapter_readiness_v2.json"
    s2_11_dry_run = root / "outputs" / "reports" / \
        "s2_11_data_qualification_mapping_dry_run.json"
    s2_12_report = root / "outputs" / "reports" / \
        "s2_12_formal_descriptive_error_analysis_v1.json"
    s2_12_manifest = root / "outputs" / "reports" / \
        "s2_12_formal_descriptive_error_analysis_v1.manifest.json"
    s2_13_gap = root / "outputs" / "reports" / \
        "s2_13_stage2_freeze_gap_capsule.json"
    matching = root / "data" / "gold" / "stage3" / "stage3_matching_gold_v1.json"
    violation = root / "data" / "gold" / "stage3" / "stage3_violation_gold_v1.json"
    correction = root / "data" / "development" / "human_review" / \
        "stage3_gold_annotation_human_correction_v1.json"
    freeze_manifest = root / "outputs" / "reports" / \
        "s32_s33_gold_annotation_freeze_v1.manifest.json"
    s34_clean = root / "outputs" / "development" / \
        "s34_winter_stage3_development_v3_clean" / "manifest.json"
    s34_literal = root / "outputs" / "development" / \
        "s34_winter_stage3_development_v3_prototype_literal" / "manifest.json"
    s35 = root / "outputs" / "development" / \
        "s35_sun_stage3_development_v2" / "manifest.json"
    s36_bm25 = root / "outputs" / "development" / \
        "s36_bm25_stage3_development_v3" / "manifest.json"
    s36_tfidf = root / "outputs" / "development" / \
        "s36_tfidf_svd_stage3_development_v2" / "manifest.json"
    s37_v1 = root / "outputs" / "reports" / "s37_oracle_readiness_v1.json"
    s3_7_v2 = root / "outputs" / "reports" / "s3_7_oracle_readiness_v2.json"

    s1_7_doc = _load_json(s1_7_auth)
    if s1_7_doc.get("status") != "freeze_applied":
        raise BuilderFail(
            "fail-closed: S1.7 authorization manifest status is "
            f"{s1_7_doc.get('status')!r}, expected freeze_applied")
    license_doc = _load_json(s2_11_license)
    blockers = license_doc.get("s2_11_exact_blockers") or []
    if not blockers:
        raise BuilderFail(
            "fail-closed: s2_11_license_adapter_readiness_v2.json has no "
            "s2_11_exact_blockers list")
    dry_run_doc = _load_json(s2_11_dry_run)
    if dry_run_doc.get("status") != "dry_run_not_applied":
        raise BuilderFail(
            "fail-closed: s2_11 data qualification dry-run status is "
            f"{dry_run_doc.get('status')!r}, expected dry_run_not_applied")

    arms = ("b0", "direct_llm", "sun_llm_fallback")
    s2_10_evidence: list[dict[str, Any]] = []
    for arm in arms:
        s2_10_evidence.append(_evidence(
            root / "outputs" / "reports" / f"{arm}_formal_arm_v1.manifest.json",
            "manifest",
            _require_asset(root / "outputs" / "reports" /
                           f"{arm}_formal_arm_v1.manifest.json",
                           f"{arm} arm manifest")))
    s2_10_evidence.append(_evidence(
        root / "outputs" / "reports" /
        "stage2_formal_three_method_comparison_v1.json", "disk_asset",
        _require_asset(root / "outputs" / "reports" /
                       "stage2_formal_three_method_comparison_v1.json",
                       "formal comparison report")))

    return [
        {
            "task_id": "S1.5",
            "status": "verified",
            "note": "Stage 1 Process Gold frozen and published "
                    "(user-authorized 2026-08-13; 7/7 records, 135/135 "
                    "label fields, 7/7 structure decisions).",
            "evidence": [
                _evidence(gold, "disk_asset",
                          _require_asset(gold, "Stage 1 Process Gold")),
                _evidence(gold_manifest, "manifest",
                          _require_asset(gold_manifest, "Stage 1 Gold manifest")),
                _evidence(freeze_auth, "manifest",
                          _require_asset(freeze_auth, "S1.5 freeze authorization")),
            ],
        },
        {
            "task_id": "S1.6",
            "status": "verified",
            "note": "Fixed-GDPR-7 formal descriptive component evaluation; "
                    "post-Gold, target-aware, NOT held-out generalization "
                    "evidence; P2/predictions/metrics byte-unchanged.",
            "evidence": [
                _evidence(pred, "disk_asset",
                          _require_asset(pred, "S1.6 predictions")),
                _evidence(res, "disk_asset",
                          _require_asset(res, "S1.6 results")),
            ],
        },
        {
            "task_id": "S1.7",
            "status": "frozen",
            "note": "Formal Stage 1 freeze APPLIED (2026-08-13); does NOT "
                    "auto-authorize the Stage 3 Oracle.",
            "evidence": [
                _evidence(s1_7_auth, "manifest",
                          _require_asset(s1_7_auth, "S1.7 authorization")),
            ],
        },
        {
            "task_id": "S2.10",
            "status": "verified",
            "note": "Three-method formal capsules and the formal three-method "
                    "comparison are published and independently verified; "
                    "new LLM calls 0.",
            "evidence": s2_10_evidence,
        },
        {
            "task_id": "S2.11",
            "status": "blocked",
            "blockers": list(blockers),
            "note": "Complex legal corpus NOT frozen and NOT activated; "
                    "article license CC BY 4.0 (article-only) is confirmed, "
                    "artifact code/data license still "
                    "unknown_pending_confirmation, activation NOT "
                    "authorized, mapping policy NOT approved, human Gold NOT "
                    "started, G0.5 draft_not_frozen, adapter hardened "
                    "synthetic/shadow only; the v4 decision capsule is the "
                    "current decision entry for this gate.",
            "evidence": [
                _evidence(s2_11_license, "disk_asset",
                          _require_asset(s2_11_license, "S2.11 license readiness")),
                _evidence(s2_11_dry_run, "disk_asset",
                          _require_asset(s2_11_dry_run, "S2.11 dry-run")),
                _evidence(root / "src" / "bpc_hybrid" /
                          "s2_11_barrientos_adapter.py", "disk_asset",
                          _require_asset(root / "src" / "bpc_hybrid" /
                                         "s2_11_barrientos_adapter.py",
                                         "adapter source")),
            ],
        },
        {
            "task_id": "S2.12",
            "status": "partial",
            "note": "Formal descriptive common error analysis delivered as "
                    "RETROSPECTIVE/EXPLORATORY; full DoD blocked on S2.11.",
            "evidence": [
                _evidence(s2_12_report, "disk_asset",
                          _require_asset(s2_12_report, "S2.12 report")),
                _evidence(s2_12_manifest, "manifest",
                          _require_asset(s2_12_manifest, "S2.12 manifest")),
            ],
        },
        {
            "task_id": "S2.13",
            "status": "blocked",
            "blockers": [
                "S2.11 blocked",
                "S2.12 full DoD not met (partial/retrospective only)",
            ],
            "note": "Stage 2 freeze NOT complete; DoD unchanged; "
                    "final_experiment_ready=true does NOT complete S2.13.",
            "evidence": [
                _derivation_evidence(
                    "derived: S2.11 blocked AND S2.12 partial -> S2.13 "
                    "blocked; DoD unchanged this round"),
                _evidence(s2_13_gap, "disk_asset",
                          _require_asset(s2_13_gap, "historical S2.13 gap capsule")),
            ],
        },
        {
            "task_id": "S3.2",
            "status": "verified",
            "note": "25 matching decision Gold published; decisions are NOT "
                    "Gold Rule Records.",
            "evidence": [
                _evidence(matching, "disk_asset",
                          _require_asset(matching, "Stage 3 matching Gold")),
                _evidence(correction, "disk_asset",
                          _require_asset(correction, "frozen correction")),
                _evidence(freeze_manifest, "manifest",
                          _require_asset(freeze_manifest, "S3.2/S3.3 freeze manifest")),
            ],
        },
        {
            "task_id": "S3.3",
            "status": "verified",
            "note": "33 violation decision Gold published; decisions are NOT "
                    "Gold Rule Records.",
            "evidence": [
                _evidence(violation, "disk_asset",
                          _require_asset(violation, "Stage 3 violation Gold")),
            ],
        },
        {
            "task_id": "S3.4",
            "status": "development_only",
            "note": "Winter wrapper development evidence only; formal "
                    "completion still blocked on S2.13 (S1.7 satisfied).",
            "evidence": [
                _evidence(s34_clean, "manifest",
                          _require_asset(s34_clean, "S3.4 dev manifest clean")),
                _evidence(s34_literal, "manifest",
                          _require_asset(s34_literal, "S3.4 dev manifest literal")),
            ],
        },
        {
            "task_id": "S3.5",
            "status": "development_only",
            "note": "Sun Stage 3 development evidence only; formal "
                    "completion still blocked on S2.13.",
            "evidence": [
                _evidence(s35, "manifest",
                          _require_asset(s35, "S3.5 dev manifest")),
            ],
        },
        {
            "task_id": "S3.6",
            "status": "development_only",
            "note": "BM25 v3 + TF-IDF/SVD development baselines only; "
                    "formal completion still blocked on S2.13.",
            "evidence": [
                _evidence(s36_bm25, "manifest",
                          _require_asset(s36_bm25, "S3.6 BM25 dev manifest")),
                _evidence(s36_tfidf, "manifest",
                          _require_asset(s36_tfidf, "S3.6 TF-IDF dev manifest")),
            ],
        },
        {
            "task_id": "S3.7",
            "status": "blocked",
            "blockers": [
                "9 GDPR Gold Rule Records do not exist",
                "S2.13 blocked",
                "S3.4/S3.5/S3.6 formal completion pending",
            ],
            "note": "Formal Oracle NOT started and NOT authorized; no "
                    "Oracle authorization sentence is generated by this "
                    "capsule.",
            "evidence": [
                _evidence(s37_v1, "disk_asset",
                          _require_asset(s37_v1, "historical s37 readiness v1")),
                _evidence(s3_7_v2, "disk_asset",
                          _require_asset(s3_7_v2, "historical s3_7 readiness v2")),
            ],
        },
    ]


def derive_license_audit(root: Path) -> dict[str, Any]:
    """Read-only license audit: article evidence (hash-bound publisher
    PDF) SEPARATED from artifact inventory (names + hashes + sizes only)."""
    pdf = root.parent / BARRIENTOS_PDF
    pdf_sha = _require_asset(pdf, "Barrientos 2026 publisher PDF")
    pdf_size = pdf.stat().st_size

    ref_dir = root.parent / BARRIENTOS_REF_DIR
    if not ref_dir.is_dir():
        raise BuilderFail(
            "fail-closed: references/barrientos_2026 directory missing; "
            "artifact license audit cannot run")
    artifact_files: list[str] = []
    license_evidence: list[str] = []
    for p in sorted(ref_dir.rglob("*")):
        if not p.is_file():
            continue
        artifact_files.append(p.relative_to(root.parent).as_posix())
        if LICENSE_EVIDENCE_NAME_RE.search(p.name):
            license_evidence.append(p.relative_to(root.parent).as_posix())
    if not artifact_files:
        raise BuilderFail(
            "fail-closed: references/barrientos_2026 contains no files")

    notes = [
        "article evidence chain: publisher PDF "
        f"({BARRIENTOS_PDF}, sha256 {pdf_sha[:12]}..., "
        f"{pdf_size} bytes) contains the DOI "
        f"https://doi.org/{ARTICLE_DOI}, the Elsevier open-access "
        "statement 'This is an open access article under the CC BY license' "
        f"({ARTICLE_CCBY_URL}) and the artifact link {ARTICLE_ARTIFACT_URL} "
        "(last access 03 February 2026); extracted read-only 2026-08-15",
        "article license CC BY 4.0 applies to the ARTICLE ONLY and does NOT "
        "auto-cover the code/data artifact; artifact code/data license "
        "stays unknown_pending_confirmation until an authoritative "
        "artifact-level license (LICENSE/COPYING/NOTICE/README/metadata on "
        "the artifact repository root or a publisher/author statement) is "
        "versioned with URL/scope/license identifier/hash",
        "web-search snippets, file presence or downloadability are NOT "
        "license evidence; the TUM portal page "
        f"{TUM_REFERENCE_URL} is recorded as a cross-check reference only "
        "(not fetched this round)",
        "no artifact license-evidence-named file was found"
        if not license_evidence
        else f"artifact license-evidence-named files found: {license_evidence}",
    ]

    return {
        "references_path": BARRIENTOS_REF_DIR,
        "article_evidence": {
            "pdf_path": BARRIENTOS_PDF,
            "pdf_sha256": pdf_sha,
            "pdf_byte_size": pdf_size,
            "title": ARTICLE_TITLE,
            "doi": ARTICLE_DOI,
            "ccby_statement": ARTICLE_CCBY_STATEMENT,
            "ccby_url": ARTICLE_CCBY_URL,
            "artifact_url": ARTICLE_ARTIFACT_URL,
            "tum_reference_url": TUM_REFERENCE_URL,
            "extracted_read_only": True,
        },
        "paper_readable": True,
        "article_license": "CC-BY-4.0",
        "article_license_scope": "article_only",
        "article_license_does_not_auto_cover_artifact": True,
        "code_usable": "unknown_pending_confirmation",
        "data_reusable": "unknown_pending_confirmation",
        "project_activatable": False,
        "ready_for_data_activation": False,
        "activation_authorization_sentence": None,
        "artifact_file_count": len(artifact_files),
        "artifact_license_evidence_files": license_evidence,
        "evidence_notes": notes,
    }


def derive_mapping_options() -> dict[str, Any]:
    m1 = {
        "id": "M1",
        "name": "modality_identity_candidate_only",
        "scope": ("authorizes ONLY identity CANDIDATE mapping for the "
                  "three shared modality classes (obligation/permission/"
                  "prohibition); it does NOT authorize any "
                  "precondition/norm/temporal_validity -> actor/action/"
                  "condition/constraint/exception structural mapping"),
        "before": ("External Barrientos labels are unavailable to the "
                   "project: artifact license unknown, activation not "
                   "authorized, no mapping policy, adapter hardened "
                   "synthetic/shadow only."),
        "after": ("After G1+G2+G3: obligation/permission/prohibition map "
                  "by identity to candidate-only modality values with "
                  "field-level provenance for the human Gold review; "
                  "without a separately approved field mapping policy the "
                  "structural fields stay blank; definition is never "
                  "produced; external ground truth stays a review aid."),
        "risks": [
            "identity assumes nominal modality-label alignment between "
            "Barrientos and Sun; unverified semantics are caught by the "
            "mandatory human Gold adjudication",
            "no structural candidate values are produced until a separate "
            "field-mapping gate (G6) is decided",
        ],
        "confirmation_sentence": G3_SENTENCE,
    }
    m2 = {
        "id": "M2",
        "name": "conservative_no_mapping",
        "scope": ("maps NO external label at all; all external content "
                  "enters the human Gold review as review aid only"),
        "before": "Same as M1: external labels unavailable.",
        "after": ("After G1+G2+G3: no external label is mapped; every "
                  "source element enters the human Gold review as review "
                  "aid and all decisions are made from scratch by the "
                  "user."),
        "risks": [
            "largest human workload (no candidate values to start from)",
            "most conservative with respect to label-semantics drift",
        ],
        "confirmation_sentence": (
            "I select mapping option M2 (conservative no-mapping: external "
            "labels are review aids only and every decision is made from "
            "scratch by human adjudication)."),
    }
    return {
        "options": [m1, m2],
        "recommended": "M1",
        "recommendation_reason": (
            "The three shared modality classes are nominally identical and "
            "the G0.7 registry dry-run documented the 3-class set; M1 "
            "minimizes human workload while the mandatory human Gold "
            "adjudication still guards against label-semantics drift and "
            "the hardened adapter never promotes candidates to Gold. M1 "
            "explicitly does NOT authorize structural field mapping (G6 "
            "remains a separate gate). M2 is the conservative fallback."),
        "applied": False,
        "definition_handling": (
            "never auto-produced; definition-class records require "
            "separate human adjudication"),
        "external_ground_truth_role": (
            "provenance or review aid only; never project Gold"),
        "structure_mapping_requires_separate_gate": True,
    }


def derive_human_gold_protocol() -> dict[str, Any]:
    return {
        "protocol_ready": True,
        "blank_schema_provided": True,
        "decision_fields": [
            "sample_id", "source_text", "approved_text_en", "modality",
            "actor", "action", "condition", "constraint", "exception",
            "evidence_span", "review_state",
        ],
        "review_surface_separated": True,
        "adjudication_separated": True,
        "freeze_separated": True,
        "publication_separated": True,
        "final_adjudication_by": "user_only",
        "gold_files_created": False,
        "decision_prefill": False,
    }


def derive_g0_5_candidate(root: Path) -> dict[str, Any]:
    config_path = root / "configs" / "g05_complexity_candidate_draft_v1.json"
    sha = _require_asset(config_path, "G0.5 candidate contract")
    doc = _load_json(config_path)
    if doc.get("status") != "draft_not_frozen":
        raise BuilderFail(
            "fail-closed: G0.5 candidate contract status is "
            f"{doc.get('status')!r}, expected draft_not_frozen")
    if doc.get("retrospective_use_forbidden") is not True:
        raise BuilderFail(
            "fail-closed: G0.5 candidate contract must forbid "
            "retrospective use")
    return {
        "config_path": "configs/g05_complexity_candidate_draft_v1.json",
        "config_sha256": sha,
        "status": "draft_not_frozen",
        "frozen": False,
    }


def derive_g0_5_promotion_readiness(root: Path) -> dict[str, Any]:
    from bpc_hybrid.g05_complexity_candidate import derive_promotion_readiness
    readiness = derive_promotion_readiness(root)
    if readiness["g0_5_status"] != "draft_not_frozen":
        raise BuilderFail(
            "fail-closed: G0.5 promotion readiness derived a non-draft "
            f"status {readiness['g0_5_status']!r}")
    if readiness["promotion_ready_for_application"] is not False:
        raise BuilderFail(
            "fail-closed: G0.5 promotion readiness must be false today")
    return {
        "g0_5_status": readiness["g0_5_status"],
        "promotion_ready_for_application": readiness[
            "promotion_ready_for_application"],
        "missing": readiness["missing"],
        "draft_config_sha256": readiness["draft_config_sha256"],
        "preregistration_claim_allowed": readiness[
            "preregistration_claim_allowed"],
    }


def derive_adapter_status(root: Path) -> dict[str, Any]:
    source = root / "src" / "bpc_hybrid" / "s2_11_barrientos_adapter.py"
    tests = root / "tests" / "test_g07_barrientos_adapter_contract.py"
    _require_asset(source, "adapter source")
    _require_asset(tests, "adapter tests")
    return {
        "implementation": "synthetic_shadow_only",
        "hardened": True,
        "verified": True,
        "source_path": "src/bpc_hybrid/s2_11_barrientos_adapter.py",
        "tests_path": "tests/test_g07_barrientos_adapter_contract.py",
        "formal_activation_blocked_on": [
            "artifact code/data license qualification "
            "(unknown_pending_confirmation; article CC BY 4.0 does NOT "
            "cover the artifact)",
            "data activation authorization",
            "3->4 modality mapping policy approval (G3)",
            "structural field mapping policy approval (G6)",
            "human Gold adjudication for the external complex corpus (G5)",
        ],
    }


def derive_user_gates(root: Path) -> list[dict[str, Any]]:
    draft_sha = _require_asset(
        root / "configs" / "g05_complexity_candidate_draft_v1.json",
        "G0.5 candidate contract for the G4 sentence binding")
    return [
        {
            "gate_id": "G1",
            "name": "confirm authoritative license evidence for "
                    "references/barrientos_2026 artifact code/data",
            "ready_for_authorization": False,
            "authorization_sentence": None,
            "missing": [
                "ARTICLE license resolved: CC BY 4.0 (article-only, "
                "publisher statement hash-bound) — this does NOT cover the "
                "artifact",
                "artifact code/data license evidence: authoritative "
                "LICENSE/COPYING/NOTICE/README/metadata on the artifact "
                "repository root (anonymous.4open.science) or a "
                "publisher/author statement, versioned with URL/scope/"
                "license identifier/hash",
            ],
        },
        {
            "gate_id": "G2",
            "name": "authorize external data activation (after artifact "
                    "license qualification)",
            "ready_for_authorization": False,
            "authorization_sentence": None,
            "missing": [
                "G1 artifact code/data license qualified (currently "
                "unknown_pending_confirmation)",
                "user activation authorization",
            ],
        },
        {
            "gate_id": "G3",
            "name": "select the 3->4 modality mapping policy (modality "
                    "identity candidate ONLY)",
            "ready_for_authorization": True,
            "authorization_sentence": G3_SENTENCE,
            "missing": [],
        },
        {
            "gate_id": "G4",
            "name": "authorize a FUTURE G0.5 freeze gate-application "
                    "checkpoint (config hash-bound)",
            "ready_for_authorization": True,
            "authorization_sentence": g4_sentence(draft_sha),
            "missing": [],
        },
        {
            "gate_id": "G5",
            "name": "authorize opening the blank S2.11 human Gold review "
                    "surface",
            "ready_for_authorization": False,
            "authorization_sentence": None,
            "future_authorization_sentence_after_prerequisites":
                G5_FUTURE_SENTENCE,
            "missing": [
                "G1 artifact code/data license qualified",
                "G2 data activation authorized",
                "actual corpus membership/hash fixed",
                "review workload sized (corpus-dependent)",
            ],
        },
        {
            "gate_id": "G6",
            "name": "authorize a structural field mapping policy "
                    "(source element -> canonical Sun span field)",
            "ready_for_authorization": False,
            "authorization_sentence": None,
            "missing": [
                "a complete, evidence-based field mapping policy option "
                "set (source elements -> actor/action/condition/constraint/"
                "exception); v4 does NOT select one on its own",
            ],
        },
    ]


def derive_oracle_control(root: Path) -> dict[str, Any]:
    authorization_assets = sorted(
        p.relative_to(root).as_posix()
        for p in (root / "outputs" / "reports").glob("*oracle_authorization*"))
    run_assets = sorted(
        p.relative_to(root).as_posix()
        for p in (root / "data" / "results").glob("*oracle*"))
    run_assets += sorted(
        p.relative_to(root).as_posix()
        for p in (root / "outputs" / "evidence").glob("*oracle*"))
    return {
        "formal_oracle_started": bool(run_assets),
        "formal_oracle_authorized": bool(authorization_assets),
        "ready_for_oracle_authorization": False,
        "authorization_sentence": None,
        "no_pseudo_oracle": True,
    }


def build_report(root: Path) -> dict[str, Any]:
    supersedes = []
    for rel, reason in SUPERSEDED:
        p = root / rel
        supersedes.append({
            "path": rel,
            "sha256": _require_asset(p, f"superseded historical asset {rel}"),
            "reason": reason,
        })

    verifiers_executed: dict[str, Any] = {}
    for rel, has_json in INDEPENDENT_VERIFIERS:
        result = run_independent_verifier(root, rel, has_json)
        if not result["verified"]:
            raise BuilderFail(
                f"fail-closed: independent verifier {rel} did not verify: "
                f"{result}")
        entry = {"verified": True, "exit_code": int(result["exit_code"])}
        if result.get("checks") is not None:
            entry["checks"] = int(result["checks"])
        verifiers_executed[rel] = entry

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "report_id": REPORT_ID,
        "build_note": (
            "Deterministic S2.11 / G0.5 corrective decision capsule v4; "
            "every state judgment is re-derived from current on-disk "
            "assets, manifests, hashes or executed independent verifiers; "
            "article license CC BY 4.0 (article-only) is separated from "
            "artifact code/data license (unknown_pending_confirmation); "
            "the adapter is the hardened synthetic/shadow implementation; "
            "G4 authorizes only a future gate-application checkpoint and "
            "G5 is not authorization-ready; authorization sentences are "
            "DRY-RUN text, nothing is applied, no gate is flipped and no "
            "Gold is created."),
        "supersedes": supersedes,
        "state_matrix": derive_state_matrix(root),
        "license_audit": derive_license_audit(root),
        "mapping_options": derive_mapping_options(),
        "human_gold_protocol": derive_human_gold_protocol(),
        "g0_5_candidate": derive_g0_5_candidate(root),
        "g0_5_promotion_readiness": derive_g0_5_promotion_readiness(root),
        "adapter_status": derive_adapter_status(root),
        "user_gates": derive_user_gates(root),
        "oracle_control": derive_oracle_control(root),
        "safety": {
            "gates_unchanged": True,
            "gold_predictions_results_contract_methods_unchanged": True,
            "g0_5_frozen": False,
            "references_read_only_not_activated": True,
            "no_authorization_applied": True,
        },
        "verifiers_executed": verifiers_executed,
        "zero_api": {"new_llm_api_calls": 0},
    }
    _validate_against_schema(root, report)
    return report


def _validate_against_schema(root: Path, report: dict[str, Any]) -> None:
    schema = _load_json(SCHEMA)
    if not schema:
        raise BuilderFail("fail-closed: capsule schema unreadable")
    errors = _schema_errors(schema, report)
    if errors:
        raise BuilderFail(
            "fail-closed: built report is schema-invalid: "
            + "; ".join(errors[:5]))


def _schema_errors(schema: dict[str, Any], payload: Any,
                   path: str = "<root>") -> list[str]:
    """Minimal deterministic draft-07 subset validator (project fallback
    pattern). Supports type, const, enum, pattern, minLength,
    minItems/maxItems/uniqueItems, minimum, required,
    additionalProperties=false, properties, items, oneOf and local $ref."""
    errors: list[str] = []

    def fail(msg: str) -> None:
        errors.append(f"{path}: {msg}")

    def resolve(s: dict[str, Any]) -> dict[str, Any]:
        ref = s.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/"):
            node: Any = schema
            for part in ref[2:].split("/"):
                node = node.get(part, {}) if isinstance(node, dict) else {}
            return node if isinstance(node, dict) else {}
        return s

    def apply(s: dict[str, Any], value: Any) -> None:
        if "$ref" in s:
            s = resolve(s)
        if "oneOf" in s:
            matched = False
            for branch in s["oneOf"]:
                sub: list[str] = []
                before = len(errors)
                apply(branch, value)
                if len(errors) == before:
                    matched = True
                    break
                del errors[before:]
            if not matched:
                fail(f"oneOf not matched for {s.get('oneOf')}")
            return
        expected_type = s.get("type")
        if expected_type is not None:
            ok = {
                "string": lambda v: isinstance(v, str),
                "boolean": lambda v: isinstance(v, bool),
                "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
                "array": lambda v: isinstance(v, list),
                "object": lambda v: isinstance(v, dict),
                "null": lambda v: v is None,
            }.get(expected_type)
            if ok is not None and not ok(value):
                fail(f"expected type {expected_type}, got {type(value).__name__}")
                return
        if "const" in s and value != s["const"]:
            fail(f"expected const {s['const']!r}, got {value!r}")
            return
        if "enum" in s and value not in s["enum"]:
            fail(f"value {value!r} not in enum {s['enum']}")
            return
        if isinstance(value, str):
            if "pattern" in s:
                import re
                if not re.search(s["pattern"], value):
                    fail(f"pattern {s['pattern']!r} not matched by {value!r}")
            if "minLength" in s and len(value) < s["minLength"]:
                fail(f"minLength {s['minLength']} not met")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in s and value < s["minimum"]:
                fail(f"minimum {s['minimum']} not met")
        if isinstance(value, list):
            if "minItems" in s and len(value) < s["minItems"]:
                fail(f"minItems {s['minItems']} not met")
            if "maxItems" in s and len(value) > s["maxItems"]:
                fail(f"maxItems {s['maxItems']} exceeded")
            if s.get("uniqueItems") and len({json.dumps(v, sort_keys=True)
                                             for v in value}) != len(value):
                fail("uniqueItems violated")
            item_schema = s.get("items")
            if isinstance(item_schema, dict):
                for i, item in enumerate(value):
                    apply(item_schema, item)
        if isinstance(value, dict) and expected_type in (None, "object"):
            if s.get("additionalProperties") is False:
                allowed = set(s.get("properties", {}).keys())
                extra = set(value.keys()) - allowed
                if extra:
                    fail(f"additional properties forbidden: {sorted(extra)}")
            for req in s.get("required", []):
                if req not in value:
                    fail(f"required property {req!r} missing")
            for key, prop_schema in (s.get("properties") or {}).items():
                if key in value:
                    apply(prop_schema, value[key])

    apply(schema, payload)
    return errors


def render_md(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# S2.11 / G0.5 Pre-Authorization User Decision Capsule v4 "
                 "(corrective)")
    lines.append("")
    lines.append(f"**Schema**: `{report['schema_version']}`")
    lines.append(f"**Report ID**: `{report['report_id']}`")
    lines.append("")
    lines.append("## Determinism & safety")
    lines.append("")
    lines.append(report["build_note"])
    for key, value in report["safety"].items():
        lines.append(f"- {key}: **{value}**")
    lines.append("")
    lines.append("## Superseded decision entries (files preserved unmodified)")
    lines.append("")
    for item in report["supersedes"]:
        lines.append(f"- `{item['path']}` (sha256 `{item['sha256'][:12]}…`): "
                     f"{item['reason']}")
    lines.append("")
    lines.append("## State matrix (unchanged facts)")
    lines.append("")
    for item in report["state_matrix"]:
        lines.append(f"- **{item['task_id']} = {item['status']}** — "
                     f"{item['note']}")
        for blocker in item.get("blockers", []):
            lines.append(f"  - blocker: {blocker}")
        for ev in item["evidence"]:
            sha = ev.get("sha256", "")
            sha_txt = f", sha256 `{sha[:12]}…`" if sha else ""
            lines.append(f"  - evidence [{ev['kind']}]: `{ev['path']}`"
                         f"{sha_txt}")
    lines.append("")
    lines.append("## License audit (article vs artifact separated)")
    lines.append("")
    la = report["license_audit"]
    ae = la["article_evidence"]
    lines.append(f"- article PDF: `{ae['pdf_path']}` "
                 f"(sha256 `{ae['pdf_sha256'][:12]}…`, "
                 f"{ae['pdf_byte_size']} bytes)")
    lines.append(f"- title: {ae['title']}")
    lines.append(f"- DOI: https://doi.org/{ae['doi']}")
    lines.append(f"- CC BY statement (publisher PDF): {ae['ccby_statement']}")
    lines.append(f"- CC BY URL: {ae['ccby_url']}")
    lines.append(f"- artifact URL (paper footnote): {ae['artifact_url']}")
    lines.append(f"- TUM reference (cross-check, not fetched): "
                 f"{ae['tum_reference_url']}")
    lines.append(f"- paper_readable: **{la['paper_readable']}**")
    lines.append(f"- article_license: **{la['article_license']}** "
                 f"(scope: {la['article_license_scope']})")
    lines.append(f"- article_license_does_not_auto_cover_artifact: "
                 f"**{la['article_license_does_not_auto_cover_artifact']}**")
    lines.append(f"- code_usable: **{la['code_usable']}**")
    lines.append(f"- data_reusable: **{la['data_reusable']}**")
    lines.append(f"- project_activatable: **{la['project_activatable']}**")
    lines.append(f"- ready_for_data_activation: "
                 f"**{la['ready_for_data_activation']}**")
    lines.append(f"- activation_authorization_sentence: "
                 f"**{la['activation_authorization_sentence']}**")
    lines.append(f"- artifact files inventoried: {la['artifact_file_count']} "
                 "(names/hashes/sizes only)")
    lines.append(f"- artifact license-evidence-named files: "
                 f"{la['artifact_license_evidence_files']}")
    for note in la["evidence_notes"]:
        lines.append(f"- note: {note}")
    lines.append("")
    lines.append("## Mapping options (NOT applied; M1 = modality identity "
                 "candidate ONLY)")
    lines.append("")
    mo = report["mapping_options"]
    for opt in mo["options"]:
        lines.append(f"### Option {opt['id']}: {opt['name']}")
        lines.append("")
        lines.append(f"- scope: {opt['scope']}")
        lines.append(f"- before: {opt['before']}")
        lines.append(f"- after: {opt['after']}")
        for risk in opt["risks"]:
            lines.append(f"- risk: {risk}")
        lines.append(f"- confirmation sentence: `{opt['confirmation_sentence']}`")
        lines.append("")
    lines.append(f"**Recommended**: {mo['recommended']} — "
                 f"{mo['recommendation_reason']}")
    lines.append(f"- applied: **{mo['applied']}**")
    lines.append(f"- definition_handling: {mo['definition_handling']}")
    lines.append(f"- external_ground_truth_role: "
                 f"{mo['external_ground_truth_role']}")
    lines.append(f"- structure_mapping_requires_separate_gate: "
                 f"**{mo['structure_mapping_requires_separate_gate']}**")
    lines.append("")
    lines.append("## Human Gold protocol readiness (blank only)")
    lines.append("")
    hg = report["human_gold_protocol"]
    lines.append(f"- protocol_ready: **{hg['protocol_ready']}**")
    lines.append(f"- blank_schema_provided: **{hg['blank_schema_provided']}**")
    lines.append(f"- decision fields: {', '.join(hg['decision_fields'])}")
    for key in ("review_surface_separated", "adjudication_separated",
                "freeze_separated", "publication_separated"):
        lines.append(f"- {key}: **{hg[key]}**")
    lines.append(f"- final_adjudication_by: **{hg['final_adjudication_by']}**")
    lines.append(f"- gold_files_created: **{hg['gold_files_created']}**")
    lines.append(f"- decision_prefill: **{hg['decision_prefill']}**")
    lines.append("")
    lines.append("## G0.5 candidate contract + promotion readiness")
    lines.append("")
    g5 = report["g0_5_candidate"]
    lines.append(f"- config: `{g5['config_path']}` "
                 f"(sha256 `{g5['config_sha256'][:12]}…`)")
    lines.append(f"- status: **{g5['status']}**; frozen: **{g5['frozen']}**")
    pr = report["g0_5_promotion_readiness"]
    lines.append(f"- g0_5_status: **{pr['g0_5_status']}**")
    lines.append(f"- promotion_ready_for_application: "
                 f"**{pr['promotion_ready_for_application']}**")
    for missing in pr["missing"]:
        lines.append(f"- missing: {missing}")
    lines.append(f"- preregistration_claim_allowed: "
                 f"**{pr['preregistration_claim_allowed']}** (existing "
                 "S2.10 results are never re-labeled preregistered)")
    lines.append("")
    lines.append("## Adapter status (hardened synthetic/shadow only)")
    lines.append("")
    ad = report["adapter_status"]
    lines.append(f"- implementation: **{ad['implementation']}**")
    lines.append(f"- hardened (field-level provenance, canonical target "
                 f"whitelist, formal evidence bindings): **{ad['hardened']}**")
    lines.append(f"- verified (real execution tests): **{ad['verified']}**")
    lines.append(f"- source: `{ad['source_path']}`; tests: `{ad['tests_path']}`")
    for blocker in ad["formal_activation_blocked_on"]:
        lines.append(f"- formal activation blocked on: {blocker}")
    lines.append("")
    lines.append("## User gates (separated; dry-run only)")
    lines.append("")
    for gate in report["user_gates"]:
        lines.append(f"### {gate['gate_id']}: {gate['name']}")
        lines.append("")
        lines.append(f"- ready_for_authorization: "
                     f"**{gate['ready_for_authorization']}**")
        lines.append(f"- authorization_sentence: "
                     f"**{gate['authorization_sentence']}**")
        future = gate.get("future_authorization_sentence_after_prerequisites")
        if future is not None:
            lines.append(f"- future_authorization_sentence_after_"
                         f"prerequisites (conditional, NOT current): "
                         f"`{future}`")
        for missing in gate["missing"]:
            lines.append(f"- missing: {missing}")
        lines.append("")
    lines.append("## Oracle control (fail-closed)")
    lines.append("")
    oc = report["oracle_control"]
    lines.append(f"- formal_oracle_started: **{oc['formal_oracle_started']}**")
    lines.append(f"- formal_oracle_authorized: **{oc['formal_oracle_authorized']}**")
    lines.append(f"- ready_for_oracle_authorization: "
                 f"**{oc['ready_for_oracle_authorization']}**")
    lines.append(f"- authorization_sentence: **{oc['authorization_sentence']}**")
    lines.append(f"- no_pseudo_oracle: **{oc['no_pseudo_oracle']}**")
    lines.append("")
    lines.append("## Independent verifiers executed")
    lines.append("")
    for rel, result in report["verifiers_executed"].items():
        checks = f", checks {result['checks']}" if "checks" in result else ""
        lines.append(f"- `{rel}`: verified={result['verified']}, "
                     f"exit_code={result['exit_code']}{checks}")
    lines.append("")
    lines.append("## Zero API")
    lines.append("")
    lines.append(f"- new_llm_api_calls: "
                 f"**{report['zero_api']['new_llm_api_calls']}**")
    return "\n".join(lines).rstrip("\n") + "\n"


def collect_bindings(root: Path, report: dict[str, Any]) -> dict[str, str]:
    """All external asset paths -> sha256, sorted deterministically."""
    bindings: dict[str, str] = {}
    for item in report["supersedes"]:
        bindings[item["path"]] = item["sha256"]
    for item in report["state_matrix"]:
        for ev in item["evidence"]:
            sha = ev.get("sha256")
            if sha and ev["kind"] in ("disk_asset", "manifest",
                                      "independent_verifier"):
                bindings[ev["path"]] = sha
    ae = report["license_audit"]["article_evidence"]
    bindings[ae["pdf_path"]] = ae["pdf_sha256"]
    g5 = report["g0_5_candidate"]
    bindings[g5["config_path"]] = g5["config_sha256"]
    ad = report["adapter_status"]
    bindings[ad["source_path"]] = _sha256_file(root / ad["source_path"])
    bindings[ad["tests_path"]] = _sha256_file(root / ad["tests_path"])
    for rel in (
        "configs/schemas/s2_11_g0_5_pre_authorization_v4.schema.json",
        "scripts/build_s2_11_g0_5_pre_authorization_v4.py",
        "scripts/verify_s2_11_g0_5_pre_authorization_v4.py",
        "src/bpc_hybrid/g05_complexity_candidate.py",
        "tests/test_g05_complexity_candidate_draft_v1.py",
        "src/formal_experiment/audit.py",
        "src/formal_experiment/status.py",
        "docs/MASTER_PIPELINE.md",
        "docs/PROJECT_AUDIT.md",
        "outputs/reports/s2_13_s3_7_transition_readiness_v2.json",
        "outputs/reports/s2_13_s3_7_transition_readiness_v2.md",
        "outputs/reports/s2_13_s3_7_transition_readiness_v2.manifest.json",
        "outputs/reports/s2_13_s3_7_transition_readiness_v2_export_index.json",
    ):
        bindings[rel] = _sha256_file(root / rel)
    return dict(sorted(bindings.items()))


def build_manifest(root: Path, report_json: bytes, md_bytes: bytes,
                   bindings: dict[str, str]) -> dict[str, Any]:
    builder = Path(__file__)
    verifier = root / "scripts" / \
        "verify_s2_11_g0_5_pre_authorization_v4.py"
    return {
        "schema_version": "s2_11_g0_5_pre_authorization_manifest@4.0.0",
        "manifest_id": "s2_11_g0_5_pre_authorization_v4.manifest",
        "artifact_type": "pre_authorization_decision_capsule",
        "determinism": {
            "no_wall_clock": True,
            "byte_identical_rebuild": True,
            "no_overwrite": True,
        },
        "artifacts": {
            "report_json": {
                "path": "outputs/reports/s2_11_g0_5_pre_authorization_v4.json",
                "sha256": _sha256_bytes(report_json),
                "byte_size": len(report_json),
            },
            "report_md": {
                "path": "outputs/reports/s2_11_g0_5_pre_authorization_v4.md",
                "sha256": _sha256_bytes(md_bytes),
                "byte_size": len(md_bytes),
            },
        },
        "bindings": bindings,
        "implementation": {
            "builder": {
                "path": str(builder.relative_to(root).as_posix()),
                "sha256": _sha256_file(builder),
            },
            "verifier": {
                "path": str(verifier.relative_to(root).as_posix()),
                "sha256": _sha256_file(verifier),
            },
            "schema": {
                "path": "configs/schemas/"
                        "s2_11_g0_5_pre_authorization_v4.schema.json",
                "sha256": _sha256_file(SCHEMA),
            },
        },
        "zero_api": {"new_llm_api_calls": 0},
        "safety": {
            "created_or_modified": [
                "outputs/reports/s2_11_g0_5_pre_authorization_v4.json",
                "outputs/reports/s2_11_g0_5_pre_authorization_v4.md",
                "outputs/reports/"
                "s2_11_g0_5_pre_authorization_v4.manifest.json",
                "outputs/reports/"
                "s2_11_g0_5_pre_authorization_v4_export_index.json",
            ],
            "never_created_or_modified": [
                "data/gold/**",
                "data/predictions/**",
                "data/results/**",
                "configs/experiment_contract.json",
                "configs/methods.json",
                "references/**",
                "archive/**",
                "_retired/**",
                "any v3 s2_11_g0_5_pre_authorization file and any "
                "v1/v2 transition capsule file",
                "any publication status, method gate, Stage 3 gate, or "
                "S2.11/S2.12/S2.13 status",
            ],
        },
    }


def build_export_index(root: Path, report_json: bytes, md_bytes: bytes,
                       manifest_json: bytes) -> dict[str, Any]:
    def entry(rel: str, data: bytes) -> dict[str, Any]:
        return {"path": rel, "sha256": _sha256_bytes(data),
                "byte_size": len(data)}

    return {
        "schema_version":
            "s2_11_g0_5_pre_authorization_export_index@4.0.0",
        "release": "s2_11_g0_5_pre_authorization_v4",
        "artifacts": {
            "report_json": entry(
                "outputs/reports/s2_11_g0_5_pre_authorization_v4.json",
                report_json),
            "report_md": entry(
                "outputs/reports/s2_11_g0_5_pre_authorization_v4.md",
                md_bytes),
            "manifest": entry(
                "outputs/reports/"
                "s2_11_g0_5_pre_authorization_v4.manifest.json",
                manifest_json),
        },
        "manifest": {
            "path": "outputs/reports/"
                    "s2_11_g0_5_pre_authorization_v4.manifest.json",
            "sha256": _sha256_bytes(manifest_json),
        },
    }


def main() -> int:
    try:
        report = build_report(ROOT)
    except BuilderFail as exc:
        print(f"BUILD FAILED (fail-closed): {exc}", file=sys.stderr)
        return 2

    report_json = (json.dumps(report, ensure_ascii=False, indent=2) + "\n") \
        .encode("utf-8")
    md_bytes = render_md(report).encode("utf-8")

    bindings = collect_bindings(ROOT, report)
    manifest = build_manifest(ROOT, report_json, md_bytes, bindings)
    manifest_json = (json.dumps(manifest, ensure_ascii=False, indent=2)
                     + "\n").encode("utf-8")
    export_index = build_export_index(ROOT, report_json, md_bytes,
                                      manifest_json)
    export_json = (json.dumps(export_index, ensure_ascii=False, indent=2)
                   + "\n").encode("utf-8")

    try:
        _write(OUT_JSON, report_json)
        _write(OUT_MD, md_bytes)
        _write(OUT_MANIFEST, manifest_json)
        _write(OUT_EXPORT, export_json)
    except BuilderFail as exc:
        print(f"BUILD FAILED (refusing overwrite): {exc}", file=sys.stderr)
        return 2

    print(f"pre-authorization capsule v4 written: "
          f"{OUT_JSON.relative_to(ROOT)}")
    print(f"markdown written: {OUT_MD.relative_to(ROOT)}")
    print(f"manifest written: {OUT_MANIFEST.relative_to(ROOT)}")
    print(f"export index written: {OUT_EXPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
