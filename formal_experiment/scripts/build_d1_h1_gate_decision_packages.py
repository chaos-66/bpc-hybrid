# -*- coding: utf-8 -*-
"""D1/H1 method-gate decision DRY-RUN packages (zero-API, NOT applied).

For each of the two LLM methods a separate decision package is produced with
exact before/after of configs/methods.json, the zero-API binding evidence,
risks, expected audit changes and a copy-ready authorization sentence. The
packages are proposals only: they are NOT applied, the zero-API
re-evaluation is NOT a substitute for formal authorization, and no real
LLM/API call is implied.

Outputs:
- outputs/reports/direct_llm_method_gate_decision_dry_run.json
- outputs/reports/direct_llm_method_gate_decision_dry_run.md
- outputs/reports/sun_llm_fallback_method_gate_decision_dry_run.json
- outputs/reports/sun_llm_fallback_method_gate_decision_dry_run.md
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

METHODS_CONFIG = ROOT / "configs" / "methods.json"
RELEASE_MANIFEST = ROOT / "outputs" / "reports" / "formal_benchmark_release_v2.manifest.json"
READINESS = ROOT / "outputs" / "reports" / "b0_d1_formal_readiness_v2.json"
COMPARISON = (ROOT / "outputs" / "evidence" / "d1_h1_zero_api_reeval_v1"
              / "comparison_capsule.json")

OUT = ROOT / "outputs" / "reports"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _package(method_id: str, proposed_status: str,
             auth_sentence: str, rationale: str,
             risk_note: str, audit_change_note: str,
             llm_calls_recorded: int) -> dict[str, Any]:
    methods = _load_json(METHODS_CONFIG)
    before = next(m for m in methods.get("methods", [])
                  if m.get("id") == method_id)
    after = dict(before)
    after["formal_status"] = proposed_status
    after["command_status"] = "formal_ready_candidate_authorized"
    comparison = _load_json(COMPARISON)
    metrics = comparison.get("methods", {}).get(method_id, {})
    return {
        "schema_version": "method_gate_decision_dry_run@1.0.0",
        "method_id": method_id,
        "status": "dry_run_not_applied",
        "purpose": rationale,
        "methods_json_change": {
            "file": "configs/methods.json",
            "scope": f"{method_id} only",
            "before": before,
            "after": after,
            "diff_fields": ["formal_status", "command_status"],
        },
        "evidence": {
            "zero_api_binding": _load_json(READINESS).get("methods", {}).get(
                method_id, {}).get("binding_ok"),
            "comparison_capsule": "outputs/evidence/d1_h1_zero_api_reeval_v1/comparison_capsule.json",
            "fine_span_fields": metrics.get("fine_span_fields", {}),
            "coarse_span_fields": metrics.get("coarse_span_fields", {}),
            "modality_labels": metrics.get("modality_labels", {}),
            "historical_llm_calls": metrics.get("historical_llm_calls"),
            "new_llm_calls": 0,
            "note": ("zero-API re-evaluation is binding evidence, NOT formal "
                     "authorization; a formal run still requires the user's "
                     "LLM budget authorization"),
        },
        "risks": risk_note,
        "expected_audit_changes": audit_change_note,
        "authorization_sentence": auth_sentence,
        "rollback": "git revert of the applied commit (methods.json only)",
        "untouched": ["sun_rule_only" if method_id != "sun_rule_only" else "",
                      "experiment_contract.json", "stage3 gate", "Gold",
                      "publication status"],
    }


def main() -> int:
    d1 = _package(
        "direct_llm",
        proposed_status="ready",
        rationale=("D1-R3 historical 150-row snapshot proven bound to formal "
                   "input v2 (IDs/text hashes/prompt/model/sampling/schema), "
                   "zero-API re-evaluation complete. Proposal only; a formal "
                   "D1 run would still need the user's LLM budget "
                   "authorization."),
        auth_sentence=(
            "I authorize promoting configs/methods.json direct_llm "
            "formal_status from blocked_until_official_data_output_contract_"
            "and_evaluator_are_locked to ready (command_status "
            "formal_ready_candidate_authorized), based on the zero-API "
            "binding evidence in b0_d1_formal_readiness_v2 and the D1/H1 "
            "comparison capsule, acknowledging that a formal D1 run then "
            "requires an explicit separate LLM budget authorization."),
        risk_note=("D1-R3 used the locked v6 prompt (3aa64877) and model "
                   "deepseek-v4-pro; official API transport without "
                   "json_object; a formal rerun should reuse the same recipe. "
                   "Candidate metrics are NOT formal results."),
        audit_change_note=("formal_methods_not_ready would drop direct_llm "
                           "(2 -> 1 non-ready method); final_experiment_ready "
                           "stays False while sun_llm_fallback is blocked; "
                           "methods_unexpectedly_ready must NOT trigger."),
        llm_calls_recorded=150,
    )
    h1 = _package(
        "sun_llm_fallback",
        proposed_status="comparison_only_ready",
        rationale=("H1 150-row snapshot (s28d_h1_150_v4pro_v1) proven bound "
                   "to formal input v2; zero-API re-evaluation complete. H1 "
                   "is DOWNGRADED to comparison-only (2026-08-08 decision); "
                   "the package documents the comparison-arm status change as "
                   "a proposal; no further optimization is intended."),
        auth_sentence=(
            "I authorize recording configs/methods.json sun_llm_fallback as "
            "comparison-only: formal_status "
            "blocked_until_faithful_baseline_data_and_triggers_are_locked -> "
            "comparison_only_ready (command_status "
            "formal_ready_candidate_authorized), based on the zero-API "
            "binding evidence; this does NOT authorize any further LLM "
            "optimization or a formal fallback run."),
        risk_note=("H1 was net-negative on the primary metric (coarse F1 "
                   "0.7621 vs B0 0.7986); trigger+repair recipe added false "
                   "positives. Comparison-only status prevents misuse."),
        audit_change_note=("formal_methods_not_ready would drop "
                           "sun_llm_fallback (2 -> 1 non-ready method); "
                           "final_experiment_ready stays False while "
                           "direct_llm is blocked."),
        llm_calls_recorded=150,
    )
    for mid, pkg in (("direct_llm", d1), ("sun_llm_fallback", h1)):
        jpath = OUT / f"{mid}_method_gate_decision_dry_run.json"
        data = (json.dumps(pkg, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if jpath.exists() and jpath.read_bytes() != data:
            raise RuntimeError(f"refusing to overwrite different content: {jpath}")
        jpath.write_bytes(data)
        md = [
            f"# {mid} method gate decision (DRY-RUN, not applied)",
            "",
            f"- status: dry_run_not_applied",
            f"- proposed formal_status: {pkg['methods_json_change']['after']['formal_status']}",
            f"- zero-API binding: {pkg['evidence']['zero_api_binding']}",
            f"- new LLM calls: {pkg['evidence']['new_llm_calls']}",
            "",
            "## Authorization sentence (copy-ready)",
            f"> {pkg['authorization_sentence']}",
            "",
            "## Expected audit changes",
            f"- {pkg['expected_audit_changes']}",
            "",
            "## Rollback",
            f"- {pkg['rollback']}",
            "",
        ]
        text = "\n".join(md)
        mpath = OUT / f"{mid}_method_gate_decision_dry_run.md"
        if mpath.exists() and mpath.read_text(encoding="utf-8") != text:
            raise RuntimeError(f"refusing to overwrite different content: {mpath}")
        mpath.write_text(text, encoding="utf-8")
        print(f"decision dry-run package written: {jpath.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
