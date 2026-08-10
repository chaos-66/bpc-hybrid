# -*- coding: utf-8 -*-
"""D1/H1 method-gate decision DRY-RUN packages v2 (zero-API, NOT applied).

Corrections vs v1 (2026-08-11):

Direct-LLM (D1):
- keeps "candidate, not yet formally authorized";
- states explicitly that the historical 150-row snapshot IS bound to formal
  input v2;
- the DEFAULT path after user authorization of the method gate is a
  zero-API formal publication OF THAT SNAPSHOT (no new API call);
- a new LLM budget is only needed if the binding breaks or the user
  explicitly requests a rerun;
- the v1 statement that a formal run necessarily needs a new LLM budget is
  REMOVED.

Rules+LLM-Repair (H1):
- keeps comparison-only / stop optimizing;
- states that the historical snapshot can likewise be published formally
  (as the comparison arm) zero-API after authorization;
- `comparison_only_ready` is NOT recognized as ready by the current
  status/audit logic (status.py only recognizes "ready"; audit treats any
  formal_status != "ready" as non-ready), so it cannot be claimed that
  blockers decrease under that status;
- two reviewable options are listed with real impact:
    Option A (recommended): formal_status=ready + role/notes mark
        comparison-only (no audit/status semantics change needed);
    Option B: keep comparison_only_ready but then the formal terminal set
        and the audit/status semantics must be changed in sync.
- recommended option, exact before/after and the SIMULATED blocker state
  are given; nothing is applied.

The zero-API re-evaluation is evidence, NOT formal authorization.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

METHODS_CONFIG = ROOT / "configs" / "methods.json"
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


def _simulate_blockers(ready_methods: set[str]) -> dict[str, Any]:
    """Simulate formal_methods_not_ready under the CURRENT audit semantics
    (formal_status == 'ready' is the only recognized ready state)."""
    methods = _load_json(METHODS_CONFIG).get("methods", [])
    nonready = {m["id"]: m.get("formal_status") for m in methods
                if m.get("formal_status") != "ready"}
    for mid in ready_methods:
        nonready.pop(mid, None)
    return {
        "formal_methods_not_ready": {
            "present": bool(nonready),
            "non_ready_methods": nonready,
        },
        "methods_unexpectedly_ready": {"present": not nonready},
        "final_experiment_ready": False,
        "note": ("simulation under CURRENT audit/status semantics; "
                 "final_experiment_ready stays False because the formal "
                 "capsule/readiness hardening gates are not met"),
    }


def build_d1_package() -> dict[str, Any]:
    methods = _load_json(METHODS_CONFIG)
    before = next(m for m in methods.get("methods", [])
                  if m.get("id") == "direct_llm")
    after = dict(before)
    after["formal_status"] = "ready"
    after["command_status"] = "formal_ready_candidate_authorized"
    readiness = _load_json(READINESS).get("methods", {}).get("direct_llm", {})
    return {
        "schema_version": "method_gate_decision_dry_run@2.0.0",
        "method_id": "direct_llm",
        "status": "dry_run_not_applied",
        "purpose": (
            "D1 is a CANDIDATE, not yet formally authorized. The historical "
            "150-row snapshot (s27_d1_v6_r3_clean_rerun_150_hist56d_v1) IS "
            "bound to formal input v2 (IDs, per-row input text hashes, "
            "prompt/model/sampling locks, schema-validity all verified). "
            "After the user authorizes the method gate, the DEFAULT path is "
            "a zero-API formal publication OF THAT SNAPSHOT (same Gold views, "
            "same evaluators) -- NO new API call. A new LLM budget is only "
            "needed if the binding breaks or the user explicitly requests a "
            "rerun. The v1 claim that a formal run necessarily needs a new "
            "LLM budget was incorrect and is removed."),
        "methods_json_change": {
            "file": "configs/methods.json",
            "scope": "direct_llm only",
            "before": before,
            "after": after,
            "diff_fields": ["formal_status", "command_status"],
        },
        "zero_api_path": {
            "default_after_authorization": (
                "publish the existing bound snapshot zero-API (no new LLM "
                "budget required); new API budget ONLY if binding breaks or "
                "user explicitly requests a rerun"),
            "snapshot": "s27_d1_v6_r3_clean_rerun_150_hist56d_v1",
            "binding_ok": readiness.get("binding_ok"),
            "new_llm_calls_required_for_default_path": 0,
        },
        "evidence": {
            "comparison_capsule": "outputs/evidence/d1_h1_zero_api_reeval_v1/comparison_capsule.json",
            "fine_span_fields": _load_json(COMPARISON).get("methods", {}).get(
                "direct_llm", {}).get("fine_span_fields", {}),
            "coarse_span_fields": _load_json(COMPARISON).get("methods", {}).get(
                "direct_llm", {}).get("coarse_span_fields", {}),
        },
        "simulated_blockers_after_authorization": _simulate_blockers(
            {"direct_llm"}),
        "risks": (
            "formal publication of the D1-R3 snapshot reuses the locked v6 "
            "prompt (3aa64877) and deepseek-v4-pro recipe; the snapshot was "
            "produced on the official API without json_object. Candidate "
            "metrics are NOT formal until authorized."),
        "rollback": "git revert of the applied commit (methods.json only)",
        "untouched": ["sun_rule_only", "sun_llm_fallback",
                      "experiment_contract.json", "stage3 gate", "Gold",
                      "publication status"],
    }


def build_h1_package() -> dict[str, Any]:
    methods = _load_json(METHODS_CONFIG)
    before = next(m for m in methods.get("methods", [])
                  if m.get("id") == "sun_llm_fallback")
    readiness = _load_json(READINESS).get("methods", {}).get("sun_llm_fallback", {})

    option_a = dict(before)
    option_a["formal_status"] = "ready"
    option_a["command_status"] = "formal_ready_candidate_authorized"
    option_a["role"] = "comparison_arm_only"
    option_a["notes"] = (before.get("notes", "")
                         + " comparison-only per 2026-08-08 decision; "
                         "formal_status=ready records the authorized "
                         "comparison-arm status under the EXISTING terminal "
                         "set semantics.")

    option_b = dict(before)
    option_b["formal_status"] = "comparison_only_ready"
    option_b["command_status"] = "formal_ready_candidate_authorized"

    return {
        "schema_version": "method_gate_decision_dry_run@2.0.0",
        "method_id": "sun_llm_fallback",
        "status": "dry_run_not_applied",
        "purpose": (
            "H1 keeps comparison-only / stop optimizing (2026-08-08 user/"
            "supervisor decision). The historical 150-row snapshot "
            "(s28d_h1_150_v4pro_v1) IS bound to formal input v2 and can be "
            "published formally as the comparison arm ZERO-API after "
            "authorization (no new API call). IMPORTANT: the proposed v1 "
            "status 'comparison_only_ready' is NOT recognized as ready by the "
            "current status/audit logic (status.py recognizes only "
            "'formal_status == ready'; audit treats any other value as "
            "non-ready), so blockers would NOT decrease under it. Two "
            "reviewable options follow; nothing is applied."),
        "methods_json_change": {
            "file": "configs/methods.json",
            "scope": "sun_llm_fallback only",
            "before": before,
            "options": {
                "A_recommended_ready_plus_role": {
                    "after": option_a,
                    "diff_fields": ["formal_status", "command_status",
                                    "role", "notes"],
                    "audit_status_semantics_change_required": False,
                    "impact": (
                        "audit/status recognize formal_status=ready -> "
                        "formal_methods_not_ready drops sun_llm_fallback; "
                        "role/notes carry the comparison-only boundary"),
                    "simulated_blockers": _simulate_blockers(
                        {"sun_llm_fallback"}),
                },
                "B_keep_comparison_only_ready": {
                    "after": option_b,
                    "diff_fields": ["formal_status", "command_status"],
                    "audit_status_semantics_change_required": True,
                    "impact": (
                        "requires synchronized changes to the formal "
                        "terminal set and audit/status semantics "
                        "(status.py/audit.py + tests + docs) before any "
                        "blocker effect; NOT recognized as ready today"),
                    "simulated_blockers": _simulate_blockers(set()),
                },
            },
            "recommended": (
                "Option A: formal_status=ready with role='comparison_arm_only' "
                "and notes marking comparison-only -- uses the EXISTING "
                "terminal-set semantics and lets audit/status evaluate the "
                "arm correctly without semantic drift"),
        },
        "zero_api_path": {
            "default_after_authorization": (
                "publish the existing bound snapshot zero-API as the formal "
                "comparison arm (no new LLM budget); new API budget only if "
                "binding breaks or user explicitly requests a rerun"),
            "snapshot": "s28d_h1_150_v4pro_v1",
            "binding_ok": readiness.get("binding_ok"),
            "new_llm_calls_required_for_default_path": 0,
        },
        "evidence": {
            "comparison_capsule": "outputs/evidence/d1_h1_zero_api_reeval_v1/comparison_capsule.json",
            "fine_span_fields": _load_json(COMPARISON).get("methods", {}).get(
                "sun_llm_fallback", {}).get("fine_span_fields", {}),
            "coarse_span_fields": _load_json(COMPARISON).get("methods", {}).get(
                "sun_llm_fallback", {}).get("coarse_span_fields", {}),
        },
        "risks": (
            "H1 was net-negative (coarse F1 0.7621 vs B0 0.7986); the "
            "comparison-only boundary prevents further optimization or "
            "misuse; Option B without the audit/status sync would keep the "
            "method blocked with no visible effect."),
        "rollback": "git revert of the applied commit (methods.json only)",
        "untouched": ["sun_rule_only", "direct_llm",
                      "experiment_contract.json", "stage3 gate", "Gold",
                      "publication status"],
    }


def main() -> int:
    packages = {"direct_llm": build_d1_package(),
                "sun_llm_fallback": build_h1_package()}
    for mid, pkg in packages.items():
        jpath = OUT / f"{mid}_method_gate_decision_dry_run_v2.json"
        data = (json.dumps(pkg, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if jpath.exists() and jpath.read_bytes() != data:
            raise RuntimeError(f"refusing to overwrite different content: {jpath}")
        jpath.write_bytes(data)
        md = [
            f"# {mid} method gate decision v2 (DRY-RUN, not applied)",
            "",
            f"- status: dry_run_not_applied",
            f"- zero-API default path after authorization: no new LLM budget",
            f"- binding_ok: {pkg['zero_api_path']['binding_ok']}",
            "",
            "## Purpose",
            f"- {pkg['purpose']}",
            "",
            "## Zero-API path",
            f"- {pkg['zero_api_path']['default_after_authorization']}",
            f"- new LLM calls required for default path: {pkg['zero_api_path']['new_llm_calls_required_for_default_path']}",
            "",
        ]
        if mid == "direct_llm":
            md.append("## Proposed change")
            md.append(f"- before: {pkg['methods_json_change']['before']['formal_status']}")
            md.append(f"- after: {pkg['methods_json_change']['after']['formal_status']} / "
                      f"{pkg['methods_json_change']['after']['command_status']}")
            md.append(f"- simulated blockers: {pkg['simulated_blockers_after_authorization']}")
        else:
            md.append("## Options (H1)")
            opts = pkg["methods_json_change"]["options"]
            md.append(f"- Option A (recommended): ready + role/notes comparison-only; "
                      f"simulated blockers: {opts['A_recommended_ready_plus_role']['simulated_blockers']}")
            md.append(f"- Option B: keep comparison_only_ready; requires audit/status semantics sync; "
                      f"simulated blockers (no sync): {opts['B_keep_comparison_only_ready']['simulated_blockers']}")
            md.append(f"- recommended: {pkg['methods_json_change']['recommended']}")
        md += [
            "",
            "## Risks",
            f"- {pkg['risks']}",
            "",
            "## Rollback",
            f"- {pkg['rollback']}",
            "",
        ]
        text = "\n".join(md)
        mpath = OUT / f"{mid}_method_gate_decision_dry_run_v2.md"
        if mpath.exists() and mpath.read_text(encoding="utf-8") != text:
            raise RuntimeError(f"refusing to overwrite different content: {mpath}")
        mpath.write_text(text, encoding="utf-8")
        print(f"decision dry-run v2 package written: {jpath.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
