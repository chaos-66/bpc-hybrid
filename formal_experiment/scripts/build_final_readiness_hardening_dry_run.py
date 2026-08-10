# -*- coding: utf-8 -*-
"""Build the final-readiness gate hardening dry-run package + the G0.4
formal main-view decision proposal (dry-run only, NOT applied).

Defects recorded in the CURRENT logic (reproduced in-memory, no file changed):

1. status.py sets final_experiment_ready=true from formal Gold +
   all-three-methods ready + input/Gold files existing -- it does NOT
   require the three-method formal predictions/results capsule to be
   complete and verified;
2. it does NOT require the G0.4 formal main-view contract to be
   user-authorized and publishable;
3. audit.py unconditionally raises methods_unexpectedly_ready whenever all
   three methods are ready -- with no way for an authorized, fully
   verified state to be recognized.

Proposed (NOT applied) fail-closed target semantics:

- method states must be in a user-approved formal terminal set;
- the three formal arm capsules (sun_rule_only / direct_llm /
  sun_llm_fallback) must each exist and pass their independent verifier;
- shared comparison capsule hashes (input/Gold/schema/normalization/
  evaluators) must all agree;
- the G0.4 formal main-view reporting contract must be user-approved;
- until these hold, final_experiment_ready MUST stay false;
- after user authorization AND real satisfaction of all conditions,
  methods_unexpectedly_ready must no longer fire;
- a config state flip alone must not open the final gate early.

The G0.4 decision proposal (task 4): the formal main report consists of the
sentence-level coarse five span-bearing fields PLUS the separate four-class
modality-label metrics; modality evidence-span metrics stay explicitly
unavailable (never zeroed, never aggregated); fine-grained five fields stay
diagnostic/对照; the historical six-field coarse aggregate remains
development provenance. This is a formal evaluation-contract decision that
requires user authorization before application; main_view_publishable is
NOT flipped by this package.
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

OUT_JSON = ROOT / "outputs" / "reports" / "final_readiness_hardening_dry_run.json"
OUT_MD = ROOT / "outputs" / "reports" / "final_readiness_hardening_dry_run.md"
G04_OUT_JSON = ROOT / "outputs" / "reports" / "g04_main_view_decision_dry_run.json"
G04_OUT_MD = ROOT / "outputs" / "reports" / "g04_main_view_decision_dry_run.md"


def _repro_scenarios() -> dict[str, Any]:
    """Run the in-memory reproduction of the current logic (no file change)."""
    from formal_experiment.paths import (
        EXPERIMENT_CONTRACT,
        FROZEN_GOLD_DIR,
        FROZEN_INPUT_DIR,
    )

    def meaningful_count(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(1 for item in path.rglob("*")
                   if item.is_file() and item.name != ".gitkeep")

    def simulate(methods_status: dict[str, str]) -> dict[str, Any]:
        contract = json.loads(EXPERIMENT_CONTRACT.read_text(encoding="utf-8"))
        gate = contract["formal_gold_publication_gate"]
        publication_ready = bool(
            contract["route"].get("status") == "locked"
            and contract["stage2_dataset"].get("status") == "locked_for_human_review"
            and contract["stage3"].get("status") == "locked"
            and gate.get("status") in gate.get("allowed_publication_statuses", []))
        frozen = {"input": meaningful_count(FROZEN_INPUT_DIR),
                  "gold": meaningful_count(FROZEN_GOLD_DIR)}
        blockers = [mid for mid, st in methods_status.items() if st != "ready"]
        return {
            "formal_gold_publication_ready": publication_ready,
            "frozen_counts": frozen,
            "method_blockers": blockers,
            "final_experiment_ready (current status.py)": bool(
                publication_ready and not blockers
                and frozen["input"] and frozen["gold"]),
            "methods_unexpectedly_ready error (current audit.py)": not blockers,
        }

    return {
        "D1_alone_ready": simulate({
            "sun_rule_only": "ready", "direct_llm": "ready",
            "sun_llm_fallback":
                "blocked_until_faithful_baseline_data_and_triggers_are_locked"}),
        "H1_comparison_only_ready_not_recognized": simulate({
            "sun_rule_only": "ready",
            "direct_llm":
                "blocked_until_official_data_output_contract_and_evaluator_are_locked",
            "sun_llm_fallback": "comparison_only_ready"}),
        "all_three_ready": simulate({
            "sun_rule_only": "ready", "direct_llm": "ready",
            "sun_llm_fallback": "ready"}),
    }


def build_hardening_package() -> dict[str, Any]:
    repro = _repro_scenarios()
    return {
        "schema_version": "final_readiness_gate_hardening_dry_run@1.0.0",
        "status": "dry_run_not_applied",
        "defects_recorded": [
            "status.py: final_experiment_ready computed from formal Gold + "
            "all-three-methods ready + input/Gold file counts; no requirement "
            "for the three-method formal predictions/results capsule to exist "
            "and pass independent verification",
            "status.py: no requirement that the G0.4 formal main-view "
            "reporting contract be user-authorized and publishable",
            "audit.py: methods_unexpectedly_ready error fires unconditionally "
            "whenever all three methods are ready; no recognized authorized "
            "terminal state exists",
        ],
        "minimal_reproduction": {
            "method": "in-memory simulation of the CURRENT status.py/audit.py "
                      "computation paths (contract + methods + frozen counts); "
                      "no file modified",
            "scenarios": repro,
            "key_finding": (
                "all_three_ready -> final_experiment_ready=true under the "
                "current status.py logic while the three-method capsule is "
                "absent, and audit.py simultaneously raises "
                "methods_unexpectedly_ready -- the config flip alone opens "
                "the final gate; H1 comparison_only_ready is NOT recognized "
                "as ready (blockers unchanged)"),
        },
        "proposed_fail_closed_target_semantics": [
            "method states must be in a user-approved formal terminal set",
            "the three formal arm capsules (sun_rule_only / direct_llm / "
            "sun_llm_fallback) must each exist AND pass their independent "
            "verifier",
            "shared comparison capsule hashes (input/Gold/schema/"
            "normalization/evaluators) must all agree",
            "the G0.4 formal main-view reporting contract must be "
            "user-authorized",
            "until all of the above hold, final_experiment_ready MUST stay "
            "false",
            "after user authorization AND real satisfaction of all "
            "conditions, methods_unexpectedly_ready must no longer fire",
            "a config status flip alone must not open the final gate early",
        ],
        "recommended_state_semantics": {
            "terminal_set": ["ready"],
            "comparison_only_arm": (
                "formal_status=ready + role='comparison_arm_only' + notes "
                "(uses the existing terminal set; no audit/status semantic "
                "drift)"),
            "final_gate": (
                "final_experiment_ready = publication_ready AND all three "
                "method statuses in the approved terminal set AND three "
                "capsules verified AND G0.4 contract authorized AND shared "
                "comparison capsule consistent"),
        },
        "required_changes": {
            "code": [
                "status.py: add capsule-completeness + G0.4-authorization "
                "terms to final_experiment_ready",
                "audit.py: replace the unconditional "
                "methods_unexpectedly_ready error with a guarded check that "
                "only fires when methods are ready WITHOUT the required "
                "capsule/contract authorization",
                "audit.py: add passes for 'three formal capsules verified' "
                "and 'G0.4 main-view contract authorized'",
            ],
            "tests": [
                "final gate stays false when only the B0 arm capsule exists",
                "final gate stays false when G0.4 contract not authorized",
                "methods_unexpectedly_ready does not fire in the authorized "
                "terminal state",
            ],
            "docs": [
                "PROJECT_AUDIT / MASTER_PIPELINE gate tables updated to the "
                "new semantics after implementation (not in this dry-run)",
            ],
        },
        "unified_authorization_sentence": (
            "I authorize the formal evaluation-contract and final-readiness "
            "decisions: (1) the G0.4 formal main report consists of the "
            "sentence-level coarse five span-bearing fields plus the separate "
            "four-class modality-label metrics, with modality evidence-span "
            "metrics explicitly unavailable (never zeroed, never aggregated), "
            "fine-grained five fields as diagnostic/对照, and the historical "
            "six-field coarse aggregate retained as development provenance "
            "only; (2) the direct_llm method gate may move to ready with the "
            "existing bound D1-R3 snapshot published formally zero-API as the "
            "default path (new LLM budget only if the binding breaks or I "
            "explicitly request a rerun); (3) the sun_llm_fallback method "
            "gate may move to ready with role/notes marking it "
            "comparison-only (existing bound snapshot published formally "
            "zero-API as the comparison arm); (4) the final-readiness gate is "
            "hardened fail-closed so final_experiment_ready requires the "
            "three verified formal capsules, a consistent shared comparison "
            "capsule and the authorized G0.4 contract, and "
            "methods_unexpectedly_ready no longer fires in that authorized "
            "state."),
        "not_applied": True,
        "untouched": ["methods.json", "experiment_contract.json", "stage3 gate",
                      "Gold", "publication status", "G0.4 main_view_publishable"],
    }


def build_g04_decision() -> dict[str, Any]:
    return {
        "schema_version": "g04_main_view_decision_dry_run@1.0.0",
        "status": "dry_run_not_applied",
        "proposal": {
            "formal_main_report": (
                "sentence-level coarse five span-bearing fields (actor/action/"
                "condition/constraint/exception) via the fixed Sun "
                "literal-overlap contract, PLUS the separate four-class "
                "modality-label metrics (accuracy + macro-F1)"),
            "modality_evidence_span_metrics": (
                "explicitly unavailable (published Gold modality is a plain "
                "string); never zeroed, never aggregated into any span "
                "aggregate"),
            "fine_grained_five_fields": "diagnostic / 对照 view only",
            "historical_six_field_coarse_aggregate": (
                "development provenance only; NOT formal (includes modality "
                "evidence-span numbers not reproducible from the published "
                "Gold)"),
            "no_gold_modification": True,
            "no_fabricated_modality_evidence_spans": True,
        },
        "authorization_required": (
            "this is a formal evaluation-contract decision; it is applied "
            "only after explicit user authorization. main_view_publishable "
            "is NOT flipped by this package."),
        "not_applied": True,
    }


def _write_no_overwrite(path: Path, payload: dict[str, Any]) -> None:
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists() and path.read_bytes() != data:
        raise RuntimeError(f"refusing to overwrite different content: {path}")
    path.write_bytes(data)


def main() -> int:
    hardening = build_hardening_package()
    _write_no_overwrite(OUT_JSON, hardening)
    g04 = build_g04_decision()
    _write_no_overwrite(G04_OUT_JSON, g04)

    md = [
        "# Final-readiness gate hardening (DRY-RUN, not applied)",
        "",
        f"- status: {hardening['status']}",
        "",
        "## Recorded defects",
    ]
    for d in hardening["defects_recorded"]:
        md.append(f"- {d}")
    md += ["", "## Minimal reproduction (in-memory, no file modified)"]
    for name, s in hardening["minimal_reproduction"]["scenarios"].items():
        md.append(f"- {name}: final_experiment_ready(current)="
                  f"{s['final_experiment_ready (current status.py)']}, "
                  f"methods_unexpectedly_ready(current)="
                  f"{s['methods_unexpectedly_ready error (current audit.py)']}")
    md.append(f"- key finding: {hardening['minimal_reproduction']['key_finding']}")
    md += ["", "## Proposed fail-closed target semantics"]
    for s in hardening["proposed_fail_closed_target_semantics"]:
        md.append(f"- {s}")
    md += ["", "## Required changes"]
    for kind, items in hardening["required_changes"].items():
        md.append(f"### {kind}")
        for item in items:
            md.append(f"- {item}")
    md += ["", "## Unified authorization sentence (copy-ready)", ""]
    md.append(f"> {hardening['unified_authorization_sentence']}")
    md += ["", "## G0.4 decision proposal",
           f"- {g04['proposal']['formal_main_report']}",
           f"- modality evidence-span: {g04['proposal']['modality_evidence_span_metrics']}",
           f"- fine-grained: {g04['proposal']['fine_grained_five_fields']}",
           f"- historical aggregate: {g04['proposal']['historical_six_field_coarse_aggregate']}",
           f"- {g04['authorization_required']}", ""]
    text = "\n".join(md)
    if OUT_MD.exists() and OUT_MD.read_text(encoding="utf-8") != text:
        raise RuntimeError(f"refusing to overwrite different content: {OUT_MD}")
    OUT_MD.write_text(text, encoding="utf-8")

    md2 = [
        "# G0.4 formal main-view decision (DRY-RUN, not applied)",
        "",
        f"- status: {g04['status']}",
        "",
        "## Proposal",
        f"- formal main report: {g04['proposal']['formal_main_report']}",
        f"- modality evidence-span: {g04['proposal']['modality_evidence_span_metrics']}",
        f"- fine-grained five fields: {g04['proposal']['fine_grained_five_fields']}",
        f"- historical six-field coarse aggregate: {g04['proposal']['historical_six_field_coarse_aggregate']}",
        "",
        "## Authorization required",
        f"- {g04['authorization_required']}",
        "",
    ]
    text2 = "\n".join(md2)
    if G04_OUT_MD.exists() and G04_OUT_MD.read_text(encoding="utf-8") != text2:
        raise RuntimeError(f"refusing to overwrite different content: {G04_OUT_MD}")
    G04_OUT_MD.write_text(text2, encoding="utf-8")
    print(f"hardening dry-run written: {OUT_JSON.relative_to(ROOT)}")
    print(f"g04 decision dry-run written: {G04_OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
