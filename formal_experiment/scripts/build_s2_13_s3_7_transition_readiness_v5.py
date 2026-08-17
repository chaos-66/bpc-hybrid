# -*- coding: utf-8 -*-
"""Deterministic builder for the S2.13 -> S3.7 transition control capsule v5.

Builds (all under formal_experiment/):
  outputs/reports/s2_13_s3_7_transition_readiness_v5.json
  outputs/reports/s2_13_s3_7_transition_readiness_v5.md
  outputs/reports/s2_13_s3_7_transition_readiness_v5.manifest.json
  outputs/reports/s2_13_s3_7_transition_readiness_v5_export_index.json

v5 relationship to v1/v2/v3/v4 (which stay byte-exact, never edited or
moved):
  * v5 SUPERSEDES the v4 current-state judgments of S2.11 and S2.12:
      - S2.11: Checkpoint E1 established the CANONICAL review/proposal v2
        model (field states unresolved/absent/present, modality label +
        byte-verified evidence spans, multi-span fields, actor-action map,
        order relations; v1 proposals are declared superseded and must NOT
        be approved). proposal v2 is unadjudicated (human_approved=false,
        gold=false, reviewer never the user); the importer v2 dry-run
        shows blocked=0 / unresolved=0 / adjudicable=36; only ONE user
        content confirmation bound to the proposal v2 SHA remains.
      - S2.12: Checkpoint E3 replaced the v1 whole-field string
        exact-equality evaluator with the Stage 2 formal-contract-aligned
        stratified evaluator v2 (modality label accuracy/macro-F1/
        per-class + five-field Sun literal-overlap span P/R/F1, parity
        verified in-process) and produced execution plan/readiness v2 and
        API readiness v2 (exact model ids, call bounds, token caps,
        cost_cap_unresolved, NO final authorization sentence yet).
        S2.12 = partial + execution-ready; the real run stays blocked on
        the user S2.11 adjudication (36/36) and the API authorization.
  * All v1/v2/v3/v4 s2_13_s3_7_transition_readiness files are bound (path
    + sha256) in the supersedes list and must remain byte-identical.
  * The v2/v3/v4 fail-closed guarantees (three-state Gold Rule Record
    probe, exact manifest/export reconstruction, strict verifier verdict)
    continue unchanged.

Hard rules implemented here (same as v1/v2/v3/v4):
  * Every state judgment is RE-DERIVED from current on-disk assets,
    manifests, hashes, or executed independent verifiers. No hardcoded
    "exists / does not exist" final conclusions, no wall-clock timestamps.
  * Identical inputs produce byte-identical outputs (deterministic rebuild).
  * Existing outputs whose bytes differ are REFUSED (no overwrite).
  * The builder never creates or modifies Gold, predictions, results,
    contracts, or gates. It only writes its own four outputs.
  * Fail closed: any missing required evidence asset, any failed
    independent verifier, any unverified Gold Rule Record candidate, any
    schema-invalid report, any S1.7 authorization manifest not in
    freeze_applied state, any Stage 3 decision-Gold inconsistency with the
    frozen correction, or any audit claim_boundary contradiction aborts the
    build with exit 2.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

OUT_DIR = ROOT / "outputs" / "reports"
OUT_JSON = OUT_DIR / "s2_13_s3_7_transition_readiness_v5.json"
OUT_MD = OUT_DIR / "s2_13_s3_7_transition_readiness_v5.md"
OUT_MANIFEST = OUT_DIR / "s2_13_s3_7_transition_readiness_v5.manifest.json"
OUT_EXPORT = OUT_DIR / "s2_13_s3_7_transition_readiness_v5_export_index.json"

SCHEMA = ROOT / "configs" / "schemas" / "s2_13_s3_7_transition_readiness_v5.schema.json"

SCHEMA_VERSION = "s2_13_s3_7_transition_readiness@5.0.0"
REPORT_ID = "s2_13_s3_7_transition_readiness_v5"

EXPECTED_RULE_IDS = [
    "article6", "article7", "article15", "article16", "article17",
    "article20", "article22", "article33", "article34",
]

# Files that are KNOWN non-Gold-Rule-Record assets. The name-pattern probe
# skips them defensively so that no legitimate Stage 2 span Gold, Stage 3
# decision Gold, or Stage 1 Process Gold can ever be misjudged as a Gold
# Rule Record candidate.
KNOWN_NON_GOLD_RULE_RECORD_FILES = (
    "data/gold/stage2/estg150_formal_gold_v1.json",
    "data/gold/stage3/stage3_matching_gold_v1.json",
    "data/gold/stage3/stage3_violation_gold_v1.json",
    "data/gold/stage1/process_records/stage1_process_gold_v1.json",
)

# Historical readiness reports that may mention expected Gold Rule Record
# paths; any concrete existing path they mention is probed as a candidate.
HISTORY_READINESS_SOURCES = (
    "outputs/reports/s37_oracle_readiness_v1.json",
    "outputs/reports/s3_7_oracle_readiness_v2.json",
)


def _sort_rule_ids(ids: set[str]) -> list[str]:
    """Canonical deterministic order: article + numeric suffix."""
    return sorted(ids, key=lambda s: (s.split("article")[0],
                                      int(s.split("article")[1])))

# (relative path, supports --json)
INDEPENDENT_VERIFIERS: tuple[tuple[str, bool], ...] = (
    ("scripts/verify_stage1_process_gold.py", True),
    ("scripts/verify_s1_7_freezer_authorization.py", True),
    ("scripts/verify_formal_benchmark_release_v2.py", True),
    ("scripts/verify_s2_12_execution_ready.py", True),
    ("scripts/verify_s2_12_execution_ready_v2.py", True),
    ("outputs/reports/verify_b0_formal_arm_v1.py", False),
    ("outputs/reports/verify_direct_llm_formal_arm_v1.py", False),
    ("outputs/reports/verify_sun_llm_fallback_formal_arm_v1.py", False),
    ("outputs/reports/verify_stage2_formal_comparison_v1.py", False),
)

# Historical assets whose CURRENT-STATE judgments are superseded by this
# ledger, PLUS the complete v1 capsule. The files themselves are preserved
# unmodified; the verifier binds their bytes. Reasons are provenance
# annotations, not disk conclusions.
SUPERSEDED: tuple[tuple[str, str], ...] = (
    ("outputs/reports/s2_13_stage2_freeze_gap_capsule.json",
     "2026-08-11 current-state judgment predates the S1.7 freeze (2026-08-13) "
     "and still lists S1.7 as blocked ('true Gold Process Records'); the "
     "remaining-items list is superseded by this v2 ledger while the "
     "historical file stays unmodified."),
    ("outputs/reports/s2_13_stage2_freeze_gap_capsule.md",
     "2026-08-11 Markdown rendering of the same superseded gap capsule; "
     "preserved unmodified as historical provenance."),
    ("outputs/reports/s3_7_oracle_readiness_v2.json",
     "2026-08-11 current-state judgment is stale: it hardcodes "
     "gold_process_records.exist=false with 'S1.5 human Process Gold not "
     "started', which the 2026-08-13 Stage 1 Process Gold publication and "
     "S1.7 freeze invalidated; superseded by this v2 ledger, historical "
     "content preserved."),
    ("outputs/reports/s37_oracle_readiness_v1.json",
     "2026-08-09 current-state judgment is stale: 'true Gold Process Records "
     "not present' and the S1.7 gap no longer hold after 2026-08-13; its "
     "Gold-Rule-Records absence finding remains true and is carried forward; "
     "superseded by this v2 ledger, historical content preserved."),
    ("outputs/reports/formal_benchmark_release_v2.manifest.json",
     "Its publication-time exclusions block ('gold_process_records DO NOT "
     "EXIST', 'gold_rule_records DO NOT EXIST') is a historical snapshot: the "
     "gold_process_records exclusion is now stale (Stage 1 Process Gold "
     "published 2026-08-13) while the gold_rule_records exclusion remains "
     "true; the release manifest file itself stays unmodified."),
    ("scripts/build_s1_5_s3_7_readiness_v1.py",
     "Historical builder that hardcodes the pre-freeze conclusion "
     "'true Gold Process Records DO NOT EXIST (S1.5 human Process Gold not "
     "started)'; preserved unmodified as provenance; its current-state output "
     "logic is superseded by this deterministic v2 builder."),
    ("scripts/build_s3_7_oracle_readiness.py",
     "Historical builder for s37_oracle_readiness_v1.json that hardcodes "
     "'true Gold Process Records ... NOT present'; preserved unmodified as "
     "provenance; its current-state output logic is superseded by this "
     "deterministic v2 builder."),
    # --- v1 capsule: current-state conclusions still basically correct,
    #     verifier-completeness / fail-closed guarantees superseded by v2 ---
    ("configs/schemas/s2_13_s3_7_transition_readiness.schema.json",
     "v1 schema; kept byte-exact. v2 supersedes v1's verifier-completeness "
     "guarantees (v1 schema cannot express the three-state Gold-Rule-Record "
     "probe, the exact manifest/export reconstruction checks, or the strict "
     "verifier verdict)."),
    ("scripts/build_s2_13_s3_7_transition_readiness_v1.py",
     "v1 builder; kept byte-exact. Its Gold-Rule-Record probe computed "
     "candidates but unconditionally returned exist=false, its manifest and "
     "export checks only iterated existing entries, and its non-JSON "
     "verifier verdict accepted the bare 'VERIFIED' substring (which "
     "'NOT VERIFIED' also contains); these v1 fail-closed gaps are "
     "superseded by the v2 builder."),
    ("scripts/verify_s2_13_s3_7_transition_readiness_v1.py",
     "v1 verifier; kept byte-exact. Its manifest/export checks only "
     "re-verified entries already present in the files (missing or empty "
     "maps escaped), so v2 supersedes that completeness guarantee."),
    ("tests/test_s2_13_s3_7_transition_readiness_v1.py",
     "v1 focused tests; kept byte-exact. v2 adds the three-state Gold-Rule-"
     "Record candidate, exact manifest/export reconstruction and strict "
     "verdict negative cases."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v1.json",
     "v1 transition ledger report; its current-state conclusions remain "
     "basically correct and are carried forward by v2, while its "
     "verifier-completeness / fail-closed guarantees are superseded by v2; "
     "the file stays byte-exact."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v1.md",
     "v1 Markdown rendering; preserved byte-exact as historical provenance; "
     "the current-state report is superseded by the v2 report."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v1.manifest.json",
     "v1 manifest; preserved byte-exact; v2's manifest is independently "
     "re-constructed and compared exactly (v1 manifest structure is not "
     "modified)."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v1_export_index.json",
     "v1 export index; preserved byte-exact; v2's export index is exactly "
     "re-constructed from disk bytes and compared (no entry-level iteration "
     "that could miss missing or extra entries)."),
    # --- v2 capsule: fail-closed guarantees carried forward by v3; the
    #     v2 current-state S2.11 judgment is superseded by v3 (S2.11 is now
    #     in_progress_human_adjudication) ---
    ("configs/schemas/s2_13_s3_7_transition_readiness_v2.schema.json",
     "v2 schema; kept byte-exact (historical lifecycle semantics)."),
    ("scripts/build_s2_13_s3_7_transition_readiness_v2.py",
     "v2 builder; kept byte-exact; its S2.11 current-state judgment "
     "(blocked on authorization) is superseded by v3."),
    ("scripts/verify_s2_13_s3_7_transition_readiness_v2.py",
     "v2 verifier; kept byte-exact; its active-verification role is "
     "superseded by v3."),
    ("tests/test_s2_13_s3_7_transition_readiness_v2.py",
     "v2 pytest file: CORRECTED lifecycle test semantics only (v3); the "
     "v2 core assets are untouched."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v2.json",
     "v2 transition ledger report; byte-exact historical provenance; its "
     "S2.11=blocked judgment is superseded by v3."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v2.md",
     "v2 Markdown rendering; byte-exact historical provenance."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v2.manifest.json",
     "v2 manifest; byte-exact historical provenance."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v2_export_index.json",
     "v2 export index; byte-exact historical provenance."),
    # --- v3 capsule: fail-closed guarantees carried forward by v4; the
    #     v3 current-state S2.11 (workload derived from the 29-candidate
    #     run) and S2.12 (retrospective only) judgments are superseded by
    #     v4 (36-item review population; S2.12 execution-ready) ---
    ("configs/schemas/s2_13_s3_7_transition_readiness_v3.schema.json",
     "v3 schema; kept byte-exact (historical lifecycle semantics)."),
    ("scripts/build_s2_13_s3_7_transition_readiness_v3.py",
     "v3 builder; kept byte-exact; its S2.11/S2.12 current-state judgments "
     "are superseded by v4."),
    ("scripts/verify_s2_13_s3_7_transition_readiness_v3.py",
     "v3 verifier; kept byte-exact; its active-verification role is "
     "superseded by v4."),
    ("tests/test_s2_13_s3_7_transition_readiness_v3.py",
     "v3 pytest file: lifecycle test semantics only (v4); the v3 core "
     "assets are untouched."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v3.json",
     "v3 transition ledger report; byte-exact historical provenance; its "
     "S2.11 workload (29-candidate run) and S2.12 retrospective-only "
     "judgments are superseded by v4."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v3.md",
     "v3 Markdown rendering; byte-exact historical provenance."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v3.manifest.json",
     "v3 manifest; byte-exact historical provenance."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v3_export_index.json",
     "v3 export index; byte-exact historical provenance."),
    # --- v4 capsule: fail-closed guarantees carried forward by v5; the
    #     v4 current-state S2.11 (v1 proposals) and S2.12 (v1 plan/
    #     evaluator) judgments are superseded by v5 (canonical v2 model;
    #     formal-contract-aligned evaluator v2) ---
    ("configs/schemas/s2_13_s3_7_transition_readiness_v4.schema.json",
     "v4 schema; kept byte-exact (historical lifecycle semantics)."),
    ("scripts/build_s2_13_s3_7_transition_readiness_v4.py",
     "v4 builder; kept byte-exact; its S2.11/S2.12 current-state judgments "
     "are superseded by v5."),
    ("scripts/verify_s2_13_s3_7_transition_readiness_v4.py",
     "v4 verifier; kept byte-exact; its active-verification role is "
     "superseded by v5."),
    ("tests/test_s2_13_s3_7_transition_readiness_v4.py",
     "v4 pytest file: lifecycle test semantics only (v5); the v4 core "
     "assets are untouched."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v4.json",
     "v4 transition ledger report; byte-exact historical provenance; its "
     "S2.11 (v1 proposals) and S2.12 (v1 evaluator) judgments are "
     "superseded by v5."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v4.md",
     "v4 Markdown rendering; byte-exact historical provenance."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v4.manifest.json",
     "v4 manifest; byte-exact historical provenance."),
    ("outputs/reports/s2_13_s3_7_transition_readiness_v4_export_index.json",
     "v4 export index; byte-exact historical provenance."),
)

PROHIBITIONS = (
    "Stage 2 method predictions must NOT be treated as Gold Rule Records.",
    "Parser candidates must NOT be treated as Gold Process Records.",
    "Stage 3 matching/violation decision labels must NOT be treated as "
    "complete Rule/Process Gold.",
    "Development Stage 3 numbers must NOT be promoted to formal results.",
    "audit_project.py --require-final-ready returning 0 must NOT bypass the "
    "MASTER_PIPELINE S2.13 / S3.7 dependencies.",
)

FINAL_READY_SEMANTICS = (
    "final_experiment_ready=true means ONLY that the Stage 2 three-method "
    "formal evaluation / final-metric MACHINE gates are ready (three "
    "verified formal capsules, hash-consistent shared comparison capsule, "
    "user-authorized G0.4 contract); it does NOT mean S2.13, S3.7, or full "
    "MASTER_PIPELINE completion."
)

AUTHORIZATION_SENTENCE_REASON = (
    "No 'directly start the formal Oracle' authorization sentence may be "
    "generated now: substantive dependencies remain (S2.13 freeze; formal, "
    "user-adjudicated and frozen GDPR Gold Rule Records for the 9 rule IDs; "
    "S3.4-S3.6 formal promotion). Oracle readiness is not reducible to a "
    "single authorization."
)


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
    """Project-relative display path; falls back to the absolute path when
    the given path is outside the project root (e.g. pytest tmp_path)."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _require_asset(path: Path, what: str) -> str:
    """Return the sha256 of a required evidence asset; abort if missing."""
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


def _iter_strings(value: Any):
    """Recursively yield every string inside a JSON-like structure."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)


def run_independent_verifier(root: Path, rel: str,
                             has_json: bool) -> dict[str, Any]:
    """Run one independent verifier as a subprocess and report its result.

    Deterministic: verifier scripts are offline and byte-deterministic.
    Strict verdict: exit code 0 AND an explicit success line are required;
    the bare substring 'VERIFIED' is NOT sufficient because 'NOT VERIFIED'
    also contains it (v2 fix).
    """
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
    explicit_verdict = bool(
        "VERIFIED" in out and "NOT VERIFIED" not in out)
    verified = bool(rc == 0 and (explicit_verdict or has_json))
    if has_json and rc == 0 and checks is None:
        verified = False
    result: dict[str, Any] = {"path": rel, "verified": verified,
                              "exit_code": rc, "checks": checks}
    return result


# ---------------------------------------------------------------------------
# Pure derivations from disk (no subprocesses, no wall-clock)
# ---------------------------------------------------------------------------

def derive_stage1(root: Path) -> list[dict[str, Any]]:
    gold = root / "data" / "gold" / "stage1" / "process_records" / \
        "stage1_process_gold_v1.json"
    gold_manifest = root / "data" / "gold" / "stage1" / "manifest.json"
    freeze_auth = root / "outputs" / "reports" / \
        "s1_5_process_gold_freeze_authorization_v1.manifest.json"
    pred = root / "data" / "predictions" / "stage1_formal_v1" / \
        "formal_predictions_v1.json"
    res = root / "data" / "results" / "stage1_formal_v1" / \
        "stage1_formal_evaluation_v1.json"
    report_v2 = root / "outputs" / "reports" / "stage1_formal_evaluation_v2.json"
    report_v2_manifest = root / "outputs" / "reports" / \
        "stage1_formal_evaluation_v2.manifest.json"
    s1_7_auth = root / "outputs" / "reports" / \
        "s1_7_freezer_authorization_v1.manifest.json"
    s1_7_v2_packet = root / "outputs" / "reports" / \
        "s1_7_freezer_readiness_dry_run_v2.json"
    gold_verifier = root / "scripts" / "verify_stage1_process_gold.py"
    s1_7_verifier = root / "scripts" / "verify_s1_7_freezer_authorization.py"

    gold_sha = _require_asset(gold, "Stage 1 Process Gold")
    gold_manifest_sha = _require_asset(gold_manifest, "Stage 1 Gold manifest")
    freeze_auth_sha = _require_asset(freeze_auth, "S1.5 freeze authorization")
    s1_7_auth_sha = _require_asset(s1_7_auth, "S1.7 freezer authorization")
    s1_7_auth_doc = _load_json(s1_7_auth)
    if s1_7_auth_doc.get("status") != "freeze_applied":
        raise BuilderFail(
            "fail-closed: s1_7_freezer_authorization_v1.manifest.json status "
            f"is {s1_7_auth_doc.get('status')!r}, expected 'freeze_applied'")
    if s1_7_auth_doc.get("authorized_by_user") is not True:
        raise BuilderFail(
            "fail-closed: s1_7 freezer authorization manifest is not "
            "authorized_by_user=true")

    return [
        {
            "task_id": "S1.5",
            "status": "verified",
            "note": "Stage 1 Process Gold frozen and published (user-authorized "
                    "2026-08-13; 7/7 records, 135/135 label fields, 7/7 "
                    "structure decisions); independent verifier "
                    "scripts/verify_stage1_process_gold.py VERIFIED.",
            "evidence": [
                _evidence(gold, "disk_asset", gold_sha),
                _evidence(gold_manifest, "manifest", gold_manifest_sha),
                _evidence(freeze_auth, "manifest", freeze_auth_sha),
                _evidence(gold_verifier, "independent_verifier",
                          _sha256_file(gold_verifier)),
            ],
        },
        {
            "task_id": "S1.6",
            "status": "verified",
            "note": "Fixed-GDPR-7 formal descriptive component evaluation "
                    "(target-aware claim: post-Gold development, "
                    "strict_test_blind=false, no held-out generalization "
                    "claim); P2 config/implementation/runtime, predictions "
                    "and ORIGINAL metrics byte-unchanged.",
            "evidence": [
                _evidence(pred, "disk_asset", _require_asset(pred, "S1.6 predictions")),
                _evidence(res, "disk_asset", _require_asset(res, "S1.6 results")),
                _evidence(report_v2, "disk_asset", _require_asset(report_v2, "S1.6 v2 report")),
                _evidence(report_v2_manifest, "manifest",
                          _require_asset(report_v2_manifest, "S1.6 v2 report manifest")),
            ],
        },
        {
            "task_id": "S1.7",
            "status": "frozen",
            "note": "Formal Stage 1 freeze APPLIED (user-authorized "
                    "2026-08-13): non-tuned P2 method, existing P0/P1/P2 "
                    "predictions, ORIGINAL metrics, Stage 1 Process Gold and "
                    "the verified evaluation capsule are frozen; zero "
                    "LLM/API; the freeze does NOT auto-authorize the Stage 3 "
                    "Oracle.",
            "evidence": [
                _evidence(s1_7_auth, "manifest", s1_7_auth_sha),
                _evidence(s1_7_v2_packet, "disk_asset",
                          _require_asset(s1_7_v2_packet, "S1.7 readiness v2 packet")),
                _evidence(s1_7_verifier, "independent_verifier",
                          _sha256_file(s1_7_verifier)),
            ],
        },
    ]


def derive_stage2(root: Path) -> list[dict[str, Any]]:
    arms = ("b0", "direct_llm", "sun_llm_fallback")
    pred_files: dict[str, Path] = {}
    res_files: dict[str, Path] = {}
    arm_manifests: dict[str, Path] = {}
    for arm in arms:
        pred_files[arm] = root / "data" / "predictions" / \
            f"{arm}_formal_arm_v1" / "predictions.json"
        res_files[arm] = root / "data" / "results" / \
            f"{arm}_formal_arm_v1" / "evaluation_coarse.json"
        arm_manifests[arm] = root / "outputs" / "reports" / \
            f"{arm}_formal_arm_v1.manifest.json"
    comparison = root / "outputs" / "reports" / \
        "stage2_formal_three_method_comparison_v1.json"
    comparison_manifest = root / "outputs" / "reports" / \
        "stage2_formal_three_method_comparison_v1.manifest.json"
    s2_11_license = root / "outputs" / "reports" / \
        "s2_11_license_adapter_readiness_v2.json"
    s2_11_dry_run = root / "outputs" / "reports" / \
        "s2_11_data_qualification_mapping_dry_run.json"
    s2_12_report = root / "outputs" / "reports" / \
        "s2_12_formal_descriptive_error_analysis_v1.json"
    s2_12_manifest = root / "outputs" / "reports" / \
        "s2_12_formal_descriptive_error_analysis_v1.manifest.json"
    s2_12_plan_config = root / "configs" / "s2_12_execution_plan_v2.json"
    s2_12_plan_report = root / "outputs" / "reports" / \
        "s2_12_execution_plan_v2.json"
    s2_12_readiness = root / "outputs" / "reports" / \
        "s2_12_execution_readiness_v2.json"
    s2_12_api_readiness = root / "outputs" / "reports" / \
        "s2_12_api_readiness_v2.json"
    s2_12_ready_verifier = root / "scripts" / \
        "verify_s2_12_execution_ready_v2.py"
    s2_13_gap = root / "outputs" / "reports" / \
        "s2_13_stage2_freeze_gap_capsule.json"
    verifiers = {
        "b0": root / "outputs" / "reports" / "verify_b0_formal_arm_v1.py",
        "direct_llm": root / "outputs" / "reports" / "verify_direct_llm_formal_arm_v1.py",
        "sun_llm_fallback": root / "outputs" / "reports" / "verify_sun_llm_fallback_formal_arm_v1.py",
        "comparison": root / "outputs" / "reports" / "verify_stage2_formal_comparison_v1.py",
    }

    s2_10_evidence: list[dict[str, Any]] = []
    for arm in arms:
        s2_10_evidence.append(_evidence(
            pred_files[arm], "disk_asset",
            _require_asset(pred_files[arm], f"S2.10 {arm} predictions")))
        s2_10_evidence.append(_evidence(
            res_files[arm], "disk_asset",
            _require_asset(res_files[arm], f"S2.10 {arm} results")))
        s2_10_evidence.append(_evidence(
            arm_manifests[arm], "manifest",
            _require_asset(arm_manifests[arm], f"S2.10 {arm} arm manifest")))
        s2_10_evidence.append(_evidence(
            verifiers[arm], "independent_verifier",
            _sha256_file(verifiers[arm])))
    s2_10_evidence.append(_evidence(
        comparison, "disk_asset",
        _require_asset(comparison, "S2.10 comparison report")))
    s2_10_evidence.append(_evidence(
        comparison_manifest, "manifest",
        _require_asset(comparison_manifest, "S2.10 comparison manifest")))
    s2_10_evidence.append(_evidence(
        verifiers["comparison"], "independent_verifier",
        _sha256_file(verifiers["comparison"])))

    license_sha = _require_asset(s2_11_license, "S2.11 license readiness")
    dry_run_sha = _require_asset(s2_11_dry_run, "S2.11 qualification dry-run")
    license_doc = _load_json(s2_11_license)
    blockers = license_doc.get("s2_11_exact_blockers") or []
    if not blockers:
        raise BuilderFail(
            "fail-closed: s2_11_license_adapter_readiness_v2.json has no "
            "s2_11_exact_blockers list")
    dry_run_doc = _load_json(s2_11_dry_run)
    if dry_run_doc.get("status") != "dry_run_not_applied":
        raise BuilderFail(
            "fail-closed: s2_11_data_qualification_mapping_dry_run.json "
            f"status is {dry_run_doc.get('status')!r}, expected "
            "'dry_run_not_applied'")
    if license_doc.get("authorization_sentence") is not None:
        raise BuilderFail(
            "fail-closed: S2.11 license readiness unexpectedly carries an "
            "authorization sentence")
    # Real glob (v3: carried forward from v2; no frozen G0.5 complexity
    # contract may exist under configs/evaluation/).
    g05_matches = sorted(
        p.relative_to(root).as_posix()
        for p in (root / "configs" / "evaluation").glob("g05_*"))
    g05_matches += sorted(
        p.relative_to(root).as_posix()
        for p in (root / "configs" / "evaluation").glob("complexity_*"))

    # Checkpoint A-E S2.11 assets (all re-verified from disk; v5 reads the
    # CANONICAL v2 surface/proposals/importer assets).
    s2_11_candidate_run = root / "outputs" / "reports" / \
        "s2_11_candidate_run_v1.json"
    s2_11_g5_report = root / "outputs" / "reports" / \
        "s2_11_g5_review_surface_v1.json"
    s2_11_blank_review = root / "data" / "development" / "human_review" / \
        "s2_11_blank_review_v2.json"
    s2_11_decisions = root / "data" / "development" / "human_review" / \
        "s2_11_review_decisions_v2.json"
    s2_11_membership = root / "outputs" / "reports" / \
        "s2_11_corpus_membership_v1.json"
    s2_11_proposal_v2 = root / "outputs" / "reports" / \
        "s2_11_proposal_report_v2.json"
    s2_11_importer_v2 = root / "outputs" / "reports" / \
        "s2_11_batch_import_dry_run_v2.json"
    candidate_run_doc = _load_json(s2_11_candidate_run)
    if not candidate_run_doc.get("candidates"):
        raise BuilderFail(
            "fail-closed: S2.11 candidate run report has no candidates")
    if candidate_run_doc.get("gold_created") is not False:
        raise BuilderFail(
            "fail-closed: S2.11 candidate run must not create Gold")
    g5_doc = _load_json(s2_11_g5_report)
    if g5_doc.get("status") != "applied_review_surface_open":
        raise BuilderFail(
            "fail-closed: G5 review surface must be applied_review_surface_"
            f"open, got {g5_doc.get('status')!r}")
    quarantine_total = int(candidate_run_doc["counts"]["total_quarantined"])
    # v5: review workload from the CANONICAL v2 blank pack (40/4/36).
    blank_doc = _load_json(s2_11_blank_review)
    pop = blank_doc.get("population") or {}
    if int(pop.get("review_population", 0)) != 36 or \
            int(pop.get("nonempty_membership", 0)) != 36 or \
            int(pop.get("candidate_available", 0)) != 29 or \
            int(pop.get("candidate_unavailable", 0)) != 7:
        raise BuilderFail(
            "fail-closed: blank review pack v2 population must be "
            "36=29+7 (review_population == nonempty_membership == 36)")
    workload = int(pop["review_population"])
    unavailable = int(pop["candidate_unavailable"])
    proposal_doc = _load_json(s2_11_proposal_v2)
    if proposal_doc.get("coverage") != "36/36" or \
            proposal_doc.get("human_approved") is not False or \
            proposal_doc.get("gold_created") is not False:
        raise BuilderFail(
            "fail-closed: proposal v2 must be 36/36, human_approved=false, "
            "gold_created=false")
    importer_doc = _load_json(s2_11_importer_v2)
    import_stats = importer_doc.get("import_stats") or {}
    if import_stats.get("blocked_fields") != 0 or \
            import_stats.get("blocked_samples") != 0 or \
            import_stats.get("unresolved_fields") != 0 or \
            import_stats.get("adjudicable") != 36:
        raise BuilderFail(
            "fail-closed: importer v2 dry-run must show blocked=0/"
            "unresolved=0/adjudicable=36")

    return [
        {
            "task_id": "S2.10",
            "status": "verified",
            "note": "Three-method formal capsules, hash-consistent shared "
                    "comparison capsule and the formal three-method "
                    "comparison report are published and independently "
                    "verified (authorized G0.4 evaluation views; new LLM "
                    "calls 0).",
            "evidence": s2_10_evidence,
        },
        {
            "task_id": "S2.11",
            "status": "in_progress_human_adjudication",
            "blockers": [
                f"{workload} review items require ONE user content "
                "confirmation bound to the proposal v2 SHA (canonical v2 "
                "model; importer v2 dry-run: blocked=0 / unresolved=0 / "
                "adjudicable=36; reviewer only from the confirmation "
                "event)",
                f"{unavailable} of the {workload} review items carry no "
                "candidate (stable error codes in the blank pack); "
                f"{quarantine_total} records quarantined overall (see the "
                "candidate run report)",
            ],
            "note": "Complex legal corpus ACTIVATED under the "
                    "user-authorized local read-only non-redistributive "
                    "containment policy: Checkpoint A applied "
                    "G1/G2/G3/G4/G6 and froze G0.5; Checkpoint B generated "
                    "candidates and opened the blank review surface; "
                    "Checkpoint C closed the review population to 40/4/36 "
                    "(29 available / 7 unavailable); Checkpoint E1 "
                    "established the CANONICAL v2 model (unresolved/absent/"
                    "present, modality label + byte-verified evidence "
                    "spans, multi-span fields, actor-action map, order "
                    "relations) with 36 re-reviewed offline proposals "
                    "(deepseek_offline_proposal_v2; human_approved=false, "
                    "gold=false, reviewer never the user; proposal v1 "
                    "declared superseded and NOT approvable). artifact "
                    "license remains unknown (never claimed verified); raw "
                    "third-party text is never committed.",
            "evidence": [
                _evidence(s2_11_candidate_run, "disk_asset",
                          _require_asset(s2_11_candidate_run,
                                         "S2.11 candidate run")),
                _evidence(s2_11_g5_report, "disk_asset",
                          _require_asset(s2_11_g5_report,
                                         "S2.11 G5 review surface")),
                _evidence(s2_11_blank_review, "disk_asset",
                          _require_asset(s2_11_blank_review,
                                         "S2.11 blank review pack v2")),
                _evidence(s2_11_decisions, "disk_asset",
                          _require_asset(s2_11_decisions,
                                         "S2.11 review decisions v2")),
                _evidence(s2_11_membership, "disk_asset",
                          _require_asset(s2_11_membership,
                                         "S2.11 corpus membership")),
                _evidence(s2_11_proposal_v2, "disk_asset",
                          _require_asset(s2_11_proposal_v2,
                                         "S2.11 proposal report v2")),
                _evidence(s2_11_importer_v2, "disk_asset",
                          _require_asset(s2_11_importer_v2,
                                         "S2.11 importer v2 dry-run")),
                _derivation_evidence(
                    "derived: S2.11 = in_progress_human_adjudication from "
                    "the canonical v2 blank pack population (36 = 29 + 7), "
                    "the unadjudicated proposal v2 and the importer v2 "
                    "dry-run (blocked=0); no Gold created"),
            ],
        },
        {
            "task_id": "S2.12",
            "status": "partial",
            "note": "Execution-ready v2 (Checkpoint E3): the S2.12 "
                    "execution plan v2 is FROZEN (pre-registered G0.5 "
                    "L1/L2/L3 stratification; supersedes the v1 plan whose "
                    "evaluator/Gold-shape contract was corrected); the "
                    "stratified evaluator v2 reuses the Stage 2 FORMAL "
                    "contract (modality label accuracy/macro-F1/per-class + "
                    "five-field Sun literal-overlap span P/R/F1) with an "
                    "in-process parity check against the formal evaluator; "
                    "API readiness v2 derives exact model ids "
                    "(deepseek-v4-pro both arms), call bounds (36/72/108), "
                    "output token cap 4096, input cap unresolved, "
                    "cost_cap_unresolved - NO final authorization sentence "
                    "is issued; the REAL run stays blocked on the user "
                    "S2.11 adjudication (36/36) and the API authorization.",
            "evidence": [
                _evidence(s2_12_report, "disk_asset",
                          _require_asset(s2_12_report, "S2.12 report")),
                _evidence(s2_12_manifest, "manifest",
                          _require_asset(s2_12_manifest, "S2.12 manifest")),
                _evidence(s2_12_plan_config, "disk_asset",
                          _require_asset(s2_12_plan_config,
                                         "S2.12 execution plan config v2")),
                _evidence(s2_12_plan_report, "disk_asset",
                          _require_asset(s2_12_plan_report,
                                         "S2.12 execution plan report v2")),
                _evidence(s2_12_readiness, "disk_asset",
                          _require_asset(s2_12_readiness,
                                         "S2.12 execution readiness v2")),
                _evidence(s2_12_api_readiness, "disk_asset",
                          _require_asset(s2_12_api_readiness,
                                         "S2.12 API readiness v2")),
                _evidence(s2_12_ready_verifier, "independent_verifier",
                          _sha256_file(s2_12_ready_verifier)),
                _derivation_evidence(
                    "derived: S2.12 = partial + execution-ready v2 from "
                    "the frozen plan v2 (status=frozen, supersedes_v1), "
                    "the readiness v2 (real_run_refused, gates pending, "
                    "parity passed) and the executed independent S2.12 "
                    "verifier v2"),
            ],
        },
        {
            "task_id": "S2.13",
            "status": "blocked",
            "blockers": [
                "S2.11 in_progress_human_adjudication (36 review items "
                "pending the ONE user confirmation bound to the proposal "
                "v2 SHA)",
                "S2.12 full DoD not met (execution-ready v2 but the real "
                "stratified run is blocked on the user adjudication and "
                "the API authorization)",
            ],
            "note": "Stage 2 freeze NOT complete. DoD unchanged (S2.1-S2.12 "
                    "full DoD); NOT decomposed into new formal tasks and "
                    "NOT modified this round; final_experiment_ready=true "
                    "does NOT complete S2.13.",
            "evidence": [
                _derivation_evidence(
                    "derived: S2.11 in_progress_human_adjudication AND "
                    "S2.12 partial -> S2.13 blocked; Stage 2 freeze DoD "
                    "unchanged this round (see this round's change event)"),
                _evidence(s2_13_gap, "disk_asset",
                          _require_asset(s2_13_gap, "historical S2.13 gap capsule")),
                _evidence(s2_11_license, "disk_asset", license_sha),
            ],
        },
    ]


def derive_stage3(root: Path) -> list[dict[str, Any]]:
    matching = root / "data" / "gold" / "stage3" / "stage3_matching_gold_v1.json"
    violation = root / "data" / "gold" / "stage3" / "stage3_violation_gold_v1.json"
    correction = root / "data" / "development" / "human_review" / \
        "stage3_gold_annotation_human_correction_v1.json"
    freeze_manifest = root / "outputs" / "reports" / \
        "s32_s33_gold_annotation_freeze_v1.manifest.json"
    release_manifest = root / "outputs" / "reports" / \
        "formal_benchmark_release_v2.manifest.json"
    release_verifier = root / "scripts" / "verify_formal_benchmark_release_v2.py"
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

    matching_sha = _require_asset(matching, "Stage 3 matching Gold")
    violation_sha = _require_asset(violation, "Stage 3 violation Gold")
    correction_sha = _require_asset(correction, "Stage 3 frozen correction")
    freeze_sha = _require_asset(freeze_manifest, "S3.2/S3.3 freeze manifest")
    release_sha = _require_asset(release_manifest, "release v2 manifest")

    matching_doc = _load_json(matching)
    violation_doc = _load_json(violation)
    consistent = bool(
        matching_doc.get("count") == 25
        and violation_doc.get("count") == 33
        and matching_doc.get("sources", {}).get("correction_pack_sha256")
        == correction_sha
        and violation_doc.get("sources", {}).get("correction_pack_sha256")
        == correction_sha)
    if not consistent:
        raise BuilderFail(
            "fail-closed: Stage 3 matching/violation decision Gold is "
            "inconsistent with the frozen correction pack (counts or "
            "correction_pack_sha256 mismatch)")

    rule_ids = _sort_rule_ids(
        {item.get("rule_id") for item in matching_doc.get("items", [])}
        | {item.get("rule_id") for item in violation_doc.get("items", [])})
    if rule_ids != EXPECTED_RULE_IDS:
        raise BuilderFail(
            f"fail-closed: derived Stage 3 rule-id set {rule_ids} differs "
            f"from the expected 9 GDPR rule IDs {EXPECTED_RULE_IDS}")

    s3_2_evidence = [
        _evidence(matching, "disk_asset", matching_sha),
        _evidence(correction, "disk_asset", correction_sha),
        _evidence(freeze_manifest, "manifest", freeze_sha),
        _evidence(release_manifest, "manifest", release_sha),
        _evidence(release_verifier, "independent_verifier",
                  _sha256_file(release_verifier)),
    ]
    s3_3_evidence = [
        _evidence(violation, "disk_asset", violation_sha),
        _evidence(correction, "disk_asset", correction_sha),
        _evidence(freeze_manifest, "manifest", freeze_sha),
        _evidence(release_manifest, "manifest", release_sha),
        _evidence(release_verifier, "independent_verifier",
                  _sha256_file(release_verifier)),
    ]

    return [
        {
            "task_id": "S3.2",
            "status": "verified",
            "note": "25 matching decision Gold frozen and published "
                    "(data/gold/stage3/stage3_matching_gold_v1.json); these "
                    "relevance decisions are NOT Gold Rule Records.",
            "evidence": s3_2_evidence,
        },
        {
            "task_id": "S3.3",
            "status": "verified",
            "note": "33 violation decision Gold frozen and published "
                    "(data/gold/stage3/stage3_violation_gold_v1.json); these "
                    "type/evidence decisions are NOT Gold Rule Records.",
            "evidence": s3_3_evidence,
        },
        {
            "task_id": "S3.4",
            "status": "development_only",
            "note": "Winter wrapper development evidence only; formal "
                    "completion still blocked: S1.7 dependency is now "
                    "SATISFIED (frozen 2026-08-13), S2.13 remains blocked.",
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
            "note": "Sun Stage 3 method-level reconstruction development "
                    "evidence only; formal completion still blocked on S2.13 "
                    "(S1.7 dependency now satisfied).",
            "evidence": [
                _evidence(s35, "manifest",
                          _require_asset(s35, "S3.5 dev manifest")),
            ],
        },
        {
            "task_id": "S3.6",
            "status": "development_only",
            "note": "BM25 v3 + TF-IDF/SVD development baselines only; formal "
                    "completion still blocked on S2.13 (S1.7 dependency now "
                    "satisfied); threshold 0.5 remains a fixed development "
                    "setting.",
            "evidence": [
                _evidence(s36_bm25, "manifest",
                          _require_asset(s36_bm25, "S3.6 BM25 v3 dev manifest")),
                _evidence(s36_tfidf, "manifest",
                          _require_asset(s36_tfidf, "S3.6 TF-IDF dev manifest")),
            ],
        },
        {
            "task_id": "S3.7",
            "status": "blocked",
            "blockers": [
                "Formal, user-adjudicated and frozen GDPR Gold Rule Records "
                "for the 9 rule IDs do not exist",
                "S2.13 blocked",
                "S3.4/S3.5/S3.6 formal completion pending",
            ],
            "note": "Formal Oracle NOT started and NOT authorized; "
                    "development Stage 3 numbers must not be promoted; the "
                    "oracle_control block records the fail-closed flags.",
            "evidence": [
                _evidence(s37_v1, "disk_asset",
                          _require_asset(s37_v1, "historical s37 readiness v1")),
                _evidence(s3_7_v2, "disk_asset",
                          _require_asset(s3_7_v2, "historical s3_7 readiness v2")),
                _derivation_evidence(
                    "derived: no oracle authorization manifest and no formal "
                    "oracle run/result assets found on disk"),
            ],
        },
    ]


def derive_dependency_matrix(root: Path) -> dict[str, Any]:
    return {
        "stage1": derive_stage1(root),
        "stage2": derive_stage2(root),
        "stage3": derive_stage3(root),
    }


def derive_stage1_process_gold(root: Path) -> dict[str, Any]:
    gold = root / "data" / "gold" / "stage1" / "process_records" / \
        "stage1_process_gold_v1.json"
    manifest = root / "data" / "gold" / "stage1" / "manifest.json"
    gold_sha = _require_asset(gold, "Stage 1 Process Gold")
    manifest_sha = _require_asset(manifest, "Stage 1 Gold manifest")
    doc = _load_json(manifest)
    counts = doc.get("record_counts", {})
    if counts != {"process_records": 7, "label_fields": 135,
                  "structure_decisions": 7}:
        raise BuilderFail(
            f"fail-closed: Stage 1 Gold manifest record_counts {counts} "
            "differ from 7/135/7")
    return {
        "exists": True,
        "path": "data/gold/stage1/process_records/stage1_process_gold_v1.json",
        "sha256": gold_sha,
        "manifest_path": "data/gold/stage1/manifest.json",
        "manifest_sha256": manifest_sha,
        "counts": dict(counts),
    }


def derive_stage3_decision_gold(root: Path) -> dict[str, Any]:
    matching = root / "data" / "gold" / "stage3" / "stage3_matching_gold_v1.json"
    violation = root / "data" / "gold" / "stage3" / "stage3_violation_gold_v1.json"
    correction = root / "data" / "development" / "human_review" / \
        "stage3_gold_annotation_human_correction_v1.json"
    matching_sha = _require_asset(matching, "Stage 3 matching Gold")
    violation_sha = _require_asset(violation, "Stage 3 violation Gold")
    correction_sha = _require_asset(correction, "Stage 3 frozen correction")
    matching_doc = _load_json(matching)
    violation_doc = _load_json(violation)
    consistent = bool(
        matching_doc.get("sources", {}).get("correction_pack_sha256")
        == correction_sha
        and violation_doc.get("sources", {}).get("correction_pack_sha256")
        == correction_sha)
    if not consistent:
        raise BuilderFail(
            "fail-closed: Stage 3 decision Gold inconsistent with the frozen "
            "correction pack")
    return {
        "matching": {
            "path": "data/gold/stage3/stage3_matching_gold_v1.json",
            "sha256": matching_sha,
            "count": matching_doc.get("count"),
        },
        "violation": {
            "path": "data/gold/stage3/stage3_violation_gold_v1.json",
            "sha256": violation_sha,
            "count": violation_doc.get("count"),
        },
        "frozen_correction": {
            "path": "data/development/human_review/"
                    "stage3_gold_annotation_human_correction_v1.json",
            "sha256": correction_sha,
        },
        "consistency_with_frozen_correction": True,
        "note": "The published matching/violation decisions are DECISION "
                "Gold only; they are NOT complete Rule/Process Gold and must "
                "never be used as Gold Rule Records.",
    }


def _probe_gold_rule_record_candidates(root: Path) -> list[tuple[Path, str]]:
    """THREE-STATE probe (v2): find ANY unverified Gold Rule Record
    candidate on disk.

    Sources covered:
      1. any file under data/gold/** whose name contains 'rule_record' or
         'rule-record' (case-insensitive), excluding the explicitly known
         non-Gold assets (Stage 2 EStG-150 span Gold, Stage 3
         matching/violation decision Gold, Stage 1 Process Gold);
      2. any concrete path mentioned by the historical readiness reports
         that matches a rule-record name pattern and exists on disk;
      3. any file under outputs/reports/** whose name contains
         'rule_record' or 'rule-record' (defensive: no rule-record-named
         report may appear without the user-authorized formal
         manifest/schema/verifier trio).

    Returns [] when the disk is clean (state 1). Any hit is state 2 and
    must make the build fail closed (the builder never self-promotes a
    candidate to formal Gold; state 3 - exist=true - requires a future
    user-authorized freeze/publication path that v2 does NOT implement).
    """
    found: list[tuple[Path, str]] = []

    def _name_matches(name: str) -> bool:
        low = name.lower()
        return "rule_record" in low or "rule-record" in low

    gold_dir = root / "data" / "gold"
    if gold_dir.is_dir():
        for p in sorted(gold_dir.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if rel in KNOWN_NON_GOLD_RULE_RECORD_FILES:
                continue  # explicit known non-Gold (defensive)
            if _name_matches(p.name):
                found.append((p, "data/gold name pattern "
                                 "(rule_record / rule-record)"))

    reports_dir = root / "outputs" / "reports"
    if reports_dir.is_dir():
        for p in sorted(reports_dir.rglob("*")):
            if not p.is_file():
                continue
            if _name_matches(p.name):
                found.append((p, "outputs/reports name pattern "
                                 "(rule_record / rule-record)"))

    for rel in HISTORY_READINESS_SOURCES:
        doc = _load_json(root / rel)
        for value in _iter_strings(doc):
            if not _name_matches(value):
                continue
            candidate = value.strip()
            if not candidate or "*" in candidate:
                continue  # glob pattern, not a concrete path
            p = root / candidate
            if p.is_file():
                found.append((p, f"concrete path mentioned in {rel}"))
    return found


def derive_gold_rule_records(root: Path) -> dict[str, Any]:
    """Derive Gold-Rule-Record absence with the THREE-STATE probe (v2).

    State 1 (clean disk): exist=false, the 9 rule IDs, the probe record and
    an explicit path/hash binding of the checked Stage 2 EStG-150 Gold.
    State 2 (any unverified candidate): BuilderFail listing every candidate
    path - the build never emits a report claiming exist=false.
    State 3 (exist=true): reserved for a future user-authorized freeze /
    publication path with a formal schema, manifest and independent
    verifier; NOT implemented or simulated by v2.
    """
    matching = root / "data" / "gold" / "stage3" / "stage3_matching_gold_v1.json"
    violation = root / "data" / "gold" / "stage3" / "stage3_violation_gold_v1.json"
    estg_gold = root / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
    matching_doc = _load_json(matching)
    violation_doc = _load_json(violation)
    rule_ids = _sort_rule_ids(
        {item.get("rule_id") for item in matching_doc.get("items", [])}
        | {item.get("rule_id") for item in violation_doc.get("items", [])})
    if rule_ids != EXPECTED_RULE_IDS:
        raise BuilderFail(
            f"fail-closed: derived rule-id set {rule_ids} differs from the "
            f"expected 9 GDPR rule IDs {EXPECTED_RULE_IDS}")
    estg_sha = _require_asset(estg_gold, "Stage 2 EStG-150 formal Gold")

    candidates = _probe_gold_rule_record_candidates(root)
    if candidates:
        listed = "; ".join(
            f"{p.relative_to(root).as_posix()} ({reason})"
            for p, reason in candidates)
        raise BuilderFail(
            "fail-closed: unverified Gold Rule Record candidate(s) found on "
            "disk WITHOUT a user-authorized formal manifest/schema/verifier "
            "trio; not reporting exist=false and NOT self-promoting to "
            f"formal Gold. Candidates: {listed}")

    return {
        "exist": False,
        "absence_derived_from": (
            "no file under data/gold/ or outputs/reports/ matches a Gold "
            "Rule Record artifact name pattern (rule_record / rule-record) "
            "and no concrete rule-record path mentioned by the historical "
            "readiness reports exists on disk; data/gold/stage2/"
            "estg150_formal_gold_v1.json was explicitly checked and bound "
            "below - it is the EStG-150 Stage 2 six-element span Gold and "
            "is NOT a GDPR Rule Record"),
        "candidate_probe": {
            "patterns": [
                "data/gold/** file name contains rule_record or rule-record "
                "(case-insensitive; known non-Gold assets excluded)",
                "outputs/reports/** file name contains rule_record or "
                "rule-record (defensive)",
                "concrete rule-record paths mentioned by historical "
                "readiness reports (s37_oracle_readiness_v1 / "
                "s3_7_oracle_readiness_v2) that exist on disk",
            ],
            "history_sources": list(HISTORY_READINESS_SOURCES),
            "found": [],
        },
        "covered_rule_ids": rule_ids,
        "rule_ids_derived_from": [
            "data/gold/stage3/stage3_matching_gold_v1.json",
            "data/gold/stage3/stage3_violation_gold_v1.json",
        ],
        "stage2_estg150_gold_is_not_gdpr_rule_records": True,
        "checked_stage2_estg150_gold": {
            "path": "data/gold/stage2/estg150_formal_gold_v1.json",
            "sha256": estg_sha,
        },
        "note": "Formal, user-adjudicated and frozen GDPR Gold Rule Records "
                "for the 9 rule IDs do NOT exist. This round did NOT create, "
                "infer, or auto-fill any Gold Rule Record; their production "
                "remains a user-owned adjudication + freeze task, and "
                "exist=true would require a separate user-authorized "
                "freeze/publication path with formal schema, manifest and "
                "independent verifier (NOT implemented by v2).",
    }


def derive_stage3_development_only(root: Path) -> dict[str, Any]:
    def dev_item(task: str, formal_completion: str,
                 manifest_paths: list[str]) -> dict[str, Any]:
        evidence = []
        for rel in manifest_paths:
            p = root / rel
            evidence.append(_evidence(
                p, "manifest", _require_asset(p, f"{task} development manifest")))
        return {"status": "development_only",
                "formal_completion": formal_completion,
                "evidence": evidence}

    return {
        "s3_4": dev_item(
            "S3.4",
            "Winter wrapper development evidence only; formal completion "
            "still blocked on S2.13 (S1.7 dependency now satisfied by the "
            "2026-08-13 freeze).",
            ["outputs/development/s34_winter_stage3_development_v3_clean/manifest.json",
             "outputs/development/s34_winter_stage3_development_v3_prototype_literal/manifest.json"]),
        "s3_5": dev_item(
            "S3.5",
            "Sun Stage 3 development evidence only; formal completion still "
            "blocked on S2.13 (S1.7 dependency now satisfied).",
            ["outputs/development/s35_sun_stage3_development_v2/manifest.json"]),
        "s3_6": dev_item(
            "S3.6",
            "BM25 v3 + TF-IDF/SVD development baselines only; formal "
            "completion still blocked on S2.13 (S1.7 dependency now "
            "satisfied).",
            ["outputs/development/s36_bm25_stage3_development_v3/manifest.json",
             "outputs/development/s36_tfidf_svd_stage3_development_v2/manifest.json"]),
    }


def derive_oracle_control(root: Path) -> dict[str, Any]:
    matrix = derive_dependency_matrix(root)
    grr = derive_gold_rule_records(root)
    s2_13 = next(i for i in matrix["stage2"] if i["task_id"] == "S2.13")
    dev = derive_stage3_development_only(root)
    all_dev = all(item["status"] == "development_only"
                  for item in dev.values())
    authorization_assets = sorted(
        p.relative_to(root).as_posix()
        for p in (root / "outputs" / "reports").glob("*oracle_authorization*"))
    run_assets = sorted(
        p.relative_to(root).as_posix()
        for p in (root / "data" / "results").glob("*oracle*"))
    run_assets += sorted(
        p.relative_to(root).as_posix()
        for p in (root / "outputs" / "evidence").glob("*oracle*"))
    started = bool(run_assets)
    authorized = bool(authorization_assets)
    ready = bool(
        s2_13["status"] == "verified" or s2_13["status"] == "complete"
        or s2_13["status"] == "frozen") and grr["exist"] and not all_dev
    # (always False today: S2.13 blocked, Gold Rule Records absent, S3.4-S3.6
    #  development-only)
    probe_evidence = [
        _derivation_evidence(
            "probe outputs/reports/*oracle_authorization* -> "
            f"{authorization_assets or 'no matches'}"),
        _derivation_evidence(
            "probe data/results/*oracle* + outputs/evidence/*oracle* -> "
            f"{run_assets or 'no matches'}"),
    ]
    return {
        "formal_oracle_started": started,
        "formal_oracle_authorized": authorized,
        "ready_for_oracle_authorization": ready,
        "ready_for_oracle_authorization_reason": (
            "Substantive dependencies remain, so readiness is NOT reducible "
            "to a single authorization: S2.13 is blocked, formal "
            "user-adjudicated frozen GDPR Gold Rule Records for the 9 rule "
            "IDs do not exist, and S3.4/S3.5/S3.6 formal completion is "
            "pending."),
        "authorization_sentence": None,
        "authorization_sentence_reason": AUTHORIZATION_SENTENCE_REASON,
        "no_pseudo_oracle": True,
        "probe_evidence": probe_evidence,
    }


def derive_audit_consistency(root: Path) -> dict[str, Any]:
    from formal_experiment.audit import collect_project_audit
    audit = collect_project_audit()
    final_ready = bool(audit.get("final_experiment_ready"))
    claim_boundary = str(audit.get("claim_boundary", ""))
    warning_msgs = [
        item.get("message", "")
        for item in audit.get("findings", {}).get("warnings", [])
        if item.get("code") == "estg_reconstruction_development_only"]
    warning_text = "\n".join(warning_msgs)
    contradiction_free = True
    if final_ready:
        if "remains false" in claim_boundary:
            contradiction_free = False
        if "NOT produced yet" in claim_boundary:
            contradiction_free = False
        if "remains false" in warning_text:
            contradiction_free = False
    if not contradiction_free:
        raise BuilderFail(
            "fail-closed: audit claim_boundary / estg warning still contain "
            "stale false statements that contradict "
            "final_experiment_ready=true")
    return {
        "final_experiment_ready": final_ready,
        "semantics": FINAL_READY_SEMANTICS,
        "derived_from": "formal_experiment.audit.collect_project_audit() "
                        "run in-process at build time",
        "claim_boundary_contradiction_free": True,
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
            "Every state judgment in this report is re-derived from current "
            "on-disk assets, manifests, hashes, or executed independent "
            "verifiers; no hardcoded existence conclusions and no wall-clock "
            "timestamps. v2 added the three-state Gold-Rule-Record probe, "
            "exact in-memory reconstruction of the manifest and the export "
            "index (no entry-level iteration that could miss missing or "
            "extra entries), and the strict non-JSON verifier verdict; "
            "v3/v4 carry those guarantees forward. v4 derives the S2.11 "
            "adjudication workload from the closed 40/4/36 review "
            "population (blank pack) instead of the 29-candidate run, and "
            "reports the S2.12 execution readiness (frozen plan, synthetic "
            "runner/evaluator readiness, zero-call API budget dry-run). "
            "v5 supersedes v4's S2.11 judgment with the CANONICAL v2 model "
            "(unresolved/absent/present, modality label + byte-verified "
            "evidence spans, multi-span fields, actor-action map, order "
            "relations; proposal v1 superseded/not approvable; proposal v2 "
            "unadjudicated; importer v2 dry-run blocked=0) and the S2.12 "
            "judgment with the formal-contract-aligned evaluator v2 "
            "(parity verified), plan/readiness v2 and API readiness v2 "
            "(cost_cap_unresolved; no final authorization sentence). "
            "Rebuilding on identical inputs produces byte-identical outputs; "
            "existing outputs with different bytes are refused."),
        "supersedes": supersedes,
        "dependency_matrix": derive_dependency_matrix(root),
        "stage1_process_gold": derive_stage1_process_gold(root),
        "stage3_decision_gold": derive_stage3_decision_gold(root),
        "gold_rule_records": derive_gold_rule_records(root),
        "stage3_development_only": derive_stage3_development_only(root),
        "oracle_control": derive_oracle_control(root),
        "prohibitions": list(PROHIBITIONS),
        "audit_consistency": derive_audit_consistency(root),
        "verification_scope": {
            "exact_manifest_reconstruction": True,
            "exact_export_reconstruction": True,
            "strict_verifier_verdict": True,
            "gold_rule_record_three_state_probe": True,
            "markdown_single_eof_newline": True,
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
    pattern, mirrors stage2_canonical.validate_schema_json). Supports the
    constructs this capsule schema actually uses: type, const, enum,
    pattern, minLength, minItems/maxItems/uniqueItems, minimum, required,
    additionalProperties=false, properties, items and local $ref. Fully
    offline and byte-deterministic (no third-party package)."""
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
    lines.append("# S2.13 → S3.7 Transition Readiness Ledger v2")
    lines.append("")
    lines.append(f"**Schema**: `{report['schema_version']}`")
    lines.append(f"**Report ID**: `{report['report_id']}`")
    lines.append("")
    lines.append("## Determinism")
    lines.append("")
    lines.append(report["build_note"])
    lines.append("")
    lines.append("## Superseded current-state judgments (historical files "
                 "preserved unmodified)")
    lines.append("")
    for item in report["supersedes"]:
        lines.append(f"- `{item['path']}` (sha256 `{item['sha256'][:12]}…`): "
                     f"{item['reason']}")
    lines.append("")
    lines.append("## Dependency matrix")
    lines.append("")
    for stage_key, stage_title in (("stage1", "Stage 1"),
                                   ("stage2", "Stage 2"),
                                   ("stage3", "Stage 3")):
        lines.append(f"### {stage_title}")
        lines.append("")
        for item in report["dependency_matrix"][stage_key]:
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
    lines.append("## Stage 1 Process Gold")
    lines.append("")
    pg = report["stage1_process_gold"]
    lines.append(f"- exists: **{pg['exists']}**")
    lines.append(f"- path: `{pg['path']}` (sha256 `{pg['sha256'][:12]}…`)")
    lines.append(f"- manifest: `{pg['manifest_path']}` "
                 f"(sha256 `{pg['manifest_sha256'][:12]}…`)")
    lines.append(f"- counts: {pg['counts']}")
    lines.append("- independent verifier `scripts/verify_stage1_process_gold.py` "
                 "VERIFIED (see verifiers_executed)")
    lines.append("")
    lines.append("## Stage 3 decision Gold")
    lines.append("")
    dg = report["stage3_decision_gold"]
    lines.append(f"- matching: `{dg['matching']['path']}` "
                 f"(count {dg['matching']['count']}, "
                 f"sha256 `{dg['matching']['sha256'][:12]}…`)")
    lines.append(f"- violation: `{dg['violation']['path']}` "
                 f"(count {dg['violation']['count']}, "
                 f"sha256 `{dg['violation']['sha256'][:12]}…`)")
    lines.append(f"- frozen correction: `{dg['frozen_correction']['path']}`")
    lines.append(f"- consistency_with_frozen_correction: "
                 f"**{dg['consistency_with_frozen_correction']}**")
    lines.append(f"- {dg['note']}")
    lines.append("")
    lines.append("## Gold Rule Records (three-state probe)")
    lines.append("")
    grr = report["gold_rule_records"]
    lines.append(f"- exist: **{grr['exist']}**")
    lines.append(f"- absence derived from: {grr['absence_derived_from']}")
    probe = grr["candidate_probe"]
    lines.append("- candidate probe patterns:")
    for pat in probe["patterns"]:
        lines.append(f"  - {pat}")
    lines.append(f"- candidate probe history sources: "
                 + ", ".join(probe["history_sources"]))
    lines.append(f"- candidate probe found: {probe['found']}")
    lines.append("- the 9 GDPR rule IDs covered by the matching/violation "
                 "decision packs (derived from disk): "
                 + ", ".join(grr["covered_rule_ids"]))
    lines.append(f"- rule_ids_derived_from: "
                 + ", ".join(grr["rule_ids_derived_from"]))
    lines.append(f"- stage2 EStG-150 Gold is NOT GDPR Rule Records: "
                 f"**{grr['stage2_estg150_gold_is_not_gdpr_rule_records']}**")
    checked = grr["checked_stage2_estg150_gold"]
    lines.append(f"- checked Stage 2 EStG-150 Gold: `{checked['path']}` "
                 f"(sha256 `{checked['sha256'][:12]}…`) - checked and bound, "
                 "NOT a GDPR Rule Record")
    lines.append(f"- {grr['note']}")
    lines.append("")
    lines.append("## S3.4–S3.6 development-only")
    lines.append("")
    for key in ("s3_4", "s3_5", "s3_6"):
        item = report["stage3_development_only"][key]
        lines.append(f"- **{key}**: {item['status']} — "
                     f"{item['formal_completion']}")
        for ev in item["evidence"]:
            lines.append(f"  - evidence [{ev['kind']}]: `{ev['path']}` "
                         f"sha256 `{ev['sha256'][:12]}…`")
    lines.append("")
    lines.append("## Oracle control (fail-closed)")
    lines.append("")
    oc = report["oracle_control"]
    lines.append(f"- formal_oracle_started: **{oc['formal_oracle_started']}**")
    lines.append(f"- formal_oracle_authorized: **{oc['formal_oracle_authorized']}**")
    lines.append(f"- ready_for_oracle_authorization: "
                 f"**{oc['ready_for_oracle_authorization']}** "
                 f"({oc['ready_for_oracle_authorization_reason']})")
    lines.append(f"- authorization_sentence: **{oc['authorization_sentence']}** "
                 f"({oc['authorization_sentence_reason']})")
    lines.append(f"- no_pseudo_oracle: **{oc['no_pseudo_oracle']}**")
    for ev in oc["probe_evidence"]:
        lines.append(f"- probe: {ev['path']}")
    lines.append("")
    lines.append("## Prohibitions")
    lines.append("")
    for i, text in enumerate(report["prohibitions"], start=1):
        lines.append(f"{i}. {text}")
    lines.append("")
    lines.append("## Audit consistency")
    lines.append("")
    ac = report["audit_consistency"]
    lines.append(f"- final_experiment_ready: "
                 f"**{ac['final_experiment_ready']}**")
    lines.append(f"- semantics: {ac['semantics']}")
    lines.append(f"- derived from: {ac['derived_from']}")
    lines.append(f"- claim_boundary_contradiction_free: "
                 f"**{ac['claim_boundary_contradiction_free']}**")
    lines.append("")
    lines.append("## Verification scope (v2 fail-closed guarantees)")
    lines.append("")
    for key, value in report["verification_scope"].items():
        lines.append(f"- {key}: **{value}**")
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
    # Single EOF newline: exactly one trailing "\n" (v2 fix) so that
    # `git diff --cached --check` passes on the generated Markdown.
    return "\n".join(lines).rstrip("\n") + "\n"


def collect_bindings(root: Path, report: dict[str, Any]) -> dict[str, str]:
    """All external asset paths -> sha256, in sorted deterministic order.

    v2 extends the v1 binding set with the audit/status sources of truth,
    the checked Stage 2 EStG-150 Gold, and the v2 builder/verifier/schema
    implementation files, so a complete exact-key comparison is possible.
    """
    bindings: dict[str, str] = {}
    for item in report["supersedes"]:
        bindings[item["path"]] = item["sha256"]
    for stage_key in ("stage1", "stage2", "stage3"):
        for entry in report["dependency_matrix"][stage_key]:
            for ev in entry["evidence"]:
                sha = ev.get("sha256")
                if sha and ev["kind"] in ("disk_asset", "manifest",
                                          "independent_verifier"):
                    bindings[ev["path"]] = sha
    for dev in report["stage3_development_only"].values():
        for ev in dev["evidence"]:
            if ev.get("sha256"):
                bindings[ev["path"]] = ev["sha256"]
    pg = report["stage1_process_gold"]
    bindings[pg["path"]] = pg["sha256"]
    bindings[pg["manifest_path"]] = pg["manifest_sha256"]
    dg = report["stage3_decision_gold"]
    bindings[dg["matching"]["path"]] = dg["matching"]["sha256"]
    bindings[dg["violation"]["path"]] = dg["violation"]["sha256"]
    bindings[dg["frozen_correction"]["path"]] = \
        dg["frozen_correction"]["sha256"]
    grr = report["gold_rule_records"]
    bindings[grr["checked_stage2_estg150_gold"]["path"]] = \
        grr["checked_stage2_estg150_gold"]["sha256"]
    # v5 additions: sources of truth read by this capsule and the audit
    # consistency derivation, the S2.11 canonical v2 assets, the S2.12 v2
    # execution-ready assets, plus the implementation files themselves.
    for rel in (
        "src/formal_experiment/audit.py",
        "src/formal_experiment/status.py",
        "scripts/build_s2_13_s3_7_transition_readiness_v5.py",
        "scripts/verify_s2_13_s3_7_transition_readiness_v5.py",
        "scripts/s2_11_build_proposals_v2.py",
        "scripts/s2_11_batch_import_v2.py",
        "scripts/verify_s2_11_review_freeze_v2.py",
        "src/bpc_hybrid/s2_11_canonical_v2.py",
        "data/development/human_review/s2_11_blank_review_v2.json",
        "data/development/human_review/s2_11_review_decisions_v2.json",
        "outputs/reports/s2_11_proposal_report_v2.json",
        "outputs/reports/s2_11_batch_import_dry_run_v2.json",
        "scripts/s2_12_build_execution_ready.py",
        "scripts/verify_s2_12_execution_ready.py",
        "scripts/s2_12_build_execution_ready_v2.py",
        "scripts/verify_s2_12_execution_ready_v2.py",
        "src/bpc_hybrid/s2_12_stratified_evaluator.py",
        "src/bpc_hybrid/s2_12_stratified_evaluator_v2.py",
        "src/bpc_hybrid/s2_12_method_adapter.py",
        "configs/s2_12_execution_plan_v1.json",
        "outputs/reports/s2_12_execution_plan_v1.json",
        "outputs/reports/s2_12_execution_readiness_v1.json",
        "configs/s2_12_execution_plan_v2.json",
        "outputs/reports/s2_12_execution_plan_v2.json",
        "outputs/reports/s2_12_execution_readiness_v2.json",
        "outputs/reports/s2_12_api_readiness_v2.json",
    ):
        bindings[rel] = _sha256_file(root / rel)
    bindings[str(SCHEMA.relative_to(root).as_posix())] = _sha256_file(SCHEMA)
    return dict(sorted(bindings.items()))


def build_manifest(root: Path, report_json: bytes, md_bytes: bytes,
                   bindings: dict[str, str]) -> dict[str, Any]:
    builder = Path(__file__)
    verifier = root / "scripts" / \
        "verify_s2_13_s3_7_transition_readiness_v5.py"
    return {
        "schema_version": "s2_13_s3_7_transition_readiness_manifest@5.0.0",
        "manifest_id": "s2_13_s3_7_transition_readiness_v5.manifest",
        "artifact_type": "transition_control_capsule",
        "determinism": {
            "no_wall_clock": True,
            "byte_identical_rebuild": True,
            "no_overwrite": True,
        },
        "artifacts": {
            "report_json": {
                "path": "outputs/reports/s2_13_s3_7_transition_readiness_v5.json",
                "sha256": _sha256_bytes(report_json),
                "byte_size": len(report_json),
            },
            "report_md": {
                "path": "outputs/reports/s2_13_s3_7_transition_readiness_v5.md",
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
                        "s2_13_s3_7_transition_readiness_v5.schema.json",
                "sha256": _sha256_file(SCHEMA),
            },
        },
        "zero_api": {"new_llm_api_calls": 0},
        "safety": {
            "created_or_modified": [
                "outputs/reports/s2_13_s3_7_transition_readiness_v5.json",
                "outputs/reports/s2_13_s3_7_transition_readiness_v5.md",
                "outputs/reports/"
                "s2_13_s3_7_transition_readiness_v5.manifest.json",
                "outputs/reports/"
                "s2_13_s3_7_transition_readiness_v5_export_index.json",
            ],
            "never_created_or_modified": [
                "data/gold/**",
                "data/predictions/**",
                "data/results/**",
                "configs/experiment_contract.json",
                "configs/methods.json",
                "any v1/v2/v3/v4 s2_13_s3_7_transition_readiness file "
                "(schema/builder/verifier/tests/reports)",
                "any publication status, method gate, Stage 3 gate, or "
                "S2.13/S3.7 status",
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
            "s2_13_s3_7_transition_readiness_export_index@5.0.0",
        "release": "s2_13_s3_7_transition_readiness_v5",
        "artifacts": {
            "report_json": entry(
                "outputs/reports/s2_13_s3_7_transition_readiness_v5.json",
                report_json),
            "report_md": entry(
                "outputs/reports/s2_13_s3_7_transition_readiness_v5.md",
                md_bytes),
            "manifest": entry(
                "outputs/reports/"
                "s2_13_s3_7_transition_readiness_v5.manifest.json",
                manifest_json),
        },
        "manifest": {
            "path": "outputs/reports/"
                    "s2_13_s3_7_transition_readiness_v5.manifest.json",
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
    md_text = render_md(report)
    md_bytes = md_text.encode("utf-8")

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

    print(f"transition readiness capsule v5 written: {OUT_JSON.relative_to(ROOT)}")
    print(f"markdown written: {OUT_MD.relative_to(ROOT)}")
    print(f"manifest written: {OUT_MANIFEST.relative_to(ROOT)}")
    print(f"export index written: {OUT_EXPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
