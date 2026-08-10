# -*- coding: utf-8 -*-
"""Build the B0 (sun_rule_only) method-gate authorization DRY-RUN package.

This package describes the ONLY formal method gate change the user is asked
to decide after this round. It is a dry-run: it is NOT applied. Nothing is
modified: methods.json, experiment_contract.json, Stage 3 gate, Gold or
publication status stay untouched.

The package contains:
- exact before/after of configs/methods.json for sun_rule_only only
- proposed formal_status
- B0 formal config / runner / input / Gold / evaluator hashes
- candidate metrics and replay evidence
- the exact formal run command that WOULD be executed after authorization
- expected audit blocker changes
- rollback method

Outputs:
- outputs/reports/sun_rule_only_method_gate_authorization_dry_run.json
- outputs/reports/sun_rule_only_method_gate_authorization_dry_run.md

Usage:
    python scripts/build_sun_rule_only_authorization_dry_run.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

METHODS_CONFIG = ROOT / "configs" / "methods.json"
B0_CONFIG = ROOT / "configs" / "models" / "estg150_b0_enhanced_s27_v10a.json"
B0_RUNNER = ROOT / "scripts" / "run_estg150_b0_formal.py"
V2_INPUT = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
GOLD_STAGE2 = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
SUN_LITERAL_CONFIG = ROOT / "configs" / "evaluation" / "sun_table8_literal_overlap_v2.json"
EVALUATOR_V3 = ROOT / "configs" / "stage2_evaluator_s210_v3.json"
RELEASE_MANIFEST = ROOT / "outputs" / "reports" / "formal_benchmark_release_v2.manifest.json"
CANDIDATE_DIR = ROOT / "outputs" / "development" / "b0_r4_formal_candidate_v1"
REPLAY_DIR = ROOT / "outputs" / "development" / "b0_r4_formal_candidate_v1_replay"
READINESS = ROOT / "outputs" / "reports" / "b0_d1_formal_readiness_v2.json"

OUT_JSON = ROOT / "outputs" / "reports" / "sun_rule_only_method_gate_authorization_dry_run.json"
OUT_MD = ROOT / "outputs" / "reports" / "sun_rule_only_method_gate_authorization_dry_run.md"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_package() -> dict[str, Any]:
    methods = _load_json(METHODS_CONFIG)
    before = next(m for m in methods.get("methods", [])
                  if m.get("id") == "sun_rule_only")
    after = dict(before)
    after["formal_status"] = "ready"
    after["command_status"] = "formal_ready_candidate_authorized"
    after["notes"] = (
        before.get("notes", "")
        + " B0-R4 formal candidate completed 2026-08-10 (F1 0.71865, "
        "P 0.6845 / R 0.7564, identical to the development snapshot), "
        "bound to formal input v2; formal status promoted by user "
        "authorization (dry-run package), NOT applied yet."
    )
    candidate_manifest = _load_json(CANDIDATE_DIR / "manifest.json")
    primary = _load_json(CANDIDATE_DIR / "evaluation_primary.json").get("overall", {})
    return {
        "schema_version": "sun_rule_only_method_gate_authorization_dry_run@1.0.0",
        "status": "dry_run_not_applied",
        "purpose": (
            "The ONLY formal method gate change the user is asked to decide. "
            "Nothing in this package is applied; methods.json / "
            "experiment_contract.json / Stage 3 gate / Gold / publication "
            "status are untouched."),
        "methods_json_change": {
            "file": "configs/methods.json",
            "scope": "sun_rule_only only; direct_llm and sun_llm_fallback untouched",
            "before": before,
            "after": after,
            "diff_fields": ["formal_status", "command_status", "notes"],
        },
        "proposed_formal_status": "ready",
        "binding_hashes": {
            "b0_config": {"path": "configs/models/estg150_b0_enhanced_s27_v10a.json",
                          "sha256": _sha256_file(B0_CONFIG)},
            "b0_runner": {"path": "scripts/run_estg150_b0_formal.py",
                          "sha256": _sha256_file(B0_RUNNER)},
            "formal_input_v2": {"path": "data/input/estg150_formal_inference_input_v2.json",
                                "sha256": _sha256_file(V2_INPUT)},
            "gold_stage2": {"path": "data/gold/stage2/estg150_formal_gold_v1.json",
                            "sha256": _sha256_file(GOLD_STAGE2)},
            "primary_evaluator_config": {"path": "configs/evaluation/sun_table8_literal_overlap_v2.json",
                                         "sha256": _sha256_file(SUN_LITERAL_CONFIG)},
            "strict_evaluator_config": {"path": "configs/stage2_evaluator_s210_v3.json",
                                        "sha256": _sha256_file(EVALUATOR_V3)},
            "release_manifest_v2": {"path": "outputs/reports/formal_benchmark_release_v2.manifest.json",
                                    "sha256": _sha256_file(RELEASE_MANIFEST)},
            "candidate_manifest": {"path": "outputs/development/b0_r4_formal_candidate_v1/manifest.json",
                                   "sha256": _sha256_file(CANDIDATE_DIR / "manifest.json")},
        },
        "candidate_metrics": {
            "records": len(_load_json(CANDIDATE_DIR / "b0_attempts.json").get("records", [])),
            "sun_literal_overlap_primary": primary,
            "replay_evidence": {
                "main_dir": "outputs/development/b0_r4_formal_candidate_v1",
                "replay_dir": "outputs/development/b0_r4_formal_candidate_v1_replay",
                "primary_metrics_byte_identical": True,
                "error_analysis_byte_identical": True,
                "config_snapshot_byte_identical": True,
                "attempts_record_content_identical": True,
                "nondeterministic_only": "runtime latency / seconds (performance timing)",
                "claim_scope": "formal_candidate_not_yet_authorized_as_formal_result",
            },
            "comparison_with_development_snapshot": (
                "identical metrics to the B0-R3 development snapshot "
                "(F1 0.71865): method semantics unchanged; only the input "
                "channel changed to formal input v2 (Gold-blind)"),
        },
        "formal_run_command_after_authorization": (
            "python scripts/run_estg150_b0_formal.py "
            "--runtime-home D:\\environment\\stanford-corenlp-4.5.10 "
            "--output-dir outputs/development/b0_r4_formal_candidate_v2_authorized "
            "&& python scripts/audit_project.py"),
        "expected_audit_changes_after_authorization": {
            "formal_methods_not_ready": "sun_rule_only moves out of the non-ready set",
            "final_experiment_not_ready": (
                "remains present while sun_llm_fallback and direct_llm are "
                "not ready (their authorization is a separate decision)"),
            "methods_unexpectedly_ready": (
                "MUST NOT trigger: audit currently errors when ALL three "
                "methods are ready; with only sun_rule_only ready the "
                "non-ready set still has 2 members"),
        },
        "rollback": {
            "git": "git revert of the authorization commit (methods.json only)",
            "manual": (
                "restore configs/methods.json sun_rule_only formal_status to "
                "'blocked_final_sun_stage2_reimplementation_required' and "
                "command_status to 'development_only_not_formal'; the "
                "candidate outputs under outputs/development are non-formal "
                "and need no rollback"),
        },
        "readiness_ref": {
            "path": "outputs/reports/b0_d1_formal_readiness_v2.json",
            "all_methods_bound_to_formal_input_v2": (
                _load_json(READINESS).get("summary", {}).get("d1_historical_predictions_reusable_zero_api") is True
                and _load_json(READINESS).get("summary", {}).get("h1_historical_predictions_reusable_zero_api") is True),
        },
        "untouched": [
            "configs/methods.json direct_llm",
            "configs/methods.json sun_llm_fallback",
            "configs/experiment_contract.json",
            "stage3 gate",
            "Gold files",
            "publication status",
        ],
    }


def main() -> int:
    package = build_package()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(package, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT_JSON.exists() and OUT_JSON.read_bytes() != data:
        raise RuntimeError(f"refusing to overwrite different content: {OUT_JSON}")
    OUT_JSON.write_bytes(data)

    md = ["# sun_rule_only method gate authorization (DRY-RUN, not applied)",
          "",
          "- status: dry_run_not_applied",
          f"- proposed formal_status: {package['proposed_formal_status']}",
          f"- candidate primary F1: {package['candidate_metrics']['sun_literal_overlap_primary'].get('f1')}",
          "",
          "## methods.json sun_rule_only diff (only this method)",
          "### before",
          f"- formal_status: {package['methods_json_change']['before']['formal_status']}",
          f"- command_status: {package['methods_json_change']['before']['command_status']}",
          "### after (proposed)",
          f"- formal_status: {package['methods_json_change']['after']['formal_status']}",
          f"- command_status: {package['methods_json_change']['after']['command_status']}",
          "",
          "## Binding hashes",
          ]
    for name, info in package["binding_hashes"].items():
        md.append(f"- {name}: {info['sha256'][:16]}... ({info['path']})")
    md += [
        "",
        "## Formal run command (after authorization)",
        f"```\n{package['formal_run_command_after_authorization']}\n```",
        "",
        "## Expected audit changes",
        f"- {package['expected_audit_changes_after_authorization']}",
        "",
        "## Rollback",
        f"- {package['rollback']['git']}",
        f"- {package['rollback']['manual']}",
        "",
    ]
    text = "\n".join(md)
    if OUT_MD.exists() and OUT_MD.read_text(encoding="utf-8") != text:
        raise RuntimeError(f"refusing to overwrite different content: {OUT_MD}")
    OUT_MD.write_text(text, encoding="utf-8")
    print(f"authorization dry-run package written: {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
