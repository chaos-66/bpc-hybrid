# -*- coding: utf-8 -*-
"""Build deterministic transition capsule v8 without changing older capsules."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/reports"
REPORT = OUT / "s2_13_s3_7_transition_readiness_v8.json"
MARKDOWN = OUT / "s2_13_s3_7_transition_readiness_v8.md"
MANIFEST = OUT / "s2_13_s3_7_transition_readiness_v8.manifest.json"
EXPORT = OUT / "s2_13_s3_7_transition_readiness_v8_export_index.json"
SCHEMA = ROOT / "configs/schemas/s2_13_s3_7_transition_readiness_v8.schema.json"
READINESS = ROOT / "outputs/reports/s2_12_execution_readiness_v4.json"

V7_ASSETS = (
    "configs/schemas/s2_13_s3_7_transition_readiness_v7.schema.json",
    "scripts/build_s2_13_s3_7_transition_readiness_v7.py",
    "scripts/verify_s2_13_s3_7_transition_readiness_v7.py",
    "tests/test_s2_13_s3_7_transition_readiness_v7.py",
    "outputs/reports/s2_13_s3_7_transition_readiness_v7.json",
    "outputs/reports/s2_13_s3_7_transition_readiness_v7.md",
    "outputs/reports/s2_13_s3_7_transition_readiness_v7.manifest.json",
    "outputs/reports/s2_13_s3_7_transition_readiness_v7_export_index.json",
)

CURRENT_HISTORY = {1, 2, 3, 4, 7}
SUPERSEDED_HISTORY_EXPECTED_FAILURES = {
    5: {
        "manifest exact reconstruction matches disk (structure, keys, values; no missing/extra entries)",
        "manifest bindings match disk",
        "dependency matrix re-derived and compared item-by-item",
    },
    6: {
        "manifest exact reconstruction matches disk (structure, keys, values; no missing/extra entries)",
        "manifest bindings match disk",
        "dependency matrix re-derived and compared item-by-item",
        "superseded historical reports + full v1-v5 capsule present, byte-unchanged and declared",
    },
}


class TransitionFail(ValueError):
    """Fail-closed transition builder error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _binding(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.is_file():
        raise TransitionFail(f"missing binding: {rel}")
    return {"path": rel, "sha256": _sha(path), "byte_size": path.stat().st_size}


def run_historical_verifiers() -> dict[str, Any]:
    matrix: dict[str, Any] = {}
    for version in range(1, 8):
        rel = f"scripts/verify_s2_13_s3_7_transition_readiness_v{version}.py"
        proc = subprocess.run(
            [sys.executable, str(ROOT / rel), "--json"],
            cwd=ROOT.parent, capture_output=True, text=True, timeout=180,
        )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise TransitionFail(f"transition v{version} verifier returned invalid JSON") from exc
        failed = {item["name"] for item in payload.get("checks", []) if not item.get("ok")}
        if version in CURRENT_HISTORY:
            if proc.returncode != 0 or payload.get("verified") is not True or failed:
                raise TransitionFail(f"transition v{version} verifier unexpectedly failed: {sorted(failed)}")
            outcome = "verified_current_or_preserved"
        else:
            expected = SUPERSEDED_HISTORY_EXPECTED_FAILURES[version]
            if proc.returncode == 0 or payload.get("verified") is not False or failed != expected:
                raise TransitionFail(
                    f"transition v{version} superseded fail-closed signature drift: "
                    f"expected={sorted(expected)} actual={sorted(failed)}"
                )
            outcome = "expected_fail_closed_superseded_snapshot"
        matrix[f"v{version}"] = {
            "path": rel,
            "sha256": _sha(ROOT / rel),
            "exit_code": proc.returncode,
            "verified": payload.get("verified"),
            "outcome": outcome,
            "failed_checks": sorted(failed),
        }
    return matrix


def _probe_gold_rule_records() -> dict[str, Any]:
    found: list[str] = []
    for base in (ROOT / "data/gold", ROOT / "outputs/reports"):
        for path in base.rglob("*"):
            if path.is_file() and ("rule_record" in path.name.lower() or "rule-record" in path.name.lower()):
                found.append(path.relative_to(ROOT).as_posix())
    if found:
        raise TransitionFail(f"Gold Rule Record candidate requires separate verification: {found}")
    return {
        "exist": False,
        "candidate_probe_found": [],
        "covered_rule_ids": [
            "article6", "article7", "article15", "article16", "article17",
            "article20", "article22", "article33", "article34",
        ],
        "note": "formal user-adjudicated frozen GDPR Gold Rule Records remain absent; none were created in this checkpoint",
    }


def build_report(history: Mapping[str, Any]) -> dict[str, Any]:
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    if readiness.get("status") != "partial_zero_api_arm_complete_api_arms_pending_authorization":
        raise TransitionFail("S2.12 readiness v4 status drift")
    return {
        "schema_version": "s2_13_s3_7_transition_readiness@8.0.0",
        "report_id": "s2_13_s3_7_transition_readiness_v8",
        "supersedes": [
            {**_binding(rel), "reason": "v8 supersedes v7 current-state judgments while preserving the v7 asset byte-exact"}
            for rel in V7_ASSETS
        ],
        "pipeline_state": {
            "S1.7": "frozen",
            "S2.11": "verified_frozen",
            "S2.12": "partial_zero_api_arm_complete_api_arms_pending",
            "S2.13": "blocked_only_on_remaining_S2.12_DoD",
            "S3.4_S3.6": "development_only",
            "S3.7": "formal_oracle_not_started",
        },
        "s2_11": {
            "status": "verified_frozen",
            "adjudicated": 36,
            "unresolved": 0,
            "reviewer": "hyc",
            "formal_gold": readiness["s2_11"]["formal_gold"],
            "formal_gold_payload_sha256": readiness["s2_11"]["formal_gold_payload_sha256"],
            "confirmation_event": readiness["s2_11"]["confirmation_event"],
            "provenance": "deepseek_offline_proposal_v3 + user batch confirmation by hyc; not independent-from-scratch expert annotation",
        },
        "s2_12": {
            "status": "partial",
            "readiness_v4": _binding("outputs/reports/s2_12_execution_readiness_v4.json"),
            "gold_blind_input": _binding("data/input/s2_12_complex_corpus_formal_input_v1.json"),
            "sun_rule_only": {
                "status": "verified_complete",
                "single_zero_api_arm_only": True,
                "evaluation": _binding("data/results/s2_12_sun_rule_only_v1/evaluation.json"),
                "actual_cost_usd": 0.0,
            },
            "direct_llm": "pending_explicit_api_authorization",
            "sun_llm_fallback": "pending_explicit_api_authorization",
            "api_preflight": _binding("outputs/reports/s2_12_api_preflight_v1.json"),
            "three_method_comparison_complete": False,
            "post_result_tuning_performed": False,
        },
        "s2_13": {
            "status": "blocked",
            "blockers": ["S2.12 remaining DoD: two API arms, three-method comparison, and S2.12 completion freeze"],
        },
        "stage3": {
            "S3.4": "development_only",
            "S3.5": "development_only",
            "S3.6": "development_only",
            "S3.7": {
                "status": "formal_oracle_not_started",
                "authorized": False,
                "blockers": ["S2.13", "formal GDPR Gold Rule Records", "formal promotion of S3.4-S3.6"],
            },
        },
        "gold_rule_records": _probe_gold_rule_records(),
        "historical_transition_verifiers": dict(history),
        "authorization": readiness["authorization"],
        "safety": {
            "new_llm_api_calls": 0,
            "new_network_calls": 0,
            "gold_rule_records_created": False,
            "oracle_started": False,
            "historical_transition_assets_modified": False,
            "project_audit_md_modified": False,
        },
    }


def _render_md(report: Mapping[str, Any]) -> bytes:
    lines = [
        "# S2.13 → S3.7 Transition Readiness v8",
        "",
        "- S2.11: **verified / frozen**, 36/36 adjudicated; formal Gold published.",
        "- S2.12: **partial**; `sun_rule_only` zero-API arm complete; `direct_llm` and `sun_llm_fallback` await explicit API authorization.",
        "- S2.13: **blocked only on remaining S2.12 DoD**.",
        "- S3.4–S3.6: **development-only**.",
        "- S3.7: **formal Oracle not started or authorized**; GDPR Gold Rule Records remain absent.",
        "",
        "The complex-corpus result is one zero-API arm, not a three-method comparison. No post-result method, rule, prompt, threshold, or Gold adjustment was made.",
        "",
        "Historical verifier lifecycle: v1–v4 and v7 verify; v5/v6 fail closed with their exact expected superseded-snapshot signatures.",
        "",
    ]
    return ("\n".join(lines)).encode("utf-8")


def build_artifacts(history: Mapping[str, Any]) -> dict[Path, bytes]:
    report = build_report(history)
    report_bytes = _json_bytes(report)
    md_bytes = _render_md(report)
    bindings = {
        rel: _sha(ROOT / rel)
        for rel in (
            *V7_ASSETS,
            "outputs/reports/s2_12_execution_readiness_v4.json",
            "outputs/reports/s2_12_api_preflight_v1.json",
            "data/input/s2_12_complex_corpus_formal_input_v1.json",
            "data/results/s2_12_sun_rule_only_v1/evaluation.json",
            *(f"scripts/verify_s2_13_s3_7_transition_readiness_v{v}.py" for v in range(1, 8)),
        )
    }
    manifest = {
        "schema_version": "s2_13_s3_7_transition_readiness_manifest@8.0.0",
        "manifest_id": "s2_13_s3_7_transition_readiness_v8.manifest",
        "artifacts": {
            "report_json": {"path": REPORT.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(report_bytes).hexdigest(), "byte_size": len(report_bytes)},
            "report_md": {"path": MARKDOWN.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(md_bytes).hexdigest(), "byte_size": len(md_bytes)},
        },
        "bindings": bindings,
        "implementation": {
            "builder": _binding("scripts/build_s2_13_s3_7_transition_readiness_v8.py"),
            "verifier": _binding("scripts/verify_s2_13_s3_7_transition_readiness_v8.py"),
            "schema": _binding("configs/schemas/s2_13_s3_7_transition_readiness_v8.schema.json"),
        },
        "zero_api": {"new_llm_api_calls": 0, "new_network_calls": 0},
    }
    manifest_bytes = _json_bytes(manifest)
    export = {
        "schema_version": "s2_13_s3_7_transition_readiness_export_index@8.0.0",
        "files": {
            REPORT.relative_to(ROOT).as_posix(): {"sha256": hashlib.sha256(report_bytes).hexdigest(), "byte_size": len(report_bytes)},
            MARKDOWN.relative_to(ROOT).as_posix(): {"sha256": hashlib.sha256(md_bytes).hexdigest(), "byte_size": len(md_bytes)},
            MANIFEST.relative_to(ROOT).as_posix(): {"sha256": hashlib.sha256(manifest_bytes).hexdigest(), "byte_size": len(manifest_bytes)},
        },
    }
    return {REPORT: report_bytes, MARKDOWN: md_bytes, MANIFEST: manifest_bytes, EXPORT: _json_bytes(export)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        history = run_historical_verifiers()
        artifacts = build_artifacts(history)
        if args.publish:
            existing = [path for path in artifacts if path.exists()]
            if existing:
                raise TransitionFail(f"refusing to overwrite v8 outputs: {existing}")
            OUT.mkdir(parents=True, exist_ok=True)
            staged: list[tuple[Path, Path]] = []
            for target, payload in artifacts.items():
                with tempfile.NamedTemporaryFile(dir=OUT, delete=False) as stream:
                    stage = Path(stream.name)
                    stream.write(payload)
                staged.append((stage, target))
            try:
                for stage, target in staged:
                    stage.replace(target)
            except Exception:
                for stage, _target in staged:
                    stage.unlink(missing_ok=True)
                raise
        else:
            for path, expected in artifacts.items():
                if not path.is_file() or path.read_bytes() != expected:
                    raise TransitionFail(f"v8 replay differs: {path}")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"Transition readiness v8 refused: {exc}")
        return 2
    print("S2.13 -> S3.7 transition readiness v8 VERIFIED (zero API, Oracle not started)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
