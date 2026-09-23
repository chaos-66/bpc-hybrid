# -*- coding: utf-8 -*-
"""Render the Stage-3 repair summary from frozen JSON reports."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/reports/stage3_binding_repair_summary_v1.md"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build() -> str:
    audit = _load(ROOT / "data/development/stage3_synth/stage3_binding_audit_v1.json")
    ref = _load(ROOT / "data/development/stage3_synth/stage3_binding_reference_v1.json")
    elig = _load(ROOT / "data/development/stage3_synth/stage3_paired_benchmark_eligibility_v1.json")
    ag = _load(ROOT / "outputs/reports/stage3_automatic_grounding_evaluation_v1.json")
    ours = _load(ROOT / "outputs/reports/stage3_ours_v1_evaluation.json")
    table = _load(ROOT / "outputs/reports/stage3_table3_v1.json")
    lines = [
        "# Stage 3 binding / automatic grounding / Table 3 repair summary",
        "",
        "## Binding audit (30 pairs)",
        "",
        f"- audit classes: {audit['summary']}",
        f"- action human fields: {ref['counts'].get('action_binding:human')}",
        f"- action AI-unresolved fields: {ref['counts'].get('action_binding:ai_proposed_unresolved')}",
        f"- actor human fields: {ref['counts'].get('actor_binding:human')}",
        f"- actor AI-proposal fields: {ref['counts'].get('actor_binding:ai_proposal')}",
        f"- actor unresolved fields: {ref['counts'].get('actor_binding:ai_proposed_unresolved')}",
        f"- order human/not-applicable fields: {ref['counts'].get('order_binding:human')}",
        f"- order AI-ineligible fields: {ref['counts'].get('order_binding:ai_assessment')}",
        f"- required-field human-approved pairs: {ref['counts'].get('review_state:human_approved')}",
        "- pairs needing final human approval: 19 (packet-level; required-field review_state count is 17)",
        "- human approval packet: `outputs/reports/stage3_binding_final_human_approval_packet_v1.md`",
        "",
        "## Benchmark eligibility",
        "",
        f"- missing_action eligible pairs: {len(elig['eligible_pairs_by_type']['missing_action'])}",
        f"- incorrect_actor eligible pairs: {len(elig['eligible_pairs_by_type']['incorrect_actor'])}",
        f"- out_of_order eligible pairs: {len(elig['eligible_pairs_by_type']['out_of_order'])}",
        "",
        "## Automatic grounding (evaluated after prediction persistence)",
        "",
        f"- action any-action top1 accuracy: {ag['action_grounding']['any_action_top1_accuracy']:.4f}",
        f"- action candidate-set recall: {ag['action_grounding']['candidate_set_recall']:.4f}",
        f"- action strong-set recall: {ag['action_grounding']['strong_set_recall']:.4f}",
        f"- action coverage: {ag['action_grounding']['coverage']:.4f}",
        f"- lane coverage: {ag['actor_lane_grounding']['lane_coverage']:.4f}",
        f"- lane exact accuracy: {ag['actor_lane_grounding']['lane_exact_accuracy_on_expected_lanes']:.4f}",
        f"- rule-order reference available: {ag['order_grounding']['rule_order_reference_available']}",
        "",
        "## Ours (eligible subset only)",
        "",
        f"- eligible items: {ours['overall_eligible']['items']}",
        f"- macro-F1: {ours['overall_eligible']['macro_f1']}",
        f"- micro-F1: {ours['overall_eligible']['micro_f1']['f1']}",
        f"- compliant specificity: {ours['overall_eligible']['compliant_specificity']}",
        f"- exact type accuracy: {ours['overall_eligible']['variant_exact_type_accuracy']}",
        "",
        "## Table 3",
        "",
        "See `outputs/reports/stage3_table3_v1.md` for the full table.",
        f"- Ours macro-F1: {table['methods']['ours']['macro_f1_eligible_types']}",
        f"- Sun macro-F1: {table['methods']['sun_reconstruction']['macro_f1_eligible_types']}",
        f"- Winter macro-F1: {table['methods']['winter_wrapper']['macro_f1_eligible_types']}",
        f"- Oracle/Grounded upper bound macro-F1: {table['methods']['oracle_grounded_upper_bound']['macro_f1_eligible_types']}",
        "",
        "## Claim boundary",
        "",
        "- Ours inference never reads Binding Reference or benchmark mutation answers; it uses a gold-blind inference view and persisted automatic grounding predictions.",
        "- Oracle/Grounded upper bound uses supplied bindings and is reported separately, never as Ours.",
        "- out_of_order is N/A because no eligible rule-side order relation exists; process-only mutations are not formal Gold.",
        "- Full three-type formal Table 3 still requires human approval of 19 unresolved pairs.",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return "\n".join(lines)


def main() -> int:
    print(build())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
