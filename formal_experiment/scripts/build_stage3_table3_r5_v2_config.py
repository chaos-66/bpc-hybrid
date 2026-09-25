"""Generate the S3-TABLE3-R5.1 corrected benchmark config (v2) and disposition.

This is an offline, deterministic transformation of the preserved R5 v1 config.
It does not read predictions, Gold, or call any API.  Each of the 36 v1
requirements gets an explicit per-violation-type eligibility decision with a
legal/semantic basis, a problem category, a disposition, and the concrete fixes
applied.  `has_variants` (all-or-nothing) is replaced by
eligible_missing_action / eligible_incorrect_actor / eligible_out_of_order.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V1_CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v1.json"
V2_CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v2.json"
V2_DATA = ROOT / "data/development/stage3_table3_r5_benchmark_v2"
REPORTS = ROOT / "outputs/reports"
BENCHMARK_ID_V1 = "stage3_table3_r5_benchmark_v1"
BENCHMARK_ID_V2 = "stage3_table3_r5_benchmark_v2"


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def ws(value: str) -> str:
    return " ".join(value.split())


# ---------------------------------------------------------------------------
# Per-requirement decisions.
#
# eligible_* : whether the frozen three-class scorer may generate a scored
#              variant of that type for this requirement.
# basis_*    : the semantic/legal reason (must exist before a variant exists).
# disposition: "core" -> in frozen three-class scoring; else candidate asset.
# issues     : problem categories found during the review.
# fixes      : concrete corrections applied in v2.
# ---------------------------------------------------------------------------
DECISIONS: dict[str, dict] = {
    # R5-D-01..05: the R1-R4 five historical development rules.  All three
    # types have direct textual support (strict "prior to"/"before" edges).
    "R5-D-01": {
        "ma": True, "ia": True, "oo": True, "disposition": "core",
        "basis_ma": "13(3) imposes a positive duty to provide the other-purpose information.",
        "basis_ia": "The duty is on the controller; the data subject is not the actor.",
        "basis_oo": "Explicit strict order: provide information 'prior to that further processing'.",
        "issues": [],
        "fixes": ["condition_present corrected to True (intends further processing for another purpose)."],
    },
    "R5-D-02": {
        "ma": True, "ia": True, "oo": True, "disposition": "core",
        "basis_ma": "14(4) imposes a positive duty to provide the other-purpose information.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "Explicit strict order: provide information 'prior to that further processing'.",
        "issues": [],
        "fixes": ["condition_present corrected to True (intends further processing for another purpose)."],
    },
    "R5-D-03": {
        "ma": True, "ia": True, "oo": True, "disposition": "core",
        "basis_ma": "18(3) imposes a positive duty to inform before lifting a restriction.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "Explicit strict order: inform 'before the restriction of processing is lifted'.",
        "issues": [],
        "fixes": ["condition_present corrected to True (restriction obtained under paragraph 1)."],
    },
    "R5-D-04": {
        "ma": True, "ia": True, "oo": True, "disposition": "core",
        "basis_ma": "35(1) imposes a positive duty to carry out a DPIA.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "Explicit strict order: carry out the assessment 'prior to the processing'.",
        "issues": [],
        "fixes": [],
    },
    "R5-D-05": {
        "ma": True, "ia": True, "oo": True, "disposition": "core",
        "basis_ma": "36(1) imposes a positive duty to consult the supervisory authority.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "Explicit strict order: consult 'prior to processing'.",
        "issues": [],
        "fixes": [],
    },
    # R5-D-06..12: historical GDPR7 development rules.
    "R5-D-06": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "7(1) imposes a positive duty to be able to demonstrate consent.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "No explicit order between two required activities; 'demonstrate that ... has consented' is an evidentiary state, not a strict order rule.",
        "issues": ["order_evidence_text_is_not_order_rule"],
        "fixes": ["out_of_order marked ineligible", "condition_present corrected to True (processing based on consent)."],
    },
    "R5-D-07": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "7(4) requires utmost account to be taken when assessing free consent.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "'When assessing whether consent is freely given' is a simultaneity/condition, not an order between two required activities.",
        "issues": ["simultaneity_not_order"],
        "fixes": ["out_of_order marked ineligible"],
    },
    "R5-D-08": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "15(1) right to obtain confirmation and access implies a positive controller duty to provide it.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "The recital is a right to obtain, not an explicit two-activity strict-order rule.",
        "issues": ["right_not_order_rule"],
        "fixes": ["out_of_order marked ineligible"],
    },
    "R5-D-09": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "16 right to rectification implies a positive controller duty to rectify.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "'without undue delay' is a deadline with no explicit trigger phrase; this round does not assert deadline satisfaction or an invented trigger order.",
        "issues": ["deadline_without_explicit_trigger"],
        "fixes": ["out_of_order marked ineligible"],
    },
    "R5-D-10": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "17(1) imposes a positive duty to erase where a ground applies.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "'without undue delay' is a deadline with no explicit trigger phrase; no strict order asserted.",
        "issues": ["deadline_without_explicit_trigger"],
        "fixes": ["out_of_order marked ineligible", "condition_present corrected to True (one of the 17(1) grounds applies)."],
    },
    "R5-D-11": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "20(1) right to receive/transmit implies a positive controller duty to provide portability.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "The excerpt lists two rights; it does not state a strict order between two required activities.",
        "issues": ["right_not_order_rule"],
        "fixes": ["out_of_order marked ineligible"],
    },
    "R5-D-12": {
        "ma": True, "ia": True, "oo": True, "disposition": "core",
        "basis_ma": "33(1) imposes a positive duty to notify the supervisory authority.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "Explicit trigger + subsequent act: notify 'after having become aware' (deadline is not asserted as satisfied, only trigger order).",
        "issues": ["condition_text_confused_with_exception"],
        "fixes": ["condition_text corrected to 'a personal data breach occurs' (exception kept separate in 33(1) 'unless ... unlikely to result in a risk')."],
    },
    # ---- test core requirements ----
    "R5-S1-T1": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "13(1) imposes a positive duty to provide the listed information.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "'at the time when personal data are obtained' is simultaneity, not a strict collect-then-inform order (A1).",
        "issues": ["simultaneity_misread_as_order", "missing_condition_flag"],
        "fixes": ["out_of_order marked ineligible (A1)", "condition_present corrected to True (direct collection from the data subject)."],
    },
    "R5-S1-T2": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "13(2) imposes a positive duty to provide the further fairness/transparency information.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "'at the time when personal data are obtained' is simultaneity, not a strict order (A1).",
        "issues": ["simultaneity_misread_as_order", "missing_condition_flag"],
        "fixes": ["out_of_order marked ineligible (A1)", "condition_present corrected to True (paragraph 1 information obligation applies)."],
    },
    "R5-S1-T3": {
        "ma": True, "ia": True, "oo": True, "disposition": "core",
        "basis_ma": "14(1) imposes a positive duty to provide the listed information.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "Explicit trigger + subsequent act: provide 'within a reasonable period after obtaining' (only trigger order evaluated).",
        "issues": ["missing_condition_flag"],
        "fixes": ["condition_present corrected to True (personal data not obtained from the data subject)."],
    },
    "R5-S1-T4": {
        "ma": True, "ia": True, "oo": True, "disposition": "core",
        "basis_ma": "14(2) imposes a positive duty to provide the further information.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "Explicit trigger + subsequent act: provide after obtaining under 14(3) timing (only trigger order evaluated).",
        "issues": ["missing_condition_flag"],
        "fixes": ["condition_present corrected to True (paragraph 1 indirect-collection obligation applies)."],
    },
    "R5-S2-T1": {
        "ma": False, "ia": False, "oo": False, "disposition": "candidate_semantic",
        "basis_ma": "8(1) states a lawfulness/permission condition, not a positive duty; absence of a named activity is not itself a violation (permission template rule).",
        "basis_ia": "The provision conditions lawfulness on consent/authorisation rather than assigning the duty to a fallible actor-surface obligation.",
        "basis_oo": "No explicit strict order between two required activities.",
        "issues": ["permission_modelled_as_positive_duty"],
        "fixes": ["moved out of the frozen three-class core scoring; kept as semantic/candidate asset (no permission decision formula added)."],
    },
    "R5-S2-T2": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "8(2) imposes a positive duty to make reasonable efforts to verify parental authorisation.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "'in such cases' is a condition, not an order between activities.",
        "issues": [],
        "fixes": [],
    },
    "R5-S2-T3": {
        "ma": False, "ia": False, "oo": False, "disposition": "candidate_semantic",
        "basis_ma": "9(2)(a) is a permission (derogation from the 9(1) prohibition); absence of a named activity is not itself a violation.",
        "basis_ia": "The provision conditions lawfulness on explicit consent; it is not a per-actor positive duty.",
        "basis_oo": "No explicit strict order between two required activities.",
        "issues": ["permission_modelled_as_positive_duty", "condition_and_negated_condition_confused_with_exception"],
        "fixes": ["moved out of core scoring (A4); kept as semantic/candidate asset; condition and legal basis documented."],
    },
    "R5-S2-T4": {
        "ma": False, "ia": False, "oo": False, "disposition": "candidate_semantic",
        "basis_ma": "9(2)(b) is a permission (derogation); absence of a named activity is not itself a violation.",
        "basis_ia": "The provision conditions lawfulness on a legal basis/safeguards; it is not a per-actor positive duty.",
        "basis_oo": "No explicit strict order between two required activities.",
        "issues": ["permission_modelled_as_positive_duty", "negated_condition_misstated_as_exception"],
        "fixes": ["moved out of core scoring (A4); kept as semantic/candidate asset."],
    },
    "R5-S3-T1": {
        "ma": True, "ia": True, "oo": True, "disposition": "core",
        "basis_ma": "12(3) imposes a positive duty to provide information on action taken.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "Explicit trigger + subsequent act: provide 'within one month of receipt of the request' (only trigger order evaluated).",
        "issues": ["missing_condition_flag"],
        "fixes": ["condition_present corrected to True (a request under Articles 15-22 is received)."],
    },
    "R5-S3-T2": {
        "ma": True, "ia": True, "oo": True, "disposition": "core",
        "basis_ma": "12(4) imposes a positive duty to inform about reasons for not taking action.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "Explicit trigger + subsequent act: inform 'within one month of receipt of the request' (only trigger order evaluated).",
        "issues": ["missing_condition_flag"],
        "fixes": ["condition_present corrected to True (controller does not take action on the request)."],
    },
    "R5-S3-T3": {
        "ma": False, "ia": False, "oo": False, "disposition": "candidate_semantic",
        "basis_ma": "21(1) is a cessation/prohibition of further processing, not a positive duty; a 'Stop' task cannot prove that prohibited processing happened.",
        "basis_ia": "No per-actor positive duty; the provision constrains continued processing.",
        "basis_oo": "'shall no longer process unless' is a prohibition/condition, not an order between two required activities.",
        "issues": ["prohibition_cessation_modelled_as_missing_action", "invented_stop_task"],
        "fixes": ["moved out of core scoring (A5); Stop task removed from core; kept as semantic/candidate asset with source."],
    },
    "R5-S3-T4": {
        "ma": False, "ia": False, "oo": False, "disposition": "candidate_semantic",
        "basis_ma": "21(3) is a cessation/prohibition, not a positive duty; a 'Cease' task cannot prove prohibited processing.",
        "basis_ia": "No per-actor positive duty.",
        "basis_oo": "'shall no longer be processed' is a prohibition, not an order between two required activities.",
        "issues": ["prohibition_cessation_modelled_as_missing_action", "invented_cease_task"],
        "fixes": ["moved out of core scoring (A5); Cease task removed from core; kept as semantic/candidate asset with source."],
    },
    "R5-S4-T1": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "24(1) imposes a positive duty to implement appropriate measures.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "'Those measures shall be reviewed and updated where necessary' describes a lifecycle, not an explicit strict order between two required activities.",
        "issues": ["lifecycle_not_strict_order"],
        "fixes": ["out_of_order marked ineligible"],
    },
    "R5-S4-T2": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "25(1) imposes a positive duty to implement data-protection-by-design measures.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "'both at the time of the determination ... and at the time of the processing itself' is simultaneity, not an order.",
        "issues": ["simultaneity_not_order"],
        "fixes": ["out_of_order marked ineligible"],
    },
    "R5-S4-T3": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "28(3)(a) stipulates a positive duty: process only on documented instructions.",
        "basis_ia": "The duty is on the processor.",
        "basis_oo": "'only on documented instructions' is a condition/precondition, not a strict order between two required activities; 'before processing' belongs to the legal-requirement exception, not the main duty.",
        "issues": ["excerpt_includes_subsequent_subparagraphs", "condition_precondition_misread_as_order", "processed_source_not_flagged"],
        "fixes": ["excerpt narrowed to the 28(3)(a) sentence only (A6); precise char span recorded; processed-source status flagged; out_of_order marked ineligible."],
    },
    "R5-S4-T4": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "19 imposes a positive duty to communicate changes to recipients.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "Communicating a change already carried out is not a strict order between two required activities.",
        "issues": ["missing_condition_flag"],
        "fixes": ["condition_present corrected to True (a rectification/erasure/restriction was carried out)."],
    },
    "R5-S5-T1": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "35(2) imposes a positive duty to seek the DPO advice.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "'when carrying out a DPIA' is simultaneity/condition, not an order.",
        "issues": ["simultaneity_not_order"],
        "fixes": ["out_of_order marked ineligible"],
    },
    "R5-S5-T2": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "35(9) imposes a positive duty to seek the views of data subjects.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "'on the intended processing' implies a preference, not an explicit strict order between two required activities.",
        "issues": ["implicit_preference_not_strict_order"],
        "fixes": ["out_of_order marked ineligible"],
    },
    "R5-S5-T3": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "35(11) imposes a positive duty to carry out a review.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "'at least when there is a change of the risk' is a trigger/condition, not an order between two required activities.",
        "issues": ["condition_not_order"],
        "fixes": ["out_of_order marked ineligible"],
    },
    "R5-S5-T4": {
        "ma": True, "ia": True, "oo": True, "disposition": "core",
        "basis_ma": "36(2) imposes a positive duty on the supervisory authority to provide written advice.",
        "basis_ia": "The duty is on the supervisory authority; the controller is not the actor.",
        "basis_oo": "Explicit trigger + subsequent act: advice 'within period of up to eight weeks of receipt of the request' (only trigger order evaluated).",
        "issues": ["missing_condition_flag"],
        "fixes": ["condition_present corrected to True (supervisory authority is of the opinion that the intended processing would infringe)."],
    },
    "R5-S6-T1": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "32(1) imposes a positive duty to implement appropriate security measures.",
        "basis_ia": "The duty is on the controller and processor.",
        "basis_oo": "'to ensure a level of security appropriate to the risk' is a risk-appropriateness standard, not a strict order between two activities (A2).",
        "issues": ["risk_appropriateness_misread_as_order"],
        "fixes": ["out_of_order marked ineligible (A2)"],
    },
    "R5-S6-T2": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "32(4) imposes a positive duty to take steps ensuring instruction-only processing.",
        "basis_ia": "The duty is on the controller and processor.",
        "basis_oo": "'does not process them except on instructions' is a prohibition/condition, not an order.",
        "issues": ["prohibition_not_order"],
        "fixes": ["out_of_order marked ineligible"],
    },
    "R5-S6-T3": {
        "ma": True, "ia": True, "oo": True, "disposition": "core",
        "basis_ma": "33(2) imposes a positive duty on the processor to notify the controller.",
        "basis_ia": "The duty is on the processor; the data subject is not the actor.",
        "basis_oo": "Explicit trigger + subsequent act: notify 'after becoming aware of a personal data breach' (only trigger order evaluated).",
        "issues": ["missing_condition_flag"],
        "fixes": ["condition_present corrected to True (becomes aware of a personal data breach)."],
    },
    "R5-S6-T4": {
        "ma": True, "ia": True, "oo": False, "disposition": "core",
        "basis_ma": "34(1) imposes a positive duty to communicate a high-risk breach to the data subject.",
        "basis_ia": "The duty is on the controller.",
        "basis_oo": "'without undue delay' has no explicit trigger phrase and the added 'assess high risk' task is not a source activity; no order asserted (A3).",
        "issues": ["undue_delay_misread_as_assessment_order", "invented_assessment_task"],
        "fixes": ["out_of_order marked ineligible (A3)"],
    },
}


# Condition/exception text corrections (v2).  `None` means "leave v1 value".
# For conditions the value is (present, text); for exceptions (present, text,
# evidence_scope, cross_reference_text).  Cross-reference text is filled from the
# local processed source where the exception lives in another paragraph.
CONDITION_FIX = {
    "R5-D-01": (True, "the controller intends to further process for a purpose other than that for which the data were collected"),
    "R5-D-02": (True, "the controller intends to further process for a purpose other than that for which the data were obtained"),
    "R5-D-03": (True, "the data subject has obtained restriction of processing pursuant to Article 18(1)"),
    "R5-D-06": (True, "processing is based on consent"),
    "R5-D-08": (True, "personal data concerning the data subject are being processed"),
    "R5-D-10": (True, "one of the Article 17(1) erasure grounds applies"),
    "R5-D-12": (True, "a personal data breach occurs"),
    "R5-S1-T1": (True, "personal data relating to a data subject are collected from the data subject"),
    "R5-S1-T2": (True, "the paragraph 1 information obligation applies to the direct collection"),
    "R5-S1-T3": (True, "personal data have not been obtained from the data subject"),
    "R5-S1-T4": (True, "the paragraph 1 information obligation applies to the indirect collection"),
    "R5-S3-T1": (True, "a request under Articles 15 to 22 is received"),
    "R5-S3-T2": (True, "the controller does not take action on the request of the data subject"),
    "R5-S4-T4": (True, "a rectification, erasure or restriction of processing has been carried out under Articles 16, 17(1) or 18"),
    "R5-S6-T3": (True, "the processor becomes aware of a personal data breach"),
    "R5-S5-T4": (True, "the supervisory authority is of the opinion that the intended processing would infringe the Regulation or the risk is insufficiently mitigated"),
}


def build_v2_config() -> dict:
    v1 = load_json(V1_CONFIG)
    v2 = json.loads(json.dumps(v1))  # deep copy
    v2["schema_version"] = "stage3_table3_r5_benchmark_config@2.0.0"
    v2["benchmark_id"] = BENCHMARK_ID_V2
    v2["task_id"] = "S3-TABLE3-R5.1-TARGETED-BENCHMARK-CORRECTION"
    v2["status"] = "construction_reference_not_formal_gold_v2"
    v2["supersedes"] = BENCHMARK_ID_V1
    v2["preserved_from"] = {"benchmark_id": BENCHMARK_ID_V1, "config_path": "configs/stage3_table3_r5_benchmark_v1.json"}
    v2["eligibility_model"] = {
        "description": "Per-type eligibility replaces the all-or-nothing has_variants flag. A variant may only be generated when the type has an explicit legal/semantic basis in the current source.",
        "types": ["missing_action", "incorrect_actor", "out_of_order"],
        "candidate_requirements": "requirements with no eligible core type are kept as semantic/candidate assets, not scored in the frozen three-class F1",
    }
    v2["split_seed"] = v1["split_seed"]
    v2["split_algorithm"] = (
        "source_family (same Article) -> single split; R1-R4 five historical rules "
        "and any exposed family stay development; no family crosses split; seed used only for deterministic ordering"
    )
    v2.pop("target_counts", None)
    v2["target_counts"] = {
        "note": "targets are informational only; real counts are reported and gaps stated (no forced 12/24 or 108)",
        "independent_requirements_v1": 36,
    }

    for spec in v2["requirements"]:
        rid = spec["requirement_id"]
        dec = DECISIONS[rid]
        spec["eligible_missing_action"] = bool(dec["ma"])
        spec["eligible_incorrect_actor"] = bool(dec["ia"])
        spec["eligible_out_of_order"] = bool(dec["oo"])
        spec["eligibility_basis"] = {
            "missing_action": dec["basis_ma"],
            "incorrect_actor": dec["basis_ia"],
            "out_of_order": dec["basis_oo"],
        }
        spec["disposition"] = dec["disposition"]
        spec["review_issues"] = dec["issues"]
        spec["review_fixes"] = dec["fixes"]
        spec["core_eligible"] = any((dec["ma"], dec["ia"], dec["oo"]))
        # v1 all-or-nothing flag is preserved as an explicitly legacy field.
        spec["has_variants_v1_legacy"] = spec.pop("has_variants", False)
        spec["source_family_id"] = f"gdpr_art{spec['article']}"
        # Condition fix
        if rid in CONDITION_FIX:
            present, text = CONDITION_FIX[rid]
            spec["condition_present"] = present
            spec["condition_text"] = text
            spec["condition_fix_basis"] = "v1 condition_present was false although the excerpt contains an applicability clause; corrected in v2."
        if rid == "R5-D-11":
            spec["exception_text"] = (
                "The right referred to in paragraph 1 shall not adversely affect the rights and freedoms of others."
            )
            spec["exception_fix_basis"] = (
                "Corrected from the unsupported 'Article 20(4) public-interest or official-authority exception' "
                "to the actual Article 20(4) source text in the local processed snapshot."
            )
        # Exception: never let a negated condition masquerade as an independent exception.
        if rid in ("R5-S2-T1", "R5-S2-T4"):
            spec["exception_present"] = False
            spec["exception_text"] = ""
            spec["exception_fix_basis"] = (
                "v1 exception was the mere negation of the condition ('child at least 16' negates "
                "'child below 16'; 'no authorising law' negates the legal basis); removed as an "
                "independent exception per the condition-vs-exception separation rule."
            )

    # A6: precise narrow excerpt for R5-S4-T3 (28(3)(a) only).
    for spec in v2["requirements"]:
        if spec["requirement_id"] == "R5-S4-T3":
            spec["excerpt_mode"] = "char_span"
            spec["excerpt_char_span_text"] = (
                "the processor processes the personal data only on documented instructions from the controller, "
                "including with regard to transfers of personal data to a third country or an international organisation, "
                "unless required to do so by Union or Member State law to which the processor is subject; "
                "in such a case, the processor shall inform the controller of that legal requirement before processing, "
                "unless that law prohibits such information on important grounds of public interest"
            )
            spec["excerpt_source_status"] = (
                "processed_local_winter_snapshot_not_official_verbatim: references/winter_2020_model_check/.../article28.txt "
                "has been whitespace-normalised and split into separate enumerated items; the excerpt is a contiguous "
                "substring of that processed file, not a claim of official OJ byte identity."
            )

    # Bounded source-only order-closure additions (2026-09-26, zero API,
    # prediction-blind).  Two unexposed Article families with explicit
    # action-precedence source text are added as test requirements; the
    # bounded search stops at two additional independent families.
    v2["requirements"].extend([
        {
            "actor_required": "Supervisory authority",
            "actor_wrong": "Board",
            "article": 40,
            "business_scenario_en": "A multi-State draft code of conduct must be submitted to the Board before it is approved.",
            "business_scenario_zh": "涉及多个成员国的行为准则草案须在批准前提交给欧盟数据保护委员会。",
            "citation": "GDPR Article 40(7)",
            "condition_present": True,
            "condition_text": "a draft code of conduct relates to processing activities in several Member States",
            "constraint_present": True,
            "constraint_text": "before approving the draft code, amendment or extension",
            "core_eligible": True,
            "disposition": "core",
            "eligibility_basis": {
                "incorrect_actor": "The duty is on the competent supervisory authority, not on the Board.",
                "missing_action": "Article 40(7) imposes a positive duty to submit the multi-State draft to the Board.",
                "out_of_order": "Explicit action precedence: submit the draft 'before approving' it.",
            },
            "eligible_incorrect_actor": True,
            "eligible_missing_action": True,
            "eligible_out_of_order": True,
            "exception_present": False,
            "exception_text": "",
            "excerpt_mode": "sentence",
            "exposure_status": "no_prior_exposure_found",
            "has_variants_v1_legacy": False,
            "historical_development": False,
            "mandatory_index": 1,
            "modality": "obligation",
            "normative_content": "Competent supervisory authority must submit a multi-State draft code to the Board before approving it.",
            "order_evidence": "before approving the draft code, amendment or extension",
            "order_pair": [1, 2],
            "paragraph": "7",
            "r4_rule_id": None,
            "requirement_id": "R5-S7-T1",
            "review_fixes": ["added_by_bounded_source_only_order_closure"],
            "review_issues": [],
            "sample_id": None,
            "scenario_id": "S7",
            "scenario_zh": "行为准则审批程序",
            "source_family_id": "gdpr_art40",
            "source_family_split_basis": "same-Article family has no prior exposure and is held out as independent test",
            "source_kind": "new_article",
            "source_locator": "Where a draft code of conduct relates to processing activities in several Member States",
            "split": "test",
            "tasks": [
                "Receive the multi-State draft code of conduct",
                "Submit the draft code to the Board before approving it",
                "Approve the draft code, amendment or extension",
            ],
        },
        {
            "actor_required": "Certification body",
            "actor_wrong": "Supervisory authority",
            "article": 43,
            "business_scenario_en": "A certification body must inform the supervisory authority before issuing or renewing certification.",
            "business_scenario_zh": "认证机构须在签发或续期认证前告知监管机构。",
            "citation": "GDPR Article 43(1)",
            "condition_present": True,
            "condition_text": "certification bodies have an appropriate level of expertise in relation to data protection",
            "constraint_present": True,
            "constraint_text": "after informing the supervisory authority in order to allow it to exercise its powers pursuant to point (h) of Article 58(2) where necessary",
            "core_eligible": True,
            "disposition": "core",
            "eligibility_basis": {
                "incorrect_actor": "The duty is on the certification body, not on the supervisory authority.",
                "missing_action": "Article 43(1) imposes a positive duty to issue and renew certification.",
                "out_of_order": "Explicit action precedence: certification is issued or renewed 'after informing' the supervisory authority.",
            },
            "eligible_incorrect_actor": True,
            "eligible_missing_action": True,
            "eligible_out_of_order": True,
            "exception_present": False,
            "exception_text": "",
            "excerpt_mode": "sentence",
            "exposure_status": "no_prior_exposure_found",
            "has_variants_v1_legacy": False,
            "historical_development": False,
            "mandatory_index": 1,
            "modality": "obligation",
            "normative_content": "Certification body must inform the supervisory authority before issuing or renewing certification.",
            "order_evidence": "after informing the supervisory authority",
            "order_pair": [0, 1],
            "paragraph": "1",
            "r4_rule_id": None,
            "requirement_id": "R5-S8-T1",
            "review_fixes": ["added_by_bounded_source_only_order_closure"],
            "review_issues": [],
            "sample_id": None,
            "scenario_id": "S8",
            "scenario_zh": "认证机构程序",
            "source_family_id": "gdpr_art43",
            "source_family_split_basis": "same-Article family has no prior exposure and is held out as independent test",
            "source_kind": "new_article",
            "source_locator": "certification bodies which have an appropriate level of expertise",
            "split": "test",
            "tasks": [
                "Inform the supervisory authority",
                "Issue or renew the certification after informing",
                "Record the certification decision",
            ],
        },
    ])

    # Source-family split assignment (deterministic, no algorithm seed magic).
    exposed_prefixes = {
        "R5-D-01", "R5-D-02", "R5-D-03", "R5-D-04", "R5-D-05",  # R1-R4 five historical rules
        "R5-D-06", "R5-D-07", "R5-D-08", "R5-D-09", "R5-D-10", "R5-D-11", "R5-D-12",  # GDPR7 existing predictions
    }
    exposed_families: set[str] = set()
    for spec in v2["requirements"]:
        prior_prediction = spec.get("source_kind") in ("gdpr7_input", "r4_reference")
        if spec["requirement_id"] in exposed_prefixes or spec.get("historical_development") or prior_prediction:
            spec["exposure_status"] = "exposed_historical_or_existing_prediction"
            exposed_families.add(spec["source_family_id"])
    # Propagate exposure to the whole family (exact-input absence does not make a
    # family independent).
    for spec in v2["requirements"]:
        if spec["source_family_id"] in exposed_families:
            spec["split"] = "development"
            spec["exposure_status"] = "exposed_family_forced_development"
        else:
            spec["split"] = "test"
            spec["exposure_status"] = "no_prior_exposure_found"
        spec["source_family_split_basis"] = (
            "same-Article family forced to development because the family is exposed (R1-R4 rule or existing Stage2 prediction)"
            if spec["split"] == "development"
            else "same-Article family has no prior exposure and is held out as independent test"
        )
    v2["source_family_ids"] = sorted({s["source_family_id"] for s in v2["requirements"]})
    v2["exposed_source_family_ids"] = sorted(exposed_families)
    v2["independent_test_source_family_ids"] = sorted(
        {s["source_family_id"] for s in v2["requirements"] if s["split"] == "test"}
    )
    v2["cross_article_merge_review"] = {
        "default_rule": "same Article -> same source_family_id",
        "evaluated_pairs": [
            {"pair": ["gdpr_art13", "gdpr_art14"], "decision": "keep separate", "reason": "direct vs indirect collection are distinct duties with distinct exceptions (13(4) vs 14(5)); cross-reference does not merge families"},
            {"pair": ["gdpr_art35", "gdpr_art36"], "decision": "keep separate", "reason": "36(1) references a 35 DPIA but creates a distinct consultation duty"},
            {"pair": ["gdpr_art33", "gdpr_art34"], "decision": "keep separate", "reason": "supervisory-authority notification vs data-subject communication are distinct duties"},
        ],
        "ordinary_cross_references_do_not_merge_all_gdpr": True,
    }
    return v2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    v2 = build_v2_config()
    if args.write:
        V2_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        V2_CONFIG.write_text(json.dumps(v2, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        # disposition summary (full table with excerpt is produced by the builder)
        rows = []
        for spec in v2["requirements"]:
            rows.append({
                "requirement_id": spec["requirement_id"],
                "citation": spec["citation"],
                "source_family_id": spec["source_family_id"],
                "split": spec["split"],
                "disposition": spec["disposition"],
                "eligible_missing_action": spec["eligible_missing_action"],
                "eligible_incorrect_actor": spec["eligible_incorrect_actor"],
                "eligible_out_of_order": spec["eligible_out_of_order"],
                "eligibility_basis": spec["eligibility_basis"],
                "review_issues": spec["review_issues"],
                "review_fixes": spec["review_fixes"],
                "exposure_status": spec["exposure_status"],
                "source_family_split_basis": spec["source_family_split_basis"],
            })
        V2_DATA.mkdir(parents=True, exist_ok=True)
        (V2_DATA / "requirement_disposition.json").write_text(
            json.dumps({
                "schema_version": "stage3_table3_r5_requirement_disposition@2.0.0",
                "benchmark_id": BENCHMARK_ID_V2,
                "note": "per-requirement review; excerpt/context/SHA and evidence location are added by build_stage3_table3_r5_benchmark_v2.py",
                "count": len(rows),
                "rows": rows,
            }, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n")
    core = [s for s in v2["requirements"] if s["core_eligible"]]
    print(json.dumps({
        "requirements": len(v2["requirements"]),
        "core_eligible": len(core),
        "candidate": len(v2["requirements"]) - len(core),
        "ma": sum(1 for s in core if s["eligible_missing_action"]),
        "ia": sum(1 for s in core if s["eligible_incorrect_actor"]),
        "oo": sum(1 for s in core if s["eligible_out_of_order"]),
        "development": sum(1 for s in v2["requirements"] if s["split"] == "development"),
        "test": sum(1 for s in v2["requirements"] if s["split"] == "test"),
        "families": len(v2["source_family_ids"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

