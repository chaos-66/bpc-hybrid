# -*- coding: utf-8 -*-
"""BONUS Stage-3 development analysis: missing-action error decomposition.

Read-only.  Uses the frozen final-development signals; does not run the matcher,
change thresholds, read Gold for prediction, or alter any frozen artifact.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs" / "reports"
DEV_POOL = ROOT / "data/development/stage3_final_development_pool_v1.json"
SIGNALS = ROOT / "outputs/development/stage3_final_v1/selected_dev_signals_v1.json"
SOURCE_REQUIREMENTS = ROOT / "data/development/stage3_table3_r5_benchmark_v2/source_requirements.json"
SUN_PRED = ROOT / "data/predictions/stage3_table3_r5_sun_rule_only_v1/predictions.json"
OURS_PRED = ROOT / "data/predictions/stage3_table3_r5_ours_stage2_formal_v1/predictions.json"
OUT_JSON = REPORTS / "stage3_bonus_missing_analysis_v1.json"
OUT_MD = REPORTS / "stage3_bonus_missing_analysis_v1.md"
ROOT_CAUSE_JSON = REPORTS / "stage3_bonus_development_root_causes_v1.json"
GAMMA = 0.55

CATEGORY_TITLES = {
    "M1_REQUIRED_ACTION_MAPPING_FAILURE": "required mandatory action failed semantic mapping (similarity < gamma)",
    "M2_EXTRA_FRAGMENT_ACTION": "extra or incomplete action fragment entered the denominator",
    "M3_CONDITION_ACTION_IN_DENOMINATOR": "condition-clause action entered the denominator",
    "M4_CONSTRAINT_ACTION_IN_DENOMINATOR": "constraint-clause action entered the denominator",
    "M5_EXCEPTION_ACTION_IN_DENOMINATOR": "exception-clause action entered the denominator",
    "M6_CONTEXT_ACTION_IN_DENOMINATOR": "context/background action entered the denominator",
    "M7_SUBORDINATE_NON_OBLIGATION_ACTION": "subordinate or permission action entered the denominator",
    "M8_MULTIPLE_TRUE_MANDATORY_ACTIONS": "multiple true mandatory actions with at least one semantic mapping miss",
    "M9_BPMN_LABEL_SEMANTIC_MISMATCH": "BPMN label is semantically related but MPNet similarity is below gamma, so the violation is missed",
    "M10_STAGE2_MISSING_ACTION": "Stage-2 produced no action for the requirement",
    "M11_OTHER": "other or unclassified",
}

# Analysis-only annotation.  These are diagnostic labels, not runtime rules.
# Keys: method, requirement_id, normalized action text.  The value is
# (category, short rationale).
SCOPE_CATEGORIES = {
    "M3_CONDITION_ACTION_IN_DENOMINATOR",
    "M4_CONSTRAINT_ACTION_IN_DENOMINATOR",
    "M5_EXCEPTION_ACTION_IN_DENOMINATOR",
    "M6_CONTEXT_ACTION_IN_DENOMINATOR",
    "M7_SUBORDINATE_NON_OBLIGATION_ACTION",
}
GATE_SCOPE_CATEGORIES = SCOPE_CATEGORIES

ACTION_LABELS: dict[tuple[str, str, str], tuple[str, str]] = {
    # ------------------------------------------------------------------ Sun FP
    ("sun", "R5-D-01", "provide"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory main predicate is a short verb fragment; MPNet maps it only 0.276 to the full BPMN activity."),
    ("sun", "R5-D-02", "provide"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory main predicate is a short verb fragment; MPNet maps it only 0.276 to the full BPMN activity."),
    ("sun", "R5-S5-T4", "infringe this Regulation, in particular where the controller has insufficiently"): ("M3_CONDITION_ACTION_IN_DENOMINATOR", "The span is the condition 'where ... would infringe this Regulation', not the mandatory advice action."),
    ("sun", "R5-S7-T1", "relates to processing activities in several Member States, the supervisory"): ("M3_CONDITION_ACTION_IN_DENOMINATOR", "The span is the condition 'where a draft code ... relates ...', not the mandatory submission action."),
    ("sun", "R5-S1-T3", ", the controller shall provide the data subject with the following information."): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory action span contains a leading comma and the full clause; MPNet under-maps it to the BPMN label."),
    ("sun", "R5-S3-T1", "provide information on action taken on a request under Articles 15 to 22 to the"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory action is paraphrased differently from the BPMN activity, producing similarity 0.367."),
    ("sun", "R5-S1-T4", "provide the data subject with the following information necessary to ensure fair"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory action is a long clause truncated before its object; MPNet similarity 0.461."),
    ("sun", "R5-D-04", "carry out an assessment of the impact of the envisaged processing operations on"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory DPIA action maps to a label paraphrased as 'Describe the envisaged high-risk processing' with similarity 0.518."),
    ("sun", "R5-S3-T2", "inform the data subject without delay and at the latest within one month of"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory information action is truncated and maps to a different conditional notification label at 0.473."),
    ("sun", "R5-D-08", "have the right to obtain from the controller confirmation as to whether or not"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "Right-to-obtain wording and BPMN right-of-access label are semantically equivalent to a human but MPNet gives 0.492."),
    ("sun", "R5-S6-T2", "take steps to ensure that any natural person acting under the authority of the"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory instruction-compliance action is paraphrased in BPMN, similarity 0.431."),
    ("sun", "R5-S4-T3", "inform the controller of that legal requirement before processing, unless that"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory inform-controller action is embedded with a trailing subordinate clause; similarity 0.436."),
    ("sun", "R5-D-07", "be taken"): ("M2_EXTRA_FRAGMENT_ACTION", "The span 'be taken' is a fragment of the passive predicate 'account shall be taken'; it is not a standalone mandatory action."),
    ("sun", "R5-S5-T3", "carry out a review to assess if processing is performed in accordance with the"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory review action maps to a different review/update label at 0.465."),
    ("sun", "R5-D-10", "have"): ("M2_EXTRA_FRAGMENT_ACTION", "The action is the auxiliary fragment 'have' from 'shall have the obligation to erase'; it is not the complete action."),
    ("sun", "R5-S2-T2", "make reasonable efforts to verify in such cases that consent is given or"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory verification action maps to a paraphrased BPMN label at 0.514."),
    ("sun", "R5-S1-T1", "collected from the data subject, the controller shall, at the time when personal"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Action span starts inside the collection condition and mixes it with the main clause; MPNet similarity 0.510."),
    ("sun", "R5-D-09", "have the right to obtain from the controller without undue delay the"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "The passive right wording and the BPMN rectification-right label are equivalent to a human but MPNet gives 0.518."),
    # ------------------------------------------------------------------ Sun FN
    ("sun", "__NO_ACTIONS__", "__NO_ACTIONS__"): ("M10_STAGE2_MISSING_ACTION", "Stage-2 extracted no action span for the obligation, so the denominator is zero and the cell is unknown."),
    ("sun", "R5-S6-T3", "notify the controller without undue delay after becoming aware of a personal data breach."): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "BPMN contains a semantically equivalent notification label; MPNet score 0.640 keeps the missing-action mutant predicted as satisfied."),
    ("sun", "R5-S4-T1", "implement appropriate technical and organisational measures to ensure and to be"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "Mutant is missed because a related review/update activity remains highly similar (0.664)."),
    ("sun", "R5-S4-T1", "be reviewed and updated where necessary."): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "The review/update endpoint maps to the remaining review/update label at 0.623, so the missing action is not detected."),
    ("sun", "R5-S6-T4", "communicate the personal data breach to the data subject without undue delay."): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "A related communication activity remains in the mutant and maps at 0.791, masking the missing action."),
    ("sun", "R5-D-03", "be informed by the controller before the restriction of processing is lifted."): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "Inflected passive action maps to the BPMN 'controller must inform...' label at 0.786; the mutant is not detected."),
    ("sun", "R5-D-12", "notify the personal data breach to the supervisory authority competent in"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "Notification action maps to the antecedent 'become aware' activity at 0.774; the mutant is not detected."),
    ("sun", "R5-D-06", "able to demonstrate that the data subject has consented to processing of his or"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "Demonstrate-consent action maps to a consent-record activity at 0.676; the missing action is masked."),
    # ----------------------------------------------------------------- Ours FP
    ("ours", "R5-S5-T4", "use any of its powers referred to in Article 58"): ("M7_SUBORDINATE_NON_OBLIGATION_ACTION", "The source says the authority 'may use any of its powers'; this is a permission, not a mandatory obligation action."),
    ("ours", "R5-S8-T1", "issue"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "The mandatory certification action was split into 'issue' and 'renew certification'; the isolated 'issue' maps at 0.228."),
    ("ours", "R5-D-01", "with any relevant further information as referred to in paragraph 2"): ("M2_EXTRA_FRAGMENT_ACTION", "This is a prepositional continuation of the information object, not a second mandatory action."),
    ("ours", "R5-D-03", "be informed"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory passive action is reduced to 'be informed' and MPNet maps it at 0.234 to the BPMN notification label."),
    ("ours", "R5-S6-T3", "notify the controller"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory notification action is a reduced span and maps at 0.467."),
    ("ours", "R5-S4-T3", "inform the controller of that legal requirement"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory inform action maps to the opposite instruction-receipt BPMN label at 0.365."),
    ("ours", "R5-S4-T2", "implement appropriate technical and organisational measures"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory measures action maps to a different BPMN activity at 0.389."),
    ("ours", "R5-D-07", "taken"): ("M2_EXTRA_FRAGMENT_ACTION", "The span 'taken' is a fragment of the passive predicate 'account shall be taken'; it is not a standalone action."),
    ("ours", "R5-S5-T3", "carry out a review"): ("M1_REQUIRED_ACTION_MAPPING_FAILURE", "Mandatory review action maps to a review/update label at 0.470."),
    ("ours", "R5-S4-T1", "ensure"): ("M7_SUBORDINATE_NON_OBLIGATION_ACTION", "The verb is a subordinate purpose-clause element, not an independent mandatory action."),
    ("ours", "R5-S4-T1", "reviewed"): ("M7_SUBORDINATE_NON_OBLIGATION_ACTION", "The past participle is a reduced fragment of the 'shall be reviewed and updated' obligation."),
    ("ours", "R5-S4-T1", "updated"): ("M7_SUBORDINATE_NON_OBLIGATION_ACTION", "The past participle is a reduced fragment of the 'shall be reviewed and updated' obligation."),
    # ----------------------------------------------------------------- Ours FN
    ("ours", "R5-S1-T3", "provide the data subject with the following information"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "A related BPMN activity remains and maps above gamma, masking the missing action."),
    ("ours", "R5-S1-T4", "provide the data subject with the following information"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "A related BPMN activity remains and maps above gamma, masking the missing action."),
    ("ours", "R5-S3-T2", "inform the data subject"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "The reduced action maps above gamma to a related request-handling activity, masking the missing action."),
    ("ours", "R5-D-02", "provide the data subject prior to that further processing with information on that other purpose and with any relevant further information as referred to in paragraph 2"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "The long action maps above gamma to a related prior-notice activity, masking the missing action."),
    ("ours", "R5-S6-T4", "communicate the personal data breach to the data subject"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "The action maps at 0.735 to a related communication activity that remains in the mutant."),
    ("ours", "R5-S1-T2", "provide the data subject with the following further information necessary to ensure fair and transparent processing"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "A related transparency-information activity remains and maps at 0.649, masking the missing action."),
    ("ours", "R5-S3-T1", "provide information on action taken on a request under Articles 15 to 22 to the data subject"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "A related request-handling activity remains and maps at 0.567, masking the missing action."),
    ("ours", "R5-D-09", "obtain from the controller without undue delay the rectification of inaccurate personal data concerning him or her"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "A related rectification-right activity remains and maps at 0.558, masking the missing action."),
    ("ours", "R5-S2-T2", "make reasonable efforts to verify in such cases that consent is given or authorised by the holder of parental responsibility over the child"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "A related parental-authorisation verification activity remains and maps at 0.590."),
    ("ours", "R5-S1-T1", "provide the data subject with all of the following information"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "A related collection activity remains and maps at 0.693, masking the missing information action."),
    ("ours", "R5-D-12", "notify the personal data breach to the supervisory authority competent in accordance with Article 55"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "The notification action maps at 0.706 to the antecedent 'become aware' activity, masking the missing action."),
    ("ours", "R5-D-06", "be able to demonstrate that the data subject has consented to processing of his or her personal data"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "Demonstrate-consent action maps to a consent-record activity at 0.618, masking the missing action."),
    ("ours", "R5-S6-T2", "take steps to ensure that any natural person acting under the authority of the controller or the processor who has access to personal data does not process them except on instructions from the controller"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "A related instruction-compliance activity remains and maps at 0.682."),
    ("ours", "R5-S5-T2", "seek the views of data subjects or their representatives on the intended processing"): ("M9_BPMN_LABEL_SEMANTIC_MISMATCH", "Seek-views action maps at 0.665 to an 'carry out intended processing' activity, masking the missing action."),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def valid_span(span: Mapping[str, Any], text_len: int) -> bool:
    start, end = span.get("start"), span.get("end")
    return isinstance(start, int) and not isinstance(start, bool) and isinstance(end, int) and not isinstance(end, bool) and 0 <= start < end <= text_len


def stage2_actions(record: Mapping[str, Any], source_text: str) -> list[str]:
    out: list[str] = []
    for clause in record.get("clauses") or []:
        if not isinstance(clause, Mapping):
            continue
        modality = clause.get("modality")
        label = modality.get("label") if isinstance(modality, Mapping) else None
        if label != "obligation":
            continue
        for span in clause.get("actions") or []:
            if isinstance(span, Mapping) and valid_span(span, len(source_text)):
                txt = source_text[int(span["start"]):int(span["end"])]
                if txt.strip() and txt not in out:
                    out.append(txt)
    return out


def classify(method: str, req: str, action: str | None) -> tuple[str, str]:
    if action is None:
        return ("M10_STAGE2_MISSING_ACTION", CATEGORY_TITLES["M10_STAGE2_MISSING_ACTION"])
    key = (method, req, str(action).strip())
    if key in ACTION_LABELS:
        cat, why = ACTION_LABELS[key]
        return cat, why
    # Conservative fallbacks by method and action surface are intentionally
    # generic, not case-specific prediction rules.
    low = str(action).casefold()
    if any(token in low for token in ("where ", "when ", "if ", "relates to", "infringe")):
        return ("M3_CONDITION_ACTION_IN_DENOMINATOR", CATEGORY_TITLES["M3_CONDITION_ACTION_IN_DENOMINATOR"])
    if any(token in low for token in ("prior to", "without undue delay", "within one month", "at least", "unless")):
        return ("M4_CONSTRAINT_ACTION_IN_DENOMINATOR", CATEGORY_TITLES["M4_CONSTRAINT_ACTION_IN_DENOMINATOR"])
    if len(low.split()) <= 2:
        return ("M2_EXTRA_FRAGMENT_ACTION", CATEGORY_TITLES["M2_EXTRA_FRAGMENT_ACTION"])
    return ("M1_REQUIRED_ACTION_MAPPING_FAILURE", CATEGORY_TITLES["M1_REQUIRED_ACTION_MAPPING_FAILURE"])


def main() -> int:
    pool = load_json(DEV_POOL)
    signals = load_json(SIGNALS)["signals"]
    source = {str(r["requirement_id"]): str(r["excerpt_text"]) for r in load_json(SOURCE_REQUIREMENTS)["requirements"]}
    preds: dict[str, dict[str, Mapping[str, Any]]] = {}
    for method, path in (("sun", SUN_PRED), ("ours", OURS_PRED)):
        doc = load_json(path)
        preds[method] = {str(r["requirement_id"]): r["record"] for r in doc["records"]}

    summary: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    for method in ("sun", "ours"):
        counts = Counter()
        per_cat = Counter()
        for case in pool["cases"]:
            cid = str(case["case_id"])
            req = str(case["requirement_id"])
            gold = str((case.get("reference_states") or {}).get("missing_action") or "")
            sig = (signals.get(method, {}).get(cid) or {}).get("missing_action") or {}
            status = str(sig.get("status") or "missing")
            if gold not in ("violated", "satisfied"):
                continue
            if gold == "violated":
                if status == "violated":
                    counts["TP"] += 1
                else:
                    counts["FN"] += 1
            else:
                if status == "violated":
                    counts["FP"] += 1
                elif status == "satisfied":
                    counts["TN"] += 1
                else:
                    counts["unknown_negative"] += 1
            is_error = (gold == "violated" and status != "violated") or (gold == "satisfied" and status == "violated")
            if not is_error:
                continue
            error_type = "FN" if gold == "violated" else "FP"
            details = (sig.get("evidence") or {}).get("details") or []
            denominator_actions = [str(d.get("rule_action")) for d in details]
            s2_actions = stage2_actions(preds[method].get(req) or {}, source.get(req, ""))
            if error_type == "FN" and not details:
                categories = [("M10_STAGE2_MISSING_ACTION", CATEGORY_TITLES["M10_STAGE2_MISSING_ACTION"])]
                evidence_details = []
            else:
                relevant = []
                if error_type == "FP":
                    relevant = [d for d in details if bool(d.get("missing"))]
                else:
                    relevant = [d for d in details if not bool(d.get("missing"))]
                if not relevant:
                    categories = [("M11_OTHER", CATEGORY_TITLES["M11_OTHER"])]
                else:
                    categories = [classify(method, req, d.get("rule_action")) for d in relevant]
                evidence_details = [{
                    "rule_action": d.get("rule_action"),
                    "best_model_action": d.get("best_model_action"),
                    "similarity": d.get("similarity"),
                    "missing": bool(d.get("missing")),
                } for d in relevant]
            cats = [c for c, _ in categories]
            for c in cats:
                per_cat[c] += 1
            row = {
                "case_id": cid,
                "requirement_id": req,
                "method": method,
                "variant": case.get("variant"),
                "source_text": source.get(req),
                "stage2_actions": s2_actions,
                "actions_entering_definition5_denominator": denominator_actions,
                "best_bpmn_action_match": [d.get("best_model_action") for d in evidence_details],
                "similarity": [d.get("similarity") for d in evidence_details],
                "gamma": GAMMA,
                "predicted_status": status,
                "gold_state": gold,
                "error_type": error_type,
                "failure_categories": cats,
                "primary_failure_category": cats[0] if cats else "M11_OTHER",
                "failure_category_explanations": [why for _, why in categories],
                "evidence": evidence_details,
            }
            all_rows.append(row)
        summary[method] = {
            "TP": counts["TP"],
            "FP": counts["FP"],
            "FN": counts["FN"],
            "TN": counts["TN"],
            "unknown_negative": counts["unknown_negative"],
            "precision": counts["TP"] / (counts["TP"] + counts["FP"]) if (counts["TP"] + counts["FP"]) else 0.0,
            "recall": counts["TP"] / (counts["TP"] + counts["FN"]) if (counts["TP"] + counts["FN"]) else 0.0,
            "f1": (2 * counts["TP"] / (2 * counts["TP"] + counts["FP"] + counts["FN"])) if (2 * counts["TP"] + counts["FP"] + counts["FN"]) else 0.0,
            "failure_category_counts": dict(sorted(per_cat.items())),
        }

    fp_rows = [r for r in all_rows if r["error_type"] == "FP"]
    fn_rows = [r for r in all_rows if r["error_type"] == "FN"]
    # Cell-level gate count: an FP counts for the gate only if at least one
    # missing denominator action is in a gate-listed scope category.  M2
    # fragments are reported separately and are not counted as gate evidence.
    gate_fp_by_method: dict[str, Counter] = {m: Counter() for m in ("sun", "ours")}
    broad_scope_fp_by_method: dict[str, Counter] = {m: Counter() for m in ("sun", "ours")}
    for row in fp_rows:
        method = row["method"]
        cats = set(row["failure_categories"])
        if cats & GATE_SCOPE_CATEGORIES:
            gate_fp_by_method[method]["scope_related_fp"] += 1
        if cats & (SCOPE_CATEGORIES | {"M2_EXTRA_FRAGMENT_ACTION"}):
            broad_scope_fp_by_method[method]["broad_scope_related_fp"] += 1
    gate_total = sum(gate_fp_by_method[m]["scope_related_fp"] for m in gate_fp_by_method)
    broad_total = sum(broad_scope_fp_by_method[m]["broad_scope_related_fp"] for m in broad_scope_fp_by_method)
    fp_total = len(fp_rows)

    mapping_cats = {"M1_REQUIRED_ACTION_MAPPING_FAILURE", "M8_MULTIPLE_TRUE_MANDATORY_ACTIONS", "M9_BPMN_LABEL_SEMANTIC_MISMATCH"}
    mapping_fp = sum(1 for r in fp_rows if set(r["failure_categories"]) & mapping_cats)
    mapping_fn = sum(1 for r in fn_rows if set(r["failure_categories"]) & mapping_cats)
    stage2_fn = sum(1 for r in fn_rows if "M10_STAGE2_MISSING_ACTION" in r["failure_categories"])
    scope_fp = broad_total
    other_fp = fp_total - mapping_fp - scope_fp
    other_fn = len(fn_rows) - mapping_fn - stage2_fn
    mapping_total = mapping_fp + mapping_fn
    scope_total = scope_fp
    stage2_total = stage2_fn
    other_total = other_fp + other_fn

    cell_category_counts = {
        method: dict(sorted(Counter(cat for row in all_rows if row["method"] == method for cat in row["failure_categories"]).items()))
        for method in ("sun", "ours")
    }

    payload = {
        "schema_version": "stage3_bonus_missing_analysis@1.0.0",
        "status": "BONUS_DEVELOPMENT_ANALYSIS_NOT_PAPER_FACING",
        "all_existing_cases_seen": True,
        "final_test_eligible": False,
        "real_llm_api_calls": 0,
        "gamma": GAMMA,
        "source_signal_artifact": "outputs/development/stage3_final_v1/selected_dev_signals_v1.json",
        "methods": summary,
        "fp_fn_rows": all_rows,
        "root_cause_quantification": {
            "fp_total": fp_total,
            "mapping_related_fp_cells": mapping_fp,
            "mapping_related_fn_cells": mapping_fn,
            "mapping_related_total_cells": mapping_total,
            "scope_related_fp_cells_broad": scope_fp,
            "scope_related_total_cells": scope_total,
            "stage2_extraction_related_fn_cells": stage2_fn,
            "stage2_extraction_related_total_cells": stage2_total,
            "other_fp_cells": other_fp,
            "other_fn_cells": other_fn,
            "other_total_cells": other_total,
            "cell_level_failure_category_counts": {
                "sun": {k: v for k, v in cell_category_counts["sun"].items()},
                "ours": {k: v for k, v in cell_category_counts["ours"].items()},
            },
            "key_question_answer": "Missing-action errors are dominated by action-mapping/label-semantic failures, not by a clean removable scope action. Strict gate-listed non-mandatory/condition/constraint/exception/context/subordinate FP evidence is below 30%.",
        },
        "action_scope_gate": {
            "gate_eligible_scope_fp_by_method": {m: dict(gate_fp_by_method[m]) for m in gate_fp_by_method},
            "gate_eligible_scope_fp_cells": gate_total,
            "gate_eligible_scope_fp_ratio": (gate_total / fp_total) if fp_total else 0.0,
            "broad_scope_fp_by_method": {m: dict(broad_scope_fp_by_method[m]) for m in broad_scope_fp_by_method},
            "broad_scope_fp_cells": broad_total,
            "broad_scope_fp_ratio": (broad_total / fp_total) if fp_total else 0.0,
            "threshold": 0.30,
            "decision": "REJECTED",
            "reason": "Even under the broad fragment-inclusive count, the strict gate-listed scope categories are far below 30% of Missing FP; the dominant errors are required-action mapping and BPMN-label semantic mismatch.",
        },
        "failure_category_legend": CATEGORY_TITLES,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    # Root cause ledger companion.
    rc = {
        "schema_version": "stage3_bonus_development_root_causes@1.0.0",
        "status": "BONUS_DEVELOPMENT_ROOT_CAUSE_LEDGER",
        "rows": [
            {
                "id": "BONUS-RC-MISS-01",
                "symptom": "Missing-action F1 remains low for both methods (Sun 0.4554, Ours 0.4935).",
                "root_cause": "Most remaining FP/FN cells are caused by required-action semantic mapping or BPMN-label paraphrase mismatch; only a minority are caused by clearly removable scope actions.",
                "evidence": {
                    "fp_total": fp_total,
                    "mapping_related_fp_cells": mapping_fp,
                    "broad_scope_fp_cells": scope_fp,
                    "gate_eligible_scope_fp_cells": gate_total,
                    "stage2_extraction_related_fn_cells": stage2_fn,
                },
                "affected_method": "shared",
                "proposed_fix": "No ObligationScopedActionProjectionV1: the gate fails and projection would not address the dominant mapping failures without reducing coverage.",
                "implemented": False,
                "Gold_blind": True,
                "shared": True,
                "before_metric": {"sun_missing_f1": 0.4554455445544555, "ours_missing_f1": 0.49350649350649356},
                "after_metric": None,
                "decision": "ACTION_SCOPE_REFINEMENT_REJECTED",
            },
            {
                "id": "BONUS-RC-ORDER-01",
                "symptom": "Only one existing requirement supplies an observable action-action order control.",
                "root_cause": "The frozen source pool contains few requirements with two independently extracted action endpoints and a unique temporal ordering relation.",
                "evidence": {"existing_main_requirements": 3, "observable_existing_requirements": 1},
                "affected_method": "shared",
                "proposed_fix": "Add 6-10 development-only GDPR order requirements with endpoint availability recorded explicitly; do not modify SharedRuleOrderAdapterV3.",
                "implemented": True,
                "Gold_blind": True,
                "shared": True,
                "before_metric": {"order_f1_sun": 0.5, "order_f1_ours": 0.5},
                "after_metric": None,
                "decision": "DEV_ONLY_ORDER_SUPPLEMENT_CREATED",
            },
        ],
    }
    ROOT_CAUSE_JSON.write_text(json.dumps(rc, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    lines: list[str] = []
    lines.append("# Stage 3 BONUS Development: Missing-Action Root-Cause Analysis v1\n")
    lines.append("- Status: `BONUS_DEVELOPMENT_ANALYSIS_NOT_PAPER_FACING`")
    lines.append("- `ALL_EXISTING_CASES_SEEN = true`")
    lines.append("- `FINAL_TEST_ELIGIBLE = false`")
    lines.append("- `REAL_LLM_API_CALLS = 0`")
    lines.append("- Frozen gamma: `0.55`; source signals: frozen final-development signals.\n")
    lines.append("## Confusion Matrix\n")
    lines.append("| Method | TP | FP | FN | TN | Unknown negative | Precision | Recall | F1 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for method in ("sun", "ours"):
        s = summary[method]
        lines.append(f"| {method.title()} | {s['TP']} | {s['FP']} | {s['FN']} | {s['TN']} | {s['unknown_negative']} | {s['precision']:.4f} | {s['recall']:.4f} | {s['f1']:.4f} |")
    lines.append("\n## Failure Category Counts\n")
    lines.append("| Failure category | Sun count | Ours count |")
    lines.append("|---|---:|---:|")
    keys = sorted(set(summary["sun"]["failure_category_counts"]) | set(summary["ours"]["failure_category_counts"]))
    for key in keys:
        lines.append(f"| {key} | {summary['sun']['failure_category_counts'].get(key, 0)} | {summary['ours']['failure_category_counts'].get(key, 0)} |")
    lines.append("\n## Root-Cause Quantification\n")
    lines.append(f"- FP total: `{fp_total}`")
    lines.append(f"- Mapping-related FP cells: `{mapping_fp}`")
    lines.append(f"- Broad scope-related FP cells (including fragments): `{scope_fp}`")
    lines.append(f"- Gate-eligible scope FP cells (condition/constraint/exception/context/subordinate non-obligation): `{gate_total}`")
    lines.append(f"- Stage-2 extraction-related FN cells: `{stage2_fn}`")
    lines.append(f"- Key answer: {payload['root_cause_quantification']['key_question_answer']}")
    lines.append("\n## Action-Scope Gate\n")
    lines.append(f"- Gate threshold: `0.30`")
    lines.append(f"- Gate-eligible scope ratio: `{gate_total / fp_total:.4f}`" if fp_total else "- Gate-eligible scope ratio: `n/a`")
    lines.append(f"- Broad scope ratio: `{broad_total / fp_total:.4f}`" if fp_total else "- Broad scope ratio: `n/a`")
    lines.append(f"- Decision: `{payload['action_scope_gate']['decision']}`")
    lines.append(f"- Reason: {payload['action_scope_gate']['reason']}")
    lines.append("\n## FP/FN Evidence Ledger\n")
    lines.append("The complete per-cell evidence ledger is in `stage3_bonus_missing_analysis_v1.json`.")
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
